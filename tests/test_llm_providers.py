import json

import pytest

from services.summary.llm_providers import (
    _gemini_text_from_response,
    _normalize_payload,
    call_summary_llm,
)


def test_gemini_text_from_response():
    data = {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps({"status": "ok", "ticker": "AAPL"})}]}}
        ]
    }
    text = _gemini_text_from_response(data)
    assert json.loads(text)["ticker"] == "AAPL"


def test_gemini_text_from_response_raises_without_candidates():
    with pytest.raises(ValueError, match="no candidates"):
        _gemini_text_from_response({})


def test_normalize_payload_adds_defaults():
    payload = _normalize_payload({"status": "ok"})
    assert payload["$schema"] == "summary_v1"
    assert "disclaimer" in payload


@pytest.mark.asyncio
async def test_call_summary_llm_gemini(monkeypatch):
    captured: dict = {}

    response_text = json.dumps(
        {
            "status": "ok",
            "ticker": "NVDA",
            "window": "24h",
            "as_of": "2026-05-16T00:00:00+00:00",
            "bull_points": [],
            "bear_points": [],
            "catalysts": [],
            "risks": [],
            "consensus": "test",
            "citations": [],
        }
    )

    async def fake_post(self, url, *, headers=None, json=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json

        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "candidates": [
                        {"content": {"parts": [{"text": response_text}]}}
                    ]
                }

        return Resp()

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        post = fake_post

    monkeypatch.setattr(
        "services.summary.llm_providers.httpx.AsyncClient",
        FakeClient,
    )

    result = await call_summary_llm(
        provider="gemini",
        api_key="test-key",
        model="gemini-2.0-flash",
        temperature=0.2,
        context={
            "ticker": "NVDA",
            "window": "24h",
            "window_end": "2026-05-16T00:00:00+00:00",
            "stats": {"weighted_mentions": 10},
            "posts": [],
            "comments": [],
            "source_ids": [],
        },
        market_snippet={},
    )

    assert result["ticker"] == "NVDA"
    assert "gemini-2.0-flash" in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "test-key"
    assert captured["body"]["generationConfig"]["responseMimeType"] == "application/json"
