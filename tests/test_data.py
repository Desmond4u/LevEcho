from datetime import date

from levecho.data import FetchResult, FallbackProvider
from levecho.types import PriceBar


class _FakeProvider:
    name = "fake"

    def __init__(self, bars: dict[str, list[PriceBar]], errors: dict[str, str] | None = None) -> None:
        self.result = FetchResult(bars=bars, errors=errors or {})

    def fetch(self, symbols, lookback_days=15):
        wanted = set(symbols)
        return FetchResult(
            bars={symbol: bars for symbol, bars in self.result.bars.items() if symbol in wanted},
            errors={symbol: error for symbol, error in self.result.errors.items() if symbol in wanted},
        )


def test_fallback_only_fetches_missing_symbols() -> None:
    primary = _FakeProvider({"AAA": [PriceBar("AAA", date(2026, 9, 4), 10)]}, {"BBB": "missing"})
    fallback = _FakeProvider({"BBB": [PriceBar("BBB", date(2026, 9, 4), 20)]})
    result = FallbackProvider(primary, fallback).fetch(["AAA", "BBB"])
    assert set(result.bars) == {"AAA", "BBB"}
    assert not result.errors
