# ADR-001: 使用 `docs/` 作为正式文档体系

> 状态：Accepted  
> 日期：2026-05-16  
> 决策范围：项目文档结构、AI 迭代协作方式、历史文档迁移

## 背景

SellerDataPipeline 项目已经从初始取样和草案阶段进入真实 Azure SQL 入库验证阶段。早期文档主要集中在 `requirements/` 下，其中混合了：

- 项目目标。
- 数据接入取样计划。
- 数据库设计。
- 当前真实进度。
- 未来功能设想。
- 临时开发计划。

这种方式在早期探索阶段效率较高，但随着项目开始长期迭代，容易出现以下问题：

1. 设计和真实实现混在一起。
2. 数据接入能力和业务功能设计混在一起。
3. 当前数据库真实结构和未来目标结构混在一起。
4. AI 接手时难以判断哪个文档是唯一事实。
5. 同一信息在多个文档重复维护后容易不一致。

项目后续会主要依赖 AI 协助开发，因此需要更严格、可导航、职责清晰的文档体系。

## 决策

从 2026-05-16 起，项目正式使用 `docs/` 作为长期文档目录。

文档结构如下：

```text
docs/
  README.md

  project/
    project_overview.md
    development_rules.md
    progress_next_steps.md

  data_access/
    amazon_data_access_catalog.md
    sp_api_reports_catalog.md
    amazon_ads_reports_catalog.md
    seller_central_manual_exports.md

  features/
    FEATURE_TEMPLATE.md
    feature_*.md

  database/
    database_current_schema_spec.md
    database_migration_policy.md
    database_field_naming_conventions.md

  adr/
    ADR-xxx-*.md
```

第一批先创建：

```text
README.md
docs/README.md
docs/project/project_overview.md
docs/project/development_rules.md
docs/project/progress_next_steps.md
docs/features/FEATURE_TEMPLATE.md
docs/database/database_migration_policy.md
docs/database/database_current_schema_spec.md
docs/adr/ADR-001-documentation-structure.md
docs/adr/ADR-002-do-not-edit-executed-migrations.md
```

## 文档职责

| 目录 | 职责 |
|---|---|
| `project/` | 项目说明、开发规则、真实进度。 |
| `data_access/` | 只记录能从 Amazon / Ads / Seller Central 拿到什么数据。 |
| `features/` | 记录单个功能的业务目标、设计、实现状态、验收标准。 |
| `database/` | 记录当前真实数据库状态和 migration 规则。 |
| `adr/` | 记录长期架构决策及原因。 |

## 后果

正面影响：

1. AI 和开发者可以按固定路径理解项目。
2. 新功能开发前有标准功能文档模板。
3. 数据源、功能、数据库事实分离，减少混乱。
4. 已执行数据库状态有明确 spec，不再混在未来设计里。
5. 架构决策可以通过 ADR 长期追溯。

需要付出的代价：

1. 旧的 `requirements/` 文档需要分批迁移。
2. 迁移期间会短期存在 `requirements/` 和 `docs/` 并存。
3. 每次功能开发前需要先更新文档，短期看起来更慢，但长期减少返工。

## 迁移规则

1. 新设计、新功能、新进度优先写入 `docs/`。
2. `requirements/` 中历史文档暂时作为迁移来源和兼容参考。
3. 不再在 `requirements/database_design.md` 中追加新的长期设计。
4. 每批迁移完成后，应更新 `docs/project/progress_next_steps.md`。
5. 若旧文档与新 `docs/` 冲突，以 `docs/` 为准。

## 状态

Accepted。
