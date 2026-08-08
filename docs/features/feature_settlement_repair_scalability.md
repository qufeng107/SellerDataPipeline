# Feature: Settlement Duplicate Repair Scalability and Bounded Diagnostics

> 文档状态：Implemented locally; Azure v1.82 verification pending  
> 更新时间：2026-08-08  
> 迭代版本：v1.82  
> 相关功能：`feature_monthly_ingestion_recovery.md`、`feature_settlement_ingestion.md`

## 1. 背景

v1.81 增加了 `scripts/repair_settlement_idempotency.py`，用于在补跑月报前安全清理历史 Settlement exact source-identity duplicates。Azure dry-run 暴露出明显的性能问题：数据库已显式 warm-up 且处于 `Online`，repair execution 运行超过 5 分钟仍无业务输出。

随后执行只读诊断：

```text
amazon_settlement_transaction rows = 12,210
exact duplicate groups            = 3,878
COUNT rows elapsed                = 0.22s
duplicate GROUP BY elapsed        = 0.19s
```

因此数据库扫描本身不是瓶颈。v1.81 repair planner 对每个 duplicate group 再执行两次 repository 查询，形成约：

```text
1 + 2 * 3,878 = 7,757 SQL round trips
```

此外 v1.81 execute path 会逐 group DELETE / UPDATE；大量 `DELETE ... IN (...)` 还可能触及 SQL Server 2100 parameters 限制。`--json` 默认输出全部 3,878 plans 也会导致 Azure console / Log Analytics 输出过大。

## 2. 目标

本迭代优先保证维护工具的：

1. **性能可预测**：repair planning 不随 duplicate group 数量线性增加 SQL round trips。
2. **财务安全不降级**：exact source identity 才允许自动合并，cross-identity canonical hash conflict 仍 fail closed。
3. **执行可批量化**：DELETE / rekey 在 SQL Server 参数限制内分批执行。
4. **日志有界**：默认输出 summary + 有限 plan sample，不向 Azure 日志写入几千个 plan。
5. **无数据库结构变化**：当前 12,210 行数据规模可通过单次 bounded scan + Python 分组完成，不新增 migration / index。

## 3. 冻结设计

### 3.1 Planning 改为 single-scan + in-memory grouping

v1.81：

```text
GROUP BY duplicate identities
-> for each duplicate group:
     SELECT group rows
     SELECT canonical owner
```

v1.82：

```text
SELECT repair-required identity/ownership columns once
-> Python builds:
     identity -> rows
     business_key_hash -> owner rows
-> Python computes all repair plans
```

单次扫描字段：

```text
id
marketplace_id
source_report_id
source_row_index
source_row_hash
business_key_hash
source_raw_file_path
source_run_id
```

对指定 marketplace 使用 `WHERE marketplace_id = ?`，避免无关 marketplace 数据进入内存。

### 3.2 Safety contract 不变

可自动 repair 的 identity 仍必须四项完全一致：

```text
marketplace_id
source_report_id
source_row_index
source_row_hash
```

对每个 duplicate group：

1. 计算当前 canonical `business_key_hash`。
2. 若 canonical hash 被 group 外 row 占用 -> `conflict`，整个 execute blocked。
3. 若 group 内已有唯一 canonical row -> 保留该 row。
4. 若 group 内没有 canonical row -> 保留最大 id（最新 provenance）并计划 rekey。
5. 若 group 内异常出现多个 canonical owner -> `conflict`。
6. 其余 exact duplicates 才进入 delete plan。

### 3.3 Execute 改为 bounded batch DML

DELETE：

```text
all delete ids
-> batches of <= 1000 ids
-> DELETE ... WHERE id IN (?, ...)
```

Rekey：

```text
(id, canonical_hash) rows
-> batches of <= 900 rows
-> UPDATE ... FROM (VALUES (?, ?), ...)
```

900 rows = 1800 SQL parameters，低于 SQL Server 2100 parameter limit。

删除在前、rekey 在后；任意异常 rollback 整个 repair transaction。

### 3.4 Bounded output

默认 CLI：

```text
--json
-> summary counts
-> conflict_plan_sample <= 20
-> repairable_plan_sample <= 20
```

只有显式：

```text
--include-plans
```

才输出全部 plan。这样生产诊断不会因为数千 duplicate groups 造成 console/log ingestion 过载。

## 4. 主要代码路径

```text
scripts/repair_settlement_idempotency.py
src/seller_data_pipeline/ingestion/settlement_idempotency_repair.py
src/seller_data_pipeline/db/repositories/settlement_repo.py
tests/unit/ingestion/test_settlement_idempotency_repair.py
tests/unit/db/test_settlement_repo.py
```

## 5. 数据库变更判断

```text
Current schema already supports this feature.
```

本迭代不新增 migration、不修改 live schema spec。当前生产诊断已证明 12,210 rows 的 aggregate/group scan 均低于 0.25s；瓶颈来自客户端 N+1 round trips，而不是缺少索引。

## 6. 验收标准

本地：

```text
4000 duplicate groups can be planned entirely in memory
service performs one repository scan, not per-group SELECTs
large delete id list is batched <= 1000 parameters/query
large rekey list is batched <= 1800 parameters/query
cross-identity canonical owner remains blocking
full test suite + compileall + Safety lint pass
```

Azure dry-run：

```text
repair scan produces progress logs
scanned_rows ~= 12,210
duplicate_groups ~= 3,878
execution completes in a practical bounded time
rows_deleted=0
conflict_group_count reviewed before execute
```

Azure execute only after dry-run shows `conflict_group_count=0`：

```text
rows_deleted == rows_to_delete
rows_rekeyed == rows_to_rekey
rerun dry-run -> duplicate_group_count=0
```

完成后才继续 2026-06 / 2026-07 monthly collect_ingest 和 report delivery。
