import json

import httpx

from src.config import get_settings

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

METADATA_SYSTEM_PROMPT = """Extract metadata from the user's captured thought. Return JSON with:
- "people": array of people mentioned (empty if none)
- "action_items": array of implied to-dos (empty if none)
- "dates_mentioned": array of dates YYYY-MM-DD (empty if none)
- "topics": array of 1-3 short topic tags (always at least one)
- "type": one of "observation", "task", "idea", "reference", "person_note"
Only extract what's explicitly there."""


async def _post_openrouter(path: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{OPENROUTER_BASE}{path}",
            headers={
                "Authorization": f"Bearer {get_settings().openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if not r.is_success:
            msg = r.text
            raise RuntimeError(f"OpenRouter request failed: {r.status_code} {msg}")
        return r.json()


async def embed(text: str) -> list[float]:
    data = await _post_openrouter("/embeddings", {
        "model": "openai/text-embedding-3-small",
        "input": text,
    })
    return data["data"][0]["embedding"]


async def extract_metadata(text: str) -> dict:
    data = await _post_openrouter("/chat/completions", {
        "model": "openai/gpt-4o-mini",
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": METADATA_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    })
    try:
        return json.loads(data["choices"][0]["message"]["content"])
    except (json.JSONDecodeError, KeyError, IndexError):
        return {"topics": ["uncategorized"], "type": "observation"}
