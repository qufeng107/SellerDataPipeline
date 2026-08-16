# v1.90-v1.90.3 Natural-Month Finances Azure Rollout and Closeout

> 状态：Completed / production verified  
> 更新时间：2026-08-10  
> 目标：记录从 v1.89 sampling 到 v1.90.3 production rollout 的完整 Gate、最终证据、回滚边界和运维注意事项。历史 2026-05/06/07 邮件不重发。

## 1. 最终生产状态

```text
Production version: v1.90.3
Image:
  ghcr.io/qufeng107/seller-data-pipeline:2fa19ad316720742d1871765fa0c1149c6b9fb9a

Monthly jobs:
  sdp-monthly-submit
  sdp-monthly-collect-ingest
  sdp-monthly-report-delivery
```

正式命令：

```text
submit:
  run_automation_stage.py --workflow monthly --phase submit ... --execute

collect_ingest:
  run_automation_stage.py --workflow monthly --phase collect_ingest ... --execute
  # fail-closed; no --continue-on-error

report_delivery:
  run_automation_stage.py --workflow monthly --phase report_delivery ... --execute --send-email
```

Weekly jobs 不属于本次版本切换范围。

## 2. 为什么升级

Settlement posted/release timing 适合 Amazon close/cash reconciliation，但不能直接代表 marketplace natural month。v1.87/v1.88 的 Management P&L 曾混用 Settlement posted-date operating rows 与 Ads API report-date spend，月份语义不一致。

v1.89 live Finances sampling 证明：Seller Central Monthly Transaction 可通过 Finances API + `America/Los_Angeles` local-month + lifecycle normalization 精确还原。于是 v1.90 正式建立 `amazon_finance_transaction` natural-month ledger，并把 Management Operating P&L 切到该 ledger；Settlement Close 保留独立视图。

## 3. Gate 历史

### Gate 0 — CI

每个版本正常通过项目 CI quality gate；不绕过 Safety lint。

### Gate 1 — migration 016

执行命令使用实际 CLI 参数 `--file`：

```bash
python scripts/run_sql_migration.py \
  --file sql/migrations/016_create_finances_natural_month_ledger.sql
```

Azure 结果：

```text
Migration executed successfully: 3/3 batches
amazon_finance_transaction exists=True
IX_amazon_finance_transaction_marketplace_local_date exists
UX_amazon_finance_transaction_business_key_hash unique=True
initial rows=0
```

### Gate 2 — May/June/July dry-run

最终 v1.90.1 结果：

| Month | Product Sales | Shipment units | Liquidation units | Management units | review_required |
|---|---:|---:|---:|---:|---:|
| 2026-05 | 2316.38 | 94 | 5 | 99 | 0 |
| 2026-06 | 2870.06 | 120 | 2 | 122 | 0 |
| 2026-07 | 1464.14 | 58 | 4 | 62 | 0 |

Seller Central reconciliation anchors：

```text
2026-05 Orders 1915.68 / Refunds -355.95 / Liquidation 2.30
2026-06 Orders 2184.16 / Refunds -380.50 / Liquidation 0.55
2026-07 Orders 1097.24 / Refunds -209.00 / Liquidation 2.08
```

June 的两个额外 units 被证明是 `RELEASED Shipment amount=0`，不进 revenue 但进入 COGS。

### Gate 3A — first execute backfill

```text
2026-05 attempted=227 inserted=227 updated=0
2026-06 attempted=264 inserted=264 updated=0
2026-07 attempted=161 inserted=161 updated=0
Total rows=652
review_required=0
```

独立 SQL postcheck：三个月 row count / unique transaction IDs / USD / timezone / amounts / units 全部通过。

### Gate 3B — idempotency

第二次 execute：

```text
2026-05 inserted=0 updated=227
2026-06 inserted=0 updated=264
2026-07 inserted=0 updated=161
row_count=652
transaction_id_count=652
review_required_count=0
```

June 保留：

```text
zero_value_cogs_rows=2
zero_value_cogs_units=2
```

### Gate 4 — Monthly Financial Close preview

v1.90.1 初次 Gate 4 暴露两个 FNSKU cost identity 缺口：

```text
May  X004Q3AKFX
July X004WU7DSH
```

v1.90.2 通过历史 inventory FNSKU -> canonical Seller SKU 解析已有真实成本：

```text
X004Q3AKFX -> HU-4XAJ-PYLD -> USD 6.94 all-in
X004WU7DSH -> SC-9HC3-5TFL -> USD 4.17 + first-mile 0.5271
```

最终三个月：

```text
status=ok
source_status=ok
missing_cost_skus=[]
needs_review=[]
```

