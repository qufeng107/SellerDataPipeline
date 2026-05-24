# Feature: Monthly Financial Close Report

> 文档状态：Design frozen / ready for implementation  
> 负责人：AI + Feng  
> 更新时间：2026-05-22  
> 功能状态：Implemented / pending live Azure SQL verification  
> 设计版本：v1.0-json-xlsx-output  
> 相关数据接入文档：`docs/data_access/sp_api_reports_catalog.md`, `docs/data_access/amazon_ads_reports_catalog.md`, `docs/data_access/seller_central_manual_exports.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`  
> 相关功能：`docs/features/feature_profit_calculation.md`, `docs/features/feature_sku_cost_management.md`, `docs/operations/manual_refresh_plan_workflow.md`, `docs/operations/historical_backfill_workflow.md`  
> 相关 ADR：`docs/adr/ADR-009-settlement-led-profit-policy.md`, `docs/adr/ADR-010-overlapping-refresh-weekly-analysis.md`

---

## 1. 功能摘要

Monthly Financial Close Report（月度财务结算报表）是 SellerDataPipeline 第一类管理层数据加工报表，定位为小公司版 CFO / CEO 月度经营结果包。它回答一个核心问题：

```text
这个月在 Amazon 美国站，按 Amazon 实际 Settlement 财务结算口径和内部 SKU 标准成本，公司估算赚了多少钱？
```

本功能基于已冻结的 `Settlement-led Financial Profit v1.0` 口径：

```text
Amazon 财务金额以 Settlement / Payments / Flat File V2 入库后的 amazon_settlement_transaction 为主。
内部商品成本以 amazon_sku_cost 为主。
Orders / Sales & Traffic / Ads / Promotion / Coupon / FBA Reimbursements 用于运营解释、交叉校验和辅助指标，不反向覆盖财务主口径。
```

v1 不新增数据库结果表，不自动发送邮件，不生成正式 PDF；先输出文件型月结结果，供人工复核、会计沟通、股东/管理层月度回顾使用。

---

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认：先做 Monthly Financial Close Report，再做 Weekly Business Review 和 Weekly Ads Optimization Report。 |
| 口径依赖 | 已冻结：Settlement-led Financial Profit v1.0。 |
| 数据源可用性 | 足够支持 v1：Settlement、SKU Cost、Sales & Traffic、Orders、Ads、Promotion/Coupon、Reimbursements 均已入库并验证过。 |
| 设计状态 | 本文冻结 v1 设计到指标、字段、公式、输出文件和 XLSX sheet 级别。 |
| 数据库变更 | v1 不新增数据库表，不新增 migration。 |
| 代码实现 | 已实现 v1：新增 service / repo / CLI / unit tests；待真实 Azure SQL 跑 2026-03、2026-04 人工复核。 |
| 默认输出形式 | `monthly_financial_close_{YYYY-MM}.json` + `monthly_financial_close_{YYYY-MM}.xlsx`。已由 CLI 默认生成。 |
| 不再默认输出 | 不默认输出 Markdown；不默认输出多个 CSV。 |
| 验收样本 | 先以 `2026-03`、`2026-04` 为主，因为 Settlement 和 SKU 成本当前最完整。 |

---

## 3. 业务目标

### 3.1 CEO / CFO 视角目标

1. **月度结论清晰**：一眼看到本月商品销售、Settlement net、内部 COGS、估算经营利润、利润率和报表状态。
2. **费用结构可解释**：知道广告费、FBA 费、Referral fee、促销、退款、仓储费、赔偿分别影响多少。
3. **SKU 贡献可判断**：看出哪些 SKU 贡献利润，哪些 SKU 虽有销量但被广告、退款或费用吃掉利润。
4. **能和 Amazon 后台对账**：Settlement net 应能回溯到 Flat File V2 / Payments Date Range / All Statements。
5. **能给会计使用**：输出清晰的 Amazon 侧费用结构和内部成本，不替代正式会计报表，但可作为会计解释材料。
6. **能给股东/管理层复核**：XLSX 方便查看和归档；JSON 方便后续生成邮件、PDF 或 Dashboard。
7. **能指导经营决策**：识别广告费率、退款率、促销成本、SKU 盈亏和数据质量风险。

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
- 输出月度 estimated operating profit。
- 输出 SKU 利润贡献、销售贡献和异常 SKU。
- 输出费用结构分析。
- 输出运营解释指标：Sales & Traffic、Orders、Ads API、Promotion/Coupon、FBA Reimbursements。
- 输出对账和数据完整性检查。
- 输出人工复核 notes / warnings。
- 输出一个结构化 JSON 和一个多 sheet XLSX。

