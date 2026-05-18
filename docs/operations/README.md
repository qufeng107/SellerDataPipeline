# Operations Runbooks

> 文档定位：记录人工执行、半自动执行和未来自动化 Jobs 的运行流程。这里不定义业务口径；业务口径见 `docs/features/`。这里不记录真实数据库字段；真实 schema 见 `docs/database/database_current_schema_spec.md`。

## 当前文档

| 文档 | 用途 |
|---|---|
| `manual_execution_workflow.md` | 本地/人工执行数据下载、入库、加工报表和邮件发送的标准流程。 |
| `data_refresh_policy.md` | 数据源滚动刷新、upsert 覆盖、stable cutoff 与周报/月报加工节奏。 |
| `ingestion_job_cadence_catalog.md` | 每类数据项的建议下载/入库周期、数据窗口和未来自动化频率。 |
| `data_coverage_audit_workflow.md` | 利润/周报前如何审计 normalized 数据覆盖范围和 stable cutoff。 |

## 当前原则

当前项目进入“手动可重复执行”阶段，自动化 Jobs 之前必须先满足：

```text
手动下载 raw data
-> 手动入库 normalized tables
-> 手动刷新/复核覆盖范围
-> 手动加工利润 preview 和周报/月报
-> 手动复核并发送邮件
-> 再迁移到 Azure Container Apps Jobs
```

数据刷新和分析产物频率已明确分离：

```text
数据刷新：可以每 1-2 天执行一次，使用重叠窗口 + upsert 覆盖。
分析产物：销售周报、广告周报、利润周报/月报最短周期为一周。
```

自动化不应改变业务逻辑，只应复用已经通过手动验收的 CLI、配置和审计表。利润核算当前采用 Settlement-led Financial Profit v1.0，第一版必须先人工复核后再进入周报或邮件。
