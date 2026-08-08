# Feature: Monthly Ingestion Recovery and Settlement Idempotency Hardening

> 文档状态：Implemented locally; Azure repair/recovery verification pending  
> 更新时间：2026-08-08  
> 迭代版本：v1.81  
> 相关功能：`feature_settlement_ingestion.md`、`feature_promotion_coupon_ingestion.md`、`feature_monthly_financial_close_report.md`  
> 相关 ADR：`../adr/ADR-013-schema-guard-compatibility-policy.md`

## 1. 背景

2026-08-05 的 monthly `collect_ingest` 已确认 Amazon SP-API / Ads API 提交和下载正常，但阶段最终失败。生产日志暴露两个独立问题：

```text
Settlement:
pyodbc.IntegrityError
UX_amazon_settlement_transaction_business_key_hash duplicate key

Promotion/Coupon:
requires_review=True
prepared_rows=0
```

Promotion/Coupon 的阻断发生在 v1.79 Schema Guard 鲁棒性规则部署前；其现有 `required_fields` 已与 `expected_fields` 分离，因此 additive new fields 在 ADR-013 新规则下应只告警、不阻断。本迭代需要补回归测试把该行为锁定。

Settlement 则属于独立幂等性/事务问题，必须修复后才能安全补跑 2026-06 / 2026-07 月度数据。

## 2. 根因设计结论

### 2.1 Settlement MERGE 不应同时匹配 canonical key 与 legacy natural key

现有 Settlement repository 与其他 normalized repository 不一致：

```text
ON business_key_hash = source.business_key_hash
OR legacy natural key matches
```

同时 UPDATE 会覆盖 `business_key_hash`。

当历史表中同时存在：

1. 一个已经持有当前 canonical `business_key_hash` 的行；
2. 一个 legacy 行，source identity 相同但 business key 不同；

同一 source row 可命中两个 target row，UPDATE legacy row 到 canonical hash 时会触发唯一索引冲突。

冻结规则：

```text
新写入/重跑：只以 business_key_hash 为 MERGE 条件
business_key_hash：写入后不可变，不在 UPDATE SET 中修改
legacy duplicate：通过显式 maintenance repair 处理，不在日常 ingestion 中静默删除
```

### 2.2 Settlement 失败时必须真正 rollback

现有 Settlement exception path 在报错后更新 failed audit 并 `commit()`，但没有先 rollback，因此前面已经成功的逐行 MERGE 可能被部分提交，与“failed and was rolled back”日志语义不一致。

冻结事务规则：

```text
1. insert running sync_run_log
2. commit audit row，让失败 run 可追踪
3. 开始 normalized data transaction
4. success -> update audit success + commit
5. exception -> rollback data transaction
6. update audit failed + commit audit status
7. re-raise original exception
```

Promotion/Coupon 已有 rollback，但 running audit row 与 data transaction 原先仍在同一事务；本迭代同步采用上述 audit transaction 边界。

## 3. Legacy duplicate repair

不在 ingestion 中自动删除财务行。本迭代增加专用 maintenance command，默认 dry-run。

可安全自动处理的重复定义必须非常严格：

```text
marketplace_id
+ source_report_id
+ source_row_index
+ source_row_hash
```

四项完全一致时，代表同一个 Amazon settlement report 的同一原始行。只有这种 exact source identity duplicate 才允许自动修复。

修复策略：

1. 查找 exact source identity count > 1 的 group。
2. 按当前 canonical business-key 算法计算应有 hash。
3. 若 group 内已有 canonical hash 行，保留该行。
4. 否则保留最新 id 行，并在确认无跨 identity hash 冲突后写入 canonical hash。
5. 删除同 group 其他重复行。
6. 任意 hash 被其他 source identity 占用时 fail closed，不自动删除。
7. 默认 dry-run；只有 `--execute` 才真实修改 Azure SQL。

本功能不新增数据库字段或索引，因此 **不需要 migration**。

## 4. Promotion/Coupon Schema Guard

沿用 ADR-013：

| 变化 | 行为 |
|---|---|
| Amazon 新增未知字段 | warning/event，继续 parse + upsert |
| 已知 optional 字段缺失 | info/warning，继续 |
| required raw path 缺失 | blocking |
| 无法解析/duplicate business key payload 冲突 | blocking |

当前 Promotion required contract：

```text
reportSpecification.reportType
reportSpecification.marketplaceIds[]
```

当前 Coupon required contract：

```text
reportSpecification.reportType
reportSpecification.marketplaceIds[]
```

本迭代重点是增加 additive-drift 回归测试，不扩大 SQL 表字段。

## 5. 本地实现结果

2026-08-08 已完成代码实现：

- Settlement repository MERGE 改为只按 immutable `business_key_hash` 匹配，UPDATE 不再改写 business key。
- Settlement execute 先持久化 running audit；异常时 rollback normalized writes，再记录 failed audit。
- 新增 `scripts/repair_settlement_idempotency.py`，默认 dry-run，只处理 exact source identity duplicates；跨 identity canonical-hash 冲突 fail closed。
- Promotion/Coupon running audit transaction 边界同步加固。
- Promotion/Coupon 已新增 additive new fields non-blocking 与 missing-required blocking 回归测试。
- 本轮不新增 migration，不修改 live database schema spec。
- `PYTHONPATH=src pytest -q` -> `319 passed`。
- `python -m compileall -q scripts src tests` -> success。
- 当前本地环境未安装 Ruff CLI，因此本地未执行 Ruff；CI 继续按 v1.80 Safety lint 规则执行。

## 6. 验收标准

本地：

```text
Settlement MERGE SQL only matches business_key_hash
Settlement UPDATE does not mutate business_key_hash
Settlement failure path rolls back normalized writes
Promotion/Coupon payload with extra unknown fields -> requires_review=False
Promotion/Coupon missing required field -> requires_review=True
settlement duplicate repair dry-run detects exact duplicate groups without writing
settlement duplicate repair execute only removes exact source-identity duplicates
pytest + compileall + safety lint pass
```

Azure 上线后：

```text
1. 先运行 repair_settlement_idempotency.py dry-run
2. 审核 duplicate groups / conflicts
3. 无 conflict 时 --execute
4. 重跑 monthly collect_ingest for 2026-06
5. 重跑 monthly collect_ingest for 2026-07
6. Settlement / Promotion-Coupon 均 exit_code=0
7. monthly report delivery 分别补发 2026-06 / 2026-07
```

旧 weekly 邮件不补发；后续 weekly 从当前周期正常继续。
