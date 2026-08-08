# Feature: Schema Guard Resilience / 向后兼容的数据契约校验

> 文档状态：Implemented locally; Azure verification pending  
> 负责人：AI / 待定  
> 更新时间：2026-08-08  
> 功能状态：Implemented / pending Azure production verification  
> 相关功能文档：`docs/features/feature_sales_traffic_ingestion.md`、`docs/features/feature_inventory_ingestion.md` 及其他 normalized ingestion feature 文档  
> 相关 ADR：`docs/adr/ADR-013-schema-guard-compatibility-policy.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`

---

## 1. 功能摘要

本功能重构 SellerDataPipeline 的 schema guard 判定策略，使自动化 ingestion 优先保证长期连续运行，同时继续防止真正会破坏数据正确性的 schema 变化。核心原则是：**Amazon 仅新增未知字段属于向后兼容的 additive drift，不应阻断既有字段解析和写库；只有关键字段缺失、关键结构/语义变化、关键字段解析失败等会破坏当前数据契约的情况才阻断。**

2026-08-03 的真实 Azure 自动化运行暴露了当前策略过严的问题：`GET_SALES_AND_TRAFFIC_REPORT` 仅新增 24 个字段、`GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` 仅新增 2 个字段，均无 required field 缺失，但两个 ingestion 都被 `requires_review=True` 阻断，随后 Weekly Business Review 变成 `no_data`，邮件被 send guard 阻止。本功能用于从机制上避免同类故障再次发生。

本次设计不新增数据库字段，不自动把 Amazon 新字段映射到 normalized table；未知字段继续由 raw file / `raw_data` 保留，并通过 validation event 记录。

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认 |
| 生产故障根因 | 已确认：additive schema drift 被错误当作 blocking condition |
| 设计 | 已冻结 |
| 数据库 migration | 不需要 |
| 公共 schema policy 重构 | 已完成 |
| Sales & Traffic 回归修复 | 已完成 |
| Inventory 回归修复 | 已完成 |
| 其他 ingestion 回归检查 | 已完成：统一 blocking policy 迁至公共 schema 模块，全量单测通过 |
| 单元测试 | 已新增/补强；全量 `313 passed` |
| Azure 手动回归 | 待验证：需构建/部署新镜像后重跑最近一期 weekly |
| 文档同步 | 已完成实现阶段同步 |

功能整体状态：`Implemented / pending Azure verification`。本地代码、回归测试与文档已完成；尚未修改 Azure Job 配置或数据库 schema，下一步需构建新镜像并手动验证最近一期 weekly。

## 3. 业务目标

本功能服务无人值守的 Amazon 数据自动化管道，优先级高于“源报表字段必须与旧样例完全一致”。业务目标：

1. Amazon 增加不影响现有业务逻辑的新字段时，周报、库存、广告、财务等自动数据链路继续运行。
2. 现有 parser 只读取已支持字段；新增未知字段不应阻止已支持字段正常入库。
3. 真正影响业务键、核心指标或解析语义的变化仍必须 fail closed，避免静默写错数据。
4. 所有 schema drift 继续留痕，可在不中断生产的前提下后续人工评估是否值得结构化新字段。
5. 减少因第三方 API 向后兼容扩展导致的人工值守和无效停机。

## 4. 范围与非范围

### 4.1 本功能包含

- 调整公共 schema validation 的 blocking / non-blocking 判定语义。
- 明确区分 `expected_fields` 与 `required_fields`。
- 新字段、未知字段、非关键字段缺失默认不阻断生产，但保留 warning 和 validation event。
- 缺失关键字段、关键字段解析失败、关键结构/粒度变化继续阻断。
- 首先用 2026-08-03 Sales & Traffic / Inventory 真实 schema drift 做回归测试。
- 复核所有复用 `ExpectedReportSchema` 的 normalized ingestion，避免同一问题在 Ads、Orders、Settlement 等模块重复出现。
- 保留 raw data 和 observed/new/missing field 审计能力。

### 4.2 本功能不包含

