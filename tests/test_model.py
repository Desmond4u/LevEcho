import math

import pytest

from levecho.model import (
    ModelInputError,
    price_from_return,
    solve_etf_price,
    solve_stock_price,
)


def test_example_works_in_both_directions() -> None:
    assert solve_stock_price(100, 10, 2, 12) == pytest.approx(110)
    assert solve_etf_price(100, 10, 2, 110) == pytest.approx(12)


def test_next_session_example_uses_previous_close_as_base() -> None:
    theoretical_etf = solve_etf_price(1740, 17.36, 2, 1800)

    assert theoretical_etf == pytest.approx(18.5572413793)
    assert solve_stock_price(1740, 17.36, 2, theoretical_etf) == pytest.approx(1800)


@pytest.mark.parametrize(
    ("base_price", "return_rate", "expected"),
    [(100, 0.10, 110), (100, -0.20, 80), (17.36, 0, 17.36)],
)
def test_price_from_return(base_price: float, return_rate: float, expected: float) -> None:
    assert price_from_return(base_price, return_rate) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("base_price", "return_rate"),
    [(100, -1), (100, -1.1), (0, 0), (100, math.nan), (100, math.inf)],
)
def test_price_from_return_rejects_invalid_inputs(
    base_price: float, return_rate: float
) -> None:
    with pytest.raises(ModelInputError):
        price_from_return(base_price, return_rate)


@pytest.mark.parametrize("leverage", [3, -2, -3])
def test_signed_leverage_is_supported(leverage: float) -> None:
    stock_input = 105
    etf = solve_etf_price(100, 10, leverage, stock_input)
    assert solve_stock_price(100, 10, leverage, etf) == pytest.approx(stock_input)


@pytest.mark.parametrize(
    "args",
    [
        (0, 10, 2, 100),
        (100, 0, 2, 100),
        (100, 10, 0, 100),
        (100, 10, 2, 0),
        (100, 10, 2, math.nan),
    ],
)
def test_invalid_inputs_raise(args: tuple[float, float, float, float]) -> None:
    with pytest.raises(ModelInputError):
        solve_etf_price(*args)


def test_non_positive_theoretical_price_is_rejected() -> None:
    with pytest.raises(ModelInputError):
        solve_etf_price(100, 10, 3, 60)
