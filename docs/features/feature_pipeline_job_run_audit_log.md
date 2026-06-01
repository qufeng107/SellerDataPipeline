# Feature: Pipeline Job Run Audit Log

> 文档状态：Implemented; migration 015 executed and schema exported  
> 负责人：AI + Feng  
> 更新时间：2026-06-01  
> 功能状态：Implemented; migration 015 已执行，repository/service/wrapper audit hooks 已接入，等待新镜像 job 产生首批审计记录  
> 相关功能：`docs/features/feature_automation_jobs_workflow.md`, `docs/features/feature_pipeline_artifact_store.md`, `docs/features/feature_report_delivery_email.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`  
> 相关原则：先文档后实现、先 migration 后 spec、审计元数据入库、raw/report 文件继续由 `pipeline_artifact_store` 保存

---

## 1. 功能摘要

Pipeline Job Run Audit Log 是 SellerDataPipeline 自动化运行的结构化审计账本。

它要解决的问题不是“看一段 console log”，而是在未来出现数据口径异常、报表数字异常、Amazon 源文件变动、邮件重复发送或某个 job 失败时，可以通过 SQL 直接回答：

```text
哪一次 job 运行了？
它跑的是哪个 workflow / phase / 日期窗口？
调用了哪些子命令？
每个命令成功还是失败？
读取/保存了哪些 artifacts？
写入了哪些 normalized 表？
产生了哪些报表和邮件发送结果？
对应的 Azure Job / image / artifact_scope 是什么？
```

v1 不替代 Log Analytics，也不把全文 console log 大量写入数据库。它只把排查所需的关键结构化摘要写入 Azure SQL，并通过 `artifact_scope` / `artifact_id` / `source_raw_file_path` 指回 `pipeline_artifact_store` 和 normalized 业务表。

---

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认：需要长期数据审计与问题回溯 |
| 数据源取样 | 不适用，读取本系统 job/runtime/artifact 信息 |
| Parser | v1 已实现：从 ingestion summary JSON 提取 table write summary；后续逐步增强 |
| Dry-run preview | 支持：automation wrapper dry-run 仍可生成 run/command 审计，业务写入不执行 |
| Schema guard | 已设计并接入 redaction guard；业务 schema guard 结果通过 command/artifact/table summary 记录 |
| Repository/upsert | 已实现 append-only repository，不覆盖历史 run |
| Azure SQL execute | migration 015 已执行，live schema export 已更新 |
| 幂等性验证 | 单元测试覆盖 append 写入与重复运行设计；Azure 首批 job 写入待新镜像/dev job 验证 |
| 单元测试 | 已新增 repo/service/automation callback/migration/artifact type 测试 |
| 文档同步 | 本文档已更新为 implementation-ready 版 |

功能整体状态：

```text
Implemented; migration executed; awaiting first cloud job audit rows
```

---

## 3. 业务目标

### 3.1 谁会用

1. 运营负责人：确认每周/每月自动化是否成功、失败原因是什么。
2. 财务/会计协作时的内部排查：发现月报/周报数字异常时，定位使用了哪批源数据。
3. 开发者/AI 后续维护：根据结构化 job 记录快速复现问题，不依赖聊天记录或临时截图。

### 3.2 解决什么问题

当前系统已经有：

```text
Log Analytics：保存容器 stdout/stderr，适合看即时运行日志。
pipeline_artifact_store：保存 manifests/raw reports/report packs/send_result 等文件型证据。
normalized tables：保存解析后的业务事实。
amazon_sync_run_log：保存部分采集/解析/入库任务运行状态。
```

但这些信息分散，未来排查一个数据错误时，需要人工拼接：Azure execution history、KQL log、artifact store、raw report、normalized 表、报表文件、邮件发送结果。

本功能的目标是新增一层结构化审计账本，把每次自动化阶段和子命令串起来，形成可查询的 lineage：

```text
Azure Job execution
  -> pipeline_job_run
  -> pipeline_job_command_run
  -> pipeline_job_artifact_link
  -> pipeline_job_table_write_summary
  -> pipeline_artifact_store / normalized tables / reports / emails
```

### 3.3 输出影响什么决策

1. 判断某次周报/月报是否可信。
2. 判断是否需要重跑 submit / collect / report_delivery。
3. 判断数据异常来自 Amazon 源数据、下载未完成、schema guard、入库逻辑、报表加工、邮件发送，还是人工配置。
4. 判断是否需要加长 submit 与 collect 间隔，或新增 late collect job。
5. 判断某次数据库写入是否覆盖了历史数据，以及覆盖范围是什么。

### 3.4 当前优先级

优先级：高。

原因：weekly main scheduled jobs 已开始运行，monthly jobs 即将接入。越早建立结构化审计，后续数据问题越容易回溯；等自动化运行数周后再补，历史运行很难完整补齐。

### 3.5 触发来源记录策略

