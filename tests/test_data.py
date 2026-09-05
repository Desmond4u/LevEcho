from datetime import date
from types import SimpleNamespace

import levecho.data as data_module
from levecho.data import FetchResult, FallbackProvider, NasdaqProvider
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


def test_nasdaq_uses_curl_when_python_request_fails(monkeypatch) -> None:
    def fail_request(*args, **kwargs):
        raise OSError("TLS handshake failed")

    payload = b'{"data": {"ok": true}}'
    calls: list[list[str]] = []

    def fake_curl(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout=payload)

    monkeypatch.setattr(data_module.requests, "get", fail_request)
    monkeypatch.setattr(data_module.subprocess, "run", fake_curl)
    result = NasdaqProvider._request_json(
        "https://example.test/historical",
        {"assetclass": "stocks"},
        {"User-Agent": "test", "Accept": "application/json", "Origin": "https://example.test", "Referer": "https://example.test/"},
        5,
    )

    assert result == {"data": {"ok": True}}
    assert calls and calls[0][0] == "curl"