- 不因为 Amazon 新增字段就自动新增 Azure SQL column。
- 不自动把所有 unknown field 纳入 normalized table。
- 不修改现有业务指标、周报公式或利润口径。
- 不处理 2026-08 monthly Settlement duplicate-key bug；该问题独立迭代。
- 不处理 Promotion/Coupon 当前 schema review；完成公共策略后再根据其真实 missing/extra 情况单独复核。
- 本次实现不新增 SQL migration、不修改 Azure Job 配置；Python schema policy、Sales/Inventory contract 与相关测试已更新。

## 5. 输入数据

本功能不新增外部数据源，作用于现有 ingestion 的 schema validation metadata。

| 输入 | 来源 | 用途 |
|---|---|---|
| observed raw fields | `analyze_report_file(...)` | 判断 Amazon 当前实际返回字段 |
| expected fields | 各 ingestion table/schema spec | 已知、可识别字段目录 |
| required fields | 各 ingestion 的核心数据契约 | 判断是否仍能安全写入现有 normalized table |
| parser result | 各 report parser | 判断关键值是否可正确解析 |
| report options / granularity | report metadata | 判断数据语义是否仍与目标表一致 |

2026-08-03 回归样例：

```text
GET_SALES_AND_TRAFFIC_REPORT:
  missing required/expected at incident time = []
  new fields = 24
  result at incident time = requires_review=True -> blocked

GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA:
  missing required/expected at incident time = []
  new fields = 2
  result at incident time = requires_review=True -> blocked
```

## 6. 输出结果

| 输出 | 目标行为 |
|---|---|
| normalized rows | additive drift 时继续按原 mapping 写入 |
| `raw_data` | 完整保留原始行/对象，包括当前 parser 未结构化的新字段 |
| schema validation event | 继续记录 observed / expected / missing / new / unmapped |
| `requires_review` | 只表示“需要人工处理后才能安全继续”，不再等价于所有 warning |
| CLI / automation exit code | non-blocking drift 为 0；blocking contract failure 保持非 0 |

## 7. 处理流程

目标流程：

```text
raw report
  -> analyze observed fields
  -> compare with expected/required contract
  -> classify drift
       additive new fields ----------------------> warning, non-blocking
       optional/known non-critical field absent -> warning/info, non-blocking
       required field absent --------------------> blocking
       unsupported semantic option/granularity --> blocking
       required value parse/type failure --------> blocking
       malformed/unparseable report -------------> blocking
  -> always persist schema validation evidence when possible
  -> if non-blocking: parser -> mapping -> preview -> execute/upsert
  -> if blocking: stop before DB write
```

关键点：**warning 与 blocking 解耦**。`severity=warning` 不应自动推导 `requires_review=True`。

## 8. 数据契约模型

### 8.1 `expected_fields`

定义“当前系统已知/已观察/可识别的源字段集合”。用途：

- 发现 Amazon 是否新增字段。
- 生成 schema drift audit。
- 帮助后续决定是否扩展 normalized mapping。

`expected_fields` **不代表每一份 report 都必须出现这些字段**。

### 8.2 `required_fields`

定义“当前 ingestion 若缺失就无法安全完成核心业务写入的最小字段集合”。只应包含：

- 目标表业务键/核心身份字段所必需的源字段；
- 当前核心业务指标必须依赖的源字段；
- 当前 parser 无法合理 fallback 的关键结构字段。

`required_fields` 必须显著小于或等于 `expected_fields`，禁止继续使用：

```python
REQUIRED_FIELDS = EXPECTED_FIELDS
```

作为默认策略。

### 8.3 Unknown / extra fields

```text
new_fields = observed_fields - expected_fields
```

默认行为：

```text
status = new_fields
severity = warning
requires_review = False
blocking = False
```

这些字段：

1. 不自动进入 SQL column；
2. parser 可以忽略；
3. raw file / raw_data 继续保留；
4. validation event 继续记录；
5. 后续如果业务有价值，再单独设计字段映射和 migration。

## 9. Blocking policy

### 9.1 默认判定矩阵

