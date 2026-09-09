"""End-of-day price providers with a primary/fallback interface."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO
from typing import Iterable, Protocol
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

from .types import PriceBar


class DataSourceError(RuntimeError):
    """Raised when a provider cannot return usable data."""


@dataclass
class FetchResult:
    bars: dict[str, list[PriceBar]] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


class PriceProvider(Protocol):
    name: str

    def fetch(self, symbols: Iterable[str], lookback_days: int = 15) -> FetchResult:
        ...


def _session_date(value: object):
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("America/New_York")
    else:
        timestamp = timestamp.tz_convert("America/New_York")
    return timestamp.date()


def _field(frame: pd.DataFrame, name: str) -> pd.Series | None:
    for column in frame.columns:
        if str(column).strip().lower() == name.lower():
            return frame[column]
    return None


def _symbol_frame(data: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()
    if not isinstance(data.columns, pd.MultiIndex):
        return data.copy()

    for level in range(data.columns.nlevels):
        values = {str(value).upper(): value for value in data.columns.get_level_values(level)}
        if symbol.upper() in values:
            return data.xs(values[symbol.upper()], axis=1, level=level, drop_level=True)
    return pd.DataFrame()


def _bars_from_frame(symbol: str, frame: pd.DataFrame, source: str) -> list[PriceBar]:
    close_series = _field(frame, "Close")
    if close_series is None:
        return []
    dividend_series = _field(frame, "Dividends")
    split_series = _field(frame, "Stock Splits")
    result: list[PriceBar] = []
    for index, raw_close in close_series.items():
        if pd.isna(raw_close):
            continue
        dividend = 0.0 if dividend_series is None else float(dividend_series.get(index, 0.0) or 0.0)
        split = 1.0 if split_series is None else float(split_series.get(index, 1.0) or 1.0)
        result.append(
            PriceBar(
                symbol=symbol,
                session=_session_date(index),
                close=float(raw_close),
                dividend=dividend,
                split=split,
                source=source,
            )
        )
    return sorted(result, key=lambda item: item.session)


class YFinanceProvider:
    name = "yfinance"

    def __init__(self, chunk_size: int = 100, timeout: int = 15) -> None:
        self.chunk_size = chunk_size
        self.timeout = timeout

    def fetch(self, symbols: Iterable[str], lookback_days: int = 15) -> FetchResult:
        unique_symbols = list(dict.fromkeys(str(symbol).upper() for symbol in symbols))
        result = FetchResult()
        for start in range(0, len(unique_symbols), self.chunk_size):
            chunk = unique_symbols[start : start + self.chunk_size]
            try:
                downloaded = yf.download(
                    tickers=chunk,
                    period=f"{max(5, lookback_days)}d",
                    interval="1d",
                    auto_adjust=False,
                    actions=True,
                    progress=False,
                    group_by="column",
                    threads=True,
                    timeout=self.timeout,
                )
            except Exception as exc:  # provider failures are handled by the fallback layer
                message = f"{type(exc).__name__}: {exc}"
                result.errors.update({symbol: message for symbol in chunk})
                continue

            for symbol in chunk:
                bars = _bars_from_frame(symbol, _symbol_frame(downloaded, symbol), self.name)
                if bars:
                    result.bars[symbol] = bars
                    result.errors.pop(symbol, None)
                else:
                    result.errors[symbol] = "no usable daily close returned"
        return result


class NasdaqProvider:
    """Read daily closes from Nasdaq's public historical quote endpoint."""

    name = "nasdaq"

    def __init__(self, timeout: int = 15, max_workers: int = 6) -> None:
        self.timeout = timeout
        self.max_workers = max_workers

    @staticmethod
    def _request_symbol(symbol: str) -> str:
        return symbol.upper().replace("-", ".")

    @staticmethod
    def _request_json(
        url: str,
        params: dict[str, str | int],
        headers: dict[str, str],
        timeout: int,
    ) -> dict:
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as request_error:  # noqa: BLE001 - try the transport fallback
            try:
                result = subprocess.run(
                    [
                        "curl",
                        "--fail",
                        "--silent",
                        "--show-error",
                        "--location",
                        "--max-time",
                        str(timeout),
                        "--user-agent",
                        headers["User-Agent"],
                        "--header",
                        f"Accept: {headers['Accept']}",
                        "--header",
                        f"Origin: {headers['Origin']}",
                        "--header",
                        f"Referer: {headers['Referer']}",
                        f"{url}?{urlencode(params)}",
                    ],
                    check=True,
                    capture_output=True,
                    timeout=timeout + 5,
                )
                return json.loads(result.stdout.decode("utf-8"))
            except Exception as curl_error:  # noqa: BLE001 - surface both failures
                raise DataSourceError(
                    f"requests failed ({type(request_error).__name__}: {request_error}); "
                    f"curl failed ({type(curl_error).__name__}: {curl_error})"
                ) from request_error

    def _fetch_one(self, symbol: str, asset_class: str, lookback_days: int) -> list[PriceBar]:
        today = datetime.now(ZoneInfo("America/New_York")).date()
        from_date = today - timedelta(days=max(30, lookback_days * 3))
        url = f"https://api.nasdaq.com/api/quote/{self._request_symbol(symbol)}/historical"
        params = {
            "assetclass": asset_class,
            "fromdate": from_date.isoformat(),
            "todate": today.isoformat(),
            "limit": max(20, lookback_days * 2),
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.nasdaq.com",
            "Referer": "https://www.nasdaq.com/",
        }
        payload = self._request_json(url, params, headers, self.timeout)
        data = payload.get("data") or {}
        table = data.get("tradesTable") or {}
        rows = table.get("rows") or []
        if not rows:
            status = payload.get("status") or {}
            messages = status.get("bCodeMessage") or []
            detail = "; ".join(str(item.get("errorMessage", "")) for item in messages)
            raise DataSourceError(detail or "no historical rows returned")

        result: list[PriceBar] = []
        for row in rows:
            close_text = str(row.get("close", "")).replace("$", "").replace(",", "").strip()
            if not close_text:
                continue
            result.append(
                PriceBar(
                    symbol=symbol,
                    session=datetime.strptime(str(row["date"]), "%m/%d/%Y").date(),
                    close=float(close_text),
                    source=self.name,
                )
            )
        if not result:
            raise DataSourceError("no usable daily close returned")
        return sorted(result, key=lambda item: item.session)

    def _fetch_symbol(self, symbol: str, lookback_days: int) -> tuple[str, list[PriceBar] | None, str | None]:
        try:
            return symbol, self._fetch_one(symbol, "stocks", lookback_days), None
        except Exception as stock_exc:
            try:
                return symbol, self._fetch_one(symbol, "etf", lookback_days), None
            except Exception as etf_exc:  # noqa: BLE001 - surfaced through FetchResult
                return (
                    symbol,
                    None,
                    f"stocks: {type(stock_exc).__name__}: {stock_exc}; "
                    f"etf: {type(etf_exc).__name__}: {etf_exc}",
                )

    def fetch(self, symbols: Iterable[str], lookback_days: int = 15) -> FetchResult:
        unique_symbols = list(dict.fromkeys(str(symbol).upper() for symbol in symbols))
        result = FetchResult()
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._fetch_symbol, symbol, lookback_days): symbol
                for symbol in unique_symbols
            }
            for future in as_completed(futures):
                symbol, bars, error = future.result()
                if bars:
                    result.bars[symbol] = bars
                elif error:
                    result.errors[symbol] = error
        return result


