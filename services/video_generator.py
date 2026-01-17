import asyncio
import httpx
from supabase import create_client
from core.config import (
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY,
    AZURE_SPEECH_KEY,
    AZURE_SPEECH_REGION,
)

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

API_VERSION = "2024-08-01"


def _extract_video_script(script_text: str) -> str:
    marker = "VIDEO SCRIPT:"
    if marker in script_text:
        return script_text.split(marker, 1)[1].split("AUDIO SCRIPT:", 1)[0].strip()
    return script_text.strip()


def _to_ssml(text: str) -> str:
    # Keep it simple; you can map voice using lectures.avatar_voice later.
    return f"""
<speak version='1.0' xml:lang='en-US'>
  <voice name='en-US-AvaMultilingualNeural'>
    {text}
  </voice>
</speak>
""".strip()


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
    text = _extract_video_script(script_text)
    if not text:
        raise RuntimeError("No text found for video generation")

    # Must be 3-64 chars, letters/numbers/-/_, start+end with alnum
    synthesis_id = f"{lecture_id}-avatar".replace("_", "-")
    synthesis_id = synthesis_id[:64]
    if not synthesis_id[-1].isalnum():
        synthesis_id = synthesis_id.rstrip("-_") + "0"

    base = f"https://{AZURE_SPEECH_REGION}.api.cognitive.microsoft.com"
    put_url = f"{base}/avatar/batchsyntheses/{synthesis_id}?api-version={API_VERSION}"
    get_url = f"{base}/avatar/batchsyntheses/{synthesis_id}?api-version={API_VERSION}"

    headers = {
        "Ocp-Apim-Subscription-Key": str(AZURE_SPEECH_KEY),
        "Content-Type": "application/json",
    }

    payload = {
        "inputKind": "SSML",
        "inputs": [{"content": _to_ssml(text)}],
        "avatarConfig": {
            "talkingAvatarCharacter": avatar_character,
            "talkingAvatarStyle": avatar_style,
            # Optional: you can set other properties (bitrate, backgroundColor, etc.)
        },
    }

    async with httpx.AsyncClient(timeout=180) as client:
        # Create/replace synthesis job
        r = await client.put(put_url, headers=headers, json=payload)
        r.raise_for_status()

        # Poll until finished
        status = "NotStarted"
        outputs_result_url = None

        # Progress stepping: NotStarted->10, Running->50..90, Succeeded->100
        running_ticks = 0

        while True:
            gr = await client.get(get_url, headers={"Ocp-Apim-Subscription-Key": str(AZURE_SPEECH_KEY)})
            gr.raise_for_status()
            data = gr.json()

            status = data.get("status") or status

            if status in ("Succeeded", "Failed"):
                outputs = data.get("outputs") or {}
                outputs_result_url = outputs.get("result")
                if status == "Failed":
                    # Some failures expose info in outputs.summary; we return best message we can.
                    raise RuntimeError(f"Azure avatar batch synthesis failed: {data}")
                break

            # optional job progress updates in Supabase
            if job_id:
                running_ticks += 1
                approx = 50 + min(40, running_ticks * 5)  # 55,60,... up to 90
                supabase.table("lecture_jobs").update({"progress": approx, "status": "running"}).eq("id", job_id).execute()

            await asyncio.sleep(2)

        if not outputs_result_url:
            raise RuntimeError("Azure returned Succeeded but no outputs.result URL found")

        # Download mp4 (doc shows adding key header; we include it)
        vr = await client.get(outputs_result_url, headers={"Ocp-Apim-Subscription-Key": str(AZURE_SPEECH_KEY)})
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