| 场景 | Severity | `requires_review` | 阻塞 execute | 说明 |
|---|---|---:|---:|---|
| 完全匹配 | info | false | no | 正常 |
| 仅新增 unknown fields | warning | false | no | 向后兼容 additive drift |
| 仅 unmapped extra fields | warning | false | no | raw 保留，后续评估 |
| 已知非关键字段缺失 | warning/info | false | no | 不影响核心契约 |
| required field 缺失 | error/warning | true | yes | 核心契约破坏 |
| required field 类型/值解析失败 | error | true | yes | 可能写错业务数据 |
| JSON/TSV 结构无法解析 | error | true | yes | 无法可信入库 |
| unsupported date/asin granularity | warning/error | true | yes | 数据语义与目标表不一致 |
| unexpected empty report | warning/error | true | yes | 由 feature 的 `allow_empty_report` 决定 |
| duplicate business key inside same batch | error | true | yes | 数据完整性风险 |
| raw file 不存在 | error | true | yes | 无输入可处理 |

### 9.2 `schema_drift`

当同时出现 new fields 与 required field 缺失时，可以继续使用 `status=schema_drift`，但阻塞原因必须明确来自 **missing required contract**，而不是因为存在 new fields。

## 10. 第一阶段 critical contract

本节冻结本次实现首批回归所需的最小契约；后续可在各 feature 文档中继续收敛。

### 10.1 Sales & Traffic

首批 required raw contract 建议：

```text
reportSpecification.reportType
reportSpecification.reportOptions.dateGranularity
salesAndTrafficByDate[].date
salesAndTrafficByDate[].salesByDate.orderedProductSales.amount
salesAndTrafficByDate[].salesByDate.unitsOrdered
salesAndTrafficByDate[].trafficByDate.sessions
```

补充规则：

- `dateGranularity` 仍必须为当前目标表支持的 `DAY`；其他粒度属于 semantic incompatibility，继续阻断。
- ASIN section 的身份字段采用 row-level/conditional validation：有 ASIN 行时必须能生成稳定 business key；不要为了一个可选 ASIN section 把所有 observed path 都设为 required。
- currency、refund、claims、feedback、B2B、shipped 等字段缺失默认不应让店铺核心 daily sales/traffic 全部停写。

### 10.2 Inventory

首批 required raw contract 建议：

```text
sku
afn-fulfillable-quantity
```

补充规则：

- `sku` 是核心身份字段。
- `afn-fulfillable-quantity` 是当前库存运营主口径。
- `asin` / `fnsku` / inbound / reserved / unsellable / future-supply 等字段继续解析并写入，但单个非关键字段整体缺失不应让全部库存快照停写。
- 关键 quantity 值若存在但无法解析为合法整数，仍应阻断，避免把错误库存写入 SQL。

## 11. 公共实现设计与当前实现

实现已按公共 schema 层优先完成，而不是在 Sales/Inventory 各自硬编码“接受这 26 个字段”。当前代码结构：

```text
src/seller_data_pipeline/sampling/schema_drift.py
  ExpectedReportSchema
  SchemaValidationResult
  blocking policy / requires_review policy

src/seller_data_pipeline/ingestion/*_table_mapping.py
  expected_fields = known field catalog
  required_fields = minimal feature contract

src/seller_data_pipeline/ingestion/*_ingestion_dry_run.py
  consume centralized blocking result
  feature-specific semantic validation remains local
```

设计要求：

1. `SchemaValidationResult.requires_review` 不再由 `severity in {warning,error}` 自动决定。
2. `new_fields`、普通 `unmapped_fields` 不进入 blocking status。
3. blocking status/policy 只保留一份公共定义，避免各 ingestion 重复维护不同集合。
4. feature-specific semantic guard（例如 `dateGranularity != DAY`）仍可显式 `requires_review=True`。
5. 不需要 database migration；现有 `amazon_schema_validation_event` 字段足以表达 `status + severity + requires_review + new_fields_json`。

## 12. 幂等性设计

本功能不改变 repository business key 和 MERGE/upsert 规则。

Additive drift 下：

```text
同一业务窗口第一次 execute -> 正常 insert/update
同一业务窗口重复 execute -> 仍按原 business_key_hash update/skip
unknown fields 不参与现有 business key
```