需要区分“这个 Azure Job 配置为 Manual 还是 Schedule”和“这一次 execution 实际由人工 Run now 还是 cron 自动触发”。

v1 采用 best-effort 设计：

```text
configured_trigger_type
  记录 job 配置类型，例如 Manual / Schedule。建议通过 SDP_CONFIGURED_TRIGGER_TYPE 注入。

run_trigger_type
  记录本次实际触发类型，例如 manual / schedule / unknown。建议通过 SDP_RUN_TRIGGER_TYPE 或 CLI --run-trigger-type 注入。

run_trigger_source
  记录该判断来自 CLI、env，还是 default unknown。
```

注意：Azure Container Apps Job 的容器内部不一定天然暴露“本次 execution 是 cron 触发还是 Portal Run now 触发”。因此，正式 schedule job 至少应注入 `SDP_CONFIGURED_TRIGGER_TYPE=Schedule` 和 `SDP_AZURE_JOB_NAME=<job-name>`；如果未来需要严格区分 manual补跑，可在补跑前临时设置 `--run-trigger-type manual` 或维护一套 manual recovery job。

---

## 4. 范围与非范围

### 4.1 本功能包含

1. 新增 automation/job run 级别结构化审计表。
2. 记录 `run_automation_stage.py` 每次 invocation 的 workflow、phase、window、artifact_scope、status、失败摘要。
3. 记录 wrapper 内部每个子命令的 label、script、redacted args、exit_code、duration、status。
4. 记录 restore/save 到 `pipeline_artifact_store` 的 artifact 链接和统计。
5. 记录每个命令对 normalized 表的写入摘要：目标表、日期范围、rows_read / inserted / updated / skipped / failed、source report 类型。
6. 保存 Azure Job / image / git sha / GHCR tag 等运行环境信息，方便未来确认运行版本。
7. 对参数、环境变量和错误摘要做 secret redaction，禁止把 token/password 写入数据库。
8. 提供 SQL 查询样例，用于未来审计和排查。

### 4.2 本功能不包含

1. 不把完整 console log 全量写入 SQL。完整 stdout/stderr 继续看 Log Analytics。
2. 不替代 `pipeline_artifact_store`；raw report、XLSX、JSON、delivery pack 仍由 artifact store 保存。
3. 不替代 normalized 表；业务指标仍从 normalized 表计算。
4. 不改变利润、广告、订单、库存、结算等业务口径。
5. 不绕过 schema guard；`requires_review=True` 仍应阻断或标记失败。
6. 不保存 secrets、OAuth token、SMTP 密码、Azure SQL 密码、Amazon refresh token。
7. v1 不做可视化 dashboard；先保证 SQL 可查。
8. v1 不接 Azure Monitor API 自动拉取全文日志；只保存本系统可直接生成的结构化摘要。

---

## 5. 输入数据

| 来源系统 | Report/API/文件 | 格式 | 当前状态 | 用途 |
|---|---|---|---|---|
| `scripts/run_automation_stage.py` | CLI 参数与计算出的 automation window | argparse/runtime object | 已存在 | 生成 `workflow`, `phase`, `artifact_scope`, stats/request window。 |
| `AutomationScheduleService` | 子命令列表与 return codes | Python dataclass | 已存在 | 生成 command run 记录。 |
| Azure Container Apps Job | job name / image / trigger / execution metadata | env/config/manual input | 部分可用 | 记录运行环境；无法自动获得的字段允许为空或由 job env 注入。 |
| `PipelineArtifactService` | restore/save 结果 | Python dataclass | 已存在 | 记录 restored/saved/skipped counts。 |
| `pipeline_artifact_store` | artifact metadata | Azure SQL table | 已存在 | 通过 artifact id/path/scope 关联 raw/report/delivery 文件证据。 |
| 子命令输出文件 | ingestion summary / validation events / report JSON / send_result | JSON/JSONL | 部分已存在 | 用于提取 rows、status、report period、发送状态等摘要。 |
| existing `amazon_sync_run_log` | 采集/解析/入库任务运行记录 | Azure SQL table | 已存在 | 保留 ingestion 级别日志；新功能不删除该表。 |

---

## 6. 输出结果

| 输出类型 | 输出位置 | 用途 |
|---|---|---|
| Azure SQL table | `dbo.pipeline_job_run` | 每次 automation stage invocation 一行。 |
| Azure SQL table | `dbo.pipeline_job_command_run` | stage 内每个子命令一行。 |
| Azure SQL table | `dbo.pipeline_job_artifact_link` | run/command 与 artifact store 的输入输出关系。 |
| Azure SQL table | `dbo.pipeline_job_table_write_summary` | 每个命令对 normalized 表的写入摘要。 |
| Runtime artifact | `runtime/automation_audit/.../stage_result.json` | 保留 JSON 审计快照，方便 artifact store 归档。 |
| SQL 查询样例 | 本功能文档 / operations runbook | 排查某一期周报/月报的数据 lineage。 |

