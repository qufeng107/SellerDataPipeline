# SellerDataPipeline 数据库文档入口（Legacy Pointer）

> 更新时间：2026-05-16  
> 状态：本文件已不再作为详细数据库设计入口，保留为旧路径兼容入口。

正式数据库文档请阅读：

```text
docs/database/database_current_schema_spec.md
docs/database/database_migration_policy.md
```

后续数据库维护流程：

```text
先更新对应 docs/features/feature_*.md 或 docs/data_access/*.md
  -> 对比 docs/database/database_current_schema_spec.md
  -> 新增 SQL migration，例如 003_xxx.sql
  -> 执行 migration
  -> 更新 docs/database/database_current_schema_spec.md
  -> 更新 docs/project/progress_next_steps.md
```

注意：`requirements/database_design.md` 暂时作为上一版整合设计的迁移来源，后续会拆分到 `docs/data_access/` 和 `docs/features/`。新设计不应继续追加到 `requirements/`。
