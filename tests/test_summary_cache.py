from services.summary.llm import SummaryService


def test_cache_key_stable_for_same_sources():
    service = SummaryService.__new__(SummaryService)
    key1 = service._cache_key("NVDA", "7d", ["t3_a", "t3_b"], "2026-05-16T00:00:00+00:00")
    key2 = service._cache_key("NVDA", "7d", ["t3_a", "t3_b"], "2026-05-16T00:00:00+00:00")
    key3 = service._cache_key("NVDA", "7d", ["t3_b", "t3_a"], "2026-05-16T00:00:00+00:00")
    assert key1 == key2 == key3