---

## 7. 处理流程

### 7.1 Stage run 生命周期

```text
run_automation_stage.py starts
  -> compute workflow window and artifact_scope
  -> open Azure SQL connection
  -> insert pipeline_job_run(status='running')
  -> restore artifacts if phase != submit
  -> insert artifact restore links / counts
  -> execute each command
      -> insert pipeline_job_command_run(status='running')
      -> run subprocess
      -> parse available summary artifacts / output markers
      -> update command run(status, exit_code, duration, row counts, error summary)
      -> insert table write summaries where available
  -> save artifacts
  -> insert artifact save links / counts
  -> update pipeline_job_run(status='succeeded'/'failed'/'partial')
  -> write stage_result.json
```

### 7.2 失败时怎么处理

| 失败点 | 处理方式 | 是否写审计 |
|---|---|---|
| SQL 连接失败，无法创建 run row | console log 输出错误；无法写 SQL 审计 | no |
| artifact restore 失败 | `pipeline_job_run.status='failed'`，记录 `error_summary` | yes if DB available |
| 子命令失败且 stop_on_error=True | 当前 command 标记 failed，后续命令不执行，stage failed | yes |
| 子命令失败且 continue_on_error=True | 当前 command failed，后续命令继续，stage 最终 failed 或 partial | yes |
| artifact save 失败 | stage failed；尽量保留前面 command run rows | yes if DB available |
| 程序异常退出 | `finally` 中尽量 update run status 和 error_summary | best effort |

### 7.3 status 语义

| status | 说明 |
|---|---|
| `running` | 已开始，尚未完成。 |
| `succeeded` | 所有需要执行的命令成功，关键 artifact save 成功。 |
| `failed` | 一个或多个关键步骤失败，exit code 非 0。 |
| `partial` | 允许继续执行后有部分命令失败，或某些数据源 pending/缺失但报表仍可生成。v1 可先不用，后续根据 audit 细化。 |
| `skipped` | dry-run、send guard、already sent 等导致未执行真实动作。 |
| `blocked` | schema/privacy guard、needs_review、missing required env 等主动阻断。 |

---

## 8. 字段映射

### 8.1 CLI/runtime 到 `pipeline_job_run`

| 来源 | 目标字段 | 类型 | 是否必需 | 说明 |
|---|---|---|---|---|
| `--workflow` | `workflow` | NVARCHAR(40) | yes | `weekly` / `monthly`。 |
| `--phase` | `phase` | NVARCHAR(40) | yes | `submit` / `collect_ingest` / `report_delivery`。 |
| `--execute` | `execution_mode` | NVARCHAR(20) | yes | `execute` / `dry_run`。 |
| `--marketplace-id` or env | `marketplace_id` | NVARCHAR(50) | no | Amazon marketplace id。 |
| `--profile-id` or env | `profile_id` | NVARCHAR(100) | no | Amazon Ads profile id。 |
| computed | `artifact_scope` | NVARCHAR(220) | yes | 与 artifact store 对齐。 |
| computed weekly window | `stats_start`, `stats_end`, `request_start`, `request_end` | DATE | no | weekly 使用。 |
| computed monthly window | `period_key`, `stats_start`, `stats_end` | NVARCHAR/DATE | no | monthly 使用 `YYYY-MM`。 |
| env/config | `azure_job_name`, `azure_execution_name` | NVARCHAR | no | 可通过 job env 显式注入；没有则为空。 |
| env/CLI | `configured_trigger_type`, `run_trigger_type`, `run_trigger_source` | NVARCHAR | no | 区分 job 配置触发类型与本次实际触发类型；actual trigger 只能 best-effort。 |
| env/config | `azure_resource_group`, `container_app_name`, `container_revision`, `container_replica` | NVARCHAR | no | 运行环境定位信息，方便从 Azure Portal / Log Analytics 反查。 |
| image/env | `container_image`, `git_sha`, `image_tag` | NVARCHAR | no | 用于版本追踪。 |
| result | `commands_total`, `commands_failed` | INT | yes | 子命令数量与失败数量。 |
| result | `artifact_restored_count`, `artifact_saved_count`, `artifact_skipped_count` | INT | yes | artifact 操作摘要。 |
| result | `status`, `error_type`, `error_summary` | NVARCHAR | yes/no | 结果和错误摘要。 |

### 8.2 command 到 `pipeline_job_command_run`

