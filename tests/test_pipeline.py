from datetime import date

import pytest

from levecho.data import FetchResult
from levecho.pipeline import SnapshotBuildError, build_snapshot
from levecho.types import PairConfig, PriceBar


def _bars(symbol: str, closes: list[float], source: str = "fixture") -> list[PriceBar]:
    days = [date(2026, 9, 3), date(2026, 9, 4)]
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
