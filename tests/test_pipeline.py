from datetime import date

import pytest

from levecho.data import FetchResult
from levecho.pipeline import SnapshotBuildError, build_snapshot
from levecho.types import PairConfig, PriceBar


def _bars(
    symbol: str,
    closes: list[float],
    source: str = "fixture",
    days: tuple[date, ...] = (date(2026, 9, 3), date(2026, 9, 4)),
) -> list[PriceBar]:
    return [PriceBar(symbol, day, close, source=source) for day, close in zip(days, closes)]


def test_snapshot_contains_tracking_error() -> None:
    pair = PairConfig("abc-abcu", "ABC", "ABCU", 2)
    fetched = FetchResult(
        bars={
            "ABC": _bars("ABC", [100, 110]),
            "ABCU": _bars("ABCU", [10, 12]),
        }
    )
    snapshot = build_snapshot([pair], fetched)
    item = snapshot["pairs"][0]
    assert item["stock_return"] == pytest.approx(0.1)
    assert item["ideal_etf_return"] == pytest.approx(0.2)
    assert item["tracking_error"] == pytest.approx(0)
    assert snapshot["calculation_base_session"] == "2026-09-04"
    assert item["calculation_base_session"] == "2026-09-04"
    assert item["calculation_base_stock_close"] == pytest.approx(110)
    assert item["calculation_base_etf_close"] == pytest.approx(12)


def test_mismatched_latest_sessions_do_not_publish() -> None:
    pair = PairConfig("abc-abcu", "ABC", "ABCU", 2)
    fetched = FetchResult(
        bars={
            "ABC": _bars("ABC", [100, 110]),
            "ABCU": [PriceBar("ABCU", date(2026, 9, 3), 10), PriceBar("ABCU", date(2026, 9, 5), 12)],
        }
    )
    with pytest.raises(SnapshotBuildError):
        build_snapshot([pair], fetched)


def test_holiday_and_weekend_bridge_is_accepted() -> None:
    # Friday 2026-09-04 -> Tuesday 2026-09-08 spans a weekend and Labor Day (09-07).
    pair = PairConfig("abc-abcu", "ABC", "ABCU", 2)
    days = (date(2026, 9, 4), date(2026, 9, 8))
    fetched = FetchResult(
        bars={
            "ABC": _bars("ABC", [100, 110], days=days),
            "ABCU": _bars("ABCU", [10, 12], days=days),
        }
    )
    snapshot = build_snapshot([pair], fetched)
    assert snapshot["pairs"][0]["stock_return"] == pytest.approx(0.1)


def test_weekend_bridge_is_accepted() -> None:
    pair = PairConfig("abc-abcu", "ABC", "ABCU", 2)
    days = (date(2026, 9, 11), date(2026, 9, 14))  # Friday -> Monday
    fetched = FetchResult(
        bars={
            "ABC": _bars("ABC", [100, 110], days=days),
            "ABCU": _bars("ABCU", [10, 12], days=days),
        }
    )
    snapshot = build_snapshot([pair], fetched)
    assert snapshot["base_session"] == "2026-09-11"


def test_missing_middle_session_is_rejected() -> None:
    # Both sides lost 2026-09-03; a two-day return must not pose as one session.
    pair = PairConfig("abc-abcu", "ABC", "ABCU", 2)
    days = (date(2026, 9, 2), date(2026, 9, 4))
    fetched = FetchResult(
        bars={
            "ABC": _bars("ABC", [100, 110], days=days),
            "ABCU": _bars("ABCU", [10, 12], days=days),
        }
    )
    with pytest.raises(SnapshotBuildError, match="consecutive NYSE"):
        build_snapshot([pair], fetched)


def test_non_session_date_is_rejected() -> None:
    # A provider returning a Sunday bar would bridge Fri -> Sun, which is
    # never adjacent on the NYSE calendar.
    pair = PairConfig("abc-abcu", "ABC", "ABCU", 2)
    days = (date(2026, 9, 4), date(2026, 9, 6))
    fetched = FetchResult(
        bars={
            "ABC": _bars("ABC", [100, 110], days=days),
            "ABCU": _bars("ABCU", [10, 12], days=days),
        }
    )
    with pytest.raises(SnapshotBuildError, match="consecutive NYSE"):
        build_snapshot([pair], fetched)


def test_corporate_action_is_recorded_as_warning() -> None:
    pair = PairConfig("abc-abcu", "ABC", "ABCU", 2)
    fetched = FetchResult(
        bars={
            "ABC": [PriceBar("ABC", date(2026, 9, 3), 100), PriceBar("ABC", date(2026, 9, 4), 110, dividend=1)],
            "ABCU": _bars("ABCU", [10, 12]),
        }
    )
    snapshot = build_snapshot([pair], fetched)
    assert any("dividend" in warning for warning in snapshot["pairs"][0]["warnings"])