| 来源 | 目标字段 | 类型 | 是否必需 | 说明 |
|---|---|---|---|---|
| command index | `command_index` | INT | yes | stage 内顺序，从 1 开始。 |
| `AutomationCommand.label` | `command_label` | NVARCHAR(240) | yes | 人类可读命令名。 |
| `AutomationCommand.argv[0]` | `script_path` | NVARCHAR(500) | yes | 例如 `scripts/ingest_orders_report.py`。 |
| argv | `redacted_args_json` | NVARCHAR(MAX) | yes | 参数 JSON，敏感值脱敏。 |
| argv | `args_sha256` | CHAR(64) | yes | 用于判断命令配置是否变化。 |
| subprocess | `exit_code` | INT | no | dry-run 时可空。 |
| runtime | `started_at`, `finished_at`, `duration_ms` | DATETIME2/BIGINT | yes/no | 命令级耗时。 |
| parsed output | `rows_read`, `rows_inserted`, `rows_updated`, `rows_skipped`, `rows_failed` | INT | no | 从 summary/known output 中提取。 |
| parsed output | `status`, `error_summary` | NVARCHAR | yes/no | 命令结果。 |

### 8.3 artifact 到 `pipeline_job_artifact_link`

| 来源 | 目标字段 | 类型 | 是否必需 | 说明 |
|---|---|---|---|---|
| `pipeline_job_run.id` | `job_run_id` | BIGINT | yes | 父 run。 |
| `pipeline_job_command_run.id` | `command_run_id` | BIGINT | no | 能归属到具体命令时填写。 |
| `pipeline_artifact_store.id` | `artifact_id` | BIGINT | yes | 关联 artifact。 |
| restore/save | `artifact_role` | NVARCHAR(40) | yes | `restored_input` / `saved_output` / `report_output` / `email_result`。 |
| artifact store | `artifact_type`, `relative_path`, `content_sha256` | NVARCHAR/CHAR | yes | 冗余快照，便于 artifact 后续软删除后仍可查。 |

### 8.4 table write 到 `pipeline_job_table_write_summary`

| 来源 | 目标字段 | 类型 | 是否必需 | 说明 |
|---|---|---|---|---|
| command run | `command_run_id` | BIGINT | yes | 对应哪个子命令。 |
| known script mapping | `target_table` | NVARCHAR(300) | yes | 例如 `dbo.amazon_order_item`。 |
| parsed summary | `rows_read`, `rows_inserted`, `rows_updated`, `rows_skipped`, `rows_failed` | INT | no | 写入摘要。 |
| parsed summary | `source_system`, `source_report_type`, `source_report_id` | NVARCHAR | no | 源数据来源。 |
| parsed summary/window | `data_start_date`, `data_end_date` | DATE | no | 本次覆盖的数据日期范围。 |
| parsed summary | `source_raw_file_path`, `source_raw_file_sha256` | NVARCHAR/CHAR | no | 原始文件证据。 |

---

## 9. 目标数据表设计

> 注意：本节是目标设计，不代表当前 Azure SQL 已存在。只有 migration 执行成功并导出 schema 后，才能更新 `docs/database/database_current_schema_spec.md`。

### 9.1 涉及表

| 表 | 当前是否存在 | 用途 | 写入方式 |
|---|---|---|---|
| `dbo.pipeline_job_run` | no | 自动化 stage run 主表 | insert at start, update at finish |
| `dbo.pipeline_job_command_run` | no | 子命令运行明细 | insert/update |
| `dbo.pipeline_job_artifact_link` | no | run/command 与 artifacts 的 lineage | insert append-only |
| `dbo.pipeline_job_table_write_summary` | no | 目标表写入摘要 | insert append-only |
| `dbo.pipeline_artifact_store` | yes | 文件型证据 | read/link only，本功能不改变其语义 |
| `dbo.amazon_sync_run_log` | yes | 现有采集/入库日志 | 保留；v1 不删除、不强改 |

### 9.2 `pipeline_job_run` 设计

建议字段：

```sql
id BIGINT IDENTITY(1,1) PRIMARY KEY,
run_uid UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID(),
workflow NVARCHAR(40) NOT NULL,
phase NVARCHAR(40) NOT NULL,
execution_mode NVARCHAR(20) NOT NULL,
configured_trigger_type NVARCHAR(40) NULL,
run_trigger_type NVARCHAR(40) NULL,
run_trigger_source NVARCHAR(160) NULL,
marketplace_id NVARCHAR(50) NULL,
profile_id NVARCHAR(100) NULL,
period_key NVARCHAR(80) NULL,
stats_start DATE NULL,
stats_end DATE NULL,
request_start DATE NULL,
request_end DATE NULL,
artifact_scope NVARCHAR(220) NOT NULL,
azure_resource_group NVARCHAR(200) NULL,
azure_job_name NVARCHAR(200) NULL,
azure_execution_name NVARCHAR(300) NULL,
container_app_name NVARCHAR(200) NULL,
container_revision NVARCHAR(200) NULL,
container_replica NVARCHAR(200) NULL,
container_image NVARCHAR(500) NULL,
image_tag NVARCHAR(120) NULL,
git_sha NVARCHAR(80) NULL,
command_line_hash CHAR(64) NULL,
status NVARCHAR(40) NOT NULL DEFAULT 'running',
started_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
finished_at DATETIME2 NULL,
duration_ms BIGINT NULL,
commands_total INT NOT NULL DEFAULT 0,
commands_failed INT NOT NULL DEFAULT 0,
artifact_restored_count INT NOT NULL DEFAULT 0,
artifact_saved_count INT NOT NULL DEFAULT 0,
artifact_skipped_count INT NOT NULL DEFAULT 0,
error_type NVARCHAR(200) NULL,
error_summary NVARCHAR(MAX) NULL,
config_snapshot_json NVARCHAR(MAX) NULL,
created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
```

