# 数据流程与日期口径

LevEcho 的网页读取已经生成的快照，不在用户访问页面时抓取行情。数据更新由脚本和 GitHub Actions 完成，目标是让股票和 ETF 的价格、交易日、来源保持可追溯。

## 数据文件

| 文件 | 作用 |
| --- | --- |
| `config/index_sources.json` | S&P 500 和 Nasdaq-100 的成分股来源配置 |
| `config/issuer_sources.json` | ETF 发行商目录和解析配置 |
| `data/approved_universe.json` | 当前已批准的股票池 |
| `data/universe_candidate.json` | 指数检查脚本生成的候选股票池 |
| `data/approved_pairs.json` | 当前已批准的 ETF 配对 |
| `data/approved_pairs_proposal.json` | ETF 检查脚本生成的配对提案 |
| `data/pending_pairs.json` | 无法自动确认或发生变化、等待审核的记录 |
| `data/latest.json` | Streamlit 使用的最新完整行情快照 |
| `reports/` | 指数和 ETF 审核报告 |

一次抓取失败或空响应不能被解释为全部成分股退出。指数和 ETF 变更先进入候选、提案或审核报告，确认后再更新已批准清单。

## 每日行情更新

`scripts.update_daily` 的流程如下：

1. 读取已批准股票池和 ETF 配对；
2. 根据发行商来源刷新配对元数据；
3. 使用 `yfinance` 获取日线收盘价；
4. 对缺失标的，或最新交易日落后于全体标的最新交易日的（如 `yfinance` 历史行情对低流动性 ETF 的收盘价回填滞后），使用 Nasdaq 公共历史行情接口补齐缺失交易日；
5. 为每个配对寻找共同的最近两个交易日；
6. 检查所有活跃配对的日期是否一致；
7. 构建并原子写入 `data/latest.json`。

行情请求使用未复权收盘价，并尽量保留分红、拆分等公司行为字段。数据源缺少这些字段时，字段缺失不会被当作“已确认没有公司行为”。

## 日期语义

快照中有两组容易混淆的日期：

- `as_of_session`：最近的共同交易日。
- `calculation_base_session`：下一目标交易日计算使用的基准日，当前与 `as_of_session` 相同。
- `base_session`：再前一个共同交易日，用于展示最近一段实际涨幅和理想杠杆涨幅。

对应价格字段为：

- `calculation_base_stock_close` / `calculation_base_etf_close`：页面理论价格计算基准；
- `latest_stock_close` / `latest_etf_close`：最近共同交易日价格；当前与计算基准价格相同；
- `base_stock_close` / `base_etf_close`：前一个共同交易日价格，用于历史对比。

因此，如果最近一个共同交易日是周五，周一页面输入的价格会相对于周五收盘价计算。输入值代表基准日之后目标交易日的假设价格。周末和节假日不会凭空生成新的常规收盘价。

当前实现会检查共同日期数量、双方最新日期以及所有活跃配对的日期一致性；它还没有接入交易所日历来验证两个共同日期是否严格相邻。缺失的中间行情不会通过前向填充隐藏。

## 快照字段

顶层快照至少包含：

```text
model_version
source_status
calculation_base_session
base_session
as_of_session
published_at
pairs[]
```

每个配对记录股票、ETF、有符号杠杆、两组基准价格、最近价格、来源、实际收益、理想杠杆收益、跟踪误差和警告。`published_at` 是生成快照的实际 UTC 时间，页面再根据语言格式化展示。

## 失败处理

只有所有活跃配对都能形成完整、日期一致的快照时，更新脚本才发布新 `latest.json`。数据不完整时保留上一次成功快照，并将错误输出给工作流；这样网页不会展示日期混杂或空的公开数据。

## 使用和再分发

`yfinance` 和 Nasdaq 公共接口都属于外部数据服务。公开可访问性不代表可以无条件再分发数据。部署或扩大数据使用范围前，应核对各服务的条款、频率限制和允许用途；需要密钥的正式数据源应通过 GitHub Secrets 或 Streamlit Secrets 注入。
