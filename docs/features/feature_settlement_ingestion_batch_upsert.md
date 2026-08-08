# Settlement Normal Ingestion Batch Upsert

> 文档状态：Implemented locally / Azure verification pending  
> 更新时间：2026-08-08  
> 迭代版本：v1.84  
> 相关功能：`feature_settlement_ingestion.md`、`feature_monthly_chunk_completeness_recovery.md`、`feature_settlement_repair_scalability.md`

## 1. 背景

2026-06 Monthly recovery 在 v1.82 repair 完成后成功执行正常 Settlement ingestion：

```text
prepared_rows=3921
inserted=1369
updated=2552
status=success
```

但 `sdp-monthly-collect-ingest` 总耗时约 17 分钟。代码检查确认正常 Settlement repository 仍对每一行执行一次：

```text
MERGE ...
OUTPUT $action
fetchone()
```

因此 3,921 rows 约产生 3,921 次 Azure SQL round trip。此前 v1.82 只优化了历史 duplicate repair maintenance path，并未优化正常 ingestion path。

## 2. 与 v1.83 的关系

v1.83 解决 Monthly 数据完整性：Sales & Traffic / Orders / Ads 多 chunk 选择、目标月 coverage window，以及 Ads timing reconciliation。

v1.84 只改变 Settlement repository 的写入执行方式：

```text
v1.83: which raw files / rows must be ingested
v1.84: how prepared Settlement rows are written efficiently
```

两者职责正交。v1.84 不改变 v1.83 manifest-bound period selection、coverage gate、Sales/Orders/Ads 行为或 report reconciliation policy，因此可以在月报恢复前一起部署并验证。

## 3. 冻结目标

1. 将正常 Settlement ingestion 从 per-row MERGE 改为 bounded staging + set-based MERGE。
2. 保持 immutable `business_key_hash` 为唯一 MERGE match key。
3. 保持一个 ingestion run 内原子事务：任何 staging / MERGE / audit 异常都 rollback normalized writes。
4. 不修改 live table schema，不新增 migration。
5. SQL Server 单 statement 参数数量保持在安全上限内。
6. 对输入内重复 `business_key_hash` 保持旧 per-row 语义，避免 SQL Server MERGE 的 multiple source rows matching one target 错误。
7. 保留准确 inserted / updated / skipped audit counts。
8. 增加 bounded progress logging 和大批量回归测试。

## 4. 设计

### 4.1 输入分类

先过滤缺少 `business_key_hash` 或 `source_row_index` 的无效行，计入 `skipped_rows`。

对剩余行按 `business_key_hash` 计数：

- 只出现一次的 key -> set-based staging path。
- 同一 run 内出现多次的 key -> 保持 single-row MERGE fallback，按原顺序处理，确保行为与旧实现一致。

### 4.2 Typed temporary staging table

在同一个 Azure SQL connection / transaction 内创建 local temp table：

```sql
SELECT TOP (0) <mapped columns>
INTO #settlement_upsert_stage
FROM dbo.amazon_settlement_transaction;
```

这样 staging columns 直接继承生产 target column types，避免 Python 自行维护第二套 SQL type mapping。

### 4.3 Bounded multi-row INSERT

Settlement target 当前 39 mapped columns。SQL Server statement parameter hard limit 为 2100；代码使用 2000 的安全预算并动态计算实际 batch size：

```text
max rows per batch = floor(2000 / column_count)
```

当前 39 columns 时最大 51 rows/batch；默认请求 50 rows/batch。

每批执行：

```sql
INSERT INTO #settlement_upsert_stage (...)
VALUES (?, ...), (?, ...), ...;
```

3,921 rows 在没有 duplicate-key fallback 时约为 77-79 个 staging INSERT round trips，而不是 3,921 个 target MERGE round trips。

### 4.4 Single set-based MERGE

全部 unique-key staging rows 装载完成后执行一次：

```sql
MERGE dbo.amazon_settlement_transaction WITH (HOLDLOCK) AS target
USING #settlement_upsert_stage AS source
ON target.business_key_hash = source.business_key_hash
WHEN MATCHED THEN UPDATE ...
WHEN NOT MATCHED THEN INSERT ...
OUTPUT $action;
```

`business_key_hash` 不在 UPDATE set 中，继续保持 immutable key contract。

### 4.5 Duplicate-key fallback

如果同一个 ingestion input 内同一 `business_key_hash` 出现多次，不能把这些行同时放入一个 MERGE source，否则 target 已存在时 SQL Server 可能报：

```text
MERGE attempted to UPDATE or DELETE the same row more than once
```

因此这些 key 的所有 occurrences 从 staging path 排除，继续逐行使用旧 single-row MERGE。正常 Amazon Settlement prepared rows 理论上应极少触发该 fallback；它优先保证语义与安全。

### 4.6 Transaction contract

事务边界不变：

```text
insert running audit -> COMMIT
normalized batch upsert + schema events + finished audit
  -> success: COMMIT
  -> any exception: ROLLBACK normalized writes
                    update failed audit
                    COMMIT failed audit only
```

Temp table 与业务 DML 都处于 normalized transaction 内，不引入 partial financial commits。

## 5. 不做的事情

- 不修改 Settlement parser / business key algorithm。
- 不修改 Settlement repair v1.82 safety contract。
- 不修改 live unique index。
- 不新增 permanent staging table。
- 不使用 `--allow-blocked` 绕过 Monthly report send guard。

## 6. 验收标准

本地：

```text
large unique-key input uses bounded multi-row staging inserts + one set-based MERGE
no staging INSERT exceeds 2000 SQL parameters
duplicate business keys use per-row fallback
business_key_hash remains immutable in UPDATE
insert/update/skip counts preserved
rollback/audit tests remain green
full pytest + compileall + Safety lint
```

Azure：

```text
rerun 2026-06 monthly collect_ingest without re-submit
Settlement status=success
same logical rows remain idempotent
runtime materially lower than previous ~17 minute collect
commands=9 failed=0
```

完成后继续生成 2026-06 Monthly Financial Close；确认真正财务 checks 正常后才发送邮件，再恢复 2026-07。

## 7. 本地实现结果

```text
PYTHONPATH=src pytest -q
335 passed

python -m compileall -q scripts src tests
COMPILE_OK

Markdown internal links
0 missing
```

当前环境未安装 Ruff CLI；CI blocking Safety lint 仍由 GitHub Actions 执行（E4/E7/E9/F/B）。
