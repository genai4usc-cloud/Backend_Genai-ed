import httpx
from core.config import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION,
)

async def call_azure_openai(prompt: str) -> str:
    url = f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions"
    params = {"api-version": AZURE_OPENAI_API_VERSION}

    headers = {
        "api-key": AZURE_OPENAI_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "messages": [
            {"role": "system", "content": "You are an expert educational content creator."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": 3000,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, headers=headers, params=params, json=payload)
        response.raise_for_status()
        data = response.json()

    return data["choices"][0]["message"]["content"]
