import os
from dotenv import load_dotenv

load_dotenv()  # loads .env from project root

def env(name: str, default: str | None = None) -> str | None:
    """
    Always returns a stripped string or None.
    Never returns bool/int etc. (prevents header type errors).
    """
    v = os.getenv(name, default)
    if v is None:
        return None
    return str(v).strip()

# -----------------------
# Supabase
# -----------------------
SUPABASE_URL = env("SUPABASE_URL")
SUPABASE_SERVICE_KEY = env("SUPABASE_SERVICE_KEY")

# -----------------------
# Azure OpenAI
# -----------------------
AZURE_OPENAI_ENDPOINT = env("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = env("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = env("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = env("AZURE_OPENAI_API_VERSION")

# -----------------------
# Azure Speech (TTS)
# -----------------------
AZURE_SPEECH_KEY = env("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = env("AZURE_SPEECH_REGION")
