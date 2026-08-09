# Feature: Monthly Financial Close Report

> 文档状态：Implemented / in production observation  
> 负责人：AI + Feng  
> 更新时间：2026-08-09  
> 功能状态：Implemented / v1.4 Settlement correctness query guard 已完成本地实现，待 v1.88 Azure 历史修复与月报复核  
> 设计版本：v1.4-settlement-correctness  
> 相关数据接入文档：`docs/data_access/sp_api_reports_catalog.md`, `docs/data_access/amazon_ads_reports_catalog.md`, `docs/data_access/seller_central_manual_exports.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`  
> 相关功能：`docs/features/feature_profit_calculation.md`, `docs/features/feature_sku_cost_management.md`, `docs/operations/manual_refresh_plan_workflow.md`, `docs/operations/historical_backfill_workflow.md`  
> 相关 ADR：`docs/adr/ADR-009-settlement-led-profit-policy.md`, `docs/adr/ADR-010-overlapping-refresh-weekly-analysis.md`

---

## 1. 功能摘要

Monthly Financial Close Report（月度财务结算报表）是 SellerDataPipeline 第一类管理层数据加工报表，定位为小公司版 CFO / CEO 月度经营结果包。它回答一个核心问题：

```text
这个月在 Amazon 美国站，按 Amazon 实际 Settlement 财务结算口径赚了多少钱；如果把广告费按 Ads API 投放发生日期重列，这个月经营上到底赚了多少钱？
```

本功能继续保留已冻结的 `Settlement-led Financial Profit v1.0` 作为财务/会计主口径，并从 v1.2 起新增管理经营口径，用于解决广告账单 posted-date 与广告实际投放 report-date 错位导致的利润误读问题：

```text
Amazon 财务金额以 Settlement / Payments / Flat File V2 入库后的 amazon_settlement_transaction 为主。
内部商品成本以 amazon_sku_cost 为主。
Orders / Sales & Traffic / Ads / Promotion / Coupon / FBA Reimbursements 用于运营解释、交叉校验和辅助指标，不反向覆盖财务主口径。
月报必须同时展示 Settlement-led estimated profit 与 Management estimated profit with report-date ads；后者只用于经营复盘，不替代会计结算口径。
```

v1 不新增数据库结果表，不自动发送邮件，不生成正式 PDF；先输出文件型月结结果，供人工复核、会计沟通、股东/管理层月度回顾使用。

v1.1 在既有管理口径月报基础上增加 Accountant Bookkeeping Pack（会计做账辅助包）设计，目标是让会计每月拿到 XLSX 后，能直接理解 Amazon 销售、退款、平台费、广告费、FBA 费、赔偿、内部成本、汇率、凭证附件和季度汇总之间的关系，减少人工拆账和解释成本。

v1.2 新增双利润口径和 Ads Timing Reconciliation：月报首页必须并列展示 `settlement_led_estimated_profit` 与 `management_estimated_profit_report_date_ads`，并单独展示 Settlement posted-date advertising fee、Ads API report-date spend 和二者差异，避免 Amazon Ads 账单集中入账时误判单月真实经营利润。

v1.3 / v1.87 进一步把经营视角改成 CEO-first：`Management Operating Profit` 成为首页主利润指标，并把 `internal_cogs` 展开为商品货款、头程、包装和其他单位成本。Settlement-led profit 保留为 `Settlement Close Profit` 会计/月结参考；旧 JSON 字段继续保留兼容，但 XLSX 首页不再把 legacy `Estimated Operating Profit` 重复展示成经营主利润。详细设计见 `feature_monthly_executive_pnl_landed_cogs.md`。

v1.4 / v1.88 不修改 P&L 业务公式，专门收紧 Settlement 输入口径：报表查询改用显式 ISO / `DD.MM.YYYY` 日期 SQL helper，对已验证的 Amazon US marketplace 只纳入 `USD` Settlement。历史 foreign-currency / 重复 report repair 与 late-generated Settlement recovery 详见 `feature_settlement_correctness_late_discovery.md`。

---

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认：先做 Monthly Financial Close Report，再做 Weekly Business Review 和 Weekly Ads Optimization Report。 |
| 口径依赖 | 财务/会计主口径仍冻结为 Settlement-led Financial Profit v1.0；v1.2 新增 report-date Ads 管理经营口径，不替代会计结算口径。 |
| 数据源可用性 | 足够支持 v1：Settlement、SKU Cost、Sales & Traffic、Orders、Ads、Promotion/Coupon、Reimbursements 均已入库并验证过。 |
| 设计状态 | v1 已实现；v1.1 会计做账辅助包已实现；v1.2 双利润口径与广告跨期对账已完成代码对齐。 |
| 数据库变更 | v1 不新增数据库表，不新增 migration。 |
| 代码实现 | 已实现 v1/v1.1/v1.2：service / repo / CLI / unit tests 已支持双利润口径、`02_Management_PnL`、`03_Ads_Timing_Recon` 和会计辅助包；待真实 Azure SQL 周期重新生成并人工复核。 |
| 默认输出形式 | `monthly_financial_close_{YYYY-MM}.json` + `monthly_financial_close_{YYYY-MM}.xlsx`。当前代码生成 `01_Summary`、`02_Management_PnL`、`03_Ads_Timing_Recon`、核心明细 sheet 与会计辅助 sheet；`01_Summary` 已包含双利润指标。 |
| 不再默认输出 | 不默认输出 Markdown；不默认输出多个 CSV。 |
| 验收样本 | 先以 `2026-03`、`2026-04` 为主，因为 Settlement 和 SKU 成本当前最完整。 |

---


## 2.1 2026-08-08 Monthly recovery dependency

2026-08-05 自动化暴露的 Settlement duplicate-key 与 Promotion/Coupon schema review 不属于月报计算公式错误，而是上游 ingestion 可靠性问题。补发 2026-06 / 2026-07 月报前必须先完成 `feature_monthly_ingestion_recovery.md`：Settlement exact duplicate repair、canonical-key MERGE/rollback 验证，以及 Promotion/Coupon additive-drift non-blocking 验证。旧 weekly 报告不做历史补发。

## 2.2 2026-08-09 Settlement correctness dependency (v1.88)

Seller Central 2026-05/06/07 Monthly Transaction 人工对账确认，历史 Settlement normalized 数据存在三类 correctness 风险：同一 Amazon report 跨 collection path 重复、`DD.MM.YYYY` 被 SQL Server 无 style 日期解析误判月份、Amazon-generated late Settlement 在后续 collect-only rerun 中未重新 discovery。另发现 US 路径中混入 CAD Settlement。

因此 v1.4 报表读取层增加 explicit-date + expected-currency guard，但**只靠查询 guard 不等同于历史数据已经修复**。2026-05/06/07 正式财务数字必须等待 `feature_settlement_correctness_late_discovery.md` 的 repair + late discovery Azure 验收完成后重新生成；此前董事会修正版只作废稿，不作为正式经营结论。

## 3. 业务目标

### 3.1 CEO / CFO 视角目标

1. **月度结论清晰**：一眼看到本月商品销售、Settlement net、内部 COGS、估算经营利润、利润率和报表状态。
2. **费用结构可解释**：知道广告费、FBA 费、Referral fee、促销、退款、仓储费、赔偿分别影响多少。
3. **SKU 贡献可判断**：看出哪些 SKU 贡献利润，哪些 SKU 虽有销量但被广告、退款或费用吃掉利润。
4. **能和 Amazon 后台对账**：Settlement net 应能回溯到 Flat File V2 / Payments Date Range / All Statements。
5. **能给会计使用**：输出清晰的 Amazon 侧费用结构和内部成本，不替代正式会计报表，但可作为会计解释材料。
6. **能给股东/管理层复核**：XLSX 方便查看和归档；JSON 方便后续生成邮件、PDF 或 Dashboard。
7. **能指导经营决策**：识别广告费率、退款率、促销成本、SKU 盈亏和数据质量风险。
8. **能避免广告费跨期误判**：明确区分 Settlement posted-date 广告扣款与 Ads API report-date 投放花费，展示广告跨期差异。

### 3.2 小公司阶段原则

```text
先可复核，再自动化。
先月度结算闭环，再做复杂分摊。
先管理口径，不直接冒充法定财报。
先 JSON/XLSX 稳定，再生成邮件/PDF。
```

---

## 4. 范围与非范围

### 4.1 本功能包含

- 生成单月财务结算报表。
- 按自然月 `month_start..month_end` 汇总 Settlement posted date 财务数据。
- 汇总 Amazon 侧财务净额、收入、费用、退款、赔偿、清算、广告、促销、税费透传。
- 按 SKU 匹配内部标准成本，计算 SKU 级和总计 COGS。
- 输出月度 Settlement-led estimated operating profit。
- 输出月度 Management estimated profit with report-date Ads。
- 输出 Ads Timing Reconciliation，用于解释 Settlement 广告扣费与 Ads API 投放花费差异。
- 输出 SKU 利润贡献、销售贡献和异常 SKU。
- 输出费用结构分析。
- 输出运营解释指标：Sales & Traffic、Orders、Ads API、Promotion/Coupon、FBA Reimbursements。
- 输出对账和数据完整性检查。
- 输出人工复核 notes / warnings。
- 输出一个结构化 JSON 和一个多 sheet XLSX。
- v1.1 增加面向会计的 Accountant Bookkeeping Pack sheets，包括会计做账汇总、建议分录、季度汇总、汇率工作表、凭证索引、回款核对和手工调整表。

### 4.2 本功能不包含

- 不做 FIFO、移动加权、批次库存成本。
- 不把 Orders 金额当作财务收入主口径。
- 不把 Ads API spend 当作最终财务广告费主口径；但 Management P&L 必须使用 Ads API report-date spend 作为经营发生口径广告费。
- 不把 Promotion/Coupon performance 报表的预算或销售额当作财务促销实扣主口径。
- 不用 Monthly Transaction CSV 全表 `total` 合计替代 Settlement，因为其中可能包含 Transfer / disbursement 行。
- 不自动判断所有历史 statement 是否已经存在；v1 只做 coverage / status / warnings，最终仍需人工复核。
- 不新增月报结果表；连续几期稳定后再考虑月报结果落库。
- v1.1 会计做账辅助包不替代会计判断、不直接生成税务申报表，只提供做账/申报辅助底稿。
- 不自动发邮件；后续另设 email / PDF workflow。
- 不默认生成 Markdown，因为股东、会计和管理层使用场景主要是 XLSX / PDF / Email。
- 不默认生成多个 CSV；如调试需要，可后续增加 `--export-csv`。

---

## 5. 报表命名与使用场景

正式名称：

```text
Monthly Financial Close Report
月度财务结算报表 / 月度经营利润报表
```

v1.2 后对外解释时建议明确说成：

```text
月度财务结算 + 管理经营利润双口径报表
Monthly financial close with management P&L reconciliation
```.

