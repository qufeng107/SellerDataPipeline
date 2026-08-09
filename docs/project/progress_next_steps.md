# SellerDataPipeline 当前进展与下一步计划

> 更新时间：2026-08-09  
> 当前版本：v1.86 Settlement FBA fee classification coverage implemented locally; v1.85 Azure production verified  
> 文档定位：记录项目真实进展、已完成里程碑、当前非阻塞问题和下一步开发顺序。本文不承载详细字段设计；功能细节见 `docs/features/`。

## 1. 当前一句话状态

核心 Amazon SP-API / Ads normalized ingestion 已完成，Promotion/Coupon 和 Inventory Ledger 也已补齐并通过真实 Azure SQL execute + 第二次 execute 幂等性验证。项目现在应从“继续扩 ingestion”转向：

```text
手动运营流程
-> 任务周期配置已落库
-> 利润核算口径已冻结
-> SKU 成本模板导出/导入
-> 数据覆盖审计 + stable cutoff
-> 重叠窗口 rolling refresh
-> 月度财务结算报表 / 每周经营周报 / 广告优化周报
-> 报表口径升级代码已完成：月报双利润口径、WBR Saturday–Friday、WAOR active actions + negative snapshot
-> Report Delivery 邮件草稿包
-> SMTP 邮件发送已实现并通过真实邮件验收
-> 中英文双语 Report Delivery 已实现
-> Azure Container Apps Jobs 自动化设计已修订为 free-first profile（GHCR + Azure SQL artifact store，v1 不用 Azure Files/ACR）
-> pipeline_artifact_store migration + artifact save/restore service + run_automation_stage.py 本地 wrapper 已实现并完成本地 smoke
-> GHCR 镜像已构建成功，dev tag 可用于 Azure manual dev jobs
-> Azure Container Apps Environment / smoke job / weekly submit dev job 已创建
-> sdp-weekly-submit-dev 已在 Azure 上执行成功，下一步创建 sdp-weekly-collect-ingest-dev
```



## 1.0 2026-08-08 Schema Guard 鲁棒性迭代（已完成 Azure main 镜像生产验收）

2026-08-03 weekly / monthly 自动化故障排查已确认：Amazon SP-API 与 Ads API 鉴权、提交、下载均正常；Weekly collect/ingest 的直接阻塞来自 schema guard 对 additive fields 的 false-positive blocking。

```text
GET_SALES_AND_TRAFFIC_REPORT:
  missing_fields=[]
  new_fields=24
  -> requires_review=True -> execute blocked

GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA:
  missing_fields=[]
  new_fields=2
  -> requires_review=True -> execute blocked

Orders ingestion -> success
Ads ingestion    -> success
Weekly report    -> Sales & Traffic 0 dates + stale inventory -> no_data -> send_guard blocked
```

本轮已按项目 SOP 完成“先设计、后代码、再测试”：

- 新增 `docs/features/feature_schema_guard_resilience.md`。
- 新增 `docs/adr/ADR-013-schema-guard-compatibility-policy.md`。
- 同步更新 Sales & Traffic / Inventory feature 文档。
- 同步更新 `FEATURE_TEMPLATE.md`、`development_rules.md`、`iteration_workflow.md`，把新 policy 固化为后续默认规则。
- **不新增 migration，不修改 database current schema spec。**
- 公共 `BLOCKING_SCHEMA_STATUSES` 已迁至 `sampling/schema_drift.py`，warning 与 blocking 解耦。
- `new_fields` / 普通 `unmapped_fields` 保留 warning/event，但 `requires_review=False`。
- Sales & Traffic required contract 已收敛到 6 个核心 raw path。
- Inventory required contract 已收敛到 `sku` + `afn-fulfillable-quantity`，parser 同步允许 optional columns 缺失。
- 已新增 2026-08-03 真实 drift 形态回归：Sales 24 个新 path、Inventory 2 个新字段均继续 prepared。
- 全量验证：`PYTHONPATH=src pytest -q` -> `313 passed`；`python -m compileall -q scripts src tests` -> success。

冻结后的核心规则：

```text
新增 unknown field                -> warning + event, non-blocking
已知非关键字段缺失                -> warning/info, non-blocking
required field 缺失               -> requires_review=True, blocking
关键字段解析失败                  -> blocking
report granularity / 语义不兼容   -> blocking
```

Azure main 镜像生产验收已完成：`sdp-weekly-collect-ingest-r41hug0` -> `Succeeded`，Sales & Traffic 12 rows、Orders 19 rows、Ads 546 rows、Inventory 5 rows 均 `requires_review=False`，重复执行表现为 `inserted=0, updated=N`，stage `commands=7 failed=0`。三个 weekly jobs 已锁定同一 main SHA。旧 weekly 邮件不补发；后续 weekly 从当前周期继续。

