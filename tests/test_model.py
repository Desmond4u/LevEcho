import math

import pytest

from levecho.model import ModelInputError, solve_etf_price, solve_stock_price


def test_example_works_in_both_directions() -> None:
    assert solve_stock_price(100, 10, 2, 12) == pytest.approx(110)
    assert solve_etf_price(100, 10, 2, 110) == pytest.approx(12)


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
