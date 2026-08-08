# ADR-013: Schema Guard 采用向后兼容数据契约，而非完整字段一致性阻断

> 状态：Accepted  
> 日期：2026-08-08  
> 决策范围：所有 normalized ingestion 的 schema guard、自动化稳定性、validation event、未来 report schema 演进

## 背景

SellerDataPipeline 的 schema guard 最初按“当前 observed raw schema 与 expected schema 完整一致”设计。公共 `SchemaValidationResult.requires_review` 会把 warning 视为需要人工复核，同时各 ingestion 的 blocking status 也包含 `new_fields`。这能最大限度避免未知 schema 写库，但对于长期无人值守自动化过于严格。

2026-08-03 的真实 Azure weekly job 证明了这一点：

```text
GET_SALES_AND_TRAFFIC_REPORT
  missing_fields = []
  new_fields = 24
  -> requires_review=True
  -> ingestion blocked

GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA
  missing_fields = []
  new_fields = 2
  -> requires_review=True
  -> ingestion blocked
```

Amazon 原有字段仍然存在，SP-API/Ads 下载正常，Orders/Ads ingestion 正常，但 Sales & Traffic / Inventory 因 additive fields 被阻断，进而导致 Weekly Business Review `no_data` 和邮件 send guard 阻止发送。

这类变化属于第三方 API 的向后兼容扩展。若每次新增字段都要求先修改代码再恢复 pipeline，会把“schema 可观测性”变成“高可用性单点故障”。

## 决策

项目以后采用 **向后兼容数据契约（backward-compatible data contract）** 作为 schema guard 原则：

```text
新增 unknown field
  -> 记录 drift
  -> 不阻断现有 parser / mapping / write

缺失 required field / 关键语义改变 / 关键值无法解析
  -> requires_review=True
  -> 阻断 execute
```

### 1. `expected_fields` 与 `required_fields` 必须分离

`expected_fields` 表示当前已知字段目录，用于 drift 检测；`required_fields` 表示当前 ingestion 安全运行所需的最小数据契约。不得默认令所有 expected field 都是 required field。

### 2. Additive drift 默认 non-blocking

仅出现 `new_fields` 时：

```text
severity = warning
requires_review = false
execute = allowed
```

未知字段继续保存在 raw report / `raw_data`，并写入 schema validation event。

### 3. Warning 与 blocking 解耦

`severity=warning` 只表示值得观察，不代表必须人工处理后才能继续。`requires_review=True` 专门表示“当前数据契约不足以安全写库，需要人工处理”。

### 4. 以下情况继续 fail closed

- required field 缺失；
- 关键字段值/类型无法解析；
- raw report 无法解析；
- report option / granularity 与目标表语义不兼容；
- unexpected empty report；
- 同批数据业务键冲突等数据完整性错误。

### 5. 不自动扩数据库 schema

Amazon 新增字段不会自动触发 migration。只有业务明确需要结构化该字段时，才按正常 feature -> migration -> live schema -> docs 流程扩展数据库。

## 适用范围

该决策适用于所有复用 schema guard 的 ingestion，包括但不限于：

- Amazon Ads reports；
- Listing；
- Inventory snapshot；
- Sales & Traffic；
- Orders；
- Settlement；
- FBA Reimbursements；
- FBA Fee Preview；
- Promotion/Coupon；
- Inventory Ledger。

Feature-specific semantic validation 可以比公共 policy 更严格，但必须在对应 feature 文档中说明业务原因。

## 原因

1. **生产连续性**：第三方向后兼容新增字段不应让自动化停机。
2. **最小数据契约**：真正需要保护的是当前业务依赖，而不是历史样例的完整 shape。
3. **继续可审计**：non-blocking 不等于忽略，new fields 仍完整留痕。
4. **降低维护成本**：无需为无关新字段频繁发布新镜像。
5. **避免静默错误**：required field、类型和语义变化仍 fail closed。

## 后果

正面影响：

- Pipeline 对 Amazon schema 演进更有韧性。
- 周报/月报不会因无关新字段中断。
- schema drift 仍可通过 validation event 追踪。
- 新字段是否结构化由业务价值驱动，而不是被第三方 API 强制驱动。

代价和风险：

- unknown field 中可能包含未来有价值的数据，但不会立即进入 normalized column。
- required field 集合需要按业务依赖认真维护；过少会降低保护，过多会重新造成误阻断。
- 部分 report 需要 row-level 或 conditional semantic validation，不能只靠字段集合比较。

## 实施规则

1. 新/现有 ingestion 的 feature 文档必须明确 critical/required contract。
2. 公共 schema layer 统一维护 blocking policy，避免不同 ingestion 复制不同 status 集合。
3. `new_fields` / 普通 `unmapped_fields` 默认 non-blocking。
4. `missing_fields_json` 在现阶段语义为 missing required fields；如未来要单独记录 missing optional fields，再开新迭代。
5. feature-specific unsupported option / granularity 可继续显式 blocking。
6. 每个 ingestion 至少有“additive drift 不阻断”和“required missing 必须阻断”的单元测试。
7. 数据库结构不因 additive drift 自动变化。

## 相关文档

- `docs/features/feature_schema_guard_resilience.md`
- `docs/features/feature_sales_traffic_ingestion.md`
- `docs/features/feature_inventory_ingestion.md`
- `docs/project/development_rules.md`
- `docs/project/iteration_workflow.md`

## 状态

Accepted。设计已于 2026-08-08 冻结；代码实现和 Azure 回归验证进入下一迭代。