## 1.0.1 2026-08-08 CI Quality Gate 降噪迭代

针对 GitHub Actions 反复因 `I001` import sorting 等可自动修复风格问题失败，本轮已冻结并实施 CI lint 分层策略：

```text
CI blocking: E4 / E7 / E9 / F / B
Local maintenance only: I / UP + ruff format
```

目标不是取消静态检查，而是让 CI 红灯优先代表 correctness / likely-bug 风险。新增 `docs/project/ci_quality_gate_policy.md` 与 `ADR-014-ci-quality-gate-signal-over-style.md`；`pyproject.toml` 已移除 blocking selection 中的 `I` / `UP`，GitHub Action lint step 改名为 `Safety lint`。当前触发 I001 的 `ads_ingestion_dry_run.py` import block 也已整理。该迭代不涉及业务逻辑、数据库或 Azure 配置。



## 1.0.2 2026-08-08 Monthly ingestion recovery v1.81

目标：恢复 2026-06 / 2026-07 月度 collect/ingest 与月报发送，不补历史 weekly。

生产根因：

```text
Settlement -> UX_amazon_settlement_transaction_business_key_hash duplicate key
Promotion/Coupon -> schema review (发生于 ADR-013 新策略部署前)
```

本地已完成：

- 新增 `docs/features/feature_monthly_ingestion_recovery.md`。
- Settlement MERGE 只按 immutable `business_key_hash`，移除 legacy natural-key OR fallback，UPDATE 不再改写 business key。
- Settlement running audit 先 commit；数据异常真正 rollback，再更新 failed audit，避免“失败但部分财务行已提交”。
- 新增 `scripts/repair_settlement_idempotency.py`：默认 dry-run，只修复 `marketplace_id + source_report_id + source_row_index + source_row_hash` 完全一致的 exact duplicates；跨 identity hash conflict 阻断。
- Promotion/Coupon transaction audit 边界同步加固。
- Promotion/Coupon additive unknown fields 已通过专用回归证明 non-blocking；missing required field 仍 blocking。
- 不新增 migration，不修改数据库结构。
- 全量测试 `319 passed`，compileall success；本地环境未安装 Ruff，Safety lint 由 CI 执行。

Azure 下一步：main merge/build 后先对 Settlement duplicate repair 做 dry-run；无 conflict 再 execute；随后按 2026-06、2026-07 顺序重跑 monthly collect_ingest 与 report_delivery。


## 1.0.4 2026-08-08 Monthly chunk completeness recovery v1.83

生产恢复验证确认 v1.82 Settlement repair 已成功清理 6,803 duplicate rows，二次 dry-run 为 0 duplicate groups。随后 2026-06 Monthly collect 暴露新的完整性问题：Sales & Traffic / Orders / Ads 的月度 backfill 会拆成多个 chunk，但 ingestion 默认只选 latest raw file。

v1.83 本地已完成：

- Monthly Sales & Traffic / Orders / Ads 改为按 manifest + 目标月份选择全部 downloaded chunks；缺少任一日期覆盖时 fail closed。
- 相同 interval 重复请求只取最新 downloaded manifest。
- Monthly data coverage audit 明确限定目标月 start/end。
- Ads timing reconciliation 仅作为 timing warning，不再因跨口径差异单独阻断邮件。
- Sales/Orders ingestion 失败路径增加 rollback，避免 partial write 被 failure audit commit。
- 本地 330 tests passed，compileall passed；Ruff CLI 当前环境未安装。

下一步已并入 v1.84：CI/main image -> 仅更新 monthly jobs -> 重跑 2026-06 collect_ingest，同时验收 v1.83 chunk completeness 与 v1.84 Settlement batch upsert -> preview report/send guard -> 发送 6 月；再恢复 7 月。

## 1.0.3 2026-08-08 Settlement repair scalability v1.82

v1.81 Azure dry-run 暴露出 repair maintenance path 的性能问题。数据库 warm-up 正常且 `Online`；只读诊断确认：

```text
amazon_settlement_transaction rows = 12,210
exact duplicate groups            = 3,878
COUNT elapsed                     = 0.22s
duplicate GROUP BY elapsed        = 0.19s
```

因此数据库扫描不是瓶颈。v1.81 对每个 duplicate group 执行 group-row + canonical-owner 两次 SQL，约形成 `1 + 2 * 3,878 = 7,757` SQL round trips；原 execute path 也会产生大量逐组 DELETE / UPDATE，并可能超过 SQL Server 2100 parameter limit。

v1.82 本地已完成：