不建议只叫“营收报表”，因为本报表不仅包含 revenue，还包含费用、成本、退款、赔偿和利润。

| 使用者 | 用途 | 推荐文件 |
|---|---|---|
| CEO / 运营负责人 | 判断本月是否赚钱、费用是否失控、SKU 表现是否健康。 | XLSX + 后续 PDF 摘要。 |
| CFO / 会计 | 解释 Amazon Payments、平台费、广告费、促销费、内部成本。 | XLSX。 |
| 股东 / 管理层 | 简洁汇报本月经营结果和风险。 | 后续由 JSON 生成 PDF / Email；必要时附 XLSX。 |
| 后续自动化 | 邮件正文、PDF、Dashboard、趋势分析。 | JSON。 |

---

## 6. 周期口径

### 6.1 报表周期

第一版只支持自然月：

```text
month = YYYY-MM
month_start = YYYY-MM-01
month_end = 当月最后一天
```

CLI 设计：

```powershell
python scripts/generate_monthly_financial_close_report.py --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --month 2026-03 --dry-run
```

等价于：

```text
start_date = 2026-03-01
end_date   = 2026-03-31
```

### 6.2 财务日期口径

财务金额按 Settlement posted date 归属自然月。

从 `amazon_settlement_transaction` 取日期时，沿用现有利润 preview 逻辑：

```sql
posted_date = COALESCE(
    TRY_CONVERT(date, NULLIF(posted_date_time_raw, ''), 127),
    TRY_CONVERT(date, NULLIF(posted_date_time_raw, '')),
    TRY_CONVERT(date, NULLIF(posted_date_raw, ''), 127),
    TRY_CONVERT(date, NULLIF(posted_date_raw, '')),
    TRY_CONVERT(date, NULLIF(deposit_date_raw, ''), 127),
    TRY_CONVERT(date, NULLIF(deposit_date_raw, ''))
)
```

过滤条件：

```sql
marketplace_id = @marketplace_id
AND is_settlement_summary = 0
AND amount IS NOT NULL
AND posted_date BETWEEN @month_start AND @month_end
```

### 6.3 运营日期口径

运营解释指标按各自业务日期归属自然月：

| 数据 | 日期字段 | 用途 |
|---|---|---|
| Sales & Traffic | `amazon_sales_traffic_daily.report_date` | 订单销售、sessions、转化率。 |
| Orders | `purchase_date_raw` 解析后日期 | 订单件数、订单金额、订单状态。 |
| Ads | `report_date` | 广告花费、点击、曝光、7日归因销售。 |
| Promotion/Coupon | 活动 start/end raw 字段 | v1 只做活动概览，不做严格按天分摊。 |
| Reimbursements | `approval_date_raw` | 赔偿事件说明。 |

注意：运营日期口径不应与 Settlement posted date 强行完全一致。

---

## 7. 输入数据清单

### 7.1 主财务数据：`amazon_settlement_transaction`

核心字段：

| 字段 | 用途 |
|---|---|
| `marketplace_id` | marketplace 过滤。 |
| `settlement_id` | statement 周期追溯。 |
| `is_settlement_summary` | 排除 summary 行。 |
| `transaction_type` | 区分 Order / Refund / ServiceFee / Transfer / Liquidations 等。 |
| `amount_type` | Amazon 原始 amount type，例如 ItemPrice / ItemFees / Promotion。 |
| `amount_description` | Amazon 原始 amount description，例如 Principal / Commission / FBAPerUnitFulfillmentFee。 |
| `amount` | 单行金额。 |
| `currency` | 币种。 |
| `amount_category` | 入库时归一化后的金额类别。 |
| `profit_bucket` | 入库时归一化后的利润 bucket。 |
| `posted_date_raw`, `posted_date_time_raw`, `deposit_date_raw` | 财务日期解析。 |
| `seller_sku` | SKU 级分析与成本匹配。 |
| `quantity_purchased` | SKU 件数去重计算。 |
| `order_id`, `order_item_code` | SKU 件数去重 key。 |
| `source_report_id`, `source_raw_file_path`, `source_run_id` | 对账追溯。 |

当前样例证明 3月/4月可用：

- 2026-03 profit preview：`settlement_net=2015.42`, `product_sales=7843.43`, `internal_cogs=1477.55`, `estimated_profit=537.87`。
- 2026-04 profit preview：`settlement_net=1853.15`, `product_sales=6241.84`, `internal_cogs=1075.86`, `estimated_profit=777.29`。

### 7.2 内部成本数据：`amazon_sku_cost`

核心字段：

| 字段 | 用途 |
|---|---|
| `marketplace_id` | marketplace 过滤。 |
| `seller_sku` | 与 Settlement SKU 匹配。 |
| `asin` | 辅助识别产品。 |
| `product_cost` | 单件采购成本。 |
| `first_mile_cost` | 单件头程/海运/清关/入仓分摊成本。 |
| `packaging_cost` | 单件包装成本。 |
| `other_unit_cost` | 其他单位成本。 |
| `currency` | 成本币种；v1 要求与财务币种一致，否则 needs_review。 |
| `effective_from`, `effective_to` | 成本生效区间。 |
| `remark` | 汇率、批次、人工说明。 |

单位成本公式：

```text
unit_standard_cost = product_cost + first_mile_cost + packaging_cost + other_unit_cost
```

成本匹配规则：

```text
对每个 seller_sku 和该 SKU 的 Settlement product-sales posted_date：
选择 effective_from <= posted_date AND (effective_to IS NULL OR effective_to >= posted_date) 的成本记录。
```

若同一 SKU 在一个月内匹配到多条成本记录：

```text
设计目标：按每个 product-sales unit 的 posted_date 分别匹配成本。
如果第一版实现为了快速交付沿用现有 preview 的简化逻辑，则当月多成本行时必须 warning，并将相关 SKU 或整份报表标记为 needs_review。
```

### 7.3 运营销售数据：`amazon_sales_traffic_daily`

核心字段：

| 字段 | 用途 |
|---|---|
| `report_date` | 日期过滤。 |
| `ordered_product_sales_amount` | 运营口径订单销售额。 |
| `ordered_product_sales_currency` | 币种。 |
| `units_ordered` | 订购件数。 |
| `total_order_items` | 订单商品项。 |
| `sessions` | sessions。 |
| `page_views` | page views。 |
| `unit_session_percentage` | Amazon 已给出的 unit session percentage；也可用公式重算。 |
| `refund_rate`, `units_refunded` | 运营口径退款参考。 |

运营公式：

```text
ordered_product_sales = SUM(ordered_product_sales_amount)
units_ordered = SUM(units_ordered)
total_order_items = SUM(total_order_items)
sessions = SUM(sessions)
page_views = SUM(page_views)
unit_session_rate = units_ordered / sessions
avg_selling_price = ordered_product_sales / units_ordered
sales_per_session = ordered_product_sales / sessions
```

### 7.4 订单明细：`amazon_order_item`

核心字段：

| 字段 | 用途 |
|---|---|
| `purchase_date_raw` | 订单日期解析。 |
| `amazon_order_id` | 订单去重。 |
| `seller_sku`, `asin`, `product_name` | SKU 维度解释。 |
| `quantity` | 订单件数。 |
| `item_price` | 订单商品金额。 |
| `item_promotion_discount`, `ship_promotion_discount` | 订单口径促销折扣参考。 |
| `order_status`, `item_status` | 排查取消/异常订单。 |
| `ship_state`, `ship_country` | 后续地区分析。 |

订单解释公式：

```text
order_count = COUNT(DISTINCT amazon_order_id)
order_item_rows = COUNT(*)
ordered_units = SUM(quantity)
ordered_item_sales = SUM(item_price)
```

Orders 仅作运营解释，不作为最终财务收入。

### 7.5 广告数据：Ads daily tables

v1 月度财务报表使用 Ads 数据解释投放效率；v1.2 起 Ads 数据还用于管理经营口径的广告发生额重列。财务/会计主口径仍来自 Settlement bucket `advertising_cost` / category `advertising_fee`，但管理经营口径必须使用 Ads API report-date spend 替换 Settlement posted-date advertising fee。

主要读取：`amazon_ads_sp_campaign_daily`。

核心字段：

| 字段 | 用途 |
|---|---|
| `profile_id` | Ads 账号过滤。v1 推荐要求 CLI 显式传入。 |
| `marketplace_id` | marketplace 过滤。 |
| `report_date` | 日期过滤。 |
| `campaign_id`, `campaign_name` | campaign 维度。 |
| `impressions` | 曝光。 |
| `clicks` | 点击。 |
| `cost` | Ads API 投放日期口径花费。 |
| `sales_7d` | 7日归因销售。 |
| `purchases_7d` | 7日归因购买。 |
| `units_sold_clicks_7d` | 7日归因销售件数。 |

广告运营公式：

```text
ads_spend = SUM(cost)
ads_sales_7d = SUM(sales_7d)
ads_purchases_7d = SUM(purchases_7d)
ads_clicks = SUM(clicks)
ads_impressions = SUM(impressions)
CTR = ads_clicks / ads_impressions
CPC = ads_spend / ads_clicks
Ads CVR = ads_purchases_7d / ads_clicks
ROAS = ads_sales_7d / ads_spend
Ads ACOS = ads_spend / ads_sales_7d
TACOS = ads_spend / ordered_product_sales
```

财务广告费差异说明：

```text
settlement_advertising_fee_abs = ABS(SUM(amount WHERE profit_bucket='advertising_cost'))
ads_api_report_date_spend = SUM(amazon_ads_sp_campaign_daily.cost)
ads_timing_difference = ads_api_report_date_spend - settlement_advertising_fee_abs
```

不要求两者完全一致，因为 Settlement 是扣费/财务 posted-date 口径，Ads API 是广告 report-date/归因口径。月报必须把差异作为 Ads Timing Reconciliation 显示；当差异较大时，应提示可能存在广告账单跨期、账单未入账或 Ads 数据覆盖缺口。

### 7.6 Promotion / Coupon 数据

v1 月报使用 Promotion/Coupon 作为活动解释，不作为财务促销实扣主口径。

可读取：

- `amazon_promotion_performance`
- `amazon_promotion_product_performance`
- `amazon_coupon_performance`
- `amazon_coupon_asin`

核心字段：

| 表 | 字段 | 用途 |
|---|---|---|
| `amazon_promotion_performance` | `promotion_id`, `promotion_name`, `promotion_type`, `status`, `glance_views`, `units_sold`, `revenue`, `start_date_time_raw`, `end_date_time_raw` | 活动总体表现。 |
| `amazon_promotion_product_performance` | `asin`, `product_units_sold`, `product_revenue`, `product_glance_views` | 活动 ASIN 表现。 |
| `amazon_coupon_performance` | `coupon_id`, `name`, `clips`, `redemptions`, `total_discount`, `budget_spent`, `sales`, `start_date_time_raw`, `end_date_time_raw` | Coupon 表现。 |
| `amazon_coupon_asin` | `coupon_id`, `asin` | Coupon 与 ASIN 关系。 |

