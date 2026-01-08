import os
from dotenv import load_dotenv

load_dotenv()  # loads .env from project root

def env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name, default)
    return v.strip() if isinstance(v, str) else v

SUPABASE_URL = env("SUPABASE_URL")
SUPABASE_SERVICE_KEY = env("SUPABASE_SERVICE_KEY")

AZURE_OPENAI_ENDPOINT = env("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = env("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = env("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = env("AZURE_OPENAI_API_VERSION")
