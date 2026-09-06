# 开发与部署

本文档面向 LevEcho 的维护者，记录本地运行、数据脚本、GitHub Actions 和 Streamlit 部署约定。面向普通用户的内容请先看仓库根目录的 [README.md](../README.md)。

## 仓库分层

| 路径 | 用途 |
| --- | --- |
| `app.py` | Streamlit 页面；只读取 `data/latest.json` |
| `levecho/model.py` | 纯计算函数和输入校验 |
| `levecho/data.py` | EOD 行情源和备用源适配 |
| `levecho/universe.py` | 指数成分股获取、规范化和变更比较 |
| `levecho/discovery.py` | ETF 发行商资料解析、匹配和审核状态 |
| `levecho/pipeline.py` | 交易日对齐、收益偏差和快照构建 |
| `levecho/io.py` | JSON 读写和时间工具 |
| `data/` | 已批准清单、候选清单和最新行情快照 |
| `config/` | 指数及发行商来源配置 |
| `reports/` | 自动生成的审核报告 |
| `scripts/` | 数据更新和审核入口 |
| `tests/` | 单元测试和 Streamlit 页面测试 |

## 本地环境

请先激活一个隔离的 Python 或 Conda 环境。以下命令假设该环境已经激活：

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

启动页面：

```bash
streamlit run app.py
```

运行测试：

```bash
python -m pytest -q
```

只检查受影响模块时，可以先运行更小的范围：

```bash
python -m pytest tests/test_model.py tests/test_pipeline.py -q
```

## 数据脚本

以下命令会联网，并可能写入清单、快照或报告。执行前应先查看参数，并确认当前分支和工作区状态。

检查指数成分股变化：

```bash
python -m scripts.check_universe
```

为审核 PR 同时写入候选 approved 文件：

```bash
python -m scripts.check_universe --write-approved-proposal
```

检查 ETF 配对：

```bash
python -m scripts.check_etfs
```

生成最新 EOD 快照：

```bash
python -m scripts.update_daily
```

数据文件的职责和日期语义见 [数据流程](DATA_PIPELINE.md)；ETF 配对的审核边界见 [ETF 审核流程](ETF_REVIEW.md)。

## GitHub Actions

三个工作流都支持 `workflow_dispatch` 手动运行，也配置了定时运行：

| 工作流 | 配置时间 | 作用 |
| --- | --- | --- |
| `daily_update.yml` | 周一至周五 18:17，美东时间 | 抓取 EOD 数据并提交 `data/latest.json` |
| `universe_check.yml` | 每周一 09:23，美东时间 | 检查 S&P 500 与 Nasdaq-100 成分变化并创建审核 PR |
| `etf_review.yml` | 每周一 10:37，美东时间 | 检查 ETF 映射并创建审核 PR |

GitHub Actions 的定时任务可能延迟。页面使用快照中的 `published_at`、`base_session` 和 `as_of_session` 展示真实更新时间与交易日。

日常更新失败时，脚本不会发布不完整快照；网页继续读取上一次成功的数据。自动发现出的新配对和元数据变化会进入提案或待审核文件，不能仅凭一次抓取结果直接公开。

## Streamlit 部署

Streamlit Community Cloud 的入口是仓库根目录的 `app.py`。页面访问只加载版本库中的 `data/latest.json`，因此正常的数据更新由 GitHub Actions 完成，页面部署通常不需要手动修改代码。

发布前建议检查：

1. GitHub `main` 分支测试通过；
2. `data/latest.json` 包含完整且日期一致的快照；
3. GitHub Actions 的写入权限和定时运行状态正常；
4. 数据源使用及公开展示条款允许当前部署方式。

## 本地开发日志

个人开发日志放在被 Git 忽略的目录：

```text
notes/devlog/YYYY-MM-DD-topic.md
```

建议每篇日志记录：背景、观察到的问题、验证命令、决定、后续工作。稳定的架构决策和用户可见的功能变化应整理到版本库中的文档或 [CHANGELOG.md](../CHANGELOG.md)，避免只留在个人日志里。
