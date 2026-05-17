# 数据接入文档索引

> 更新时间：2026-05-16  
> 文档定位：本目录只记录 SellerDataPipeline 可以从 Amazon 相关系统接入哪些原始数据、每类数据如何获取、文件结构和已观察到的源字段。这里不定义利润口径、周报口径或业务功能实现。

## 1. 文档边界

本目录回答：

```text
Amazon / Ads / Seller Central 能给我们什么原始数据？
这些数据通过什么接口或路径拿到？
当前样例文件是什么格式？
样例里观察到了哪些字段？
当前下载、解析、入库验证状态如何？
```

本目录不回答：

```text
这些数据如何计算利润？
如何生成周报？
如何做清仓决策？
具体数据库表为什么这样设计？
某个功能如何验收？
```

这些内容应分别进入 `docs/features/` 和 `docs/database/`。

## 2. 文件清单

| 文档 | 用途 |
|---|---|
| [`amazon_data_access_catalog.md`](amazon_data_access_catalog.md) | Amazon 数据接入总览，汇总 SP-API、Ads API、Seller Central 手动导出的接入范围和状态。 |
| [`sp_api_reports_catalog.md`](sp_api_reports_catalog.md) | SP-API Reports 数据目录：report type、获取方式、样例结构、字段、当前状态。 |
| [`amazon_ads_reports_catalog.md`](amazon_ads_reports_catalog.md) | Amazon Ads API 数据目录：Profiles API 和 Sponsored Products Reporting v3 样例。 |
| [`seller_central_manual_exports.md`](seller_central_manual_exports.md) | Seller Central 手动导出数据目录：仅作为补充和 fallback，不作为第一优先自动化路径。 |

## 3. 维护规则

1. 新增 Amazon 数据源前，先更新本目录对应 catalog。
2. 本目录记录“原始数据能力”，不要夹带业务功能设计。
3. 源字段必须来自脱敏样例、代码常量或已验证的下载记录；不确定字段必须标记为 `not_sampled` 或 `needs_resampling`。
4. 真实 raw file 不提交 GitHub，只提交脱敏字段记录。
5. 若 Amazon 返回新字段、缺字段或结构变化，应先更新样例记录和本目录，再决定是否改 parser、feature 文档或数据库 migration。
