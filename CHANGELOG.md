# Changelog

## Unreleased

- 锁定 `requirements.txt` / `requirements-dev.txt` 到实测可用的精确版本，避免每日 Actions 安装到行为有变的新版本。
- 备用行情源除覆盖主源完全缺失的标的外，也在标的最新交易日落后于全体标的时补齐缺失交易日，规避 `yfinance` 历史行情对低流动性 ETF 收盘价的回填滞后。
- 重写 GitHub 首页 README，突出产品用途、计算示例、数据范围和模型限制。
- 增加英文版 [README.en.md](README.en.md)。
- 将数据流程、ETF 审核、开发和部署说明拆分到 `docs/`。
- 增加本地 `notes/` 开发日志目录约定，并加入 `.gitignore`。