建议约束：

```text
workflow IN ('weekly', 'monthly')
phase IN ('submit', 'collect_ingest', 'report_delivery')
execution_mode IN ('dry_run', 'execute')
status IN ('running', 'succeeded', 'failed', 'partial', 'skipped', 'blocked')
config_snapshot_json IS NULL OR ISJSON(config_snapshot_json)=1
```

建议索引：

```text
IX_pipeline_job_run_scope_phase_started (artifact_scope, phase, started_at DESC)
IX_pipeline_job_run_status_started (status, started_at DESC)
IX_pipeline_job_run_workflow_period (workflow, period_key, phase)
IX_pipeline_job_run_azure_job_started (azure_job_name, started_at DESC)
UX_pipeline_job_run_uid (run_uid)
```

### 9.3 `pipeline_job_command_run` 设计

建议字段：

```sql
id BIGINT IDENTITY(1,1) PRIMARY KEY,
job_run_id BIGINT NOT NULL,
command_index INT NOT NULL,
command_label NVARCHAR(240) NOT NULL,
script_path NVARCHAR(500) NOT NULL,
redacted_args_json NVARCHAR(MAX) NULL,
args_sha256 CHAR(64) NULL,
writes_external_or_database BIT NOT NULL DEFAULT 0,
status NVARCHAR(40) NOT NULL DEFAULT 'running',
exit_code INT NULL,
started_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
finished_at DATETIME2 NULL,
duration_ms BIGINT NULL,
rows_read INT NULL,
rows_inserted INT NULL,
rows_updated INT NULL,
rows_skipped INT NULL,
rows_failed INT NULL,
files_created INT NULL,
error_type NVARCHAR(200) NULL,
error_summary NVARCHAR(MAX) NULL,
output_summary_json NVARCHAR(MAX) NULL,
created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
```

建议约束/索引：

```text
FK job_run_id -> pipeline_job_run(id)
UNIQUE (job_run_id, command_index)
IX_pipeline_job_command_run_script_started (script_path, started_at DESC)
IX_pipeline_job_command_run_status_started (status, started_at DESC)
output_summary_json IS NULL OR ISJSON(output_summary_json)=1
```

### 9.4 `pipeline_job_artifact_link` 设计

建议字段：

```sql
id BIGINT IDENTITY(1,1) PRIMARY KEY,
job_run_id BIGINT NOT NULL,
command_run_id BIGINT NULL,
artifact_id BIGINT NOT NULL,
artifact_role NVARCHAR(40) NOT NULL,
artifact_type NVARCHAR(80) NOT NULL,
artifact_scope NVARCHAR(220) NOT NULL,
relative_path NVARCHAR(600) NOT NULL,
content_sha256 CHAR(64) NOT NULL,
content_size_bytes BIGINT NULL,
created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
```

建议 `artifact_role`：

```text
restored_input
saved_output
raw_report
request_manifest
ingestion_output
coverage_audit
analysis_report
report_delivery_pack
email_send_result
```

建议索引：

```text
IX_pipeline_job_artifact_link_run_role (job_run_id, artifact_role)
IX_pipeline_job_artifact_link_artifact (artifact_id)
IX_pipeline_job_artifact_link_scope_type (artifact_scope, artifact_type)
```

### 9.5 `pipeline_job_table_write_summary` 设计

建议字段：

```sql
id BIGINT IDENTITY(1,1) PRIMARY KEY,
job_run_id BIGINT NOT NULL,
command_run_id BIGINT NOT NULL,
target_table NVARCHAR(300) NOT NULL,
source_system NVARCHAR(50) NULL,
source_report_type NVARCHAR(180) NULL,
source_report_id NVARCHAR(180) NULL,
source_raw_file_path NVARCHAR(1000) NULL,
source_raw_file_sha256 CHAR(64) NULL,
data_start_date DATE NULL,
data_end_date DATE NULL,
rows_read INT NULL,
rows_inserted INT NULL,
rows_updated INT NULL,
rows_skipped INT NULL,
rows_failed INT NULL,
status NVARCHAR(40) NOT NULL DEFAULT 'succeeded',
summary_json NVARCHAR(MAX) NULL,
created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
```

建议索引：

```text
IX_pipeline_job_table_write_target_date (target_table, data_start_date, data_end_date)
IX_pipeline_job_table_write_run (job_run_id, command_run_id)
IX_pipeline_job_table_write_source_report (source_system, source_report_type, source_report_id)
```

