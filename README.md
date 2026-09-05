# LevEcho

LevEcho 是一个面向美股日重置杠杆 ETF 的单日理论价格计算器。

## 当前能力

- 股票池：S&P 500 与 Nasdaq-100 成分股并集。
- ETF：自动读取 Direxion、Tradr、ProShares、GraniteShares、T-REX、Leverage Shares、Defiance 的公开产品目录，匹配明确的单股票 `+2x`、`+3x`、`-2x`、`-3x` 日目标产品。
- 计算：以最新共同交易日收盘价作为价格基准，输入下一目标交易日的股票或 ETF 假设价格，进行双向理论反推。
- 数据：每日收盘后运行 EOD 更新；网页只读取 `data/latest.json`。
- 页面：Streamlit，带语言图标的中英文切换、日间/夜间模式、股票与 ETF 双向联动选择、双向计算卡片；切换语言或外观保留当前选择和输入。数据警告保留来源原文。更新时间随语言显示为北京时间（GMT+8）或 EST（固定 GMT−5，不随美国夏令时变化）；行情交易日期保持原有口径。

这是单日理论模型，不代表实时价格、NAV 或交易建议。费用、融资成本、跟踪误差、分红、拆分、买卖价差和市场价/NAV偏差都会影响实际结果。

## 计算日期口径

- `as_of_session` 是最新共同交易日；它的股票和 ETF 收盘价是下一目标交易日计算的价格基准。
- `base_session → as_of_session` 用于展示最近已完成交易日的实际涨幅、理想杠杆涨幅和跟踪误差。
- 页面输入价格被视为价格基准日之后目标交易日的假设价格。页面只读取仓库中的日收盘快照，不提供实时行情。

## 本地运行

```bash
conda run -n trading python -m pip install -r requirements-dev.txt
conda run -n trading python -m pytest
conda run -n trading streamlit run app.py
```

首次运行数据更新前，需要先审核指数候选清单：

```bash
conda run -n trading python -m scripts.check_universe
```

确认 `data/universe_candidate.json` 后，将其 `constituents` 复制到 `data/approved_universe.json`，再运行：

```bash
conda run -n trading python -m scripts.update_daily
```

当发行商页面无法解析、数据源失败或配对不明确时，程序保留已有数据并生成待审核信息。

当前本地目录检查得到 193 个高置信度配对，覆盖 93 只股票；例如 `SNDK` 已识别 `SNDG`、`SNDQ`、`SNDU`、`SNXX`。1x、1.25x、1.5x 等产品仍会记录在 `data/pending_pairs.json`，等待后续扩大模型支持范围。

ETF 审核工作流会把自动发现结果写入 `data/approved_pairs_proposal.json`，并通过 PR 提供 `reports/etf_pair_review.md`。新产品可以按高置信度规则自动加入；参考资产或杠杆发生变化的已有产品需要人工核验后再修改 `data/approved_pairs.json`。

## GitHub 连接与公开部署

本地仓库准备完成后，在 GitHub 创建一个空的公开仓库，然后执行：

```bash
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git branch -M main
git add .
git commit -m "Initial LevEcho implementation"
git push -u origin main
```

之后在 Streamlit Community Cloud 中选择这个仓库的 `app.py` 作为入口。GitHub Actions 工作流会在美东收盘后运行，并把最新快照提交回仓库。

## 数据源说明

指数成分清单使用配置化的多级来源：S&P 500 优先使用 S&P 官方页面；Nasdaq-100 优先使用 Nasdaq 的公开成分 JSON 接口，官方页面和 Wikipedia 的专门成分表作为备用。Nasdaq-100 来源必须返回至少 100 条记录，并且接口声明数量必须与实际返回数量一致，避免把截断结果写入股票池。

当前行情层优先使用 yfinance，Nasdaq 公共历史行情接口作为缺失标的的备用源；后者在 Python HTTPS 协商失败时使用本机 `curl` 传输回退。公开发布前应检查数据提供方的使用和再分发条款；若后续改用需要密钥的正式 API，密钥应放在 GitHub/Streamlit Secrets 中，不进入仓库。

## 页面显示与移动端

- 支持手机端单栏计算布局，语言/外观控件并排，快捷情景按钮保留同一行。
- 杠杆标签显示有符号每日目标；快捷情景以当前输入侧的基准价计算，支持双向计算。
- 页面标明纳斯达克100与标普500成分股并集；选择器仅列出已有可用 ETF 配对的股票。
- 输入显示及加减步长按当前一般报价规则：价格 ≥ $1 时 2 位小数、$0.01 步长；低于 $1 时 4 位、$0.0001 步长。原始基准、快捷情景和模型计算不提前舍入；这是理论计算工具，输入显示规则不作为成交价合法性校验。
- 规则核对日期：2026-09-05。[SEC Rule 612 FAQ](https://www.sec.gov/divisions/marketreg/subpenny612faq.htm)；[半美分规则实施延期至 2027 年 11 月首个工作日](https://www.sec.gov/files/rules/exorders/2026/34-105656.pdf)。新规则实施时需重新核对逐标的报价步长。