- 新增 `docs/features/feature_settlement_repair_scalability.md`。
- repair planning 改为 `fetch_idempotency_repair_rows()` 单次 bounded scan + Python in-memory grouping / ownership check。
- 财务安全规则不变：只处理 exact source identity duplicate，cross-identity canonical owner 仍 `conflict` / fail closed。
- DELETE 全局收集 row ids 后按 1000 ids/batch 执行。
- rekey 使用 `UPDATE ... FROM (VALUES ...)`，按 900 rows / 1800 params 一批，低于 SQL Server 2100 parameter limit。
- 默认 `--json` 不再输出全部数千 plan，只输出 summary + 20 条 conflict/repairable sample；显式 `--include-plans` 才展开全部。
- 增加 scan/planning/delete/rekey/completed progress log，避免长任务无可观察输出。
- 新增 4000 duplicate groups in-memory planning 回归和 bulk DML batching tests。
- 不新增 migration；生产诊断已证明当前数据规模无需为本问题增加索引。

Azure 下一步：构建 main 镜像 -> 仅更新 `sdp-monthly-collect-ingest` -> 重新运行 repair dry-run；若 `conflict_group_count=0`，再执行 `--execute`，随后 dry-run 应得到 `duplicate_group_count=0`，最后补跑 2026-06 / 2026-07 月度 pipeline。

## 1.0.5 2026-08-08 Settlement normal ingestion batch upsert v1.84

在 2026-06 Monthly recovery 中，Settlement 正常 ingestion 已成功处理 `3921` rows，但 `sdp-monthly-collect-ingest` 总耗时约 17 分钟。代码确认瓶颈为每行一次 `MERGE + OUTPUT + fetchone` 的 Azure SQL round trip。

v1.84 已在 v1.83 基础上实现，二者职责正交：v1.83 决定 Monthly 哪些 chunk/rows 必须处理；v1.84 只优化 Settlement prepared rows 如何写入 SQL。

本地实现：

- typed local temp staging table 继承 `amazon_settlement_transaction` mapped column types。
- 39 columns 使用 2000 safe parameter budget，默认 50 rows/batch，避免 SQL Server 2100 参数上限。
- unique business keys 经 bounded multi-row INSERT 后只执行一次 target set-based MERGE。
- input 内 duplicate business keys 安全回退旧 single-row MERGE，避免 multiple-source-match 错误并保持语义。
- `business_key_hash` immutable、`WITH (HOLDLOCK)`、transaction rollback / failed audit contract 均不变。
- 3921-row fake regression 由约 3921 target MERGE round trips 降为 82 SQL statements（79 staging INSERT + create + one target MERGE + drop）。
- 不新增 migration / live schema。

Azure 下一步：构建 v1.84 main image，更新 monthly jobs；直接重跑 `2026-06 collect_ingest`（不重新 submit），同时验收 v1.83 chunk completeness 与 v1.84 Settlement batch upsert；随后重新生成 6 月月报并恢复 7 月。



## 1.0.6 2026-08-08 Settlement JSON set-based upsert v1.85

v1.84 Azure 真实 recovery 结果：v1.83 Monthly chunk completeness 已验证通过，但 Settlement staging 暴露性能回退：`1815` rows 需 `37` 个 50-row / ~1950-parameter INSERT，约 20 分钟仅完成 25/37；另有 `2106` rows 因 duplicate business key 回退逐行 MERGE。

v1.85 本地改为：

- 相同 business key + 相同 immutable source identity 在 Python 按 input order last-write-wins 折叠。
- 相同 hash 但 source identity 不同 -> financial integrity conflict，fail closed / rollback。
- 每批最多 500 unique keys 序列化为单个 JSON parameter。
- Azure SQL 用 typed `OPENJSON(CAST(? AS NVARCHAR(MAX))) WITH (...)` 直接作为 MERGE source。
- 取消 temp staging multi-parameter INSERT 和 duplicate per-row fallback。
- `business_key_hash` immutable、`WITH (HOLDLOCK)`、audit transaction contract 不变。
- 旧 sequential audit count 语义保持：`updated_rows = valid_input_rows - inserted_rows`。
- 3921 unique-row 回归目标为 8 个 JSON MERGE round trips。
- 不新增 migration / live schema。

Azure 生产验收已通过：2026-06 Settlement `3921 -> 2868 unique keys`，6 个 JSON MERGE 约 7 秒完成、Settlement 全阶段约 11 秒并提交，stage `commands=9 failed=0`；2026-07 再次以 1491 unique rows / 3 batches 成功。6 月 Financial Close 已 `status=ok` 并正式发送。

## 1.0.7 2026-08-09 Settlement FBA fee classification coverage v1.86