财务促销主口径：

```text
settlement_promotion_cost = ABS(bucket_totals['promotion_cost'])
settlement_promotion_fee = ABS(bucket_totals['promotion_fee'])
```

Coupon/Promotion performance 仅解释活动效果。

### 7.7 FBA Reimbursements

可读取：`amazon_fba_reimbursement`。

核心字段：

| 字段 | 用途 |
|---|---|
| `approval_date_raw` | 赔偿日期。 |
| `reimbursement_id`, `case_id`, `reason` | 赔偿追溯。 |
| `seller_sku`, `asin`, `fnsku` | SKU 维度。 |
| `amount_total`, `currency` | 赔偿金额。 |
| `quantity_reimbursed_cash`, `quantity_reimbursed_inventory`, `quantity_reimbursed_total` | 数量。 |

v1 处理规则：

```text
财务利润中的 reimbursement 以 Settlement 为主。
FBA Reimbursements 表用于解释 Settlement reimbursement bucket / category 是否合理。
```

---

## 8. 核心财务指标与公式

### 8.1 P&L 主指标

| 指标 | 字段名建议 | 公式 / 来源 | 解释 |
|---|---|---|---|
| Settlement row count | `settlement_row_count` | COUNT(`amazon_settlement_transaction` rows after filter) | 本月财务行数。 |
| Settlement net amount | `settlement_net_amount` | `SUM(amount)` | Amazon 侧本月财务净额，已含收入、退款、平台费、FBA费、广告费、促销、赔偿等。 |
| Product sales | `product_sales_amount` | `SUM(amount WHERE amount_category='product_sales') + SUM(amount WHERE amount_category='liquidation_revenue')` | 当前 preview 已把 `product_sales` 与 `liquidation_revenue` 都纳入 SKU 销售额。报表需同时展示拆分项。 |
| Product sales units | `product_sales_units` | 对 product_sales/liquidation_revenue 行按 `(settlement_id, order_id, order_item_code, seller_sku)` 去重后 SUM(quantity_purchased) | 用于 COGS 的件数。 |
| Internal COGS | `internal_cogs` | `SUM(product_sales_units_by_sku * unit_standard_cost_by_sku)` | 内部 SKU 标准成本。 |
| Estimated operating profit | `estimated_operating_profit` | `settlement_net_amount - internal_cogs` | 月度估算经营利润。 |
| Profit margin on product sales | `profit_margin_on_product_sales` | `estimated_operating_profit / product_sales_amount` | 以 Settlement 商品销售额为分母。 |
| Settlement net margin | `settlement_net_margin` | `settlement_net_amount / product_sales_amount` | Amazon 侧扣费后、扣内部成本前的净结算比例。 |
| COGS ratio | `cogs_ratio` | `internal_cogs / product_sales_amount` | 商品成本率。 |
| Amazon fee burden | `amazon_fee_burden` | `ABS(total_amazon_side_costs) / product_sales_amount` | Amazon 侧总费用压力，可由 bucket 汇总。 |

### 8.2 Settlement bucket 指标

优先使用 `profit_bucket` 汇总，因为它是当前 ingestion 已归一化的管理口径。

| bucket | 字段名建议 | 符号约定 | 说明 |
|---|---|---|---|
| `revenue` | `settlement_revenue` | 通常正数 | 商品收入、配送收入等收入 bucket。 |
| `refund` | `settlement_refund` | 通常负数 | 退款收入冲减。 |
| `amazon_fee` | `amazon_fee` | 通常负数 | referral fee、subscription fee、chargeback 等。 |
| `amazon_fee_refund` | `amazon_fee_refund` | 通常正数 | 退款时退回的部分 commission 等。 |
| `fba_fee` | `fba_fee` | 通常负数 | FBA fulfillment / inbound placement 等。 |
| `fba_storage_fee` | `fba_storage_fee` | 通常负数 | 仓储费。 |
| `advertising_cost` | `settlement_advertising_cost` | 通常负数 | Payments 实扣广告费。 |
| `promotion_cost` | `settlement_promotion_cost` | 通常负数 | 促销折扣。 |
| `promotion_fee` | `settlement_promotion_fee` | 通常负数 | Coupon / Deal fee。 |
| `reimbursement` | `settlement_reimbursement` | 正负均可能 | 库存赔偿或赔偿调整。 |
| `liquidation` | `liquidation_revenue` | 通常正数 | 清算收入。 |
| `liquidation_fee` | `liquidation_fee` | 通常负数 | 清算手续费。 |
| `tax_passthrough` | `tax_passthrough` | 通常接近 0 | 税收代收代缴透传，通常不影响净利润。 |
| `unknown` | `unknown_bucket_amount` | 正负均可能 | 未分类金额，必须进入 review。 |

财务主表必须展示：

```text
bucket amount signed value
bucket absolute_amount = ABS(bucket amount)
bucket_pct_of_product_sales = bucket amount / product_sales_amount
```

### 8.3 `amount_category` 明细指标

在 bucket 下面进一步展示 category，便于对账和定位异常。

当前样例中已经出现的 category 包括：

```text
advertising_fee
commission_refund
coupon_fee
deal_fee
fba_fulfillment_fee
fba_inbound_placement_fee
inventory_reimbursement
liquidation_fee
liquidation_revenue
marketplace_facilitator_tax
product_sales
promotion_discount
promotion_refund_adjustment
referral_fee
refund_commission
refund_revenue
sales_tax
settlement_transfer
shipping_chargeback
shipping_revenue
storage_fee
subscription_fee
unclassified
```

v1 输出规则：

1. category 维度全部输出，不隐藏 0 以外的任何类别。
2. `unclassified` 或 `unknown` 非 0 时，report status 至少为 `needs_review`。
3. 税费透传 `sales_tax + marketplace_facilitator_tax` 应接近 0，差异非 0 时输出 warning。
4. `settlement_transfer` 不参与财务利润明细行计算；如果出现在非 0 类别中，必须说明其为打款/转账类，不应误当经营利润。

---

## 8.5 双利润口径与广告跨期处理

从 v1.2 起，月报必须同时输出两个利润口径。

### 8.5.1 Settlement-led Estimated Profit / 结算口径估算利润

用途：会计做账、Amazon Payments 对账、股东/管理层理解本月实际 posted-date 财务结算结果。

```text
settlement_led_estimated_profit
= settlement_net_amount
- internal_cogs
```

其中 `settlement_net_amount` 已经包含本月 posted-date 内入账的 Amazon fees、FBA fees、refund、promotion、advertising、reimbursement、adjustment 等 Settlement 行。

### 8.5.2 Management Estimated Profit with Report-date Ads / 广告发生口径管理估算利润

用途：运营负责人判断这个自然月真实经营是否健康，避免广告账单集中 posted 到某一天导致本月/下月利润被错配。该口径不是会计结账利润，不替代 Settlement-led 口径。

```text
management_estimated_profit_report_date_ads
= settlement_net_amount
- internal_cogs
+ settlement_advertising_fee_abs
- ads_api_report_date_spend
```

解释：

```text
1. 先从 settlement_net_amount 中把 posted-date 广告扣费加回来；
2. 再用 Ads API report_date 汇总的当月实际投放花费扣除；
3. 这样可以避免某月漏算未入账广告费，也避免下月重复承担上月广告账单。
```

### 8.5.3 Ads Timing Difference / 广告跨期差异

```text
ads_timing_difference = ads_api_report_date_spend - settlement_advertising_fee_abs
ads_timing_difference_pct = ads_timing_difference / ads_api_report_date_spend
```

建议状态规则：

| 条件 | 状态 | 处理 |
|---|---|---|
| `ABS(diff) < 20` 或 `ABS(diff_pct) < 5%` | ok | 只展示。 |
| `ABS(diff) BETWEEN 20 AND 100` 或 `ABS(diff_pct) BETWEEN 5% AND 15%` | warning | 提示可能存在账单跨期或结算截止差异。 |
| `ABS(diff) > 100` 或 `ABS(diff_pct) > 15%` | needs_review | 要求人工检查 Ads 数据覆盖、Advertising invoice、Settlement advertising lines。 |

该规则只影响 review status，不自动覆盖任何财务金额。

## 9. SKU 级指标与公式

### 9.1 SKU 汇总维度

v1 SKU 维度以 Settlement 的 `seller_sku` 为主。若存在历史 SKU / 清算 SKU / FNSKU-like SKU，也按 Settlement SKU 展示，不强行改名。

SKU 输出字段：

| 字段 | 公式 / 来源 |
|---|---|
| `seller_sku` | Settlement `seller_sku`。 |
| `units` | SKU product-sales/liquidation-revenue 行去重后的数量。 |
| `product_sales_amount` | SKU 下 `amount_category IN ('product_sales', 'liquidation_revenue')` 的金额。 |
| `settlement_net_amount` | SKU 下所有 settlement line `SUM(amount)`。 |
| `unit_standard_cost` | `amazon_sku_cost` 匹配得到。 |
| `internal_cogs` | `units * unit_standard_cost`；若按日/行匹配成本，则为每条销售 unit 成本合计。 |
| `sku_estimated_profit_after_cogs` | `settlement_net_amount - internal_cogs`。 |
| `sku_profit_margin` | `sku_estimated_profit_after_cogs / product_sales_amount`。 |
| `sku_revenue_share` | `sku.product_sales_amount / total_product_sales_amount`。 |
| `sku_profit_share` | `sku_estimated_profit_after_cogs / total_estimated_operating_profit`，若总利润 <= 0，则仅展示金额排名。 |
| `status` | ok / missing_cost / currency_mismatch / needs_review。 |
| `notes` | 成本匹配、历史 SKU、清算 SKU、无销售日期等说明。 |

### 9.2 SKU 件数去重规则

沿用当前 preview 逻辑：

```text
若 order_item_code 存在：unit_dedupe_key = (settlement_id, order_id, order_item_code, seller_sku)
否则：unit_dedupe_key = (settlement_id, order_id, seller_sku, settlement_row_id)
```

只对 `amount_category IN ('product_sales', 'liquidation_revenue')` 的行计入销售件数。

### 9.3 SKU 输出排序

XLSX 默认 SKU sheet 排序：

```text
sku_estimated_profit_after_cogs DESC
```

后续可在 PDF / Email 摘要中抽取：

1. Top SKU by profit。
2. Top SKU by sales amount。
3. Negative / low-margin SKU list。

---

## 10. 运营解释指标

月度财务结算报表不是广告周报或销售周报，但应包含简洁经营解释，帮助 CEO/CFO 理解财务结果为什么这样。

### 10.1 Sales & Traffic 指标

