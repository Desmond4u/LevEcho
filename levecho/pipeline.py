"""Build the latest close-to-close snapshot consumed by Streamlit."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from .data import FetchResult
from .io import utc_now_iso
from .model import daily_return
from .types import PairConfig, PriceBar


class SnapshotBuildError(RuntimeError):
    """Raised when a complete, same-session snapshot cannot be built."""


def _bar_map(bars: Iterable[PriceBar]) -> dict[date, PriceBar]:
    return {bar.session: bar for bar in bars if bar.close > 0}


def _source_label(stock_bar: PriceBar, etf_bar: PriceBar) -> str:
    sources = sorted({stock_bar.source, etf_bar.source})
    return "+".join(source for source in sources if source)


def build_pair_snapshot(
    pair: PairConfig,
    stock_bars: Iterable[PriceBar],
    etf_bars: Iterable[PriceBar],
) -> dict[str, Any]:
    stock_map = _bar_map(stock_bars)
    etf_map = _bar_map(etf_bars)
    stock_sessions = set(stock_map)
    etf_sessions = set(etf_map)
    common = sorted(stock_sessions & etf_sessions)
    if len(common) < 2:
        raise SnapshotBuildError(f"{pair.pair_id}: fewer than two common trading sessions")
    if max(stock_sessions) != max(etf_sessions):
        raise SnapshotBuildError(
            f"{pair.pair_id}: latest sessions differ ({max(stock_sessions)} vs {max(etf_sessions)})"
        )

    base_session, as_of_session = common[-2], common[-1]
    stock_base = stock_map[base_session]
    etf_base = etf_map[base_session]
    stock_latest = stock_map[as_of_session]
    etf_latest = etf_map[as_of_session]
    stock_return = daily_return(stock_base.close, stock_latest.close)
    etf_return = daily_return(etf_base.close, etf_latest.close)
    ideal_etf_return = pair.leverage * stock_return
    warnings: list[str] = []
    for bar, label in (
        (stock_base, "stock base"),
        (etf_base, "ETF base"),
        (stock_latest, "stock latest"),
        (etf_latest, "ETF latest"),
    ):
        if bar.dividend:
            warnings.append(f"{label} has a dividend/distribution of {bar.dividend:g}")
        if bar.split != 1.0:
            warnings.append(f"{label} has a split factor of {bar.split:g}")

    return {
        "pair_id": pair.pair_id,
        "underlying_symbol": pair.underlying_symbol,
        "etf_symbol": pair.etf_symbol,
        "leverage": pair.leverage,
        "issuer": pair.issuer,
        "reference_asset": pair.reference_asset,
        "source_url": pair.source_url,
        "confidence": pair.confidence,
        "status": pair.status,
        "base_session": base_session.isoformat(),
        "as_of_session": as_of_session.isoformat(),
        "base_stock_close": stock_base.close,
        "base_etf_close": etf_base.close,
        "latest_stock_close": stock_latest.close,
        "latest_etf_close": etf_latest.close,
        "stock_return": stock_return,
        "etf_return": etf_return,
        "ideal_etf_return": ideal_etf_return,
        "tracking_error": etf_return - ideal_etf_return,
        "source": _source_label(stock_latest, etf_latest),
        "warnings": sorted(set(warnings)),
    }


def build_snapshot(pairs: Iterable[PairConfig], fetched: FetchResult) -> dict[str, Any]:
    pair_list = [pair for pair in pairs if pair.status == "active"]
    if not pair_list:
        raise SnapshotBuildError("no active ETF pairs are configured")

    snapshots: list[dict[str, Any]] = []
    errors: list[str] = []
    for pair in pair_list:
        stock_symbol = pair.underlying_provider_symbol
        etf_symbol = pair.etf_provider_symbol
        if stock_symbol not in fetched.bars or etf_symbol not in fetched.bars:
            errors.append(
                f"{pair.pair_id}: {fetched.errors.get(stock_symbol, 'missing stock data')}; "
                f"{fetched.errors.get(etf_symbol, 'missing ETF data')}"
            )
            continue
        try:
            snapshots.append(build_pair_snapshot(pair, fetched.bars[stock_symbol], fetched.bars[etf_symbol]))
        except SnapshotBuildError as exc:
            errors.append(str(exc))
    if errors:
        raise SnapshotBuildError("; ".join(errors))

    as_of_sessions = {item["as_of_session"] for item in snapshots}
    base_sessions = {item["base_session"] for item in snapshots}
    if len(as_of_sessions) != 1 or len(base_sessions) != 1:
        raise SnapshotBuildError("active pairs do not share the same latest/base session")

    return {
        "model_version": "1.0",
        "source_status": "success",
        "base_session": next(iter(base_sessions)),
        "as_of_session": next(iter(as_of_sessions)),
        "published_at": utc_now_iso(),
        "pairs": sorted(snapshots, key=lambda item: item["pair_id"]),
    }