2026-06 recovery 已完成：v1.85 main image `ef6941c97322c717fb86872baac16530271fbe55` 在 Azure 上将 3,921 Settlement input rows 折叠为 2,868 unique business keys，6 个 JSON MERGE 约 7 秒完成，Settlement 全阶段约 11 秒完成并提交；Monthly collect `commands=9 failed=0`。随后 6 月 Financial Close `status=ok`、`send_allowed=True`，月报已正式发送给 3 个收件人。

2026-07 collect 也已成功恢复：Sales & Traffic 3 chunks、Orders 3 chunks、Ads 12 files、Settlement 1,491 rows / 3 JSON batches、FBA、Promotion/Coupon、coverage audit 均成功，stage `commands=9 failed=0`。

7 月 Financial Close preview 当前唯一真实阻断为：

```text
unknown_bucket_amount=-35.45
unclassified_amount=-35.45

FBA Inventory Storage Fee / Base fee             -32.75
FBA Customer Returns Fee (...) / Base fee         -2.70
                                                  ------
                                                  -35.45
```

v1.86 本地补丁：

- `FBA Inventory Storage Fee` -> `storage_fee / fba_storage_fee`。
- `FBA Customer Returns Fee (...)` 仅在 `transaction_type=FBAFees` 且 normalized amount type 以 `fbacustomerreturnsfee` 开头时 -> `fba_customer_returns_fee / fba_fee`。
- 不使用宽泛 fee fallback；未知组合继续 `unclassified / unknown`。
- 不新增 migration，不改金额、business key、v1.85 JSON MERGE 或 send guard。
- 新增两条真实生产字符串 parser regression。

Azure 下一步：v1.86 CI/main -> 更新 monthly jobs -> 不重新 submit，重跑 `2026-07 collect_ingest` -> 重新生成 July Financial Close preview；只有 `unknown/unclassified=0` 且无其他真实阻断时才发送 7 月月报。

## 1.1 2026-05-25 Azure Jobs handoff status

当前 Azure manual dev rollout 已进入第二阶段前：

```text
GHCR package: ghcr.io/qufeng107/seller-data-pipeline
dev image: ghcr.io/qufeng107/seller-data-pipeline:dev
Azure resource group: rg-amazon-ops
Container Apps environment: sdp-containerapps-env
Log Analytics workspace: workspacecergamazonopsb210
SQL firewall: Allow Azure services enabled
```

已验证：

```text
sdp-smoke-dev:
  status: succeeded
  purpose: verify GHCR image pull and Python container startup

sdp-weekly-submit-dev:
  status: succeeded
  command: /bin/sh
  args: -c, python scripts/run_automation_stage.py --workflow weekly --phase submit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
  evidence:
    weekly_window=stats=2026-05-16..2026-05-22 request=2026-05-13..2026-05-22
    Azure SQL warm-up succeeded after retries
    SP-API Sales & Traffic submitted
    SP-API Orders submitted
    SP-API Inventory snapshot submitted
    Amazon Ads reports submitted total=5
    Automation stage commands=4 failed=0
    artifact_save scanned=8 saved=8 skipped=0
```

旧失败原因已确认并解决：

```text
1. Command=python + Arguments='scripts/run_automation_stage.py --workflow ...'
   -> Azure 把整行 arguments 当成一个文件名，导致 can't open file。

2. Command=python + Arguments='-c, python scripts/run_automation_stage.py ...'
   -> 变成 python -c "python scripts/..."，导致 SyntaxError。

正确 Portal 写法：
Command override = /bin/sh
Arguments override = -c, python scripts/run_automation_stage.py ...
```

下一步：

```text
1. 在 Azure SQL 查询 pipeline_artifact_store，确认 submit manifests 已保存。
2. 创建 sdp-weekly-collect-ingest-dev。
3. 运行 collect_ingest；如 reports pending，30 分钟后再手动重试一次。
4. 创建 sdp-weekly-report-delivery-dev，先用 --email-to feng@cuidena.cn。
5. 三个 weekly dev jobs 稳定后，再创建 monthly dev jobs。
6. 最后再设计 main-only GitHub Actions deploy workflow 更新正式 Azure Jobs。
```

为避免手动重复填写环境变量，后续 jobs 推荐用 Azure CLI/Cloud Shell 按模板创建，而不是 Portal 逐项复制。详见：

```text
docs/operations/azure_container_apps_jobs_setup_checklist.md
```


## 2. 已完成真实入库闭环