### 9.6 业务主键 / 幂等键

审计表采用 append-only 运行记录，不把重复运行合并成一条。

```text
每次手动 Run now / schedule 触发 / retry 都创建新的 pipeline_job_run。
同一 artifact_scope 可以有多次 job_run，用 started_at 和 run_uid 区分。
```

原因：审计日志必须反映真实运行历史，不能因为重复执行而覆盖掉失败记录。

唯一性规则只用于防止同一 run 内重复插入同一个 command index 或 artifact link：

```text
pipeline_job_command_run: UNIQUE(job_run_id, command_index)
pipeline_job_artifact_link: 可选 UNIQUE(job_run_id, command_run_id, artifact_id, artifact_role)
```

### 9.7 新 migration 需求

| 变化 | 原因 | migration 文件 | 状态 |
|---|---|---|---|
| 新增 `pipeline_job_run` | 自动化 stage run 主审计表 | `015_create_pipeline_job_run_audit_tables.sql` | executed |
| 新增 `pipeline_job_command_run` | 子命令级排查 | `015_create_pipeline_job_run_audit_tables.sql` | executed |
| 新增 `pipeline_job_artifact_link` | artifact lineage | `015_create_pipeline_job_run_audit_tables.sql` | executed |
| 新增 `pipeline_job_table_write_summary` | 目标表写入摘要 | `015_create_pipeline_job_run_audit_tables.sql` | executed |

暂不更新 `docs/database/database_current_schema_spec.md`。只有 migration 015 在 Azure SQL 成功执行并导出 live schema 后再更新。

---

## 10. 幂等性设计

审计表与业务表不同：

```text
业务表：upsert / merge，保证同一业务键不重复。
审计表：append-only，保证每次运行都可追溯。
```

重复执行同一个 weekly period 时：

```text
pipeline_job_run 新增一条。
pipeline_job_command_run 新增对应命令记录。
pipeline_job_artifact_link 记录本次 restore/save 看到的 artifacts。
pipeline_job_table_write_summary 记录本次业务表 insert/update/skipped 结果。
```

这能回答：

```text
第一次为什么失败？
第二次是否修复？
第二次是否真的重新写入业务表，还是只是 updated/skipped？
邮件是否重复发送，被 guard 阻断还是 force resend？
```

验证方式：

```text
1. 手动执行同一个 weekly submit 两次。
2. pipeline_job_run 增加 2 条。
3. artifact_scope 相同，但 run_uid 不同。
4. command rows 分别挂在各自 job_run_id 下。
5. 业务表行数不因审计记录重复而异常增加。
```

---

## 11. Schema guard 与异常处理

本功能本身不做 Amazon report schema guard，但必须记录其他模块的 guard 结果。

| 场景 | 处理方式 | 是否阻塞审计写入 | 是否记录 validation event |
|---|---|---|---|
| 子命令返回 `requires_review=True` | command status=`blocked` 或 `failed`，summary 记录原因 | no | yes，引用已有 schema event artifact/table |
| 新字段导致 ingestion 阻断 | command failed，stage failed | no | yes |
| delivery pack 已发送 | command status=`skipped` 或 failed，记录 already sent | no | send_result 或 error_summary |
| SMTP env 缺失 | report_delivery command failed，stage failed | no | error_summary |
| artifact restore 为空 | 记录 restored_count=0；是否失败由 phase 规则决定 | no | no |
| SQL audit 写入失败 | 不应影响业务命令继续执行；console 输出 audit warning | yes, 因无法写入 | no |
| redaction 检测到疑似 secret | 阻止写入该字段原值，只保存 masked value/hash | no | audit warning |

Secret redaction 规则：

```text
任何参数名或 env key 包含 password / secret / token / refresh / key / credential / smtp_password 的值必须 mask。
错误摘要最多保存前 N 字符，且同样经过 redaction。
redacted_args_json 不保存完整连接串，不保存 SMTP 授权码，不保存 Amazon token。
```

---

## 12. 审计与可追溯性

### 12.1 典型排查路径：周报数字不对

```sql
-- 1. 找到这一期 weekly 的所有 stage runs
SELECT id, workflow, phase, artifact_scope, status, started_at, finished_at, commands_failed
FROM dbo.pipeline_job_run
WHERE artifact_scope = 'weekly:ATVPDKIKX0DER:3917953989967300:2026-05-16_2026-05-22'
ORDER BY started_at;
```

```sql
-- 2. 看 collect_ingest 的各子命令结果
SELECT c.command_index, c.command_label, c.script_path, c.status, c.exit_code,
       c.rows_read, c.rows_inserted, c.rows_updated, c.rows_skipped, c.error_summary
FROM dbo.pipeline_job_command_run c
WHERE c.job_run_id = @collect_job_run_id
ORDER BY c.command_index;
```