| 指标 | 字段名建议 | 公式 |
|---|---|---|
| Ordered Product Sales | `ops_ordered_product_sales` | `SUM(amazon_sales_traffic_daily.ordered_product_sales_amount)` |
| Units Ordered | `ops_units_ordered` | `SUM(units_ordered)` |
| Total Order Items | `ops_total_order_items` | `SUM(total_order_items)` |
| Sessions | `ops_sessions` | `SUM(sessions)` |
| Page Views | `ops_page_views` | `SUM(page_views)` |
| Unit Session Rate | `ops_unit_session_rate` | `ops_units_ordered / ops_sessions` |
| Average Selling Price | `ops_asp` | `ops_ordered_product_sales / ops_units_ordered` |
| Sales per Session | `ops_sales_per_session` | `ops_ordered_product_sales / ops_sessions` |

对比指标：

```text
settlement_product_sales_vs_ops_sales_diff = product_sales_amount - ops_ordered_product_sales
settlement_product_sales_vs_ops_sales_diff_pct = diff / ops_ordered_product_sales
```

解释：差异不要求为 0，因为财务 posted-date 与订单日期不同，但差异过大时需要 review。

### 10.2 Orders 指标

| 指标 | 字段名建议 | 公式 |
|---|---|---|
| Order Count | `order_count` | `COUNT(DISTINCT amazon_order_id)` |
| Order Item Rows | `order_item_rows` | `COUNT(*)` |
| Ordered Units | `order_units` | `SUM(quantity)` |
| Order Item Sales | `order_item_sales` | `SUM(item_price)` |
| Order Promo Discount | `order_promo_discount` | `SUM(item_promotion_discount + ship_promotion_discount)` |
| Cancelled / non-shipped items | `order_exception_count` | 依据 `order_status`, `item_status` 统计，v1 可选。 |

### 10.3 Ads 指标

| 指标 | 字段名建议 | 公式 |
|---|---|---|
| Ads API Spend | `ads_api_spend` | `SUM(amazon_ads_sp_campaign_daily.cost)`，按 `marketplace_id + profile_id + report_date` 过滤。 |
| Ads API Sales 7d | `ads_api_sales_7d` | `SUM(sales_7d)` |
| Ads Purchases 7d | `ads_api_purchases_7d` | `SUM(purchases_7d)` |
| Clicks | `ads_clicks` | `SUM(clicks)` |
| Impressions | `ads_impressions` | `SUM(impressions)` |
| CTR | `ads_ctr` | `ads_clicks / ads_impressions` |
| CPC | `ads_cpc` | `ads_api_spend / ads_clicks` |
| Ads CVR | `ads_cvr` | `ads_api_purchases_7d / ads_clicks` |
| ROAS | `ads_roas` | `ads_api_sales_7d / ads_api_spend` |
| Ads ACOS | `ads_acos` | `ads_api_spend / ads_api_sales_7d` |
| TACOS | `tacos` | `ads_api_spend / ops_ordered_product_sales` |
| Settlement Ads Fee | `settlement_ads_fee_abs` | `ABS(bucket_totals['advertising_cost'])` |
| Ads Timing Difference | `ads_timing_difference` | `ads_api_spend - settlement_ads_fee_abs` |
| Management Profit with Report-date Ads | `management_estimated_profit_report_date_ads` | `settlement_net_amount - internal_cogs + settlement_ads_fee_abs - ads_api_spend` |

展示规则：

```text
Ads API spend 是运营投放效率指标，也是 Management P&L 的广告发生额。
Settlement Ads Fee 是财务实际扣费指标，也是 Settlement-led P&L 的广告扣费来源。
两者并列展示，差异作为 Ads Timing Reconciliation，不互相覆盖。
```

若 Settlement 存在 `advertising_cost`，但指定 `profile_id + month` 在
`amazon_ads_sp_campaign_daily` 中没有任何行，则报表输出
`ads_api_context_missing` warning。该 warning 只说明 Ads API 运营解释数据缺失，
不影响 Settlement-led 财务利润。

### 10.4 Promotion / Coupon 指标

| 指标 | 字段名建议 | 公式 / 来源 |
|---|---|---|
| Settlement Promotion Cost | `settlement_promotion_cost_abs` | `ABS(bucket_totals['promotion_cost'])` |
| Settlement Promotion Fee | `settlement_promotion_fee_abs` | `ABS(bucket_totals['promotion_fee'])` |
| Promotion Revenue | `promotion_report_revenue` | `SUM(amazon_promotion_performance.revenue)`，仅解释。 |
| Promotion Units Sold | `promotion_report_units_sold` | `SUM(units_sold)`，仅解释。 |
| Coupon Clips | `coupon_clips` | `SUM(clips)` |
| Coupon Redemptions | `coupon_redemptions` | `SUM(redemptions)` |
| Coupon Total Discount | `coupon_total_discount` | `SUM(total_discount)`，仅解释。 |
| Coupon Budget Spent | `coupon_budget_spent` | `SUM(budget_spent)`，仅解释。 |
| Coupon Sales | `coupon_sales` | `SUM(sales)`，仅解释。 |

v1 不做 Promotion/Coupon 日期精确分摊；若活动跨月，按活动与月份有重叠进行概览展示，并在 notes 说明。

### 10.5 Reimbursement 指标

| 指标 | 字段名建议 | 来源 |
|---|---|---|
| Settlement Reimbursement | `settlement_reimbursement` | `bucket_totals['reimbursement']` |
| Reimbursement Report Amount | `reimbursement_report_amount` | `SUM(amazon_fba_reimbursement.amount_total)`，按 `approval_date_raw` 落在月内。 |
| Reimbursement Quantity | `reimbursement_quantity` | `SUM(quantity_reimbursed_total)` |
| Reimbursement Reasons | `reimbursement_reason_breakdown` | 按 `reason` 分组。 |

---

## 11. 输出文件设计

### 11.1 输出目录

默认输出目录：

```text
runtime/analysis_reports/monthly_financial_close/{marketplace_id}/{YYYY-MM}/
```

示例：

```text
runtime/analysis_reports/monthly_financial_close/ATVPDKIKX0DER/2026-03/
```

### 11.2 默认输出文件

v1 默认只输出两个文件：

```text
monthly_financial_close_{YYYY-MM}.json
monthly_financial_close_{YYYY-MM}.xlsx
```

不默认输出：

```text
monthly_financial_close.md
monthly_financial_summary.csv
monthly_settlement_bucket_breakdown.csv
monthly_amount_category_breakdown.csv
monthly_sku_profit.csv
monthly_operational_context.csv
monthly_reconciliation_checks.csv
```

原因：

```text
CSV 只能表示一张表，不支持一个文件多个 sheet。
多个 CSV 对人工复核和股东/会计沟通太碎。
Markdown 不适合当前股东/会计使用场景。
JSON + XLSX 更适合后续 PDF / Email 自动化。
```

如未来开发调试需要，可增加：

```text
--export-csv
```

用于额外导出拆分 CSV，但不是 v1 默认行为。

### 11.3 JSON 与 XLSX 的分工

本报表采用一个内存结果对象同时输出 JSON 和 XLSX：

```text
数据库查询
   ↓
MonthlyFinancialCloseResult
   ├── monthly_financial_close_{YYYY-MM}.json
   └── monthly_financial_close_{YYYY-MM}.xlsx
```

不要让 XLSX 生成 JSON，也不要让 JSON 反推 XLSX。二者应来自同一个计算结果对象，保证数字一致。

| 文件 | 定位 | 面向对象 | 内容特点 |
|---|---|---|---|
| `monthly_financial_close_{YYYY-MM}.json` | 机器可读的完整报表结果 / source of truth | 后续 PDF、Email、Dashboard、自动预警、趋势分析 | 结构化、嵌套、包含完整元信息、指标、明细、warnings、可用于生成文本摘要。 |
| `monthly_financial_close_{YYYY-MM}.xlsx` | 人可读、可筛选、可归档的复核表 | CEO、运营负责人、会计、股东 | 多 sheet 扁平表格，适合查看、筛选、排序、对账和人工复核。 |

JSON 不是“转换成文本”的最终报告，但可以包含后续生成邮件/PDF 所需的文本素材，例如 `executive_summary.headline`、`key_findings`、`management_notes`。

---

## 12. JSON 输出结构

文件：

```text
monthly_financial_close_{YYYY-MM}.json
```

建议结构：

```json
{
  "report_type": "monthly_financial_close",
  "version": "v1.0",
  "generated_at": "2026-05-22T00:00:00Z",
  "marketplace_id": "ATVPDKIKX0DER",
  "profile_id": "3917953989967300",
  "period": {
    "month": "2026-03",
    "start_date": "2026-03-01",
    "end_date": "2026-03-31"
  },
  "status": "ok | needs_review | no_data",
  "currency": "USD",
  "executive_summary": {
    "headline": "",
    "key_findings": [],
    "management_notes": []
  },
  "financial_summary": {},
  "settlement_bucket_totals": [],
  "amount_category_totals": [],
  "sku_profitability": [],
  "operational_context": {},
  "reconciliation_checks": [],
  "warnings": [],
  "source_metadata": {},
  "accountant_pack": {
    "bookkeeping_summary": [],
    "suggested_journal_entries": [],
    "quarter_rollup": [],
    "fx_rates": [],
    "source_document_index": [],
    "payout_reconciliation": [],
    "manual_adjustments": []
  },
  "output_files": {}
}
```

### 12.1 JSON `executive_summary`

用于后续生成 Email / PDF 的管理层摘要素材。

建议字段：

| 字段 | 说明 |
|---|---|
| `headline` | 一句话概括本月利润和状态。 |
| `key_findings` | 3-8 条核心发现，例如利润、最大费用项、SKU 风险、广告压力。 |
| `management_notes` | 面向经营动作的建议或人工复核提醒。 |

### 12.2 JSON `financial_summary`

包含所有主指标：

```text
settlement_row_count
settlement_net_amount
product_sales_amount
product_sales_units
internal_cogs
estimated_operating_profit
profit_margin_on_product_sales
settlement_net_margin
cogs_ratio
amazon_fee_burden
```

### 12.3 JSON arrays

以下数组应与 XLSX 对应 sheet 保持字段一致或可一一映射：

```text
settlement_bucket_totals
amount_category_totals
sku_profitability
reconciliation_checks
warnings
```

### 12.4 JSON `source_metadata`

用于追溯和审计：

```text
source_tables
row_counts
period_start
period_end
marketplace_id
profile_id
source_report_ids if available
source_run_ids if available
raw_file_paths if available
```

---

## 13. XLSX 输出结构

文件：

```text
monthly_financial_close_{YYYY-MM}.xlsx
```

### 13.1 Sheet 总览

当前代码默认生成以下 workbook sheets：