### 4.2 本功能不包含

- 不做 FIFO、移动加权、批次库存成本。
- 不把 Orders 金额当作财务收入主口径。
- 不把 Ads API spend 当作最终财务广告费主口径。
- 不把 Promotion/Coupon performance 报表的预算或销售额当作财务促销实扣主口径。
- 不用 Monthly Transaction CSV 全表 `total` 合计替代 Settlement，因为其中可能包含 Transfer / disbursement 行。
- 不自动判断所有历史 statement 是否已经存在；v1 只做 coverage / status / warnings，最终仍需人工复核。
- 不新增结果表；连续几期稳定后再考虑落库。
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

v1 月度财务报表使用 Ads 数据解释投放效率，但财务广告费主口径仍来自 Settlement bucket `advertising_cost` / category `advertising_fee`。

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
settlement_advertising_fee = ABS(SUM(amount WHERE profit_bucket='advertising_cost'))
ads_api_spend = SUM(amazon_ads_sp_campaign_daily.cost)
ads_spend_diff = settlement_advertising_fee - ads_api_spend
```

不要求两者完全一致，因为 Settlement 是扣费/财务 posted-date 口径，Ads API 是广告 report date/归因口径。

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

展示规则：

```text
Ads API spend 是运营投放效率指标。
Settlement Ads Fee 是财务实际扣费指标。
两者并列展示，差异作为 reconciliation note，不互相覆盖。
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

默认 sheets：

```text
01_Summary
02_Settlement_Buckets
03_Amount_Categories
04_SKU_Profit
05_Operational_Context
06_Reconciliation_Checks
07_Warnings
08_Raw_Metadata
```

Sheet 名保持短、稳定、英文，避免 Excel 兼容问题。

### 13.2 `01_Summary`

给 CEO / 股东 / 会计第一眼看。

建议列：

```text
metric_group
metric_name
value
currency
period
status
notes
```

建议包含：

```text
Report Status
Settlement Row Count
Settlement Net Amount
Product Sales Amount
Product Sales Units
Internal COGS
Estimated Operating Profit
Profit Margin on Product Sales
Settlement Net Margin
COGS Ratio
Amazon Fee Burden
Advertising Cost
FBA Fees
Refunds
Promotion Cost
Promotion Fee
Reimbursements
```

### 13.3 `02_Settlement_Buckets`

按 `profit_bucket` 展示费用大类。

建议列：

```text
profit_bucket
amount
absolute_amount
currency
pct_of_product_sales
pct_of_settlement_net
row_count
notes
```

### 13.4 `03_Amount_Categories`

按 `amount_category` 展示更细的 Amazon amount category。

建议列：

```text
amount_category
profit_bucket
amount
absolute_amount
currency
pct_of_product_sales
row_count
notes
```

### 13.5 `04_SKU_Profit`

SKU 盈亏核心表。

建议列：

```text
seller_sku
units
product_sales_amount
settlement_net_amount
unit_standard_cost
internal_cogs
sku_estimated_profit_after_cogs
sku_profit_margin
sku_revenue_share
sku_profit_share
currency
status
notes
scope_note
```

`scope_note` 必须说明：SKU 利润表是 SKU 归属收入、退款、SKU 层费用与内部 COGS
的分析视角，未分摊广告费、订阅费、coupon fee、仓储费等账号级费用或非 SKU
Settlement 行。因此 SKU 表合计不应被解释为公司最终月度经营利润。

### 13.6 `05_Operational_Context`

运营解释指标，用于解释财务结果。

建议列：

```text
metric_group
metric_name
value
currency
source
period_basis
notes
```

`metric_group` 示例：

```text
sales_traffic
orders
ads_api
promotion_coupon
fba_reimbursement
```

### 13.7 `06_Reconciliation_Checks`

对账和质量检查。

建议列：

```text
check_name
status
severity
expected
actual
diff
diff_pct
message
```

### 13.8 `07_Warnings`

所有需要人工看的问题。

建议列：

```text
warning_code
severity
message
related_sku
related_source
```

### 13.9 `08_Raw_Metadata`

方便追溯。

建议列：

```text
key
value
notes
```