```sql
-- 3. 看哪些表被写过
SELECT target_table, source_report_type, data_start_date, data_end_date,
       rows_read, rows_inserted, rows_updated, rows_skipped, rows_failed, status
FROM dbo.pipeline_job_table_write_summary
WHERE job_run_id = @collect_job_run_id
ORDER BY target_table;
```

```sql
-- 4. 找 raw report / report json / email result 文件证据
SELECT l.artifact_role, l.artifact_type, l.relative_path, l.content_sha256, a.created_at
FROM dbo.pipeline_job_artifact_link l
JOIN dbo.pipeline_artifact_store a ON a.id = l.artifact_id
WHERE l.job_run_id IN (@submit_job_run_id, @collect_job_run_id, @report_job_run_id)
ORDER BY a.created_at, l.relative_path;
```

### 12.2 典型排查路径：Amazon report pending

看 submit 是否创建 request，collect 是否下载 raw report：

```text
submit command rows -> report request manifest artifacts
collect command rows -> sp_raw_report / ads_raw_report artifacts
collect table write summary -> rows_read / inserted / updated
```

如果 submit 成功但 collect 没有 raw artifacts，说明 Amazon 报表可能仍在生成或请求失败；再查 `amazon_report_request` 与 artifact manifests。

### 12.3 典型排查路径：邮件没收到

```text
report_delivery job_run status
  -> command: Generate report
  -> command: Generate delivery pack
  -> command: Send report email
  -> artifact: send_result.json
  -> error_summary: SMTP / already sent / recipient guard
```

### 12.4 与 `pipeline_artifact_store` 的关系

`pipeline_job_run` 只保存摘要和索引，不保存大文件。

```text
raw report content -> pipeline_artifact_store.content_bytes
report XLSX/JSON -> pipeline_artifact_store.content_bytes
send_result.json -> pipeline_artifact_store.content_bytes
job audit summary -> pipeline_job_* tables
```

### 12.5 与 `amazon_sync_run_log` 的关系

`amazon_sync_run_log` 已存在，且 normalized 表中已有 `source_run_id` 字段指向它。该表更适合作为某个 ingestion 脚本内部的同步日志。

新表定位更上层：

```text
pipeline_job_run = Azure/automation stage 级别
pipeline_job_command_run = wrapper 内子命令级别
amazon_sync_run_log = 部分具体采集/入库脚本内部同步级别
normalized.source_run_id = 业务行追溯到具体同步日志
```

v1 不强行迁移 existing `source_run_id`。后续可在 ingestion 脚本输出 summary 时，把 `amazon_sync_run_log.id` 写到 command `output_summary_json` 中，形成更完整关联。

---

## 13. Retention 与成本控制

建议：

| 数据 | 保留建议 | 原因 |
|---|---|---|
| `pipeline_job_run` | 2-3 年 | 行数极少，是核心审计账本。 |
| `pipeline_job_command_run` | 2-3 年 | 每次 stage 约 4-10 行，成本低。 |
| `pipeline_job_table_write_summary` | 2-3 年 | 用于数据回溯，行数可控。 |
| `pipeline_job_artifact_link` | 与 artifact metadata 同步，至少 1 年 | raw content 可过期，但 link metadata 应保留。 |
| `pipeline_artifact_store.content_bytes` | 90 天起步 | 文件占空间，应按现有 artifact retention 控制。 |
| Log Analytics console log | 低成本短保留 | 全文日志体积大，非主要审计账本。 |

原则：

```text
大文件短保留，结构化元数据长保留。
```

---

## 14. 实现计划

### Phase A：migration + repository + wrapper 最小接入

状态：已实现，等待 migration 015 在 Azure SQL 执行。

1. 已新增 migration `015_create_pipeline_job_run_audit_tables.sql`。
2. 已新增 repository：`src/seller_data_pipeline/db/repositories/pipeline_job_audit_repo.py`。
3. 已新增 service：`src/seller_data_pipeline/services/pipeline_job_audit_service.py`。
4. 已修改 `scripts/run_automation_stage.py`：
   - stage start best-effort 插入 `pipeline_job_run`。
   - 每个 command 前后写 `pipeline_job_command_run`。
   - restore/save 后更新 run counts。
   - finally 更新 run status。
   - 新增 `--configured-trigger-type`, `--run-trigger-type`, `--skip-audit-log`。
5. 已输出 `runtime/automation_audit/{artifact_scope}/{phase}/stage_result.json`，并由现有 artifact save 机制保存。

### Phase B：artifact link

状态：v1 已实现。

1. `PipelineArtifactService.restore_scope` / `save_paths` 已返回 artifact ids 或可追踪 summaries。
2. 已写入 `pipeline_job_artifact_link`。
3. 已对 saved output 根据 artifact type 生成 role：raw_report / analysis_report / email_send_result / automation_audit 等。