```text
00_Readme_说明
01_Summary
02_Management_PnL
03_Ads_Timing_Recon
04_Settlement_Buckets
05_Amount_Categories
06_SKU_Profit
07_Operational_Context
08_Reconciliation_Checks
09_Warnings
10_Raw_Metadata
09_Accounting_Summary
10_Journal_Entries
11_Quarter_Rollup
12_FX_Rates
13_Source_Doc_Index
14_Payout_Recon
15_Adjustments
```

说明：v1.2 将管理经营口径 sheet 前置到 `02_Management_PnL` / `03_Ads_Timing_Recon`，方便打开月报后优先看到广告跨期影响。会计辅助包沿用既有 `09_Accounting_Summary` 至 `15_Adjustments` 命名，实际 Excel sheet 名唯一，虽存在数字前缀重复但不影响读取；后续若要统一编号，应作为兼容性变更单独处理。

Sheet 名保持短、稳定、英文，避免 Excel 兼容问题。面向会计的 sheet 必须使用双语列名，格式建议为 `English / 中文`，并在 sheet 顶部加入中文优先说明区，说明本表用途、使用方式、数据来源、会计需确认事项和限制。

### 13.2 `01_Summary`

给 CEO / 股东 / 会计第一眼看。当前代码已在 summary 中并列展示：

```text
Settlement-led Estimated Profit
Management Estimated Profit with Report-date Ads
Settlement-led Profit Margin
Management Profit Margin
Ads API Report-date Spend
Settlement Advertising Fee
Ads Timing Difference
Estimated Operating Profit  # legacy alias，等同 settlement-led estimated profit
```

建议列保持：

```text
metric_group
metric_name
value
currency
period
status
notes
```

### 13.3 `02_Management_PnL`

管理经营利润表。该 sheet 用于把月度 Settlement-led 财务结果调整为 report-date Ads 管理经营结果。它是 CEO/运营负责人判断本月经营是否真正赚钱的主表，但不替代会计结账口径。

当前代码输出行包括：

```text
Settlement Net Amount
Internal COGS
Settlement Advertising Fee Add-back
Ads API Report-date Spend
Settlement-led Estimated Profit
Management Estimated Profit with Report-date Ads
Product Sales Amount
Settlement-led Profit Margin
Management Profit Margin
```

核心公式：

```text
management_estimated_profit_report_date_ads
= settlement_net_amount
- internal_cogs
+ settlement_advertising_fee_abs
- ads_api_report_date_spend
```

### 13.4 `03_Ads_Timing_Recon`

广告跨期对账表。该 sheet 专门解释 Settlement advertising fee 与 Ads API report-date spend 的差异，避免把 Amazon Ads 账单集中 posted 到某一天误读为当日或当周投放失控。

建议列保持：

```text
period
settlement_advertising_fee_abs
ads_api_report_date_spend
ads_timing_difference
ads_timing_difference_pct
status
possible_reason
required_action
source_reference
notes
```

`possible_reason` 示例：

```text
Normal billing cutoff difference
```

只解释，不强制一致。

### 13.5 `04_Settlement_Buckets`

按内部利润 bucket 汇总 Settlement 金额，例如：

```text
product_sales
shipping_revenue
promotion_cost
advertising_cost
amazon_fee
fba_fee
refund
reimbursement
other_adjustment
```

该 sheet 是财务/会计主口径解释层，用于说明 Settlement net 为什么形成当前结果。

### 13.6 `05_Amount_Categories`

按 Amazon settlement 原始 amount category / amount type 的归类结果汇总，用于检查 parser mapping 是否把 Amazon 原始项目正确归入内部 bucket。

### 13.7 `06_SKU_Profit`

SKU 级利润明细。该 sheet 仅覆盖能从 Settlement / Orders 关联到 SKU 的 product-sales 行，不等于公司最终完整利润表。必须保留 scope note，避免将 SKU 表合计误读为最终公司净利润。

关键字段包括：

```text
seller_sku
units
product_sales_amount
settlement_net_amount
unit_standard_cost
internal_cogs
estimated_profit_after_cogs
profit_margin
revenue_share
status
notes
```

### 13.8 `07_Operational_Context`

运营解释指标。包括 Orders、Sales & Traffic、Ads、Coupon、Promotion、FBA Reimbursements 等辅助数据。该 sheet 用于解释经营变化，不反向覆盖 Settlement 财务主口径。

### 13.9 `08_Reconciliation_Checks`

对账检查项。用于标记 Settlement、Orders、Sales & Traffic、Ads context、SKU 成本覆盖、console reconciliation 等是否存在 warning 或 needs_review。

### 13.10 `09_Warnings`

数据质量和口径风险提示。示例：

```text
missing_sku_cost
currency_mismatch
ads_api_context_missing
ads_timing_needs_review
no_settlement_rows
```

### 13.11 `10_Raw_Metadata`

记录本次生成的源表、行数、日期范围、生成时间、profile/marketplace 和 report version，便于后续追溯。

### 13.12 Accountant Pack 通用格式规则

Accountant Bookkeeping Pack 是在月度经营利润报表基础上增加的会计做账辅助层。其目标不是替代会计软件或税务申报表，而是把 Amazon 复杂的 Settlement / Ads / SKU 成本 / 回款 / 凭证信息转换成会计更容易使用的底稿。

每个会计 sheet 顶部必须有说明区，至少包含以下键值行：

```text
Sheet Purpose / 本表用途
How to Use / 使用方式
Main Data Sources / 主要数据来源
Accounting Caveats / 会计注意事项
Required Accountant Confirmation / 需要会计确认
```

说明区建议中文在前、英文在后，便于中国会计直接阅读。说明区下面再进入表格标题行。会计 sheet 的固定列名必须双语，例如：

```text
Accounting Item / 会计项目
Suggested Account / 建议会计科目
Amount USD / 美元金额
FX Rate / 汇率
Amount CNY / 人民币金额
Source / 数据来源
Accountant Confirmation / 会计确认
Notes / 说明
```

通用原则：

```text
1. JSON 仍保留稳定英文 machine-readable 字段名。
2. XLSX 会计 sheet 使用双语列名，中文含义必须足够明确。
3. 系统只生成会计辅助底稿和建议分录，不宣称自动完成法定会计处理或税务申报。
4. 税务/会计最终口径由公司会计确认，尤其是汇率、收入确认、成本结转、发票合规性、汇兑损益和税务调整。
5. 所有金额必须保留原币金额；人民币金额由汇率表驱动，汇率未确认时不能假装最终入账金额已确认。
6. 每个自动生成金额都应能回溯到 Settlement bucket/category、SKU cost、bank payout、artifact metadata 或人工调整项。
```

### 13.13 `09_Accounting_Summary`

会计做账汇总表。该 sheet 是会计最先看的总览表，用来把 Amazon 的经营分类转换成会计做账语言。它帮助会计快速判断本月应确认哪些收入、费用、退款、赔偿、成本和待确认事项。

Sheet 顶部说明区建议内容：

```text
Sheet Purpose / 本表用途：按会计做账视角汇总本月 Amazon 经营数据，将 Settlement、广告费、FBA 费、退款、赔偿和内部 COGS 转换为会计可理解的项目。
How to Use / 使用方式：会计可先检查每个会计项目的 USD 金额、建议科目、汇率和 CNY 金额，再决定是否直接入账或调整科目。
Main Data Sources / 主要数据来源：Amazon Settlement Flat File V2 / Payments、amazon_sku_cost、Ads API 辅助指标、FBA Reimbursements 辅助指标。
Accounting Caveats / 会计注意事项：本表为做账辅助底稿，不替代正式会计判断；Estimated Operating Profit 是管理口径利润，不等同于企业所得税应纳税所得额。
Required Accountant Confirmation / 需要会计确认：收入是否含税/不含税、汇率口径、建议科目、发票/凭证是否齐全、COGS 是否可税前扣除。
```

建议列：

```text
Line No. / 行号
Accounting Item / 会计项目
Suggested Account / 建议会计科目
Statement Direction / 报表方向
Debit or Credit / 借贷方向
Amount USD / 美元金额
FX Rate / 汇率
Amount CNY / 人民币金额
Source Bucket / 来源利润桶
Source Category / 来源金额类别
Source Sheet / 来源Sheet
Source Reference / 来源引用
Auto Generated / 是否系统生成
Needs Accountant Review / 是否需要会计复核
Accountant Confirmation / 会计确认
Notes / 说明
```

建议会计项目映射：

