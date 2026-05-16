# ADR-005: 渐进式抽象，先专用入口后通用框架

> 状态：Accepted  
> 日期：2026-05-16  
> 影响范围：ingestion CLI、ingestion service、repository 抽象、后续 SP-API / Ads 入库功能

## 背景

SellerDataPipeline 后续会有多条相似的数据入库链路，例如 Ads、Listing、Inventory、Sales & Traffic、Settlement。直接一开始做一个完全通用的 `ingest_sp_api_reports.py` 看似节省代码，但在数据结构、业务键、schema guard、审计字段、异常处理尚未稳定时，过早抽象容易带来两个风险：

1. 通用入口为了兼容未来功能而变复杂，影响首个功能验收速度。
2. AI 后续迭代时可能误把未完成的 report 也接入通用 execute，造成未验证数据写库。

当前已验证经验是：Ads 使用专用入口 `ingest_ads_reports.py` 跑通；Listing 使用专用入口 `ingest_listing_snapshot.py` 跑通。这个节奏更稳。

## 决策

项目采用 **渐进式抽象**：

```text
第一个功能：优先专用 CLI / service / repository
第二个相似功能：仍优先专用，但开始识别重复模式
至少两个相似功能完整通过 dry-run / execute / 幂等 / 审计后：再评估是否抽象通用入口
```

不得为了“看起来架构统一”而提前创建能写入多种未验证 report 的通用 execute 入口。

## 约束

任何通用化都不得削弱以下规则：

1. 默认 dry-run，不写数据库。
2. 只有显式 `--execute` 才能写库。
3. execute 前必须经过 schema guard。
4. 写库必须幂等。
5. 必须记录 `amazon_sync_run_log`。
6. 必须记录 `amazon_schema_validation_event`。
7. 必须保留 raw file path / report type / source row hash / business key hash 等追溯字段。
8. 必须继续使用 `get_connection()`，不得绕过 Azure SQL connection warm-up retry。

## 后果

正面影响：

- 单个功能边界更清晰。
- 更容易验收和排查。
- 降低 AI 把未完成数据源误接入数据库的风险。
- 后续抽象时能基于 Ads + Listing + Inventory 的真实重复点，而不是猜测。

代价：

- 前几个 ingestion 功能会有一定重复代码。
- 后续需要专门安排一次重构，把稳定模式抽成公共组件。

## 当前应用

- Ads 入库：`scripts/ingest_ads_reports.py`，已完成。
- Listing 入库：`scripts/ingest_listing_snapshot.py`，已完成。
- 下一步 Inventory 入库：仍建议先使用专用入口，例如 `scripts/ingest_inventory_daily.py`，等 Inventory 与 Sales & Traffic 稳定后再评估通用 SP-API ingestion 框架。
