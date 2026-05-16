# ADR-003: 功能文档先于代码实现

> 状态：Accepted  
> 日期：2026-05-16  
> 决策范围：需求设计、AI 迭代、代码开发顺序、功能验收

## 背景

SellerDataPipeline 后续会持续增加功能，包括：

- SP-API normalized ingestion，例如 Listing、库存、销售流量、结算。
- Amazon Ads 数据入库和分析。
- 利润核算、周报、清仓决策、广告优化等运营功能。
- Azure Container Apps Jobs 自动任务。

如果直接从用户需求进入代码实现，容易出现：

1. 功能边界不清，多个功能被混在一次开发里。
2. 源数据、字段映射、目标表和验收标准没有提前确认。
3. 数据库结构被临时新增，后续无法追溯原因。
4. AI 只根据最近聊天上下文开发，忽略项目长期约束。
5. 开发完成后不知道如何判断是否真正完成。

当前项目已经通过 Ads ingestion 跑通一条端到端链路，并建立 `docs/features/FEATURE_TEMPLATE.md`。后续需要把这种工作方式固化为架构决策。

## 决策

任何新功能或明显扩展现有功能的开发，在写代码前必须先创建或更新对应功能文档：

```text
docs/features/feature_xxx.md
```

功能文档必须基于：

```text
docs/features/FEATURE_TEMPLATE.md
```

并至少说明：

1. 功能状态。
2. 业务目标。
3. 范围和非范围。
4. 输入数据来源。
5. 输出结果。
6. 处理流程。
7. 字段映射。
8. 目标数据库表和 business key。
9. 幂等性设计。
10. schema guard 和异常处理。
11. 审计与可追溯性。
12. 命令行入口。
13. 测试计划。
14. 验收标准。
15. 当前实现程度和后续优化。

只有当功能文档中关键设计已经明确，才进入代码实现。

## 适用范围

本 ADR 适用于：

- 新 ingestion 功能。
- 新分析报表功能。
- 新自动任务功能。
- 会影响数据库结构、字段映射、审计逻辑或业务口径的改动。
- 大规模重构。

小范围 bug fix 可以先修复，但修复完成后如果改变了功能行为，也必须回写对应 feature 文档。

## 原因

1. **避免需求漂移**：功能文档是需求和实现之间的稳定契约。
2. **便于 AI 接手**：AI 可以读取 feature 文档理解边界，而不是依赖聊天记录。
3. **减少数据库误改**：feature 文档先说明为什么需要新增表/字段，再写 migration。
4. **提高验收质量**：验收标准在开发前明确，开发后不靠主观判断。
5. **支持分批迭代**：可以先把功能标为 `Planned`，再逐步推进到 `Implementing` 和 `Implemented`。

## 后果

正面影响：

- 每个功能都有明确设计来源。
- 字段映射、业务键、异常处理和验收标准可追溯。
- 后续 AI 更容易局部迭代，不会误改其他模块。
- 文档和代码更容易长期保持一致。

代价：

- 开发前需要花时间写文档。
- 简单功能也需要至少补充最小设计说明。
- 如果需求快速变化，需要同步维护 feature 文档状态。

## 实施规则

1. 新功能先复制 `docs/features/FEATURE_TEMPLATE.md`。
2. 设计未明确时，feature 状态使用 `Proposed` 或 `Planned`。
3. 开始开发时，状态改为 `Implementing`。
4. 通过验收后，状态改为 `Implemented`。
5. 如果放弃，状态改为 `Deprecated`，并说明弃置原因。
6. 相关代码路径和测试命令必须回写到 feature 文档。
7. 如果功能涉及数据库变更，feature 文档必须列出 migration 需求和执行状态。
8. 完成后同步更新 `docs/project/progress_next_steps.md`。

## 示例

Listing 入库功能遵守本 ADR：

```text
docs/features/feature_listing_snapshot_ingestion.md
```

该文档先定义：

```text
GET_MERCHANT_LISTINGS_ALL_DATA -> amazon_listing_snapshot
business_key_hash
schema guard
upsert 幂等性
验收命令和行数检查
```

随后才执行：

```text
sql/migrations/003_add_listing_snapshot_business_key_hash.sql
```

并在 003 执行成功后同步 current schema spec。

## 状态

Accepted。
