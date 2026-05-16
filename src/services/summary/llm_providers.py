from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from services.summary.prompt import PROMPT_VERSION, SYSTEM_PROMPT, build_user_message

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


async def call_summary_llm(
    *,
    provider: str,
    api_key: str,
    model: str,
    temperature: float,
    context: dict,
    market_snippet: dict,
) -> dict:
    user_message = build_user_message(context, market_snippet)
    if provider == "gemini":
        raw = await _call_gemini(api_key, model, temperature, user_message)
    else:
        raw = await _call_openai(api_key, model, temperature, user_message)
    return _normalize_payload(raw)


async def _call_openai(api_key: str, model: str, temperature: float, user_message: str) -> dict:
    body = {
        "model": model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(OPENAI_CHAT_URL, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


async def _call_gemini(api_key: str, model: str, temperature: float, user_message: str) -> dict:
    url = f"{GEMINI_BASE_URL}/{model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": user_message}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "temperature": temperature,
            "responseMimeType": "application/json",
        },
    }
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
    text = _gemini_text_from_response(data)
    return json.loads(text)


def _gemini_text_from_response(data: dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        block = data.get("promptFeedback") or data
        raise ValueError(f"Gemini returned no candidates: {block}")
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    if not parts:
        raise ValueError("Gemini candidate has no content parts")
    text = parts[0].get("text")
    if not text:
        raise ValueError("Gemini response part has no text")
    return text


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload.setdefault("$schema", PROMPT_VERSION)
    payload.setdefault(
        "disclaimer",
        "AI-generated summary of public posts; not financial advice.",
    )
    return payload
