# Azure SQL 连接与 Migration 执行说明

> 版本：v1.6  
> 日期：2026-05-14  
> 目的：在正式执行 `sql/migrations/001_create_core_tables.sql` 和 `002_create_indexes.sql` 前，先固定本项目的 Azure SQL 连接、检查、dry-run 与 migration 执行流程。当前文档只覆盖建表前后的最小必要步骤；自动任务调度和 repository/upsert 在下一阶段开发。

---


## 0. 当前状态提醒（2026-05-15）

本轮 chat 中用户确认：Azure SQL 参数尚未配置，真实 SQL 执行和真实入库将在后续新 chat 继续。

当前不要执行：

```powershell
python scripts/run_sql_migration.py --file sql/migrations/001_create_core_tables.sql
python scripts/run_sql_migration.py --file sql/migrations/002_create_indexes.sql
python scripts/ingest_ads_reports.py --execute
```

下一次继续时，先完成 `.env` 中 Azure SQL 参数配置，再运行：

```powershell
python scripts/test_azure_sql_connection.py --json
```

连接成功后再 dry-run migration，并人工确认 `requirements/database_spec.md` 与 SQL migration 一致。


## 1. 当前结论

当前不要通过 Azure Portal 手动复制粘贴整段 SQL。建议统一使用项目内脚本执行：

```bash
python scripts/test_azure_sql_connection.py --json
python scripts/run_sql_migration.py --file sql/migrations/001_create_core_tables.sql --dry-run --show-batches
python scripts/run_sql_migration.py --file sql/migrations/002_create_indexes.sql --dry-run --show-batches
```

如果本地尚未把项目安装为 editable package，命令前加 `PYTHONPATH=src`：

```bash
PYTHONPATH=src python scripts/test_azure_sql_connection.py --json
```

确认连接和 dry-run 均通过后，再执行真实 migration。

---

## 2. 新增文件

```text
src/seller_data_pipeline/db/connection.py       # Azure SQL 连接字符串、连接上下文、诊断查询
src/seller_data_pipeline/db/migrations.py       # SQL Server GO batch 拆分、migration 文件执行
scripts/test_azure_sql_connection.py            # 连接测试入口
scripts/run_sql_migration.py                    # 单个 migration 执行入口
```

原有：

```text
src/seller_data_pipeline/db/azure_sql.py
```

已改为兼容导出层，继续暴露 `build_connection_string`、`get_connection` 等旧名字，避免后续代码引用断裂。

---

## 3. 环境变量

复制 `.env.example` 中 Azure SQL 片段到本地 `.env`，并填入真实值。

第一版本地/手动 migration 推荐：

```env
AZURE_SQL_SERVER='tcp:<your-server>.database.windows.net,1433'
AZURE_SQL_DATABASE='<your-database-name>'
AZURE_SQL_AUTH_MODE='sql_password'
AZURE_SQL_USERNAME='<your-sql-admin-or-user>'
AZURE_SQL_PASSWORD='<your-password>'
AZURE_SQL_DRIVER='ODBC Driver 18 for SQL Server'
AZURE_SQL_ENCRYPT='yes'
AZURE_SQL_TRUST_SERVER_CERTIFICATE='no'
AZURE_SQL_CONNECTION_TIMEOUT='30'
AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID=''
```

未来 Azure Container Apps Job 推荐：

```env
AZURE_SQL_AUTH_MODE='entra_managed_identity'
AZURE_SQL_USERNAME=''
AZURE_SQL_PASSWORD=''
AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID=''  # system-assigned identity 可留空；user-assigned identity 再填 client id
```

但 Managed Identity 需要先在 Azure SQL 中配置对应身份权限；当前建表阶段不强制使用。

---

## 4. 本地前置条件

执行连接测试前，需要本机具备：

```text
Python 3.11+
项目 requirements.txt 已安装
pyodbc 可导入
Microsoft ODBC Driver for SQL Server 已安装
Azure SQL firewall 已允许当前出口 IP
.env 已填 Azure SQL 真实连接参数
```

如果出现 `pyodbc is not installed`，先执行：

```bash
pip install -r requirements.txt
```

如果仍报 driver 找不到，通常是系统尚未安装 Microsoft ODBC Driver，或者 `AZURE_SQL_DRIVER` 名称与本机实际驱动名称不一致。

---

## 5. 连接测试

```bash
python scripts/test_azure_sql_connection.py --json
# 或：PYTHONPATH=src python scripts/test_azure_sql_connection.py --json
```

成功时会输出非敏感诊断信息：

```json
{
  "database_name": "...",
  "login_name": "...",
  "server_name": "...",
  "edition": "...",
  "user_table_count": 0
}
```

如果已经执行过建表，可以查看表清单：

```bash
python scripts/test_azure_sql_connection.py --list-tables
```

---

## 6. Migration dry-run

pyodbc 不认识 SQL Server 工具里的 `GO`，因此项目会在客户端先把 migration 文件拆成 batch。

执行前先 dry-run：

```bash
python scripts/run_sql_migration.py \
  --file sql/migrations/001_create_core_tables.sql \
  --dry-run \
  --show-batches

python scripts/run_sql_migration.py \
  --file sql/migrations/002_create_indexes.sql \
  --dry-run \
  --show-batches
```

你需要检查：

1. batch 数量合理；
2. batch 第一行看起来是预期的 `IF NOT EXISTS` / `CREATE INDEX` 等；
3. 没有误把多个 migration 文件一起执行；
4. 仍然确认 Ads、退货、补货建议、复杂利润汇总和报表快照表不在第一批建表范围。

---

## 7. 正式执行 migration

确认无误后按顺序执行：

```bash
python scripts/run_sql_migration.py --file sql/migrations/001_create_core_tables.sql
python scripts/run_sql_migration.py --file sql/migrations/002_create_indexes.sql
```

执行后检查：

```bash
python scripts/test_azure_sql_connection.py --list-tables
```

重要规则：

1. `001` 和 `002` 一旦在 Azure SQL 成功执行，之后不要再修改这两个历史 migration。
2. 后续结构调整只能新增 `003_xxx.sql`、`004_xxx.sql`。
3. 如果执行中途失败，先保留错误日志，不要反复手动改数据库；应根据失败位置决定回滚、修补或新增 migration。
4. 当前 migration runner 使用事务执行单个文件；如果 SQL Server 对某些 DDL 的事务行为产生特殊错误，需要按错误信息单独处理。

---

## 8. 与任务审计表的关系

`amazon_sync_run_log` 是第一版任务审计表，但初始建表前它还不存在。因此：

1. `scripts/test_azure_sql_connection.py` 暂时只输出命令行日志；
2. `scripts/run_sql_migration.py` 暂时只输出命令行日志；
3. 建表后，下一阶段开发 `TaskAuditRepository`；
4. 之后每次 SP-API 同步、raw 下载、parser、upsert、报表生成、邮件发送、Azure Job 执行，都写入 `amazon_sync_run_log`。

---

## 9. 下一阶段

建表成功后进入 repository/upsert 阶段，优先打通：

```text
amazon_listing_snapshot
amazon_inventory_daily
amazon_sales_traffic_daily
amazon_sales_traffic_asin_daily
```

然后再接：

```text
amazon_settlement_transaction
amazon_order_item
amazon_fba_reimbursement
amazon_fba_fee_preview
```

Ads API 仍暂停，直到 Amazon Ads API 审核通过并能拿到 profile / report 数据。