class StooqProvider:
    name = "stooq"

    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout

    @staticmethod
    def _source_symbol(symbol: str) -> str:
        return f"{symbol.lower().replace('-', '.')}.us"

    def fetch(self, symbols: Iterable[str], lookback_days: int = 15) -> FetchResult:
        unique_symbols = list(dict.fromkeys(str(symbol).upper() for symbol in symbols))
        result = FetchResult()
        for symbol in unique_symbols:
            try:
                response = requests.get(
                    "https://stooq.com/q/d/l/",
                    params={"s": self._source_symbol(symbol), "i": "d"},
                    timeout=self.timeout,
                    headers={"User-Agent": "LevEcho/1.0"},
                )
                response.raise_for_status()
                frame = pd.read_csv(StringIO(response.text))
                if frame.empty or "Close" not in frame.columns:
                    raise DataSourceError("no usable daily close returned")
                bars: list[PriceBar] = []
                for _, row in frame.tail(max(5, lookback_days)).iterrows():
                    if pd.isna(row.get("Close")):
                        continue
                    bars.append(
                        PriceBar(
                            symbol=symbol,
                            session=pd.Timestamp(row["Date"]).date(),
                            close=float(row["Close"]),
                            source=self.name,
                        )
                    )
                if not bars:
                    raise DataSourceError("no usable daily close returned")
                result.bars[symbol] = sorted(bars, key=lambda item: item.session)
            except Exception as exc:  # noqa: BLE001 - provider failures are data, not process crashes
                result.errors[symbol] = f"{type(exc).__name__}: {exc}"
        return result


class FallbackProvider:
    """Use the fallback only for symbols missing from the primary result."""

    def __init__(self, primary: PriceProvider, fallback: PriceProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    def fetch(self, symbols: Iterable[str], lookback_days: int = 15) -> FetchResult:
        unique_symbols = list(dict.fromkeys(str(symbol).upper() for symbol in symbols))
        primary_result = self.primary.fetch(unique_symbols, lookback_days)
        missing = [symbol for symbol in unique_symbols if symbol not in primary_result.bars]
        if not missing:
            return primary_result

        fallback_result = self.fallback.fetch(missing, lookback_days)
        merged = FetchResult(bars=dict(primary_result.bars), errors=dict(primary_result.errors))
        merged.bars.update(fallback_result.bars)
        for symbol in missing:
            if symbol in fallback_result.bars:
                merged.errors.pop(symbol, None)
            elif symbol in fallback_result.errors:
                merged.errors[symbol] = (
                    f"primary: {primary_result.errors.get(symbol, 'missing')}; "
                    f"fallback: {fallback_result.errors[symbol]}"
                )
        return merged