| Accounting Item / 会计项目 | Suggested Account / 建议会计科目 | Direction / 方向 | Source / 数据来源 | Notes / 说明 |
|---|---|---|---|---|
| Product Sales Revenue / 商品销售收入 | Main Business Revenue / 主营业务收入 | Credit / 贷方 | Settlement `product_sales`, `liquidation_revenue` | 会计确认收入是否按不含税口径入账。 |
| Refunds and Sales Returns / 退款及销售退回 | Sales Returns / 主营业务收入-销售退回或销售折让 | Debit / 借方 | Settlement `refund_revenue` | 可作为收入冲减或单独销售退回科目，最终由会计确认。 |
| Referral and Platform Fees / 平台佣金及服务费 | Selling Expenses - Platform Fees / 销售费用-平台服务费 | Debit / 借方 | Settlement `referral_fee`, `subscription_fee`, chargebacks | 需配合 Amazon fee invoice 或结算单。 |
| FBA Fulfillment Fees / FBA配送履约费 | Selling Expenses - Fulfillment Fees / 销售费用-FBA履约费 | Debit / 借方 | Settlement `fba_fulfillment_fee` | Amazon 代履约费用。 |
| FBA Storage and Inbound Fees / FBA仓储及入仓相关费用 | Selling Expenses - Storage/FBA Fees / 销售费用-FBA仓储及入仓费用 | Debit / 借方 | Settlement storage/inbound categories | 可按公司科目细分。 |
| Advertising Fees / 广告费 | Selling Expenses - Advertising / 销售费用-广告费 | Debit / 借方 | Settlement `advertising_fee` | 财务扣费以 Settlement 为主，Ads API 仅用于投放解释。 |
| Promotion Discounts and Fees / 促销折扣及活动费用 | Selling Expenses - Promotion / 销售费用-促销费 | Debit / 借方 | Settlement promotion buckets | Coupon/Promotion performance 只做解释，不替代实扣。 |
| Reimbursements / 亚马逊赔偿 | Other Income or Expense Offset / 其他收益或费用冲减 | Credit or Debit / 借或贷 | Settlement reimbursement bucket | 赔偿类科目需会计确认。 |
| Internal COGS / 内部商品成本 | Cost of Goods Sold / 主营业务成本 | Debit / 借方 | `amazon_sku_cost` × product sales units | 管理成本口径，需会计结合采购发票、库存结转确认。 |
| Marketplace Facilitator Tax / 平台代收代缴税费 | Pass-through Tax / 代收代缴税费或不入账 | Informational / 备查 | Settlement tax categories | 通常不作为公司收入或费用，最终由会计确认。 |
```

### 13.14 `10_Journal_Entries`

建议记账凭证分录表。该 sheet 用于把 `09_Accounting_Summary` 的会计项目进一步转换成可录入财务软件的建议分录。会计可以复制后调整科目、汇率、摘要和凭证附件。

Sheet 顶部说明区建议内容：

```text
Sheet Purpose / 本表用途：提供月度 Amazon 业务的建议记账分录，减少会计手工拆分 Amazon 结算单的工作量。
How to Use / 使用方式：会计逐行检查借方科目、贷方科目、原币金额、汇率、人民币金额和附件索引，确认后录入财务软件。
Main Data Sources / 主要数据来源：09_Accounting_Summary、Amazon Settlement、SKU成本、银行/万里汇到账核对、人工调整项。
Accounting Caveats / 会计注意事项：本表是建议分录，不是强制分录；收入、成本、费用、汇兑损益和银行到账的最终分录方式由会计决定。
Required Accountant Confirmation / 需要会计确认：凭证日期、摘要、借贷科目、汇率、附件、是否需要拆分多张凭证。
```

建议列：

```text
Voucher Date / 凭证日期
Voucher Group / 凭证组
Voucher Line No. / 凭证行号
Entry Type / 分录类型
Summary / 摘要
Debit Account / 借方科目
Credit Account / 贷方科目
Currency / 币种
Amount Original / 原币金额
FX Rate / 汇率
Amount CNY / 人民币金额
Source Sheet / 来源Sheet
Source Line No. / 来源行号
Source Document ID / 来源凭证ID
Attachment Required / 是否需要附件
Accountant Confirmation / 会计确认
Notes / 说明
```

建议分录组：

```text
1. Revenue recognition / 确认销售收入与退款冲减
2. Amazon fees recognition / 确认平台佣金、FBA费、广告费、促销费等 Amazon 费用
3. COGS recognition / 确认主营业务成本，需结合库存和采购发票
4. Reimbursement recognition / 确认赔偿收入或费用冲减
5. Payout clearing / Amazon应收与万里汇/银行到账核对
6. FX gain/loss / 汇兑损益，需银行结汇或会计政策确认
7. Manual adjustments / 会计手工调整
```

### 13.15 `11_Quarter_Rollup`

季度税务/做账汇总表。该 sheet 用于把月度数据按季度累计，方便中国小企业按季度申报或季度内部复核。第一版可以在单月月报中展示当季截至当前月份的可累计字段；后续季度包可自动合并三个月数据。

Sheet 顶部说明区建议内容：

```text
Sheet Purpose / 本表用途：按季度汇总每月 Amazon 收入、退款、费用、成本、利润和待确认项，帮助会计做季度报税和内部对账准备。
How to Use / 使用方式：会计可把三个月的月报数据合并复核，检查季度累计销售收入、费用、成本和调整项是否完整。
Main Data Sources / 主要数据来源：本月月报、同季度其他月份月报、09_Accounting_Summary、15_Adjustments。
Accounting Caveats / 会计注意事项：季度汇总是申报辅助表，不等于税务申报表；季度申报口径需结合公司其他非 Amazon 收入费用、发票、税务政策和会计账簿。
Required Accountant Confirmation / 需要会计确认：季度所属月份是否齐全、汇率是否一致、是否存在跨月调整、非 Amazon 费用是否已纳入账簿。
```

建议列：

```text
Quarter / 季度
Month / 月份
Accounting Item / 会计项目
Suggested Account / 建议会计科目
Amount USD / 美元金额
FX Rate / 汇率
Amount CNY / 人民币金额
Quarter-to-Date Amount CNY / 季度累计人民币金额
Source Report / 来源月报
Status / 状态
Needs Accountant Review / 是否需要会计复核
Notes / 说明
```

建议季度汇总项目：

```text
Product Sales Revenue / 商品销售收入
Refunds and Sales Returns / 退款及销售退回
Amazon Platform Fees / 亚马逊平台费
FBA Fees / FBA费用
Advertising Fees / 广告费
Promotion Costs / 促销费用
Reimbursements / 亚马逊赔偿
Internal COGS / 内部商品成本
Estimated Operating Profit / 估算经营利润
Manual Adjustments / 手工调整
Unresolved Items / 未决事项
```

### 13.16 `12_FX_Rates`

汇率换算工作表。该 sheet 用于把 USD 等原币金额折算成人民币，给会计保留明确的汇率输入和确认位置。

Sheet 顶部说明区建议内容：

```text
Sheet Purpose / 本表用途：记录本月用于会计入账和季度汇总的汇率口径，驱动会计辅助表中的人民币金额换算。
How to Use / 使用方式：会计填写或确认本月 USD/CNY 汇率，系统据此计算各会计项目人民币金额；如不同项目需要不同汇率，应逐项说明。
Main Data Sources / 主要数据来源：会计确认的记账汇率、中国人民银行/银行结汇单/公司会计政策，系统不自动替代会计判断。
Accounting Caveats / 会计注意事项：不同税种、会计事项或实际结汇可能使用不同汇率；系统默认汇率只能作为草稿，最终以会计确认口径为准。
Required Accountant Confirmation / 需要会计确认：汇率日期、汇率来源、适用范围、是否使用月末汇率/月平均汇率/实际结汇汇率。
```

建议列：

```text
Currency Pair / 货币对
Period / 期间
FX Rate Type / 汇率类型
FX Rate / 汇率
Rate Date / 汇率日期
Rate Source / 汇率来源
Applies To / 适用范围
Accountant Confirmation / 会计确认
Notes / 说明
```

`FX Rate Type / 汇率类型` 示例：

```text
Month-End Rate / 月末汇率
Monthly Average Rate / 月平均汇率
Transaction Date Rate / 交易日汇率
Bank Settlement Rate / 银行结汇汇率
Accountant Manual Rate / 会计手工确认汇率
```

### 13.17 `13_Source_Doc_Index`

凭证附件索引表。该 sheet 用于告诉会计本月做账需要哪些附件、哪些已经由系统生成或保存、哪些仍需人工下载/上传。

Sheet 顶部说明区建议内容：

```text
Sheet Purpose / 本表用途：列出会计做账和税务复核可能需要的 Amazon、银行、采购、物流和内部成本凭证，减少遗漏附件。
How to Use / 使用方式：会计或运营逐项勾选凭证是否已提供，并用 Source Reference 查找原始文件或下载路径。
Main Data Sources / 主要数据来源：pipeline_artifact_store raw reports、Amazon Settlement report、Amazon fee invoice、万里汇/银行流水、采购发票、物流发票、SKU成本表。
Accounting Caveats / 会计注意事项：系统能保存 Amazon raw report，但不一定自动获取所有发票、银行流水和采购/物流凭证；缺失凭证需要人工补充。
Required Accountant Confirmation / 需要会计确认：附件是否满足入账和税务留存要求、凭证金额是否和做账金额一致。
```

建议列：

```text
Document Type / 凭证类型
Period / 期间
Document Name / 文件名
Source System / 来源系统
Source Reference / 来源引用
Related Amount Original / 相关原币金额
Currency / 币种
Related Amount CNY / 相关人民币金额
Provided to Accountant / 是否已提供给会计
Required for Booking / 是否做账必需
Required for Tax Filing / 是否报税必需
Status / 状态
Owner / 负责人
Notes / 说明
```

建议凭证类型：

```text
Amazon Settlement Flat File V2 / 亚马逊结算明细
Amazon Payments Statement / 亚马逊付款报表
Amazon Seller Fee Invoice / 亚马逊服务费发票
Amazon Advertising Invoice or Statement / 亚马逊广告费账单
WorldFirst Payout Statement / 万里汇到账流水
Bank Statement / 银行流水
Supplier Purchase Invoice / 供应商采购发票
First-Mile Freight Invoice / 头程物流发票
Customs or Duty Document / 清关或关税文件
SKU Cost Sheet / SKU成本表
Manual Adjustment Support / 手工调整依据
```

### 13.18 `14_Payout_Recon`

Amazon 结算与万里汇/银行到账核对表。该 sheet 用于把 Amazon Settlement net 与实际收款账户到账金额勾稽，帮助会计判断应收、回款、手续费和汇兑差异。

Sheet 顶部说明区建议内容：

```text
Sheet Purpose / 本表用途：核对 Amazon Settlement 净额与万里汇/银行实际到账，帮助会计确认应收账款、其他货币资金、银行存款和汇兑损益。
How to Use / 使用方式：运营或会计填入实际到账流水，系统计算与 Amazon settlement net 的差异，并标记是否为手续费、汇率差、跨月未到账或待查差异。
Main Data Sources / 主要数据来源：Amazon Settlement、Amazon Payments、WorldFirst/银行流水、12_FX_Rates。
Accounting Caveats / 会计注意事项：Amazon settlement 日期、付款日期、万里汇到账日期和银行入账日期可能跨月；差异不一定是错误，需按会计政策处理。
Required Accountant Confirmation / 需要会计确认：回款日期、到账账户、手续费、汇率、汇兑损益、跨月应收余额。
```

建议列：

```text
Settlement ID / 结算单ID
Settlement Period / 结算期间
Amazon Net Amount / 亚马逊净结算金额
Amazon Currency / 亚马逊币种
Expected Payout Date / 预计打款日期
Payout Account / 到账账户
Actual Received Amount / 实际到账金额
Received Currency / 到账币种
Bank or WorldFirst Fee / 银行或万里汇手续费
FX Rate / 汇率
Received Amount CNY / 到账人民币金额
Difference Original / 原币差异
Difference CNY / 人民币差异
Difference Reason / 差异原因
Reconciliation Status / 核对状态
Accountant Confirmation / 会计确认
Notes / 说明
```

`Difference Reason / 差异原因` 示例：

```text
No Difference / 无差异
Bank or Platform Fee / 银行或平台手续费
FX Difference / 汇兑差异
Timing Difference / 跨月时间差
Partial Payout / 部分到账
Pending Payout / 尚未到账
Needs Investigation / 需排查
```

### 13.19 `15_Adjustments`

会计手工调整表。该 sheet 用于保留系统无法自动判断但会计必须处理的事项，例如采购发票差异、头程物流分摊、库存成本调整、银行手续费、汇兑损益、税务调整和非 Amazon 费用。

Sheet 顶部说明区建议内容：

```text
Sheet Purpose / 本表用途：记录会计对系统月报的手工调整，保证最终入账口径与管理口径差异可追溯。
How to Use / 使用方式：会计逐项填写调整原因、金额、科目、附件和确认状态；季度汇总时将已确认调整纳入季度 rollup。
Main Data Sources / 主要数据来源：会计账簿、发票、银行流水、库存记录、采购付款记录、税务调整底稿。
Accounting Caveats / 会计注意事项：系统不会自动判断所有税务和会计调整；所有手工调整必须保留原因和附件，避免后续无法追溯。
Required Accountant Confirmation / 需要会计确认：调整金额、科目、汇率、附件、是否影响当月或跨月、是否影响季度申报。
```

建议列：

```text
Adjustment ID / 调整ID
Adjustment Type / 调整类型
Accounting Item / 会计项目
Suggested Account / 建议会计科目
Debit or Credit / 借贷方向
Currency / 币种
Amount Original / 原币金额
FX Rate / 汇率
Amount CNY / 人民币金额
Affects Month / 影响月份
Affects Quarter / 影响季度
Reason / 调整原因
Source Document ID / 来源凭证ID
Accountant Confirmation / 会计确认
Status / 状态
Notes / 说明
```

`Adjustment Type / 调整类型` 示例：

```text
Purchase Invoice Adjustment / 采购发票调整
Inventory Cost Adjustment / 库存成本调整
First-Mile Freight Allocation / 头程物流分摊
Bank Fee / 银行手续费
FX Gain or Loss / 汇兑损益
Tax Adjustment / 税务调整
Non-Amazon Expense / 非Amazon费用
Prior Period Adjustment / 前期调整
Other / 其他
```

---

## 14. 数据质量与状态规则

### 14.1 Report status

| status | 条件 |
|---|---|
| `ok` | Settlement rows > 0；无 missing cost；无 currency mismatch；unknown/unclassified 非重大或为 0；核心 self-check 通过；coverage 通过人工或审计确认。 |
| `needs_review` | 有 settlement rows，但存在 missing cost、currency mismatch、unknown bucket/category、税费透传差异、异常大 reconciliation diff、statement coverage 不确定等。 |
| `no_data` | 本月没有 settlement rows。 |

### 14.2 必须阻塞正式月报的情况

- `settlement_row_count = 0`。
- `missing_cost_skus` 非空。
- `currency_mismatch_skus` 非空。
- `unknown_bucket_amount != 0` 或 `unclassified_amount != 0` 且无法解释。
- `product_sales_units > 0` 但 `internal_cogs = 0`。
- `tax_passthrough` 绝对值明显不为 0，且不能解释。

### 14.3 可以警告但不阻塞的情况

- Ads API spend 与 Settlement advertising fee 不一致，但差异未达到 `needs_review` 阈值。
- Sales & Traffic ordered sales 与 Settlement product sales 不一致。
- Promotion/Coupon performance 与 Settlement promotion cost 不一致。
- FBA Reimbursement report 与 Settlement reimbursement 不一致。
- 最近月份 settlement 未完整关闭；例如当月仍有 `Present` statement。

---

## 15. Reconciliation checks

### 15.1 Settlement self-check

```text
settlement_net_amount = SUM(all filtered settlement amount)
```

并验证：

```text
SUM(profit_bucket totals) == settlement_net_amount
SUM(amount_category totals) == settlement_net_amount
```

允许 0.01 以内 rounding 差异。

### 15.2 Tax passthrough check

```text
tax_passthrough_check = sales_tax + marketplace_facilitator_tax
```

预期通常接近 0。

### 15.3 Product sales vs operational sales

```text
settlement_product_sales = product_sales + liquidation_revenue
ops_ordered_product_sales = SUM(sales_traffic_daily.ordered_product_sales_amount)
diff = settlement_product_sales - ops_ordered_product_sales
diff_pct = diff / ops_ordered_product_sales
```

只解释，不强制一致。

### 15.4 Settlement ads vs Ads API spend

```text
settlement_ads_fee_abs = ABS(bucket_totals['advertising_cost'])
ads_api_spend = SUM(amazon_ads_sp_campaign_daily.cost)
diff = settlement_ads_fee_abs - ads_api_spend
diff_pct = diff / ads_api_spend
```

只解释，不强制一致。差异同时进入 `03_Ads_Timing_Recon`。若 `settlement_ads_fee_abs != 0` 且 Ads API campaign daily
在指定月份/profile 下 `ads_row_count = 0`、`ads_api_spend = 0`，输出
`ads_api_context_missing` warning，提示需要检查 Ads backfill/ingestion 覆盖。若差异超过 v1.2 阈值，输出 `ads_timing_needs_review`。

### 15.5 SKU cost coverage

```text
sku_cost_coverage_rate = count(product-sales SKUs with valid cost) / count(product-sales SKUs)
```

正式月报要求 100%。

---

## 16. 示例 2026-03 / 2026-04 应输出的关键指标

当前项目已有 profit preview 样例，v1 实现后应至少能重现这些主指标。

### 16.1 2026-03

| 指标 | 当前样例值 |
|---|---:|
| Settlement net | 2015.42 |
| Product sales amount | 7843.43 |
| Product sales units | 353 |
| Internal COGS | 1477.55 |
| Estimated operating profit | 537.87 |
| Advertising cost | -2903.93 |
| FBA fee | -1500.22 |
| Refund | -1192.09 |
| Promotion cost | -220.07 |
| Promotion fee | -72.11 |
| Reimbursement | 62.96 |

### 16.2 2026-04

| 指标 | 当前样例值 |
|---|---:|
| Settlement net | 1853.15 |
| Product sales amount | 6241.84 |
| Product sales units | 258 |
| Internal COGS | 1075.86 |
| Estimated operating profit | 777.29 |
| Advertising cost | -2003.85 |
| FBA fee | -1135.83 |
| Refund | -537.65 |
| Promotion cost | -315.27 |
| Promotion fee | -166.17 |
| Reimbursement | 101.28 |

---

## 17. Implementation design

### 17.1 CLI

新增脚本：

```powershell
python scripts/generate_monthly_financial_close_report.py --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --month 2026-03 --dry-run
```

可选参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--marketplace-id` | 必填 | Marketplace。 |
| `--month` | 必填 | `YYYY-MM`。 |
| `--profile-id` | 可选但推荐 | Ads profile；如果省略，Ads API 运营指标可跳过或按 marketplace 粗略汇总并 warning。 |
| `--output-root` | `runtime/analysis_reports/monthly_financial_close` | 输出目录。 |
| `--dry-run` | false flag | 本功能 v1 不写数据库；`--dry-run` 表示只读数据库、不执行任何外部副作用，但仍生成 JSON/XLSX 文件，方便人工复核。 |
| `--no-write-files` | false | 可选调试参数；只打印 summary，不写 JSON/XLSX。 |
| `--export-csv` | false | 可选调试参数；额外导出拆分 CSV，不作为默认交付。 |
| `--allow-needs-review` | false | 若 status=needs_review，是否仍允许后续非本脚本流程使用该结果；本脚本本身仍应输出文件供复核。 |

