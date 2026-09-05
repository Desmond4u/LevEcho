"""Daily leveraged ETF price model."""

from __future__ import annotations

import math
from numbers import Real

MODEL_VERSION = "1.0"


class ModelInputError(ValueError):
    """Raised when a price or leverage input cannot be modeled."""


def _finite_float(value: Real, name: str) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise ModelInputError(f"{name} must be a number") from exc
    if not math.isfinite(converted):
        raise ModelInputError(f"{name} must be finite")
    return converted


def _positive_price(value: Real, name: str) -> float:
    converted = _finite_float(value, name)
    if converted <= 0:
        raise ModelInputError(f"{name} must be greater than zero")
    return converted


def _validate_base(stock_base: Real, etf_base: Real, leverage: Real) -> tuple[float, float, float]:
    stock = _positive_price(stock_base, "stock_base")
    etf = _positive_price(etf_base, "etf_base")
    multiple = _finite_float(leverage, "leverage")
    if multiple == 0:
        raise ModelInputError("leverage must not be zero")
    return stock, etf, multiple


def daily_return(start_price: Real, end_price: Real) -> float:
    """Return the simple return from ``start_price`` to ``end_price``."""

    start = _positive_price(start_price, "start_price")
    end = _positive_price(end_price, "end_price")
    return end / start - 1.0


def price_from_return(base_price: Real, return_rate: Real) -> float:
    """Convert a decimal simple return into a positive target price."""

    base = _positive_price(base_price, "base_price")
    rate = _finite_float(return_rate, "return_rate")
    result = base * (1.0 + rate)
    if not math.isfinite(result) or result <= 0:
        raise ModelInputError(
            "target price is not positive; the return is outside its valid domain"
        )
    return result


def solve_etf_price(
    stock_base: Real,
    etf_base: Real,
    leverage: Real,
    stock_input: Real,
) -> float:
    """Infer the ETF price from a same-session underlying stock price."""

    stock, etf, multiple = _validate_base(stock_base, etf_base, leverage)
    stock_value = _positive_price(stock_input, "stock_input")
    result = etf * (1.0 + multiple * (stock_value / stock - 1.0))
    if not math.isfinite(result) or result <= 0:
        raise ModelInputError(
            "theoretical ETF price is not positive; the one-day linear model is outside its valid domain"
        )
    return result


def solve_stock_price(
    stock_base: Real,
    etf_base: Real,
    leverage: Real,
    etf_input: Real,
) -> float:
    """Infer the underlying stock price from a same-session ETF price."""

    stock, etf, multiple = _validate_base(stock_base, etf_base, leverage)
    etf_value = _positive_price(etf_input, "etf_input")
    result = stock * (1.0 + (etf_value / etf - 1.0) / multiple)
    if not math.isfinite(result) or result <= 0:
        raise ModelInputError(
            "theoretical stock price is not positive; the one-day linear model is outside its valid domain"
        )
    return result
