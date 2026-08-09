# Settlement JSON Set-Based Upsert

> 文档状态：Implemented / Azure verified  
> 更新时间：2026-08-09  
> 迭代版本：v1.85  
> 相关功能：`feature_settlement_ingestion.md`、`feature_settlement_ingestion_batch_upsert.md`、`feature_monthly_chunk_completeness_recovery.md`

## 1. 生产反馈与根因

v1.84 已证明“正常 Settlement ingestion 应从逐行 MERGE 改为 set-based”方向正确，但 Azure 真实 2026-06 recovery 暴露两个性能瓶颈：

```text
prepared Settlement rows = 3921
unique-key staging rows   = 1815
multi-row INSERT batch    = 50 rows / 1950 parameters
staging batches           = 37
duplicate fallback rows   = 2106
```

生产日志进一步显示：

```text
22:34:05 staging started
22:54:35 only batch 25/37 completed
```

因此 v1.84 的 bounded `INSERT ... VALUES (?, ... x 1950)` 本身在当前 Azure SQL Serverless 环境中非常慢；同时 2,106 duplicate-key rows 又会回退 legacy per-row MERGE。v1.84 不能作为长期生产实现。

## 2. 冻结目标

1. 删除正常 ingestion 的 temp-table multi-parameter staging 热路径。
2. 删除 exact duplicate business key 的 per-row fallback。
3. 保持最终 normalized financial row 与旧 sequential MERGE 的 last-write-wins 结果一致。
4. 同一 `business_key_hash` 若映射到不同 immutable source identity，必须 fail closed。
5. 保持 `business_key_hash` immutable、`WITH (HOLDLOCK)`、transaction rollback、failed audit 语义不变。
6. 不新增 migration，不修改 live table schema。
7. 保持旧 audit 的 attempted / inserted / updated / skipped 计数语义。
8. 单次 SQL 参数数量从约 1950 降为 1 个 `NVARCHAR(MAX)` JSON payload parameter。
9. 使用 bounded JSON batch，避免一次发送无限大的 payload。

## 3. Duplicate business key 语义

Settlement business key 来自：

```text
marketplace_id
+ source_report_id
+ source_row_index
+ source_row_hash
```

因此同一合法 `business_key_hash` 的重复 occurrence 应属于同一 immutable source identity，通常来自同一 Amazon report row 被重复恢复/下载。

v1.85 在 SQL 前按 input order 折叠：

```text
same business key + same immutable identity
-> keep last payload
-> collapsed_duplicate_rows += N
```

最后一条 payload 与旧 sequential MERGE 的最终 target state 一致。

如果：

```text
same business_key_hash
but different marketplace/report_id/row_index/source_row_hash
```

则视为 integrity conflict，立即抛错，交由上层 transaction rollback；不猜测、不覆盖。

## 4. Typed OPENJSON source

每批最多 500 个已去重 business keys，Python 序列化成一个 JSON array，并以一个参数传给 Azure SQL：

```sql
OPENJSON(CAST(? AS NVARCHAR(MAX)))
WITH (
    marketplace_id NVARCHAR(50) '$.marketplace_id',
    ...,
    amount DECIMAL(18,4) '$.amount',
    raw_data NVARCHAR(MAX) '$.raw_data',
    source_row_index INT '$.source_row_index',
    business_key_hash NVARCHAR(100) '$.business_key_hash'
)
```

SQL type mapping 与当前 Settlement mapped columns 一一校验；代码字段变更但 type mapping 未同步时直接 fail fast。

每个 JSON batch 只执行一次 target MERGE：

```sql
MERGE dbo.amazon_settlement_transaction WITH (HOLDLOCK) AS target
USING (<typed OPENJSON source>) AS source
ON target.business_key_hash = source.business_key_hash
WHEN MATCHED THEN UPDATE ...
WHEN NOT MATCHED THEN INSERT ...
OUTPUT $action;
```

`business_key_hash` 仍不出现在 UPDATE SET 中。

## 5. Audit count 等价性

假设同一 business key 在当前 input 中出现 `k` 次：

- target 原来不存在：旧 sequential path = `1 INSERT + (k-1) UPDATE`。
- target 原来存在：旧 sequential path = `k UPDATE`。

v1.85 MERGE 只写最终一条 normalized row，但根据 MERGE action 恢复旧 audit 计数：

```text
inserted_rows = unique keys whose final MERGE action = INSERT
updated_rows  = valid_input_rows - inserted_rows
```

因此 `rows_written` 仍代表已接受处理的 source rows，数据库最终 normalized state 与旧路径一致。

## 6. Transaction / 财务安全

事务边界继续使用既有 contract：

```text
running audit -> COMMIT
JSON MERGE batches + schema events + finished audit
  -> success: COMMIT
  -> any exception: ROLLBACK normalized writes
                    update failed audit
                    COMMIT failed audit only
```

如果 JSON batch、OPENJSON 类型转换、MERGE action count 或 duplicate identity validation 任一步异常，当前 Settlement normalized transaction 都必须 rollback。

## 7. 与 v1.83 的关系

v1.83 负责 Monthly Sales & Traffic / Orders / Ads chunk completeness；生产已验证：

```text
Sales & Traffic files_selected=3 coverage_complete=True
Orders files_selected=3 coverage_complete=True
Ads 4 report types x 3 chunks = 12 files
```

v1.85 只替换 Settlement DML transport / merge strategy，不修改 Monthly chunk selection 或 report reconciliation。

## 8. 本地验收标准

```text
3921 unique rows -> 8 JSON MERGE statements at batch_size=500
1201 unique rows -> 3 JSON MERGE statements
one JSON batch -> one SQL parameter
exact duplicate key -> collapse + deterministic last-write-wins
conflicting source identity under same hash -> fail closed
business_key_hash immutable in UPDATE
OPENJSON raw_data uses NVARCHAR(MAX)
full pytest + compileall + CI Safety lint
```

## 9. Azure 验收

当前 v1.84 execution 不应继续作为性能验收。部署 v1.85 后重新执行 2026-06 collect_ingest，不重新 submit。

期望日志：

```text
Settlement JSON set-based upsert input_rows=3921
unique_business_keys=<N>
collapsed_duplicate_rows=<N>
batch_size=500
batches=<single-digit>

Settlement JSON MERGE batch=1/<N> ...
...
Settlement JSON set-based upsert completed ...
Settlement ingestion mode=execute status=success
Automation stage ... failed=0
```

验收重点是 Settlement 阶段由几十分钟降到可接受范围，同时最终 2026-06 Financial Close 不出现数据完整性回退。


## 生产验收结果（2026-08-08）

2026-06 `collect_ingest` 已在 main image `ef6941c97322c717fb86872baac16530271fbe55` 通过 Azure 验收：

```text
Settlement input_rows=3921
unique_business_keys=2868
collapsed_duplicate_rows=1053
batch_size=500
batches=6
JSON MERGE start 23:22:22
JSON MERGE completed 23:22:29
Settlement committed 23:22:33
inserted=0 updated=3921 skipped=0
commands=9 failed=0
```

相比 v1.84 约 20 分钟仍未完成 staging、最终 30 分钟 timeout，v1.85 的 6 个 JSON MERGE 在约 7 秒内完成，Settlement 全阶段约 11 秒完成并提交。随后 2026-07 recovery 再次以 `1491` unique rows / 3 batches 成功执行，证明生产路径稳定。
