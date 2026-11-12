import json
import os
import re
from typing import AsyncIterator

from google import genai
from google.genai import types


DEFAULT_MODEL = "gemini-2.5-flash"
MODELS = [
    {"id": "gemini:gemini-2.5-flash", "label": "Gemini 2.5 Flash (recommended)"},
    {"id": "gemini:gemini-2.5-pro", "label": "Gemini 2.5 Pro"},
]
MODEL_IDS = {m["id"] for m in MODELS}


def parse_json(text: str) -> dict:
    match = re.search(r"\\{.*\\}", text, re.S)
    if not match:
        raise ValueError("Model did not return a JSON object")
    return json.loads(match.group(0))


class LLMUnavailable(Exception):
    pass


def _client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise LLMUnavailable(
            "Google Gemini is not configured. Add GEMINI_API_KEY to the backend environment."
        )
    return genai.Client(api_key=key)


def _model_name(model_id: str) -> str:
    # Settings store provider:model so future providers can be added without changing callers.
    if ":" in model_id:
        provider, model = model_id.split(":", 1)
        if provider != "gemini":
            raise LLMUnavailable(f"Unsupported AI provider: {provider}")
        return model
    return model_id or DEFAULT_MODEL


async def stream(model_id: str, system: str, prompt: str) -> AsyncIterator[str]:
    client = _client()
    try:
        stream_response = await client.aio.models.generate_content_stream(
            model=_model_name(model_id),
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.2,
            ),
        )
        async for chunk in stream_response:
            if getattr(chunk, "text", None):
                yield chunk.text
    finally:
        await client.aio.aclose()


async def complete(model_id: str, system: str, prompt: str) -> str:
    client = _client()
    try:
        response = await client.aio.models.generate_content(
            model=_model_name(model_id),
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.2,
            ),
        )
        return response.text or ""
    finally:
        await client.aio.aclose()