### 17.2 建议代码结构

```text
scripts/generate_monthly_financial_close_report.py
src/seller_data_pipeline/services/monthly_financial_close_service.py
src/seller_data_pipeline/services/monthly_accountant_pack.py
src/seller_data_pipeline/db/repositories/monthly_financial_close_repo.py
tests/unit/services/test_monthly_financial_close_service.py
tests/unit/db/test_monthly_financial_close_repo.py
```

### 17.3 Repository methods

建议 repo 提供：

```python
fetch_settlement_rows(marketplace_id, start_date, end_date)
fetch_sku_cost_rows(marketplace_id, start_date, end_date)
fetch_sales_traffic_summary(marketplace_id, start_date, end_date)
fetch_orders_summary(marketplace_id, start_date, end_date)
fetch_ads_campaign_summary(marketplace_id, profile_id, start_date, end_date)
fetch_promotion_coupon_summary(marketplace_id, start_date, end_date)
fetch_fba_reimbursement_summary(marketplace_id, start_date, end_date)
```

### 17.4 Service calculation steps

```text
1. Parse month -> start_date/end_date.
2. Fetch settlement rows.
3. Exclude settlement summary rows.
4. Build settlement bucket totals and amount category totals.
5. Compute settlement net.
6. Build SKU accumulator from product_sales/liquidation_revenue rows.
7. Fetch and match SKU costs.
8. Compute SKU COGS and SKU estimated profit.
9. Fetch operational context.
10. Compute KPIs and ratios.
11. Run reconciliation checks.
12. Determine status and warnings.
13. Build MonthlyFinancialCloseResult.
14. Write monthly_financial_close_{YYYY-MM}.json.
15. Write monthly_financial_close_{YYYY-MM}.xlsx.
16. If --export-csv is passed, optionally write split CSV files for debugging only.
```

### 17.5 XLSX writer

v1 推荐使用 `openpyxl`，原因：

```text
已有 SKU 成本模板导出/导入使用 xlsx 工作流。
单文件多 sheet 更适合人工复核。
无需引入复杂 BI 或 PDF 依赖。
```

XLSX 只做轻量格式化，不在 v1 做复杂图表：

```text
冻结首行
基础列宽
数字保留 2 位
百分比保留 2 位
status/warning 用文本字段表达，不依赖颜色表达业务含义
```

---

## 18. Acceptance criteria

### 18.1 Unit tests

必须覆盖：

- 月份解析：闰年、月末日期。
- Settlement net 汇总。
- bucket/category 汇总与 settlement net 一致。
- SKU 件数去重。
- SKU 成本匹配。
- missing cost -> `needs_review`。
- currency mismatch -> `needs_review`。
- no settlement rows -> `no_data`。
- Ads / Sales & Traffic / Orders 指标公式。
- 0 分母时 ratio 输出 null 或 `None`，不得报错。
- JSON 输出结构包含必填字段。
- v1 XLSX 输出包含 8 个核心 sheet。
- v1.1 Accountant Bookkeeping Pack 输出包含 7 个会计辅助 sheet，且每个会计 sheet 包含中文优先说明区和双语固定列名。

### 18.2 数据验收

以本项目当前数据，至少验证：

```powershell
python scripts/generate_monthly_financial_close_report.py --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --month 2026-03 --dry-run
python scripts/generate_monthly_financial_close_report.py --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --month 2026-04 --dry-run
```

应输出：

```text
runtime/analysis_reports/monthly_financial_close/ATVPDKIKX0DER/2026-03/monthly_financial_close_2026-03.json
runtime/analysis_reports/monthly_financial_close/ATVPDKIKX0DER/2026-03/monthly_financial_close_2026-03.xlsx
runtime/analysis_reports/monthly_financial_close/ATVPDKIKX0DER/2026-04/monthly_financial_close_2026-04.json
runtime/analysis_reports/monthly_financial_close/ATVPDKIKX0DER/2026-04/monthly_financial_close_2026-04.xlsx
```

应满足：

| 月份 | 预期状态 | 关键验收 |
|---|---|---|
| 2026-03 | `ok` 或仅非阻塞 warning | settlement net = 2015.42；estimated profit = 537.87。 |
| 2026-04 | `ok` 或仅非阻塞 warning | settlement net = 1853.15；estimated profit = 777.29。 |

### 18.3 命令验收

代码实现阶段必须通过：

```powershell
ruff check src tests scripts
PYTHONPATH=src pytest tests/unit -q
python -m compileall -q scripts src tests
```

