# Feature: Pipeline Artifact Store

> 文档状态：Implemented in code / migration pending execution  
> 负责人：AI + Feng  
> 更新时间：2026-05-24  
> 功能状态：v1 code implemented; SQL migration 014 must be executed before cloud automation use  
> 相关 migration：`sql/migrations/014_create_pipeline_artifact_store.sql`  
> 相关功能：`feature_automation_jobs_workflow.md`  
> 相关 ADR：`docs/adr/ADR-012-zero-paid-automation-storage-profile.md`

---

## 1. 功能摘要

`pipeline_artifact_store` 是 free-first 自动化方案的轻量文件持久化层。

第一版不使用 Azure Files / Blob Storage。Azure Container Apps Job 每次执行完本地文件会丢失，因此跨 job 必须共享的文件需要压缩后存入 Azure SQL：

```text
submit job 生成 runtime/sampling manifests
  -> save to pipeline_artifact_store
collect job restore manifests, 下载 reports/raw
  -> save raw files to pipeline_artifact_store
ingest job restore raw files, 入库 normalized tables
  -> save ingestion/audit outputs
report job 生成 JSON/XLSX/delivery pack/send_result
  -> save report/delivery artifacts
```

本功能只解决 job 间文件交接和短期审计，不改变业务口径。

---

## 2. 不做什么

v1 不做：

```text
1. 不把 artifact store 当长期文件仓库。
2. 不保存 secrets / .env / SMTP 密码 / Amazon tokens。
3. 不替代 normalized tables。
4. 不从 artifact store 反算经营指标。
5. 不引入 Azure Files / Blob SDK。
6. 不新增发送日志表。
```

---

## 3. 数据库存储设计

新增表：

```text
dbo.pipeline_artifact_store
```

核心字段：

```text
artifact_type          artifact 类型，例如 sp_raw_report / analysis_report_xlsx
artifact_scope         一次自动化 workflow 的范围键
relative_path          项目内相对路径，例如 reports/raw/amazon/...
content_type           MIME 类型，可空
content_encoding       固定 gzip
content_sha256         原始内容 SHA-256
content_size_bytes     原始大小
compressed_size_bytes  gzip 后大小
content_bytes          gzip 后二进制内容
metadata_json          非敏感元数据
expires_at             保留期
is_deleted             软删除
```

唯一键：

```text
artifact_scope + relative_path + content_sha256 + active row
```

相同文件重复保存不会重复插入；内容变化会形成新版本。

> 注意：`docs/database/database_current_schema_spec.md` 必须等 migration 014 在 Azure SQL 执行成功，并运行 schema export 后再更新。

---

## 4. Artifact scope 规则

Weekly scope：

```text
weekly:{marketplace_id}:{profile_id}:{stats_start}_{stats_end}
```

例：

```text
weekly:ATVPDKIKX0DER:3917953989967300:2026-05-16_2026-05-22
```

Monthly scope：

```text
monthly:{marketplace_id}:{profile_id}:{YYYY-MM}
```

例：

```text
monthly:ATVPDKIKX0DER:3917953989967300:2026-04
```

---

## 5. Artifact type 规则

第一版自动推断：

| 路径 | artifact_type |
|---|---|
| `runtime/sampling/report_requests/` | `sp_report_request_manifest` |
| `runtime/sampling/ads_report_requests/` | `ads_report_request_manifest` |
| `reports/raw/amazon/` | `sp_raw_report` |
| `reports/raw/amazon_ads/` | `ads_raw_report` |
| `runtime/ingestion/` | `ingestion_output` |
| `runtime/data_coverage_audits/` | `coverage_audit` |
| `runtime/analysis_reports/**/*.json` | `analysis_report_json` |
| `runtime/analysis_reports/**/*.xlsx` | `analysis_report_xlsx` |
| `runtime/report_delivery/**/send_result.json` | `email_send_result` |
| `runtime/report_delivery/` | `delivery_pack_file` |

---

## 6. CLI

### 6.1 管理 artifact

```powershell
python scripts/manage_pipeline_artifacts.py save --scope weekly:ATVPDKIKX0DER:3917953989967300:2026-05-16_2026-05-22 --path runtime/sampling --execute
python scripts/manage_pipeline_artifacts.py restore --scope weekly:ATVPDKIKX0DER:3917953989967300:2026-05-16_2026-05-22 --execute
python scripts/manage_pipeline_artifacts.py list --scope weekly:ATVPDKIKX0DER:3917953989967300:2026-05-16_2026-05-22
python scripts/manage_pipeline_artifacts.py prune --execute
```

### 6.2 自动化 wrapper

```powershell
python scripts/run_automation_stage.py --workflow weekly --phase submit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_automation_stage.py --workflow weekly --phase collect_ingest --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_automation_stage.py --workflow weekly --phase report_delivery --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --send-email --execute
```

---

## 7. 周报周期设计

周报统计周期固定为：

```text
上上周六 .. 上周五（含首尾）
Saturday .. Friday
```

每周一执行 submit 时，系统自动选择最近一个已稳定的周五作为 `stats_end`，向前 6 天作为 `stats_start`。

为了覆盖 Amazon 报表延迟和重叠补数，请求下载范围为：

```text
stats_start - 3 days .. stats_end
即上上周三 .. 上周五
```

示例：如果调度日为 2026-05-25 周一：

```text
统计周期 stats window: 2026-05-16..2026-05-22
请求范围 request window: 2026-05-13..2026-05-22
```

---

## 8. 月报周期设计

每月 3 日对上一个自然月执行完整数据获取：

```text
previous month first day .. previous month last day
```

月报 submit 包含：

```text
Sales & Traffic
Orders
Ads reports
Settlement V2 discovery
FBA Reimbursements
Promotion/Coupon sampling
```

之后按同样流程执行 collect/ingest/report/delivery。

---

## 9. Retention

v1 默认：

```text
retention = 90 days
per-file limit = 20 MB
```

未来触发迁移到 Blob/Azure Files 的条件见 `ADR-012`。