除非后续单独 feature 明确需要，否则新字段不能自动改变业务键。

## 13. 审计与可追溯性

现有审计表继续使用，不新增 migration：

| 审计对象 | 现有位置 | 新规则 |
|---|---|---|
| schema validation | `amazon_schema_validation_event` | new fields 可 `severity=warning` 但 `requires_review=False` |
| raw file | raw report / artifact store | 完整保留，作为未知字段事实来源 |
| normalized row | `raw_data` | 尽可能保留完整源行/对象 |
| run log | `amazon_sync_run_log` | additive drift 不应把 ingestion run 标成 failed |
| Azure Job | pipeline job audit/log | 只有 blocking contract failure 才因 schema guard 返回失败 |

## 14. 相关代码路径

本次实现实际涉及：

| 类型 | 路径 | 计划 |
|---|---|---|
| common schema validation | `src/seller_data_pipeline/sampling/schema_drift.py` | 已集中 `BLOCKING_SCHEMA_STATUSES`；warning 与 blocking 解耦，`new_fields` / `unmapped_fields` non-blocking |
| common ingestion policy | `src/seller_data_pipeline/ingestion/*_ingestion_dry_run.py` | 已改为从公共 `schema_drift.py` 导入 blocking policy；Ads 模块仅继续提供 event builder |
| Sales mapping | `src/seller_data_pipeline/ingestion/sales_traffic_table_mapping.py` | 已拆分 expected / required；required 为冻结的 6 个核心 path |
| Sales dry-run | `src/seller_data_pipeline/ingestion/sales_traffic_ingestion_dry_run.py` | 已使用新公共 policy；2026-08-03 24 个新增 path 回归通过 |
| Inventory mapping | `src/seller_data_pipeline/ingestion/inventory_table_mapping.py` | 已拆分 expected / required；required 为 `sku` + `afn-fulfillable-quantity` |
| Inventory dry-run | `src/seller_data_pipeline/ingestion/inventory_ingestion_dry_run.py` | 已使用新公共 policy；2026-08-03 两个新增字段回归通过 |
| other ingestion | `src/seller_data_pipeline/ingestion/*_ingestion_dry_run.py` | 已统一从公共模块读取 blocking policy；全量单测通过 |
| unit tests | `tests/unit/...` | 已新增 additive drift / missing required / optional absence / empty-report policy 回归 |

## 15. 测试计划

### 15.1 公共 schema validator

必须新增至少以下测试：

1. expected 全部存在 -> `ok`, non-blocking。
2. 仅有新字段 -> `new_fields`, warning, `requires_review=False`。
3. required field 缺失 -> blocking, `requires_review=True`。
4. required field 缺失 + new fields -> blocking `schema_drift`。
5. 非关键 expected field 缺失 -> 不阻断。
6. `allow_empty_report=True` -> empty report 不阻断。
7. `allow_empty_report=False` -> empty report 阻断。

### 15.2 2026-08-03 生产事故回归

Sales & Traffic fixture 应包含当次 24 个新增 JSON path，并验证：

```text
prepared_rows > 0
requires_review = False
schema status = new_fields / non-blocking drift
```

Inventory fixture 应包含：

```text
afn-fc-transfer-quantity
afn-onhand-buyable-quantity
```

并验证：

```text
prepared_rows > 0
requires_review = False
```

### 15.3 关键字段缺失回归

分别删除：

```text
Sales & Traffic: salesAndTrafficByDate[].date
Inventory: sku
```

必须验证：

```text
prepared_rows = 0
requires_review = True
execute blocked
```

### 15.4 全量测试

```bash
PYTHONPATH=src pytest -q
python -m compileall -q scripts src tests
```

## 16. 验收标准

实现阶段验收状态：

