from __future__ import annotations

from core.config import get_settings


class IntentClassifier:
    def classify(self, text: str) -> tuple[str, float]:
        settings = get_settings()
        keywords: dict[str, list[str]] = settings.intents.get("keywords", {})
        lowered = (text or "").lower()
        best_intent = "unknown"
        best_hits = 0
        for intent, words in keywords.items():
            hits = sum(1 for w in words if w in lowered)
            if hits > best_hits:
                best_hits = hits
                best_intent = intent
        confidence = min(1.0, 0.3 + best_hits * 0.2) if best_hits else 0.5
        return best_intent, confidence
