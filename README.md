# LevEcho

> 输入股票价格，根据上一交易日收盘价估算对应单股票杠杆 ETF 的理论价格；也支持从 ETF 价格反推股票价格。

[在线体验](https://levecho.streamlit.app) · [English](README.en.md) · [开发文档](docs/DEVELOPMENT.md)

[![Daily EOD update](https://github.com/Desmond4u/LevEcho/actions/workflows/daily_update.yml/badge.svg)](https://github.com/Desmond4u/LevEcho/actions/workflows/daily_update.yml)
[![Review ETF mappings](https://github.com/Desmond4u/LevEcho/actions/workflows/etf_review.yml/badge.svg)](https://github.com/Desmond4u/LevEcho/actions/workflows/etf_review.yml)

LevEcho 是一个面向美股单股票日重置杠杆 ETF 的双向理论价格计算器。它使用股票和 ETF 最近的共同收盘价作为计算基准，让你快速回答：

- 如果股票上涨或下跌到某个价格，杠杆 ETF 的理想单日价格是多少？
- 如果 ETF 变动到某个价格，对应股票的理论价格是多少？

## 一个简单例子

假设最近共同交易日的收盘价为：

| 标的 | 基准价 |
| --- | ---: |
| 股票 | $100 |
| +2x ETF | $10 |

如果下一目标交易日 ETF 价格为 $12，ETF 上涨 20%，对应股票的理论涨幅为 10%，理论股票价格为 $110。

反向输入股票价格 $110，程序也会得到 ETF 理论价格 $12。

## 计算方式

设股票基准价为 `S0`、ETF 基准价为 `E0`、有符号日目标倍数为 `L`：

```text
ETF 理论价 = E0 × [1 + L × (股票输入价 / S0 - 1)]

股票理论价 = S0 × [1 + (ETF 输入价 / E0 - 1) / L]
```

页面支持直接输入价格，也支持输入涨跌幅；同一股票的多产品可按最近交易日跟踪偏差横向对比，选中的配对、语言与外观会同步到 URL 查询参数，便于直接分享链接。计算基准是股票和 ETF 最近的共同交易日收盘价；输入值代表基准日之后目标交易日的假设价格。周末或节假日没有新的常规收盘价时，数据快照会继续使用最近的共同交易日。

## 当前覆盖范围

- 股票池：S&P 500 与 Nasdaq-100 成分股并集，并保留指数归属信息。
- ETF：来自多个发行商公开资料的单股票日重置产品。
- 支持的有符号日目标倍数：`+1x`、`+2x`、`+3x`、`-1x`、`-2x`、`-3x`。
- 只有参考资产、日目标倍数和产品状态都能由公开资料明确核验的配对才会展示在页面中。

ETF 发现范围包括 Direxion、Tradr、ProShares、GraniteShares、T-REX、Leverage Shares 和 Defiance 等发行商。无法确认或发生元数据变化的产品会进入待审核清单。

## 数据更新

网页访问时只读取仓库中的 `data/latest.json`，不会让每位访问者重复请求行情接口。GitHub Actions 负责：

- 每个工作日收盘后更新 EOD 快照；
- 每周检查指数成分股变化；
- 每周检查 ETF 配对变化，并生成审核 PR。

行情层优先使用 `yfinance`，缺失标的或最新交易日落后于整体时，依次使用 Nasdaq 公共历史行情接口与 Yahoo 1d 报价管线补齐。数据流程和审核边界见：

- [数据流程与日期口径](docs/DATA_PIPELINE.md)
- [ETF 发现与审核流程](docs/ETF_REVIEW.md)

## 重要限制

- 这是单日理论模型，不适合直接套用于多个交易日的累计收益。杠杆 ETF 每日重置，跨日复利会产生偏离。
- 结果不是实时价格、NAV 或交易报价。费用、融资成本、跟踪误差、分红、拆分、ETF 分配、买卖价差和市场价/NAV 偏差都会影响实际结果。
- 页面使用未复权收盘价；检测到分红、拆分或 ETF 分配时会显示警告。
- 数据源的公开可访问性不等于允许任意再分发。公开部署和进一步使用前，请核对相关数据提供方的条款。
- LevEcho 仅供研究和教育用途，不构成投资建议。

## 本地运行

请先准备一个隔离的 Python 环境，然后安装依赖：

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

运行测试：

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

完整的开发、数据更新、审核和部署说明见 [开发文档](docs/DEVELOPMENT.md)。

## 项目文档

- [开发与部署](docs/DEVELOPMENT.md)
- [数据流程](docs/DATA_PIPELINE.md)
- [ETF 审核](docs/ETF_REVIEW.md)
- [变更记录](CHANGELOG.md)