最终 Management P&L：

| Month | Product Sales | Landed COGS | Ads API spend | Management Profit | Margin | Settlement Close Profit |
|---|---:|---:|---:|---:|---:|---:|
| 2026-05 | 2316.38 | 467.25 | 544.66 | 548.35 | 23.67% | 39.02 |
| 2026-06 | 2870.06 | 573.05 | 539.25 | 612.70 | 21.35% | 1130.93 |
| 2026-07 | 1464.14 | 291.23 | 555.63 | -114.89 | -7.85% | 444.55 |

### Gate 5 — v1.90.2 production smoke and v1.90.3 audit fix

v1.90.2 July `collect_ingest` 业务命令全部成功：

```text
commands=11 failed=0
Finances attempted=161 inserted=0 updated=161
Settlement attempted=1628 inserted=0 updated=1628
coverage audit success
```

随后 post-stage audit 报：

```text
AttributeError: 'list' object has no attribute 'get'
```

根因是 Finances `raw_pages.json` / `prepared_rows.json` 合法使用 JSON array root，而 automation audit helper 假设所有 ingestion JSON 都是 object。v1.90.3 对 non-object JSON 做 bounded skip，不改财务数据。

### Gate 6 — v1.90.3 final production smoke

execution：

```text
sdp-monthly-collect-ingest-cbacfwp
Succeeded
2026-08-10T09:57:38Z -> 2026-08-10T10:09:32Z
```

结果：

```text
Finances local_rows=161 review_required=0
Finances attempted=161 inserted=0 updated=161
Settlement attempted=1628 inserted=0 updated=1628
Automation commands=11 failed=0
artifact_save scanned=169 saved=169 skipped=0
No Traceback / AttributeError / ERROR
```

Rollout 完成。

## 4. 生产财务口径

```text
Management Operating Profit
  = Natural-month operating net from Finances
  - Ads API report-date spend
  - Natural-month landed COGS

Settlement Close Profit
  = Settlement posted/release view
  - Settlement-period landed COGS
```

Amazon US natural month：

```text
America/Los_Angeles
```

详细 lifecycle / COGS / FNSKU policy：`docs/features/feature_finances_api_natural_month_ledger.md` 和 `ADR-015`。

## 5. 以后月度执行原则

- `monthly collect_ingest` 必须 fail closed，不保留 `--continue-on-error`。
- Settlement discovery 失败时不能静默把不完整数据当 final close。
- Finances `review_required > 0` 时不能正常 close。
- COGS units 必须全部 costed；FNSKU 只允许唯一 canonical mapping。
- 历史 delivery pack 已 `sent` 时不 `--force-resend`。
- `needs_review/no_data` 不用 `--allow-blocked` 绕过。

## 6. Azure Container Apps 配置注意事项

### 一次性 smoke

优先使用：

```text
job show properties.template
-> 修改临时 template
-> job start --yaml
```

避免把测试参数写入永久 Job。

### 永久 command/args

实测 Cloud Shell/Azure CLI 对 `az containerapp job update --args "-c" ...` 可能把 `-c` 误解析为 Azure CLI 参数。更稳妥的已验证方法：

```text
export properties.template
-> jq modify command/args
-> az rest PATCH only properties.template
-> --body @file
-> default application/json
-> job show verify
```

当前 Jobs endpoint 实测不接受 `application/merge-patch+json`，只接受 `application/json`。

不要用 `az resource update` 回写整个 resource；它可能重新校验现有 secret references 并要求 secret plaintext/keyVaultUrl。

Cloud Shell session 是 ephemeral；重连后 `$RG/$JOB/$EXEC` 和临时 JSON 文件都可能丢失。

## 7. Rollback boundary

migration 016 是 additive。若未来应用版本异常：

1. monthly jobs 可以回滚到上一已知稳定 image；
2. 不删除 `amazon_finance_transaction`；
3. 不修改已执行 migration 016；
4. 已写 Finances ledger 使用幂等 `marketplace_id + transaction_id` 更新；
5. Settlement / historical send guards 不受影响。

## 8. 历史邮件

2026-05 / 06 / 07 已有 send result。此次重算用于数据和报表口径修正/归档，不自动重发。

```text
Do not use --force-resend unless explicitly approved.
```

## 9. 相关文档

- `docs/adr/ADR-015-natural-month-management-pnl.md`
- `docs/features/feature_finances_api_natural_month_ledger.md`
- `docs/features/feature_monthly_financial_close_report.md`
- `docs/operations/monthly_financial_troubleshooting.md`
- `docs/operations/azure_container_apps_jobs_workflow.md`