| 数据域 | 入口 | 目标表 | 验收结果 |
|---|---|---|---|
| Ads | Amazon Ads SP reports | 4 张 Ads daily 表 | `sync_run_id=1/2`; inserted=200; second run updated=200 |
| Listing | `GET_MERCHANT_LISTINGS_ALL_DATA` | `amazon_listing_snapshot` | inserted=6; second run updated=6 |
| Inventory snapshot | `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` | `amazon_inventory_daily` | inserted=5; second run updated=5 |
| Sales & Traffic | `GET_SALES_AND_TRAFFIC_REPORT` | `amazon_sales_traffic_daily`, `amazon_sales_traffic_asin_daily` | `sync_run_id=7/8`; inserted=7; second run updated=7 |
| Settlement | `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` | `amazon_settlement_transaction` | `sync_run_id=9/10`; inserted=4911; second run updated=4911 |
| Orders | `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` | `amazon_order_item` | `sync_run_id=11/12`; inserted=112; second run updated=112 |
| FBA Reimbursements | `GET_FBA_REIMBURSEMENTS_DATA` | `amazon_fba_reimbursement` | `sync_run_id=13/14`; inserted=19; second run updated=19 |
| FBA Fee Preview | `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` | `amazon_fba_fee_preview` | `sync_run_id=15/16`; inserted=8; second run updated=8 |
| Promotion/Coupon | Promotion + Coupon reports | 4 张 Promotion/Coupon 表 | `sync_run_id=17/18`; inserted=10; second run updated=10 |
| Inventory Ledger | Ledger summary + detail reports | `amazon_inventory_ledger_summary_daily`, `amazon_inventory_ledger_detail` | `sync_run_id=19/20`; inserted=357; second run updated=357 |

## 3. 数据库状态

已执行成功的 migration：

```text
001_create_core_tables.sql
002_create_indexes.sql
003_add_listing_snapshot_business_key_hash.sql
004_add_inventory_daily_business_key_hash.sql
005_add_sales_traffic_business_key_hashes.sql
006_add_settlement_transaction_business_key.sql
007_add_order_item_business_key.sql
008_add_fba_reimbursement_business_key.sql
009_add_fba_fee_preview_business_key.sql
010_add_promotion_coupon_business_keys.sql
011_add_inventory_ledger_business_keys.sql
012_create_ingestion_job_config.sql
013_create_report_email_recipient_config.sql
014_create_pipeline_artifact_store.sql
```

Seed 已执行成功：

```text
001_seed_ingestion_job_config_core_jobs.sql
```

新增待执行/可重复执行 seed：

```text
002_update_ingestion_job_config_refresh_policy.sql
```

当前真实数据库记录在：

```text
docs/database/database_current_schema_spec.md
```

最新 schema export 已在 migration 014 后执行，当前用户表数量为 31，新增 `report_email_recipient_config` 与 `pipeline_artifact_store`。

## 4. 已完成基础设施

| 能力 | 状态 |
|---|---|
| Azure SQL connection warm-up retry | 已实现，默认 max_attempts=6 |
| Firewall/IP allowlist 错误识别 | 已实现，40615 fail fast |
| `check_database_status.py` | 已实现 |
| `export_database_schema_spec.py` | 已实现 |
| schema guard | v1.79 resilience 已本地实现：additive drift non-blocking、required contract fail-closed；313 tests passed；Azure verification pending |
| dry-run preview | 已在各 ingestion 链路使用 |
| repository MERGE/upsert | 已在各 ingestion 链路使用 |
| updated-files-only 交付模式 | 当前默认工作方式 |
| GitHub Action lint/test | 已修复最近的 Ruff 与 pytest 问题 |

## 5. 新增 operations 文档

本轮新增：

```text
docs/operations/manual_execution_workflow.md
docs/operations/data_refresh_policy.md
docs/operations/ingestion_job_cadence_catalog.md
docs/operations/data_coverage_audit_workflow.md
docs/operations/historical_backfill_workflow.md
docs/operations/manual_refresh_plan_workflow.md
docs/features/feature_ingestion_job_config.md
docs/project/core_ingestion_completion_review.md
docs/project/requirements_deprecation_plan.md
```

对应 ADR：

```text
docs/adr/ADR-007-manual-first-before-automation.md
docs/adr/ADR-008-ingestion-job-config-table.md
docs/adr/ADR-010-overlapping-refresh-weekly-analysis.md
```

## 6. requirements_to_be_deprecated 状态

当前结论：暂不直接删除。

原因：仍有文档和历史 sample notes 引用 `requirements_to_be_deprecated/data_samples/*.md`。该目录已经不是正式设计来源，但仍作为历史取样证据保留。

正式清理计划见：

```text
docs/project/requirements_deprecation_plan.md
```

## 7. 当前非阻塞限制

