# Data Refresh Policy

> 更新时间：2026-05-19  
> 文档定位：定义数据下载/入库的滚动刷新策略，以及它和周报/月报分析产物之间的关系。本文件不定义利润公式；利润口径见 `docs/features/feature_profit_calculation.md`。

## 1. 冻结结论

当前项目采用：

```text
Overlapping rolling refresh + normalized upsert + weekly-or-longer analysis
```

含义：

```text
数据刷新可以每 1-2 天执行一次；
每次下载多日窗口，窗口之间故意重叠；
normalized 表使用 MERGE/upsert 覆盖同一业务 key 的当前值；
分析产物最短周期是一周，不做日报结论。
```

因此不要采用：

```text
1月1日-1月7日下载一次
1月8日-1月14日下载一次
```

而应采用：

```text
5月19日下载最近 7-14 天
5月21日再下载最近 7-14 天
5月23日继续下载最近 7-14 天
```

这样同一业务日期会被多次刷新，Amazon 后续回填或归因变化可以被 upsert 覆盖到 normalized 表里。

## 2. 为什么不做多版本共存

当前 normalized 表只保留业务 key 的当前最新版本：

```text
business_key_hash 相同 -> MERGE MATCHED -> UPDATE
business_key_hash 新增 -> MERGE NOT MATCHED -> INSERT
```

不采用：

```text
同一业务 key 多行版本共存，然后查询时取 latest created_at/updated_at
```

原因：

1. 周报/月报查询更简单，不容易重复计算。
2. 手动阶段更不容易因为重复导入导致金额翻倍。
3. 滚动刷新与 upsert 天然匹配。
4. 审计追溯应依赖 raw file、sync run log 和 `source_*` 字段，而不是让分析表膨胀成多版本表。

## 3. 刷新频率与分析频率分离

需要明确区分：

| 类型 | 目的 | 频率 |
|---|---|---|
| 数据刷新 | 补数据、刷新延迟/回填/归因变化 | 可每 1-2 天 |
| 数据覆盖审计 | 检查稳定截止日前是否覆盖 | 周报前、补数后、月报前 |
| 分析产物 | 销售周报、广告周报、利润周报/月报 | 最短一周 |
| 邮件发送 | 给内部/会计发送确认后的报告 | 周报/月报确认后 |

也就是说，可以每天或隔天刷新数据，但不要每天生成正式经营结论。

## 4. 建议刷新策略

| 数据域 | 刷新频率 | 每次刷新窗口 | 稳定滞后 | 分析用途 |
|---|---:|---:|---:|---|
| Ads SP core | 每 2 天 | 最近 14 天 | T-3 | 广告周报、关键词/搜索词优化 |
| Sales & Traffic | 每 2 天 | 最近 10 天 | T-2 | 销售/流量/转化周报 |
| Orders | 每 2 天 | 最近 10 天 | T-2 | SKU/订单结构周报，非财务收入源 |
| Promotion/Coupon | 活动期每 2 天；非活动期每周 | 最近 30 天或活动期 | T-2 | 促销/优惠券周报和活动复盘 |
| Inventory snapshot | 每 2 天或周报前 | 当前快照 | T | 周报库存余额 |
| Listing snapshot | 每周；listing 变更后立即跑 | 当前快照 | T | Listing 状态复核 |
| Settlement | 每周 discovery/ingest | 最近 60 天 | T | 财务主口径 |
| FBA Reimbursements | 每周 | 最近 60 天 | T-7 | 赔偿/异常解释 |
| Inventory Ledger | 每周 | 最近 30 天 | T-3 | 库存变动解释 |
| FBA Fee Preview | 每周或费用变动后 | 当前快照 | T | 费用预估参考 |
| SKU Cost | 进货/成本变化/复核前 | 全量 SKU 模板 | n/a | 内部标准成本 |

## 5. Stable cutoff 规则

正式分析不直接要求覆盖到今天。对会变化的数据源，按稳定截止日判断：

```text
stable_target_end_date = target_end_date - data_window_lag_days
```

例：今天是 2026-05-19。

```text
Sales & Traffic lag = 2 -> 稳定截止日 2026-05-17
Ads lag = 3 -> 稳定截止日 2026-05-16
FBA Reimbursements lag = 7 -> 稳定截止日 2026-05-12
```

因此 Seller Central 最近 7 天报表下载不到今天或昨天，不应默认判断为失败。只有稳定截止日前仍缺数据，才应进入补数或排查。

## 6. 历史 backfill 与 rolling refresh 的区别

历史补数：

```text
目标：尽量补齐 2026-01-01 到稳定截止日的数据。
频率：一次性或阶段性。
方式：按较大窗口下载/入库，直到 coverage audit 通过。
```

滚动刷新：

```text
目标：让最近数据持续吸收延迟、回填和广告归因变化。
频率：核心源每 2 天，慢源每周。
方式：重复下载最近 10/14/30/60 天窗口，并 upsert 覆盖。
```

分析加工：

```text
目标：生成销售周报、广告周报、利润周报/月报。
频率：最短一周。
方式：基于 normalized 当前值和 stable cutoff 生成，不使用今天/昨天作为最终结论。
```

## 7. 对 pipeline_job_config 的影响

`pipeline_job_config` 记录的是“刷新/加工任务建议如何运行”，不是最终业务分析口径。

本策略新增对应 seed：

```text
sql/seeds/002_update_ingestion_job_config_refresh_policy.sql
```

该 seed 会把核心数据刷新调整为：

```text
Ads：每 2 天，lookback 14，lag 3
Sales & Traffic：每 2 天，lookback 10，lag 2
Orders：每 2 天，lookback 10，lag 2
Promotion/Coupon：活动期每 2 天，lookback 30，lag 2
Inventory snapshot：每 2 天，当前快照
Settlement：每周，lookback 60
FBA Reimbursements：每周，lookback 60，lag 7
Inventory Ledger：每周，lookback 30，lag 3
Profit/Weekly Report/Email：周度，不做日报输出
```

## 8. 验收标准

本策略完成后的最低验收：

1. 文档明确区分数据刷新频率和分析产物频率。
2. `pipeline_job_config` 可通过 seed 002 更新推荐刷新窗口。
3. `scripts/audit_data_coverage.py` 输出 stable status，而不是只看是否覆盖到今天。
4. 周报/月报功能设计必须以一周为最小分析间隔。
5. 不引入 normalized 多版本共存表。
