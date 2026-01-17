import httpx
from supabase import create_client
from core.config import SUPABASE_URL, SUPABASE_SERVICE_KEY, AZURE_SPEECH_KEY, AZURE_SPEECH_REGION

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def _extract_audio_script(script_text: str) -> str:
    """
    Prefer AUDIO SCRIPT section, fallback to whole script.
    """
    marker = "AUDIO SCRIPT:"
    if marker in script_text:
        return script_text.split(marker, 1)[1].strip()
    return script_text.strip()


async def generate_audio_tts_and_upload(lecture_id: str, educator_id: str, script_text: str) -> str:
    """
    Generates MP3 via Azure TTS and uploads to Supabase Storage.
    Returns public URL of uploaded MP3.
    """
    # Validate env at runtime (prevents silent bool/None issues)
    if not isinstance(AZURE_SPEECH_KEY, str) or not AZURE_SPEECH_KEY.strip():
        raise RuntimeError(f"AZURE_SPEECH_KEY invalid: type={type(AZURE_SPEECH_KEY)} value={AZURE_SPEECH_KEY}")
    if not isinstance(AZURE_SPEECH_REGION, str) or not AZURE_SPEECH_REGION.strip():
        raise RuntimeError(f"AZURE_SPEECH_REGION invalid: type={type(AZURE_SPEECH_REGION)} value={AZURE_SPEECH_REGION}")

    text = _extract_audio_script(script_text)
    if not text:
        raise RuntimeError("No text found for audio generation")

    tts_url = f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
        "User-Agent": "genai-ed-backend",
    }
    # Ensure httpx headers are always str/bytes (prevents bool header crash)
    headers = {k: str(v) for k, v in headers.items() if v is not None}

    # Simple SSML first (later: map voice from DB)
    ssml = f"""
<speak version='1.0' xml:lang='en-US'>
  <voice xml:lang='en-US' name='en-US-AvaMultilingualNeural'>
    {text}
  </voice>
</speak>
""".strip()

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(tts_url, headers=headers, content=ssml.encode("utf-8"))
        r.raise_for_status()
        audio_bytes = r.content

    storage_path = f"{educator_id}/{lecture_id}/artifacts/audio.mp3"

    # Upload bytes to Supabase storage
    try:
        supabase.storage.from_("lecture-assets").upload(
            storage_path,
            audio_bytes,
            {"content-type": "audio/mpeg", "upsert": True},
        )
    except Exception as e:
        raise RuntimeError(f"Failed to upload audio to storage: {e}")

    public = supabase.storage.from_("lecture-assets").get_public_url(storage_path)
    return public