1. ✅ 2026-08-03 Sales & Traffic 24 个新增 path 回归样例不再阻断。
2. ✅ 2026-08-03 Inventory 两个新增字段回归样例不再阻断。
3. ✅ validation event 仍完整记录 new fields，且 `requires_review=False`。
4. ✅ Sales & Traffic 关键字段缺失仍阻断。
5. ✅ Inventory 关键字段缺失仍阻断。
6. ✅ Inventory parser 关键整数解析错误仍保持 fail closed；空 SKU 身份值也拒绝。
7. ✅ `dateGranularity` 等既有语义 guard 未放宽。
8. ✅ 全量 unit tests / compileall 通过：`313 passed`，`compileall_ok`。
9. ⏳ Azure 手动执行最近一期 weekly `collect_ingest` 成功。
10. ⏳ Weekly Business Review 恢复非 `no_data`（前提是源数据本身有数据）。
11. ⏳ report delivery send guard 不再因 schema-additive drift 间接阻断。
12. ⏳ 重新执行同一批数据的 Azure SQL 幂等性验证。
13. ✅ 本文档与 `progress_next_steps.md` 已同步到实现完成、云端验收待执行状态。

## 17. 数据库变更判断

```text
Current schema already supports this feature.
```

本次不需要 migration，原因：

- 不把 Amazon 新增字段自动结构化入库。
- 原目标字段和目标表仍可正常使用。
- `raw_data` / raw artifact 已能保留原始字段。
- `amazon_schema_validation_event` 已有 `status`、`severity`、`requires_review`、`missing_fields_json`、`new_fields_json`、`unmapped_fields_json` 等审计字段。

因此不得为本次 robustness 修复新增 SQL migration，也不得修改已执行 migration。

## 18. 当前实现状态

| 日期 | 进展 | 证据/命令 | 备注 |
|---|---|---|---|
| 2026-08-03 | Weekly production collect/ingest 暴露 schema guard false-positive blocking | Sales & Traffic `new_fields=24`, `missing_fields=[]`; Inventory `new_fields=2`, `missing_fields=[]` | 两个 ingestion 均 exit 2，WBR 后续 `no_data` |
| 2026-08-08 | 故障定位完成 | SP-API / Ads report 下载成功，Orders / Ads ingestion 成功；排除 token 为主因 | 根因收敛为 additive drift policy |
| 2026-08-08 | 新 schema guard resilience 设计冻结 | 本文档 + ADR-013 | 先设计后代码 |
| 2026-08-08 | 公共 compatibility policy 实现 | `schema_drift.py` + 各 ingestion dry-run import | `new_fields` / 普通 `unmapped_fields` warning-only；blocking policy 单一来源 |
| 2026-08-08 | Sales/Inventory 最小 required contract 实现 | table mapping + Inventory parser | Sales 6 个核心 path；Inventory 2 个核心字段 |
| 2026-08-08 | 生产事故回归测试完成 | `PYTHONPATH=src pytest -q` -> `313 passed`; `python -m compileall -q scripts src tests` -> success | 24 + 2 additive fields 均 non-blocking；required missing 仍 blocking |

## 19. 后续优化

- 可增加 drift notification 聚合，例如“本周出现 24 个新字段，但生产未受影响”。
- 可为 expected optional field 缺失增加单独字段/状态，而不复用 `missing_fields_json`；若未来需要新增 DB 字段，应另开 migration 迭代。
- 可按 report type 定义更精细的 row-level conditional contract，而不是只做 flat field-set 校验。
- 新字段有明确运营价值时，再单独设计 normalized column / migration，不与 robustness 修复耦合。

## 20. 弃置记录

| 日期 | 弃置方案 | 原因 | 替代方案 |
|---|---|---|---|
| 2026-08-08 | 每次 Amazon 新增字段都手工加入 expected whitelist 后才能恢复生产 | 仍会让向后兼容 API 扩展造成停机，长期维护成本高 | additive drift warning-only；只对 required contract fail closed |
| 2026-08-08 | 直接设置 `allow_extra_fields=True` 并完全忽略新字段 | 会失去 schema drift 可观测性 | 继续记录 `new_fields` warning，但不阻断 |
| 2026-08-08 | 自动给所有新增字段增加 SQL column | 会把第三方 schema 变化直接传导到数据库，增加 migration 和业务耦合 | raw 保留 + 按业务价值单独扩展 normalized schema |
