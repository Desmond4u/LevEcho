# Changelog

## Unreleased

- 新增 `ci.yml`：push 与 PR 时自动安装开发依赖并运行全量 pytest。
- 快照构建通过 NYSE 交易日历（`exchange_calendars`）验证基准日与最新日相邻：节假日与周末跨跃正常通过，缺失中间行情或出现非交易日数据时构建失败，避免把跨日累计收益当作单日收益。
- 锁定 `requirements.txt` / `requirements-dev.txt` 到实测可用的精确版本，避免每日 Actions 安装到行为有变的新版本。
- 备用行情源除覆盖主源完全缺失的标的外，也在标的最新交易日落后于全体标的时补齐缺失交易日，规避 `yfinance` 历史行情对低流动性 ETF 收盘价的回填滞后。
- 重写 GitHub 首页 README，突出产品用途、计算示例、数据范围和模型限制。
- 增加英文版 [README.en.md](README.en.md)。
- 将数据流程、ETF 审核、开发和部署说明拆分到 `docs/`。
- 增加本地 `notes/` 开发日志目录约定，并加入 `.gitignore`。
