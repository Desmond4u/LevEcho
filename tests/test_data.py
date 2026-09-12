from datetime import date
from types import SimpleNamespace

import pandas as pd

import levecho.data as data_module
from levecho.data import (
    FetchResult,
    FallbackProvider,
    NasdaqProvider,
    YFinanceProvider,
    YFinanceRecentProvider,
)
from levecho.types import PriceBar


class _FakeProvider:
    name = "fake"

    def __init__(self, bars: dict[str, list[PriceBar]], errors: dict[str, str] | None = None) -> None:
        self.result = FetchResult(bars=bars, errors=errors or {})
        self.requested: list[list[str]] = []

    def fetch(self, symbols, lookback_days=15):
        wanted = list(symbols)
        self.requested.append(wanted)
        wanted_set = set(wanted)
        return FetchResult(
            bars={symbol: bars for symbol, bars in self.result.bars.items() if symbol in wanted_set},
            errors={symbol: error for symbol, error in self.result.errors.items() if symbol in wanted_set},
        )


def test_fallback_only_fetches_missing_symbols() -> None:
    primary = _FakeProvider({"AAA": [PriceBar("AAA", date(2026, 9, 4), 10)]}, {"BBB": "missing"})
    fallback = _FakeProvider({"BBB": [PriceBar("BBB", date(2026, 9, 4), 20)]})
    result = FallbackProvider(primary, fallback).fetch(["AAA", "BBB"])
    assert set(result.bars) == {"AAA", "BBB"}
    assert not result.errors
    assert fallback.requested == [["BBB"]]


def test_fallback_fills_stale_latest_session() -> None:
    primary = _FakeProvider(
        {
            "SPCX": [
                PriceBar("SPCX", date(2026, 9, 8), 153.47, source="yfinance"),
                PriceBar("SPCX", date(2026, 9, 9), 147.55, source="yfinance"),
            ],
            "DSPC": [PriceBar("DSPC", date(2026, 9, 8), 13.577, source="yfinance")],
        }
    )
    fallback = _FakeProvider(
        {
            "DSPC": [
                PriceBar("DSPC", date(2026, 9, 8), 99.0, source="nasdaq"),
                PriceBar("DSPC", date(2026, 9, 9), 14.0871, source="nasdaq"),
            ]
        }
    )
    result = FallbackProvider(primary, fallback).fetch(["SPCX", "DSPC"])

    assert fallback.requested == [["DSPC"]]
    bars = {bar.session: bar for bar in result.bars["DSPC"]}
    assert bars[date(2026, 9, 9)].close == 14.0871
    assert bars[date(2026, 9, 9)].source == "nasdaq"
    assert bars[date(2026, 9, 8)].source == "yfinance"
    assert not result.errors


def test_fallback_skipped_when_all_symbols_share_latest_session() -> None:
    primary = _FakeProvider(
        {
            "SPCX": [PriceBar("SPCX", date(2026, 9, 8), 153.47)],
            "DSPC": [PriceBar("DSPC", date(2026, 9, 8), 13.577)],
        }
    )
    fallback = _FakeProvider({})
    result = FallbackProvider(primary, fallback).fetch(["SPCX", "DSPC"])

    assert fallback.requested == []
    assert set(result.bars) == {"SPCX", "DSPC"}


def test_fallback_without_newer_data_keeps_primary_bars_and_records_gap() -> None:
    primary = _FakeProvider(
        {
            "SPCX": [PriceBar("SPCX", date(2026, 9, 9), 147.55, source="yfinance")],
            "DSPC": [PriceBar("DSPC", date(2026, 9, 8), 13.577, source="yfinance")],
        }
    )
    fallback = _FakeProvider(
        {"DSPC": [PriceBar("DSPC", date(2026, 9, 8), 99.0, source="nasdaq")]}
    )
    result = FallbackProvider(primary, fallback).fetch(["SPCX", "DSPC"])

    assert fallback.requested == [["DSPC"]]
    assert result.bars["DSPC"] == [PriceBar("DSPC", date(2026, 9, 8), 13.577, source="yfinance")]
    assert "stale fill failed" in result.errors["DSPC"]
    assert "fallback latest 2026-09-08" in result.errors["DSPC"]


def test_stale_fill_transport_failure_is_visible() -> None:
    primary = _FakeProvider(
        {
            "SPCX": [PriceBar("SPCX", date(2026, 9, 9), 147.55)],
            "DSPC": [PriceBar("DSPC", date(2026, 9, 8), 13.577)],
        }
    )
    fallback = _FakeProvider({}, errors={"DSPC": "HTTP 403 blocked"})
    result = FallbackProvider(primary, fallback).fetch(["SPCX", "DSPC"])

    assert result.bars["DSPC"] == [PriceBar("DSPC", date(2026, 9, 8), 13.577)]
    assert "stale fill failed" in result.errors["DSPC"]
    assert "HTTP 403 blocked" in result.errors["DSPC"]
    assert "required 2026-09-09" in result.errors["DSPC"]


def test_nested_fallback_chain_recovers_stale_symbol() -> None:
    primary = _FakeProvider(
        {
            "SPCX": [PriceBar("SPCX", date(2026, 9, 9), 147.55)],
            "DSPC": [PriceBar("DSPC", date(2026, 9, 8), 13.577)],
        }
    )
    nasdaq = _FakeProvider({}, errors={"DSPC": "HTTP 403 blocked"})
    recent = _FakeProvider(
        {"DSPC": [PriceBar("DSPC", date(2026, 9, 9), 14.0871, source="yfinance-recent")]}
    )
    chain = FallbackProvider(primary, FallbackProvider(nasdaq, recent))
    result = chain.fetch(["SPCX", "DSPC"])

    assert recent.requested == [["DSPC"]]  # Nasdaq failed, the 1d pipeline filled the gap
    assert [bar.session for bar in result.bars["DSPC"]] == [date(2026, 9, 8), date(2026, 9, 9)]
    assert result.bars["DSPC"][-1].source == "yfinance-recent"
    assert not result.errors


class _FakeTicker:
    def __init__(self, frame) -> None:
        self._frame = frame

    def history(self, **kwargs) -> pd.DataFrame:
        assert kwargs.get("period") == "1d"
        return self._frame


def test_yfinance_recent_provider_uses_one_day_pipeline(monkeypatch) -> None:
    frame = pd.DataFrame(
        {"Close": [14.0871], "Dividends": [0.0], "Stock Splits": [1.0]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-09-09", tz="America/New_York")]),
    )
    monkeypatch.setattr(data_module.yf, "Ticker", lambda symbol: _FakeTicker(frame))
    result = data_module.YFinanceRecentProvider().fetch(["DSPC"])

    assert result.errors == {}
    assert result.bars["DSPC"] == [PriceBar("DSPC", date(2026, 9, 9), 14.0871, source="yfinance-recent")]


def test_yfinance_recent_provider_reports_null_close(monkeypatch) -> None:
    frame = pd.DataFrame(
        {"Close": [float("nan")], "Dividends": [0.0], "Stock Splits": [1.0]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-09-09", tz="America/New_York")]),
    )
    monkeypatch.setattr(data_module.yf, "Ticker", lambda symbol: _FakeTicker(frame))
    result = data_module.YFinanceRecentProvider().fetch(["DSPC"])

    assert result.bars == {}
    assert result.errors["DSPC"] == "no usable daily close returned"


def test_yfinance_uses_100_symbol_chunks_by_default() -> None:
    provider = YFinanceProvider()

    assert provider.chunk_size == 100


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
