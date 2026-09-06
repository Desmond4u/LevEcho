# ETF 发现与审核流程

LevEcho 只把高置信度的单股票日重置杠杆 ETF 展示给公众。产品名称或 ticker 的相似性可以帮助发现候选，但不能单独作为正式配对依据。

## 自动发现的范围

发行商来源配置位于 `config/issuer_sources.json`。当前配置覆盖 Direxion、Tradr、ProShares、GraniteShares、T-REX、Leverage Shares 和 Defiance 等公开产品目录。

候选产品需要尽量从发行商页面、产品目录或招募说明书中确认：

- ETF ticker；
- 明确的参考股票或指数；
- 有符号的每日目标倍数；
- 产品仍处于交易状态；
- 产品属于单股票日重置结构。

当前自动上线的目标倍数为：

```text
+1x、+2x、+3x、-1x、-2x、-3x
```

## 配对准入

只有同时满足以下条件，候选才具备自动批准资格：

1. 参考资产代码与已批准股票池代码明确一致；
2. 发行商资料明确写出每日目标倍数；
3. 发行商资料没有产品名称、参考资产或杠杆方向歧义；
4. 股票和 ETF 可以取得同一交易日的收盘数据；
5. 产品没有处于更名、分拆、清算或终止等需要人工确认的状态。

参考资产或杠杆变化属于存量配对元数据变化，也需要人工核验。待审核记录不会直接展示在公开页面。

## 文件状态

| 状态 | 文件 | 含义 |
| --- | --- | --- |
| 已批准 | `data/approved_pairs.json` | 页面和每日快照允许使用的配对 |
| 提案 | `data/approved_pairs_proposal.json` | 自动发现后建议纳入或更新的配对 |
| 待审核 | `data/pending_pairs.json` | 证据不足、资料歧义或状态变化的记录 |
| 报告 | `reports/etf_pair_review.md` | 本次检查的发行商统计、错误和待处理变化 |

## 审核流程

手动运行检查：

```bash
conda run -n trading python -m scripts.check_etfs
```

检查结果会更新提案、待审核清单和报告。GitHub Actions 每周运行同一检查并创建 PR。审核 PR 时：

1. 打开 `reports/etf_pair_review.md`；
2. 对每个新配对或元数据变化查看发行商原始资料；
3. 核对 ticker、参考股票、方向、倍数和产品状态；
4. 确认后再把配对写入 `data/approved_pairs.json`；
5. 合并 PR，让下一次每日更新使用新的已批准配置。

如果发行商页面不可解析、多个来源互相矛盾或参考资产无法明确确认，应保留在 `pending_pairs.json`，并在审核记录中说明原因。
