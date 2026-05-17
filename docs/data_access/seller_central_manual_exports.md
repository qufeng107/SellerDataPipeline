# Seller Central 手动导出数据接入目录

> 更新时间：2026-05-16  
> 文档定位：记录 Seller Central 后台手动导出文件作为补充数据源的边界和候选范围。本文只描述手动导出的数据接入可能性，不把它作为当前第一优先自动化路径。

## 1. 当前原则

本项目第一优先路径是：

```text
SP-API Reports / Amazon Ads API
  -> raw file
  -> parser
  -> schema guard
  -> Azure SQL
```

Seller Central 手动导出只作为以下场景的 fallback：

1. 某类数据暂时无法通过当前 API 权限获取。
2. Amazon API 返回空、取消或字段不完整，需要人工下载对照。
3. 会计或运营临时要求一份 Seller Central 页面里的口径文件。
4. 在 API 自动化功能完成前，用手动文件过渡。

手动导出文件通常更容易因为页面语言、地区、导出格式变化而漂移，因此不应优先作为长期稳定数据源。

## 2. 当前实现状态

| 手动导出类型 | 当前状态 | 说明 |
|---|---|---|
| Monthly Transaction / settlement-like files | `candidate_fallback` | 用户曾经使用 Seller Central 月度交易数据做利润核算；本项目当前优先使用 SP-API `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2`。 |
| Business Reports / Sales dashboard exports | `not_implemented` | 当前优先使用 SP-API `GET_SALES_AND_TRAFFIC_REPORT`。 |
| Manage Inventory exports | `not_implemented` | 当前优先使用 SP-API listing 和 FBA inventory reports。 |
| Advertising console exports | `not_implemented` | 当前优先使用 Amazon Ads API Reporting v3。 |
| Promotion / Coupon UI exports | `not_implemented` | 当前已取得 SP-API promotion/coupon report 样例。 |
| Account Health / Performance notifications | `not_implemented` | 不属于当前第一阶段数据管道主线。 |

## 3. 手动文件接入要求

如果后续确实需要把手动导出纳入项目，必须满足：

1. 在本文件新增该导出类型的说明。
2. 保存脱敏 header / 字段样例，不提交真实经营数据。
3. 明确文件来源页面、导出按钮路径、站点、语言、时间范围和币种。
4. 建立独立 parser，不要复用 SP-API parser 强行兼容。
5. 标记该数据的口径来源，避免和 SP-API / Ads API 口径混用。
6. 如要入库，必须建立对应 feature 文档和 migration 计划。

## 4. 推荐记录模板

新增手动导出时，在本文件按以下模板追加：

```markdown
### <导出文件名称>

| Item | Value |
|---|---|
| Seller Central path | `<后台页面路径>` |
| Marketplace | `<marketplace>` |
| Language / locale | `<页面语言>` |
| File format | `csv / tsv / xlsx / other` |
| Date range rule | `<时间范围规则>` |
| Currency | `<币种>` |
| Current sample status | `not_sampled / sampled_header_only / sampled_with_rows` |
| Sensitivity | `low / medium / high` |

Observed fields:

`field_a`, `field_b`, `field_c`

Notes:

- <口径或限制>
```

## 5. 当前结论

当前阶段不建议优先开发手动导入链路。应先完成 SP-API normalized ingestion，尤其是 Listing、Inventory、Sales & Traffic、Settlement，然后再根据实际缺口决定是否补手动导出 fallback。