| 限制 | 后续处理 |
|---|---|
| raw file registry 关联仍不完整，部分 `source_raw_file_id` 可能为 NULL | 后续补 raw file registry / Blob Storage 归档增强。 |
| 任务周期已写入 `pipeline_job_config` | 新增 seed 002 用于把配置调整为重叠窗口刷新 + 周度分析；执行后需导出 live schema/行数并记录。 |
| 利润核算口径已冻结并升级展示 | 财务/会计口径仍采用 Settlement-led Financial Profit v1.0；新增 Management P&L with report-date Ads 作为月报经营复盘口径。 |
| SKU 成本、采购成本、头程/海运成本需要录入机制 | 已实现 xlsx 模板导出/导入脚本，目标表为 `amazon_sku_cost`。 |
| 2026-03 起核心数据已完成第一轮补数 | Orders 历史 backfill 已逐 raw file 入库；Ads 历史 backfill 已入库；coverage audit 中 covers_stable_window 提升到 4。后续日常更新改用 `run_manual_refresh_plan.py`。 |
| 周报脚本已实现；月报脚本已初步复核 | Monthly Financial Close Report v1 已实现 JSON + 单个 XLSX 多 sheet 输出，且 2026-03 / 2026-04 dry-run 已初步复核；Weekly Business Review v1 已实现 JSON + 单个 XLSX 多 sheet 输出，并用 2026-05-11..2026-05-17 真实数据生成 status=ok。Ads API campaign daily 目前 5 月后可用于周度加工，3/4 月 Ads context 缺失仅作为运营解释 warning。Weekly Ads Optimization Report v1 已完成代码实现，并已用 2026-05-11..2026-05-17 真实 Ads 数据执行 live dry-run，结果 status=ok、reconciliation_warnings=0。Report Delivery / Email Pack v1 已实现草稿包生成；SMTP 真实发送 v1.1 已实现，采用 Python 标准库 `smtplib` / `EmailMessage`，收件人通过 `runtime/config/report_delivery_recipients.json` 按 `report_type + audience` 配置，真实发送必须显式 `--execute`。 |
| Azure Jobs manual dev rollout | Report Delivery / Email Pack、SMTP 发送、DB 收件人和双语 presentation 已完成真实邮件验收；free-first 自动化已完成 `pipeline_artifact_store`、artifact save/restore、`run_automation_stage.py` wrapper、GHCR build、Azure `sdp-smoke-dev` 与 `sdp-weekly-submit-dev`。下一步创建 `sdp-weekly-collect-ingest-dev`，再创建 `sdp-weekly-report-delivery-dev`。 |

## 8. 下一步建议

利润核算口径已冻结在：

```text
docs/features/feature_profit_calculation.md
docs/adr/ADR-009-settlement-led-profit-policy.md
```

当前冻结规则：

```text
财务利润以 Settlement 为主；
Orders / Sales & Traffic / Ads / Promotion-Coupon 只做运营解释和差异分析；
SKU 成本来自 amazon_sku_cost；
第一版采用 SKU 标准成本 + 生效日期；
第一版先输出人工复核文件，不立即新增利润结果表。
```

当前已新增 historical backfill CLI，并已补齐 2026-03 起的 Orders 与核心经营数据；Ads campaign daily 目前 5 月后数据已可稳定用于周度加工。为避免日常操作继续变成零散命令，已新增 `scripts/run_manual_refresh_plan.py`，将标准定期更新固化为 `core_rolling` / `weekly_full` 两个 plan，以及 `submit` / `collect` / `ingest` / `audit` 四个 phase。Monthly Financial Close Report v1.2 已完成代码实现，默认输出 JSON + 单个 XLSX 多 sheet，并新增 Settlement-led Estimated Profit、Management Estimated Profit with Report-date Ads、`02_Management_PnL` 和 `03_Ads_Timing_Recon`。Weekly Business Review v1.1 已完成代码对齐，统一周报周期为 Saturday–Friday，并将广告和货本后贡献明确标注为未扣完整 Amazon 平台费。Weekly Ads Optimization Report v1.1 已完成代码实现，action items 已区分 active campaigns 与 historical paused lessons，并接入 negative keyword snapshot / `--negative-keyword-csv` 去重。

## 9. 管理报表设计进展

### 9.1 2026-06-01 报表口径升级代码完成

本轮已完成设计与代码对齐，未新增数据库 migration。已确认并实现：

