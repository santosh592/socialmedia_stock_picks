from __future__ import annotations

import json

PROMPT_VERSION = "summary_v1"

SYSTEM_PROMPT = """You summarize Reddit stock discussion for a personal research tool.
Rules:
- Use ONLY the provided posts and comments.
- Every bull_point, bear_point, catalyst, and risk must include citation IDs from the input.
- Do not recommend buying or selling; do not predict price targets.
- Output valid JSON matching the schema exactly. No markdown fences.
- If discussion is too thin to summarize, set status to insufficient_discussion.
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "$schema": {"type": "string"},
        "ticker": {"type": "string"},
        "window": {"type": "string"},
        "as_of": {"type": "string"},
        "status": {"type": "string", "enum": ["ok", "insufficient_discussion", "error"]},
        "tone": {"type": ["string", "null"]},
        "bull_points": {"type": "array"},
        "bear_points": {"type": "array"},
        "catalysts": {"type": "array"},
        "risks": {"type": "array"},
        "consensus": {"type": "string"},
        "controversy": {"type": ["string", "null"]},
        "citations": {"type": "array"},
        "disclaimer": {"type": "string"},
    },
    "required": [
        "ticker",
        "window",
        "as_of",
        "status",
        "bull_points",
        "bear_points",
        "catalysts",
        "risks",
        "consensus",
        "citations",
        "disclaimer",
    ],
}


def build_user_message(context: dict, market_snippet: dict | None) -> str:
    payload = {**context, "market_snippet": market_snippet or {}}
    return (
        "Summarize the following discussion JSON. "
        f"Schema: {json.dumps(RESPONSE_SCHEMA)}\n\n"
        f"Input:\n{json.dumps(payload, default=str)}"
    )
