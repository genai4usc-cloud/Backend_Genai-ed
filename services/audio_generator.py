import httpx
from supabase import create_client
from core.config import SUPABASE_URL, SUPABASE_SERVICE_KEY, AZURE_SPEECH_KEY, AZURE_SPEECH_REGION

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def _extract_audio_script(script_text: str) -> str:
    marker = "AUDIO SCRIPT:"
    if marker in script_text:
        return script_text.split(marker, 1)[1].strip()
    return script_text.strip()


async def generate_audio_tts_and_upload(
    lecture_id: str,
    educator_id: str,
    script_text: str,
    voice_name: str = "en-US-AvaMultilingualNeural",
) -> tuple[str, str]:
    """
    Generates TTS audio using Azure Speech and uploads to Supabase Storage.

    Returns:
        (public_url, storage_path)
    """
    # ---- Validate inputs / config early (prevents confusing httpx header errors) ----
    if not isinstance(AZURE_SPEECH_KEY, str) or not AZURE_SPEECH_KEY.strip():
        raise RuntimeError(f"AZURE_SPEECH_KEY is missing/invalid (type={type(AZURE_SPEECH_KEY)})")
    if not isinstance(AZURE_SPEECH_REGION, str) or not AZURE_SPEECH_REGION.strip():
        raise RuntimeError(f"AZURE_SPEECH_REGION is missing/invalid (type={type(AZURE_SPEECH_REGION)})")

    text = _extract_audio_script(script_text)
    if not text:
        raise RuntimeError("No text found for audio generation")

    tts_url = f"https://{AZURE_SPEECH_REGION.strip()}.tts.speech.microsoft.com/cognitiveservices/v1"

    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY.strip(),
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
        "User-Agent": "genai-ed-backend",
    }
    # Ensure headers are always strings (httpx requirement)
    headers = {k: str(v) for k, v in headers.items() if v is not None}

    # NOTE: Azure Speech expects valid SSML; we keep it simple and robust.
    ssml = f"""
<speak version="1.0" xml:lang="en-US">
  <voice name="{voice_name}">
    {text}
  </voice>
</speak>
""".strip()

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(tts_url, headers=headers, content=ssml.encode("utf-8"))
        r.raise_for_status()
        audio_bytes = r.content

    storage_path = f"{educator_id}/{lecture_id}/artifacts/audio.mp3"

    # Use file_options with x-upsert string to match your ppt/video uploads
    supabase.storage.from_("lecture-assets").upload(
        path=storage_path,
        file=audio_bytes,
        file_options={
            "content-type": "audio/mpeg",
            "x-upsert": "true",
        },
    )

    public_url = supabase.storage.from_("lecture-assets").get_public_url(storage_path)
    return public_url, storage_path
