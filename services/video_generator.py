import asyncio
import re
from xml.sax.saxutils import escape

import httpx
from supabase import create_client

from core.config import (
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY,
    AZURE_SPEECH_KEY,
    AZURE_SPEECH_REGION,
)

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

_TAG_RE = re.compile(r"<[^>]+>")
API_VERSION = "2024-08-01"

# Avatar endpoint is much more reliable with Jenny than Ava
AVATAR_VOICE_NAME = "en-US-JennyMultilingualNeural"


def _sanitize_for_ssml(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    text = _TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return escape(text, entities={'"': "&quot;", "'": "&apos;"})


def _extract_video_script(script_text: str) -> str:
    marker = "VIDEO SCRIPT:"
    if isinstance(script_text, str) and marker in script_text:
        return script_text.split(marker, 1)[1].split("AUDIO SCRIPT:", 1)[0].strip()
    return (script_text or "").strip()


def _to_ssml(text: str) -> str:
    safe_text = _sanitize_for_ssml(text)[:8000]
    return f"""<speak version="1.0" xml:lang="en-US">
<voice name="{AVATAR_VOICE_NAME}">
{safe_text}
</voice>
</speak>"""


async def generate_video_avatar_and_upload(
    lecture_id: str,
    educator_id: str,
    script_text: str,
    avatar_character: str,
    avatar_style: str,
    job_id: str | None = None,
) -> tuple[str, str]:
    """
    Creates Azure batch avatar synthesis, polls until done, downloads mp4, uploads to Supabase.

    Returns:
        (public_url, storage_path)
    """
    if not avatar_character or not avatar_style:
        raise RuntimeError("Missing avatar_character/avatar_style (Step 5).")

    if not isinstance(AZURE_SPEECH_KEY, str) or not AZURE_SPEECH_KEY.strip():
        raise RuntimeError("AZURE_SPEECH_KEY is missing/invalid")
    if not isinstance(AZURE_SPEECH_REGION, str) or not AZURE_SPEECH_REGION.strip():
        raise RuntimeError("AZURE_SPEECH_REGION is missing/invalid")

    text = _extract_video_script(script_text)
    if not text:
        raise RuntimeError("No text found for video generation (VIDEO SCRIPT is empty)")

    # Must be 3-64 chars, letters/numbers/-/_, start+end with alnum
    synthesis_id = f"{lecture_id}-avatar".replace("_", "-")[:64]
    if not synthesis_id[-1].isalnum():
        synthesis_id = synthesis_id.rstrip("-_") + "0"

    base = f"https://{AZURE_SPEECH_REGION.strip()}.api.cognitive.microsoft.com"
    put_url = f"{base}/avatar/batchsyntheses/{synthesis_id}?api-version={API_VERSION}"
    get_url = f"{base}/avatar/batchsyntheses/{synthesis_id}?api-version={API_VERSION}"

    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY.strip(),
        "Content-Type": "application/json",
    }

    payload = {
        "inputKind": "SSML",
        "inputs": [{"content": _to_ssml(text)}],
        "avatarConfig": {
            "talkingAvatarCharacter": avatar_character,
            "talkingAvatarStyle": avatar_style,
            "videoFormat": "Mp4",
            "videoCodec": "h264",
            "subtitleType": "none",
        },
    }

    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.put(put_url, headers=headers, json=payload)
        r.raise_for_status()

        running_ticks = 0
        outputs_result_url = None

        while True:
            gr = await client.get(
                get_url,
                headers={"Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY.strip()},
            )
            gr.raise_for_status()
            data = gr.json()

            status = data.get("status")

            if status in ("Succeeded", "Failed"):
                outputs = data.get("outputs") or {}
                outputs_result_url = outputs.get("result")

                if status == "Failed":
                    raise RuntimeError(f"Azure avatar batch synthesis failed: {data}")
                break

            if job_id:
                running_ticks += 1
                approx = 50 + min(40, running_ticks * 5)
                supabase.table("lecture_jobs").update({"progress": approx, "status": "running"}).eq("id", job_id).execute()

            await asyncio.sleep(2)

        if not outputs_result_url:
            raise RuntimeError("Azure returned Succeeded but no outputs.result URL found")

        vr = await client.get(
            outputs_result_url,
            headers={"Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY.strip()},
        )
        vr.raise_for_status()
        video_bytes = vr.content

    storage_path = f"{educator_id}/{lecture_id}/artifacts/video_avatar.mp4"

    supabase.storage.from_("lecture-assets").upload(
        storage_path,
        video_bytes,
        file_options={
            "content-type": "video/mp4",
            "x-upsert": "true",
        },
    )

    public_url = supabase.storage.from_("lecture-assets").get_public_url(storage_path)
    return public_url, storage_path