### Phase C：table write summary

状态：v1 已部分实现，后续增强。

1. 先复用已存在的 ingestion summary JSON，不要求本轮修改所有子脚本。
2. 已从 ingestion summary 中提取 target_table、source_report_type、rows_read/inserted/updated/skipped/status。
3. 已写入 `pipeline_job_table_write_summary`。
4. 第一版不保证每个脚本都有完整 rows_inserted/updated；缺失时允许 NULL，但必须记录 command status 与 output artifact。

### Phase D：operations runbook

1. 新增 `docs/operations/pipeline_job_audit_troubleshooting.md`。
2. 提供常用 SQL：按 artifact_scope 查三阶段、按 report period 查原始数据、按 target table 查写入历史、按 failed status 查错误。
3. 周报/月报自动跑通后，用真实 run 补充验收样例。

---

## 15. 验收标准

### 15.1 本地/CI 检查

```bash
ruff check src tests scripts
PYTHONPATH=src pytest tests/unit -q
python -m compileall -q scripts src tests
```

### 15.2 migration 检查

```bash
python scripts/run_sql_migration.py --file sql/migrations/015_create_pipeline_job_run_audit_tables.sql --dry-run --show-batches
python scripts/run_sql_migration.py --file sql/migrations/015_create_pipeline_job_run_audit_tables.sql
python scripts/export_database_schema_spec.py --output-prefix after_015_pipeline_job_run_audit --include-row-counts
```

执行成功后才更新：

```text
docs/database/database_current_schema_spec.md
docs/project/progress_next_steps.md
```

### 15.3 功能验收

1. 手动运行 weekly submit main/dev job 后，`pipeline_job_run` 增加一条 `phase=submit` 记录。
2. submit 子命令在 `pipeline_job_command_run` 中有 4 条左右记录，exit_code 全部为 0。
3. 手动运行 collect_ingest 后，能看到 collect / ingest / audit 子命令记录。
4. 如果 Orders schema guard 失败，run status 为 failed，command error_summary 能看到 `requires_review` / new_fields 摘要。
5. 手动运行 report_delivery 后，能看到生成报表、生成 delivery pack、发送邮件三类命令记录。
6. `pipeline_job_artifact_link` 能查到 request manifests、raw reports、analysis reports、send_result。
7. 重复运行同一 artifact_scope，不覆盖旧 audit run，而是新增 run rows。
8. 查询 redacted args 和 error_summary，不出现 password、token、refresh token、SMTP 授权码。

---

## 16. 相关代码路径

计划新增：

```text
src/seller_data_pipeline/db/repositories/pipeline_job_audit_repo.py
src/seller_data_pipeline/services/pipeline_job_audit_service.py
sql/migrations/015_create_pipeline_job_run_audit_tables.sql
tests/unit/services/test_pipeline_job_audit_service.py
tests/unit/db/test_pipeline_job_audit_repo.py
```

计划修改：

```text
scripts/run_automation_stage.py
src/seller_data_pipeline/services/automation_schedule_service.py
src/seller_data_pipeline/services/pipeline_artifact_service.py
src/seller_data_pipeline/db/repositories/pipeline_artifact_repo.py  # 如需返回 saved artifact ids
```

可能后续修改：

```text
scripts/ingest_*_report.py
scripts/collect_*_reports.py
scripts/generate_*_report.py
scripts/send_report_email.py
```

这些脚本后续应逐步统一输出 summary JSON，便于 table write summary 提取。

---

## 17. 风险与取舍

| 风险 | 取舍 |
|---|---|
| 新增多张表增加复杂度 | 自动化已进入 main schedule，审计价值高于复杂度成本。 |
| 无法捕获 SQL 连接失败前的日志 | DB 不可用时只能依赖 Log Analytics；这是合理边界。 |
| 解析每个子脚本 rows_inserted/updated 需要逐步补齐 | v1 先记录 command status/artifact links，row summary 允许逐步增强。 |
| artifact content 90 天后可能清理 | 结构化 metadata 保留更久，必要时从 normalized 表和外部 Amazon 重新请求。 |
| env/args 可能误含 secret | 必须实现 redaction guard 和单元测试。 |

---

## 18. 当前结论

本功能已完成第一版代码实现，仍需按数据库开发规范执行 migration 015 并导出 live schema。

建议下一步：

```text
1. 本地/CI 检查：ruff、pytest、compileall。
2. dry-run migration 015。
3. execute migration 015 到 Azure SQL。
4. export live schema，并更新 docs/database/database_current_schema_spec.md。
5. 给 Azure Container Apps Jobs 补充建议 env：
   SDP_AZURE_JOB_NAME、SDP_CONFIGURED_TRIGGER_TYPE、SDP_CONTAINER_IMAGE、SDP_IMAGE_TAG。
6. 手动 Run weekly submit/collect/report_delivery 验证 pipeline_job_* 审计表写入。
```
