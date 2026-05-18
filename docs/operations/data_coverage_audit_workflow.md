# Data Coverage Audit Workflow

> 更新时间：2026-05-18  
> 文档定位：定义在继续利润核算、周报/月报前，如何检查 normalized 数据源在数据库里的实际覆盖范围。

## 1. 为什么先做 coverage audit

利润 preview 已经能跑通，但在进入更长周期利润复核前，必须先确认：

```text
每个数据源当前库里到底有多少行；
业务日期从哪天到哪天；
是否覆盖 2026-01-01 到当前日期；
哪些表只是 snapshot，不需要每天都有；
哪些表是利润关键源，缺失会影响财务结果或解释能力。
```

否则利润偏高/偏低时，很难判断是经营真实结果，还是某个数据源没补齐。

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

## 3. 覆盖状态含义

| 状态 | 含义 | 处理建议 |
|---|---|---|
| `has_target_window_data` | 该表已有目标窗口内的数据 | 可以进入人工复核，但仍要看业务日期范围是否足够长。 |
| `starts_after_target_start` | 该表有目标窗口数据，但最早业务日期晚于目标开始日 | 如需要从 2026-01-01 开始分析，应补历史数据。 |
| `outside_target_window` | 表有数据，但不在目标窗口内 | 优先检查 report 请求窗口和 raw 文件。 |
| `no_rows` | 该 marketplace 下没有数据 | 需要判断是否业务上不需要，还是 ingestion 尚未跑。 |
| `no_business_dates` | 表有行，但业务日期无法解析 | 需要检查源日期字段或 ingestion 映射。 |

## 4. 利润复核前的关键源

如果要做 2026-01-01 至今的利润复核，至少先看这些源：

```text
Settlement transaction：财务主口径，必须尽量完整；
SKU cost：内部成本，必须覆盖所有有销售的 SKU；
Orders：SKU/订单运营解释；
Ads SP campaign daily：广告运营解释；
Sales & Traffic date daily：流量/转化解释。
```

Promotion/Coupon、FBA Reimbursements、Inventory Ledger、Inventory snapshot 也很重要，但它们更多用于解释异常、活动效果和库存状态。

## 5. 与 backfill 的关系

Coverage audit 只是读库，不下载也不入库。推荐顺序：

```text
运行 coverage audit
-> 找出缺失数据源和日期范围
-> 用现有 submit/collect/ingest 脚本补 raw data 和 normalized tables
-> 再运行 coverage audit
-> 确认关键源覆盖后，跑利润 preview
```

不要在不知道当前覆盖范围的情况下直接补很多报表，否则容易重复、混乱，且难以判断哪些数据仍缺失。
