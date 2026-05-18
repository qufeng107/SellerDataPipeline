# ADR-010: Overlapping Rolling Refresh with Weekly-or-Longer Analysis

> 状态：Accepted  
> 日期：2026-05-19

## Context

Amazon 报表存在延迟、回填和归因变化。Seller Central 手动选择最近 7 天时，今天或昨天可能不会完整出现。广告归因、促销效果、订单状态、赔偿和库存调整也可能在后续几天改变。

同时，项目当前目标不是做日报，而是至少按周生成销售、广告、利润和运营复盘。

## Decision

项目采用：

```text
Overlapping rolling refresh + normalized upsert + weekly-or-longer analysis
```

具体决策：

1. normalized 表继续采用 `business_key_hash` + MERGE/upsert 覆盖当前业务行。
2. 不做 normalized 多版本共存。
3. 会变化的数据源采用重叠窗口刷新。
4. 核心经营数据可以每 1-2 天刷新一次。
5. 每次刷新多日窗口，避免一次只拉一天。
6. 周报/月报等分析产物最短周期为一周，不做日报结论。
7. 数据覆盖审计使用 source-specific stable cutoff，不要求 volatile 源覆盖到今天。

## Consequences

优点：

1. 手动和未来自动化都更简单。
2. 最近数据可以持续被修正和覆盖。
3. 周报/月报不会因为今天/昨天未稳定数据而误判。
4. 报表查询不需要复杂的 latest-version window function。

代价：

1. normalized 表无法直接查看同一业务 key 的历史版本变化。
2. 若需要审计某次导入前后的变化，需要依赖 raw file、sync run log、`source_*` 字段和后续 raw file registry 增强。

## Implementation notes

对应文档：

```text
docs/operations/data_refresh_policy.md
docs/operations/ingestion_job_cadence_catalog.md
docs/operations/data_coverage_audit_workflow.md
```

对应 seed：

```text
sql/seeds/002_update_ingestion_job_config_refresh_policy.sql
```

对应脚本增强：

```text
scripts/audit_data_coverage.py
src/seller_data_pipeline/services/data_coverage_service.py
```
