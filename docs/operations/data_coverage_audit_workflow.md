# Data Coverage Audit Workflow

> 更新时间：2026-05-19  
> 文档定位：定义在继续利润核算、周报/月报前，如何检查 normalized 数据源在数据库里的实际覆盖范围，并按 stable cutoff 判断是否足够稳定。

## 1. 为什么先做 coverage audit

利润 preview 已经能跑通，但在进入更长周期利润复核前，必须先确认：

```text
每个数据源当前库里到底有多少行；
业务日期从哪天到哪天；
是否覆盖 2026-01-01 到 stable cutoff；
哪些表只是 snapshot，不需要每天都有；
哪些表是利润关键源，缺失会影响财务结果或解释能力。
```

Amazon 报表可能延迟或回填，所以审计不应简单要求所有源覆盖到今天。当前采用：

```text
stable_target_end_date = target_end_date - data_window_lag_days
```

## 2. 审计命令

默认目标窗口是 2026-01-01 到当天：

```powershell
python scripts/audit_data_coverage.py --marketplace-id ATVPDKIKX0DER
```

也可以显式指定窗口：

```powershell
python scripts/audit_data_coverage.py --marketplace-id ATVPDKIKX0DER --target-start-date 2026-01-01 --target-end-date 2026-05-18
```

输出默认位于：

```text
runtime/data_coverage_audits/{marketplace_id}/{target_start}_{target_end}/
```

包含：

```text
data_coverage_audit.md
data_coverage_audit.json
data_coverage_audit.csv
report_request_coverage.csv
```

CLI 会打印两组状态：

```text
stable_status_counts=...
raw_status_counts=...
```

判断是否能进入周报/月报时，优先看 `stable_status_counts`。

## 3. Stable status 含义

| 状态 | 含义 | 处理建议 |
|---|---|---|
| `covers_stable_window` | 已覆盖到该数据源的稳定截止日 | 可以进入人工复核。 |
| `ends_before_stable_target` | 有目标窗口数据，但最新业务日期早于稳定截止日 | 需要补数或等待 Amazon 报表可用后重刷。 |
| `starts_after_target_start` | 有数据但历史起点晚于目标开始日 | 如果要做 2026-01-01 至今分析，应补历史数据。 |
| `outside_target_window` | 表有数据，但不在目标窗口内 | 检查 report 请求窗口和 raw 文件。 |
| `no_rows` | 该 marketplace 下没有数据 | 判断是否业务上不需要，还是 ingestion 尚未跑。 |
| `no_business_dates` | 表有行但业务日期无法解析 | 检查源日期字段或 ingestion 映射。 |

## 4. Stable lag 默认规则

| 数据域 | Stable lag |
|---|---:|
| Ads SP core | 3 天 |
| Sales & Traffic | 2 天 |
| Orders | 2 天 |
| Promotion/Coupon | 2 天 |
| FBA Reimbursements | 7 天 |
| Inventory Ledger | 3 天 |
| Inventory / Listing / FBA Fee Preview snapshot | 0 天 |
| Settlement | 0 天，但不是每天都有 |
| SKU Cost | 0 天，内部配置 |

例如今天是 2026-05-19：

```text
Sales & Traffic 稳定截止日：2026-05-17
Ads 稳定截止日：2026-05-16
FBA Reimbursements 稳定截止日：2026-05-12
```

今天/昨天缺失不应直接判定为下载错误。

## 5. 利润复核前的关键源

如果要做 2026-01-01 至今或某个自然周的利润复核，至少先看这些源：

```text
Settlement transaction：财务主口径，必须尽量完整；
SKU cost：内部成本，必须覆盖所有有销售的 SKU；
Orders：SKU/订单运营解释；
Ads SP campaign daily：广告运营解释；
Sales & Traffic date daily：流量/转化解释。
```

Promotion/Coupon、FBA Reimbursements、Inventory Ledger、Inventory snapshot 也很重要，但它们更多用于解释异常、活动效果和库存状态。

## 6. 与 backfill / rolling refresh 的关系

Coverage audit 只是读库，不下载也不入库。推荐顺序：

```text
运行 coverage audit
-> 找出历史缺口和 stable cutoff 缺口
-> 历史 backfill 2026-01-01 到稳定截止日
-> 最近窗口 rolling refresh，重复下载最近 10/14/30/60 天
-> 再运行 coverage audit
-> 核心源通过后，跑利润 preview / 周报
```

不要只做无重叠补数；也不要为了今天/昨天的数据缺失而立即判定失败。

## 7. 分析产物间隔

即使数据刷新每 1-2 天执行一次，正式分析产物仍以周为最小周期：

```text
销售情况周报
广告情况周报
利润周报
库存周报
促销活动周报/活动复盘
```

日报最多作为临时观察，不进入正式系统设计的第一版。
