# LevEcho

LevEcho 是一个面向美股日重置杠杆 ETF 的单日理论价格计算器。

## 当前能力

- 股票池：S&P 500 与 Nasdaq-100 成分股并集。
- ETF：自动读取发行商产品目录，匹配明确的单股票 `+2x`、`+3x`、`-2x`、`-3x` 日目标产品。
- 计算：输入股票价格反推 ETF 理论价格，或输入 ETF 价格反推股票理论价格。
- 数据：每日收盘后运行 EOD 更新；网页只读取 `data/latest.json`。
- 页面：Streamlit。

这是单日理论模型，不代表实时价格、NAV 或交易建议。费用、融资成本、跟踪误差、分红、拆分、买卖价差和市场价/NAV偏差都会影响实际结果。

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

当前行情层优先使用 Nasdaq 公共历史行情接口，yfinance 作为缺失标的的备用源。公开发布前应检查数据提供方的使用和再分发条款；若后续改用需要密钥的正式 API，密钥应放在 GitHub/Streamlit Secrets 中，不进入仓库。