建议包含：

```text
report_type
version
marketplace_id
profile_id
month
period_start
period_end
generated_at
source_tables
row_counts
output_files
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

- Ads API spend 与 Settlement advertising fee 不一致。
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

只解释，不强制一致。若 `settlement_ads_fee_abs != 0` 且 Ads API campaign daily
在指定月份/profile 下 `ads_row_count = 0`、`ads_api_spend = 0`，输出
`ads_api_context_missing` warning，提示需要检查 Ads backfill/ingestion 覆盖。

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
- XLSX 输出包含 8 个默认 sheet。

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
| Ads API spend 与 Settlement advertising fee 不一致 | 并列展示，不互相覆盖。 |
| Promotion/Coupon 跨月活动如何分摊 | v1 不精确分摊，仅展示与月份重叠的活动概览；财务实扣以 Settlement 为主。 |
| 多成本批次同月切换 | 设计上应按 posted_date 匹配；若实现第一版简化，需要强制 warning。 |
| 成本币种与 Settlement 币种不一致 | 阻塞正式月报，要求先在 `amazon_sku_cost` 中换算成财务币种。 |
| liquidation SKU 是否当作销售件数 | v1 纳入 product-sales-like 收入与 COGS，但在 SKU notes 标记 liquidation。 |
| 股东是否需要 Markdown | 当前不需要；后续 PDF/Email 从 JSON 生成，XLSX 作为附件或复核表。 |

---

## 20. 后续扩展

v1 稳定后再考虑：

1. 基于 JSON 生成 CEO 版一页 PDF 摘要。
2. 基于 JSON 生成股东邮件正文和附件包。
3. 生成会计版费用明细包。
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
| Weekly Business Review | 使用更及时的运营口径和 preview 数据，指导每周运营；不替代月度财务 close。 |
| Weekly Ads Optimization Report | 深入广告词、campaign、targeting、search term、advertised product 维度分析，输出否词/加词/调价/观察动作清单；财务广告费对账仍回到本报表的 Settlement advertising cost。 |

---

## 22. 设计变更记录

| 日期 | 变更 | 原因 |
|---|---|---|
| 2026-05-21 | 初版 Monthly Financial Close Report 设计冻结，默认输出 Markdown / JSON / CSV，Excel 放 v1.1。 | 先完成指标、字段和公式级设计。 |
| 2026-05-22 | 调整 v1 默认输出为 JSON + 单个 XLSX 多 sheet；取消默认 Markdown 和多个 CSV。 | 股东/会计不会使用 Markdown；多个 CSV 太碎；JSON 更适合作为后续 PDF/Email 的结构化源，XLSX 更适合人工复核。 |
| 2026-05-23 | 增加 Ads API context 缺失 warning、console reconciliation 计数、SKU Profit scope note。 | 真实 2026-03 / 2026-04 复核发现 Ads campaign daily 仅覆盖 2026-05-06 起，需避免把运营解释数据缺失误读为财务利润异常；同时避免将 SKU 表误读为最终公司利润。 |
---

## 18. v1 代码实现记录

> 更新时间：2026-05-23  
> 实现状态：本地 unit tests / compileall 通过；真实 Azure SQL 2026-03 / 2026-04 已生成并初步复核。

### 18.1 新增代码路径

```text
scripts/generate_monthly_financial_close_report.py
src/seller_data_pipeline/db/repositories/monthly_financial_close_repo.py
src/seller_data_pipeline/services/monthly_financial_close_service.py
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

### 18.5 本地验证

```powershell
PYTHONPATH=src pytest tests/unit -q
python -m compileall -q scripts src tests
```

当前容器验证结果：

```text
PYTHONPATH=src pytest tests/unit -q  -> 238 passed
python -m compileall -q scripts src tests -> passed
```

`ruff check src tests scripts` 在当前容器中无法执行，因为该环境未安装 `ruff` 命令/模块；代码已按项目 `line-length=100` 做了人工检查，用户本地或 CI 仍应运行正式 ruff。


---

## Presentation language requirement

Default presentation artifacts must be bilingual:

```text
1. JSON keeps stable machine-readable English field names.
2. XLSX includes `00_Readme_说明` and bilingual fixed headers/labels.
3. Report delivery emails are Chinese-first with English reference text.
4. Amazon-native raw values such as campaign names, search terms, keywords, SKU/ASIN and raw IDs stay unchanged.
```