```text
Monthly Financial Close Report v1.2:
  财务/会计主口径 = Settlement-led Estimated Profit
  管理经营口径 = Management Estimated Profit with Report-date Ads
  已新增 02_Management_PnL 与 03_Ads_Timing_Recon

Weekly Business Review v1.1:
  默认周期 = Saturday–Friday
  默认生成 = Monday
  Contribution After Ads 展示为广告和货本后贡献，未扣完整 Amazon 平台费
  Settlement 仅作为 posted-date 财务参考

Weekly Ads Optimization Report v1.1:
  默认周期 = Saturday–Friday
  Action Items 已拆分 active actions 和 historical paused lessons
  已接入 negative keyword snapshot 与 --negative-keyword-csv，避免重复建议已否定词
```

本地验证：

```text
PYTHONPATH=src python -m pytest tests/unit -q -> 301 passed
PYTHONPATH=src python -m compileall -q src scripts tests -> passed
```

后续不是继续改口径，而是重新生成真实周期报表，人工复核 5 月广告费跨期、WBR 贡献指标和 WAOR negative 去重效果.


当前报表体系冻结为三类：

```text
1. Monthly Financial Close Report：月度财务结算报表，偏 CFO/会计/股东汇报。
2. Weekly Business Review：每周经营周报，偏 CEO/运营负责人每周复盘。
3. Weekly Ads Optimization Report：每周广告优化报表，偏广告动作清单。
```

已完成设计：

```text
docs/features/feature_monthly_financial_close_report.md  # v1 默认输出 JSON + 单个 XLSX 多 sheet
docs/features/feature_weekly_business_review.md  # v1 默认输出 JSON + 单个 XLSX 多 sheet
docs/features/feature_weekly_ads_optimization_report.md  # v1 默认输出 JSON + 单个 XLSX 多 sheet
docs/features/feature_report_delivery_email.md  # 统一邮件草稿包与 SMTP 发送已实现；收件人走数据库；v1.3 已加中英文双语 presentation
docs/features/feature_automation_jobs_workflow.md  # Azure Container Apps Jobs 三阶段自动化设计
```

代码实现进展：Monthly Financial Close Report v1.2 已完成双利润口径与 Ads Timing Reconciliation；Weekly Business Review v1.1 已完成 Saturday-Friday 周期与贡献指标口径对齐；Weekly Ads Optimization Report v1.1 已完成 active actions / historical paused lessons 拆分和 negative keyword snapshot 去重。Report Delivery / Email Pack 与 SMTP 真实发送已完成，且 WAOR 邮件已实际收到；当前已升级为中英文双语邮件和 XLSX 固定标签/说明。之后建议顺序：重新生成三类报表与 delivery pack，人工复核双语邮件正文和附件 -> 继续 Azure Jobs dev rollout。

## 10. 当前建议手动运行顺序

参考：

```text
docs/operations/manual_execution_workflow.md
docs/operations/ingestion_job_cadence_catalog.md
```

短期规则：

```text
core_rolling：每 1-2 天按 submit -> collect -> ingest -> audit 刷新核心源
weekly_full：每周按 submit -> collect -> ingest -> audit 刷新核心源 + 慢源
SKU 成本：按需通过 xlsx 模板维护
周报/月报：只在 stable coverage audit 后生成
邮件发送：Report Delivery 已可生成草稿包并通过 SMTP 发送；收件人来自 `report_email_recipient_config`；所有管理报表 presentation 层要求中英文双语，先 `--dry-run` 校验，再使用 `--execute` 发送
Azure Jobs：复用 run_manual_refresh_plan.py 的固定 plan，不另起一套逻辑
```

注意：数据刷新可以 1-2 天一次，但销售/广告/利润等正式分析产物最短周期为一周。


## 11. Azure Jobs 自动化设计冻结

2026-05-24 已新增并冻结：

```text
docs/features/feature_automation_jobs_workflow.md
docs/operations/azure_container_apps_jobs_workflow.md
docs/adr/ADR-011-azure-container-apps-jobs-automation.md
docs/adr/ADR-012-zero-paid-automation-storage-profile.md
```

冻结结论：第一版自动化使用 Azure Container Apps Jobs，不使用 Azure Functions / Durable Functions / Airflow。2026-05-24 成本策略调整为 free-first profile：使用 GHCR 代替 ACR，使用 Azure SQL artifact store 代替 Azure Files，数据库防火墙 v1 使用 Allow Azure services。自动化按三阶段拆分：

```text
1. 数据下载：submit + collect
2. 数据入库：ingest + audit
3. 数据报表与发送：generate report -> delivery pack -> SMTP send
```

关键前置条件：

