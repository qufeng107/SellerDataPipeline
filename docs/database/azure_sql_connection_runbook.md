# Azure SQL 连接故障处理 Runbook

> 文档定位：说明本项目连接 Azure SQL `amazon_ops` 时，如何区分 serverless idle/resume、firewall/IP allowlist、账号密码、配置错误，并给出处理步骤。具体连接层设计见 `docs/adr/ADR-006-azure-sql-connection-warmup.md`。

## 1. 先判断错误类型

项目连接层会先执行：

```text
pyodbc.connect retry
  -> SELECT 1 warm-up
  -> verified connection
  -> business SQL / migration / ingestion
```

但不是所有连接失败都应该重试。

| 错误类型 | 典型错误文本 | 是否自动重试 | 处理方式 |
|---|---|---:|---|
| Azure SQL serverless idle/resume | `08001`, `Login timeout expired`, `Unable to complete login process due to delay in login response` | 是 | 等待连接层 retry；必要时提高 max attempts / delay。 |
| Azure SQL firewall/IP 未放行 | `40615`, `Client with IP address 'x.x.x.x' is not allowed to access the server` | 否 | 把当前公网 IP 加入 Azure SQL Server firewall allowlist。 |
| SQL 登录失败 | `18456`, `Login failed`, `28000` | 否 | 检查 `.env` 的用户名、密码、auth mode、数据库权限。 |
| 配置缺失 | `AZURE_SQL_* is required` | 否 | 补充 `.env`。 |
| SQL 语法或 migration 失败 | SQL Server batch 错误 | 否 | 修复 migration 或业务 SQL；不得靠连接层重试。 |

## 2. 当前项目如何处理 idle/resume

如果数据库长时间没有 SQL 请求，Azure SQL serverless 可能需要时间恢复。项目连接层会自动处理常见 transient connection 错误：

```env
AZURE_SQL_CONNECT_MAX_ATTEMPTS='6'
AZURE_SQL_CONNECT_RETRY_DELAY_SECONDS='5'
AZURE_SQL_CONNECT_RETRY_BACKOFF='1.8'
```

可临时提高：

```powershell
python scripts/test_azure_sql_connection.py --json --max-attempts 8 --retry-delay-seconds 8
```

注意：连接层只重试 `pyodbc.connect` 和 `SELECT 1 warm-up`。它不会重试 migration batch、MERGE/upsert、parser 或 schema guard。

## 3. Firewall/IP 未放行的处理

如果看到类似：

```text
Cannot open server '<server-name>' requested by the login.
Client with IP address '<client-ip>' is not allowed to access the server.
To enable access, use the Azure Management Portal or run sp_set_firewall_rule...
(40615)
```

这不是自动暂停或预热问题，也不是增加 retry 就能解决的问题。处理方式：

1. 打开 Azure Portal。
2. 进入 SQL server，例如 `amazon-ops-sql`，不是单个 database。
3. 打开 Networking / Firewalls and virtual networks。
4. 添加当前客户端公网 IP 到 allowlist。
5. 保存后等待几分钟。
6. 重新运行：

```powershell
python scripts/test_azure_sql_connection.py --json
```

如果你在公司网络、家用宽带、手机热点、VPN、英国/中国不同网络之间切换，公网 IP 可能变化，需要重新放行。

## 4. 自动化任务里的网络策略

未来 Azure Container Apps Jobs 不应该依赖“开发者当前公网 IP”。长期建议：

1. 本地开发：使用 Azure SQL firewall allowlist 放行当前开发机器公网 IP。
2. Azure Container Apps Jobs：优先使用云端固定 outbound IP、VNet integration / private endpoint，或明确放行其出站 IP。
3. 生产凭据：使用 Secret / Key Vault / Managed Identity，不把 SQL 密码写进代码。
4. 所有自动化 SQL 入口仍必须使用 `get_connection()`，保留 idle/resume warm-up。

## 5. 推荐排查顺序

```text
连接失败
  -> 看错误码/文本
    -> 08001 / timeout / delay in login response
       -> idle/resume，允许连接层 retry
    -> 40615 / IP not allowed
       -> firewall allowlist 问题，先放行 IP，不要继续重试
    -> 18456 / Login failed / 28000
       -> 账号密码或权限问题
    -> ConfigurationError
       -> .env 配置缺失或错误
    -> 其他 SQL Server 错误
       -> 看具体 SQL / migration / repository 逻辑
```

## 6. 验证命令

连接诊断：

```powershell
python scripts/test_azure_sql_connection.py --json
```

数据库状态：

```powershell
python scripts/check_database_status.py
```

真实 schema 导出：

```powershell
python scripts/export_database_schema_spec.py --output-prefix current_amazon_ops --include-row-counts
```
