from services.ticker.extract import TickerExtractor


def test_extract_cashtag_and_blocklist():
    extractor = TickerExtractor()
    tickers = extractor.extract("Long $AAPL and AI hype but ON is not a stock")
    assert "AAPL" in tickers
    assert "AI" not in tickers
    assert "ON" not in tickers


def test_weight_dd_flair():
    extractor = TickerExtractor()
    w = extractor.weight_for("title", dd_flair=True)
    assert w > extractor.weight_for("title", dd_flair=False)
