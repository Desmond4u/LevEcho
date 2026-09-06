# LevEcho

> Estimate the theoretical price of a single-stock leveraged ETF from an assumed stock price, or work backwards from an assumed ETF price.

[Live demo](https://levecho.streamlit.app) · [简体中文](README.md) · [Developer documentation](docs/DEVELOPMENT.md)

[![Daily EOD update](https://github.com/Desmond4u/LevEcho/actions/workflows/daily_update.yml/badge.svg)](https://github.com/Desmond4u/LevEcho/actions/workflows/daily_update.yml)
[![Review ETF mappings](https://github.com/Desmond4u/LevEcho/actions/workflows/etf_review.yml/badge.svg)](https://github.com/Desmond4u/LevEcho/actions/workflows/etf_review.yml)

LevEcho is a bidirectional calculator for same-session theoretical prices of U.S. single-stock daily leveraged ETFs. It uses the latest common closing prices for the stock and ETF as the calculation base and helps answer two practical questions:

- If the stock rises or falls to a given price, what would the ETF's ideal one-day price be?
- If the ETF moves to a given price, what stock price would the daily leverage model imply?

## A simple example

Assume the latest common session closed at:

| Asset | Base price |
| --- | ---: |
| Stock | $100 |
| +2x ETF | $10 |

If the ETF's assumed price for the next target session is $12, its return is +20%. The corresponding theoretical stock return is +10%, giving a theoretical stock price of $110.

Entering a stock price of $110 produces the ETF theoretical price of $12 in the reverse direction.

## How it works

Let `S0` be the stock base price, `E0` the ETF base price, and `L` the signed daily target multiple:

```text
Theoretical ETF price = E0 × [1 + L × (input stock price / S0 - 1)]

Theoretical stock price = S0 × [1 + (input ETF price / E0 - 1) / L]
```

The app accepts either a price or a percentage return. The calculation base is the latest common trading-session close for the stock and ETF. An input represents an assumed price for the target session after that base session. On weekends and market holidays, the snapshot continues to use the latest common regular-session close.

## Coverage

- Universe: the union of S&P 500 and Nasdaq-100 constituents, with index membership retained.
- ETFs: single-stock daily-reset products identified from public issuer materials.
- Supported signed daily targets: `+1x`, `+2x`, `+3x`, `-1x`, `-2x`, and `-3x`.
- Only pairs with clearly verified reference assets, daily targets, and product status are shown in the public calculator.

The discovery configuration covers issuers including Direxion, Tradr, ProShares, GraniteShares, T-REX, Leverage Shares, and Defiance. Products with ambiguous evidence or changed metadata are placed in a review queue.

## Data updates

The app reads the repository snapshot at `data/latest.json`, so visitors do not independently query market-data endpoints. GitHub Actions handles:

- end-of-day snapshot updates after each U.S. market weekday;
- weekly index constituent checks;
- weekly ETF-pair checks that create review pull requests.

The market-data layer uses `yfinance` as the primary provider and Nasdaq's public historical endpoint as a fallback for missing symbols. See:

- [Data pipeline and date semantics](docs/DATA_PIPELINE.md)
- [ETF discovery and review](docs/ETF_REVIEW.md)

## Important limitations

- This is a one-session model. Daily-reset leverage compounds across multiple sessions and can diverge materially from a simple multiple of the cumulative stock return.
- Results are theoretical values, not real-time prices, NAVs, or executable quotes. Fees, financing costs, tracking error, dividends, splits, ETF distributions, bid-ask spreads, and market-price/NAV differences affect actual results.
- The app uses unadjusted closing prices and displays warnings when dividends, splits, or ETF distributions are detected.
- Public accessibility of a data source does not automatically grant redistribution rights. Review the applicable provider terms before public deployment or further distribution.
- LevEcho is for research and educational use and is not investment advice.

## Run locally

The project uses the Conda environment `trading`:

```bash
conda run -n trading python -m pip install -r requirements.txt
conda run -n trading streamlit run app.py
```

Run the test suite with:

```bash
conda run -n trading python -m pip install -r requirements-dev.txt
conda run -n trading python -m pytest -q
```

See the [developer documentation](docs/DEVELOPMENT.md) for development, data updates, review, and deployment details.

## Documentation

- [Development and deployment](docs/DEVELOPMENT.md)
- [Data pipeline](docs/DATA_PIPELINE.md)
- [ETF review](docs/ETF_REVIEW.md)
- [Changelog](CHANGELOG.md)
- [中文 README](README.md)
