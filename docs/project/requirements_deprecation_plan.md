# requirements_to_be_deprecated 清理计划

> 更新时间：2026-05-18  
> 文档定位：回答旧 `requirements_to_be_deprecated/` 是否可以删除，以及删除前需要完成哪些条件。

## 1. 当前结论

**现在不建议直接删除 `requirements_to_be_deprecated/`。**

原因不是核心代码依赖它运行，而是当前仍有文档、分析脚本或历史字段记录引用其中的 data sample 文档。直接删除会造成文档引用断裂，也会降低后续追溯字段取样来源的能力。

当前规则：

```text
可以忽略它，不再维护新设计；
但暂时不要删除它；
新文档和新开发只维护 docs/。
```

## 2. 它现在还保留什么价值

`requirements_to_be_deprecated/` 主要保留：

```text
早期 sampling plan
旧 database design 草案
旧 progress 文档
脱敏 data_samples 字段分析记录
```

其中最有价值的是：

```text
requirements_to_be_deprecated/data_samples/*.md
```

这些文件记录了各 Amazon 报告的字段、样例行数、字段路径和特殊 reportOptions。它们不是 raw report，不含真实原始业务数据，但仍是数据接入目录的历史证据。

## 3. 删除前置条件

删除前必须完成：

1. 把仍有价值的 `data_samples/*.md` 迁移或复制到 `docs/data_access/sample_notes/`。
2. 把 `docs/` 中所有引用从 `requirements_to_be_deprecated/data_samples/...` 改成新路径。
3. `scripts/analyze_ads_downloaded_reports.py`、`scripts/analyze_settlement_reports.py` 默认输出目录已改为 `docs/data_access/sample_notes/`；后续如有其他脚本仍写旧路径，需要继续清理。
4. 更新相关测试中对旧路径的断言。
5. 全仓库执行：

```powershell
rg "requirements_to_be_deprecated|requirements/data_samples|requirements/"
```

确认没有非历史说明性质的引用。

## 4. 建议删除方式

由于我们常用 updated-files-only 覆盖包，压缩包覆盖不会自动删除本地旧目录。删除应作为单独人工步骤执行：

```powershell
Remove-Item -Recurse -Force requirements_to_be_deprecated
```

或者在 Git 中明确执行：

```powershell
git rm -r requirements_to_be_deprecated
```

## 5. 当前状态

截至 2026-05-18：

```text
status = keep_temporarily
reason = docs/data_access and several feature docs still cite historical sample notes
next_cleanup = migrate sample notes into docs/data_access/sample_notes
```