文档更新阶段不要求运行以上代码校验。

---

## 19. 已知不确定点与处理

| 不确定点 | 当前处理 |
|---|---|
| 旧月份 statement 是否全部下载 | v1 输出 coverage / statement warning；人工确认 All Statements。 |
| Monthly Transaction CSV 与 Settlement Flat File V2 差异 | v1 不使用 Monthly Transaction CSV 作为主源；仅作为人工对账参考。 |
| Ads API spend 与 Settlement advertising fee 不一致 | 并列展示，并通过 Management P&L + Ads Timing Recon 解释；不覆盖 Settlement-led 财务口径。 |
| Promotion/Coupon 跨月活动如何分摊 | v1 不精确分摊，仅展示与月份重叠的活动概览；财务实扣以 Settlement 为主。 |
| 多成本批次同月切换 | 设计上应按 posted_date 匹配；若实现第一版简化，需要强制 warning。 |
| 成本币种与 Settlement 币种不一致 | 阻塞正式月报，要求先在 `amazon_sku_cost` 中换算成财务币种。 |
| liquidation SKU 是否当作销售件数 | v1 纳入 product-sales-like 收入与 COGS，但在 SKU notes 标记 liquidation。 |
| 股东是否需要 Markdown | 当前不需要；后续 PDF/Email 从 JSON 生成，XLSX 作为附件或复核表。 |

---

## 20. 后续扩展

v1 稳定后再考虑：

1. 实现 v1.2 Management P&L 与 Ads Timing Reconciliation 代码。
2. 基于 JSON 生成 CEO 版一页 PDF 摘要。
3. 基于 JSON 生成股东邮件正文和附件包。
4. 增加 `--export-csv` 调试导出。
5. 新增 `management_report_run` / `monthly_financial_close_result` 结果表。
6. 与 `run_manual_refresh_plan.py` 串联为月度 close workflow。
7. 多 marketplace / 多币种合并报表。
8. 增加图表 sheet 或 PDF 图表页。

---

## 21. 与后续两类报表的关系

本功能是月度最终财务口径。后续两个报表不应重复定义财务净利润口径：

| 后续报表 | 与本报表关系 |
|---|---|
| Weekly Business Review | 使用更及时的运营发生口径和 Ads API report-date spend，指导每周运营；不替代月度财务 close。 |
| Weekly Ads Optimization Report | 深入广告词、campaign、targeting、search term、advertised product 维度分析，输出否词/加词/调价/观察动作清单；财务广告费对账仍回到本报表的 Settlement advertising cost。 |

---

## 22. 设计变更记录

| 日期 | 变更 | 原因 |
|---|---|---|
| 2026-05-21 | 初版 Monthly Financial Close Report 设计冻结，默认输出 Markdown / JSON / CSV，Excel 放 v1.1。 | 先完成指标、字段和公式级设计。 |
| 2026-05-22 | 调整 v1 默认输出为 JSON + 单个 XLSX 多 sheet；取消默认 Markdown 和多个 CSV。 | 股东/会计不会使用 Markdown；多个 CSV 太碎；JSON 更适合作为后续 PDF/Email 的结构化源，XLSX 更适合人工复核。 |
| 2026-05-23 | 增加 Ads API context 缺失 warning、console reconciliation 计数、SKU Profit scope note。 | 真实 2026-03 / 2026-04 复核发现 Ads campaign daily 仅覆盖 2026-05-06 起，需避免把运营解释数据缺失误读为财务利润异常；同时避免将 SKU 表误读为最终公司利润。 |
| 2026-05-30 | 增加并实现 v1.1 Accountant Bookkeeping Pack，新增 7 个会计辅助 sheet，并要求会计 sheet 顶部中文说明和双语列名。 | 让会计每月更容易基于月报做账、季度汇总和税务申报准备，减少人工拆分 Amazon 结算单和反复解释口径。 |
| 2026-06-01 | 增加并实现 v1.2 双利润口径：Settlement-led Estimated Profit + Management Estimated Profit with Report-date Ads；新增 `02_Management_PnL` 与 `03_Ads_Timing_Recon`。 | 解决广告费按账单 posted-date 集中入账导致 Amazon Finance 表面盈利但经营利润被高估的问题。 |
| 2026-08-09 | v1.87 / report v1.3：Management Operating Profit 升为首页主指标；拆分 Product / First-Mile / Packaging / Other Unit COGS；邮件 subject 改用 Operating Profit；保留 legacy JSON 字段兼容。 | 生产复核确认此前月报货本未包含头程，且 Settlement-led legacy alias 容易被误读为真正经营利润。 |
---

## 18. v1 / v1.1 / v1.2 代码实现记录

> 更新时间：2026-08-08  
> 实现状态：v1 JSON/XLSX + v1.1 Accountant Bookkeeping Pack + v1.2 双利润口径/Ads Timing Reconciliation 已实现；本地 unit tests / compileall 通过；待真实 Azure SQL 周期按新口径重新生成并人工复核。

### 18.1 新增代码路径

```text
scripts/generate_monthly_financial_close_report.py
src/seller_data_pipeline/db/repositories/monthly_financial_close_repo.py
src/seller_data_pipeline/services/monthly_financial_close_service.py
src/seller_data_pipeline/services/monthly_accountant_pack.py
tests/unit/db/test_monthly_financial_close_repo.py
tests/unit/services/test_monthly_financial_close_service.py
```

### 18.2 CLI

```powershell
python scripts/generate_monthly_financial_close_report.py --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --month 2026-03 --dry-run
python scripts/generate_monthly_financial_close_report.py --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --month 2026-04 --dry-run
```

`--dry-run` 语义保持为：只读数据库、不写入数据库或外部系统，但仍生成 JSON/XLSX 文件供人工复核。

### 18.3 默认输出

```text
runtime/analysis_reports/monthly_financial_close/{marketplace_id}/{YYYY-MM}/monthly_financial_close_{YYYY-MM}.json
runtime/analysis_reports/monthly_financial_close/{marketplace_id}/{YYYY-MM}/monthly_financial_close_{YYYY-MM}.xlsx
```

### 18.4 实现说明

- Settlement rows、SKU cost rows 和 Orders / Sales & Traffic / Ads / Coupon / Promotion / FBA Reimbursements context 均通过只读 repo 查询。
- Ads context 支持 `profile_id` 过滤，避免未来多 profile 混算。
- SKU COGS 已按 product-sales unit 的 posted_date 匹配 `amazon_sku_cost.effective_from/effective_to`。如果同一 SKU 月内匹配多条成本，会按件计算 COGS，并在 SKU notes 中说明展示的是 weighted average unit cost。
- 缺 SKU 成本或成本币种不匹配会将 report status 标为 `needs_review`，不会默认为 0 成本后静默通过。
- v1 不新增数据库表，不新增 migration，不生成 Markdown，不默认输出多个 CSV。
- v1.1 Accountant Bookkeeping Pack 不新增数据库表；在原 JSON/XLSX 月报中新增 `accountant_pack` JSON 节点和 `09_Accounting_Summary` 至 `15_Adjustments` 七张会计辅助 sheet。
- v1.2 在 `MonthlyFinancialSummary` 中新增 `settlement_led_estimated_profit`、`management_estimated_profit_report_date_ads`、`settlement_advertising_fee_abs`、`ads_api_report_date_spend`、`ads_timing_difference` 等字段；XLSX 新增 `02_Management_PnL` 和 `03_Ads_Timing_Recon`。
- 会计辅助 sheet 顶部包含中文优先说明区，列名全部为 English / 中文 双语格式，并保留会计确认、汇率、凭证、附件和调整项字段。

### 18.5 本地验证

```powershell
PYTHONPATH=src pytest tests/unit -q
python -m compileall -q scripts src tests
```

当前容器验证结果：

```text
PYTHONPATH=src pytest tests/unit -q  -> 301 passed
python -m compileall -q scripts src tests -> passed
```

`ruff check src tests scripts` 在当前容器中无法执行，因为该环境未安装 `ruff` 命令/模块；代码已按项目 `line-length=100` 做了人工检查，用户本地或 CI 仍应运行正式 ruff。


---

## Presentation language requirement

Default presentation artifacts must be bilingual:

```text
1. JSON keeps stable machine-readable English field names.
2. XLSX includes `00_Readme_说明` and bilingual fixed headers/labels. Accountant sheets must use bilingual column names and Chinese-first usage notes at the top of each sheet.
3. Report delivery emails are Chinese-first with English reference text.
4. Amazon-native raw values such as campaign names, search terms, keywords, SKU/ASIN and raw IDs stay unchanged.
```


### v1.83 Ads timing send-guard correction

`settlement_ads_fee_vs_ads_api_spend` 比较 posted-date Settlement 与 report-date Ads API，属于时间口径 reconciliation。大差异继续展示为 warning，但不再仅凭该差异把 Monthly Financial Close 升级为 `needs_review`；Settlement self-check、未知金额、成本缺失/币种冲突等真实财务完整性问题仍可阻断发送。


## 23. v1.87 Landed COGS / Executive P&L 实现记录

> 日期：2026-08-09  
> 状态：本地实现完成，待 Azure 成本补录与 2026-05/06/07 preview 验收。

本轮不新增 migration，复用 `amazon_sku_cost.first_mile_cost`。代码已：

- 将 `MonthlyFinancialSummary` 增加 `product_cost_cogs`、`first_mile_cogs`、`packaging_cogs`、`other_unit_cogs`。
- JSON 增加 `landed_cogs`、`management_operating_profit`、`management_operating_margin`、`settlement_close_profit` alias，同时保留旧字段。
- `06_SKU_Profit` 增加单位成本与 COGS component breakdown。
- `01_Summary` 以 Management Operating Profit / Margin 为经营主指标，并增加成本覆盖、头程是否计入、unknown classification、bank payout 状态。
- `02_Management_PnL` 展开 Settlement bucket detail、Ads report-date replacement、到岸成本组件和最终经营利润。
- 邮件标题从 legacy Settlement-led `Profit` 改为 `Operating Profit`，正文优先使用 management profit 和 landed COGS。
- Settlement-led profit 保留为 `Settlement Close Profit`，继续服务会计/月结解释。

当前本地全量测试：`337 passed`；compileall 成功。

## 2.3 v1.5 / v1.90 Natural-Month Management P&L

Management P&L 已从 Settlement posted-date operating rows 切换为 `amazon_finance_transaction` 的 marketplace-local natural-month ledger。Amazon US 使用 `America/Los_Angeles`。Ads 仍使用 Ads API report-date spend；Finances `ProductAdsPayment` 只作 posted-charge reconciliation reference。Settlement Close Profit 保留为独立 accounting/close reference。详细 lifecycle policy、migration 016 与三个月 live reconciliation 证据见 `feature_finances_api_natural_month_ledger.md`。
