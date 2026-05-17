# ADR-006: Azure SQL 连接预热与重试

> 状态：Accepted  
> 日期：2026-05-17  
> 影响范围：Azure SQL connection、migration、ingestion、数据库检查脚本、未来自动化任务

## 背景

项目使用 Azure SQL 作为运营数据仓库。实际测试中发现，数据库长时间没有执行 SQL 后，首次连接可能失败，典型错误包括：

```text
08001 Login timeout expired
Unable to complete login process due to delay in login response
```

随后再次执行连接测试通常会成功，并且 Azure Portal 中数据库状态会恢复为 Online。该行为符合 serverless/idle-resume 场景下的运维风险：第一次请求可能更多是在唤醒数据库，而不是稳定执行业务 SQL。

后续又观察到另一类连接失败：Azure SQL Server firewall 未放行当前客户端公网 IP，典型错误包括：

```text
40615
Client with IP address '<client-ip>' is not allowed to access the server
```

这不是 idle/resume，也不能靠 retry 解决。自动化任务和 CLI 都需要清楚区分这两类问题：idle/resume 可以由连接层 retry + warm-up 处理；firewall/IP allowlist、账号密码、权限等问题必须 fail fast，并给出可操作提示。

如果未来使用 Azure Container Apps Jobs 做定时任务，不能依赖人工先运行一次 `test_azure_sql_connection.py`。自动化任务必须自己处理连接预热，同时必须提前配置好云端出站网络/IP allowlist。

2026-05-17 的 schema export 实测中，连接在第 3 次尝试才成功：前两次为 `08001` login timeout，第 3 次 warm-up 成功。因此默认尝试次数从 `4` 调整为 `6`，给 serverless resume 留出更安全的缓冲；如遇更长冷启动，CLI 或环境变量仍可临时提高到 8 次或更多。


## 决策

所有真实 Azure SQL 入口必须使用项目统一连接层：

```text
seller_data_pipeline.db.connection.get_connection()
```

连接层负责：

```text
pyodbc.connect retry for known transient connection errors
  -> SELECT 1 warm-up query
  -> yield verified connection to migration / ingestion business SQL
```

默认配置：

```env
AZURE_SQL_CONNECT_MAX_ATTEMPTS='6'
AZURE_SQL_CONNECT_RETRY_DELAY_SECONDS='5'
AZURE_SQL_CONNECT_RETRY_BACKOFF='1.8'
```

`test_azure_sql_connection.py` 可临时覆盖：

```bash
python scripts/test_azure_sql_connection.py --json --max-attempts 8 --retry-delay-seconds 8
```

## 重试边界

连接层只重试 **连接和 warm-up 阶段**，不重试业务 SQL。

允许重试的典型情况：

- SQLSTATE `08001` login timeout。
- SQLSTATE `08S01` communication link failure。
- SQLSTATE `HYT00` / `HYT01` timeout。
- Azure SQL transient errors such as `40613`, `40197`, `40501`。

不得在连接层重试：

- Azure SQL firewall/IP allowlist 错误，例如 `40615` / `Client with IP address ... is not allowed to access the server`。
- 账号密码错误。
- 权限错误。
- SQL 语法错误。
- migration batch 执行失败。
- MERGE/upsert 业务错误。
- parser / schema guard 错误。

这些错误必须暴露出来，由对应功能的 transaction、幂等性和验收规则处理。对 firewall/IP 错误，应先在 Azure Portal SQL server Networking / Firewall rules 放行当前公网 IP，或为 Azure Container Apps Jobs 配置稳定出站网络。

## 后果

正面影响：

- 手动脚本和未来自动化任务都能更稳地处理 Azure SQL idle/resume。
- 业务 SQL 只在连接预热成功后执行。
- 不需要每个 script 自己写重复的连接重试逻辑。
- firewall/IP allowlist、SQL login 等非重试类错误会更早暴露，并给出明确处理方向。

代价：

- 首次连接在数据库恢复时可能多等待数秒到数十秒。
- 如果 Azure SQL 真正不可用，脚本会在重试后失败，而不是立即失败。

## 维护规则

1. 新的 repository、migration 工具、数据库检查工具都必须复用 `get_connection()`。
2. 不要在业务层直接调用 `pyodbc.connect()`。
3. 如果未来需要更复杂的 retry policy，应优先修改连接层和本 ADR，而不是散落在各脚本中。
4. 如果遇到 firewall/IP allowlist 问题，按 `docs/database/azure_sql_connection_runbook.md` 处理；不要通过增加 retry 次数掩盖该问题。
5. 若切换到 non-serverless Azure SQL 或改变 compute tier，本规则仍可保留；它只会增加一次轻量 `SELECT 1` warm-up。