```text
1. 执行 `sql/migrations/014_create_pipeline_artifact_store.sql`，成功后导出 live schema 并更新 `database_current_schema_spec.md`。
2. v1 不使用 Azure Files；跨 job 文件由 `pipeline_artifact_store` 压缩持久化。
3. Azure SQL firewall v1 使用 Allow Azure services，即 0.0.0.0/0.0.0.0 规则。
4. SMTP、Amazon SP-API、Amazon Ads、Azure SQL secrets 进入 Azure Container Apps secrets，不能写入 Git 或数据库。
5. 自动发送第一阶段建议先发给 `feng@cuidena.cn`，连续稳定后恢复 DB recipients 默认三人。
```

周期冻结：

```text
Weekly stats window = 上上周六..上周五，request window = 上上周三..上周五。
每周一 submit，两小时后 collect_ingest，一次半小时后重试，再一小时内 report_delivery。
Monthly = 每月3日处理上一个自然月。
```


## 12. Automation free-first current next step

本地 artifact 持久化层和 Azure manual dev submit 已通过。当前不应直接启用 schedule，而应继续按 manual dev jobs 验证：

```text
已完成：
1. migration 014 已执行，pipeline_artifact_store 已进入 live schema。
2. 本地 manage_pipeline_artifacts.py save/list/restore smoke test 已通过。
3. 本地 run_automation_stage.py weekly report_delivery 已通过，并成功发送双语 WBR/WAOR 邮件。
4. GHCR dev image 已构建成功。
5. Azure sdp-smoke-dev 已成功。
6. Azure sdp-weekly-submit-dev 已成功，submit manifests 已保存到 artifact store。

下一步：
1. SQL 查询 pipeline_artifact_store，确认 Azure submit 保存的 8 个 manifests。注意使用 live schema 字段：`artifact_scope`、`content_size_bytes`、`compressed_size_bytes`，不要使用旧写法 `scope` / `original_size_bytes`。
2. 创建 sdp-weekly-collect-ingest-dev。
3. 运行 collect_ingest；如果 reports pending，30 分钟后手动重试一次。
4. 创建 sdp-weekly-report-delivery-dev，先用 --email-to feng@cuidena.cn。
5. weekly 三阶段稳定后，再创建 monthly dev jobs。
6. dev manual jobs 稳定后合并到 main，再用 `:main` / `:latest` 镜像创建或更新正式 jobs；正式 jobs 也先 manual 验证，再启用 schedule。
7. 最后再做 main-only GitHub Actions deploy workflow。
```

复制 jobs 时不要继续在 Portal 逐项手填。优先使用 Azure CLI / Cloud Shell 按模板创建 job、设置 secret references 和 env vars，详见：

```text
docs/operations/azure_container_apps_jobs_setup_checklist.md
```


## 2026-05-24 update — date-stamped report files

Report generators now write date-stamped JSON/XLSX filenames so downloaded email attachments are self-describing:

- `monthly_financial_close_{YYYY-MM}.json` / `.xlsx`
- `weekly_business_review_{week_start}_{week_end}.json` / `.xlsx`
- `weekly_ads_optimization_{week_start}_{week_end}.json` / `.xlsx`

The report directory structure is unchanged. Report Delivery uses `output_files.xlsx` from the JSON, so email attachments inherit the date-stamped workbook filename. Automation schedule helpers were updated to point to the new date-stamped JSON paths.

## 14. GHCR branch strategy update

已将 GHCR 镜像构建策略冻结为：

```text
dev  -> ghcr.io/<owner>/seller-data-pipeline:dev
main -> ghcr.io/<owner>/seller-data-pipeline:latest and :main
sha  -> ghcr.io/<owner>/seller-data-pipeline:<git-sha>
```

下一步：

1. push 到 dev，确认 `:dev` 镜像构建成功。
2. 用 `:dev` 创建/验证第一个 manual Azure Container Apps Job。
3. 合并到 main 后，由 `:latest` 作为正式 job 镜像。
4. 等 manual jobs 全部跑通后，再新增 main-only deploy workflow 自动更新 Azure jobs。


## 15. Azure manual dev rollout update

2026-05-25 当前 Azure dev rollout 状态：

| Job | Status | Notes |
|---|---|---|
| `sdp-smoke-dev` | Succeeded | GHCR image pull + Python startup verified. |
| `sdp-weekly-submit-dev` | Succeeded | Submitted weekly Sales & Traffic, Orders, Inventory snapshot and Ads requests; saved 8 artifacts. |
| `sdp-weekly-collect-ingest-dev` | Pending creation | Use same image/env/secrets as submit; command changes to collect_ingest. |
| `sdp-weekly-report-delivery-dev` | Pending creation | Requires SMTP secrets; first run should use `--email-to feng@cuidena.cn`. |

Important operational lesson:

```text
Azure Portal command/args:
Command override = /bin/sh
Arguments override = -c, python scripts/run_automation_stage.py ...
```

Do not use `Command=python` with the whole script command in Arguments.
