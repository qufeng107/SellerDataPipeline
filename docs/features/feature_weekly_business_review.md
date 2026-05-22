# Feature: Weekly Business Review

> 文档状态：Design frozen / ready for implementation  
> 负责人：AI + Feng  
> 更新时间：2026-05-21  
> 功能状态：Design only  
> 相关数据接入文档：`docs/data_access/sp_api_reports_catalog.md`, `docs/data_access/amazon_ads_reports_catalog.md`, `docs/data_access/seller_central_manual_exports.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`  
> 相关功能：`docs/features/feature_monthly_financial_close_report.md`, `docs/features/feature_profit_calculation.md`, `docs/features/feature_sku_cost_management.md`, `docs/operations/manual_refresh_plan_workflow.md`, `docs/operations/data_refresh_policy.md`  
> 相关 ADR：`docs/adr/ADR-009-settlement-led-profit-policy.md`, `docs/adr/ADR-010-overlapping-refresh-weekly-analysis.md`

---

## 1. 功能摘要

Weekly Business Review（每周经营周报，简称 WBR）是 SellerDataPipeline 第二类管理层报表，定位为小公司版 CEO / 运营负责人每周经营复盘包。它回答的核心问题不是“这周最终入账多少钱”，而是：

```text
这一周业务有没有变好？
增长来自哪里？
利润是否被广告、促销、退款或库存问题吃掉？
下周运营应该优先做什么？
```

WBR 的特点是：

```text
比 Monthly Financial Close Report 更快；
比广告优化报表更全局；
不追求财务最终定账；
追求稳定、及时、可指导运营动作。
```

第一版 WBR 不新增数据库结果表，不自动发送邮件，不替代月度财务结算报表。它读取已经入库的 normalized 表，输出 Markdown / JSON / CSV 文件，供人工复核和每周运营决策使用。

---

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认：报表体系为 Monthly Financial Close Report、Weekly Business Review、Weekly Ads Optimization Report 三类。 |
| 设计状态 | 本文冻结 WBR v1 设计到指标、字段和公式级别。 |
| 数据源可用性 | 足够支持 v1：Sales & Traffic、Orders、Ads、SKU Cost、Inventory snapshot、Settlement preview 均已入库或已完成补数链路。 |
| 数据刷新依赖 | 依赖 `core_rolling` 每 1-2 天刷新；建议在周报生成前执行一次 `weekly_full` 或至少 `core_rolling`。 |
| 数据库变更 | v1 不新增数据库表，不新增 migration。 |
| 代码实现 | 待开发。 |
| 输出形式 | v1 输出 Markdown / JSON / CSV，可在 v1.1 增加 xlsx。 |
| 验收样本 | 先以 2026-03 起的完整自然周为主，尤其 2026-03-23、2026-03-30、2026-04-06、2026-04-13、2026-04-20 等周。 |

---

## 3. 业务目标

### 3.1 CEO / 运营负责人视角目标

WBR 应帮助回答：

1. **本周卖得怎么样**：销售额、销量、订单数、客单价是否提升。
2. **流量质量怎么样**：Sessions、Page Views、转化率是否变好。
3. **广告是否健康**：广告花费是否可控，ACOS / ROAS / TACOS 是否合理。
4. **SKU 贡献如何**：哪些 SKU 支撑销售，哪些 SKU 消耗预算或库存但贡献差。
5. **库存是否有风险**：是否有缺货、低库存、滞销或清仓压力。
6. **利润方向是否健康**：不是最终财务利润，而是估算毛利、广告后贡献和费用风险是否可接受。
7. **下周该做什么**：列出广告、促销、价格、库存、listing、清仓等行动建议。

### 3.2 小公司阶段原则

当前公司体量小、资金有限，WBR 应优先服务实际经营，而不是做复杂 BI：

```text
先做可读、可核、可行动的文件型周报；
先用 Amazon 美国站真实数据；
先按 SKU 维度，不强行建立复杂 SPU/产品线主数据；
先用标准 SKU 成本，不做 FIFO；
先做人工复核，不自动发送给外部人员；
稳定后再做 xlsx、邮件草稿、自动化调度和可视化仪表盘。
```

---

## 4. 范围与非范围

### 4.1 本功能包含

1. 生成指定自然周的 WBR。
2. 汇总销售、流量、订单、广告、SKU、库存和费用预警。
3. 计算本周、上周和环比变化。
4. 输出 SKU 级表现和库存风险。
5. 输出广告总览指标，但不做深度搜索词优化。
6. 输出经营风险提醒和下周行动建议。
7. 输出数据覆盖与稳定性检查。

### 4.2 本功能不包含

1. 不替代 Monthly Financial Close Report，不用于最终财务定账。
2. 不做完整会计科目或资产负债表。
3. 不做广告搜索词级别深度优化；该内容归 `Weekly Ads Optimization Report`。
4. 不新增数据库结果表。
5. 不自动发送邮件。
6. 不做 FIFO / 批次成本 / 汇率重估。
7. 不做复杂 SPU 映射；v1 先按 `seller_sku` 分析。
8. 不把今天/昨天的不稳定数据作为正式周报结论。

---

## 5. 输入数据

### 5.1 读取表清单

| 数据域 | 表 | 用途 | v1 使用方式 |
|---|---|---|---|
| Sales & Traffic | `amazon_sales_traffic_daily` | 周度销售、销量、订单、sessions、page views、转化率 | 主运营口径 |
| Orders | `amazon_order_item` | SKU 级订单数量、订单销售、促销折扣、地区 | SKU 运营口径 |
| Ads campaign | `amazon_ads_sp_campaign_daily` | 广告总花费、点击、曝光、7日归因销售和订单 | 广告总览主表 |
| Ads advertised product | `amazon_ads_sp_advertised_product_daily` | SKU/ASIN 维度广告花费与销售 | SKU 广告贡献 |
| Ads search term | `amazon_ads_sp_search_term_daily` | 搜索词表现 | v1 只做 top warning；深度分析留给广告优化报表 |
| Settlement | `amazon_settlement_transaction` | posted-date 财务预览、退款/费用风险 | 辅助财务 preview，不作为 WBR 主销售口径 |
| SKU Cost | `amazon_sku_cost` | 单件标准成本 | 估算 COGS / 毛利 |
| Inventory snapshot | `amazon_inventory_daily` | 当前 FBA 可售、预留、不可售、总库存 | 库存风险 |
| Listing snapshot | `amazon_listing_snapshot` | 标题、价格、listing 状态 | SKU 名称/状态补充 |
| Promotion/Coupon | `amazon_promotion_performance`, `amazon_coupon_performance` | 活动概览 | v1 只做活动上下文，不做精确跨周归因 |
| FBA Reimbursements | `amazon_fba_reimbursement` | 赔偿异常 | v1 作为风险提示和财务背景 |

### 5.2 数据充分性判断

当前项目数据足够支持 WBR v1：

```text
Sales & Traffic 可支撑周度销售/流量/转化。
Orders 已通过 historical backfill 补齐 2026-03 起主要历史，可支撑 SKU 级订单分析。
Ads 已通过 historical backfill 补齐 2026-03-17 起主要历史，可支撑广告总览和 SKU 广告贡献。
SKU Cost 已可通过 xlsx 维护，可支撑标准成本 COGS。
Inventory snapshot 已可定期刷新，可支撑库存风险。
Settlement 可作为 posted-date 财务 preview，但不适合作为 WBR 的唯一周度运营口径。
```

### 5.3 当前已知限制

| 限制 | 影响 | v1 处理 |
|---|---|---|
| Settlement posted-date 不等于订单业务日期 | 周度财务金额不能视为最终利润 | WBR 只显示 `settlement_finance_preview`，不叫 final profit |
| Ads 归因会回填 | 最近几天广告销售可能变化 | 依赖 rolling refresh；WBR 使用上周完整自然周，建议周二生成 |
| Sales & Traffic 最近 1-2 天可能延迟 | 今天/昨天不稳定 | WBR 只生成已过稳定截止日的周 |
| Orders `purchase_date_raw` 是 raw 字符串 | 周维度需要解析日期 | v1 按 ISO/UTC 解析；失败行进入 warning |
| SKU/SPU 主数据尚未建立 | 只能按 SKU 看，不按产品线 | v1 只按 `seller_sku`，未来可加 `product_group` 映射表 |
| 库存是快照，不是历史每日库存 | 周内库存变动不完整 | v1 使用最新 snapshot；Ledger 仅作补充说明 |

---

## 6. 输出结果

### 6.1 输出目录

```text
runtime/analysis_reports/weekly_business_review/{marketplace_id}/{week_start}_{week_end}/
```

示例：

```text
runtime/analysis_reports/weekly_business_review/ATVPDKIKX0DER/2026-04-06_2026-04-12/
```

### 6.2 输出文件

| 文件 | 用途 |
|---|---|
| `weekly_business_review.md` | 人工阅读主报告。 |
| `weekly_business_review.json` | 完整结构化结果，供后续 xlsx/email/BI 使用。 |
| `weekly_business_summary.csv` | 本周总览 KPI，一行或少量行。 |
| `weekly_daily_trend.csv` | 周内每日销售、流量、广告趋势。 |
| `weekly_sku_performance.csv` | SKU 销量、销售额、成本、库存、广告贡献。 |
| `weekly_ads_summary.csv` | 广告总览与 campaign 级摘要。 |
| `weekly_inventory_risk.csv` | SKU 库存天数、缺货/滞销风险。 |
| `weekly_alerts.csv` | 异常、风险和行动建议。 |
| `weekly_reconciliation_checks.csv` | 数据覆盖、稳定性和口径检查。 |

### 6.3 CLI 设计

```powershell
python scripts/generate_weekly_business_review.py `
  --marketplace-id ATVPDKIKX0DER `
  --profile-id 3917953989967300 `
  --week-start 2026-04-06 `
  --dry-run
```

可选参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--week-start` | 必填 | 自然周周一，格式 `YYYY-MM-DD`。 |
| `--week-end` | 自动 `week_start + 6 days` | v1 可不开放；内部自动计算。 |
| `--compare-previous-week` | true | 默认和前一自然周比较。 |
| `--target-acos` | `0.30` | 广告 ACOS 警戒阈值。 |
| `--target-tacos` | `0.20` | TACOS 警戒阈值。 |
| `--low-stock-days` | `14` | 低库存预警阈值。 |
| `--watch-stock-days` | `30` | 库存观察阈值。 |
| `--min-stable-lag-days` | `2` | Sales/Orders 最小稳定滞后天数。 |
| `--ads-stable-lag-days` | `3` | Ads 最小稳定滞后天数。 |
| `--output-dir` | 自动 | 自定义输出目录。 |

---

## 7. 周期与稳定性规则

### 7.1 自然周定义

WBR 以自然周为最小单位：

```text
week_start = Monday
week_end = Sunday
```

示例：

```text
2026-04-06 .. 2026-04-12
```

建议每周二生成上周周报：

```text
周一：数据可能仍有延迟；
周二：Sales & Traffic / Orders / Ads 更稳定；
周二上午先运行 core_rolling 或 weekly_full，再生成 WBR。
```

### 7.2 稳定截止日

```text
sales_stable_end = today - 2 days
orders_stable_end = today - 2 days
ads_stable_end = today - 3 days
```

如果 `week_end` 晚于任一核心源的 stable end，则报告仍可生成，但必须标记：

```text
status = preview_unstable
```

如果核心源缺失稳定窗口内的日期，则标记：

```text
status = needs_review
```

### 7.3 建议生成前置动作

生成周报前应执行：

```powershell
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase submit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase collect --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase ingest --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase audit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --target-start-date 2026-03-01 --execute
```

每周完整复盘前建议运行 `weekly_full`，但 WBR v1 不强制要求所有慢源都完整。

---

## 8. 核心指标设计

### 8.1 Executive KPI Summary

| 指标 | 字段名 | 数据源 | 公式 | 说明 |
|---|---|---|---|---|
| Ordered Product Sales | `ordered_product_sales` | `amazon_sales_traffic_daily` | `SUM(ordered_product_sales_amount)` | 本周业务销售额主口径。 |
| Units Ordered | `units_ordered` | `amazon_sales_traffic_daily` | `SUM(units_ordered)` | 本周销售件数。 |
| Total Order Items | `total_order_items` | `amazon_sales_traffic_daily` | `SUM(total_order_items)` | 本周订单商品行/订单项数。 |
| Average Selling Price | `avg_selling_price` | Sales & Traffic | `ordered_product_sales / units_ordered` | 单件平均销售额。 |
| Sessions | `sessions` | `amazon_sales_traffic_daily` | `SUM(sessions)` | 本周访问 sessions。 |
| Page Views | `page_views` | `amazon_sales_traffic_daily` | `SUM(page_views)` | 本周页面浏览。 |
| Unit Session Percentage | `unit_session_percentage` | Sales & Traffic | `units_ordered / sessions` | 用汇总值重算转化率。 |
| Ads Spend | `ads_spend` | `amazon_ads_sp_campaign_daily` | `SUM(cost)` | 本周广告花费。 |
| Ads Sales 7d | `ads_sales_7d` | `amazon_ads_sp_campaign_daily` | `SUM(sales_7d)` | 7日归因广告销售。 |
| Ads Orders 7d | `ads_orders_7d` | `amazon_ads_sp_campaign_daily` | `SUM(purchases_7d)` | 7日归因购买数。 |
| ACOS | `acos` | Ads | `ads_spend / ads_sales_7d` | 广告销售成本比。 |
| ROAS | `roas` | Ads | `ads_sales_7d / ads_spend` | 广告投入产出比。 |
| TACOS | `tacos` | Sales + Ads | `ads_spend / ordered_product_sales` | 全店广告压力。 |
| Estimated COGS | `estimated_cogs` | Orders + SKU Cost | `SUM(order_units_by_sku * unit_standard_cost)` | 标准成本估算。 |
| Gross Margin Before Ads | `gross_margin_before_ads` | Sales + COGS | `ordered_product_sales - estimated_cogs` | 不含 Amazon 平台费/广告费。 |
| Contribution After Ads | `contribution_after_ads` | Sales + COGS + Ads | `ordered_product_sales - estimated_cogs - ads_spend` | 运营贡献估算，不是净利润。 |
| Contribution Margin After Ads | `contribution_margin_after_ads` | derived | `contribution_after_ads / ordered_product_sales` | 用于周度趋势。 |
| Settlement Net Preview | `settlement_net_preview` | `amazon_settlement_transaction` | `SUM(amount)` by posted_date | posted-date 财务预览。 |

### 8.2 环比指标

所有核心 KPI 默认和上一自然周比较：

```text
previous_week_start = week_start - 7 days
previous_week_end = week_end - 7 days
```

通用公式：

```text
absolute_change = current_value - previous_value
percentage_change = (current_value - previous_value) / ABS(previous_value)
```

当 `previous_value = 0`：

```text
如果 current_value > 0，则 percentage_change = NULL，change_label = new_activity
如果 current_value = 0，则 percentage_change = 0
```

输出应同时包含：

```text
current_value
previous_value
absolute_change
percentage_change
change_label
```

---

## 9. 销售与流量模块

### 9.1 读取条件

```sql
FROM dbo.amazon_sales_traffic_daily
WHERE marketplace_id = @marketplace_id
  AND report_date BETWEEN @week_start AND @week_end
```

### 9.2 每日趋势字段

| 字段 | 公式 |
|---|---|
| `report_date` | `amazon_sales_traffic_daily.report_date` |
| `ordered_product_sales` | `ordered_product_sales_amount` |
| `units_ordered` | `units_ordered` |
| `total_order_items` | `total_order_items` |
| `sessions` | `sessions` |
| `page_views` | `page_views` |
| `unit_session_percentage` | `units_ordered / sessions` |
| `avg_selling_price` | `ordered_product_sales_amount / units_ordered` |

### 9.3 质量检查

| 场景 | 处理 |
|---|---|
| 7 天不完整 | `needs_review`，列出 missing dates。 |
| `sessions = 0` | 转化率置 NULL，生成 warning。 |
| 销售额为 0 但 sessions > 0 | 生成 conversion warning。 |
| 单日销售额较前 7 日均值跌幅超过 50% | 生成 sales_drop warning。 |

---

## 10. Orders 与 SKU 模块

### 10.1 读取条件

`amazon_order_item.purchase_date_raw` 需要解析为 `purchase_date`。v1 规则：

```text
优先按 ISO datetime / UTC datetime 解析；
解析成功后取 UTC date；
purchase_date BETWEEN week_start AND week_end；
解析失败行不参与聚合，并写入 warning。
```

建议过滤：

```text
order_status NOT IN ('Cancelled', 'Canceled') OR order_status IS NULL
item_status NOT IN ('Cancelled', 'Canceled') OR item_status IS NULL
```

### 10.2 SKU 销售字段

| 字段 | 来源/公式 |
|---|---|
| `seller_sku` | `amazon_order_item.seller_sku` |
| `asin` | `amazon_order_item.asin` |
| `product_name` | 优先 `amazon_order_item.product_name`，否则最新 listing/inventory name。 |
| `order_units` | `SUM(quantity)`，NULL 视为 0。 |
| `order_item_sales` | `SUM(item_price)`，不含 tax。 |
| `shipping_revenue` | `SUM(shipping_price)` |
| `item_promo_discount` | `SUM(item_promotion_discount)` |
| `ship_promo_discount` | `SUM(ship_promotion_discount)` |
| `order_discount_total` | `item_promo_discount + ship_promo_discount` |
| `order_net_sales_estimate` | `order_item_sales + shipping_revenue - order_discount_total` |
| `unit_standard_cost` | 从 `amazon_sku_cost` 按 SKU + 生效日期匹配。 |
| `estimated_cogs` | `order_units * unit_standard_cost` |
| `gross_margin_before_ads` | `order_item_sales - order_discount_total - estimated_cogs` |
| `gross_margin_rate_before_ads` | `gross_margin_before_ads / order_item_sales` |

### 10.3 SKU 成本匹配规则

对于每个 `seller_sku`，用周中订单日期或逐行订单日期匹配：

```text
cost.marketplace_id = @marketplace_id
cost.seller_sku = order.seller_sku
cost.effective_from <= purchase_date
(cost.effective_to IS NULL OR cost.effective_to >= purchase_date)
```

单件标准成本：

```text
unit_standard_cost = product_cost + first_mile_cost + packaging_cost + other_unit_cost
```

若同一 SKU 多条成本记录命中：

```text
选 effective_from 最大的一条。
```

若无成本：

```text
report_status = needs_review
missing_cost_skus += seller_sku
```

---

## 11. Ads 总览模块

### 11.1 读取条件

```sql
FROM dbo.amazon_ads_sp_campaign_daily
WHERE profile_id = @profile_id
  AND marketplace_id = @marketplace_id
  AND report_date BETWEEN @week_start AND @week_end
```

### 11.2 广告总览字段

| 字段 | 公式 |
|---|---|
| `ads_impressions` | `SUM(impressions)` |
| `ads_clicks` | `SUM(clicks)` |
| `ads_spend` | `SUM(cost)` |
| `ads_sales_7d` | `SUM(sales_7d)` |
| `ads_orders_7d` | `SUM(purchases_7d)` |
| `ads_units_7d` | 如字段存在则 `SUM(units_sold_clicks_7d)`，否则 NULL。 |
| `ctr` | `ads_clicks / ads_impressions` |
| `cpc` | `ads_spend / ads_clicks` |
| `ads_cvr` | `ads_orders_7d / ads_clicks` |
| `acos` | `ads_spend / ads_sales_7d` |
| `roas` | `ads_sales_7d / ads_spend` |
| `tacos` | `ads_spend / ordered_product_sales` |

### 11.3 Campaign 摘要

按 `campaign_id + campaign_name` 聚合：

| 字段 | 公式 |
|---|---|
| `campaign_name` | `campaign_name` |
| `campaign_spend` | `SUM(cost)` |
| `campaign_sales_7d` | `SUM(sales_7d)` |
| `campaign_orders_7d` | `SUM(purchases_7d)` |
| `campaign_acos` | `campaign_spend / campaign_sales_7d` |
| `campaign_roas` | `campaign_sales_7d / campaign_spend` |
| `campaign_cpc` | `SUM(cost) / SUM(clicks)` |

WBR v1 只输出 campaign top summary。搜索词级 winners/losers 归 `Weekly Ads Optimization Report`。

### 11.4 广告质量检查

| 场景 | 默认阈值 | warning |
|---|---:|---|
| `acos > target_acos` | 30% | `high_acos` |
| `tacos > target_tacos` | 20% | `high_tacos` |
| `ads_spend > 0 and ads_sales_7d = 0` | 任意 | `ads_spend_without_sales` |
| `clicks > 30 and purchases_7d = 0` | 30 clicks | `clicks_without_orders` |
| 广告花费环比上升 > 30%，销售额环比未上升 | 30% | `spend_up_sales_not_up` |

---

## 12. SKU 广告与贡献模块

### 12.1 数据源

优先使用：

```text
amazon_ads_sp_advertised_product_daily.advertised_sku
```

按 SKU 聚合广告花费与归因销售：

```sql
WHERE profile_id = @profile_id
  AND marketplace_id = @marketplace_id
  AND report_date BETWEEN @week_start AND @week_end
GROUP BY advertised_sku
```

### 12.2 SKU 贡献字段

| 字段 | 公式 |
|---|---|
| `sku_order_units` | Orders SKU units |
| `sku_order_sales` | Orders SKU item sales |
| `sku_cogs` | Orders SKU units * unit cost |
| `sku_gross_margin_before_ads` | `sku_order_sales - sku_discount_total - sku_cogs` |
| `sku_ads_spend` | `SUM(advertised_product.cost)` |
| `sku_ads_sales_7d` | `SUM(advertised_product.sales_7d)` |
| `sku_ads_orders_7d` | `SUM(advertised_product.purchases_7d)` |
| `sku_contribution_after_ads` | `sku_gross_margin_before_ads - sku_ads_spend` |
| `sku_tacos` | `sku_ads_spend / sku_order_sales` |
| `sku_ads_dependency_rate` | `sku_ads_sales_7d / sku_order_sales`，仅作粗略参考。 |

### 12.3 SKU 排名

WBR v1 输出：

```text
Top SKU by sales
Top SKU by units
Top SKU by contribution after ads
Worst SKU by contribution after ads
High ads spend SKU
Low inventory high velocity SKU
```

---

## 13. Inventory 风险模块

### 13.1 快照选择规则

库存是快照数据，不是历史每日库存。WBR v1 使用最新可用快照：

```sql
snapshot_date = MAX(snapshot_date)
WHERE marketplace_id = @marketplace_id
  AND snapshot_date <= report_generated_date
```

如果最新快照距离 `week_end` 超过 7 天：

```text
warning = stale_inventory_snapshot
```

### 13.2 库存指标

| 字段 | 来源/公式 |
|---|---|
| `afn_fulfillable_quantity` | `amazon_inventory_daily.afn_fulfillable_quantity` |
| `afn_reserved_quantity` | `amazon_inventory_daily.afn_reserved_quantity` |
| `afn_unsellable_quantity` | `amazon_inventory_daily.afn_unsellable_quantity` |
| `afn_total_quantity` | `amazon_inventory_daily.afn_total_quantity` |
| `weekly_units_ordered` | Orders SKU units |
| `avg_daily_units_ordered_7d` | `weekly_units_ordered / 7` |
| `days_of_supply` | `afn_fulfillable_quantity / avg_daily_units_ordered_7d` |
| `inventory_value_at_cost` | `afn_total_quantity * unit_standard_cost` |

如果 `avg_daily_units_ordered_7d = 0`：

```text
days_of_supply = NULL
inventory_velocity_status = no_recent_sales
```

### 13.3 库存风险分级

| 风险 | 条件 |
|---|---|
| `stockout` | `afn_fulfillable_quantity = 0` 且 `weekly_units_ordered > 0` |
| `urgent_low_stock` | `days_of_supply < 14` |
| `watch_low_stock` | `14 <= days_of_supply < 30` |
| `healthy` | `30 <= days_of_supply <= 120` |
| `overstock_watch` | `days_of_supply > 120` 或 `weekly_units_ordered = 0 and afn_fulfillable_quantity > 0` |

---

## 14. Settlement 财务 preview 模块

### 14.1 读取条件

```sql
FROM dbo.amazon_settlement_transaction
WHERE marketplace_id = @marketplace_id
  AND is_settlement_summary = 0
  AND posted_date BETWEEN @week_start AND @week_end
```

### 14.2 字段

| 字段 | 公式 | 说明 |
|---|---|---|
| `settlement_net_preview` | `SUM(amount)` | posted-date 维度本周净额。 |
| `settlement_product_sales` | `SUM(amount WHERE profit_bucket='product_sales')` | 如 bucket 可用。 |
| `settlement_advertising_fee` | `SUM(amount WHERE profit_bucket='advertising')` | 财务扣费口径广告费。 |
| `settlement_fba_fee` | `SUM(amount WHERE profit_bucket='fba_fees')` | FBA 配送/仓储相关。 |
| `settlement_refund_amount` | `SUM(amount WHERE transaction_type='Refund' OR profit_bucket='refunds')` | posted-date 退款。 |
| `settlement_promotion_amount` | `SUM(amount WHERE profit_bucket='promotions')` | posted-date 促销。 |

### 14.3 使用原则

WBR 中 Settlement 只作为财务 preview，不作为核心销售趋势口径。原因：

```text
Settlement posted-date 与订单业务日期错位；
周度 Settlement 可能只反映结算处理时间，不反映本周真实经营表现；
正式财务结论应看 Monthly Financial Close Report。
```

WBR 报告中应明确标注：

```text
Settlement preview is posted-date financial context, not final weekly profit.
```

---

## 15. Alerts 与行动建议

### 15.1 默认阈值

| 阈值 | 默认值 | 说明 |
|---|---:|---|
| `target_acos` | 30% | 清仓/低利润产品可设更低。 |
| `target_tacos` | 20% | 超过说明广告压力较大。 |
| `sales_drop_pct` | -20% | 销售额环比下降超过 20%。 |
| `conversion_drop_pct` | -20% | 转化率环比下降超过 20%。 |
| `high_refund_rate` | 10% | posted-date 退款占销售额。 |
| `low_stock_days` | 14 | 低库存紧急阈值。 |
| `watch_stock_days` | 30 | 库存观察阈值。 |
| `stale_inventory_days` | 7 | 库存快照过期。 |

### 15.2 Alert 规则

| Alert | 条件 | 建议动作 |
|---|---|---|
| `sales_drop` | 本周销售额环比下降 > 20% | 检查广告、价格、优惠券、库存、Buy Box。 |
| `conversion_drop` | 转化率环比下降 > 20% | 检查 listing、价格、评论、优惠券、图片。 |
| `high_tacos` | `tacos > target_tacos` | 降低低效广告预算，检查搜索词。 |
| `high_acos` | `acos > target_acos` | 下调高 ACOS campaign/target。 |
| `ads_spend_without_sales` | 广告花费 > 0 且广告销售为 0 | 检查投放词，必要时否定。 |
| `sku_negative_contribution` | SKU contribution after ads < 0 | 检查广告、促销、价格和成本。 |
| `missing_sku_cost` | SKU 无成本 | 先补 `amazon_sku_cost`，否则不输出成本结论。 |
| `stockout` | 可售库存为 0 且近期有销量 | 补货/关广告/避免浪费流量。 |
| `urgent_low_stock` | 库存天数 < 14 | 调整广告预算，准备补货或清仓策略。 |
| `overstock_watch` | 库存天数 > 120 或无销量 | 考虑促销、清仓、移除或降广告。 |
| `stale_inventory_snapshot` | 库存快照超过 7 天 | 先跑 inventory refresh。 |
| `settlement_refund_spike` | posted-date refund rate > 10% | 检查退货原因、质量、listing 误导。 |

### 15.3 Action List 输出格式

`weekly_alerts.csv` 字段：

| 字段 | 说明 |
|---|---|
| `severity` | `critical` / `warning` / `info` |
| `area` | sales / ads / sku / inventory / finance / data_quality |
| `metric` | 触发指标 |
| `current_value` | 当前值 |
| `previous_value` | 上周值 |
| `threshold` | 阈值 |
| `message` | 中文说明 |
| `recommended_action` | 建议动作 |
| `related_sku` | 可空 |
| `related_campaign` | 可空 |

---

## 16. 数据质量与状态规则

### 16.1 报告状态

| 状态 | 条件 | 是否可用于运营决策 |
|---|---|---|
| `ok` | 核心数据覆盖完整，无缺 SKU 成本，无严重异常。 | 是 |
| `preview_unstable` | 周期未过稳定截止日，或 Ads/Sales 最近数据可能回填。 | 只做观察 |
| `needs_review` | 缺核心数据、缺 SKU 成本、关键字段解析失败。 | 需人工修复后再用 |
| `partial` | 非核心模块缺失，如库存快照过旧、Settlement preview 缺失。 | 可用，但需看 warning |
| `no_data` | 核心销售数据为空。 | 不可用 |

### 16.2 核心数据必需性

| 数据 | 必需性 | 缺失影响 |
|---|---|---|
| Sales & Traffic | 必需 | 没有销售/流量总览，报告 `no_data` 或 `needs_review`。 |
| Orders | 必需 | 无法做 SKU 和 COGS，报告 `needs_review`。 |
| SKU Cost | 必需 | 无法输出成本和贡献，报告 `needs_review`。 |
| Ads campaign | 重要 | 可生成销售周报，但广告模块 `partial`。 |
| Inventory snapshot | 重要 | 可生成周报，但库存模块 `partial`。 |
| Settlement | 可选 | 财务 preview 缺失，不阻塞 WBR。 |
| Promotion/Coupon | 可选 | 活动上下文缺失，不阻塞 WBR。 |

### 16.3 数据覆盖检查

报表生成前建议检查：

```powershell
python scripts/audit_data_coverage.py --marketplace-id ATVPDKIKX0DER --target-start-date {week_start}
```

WBR 服务内部也应做局部覆盖检查：

```text
Sales & Traffic 是否覆盖 week_start..week_end 共 7 天；
Orders 是否有对应日期范围 raw / normalized 数据；
Ads 是否覆盖 week_start..week_end，或至少标明缺失日期；
Inventory snapshot 是否足够新；
SKU Cost 是否覆盖所有本周销售 SKU。
```

---

## 17. 字段映射与公式总表

### 17.1 Summary 字段

| 输出字段 | 来源表/字段 | 公式/规则 |
|---|---|---|
| `marketplace_id` | 参数 | 原样输出。 |
| `profile_id` | 参数 | 原样输出。 |
| `week_start` | 参数 | 必须为 Monday。 |
| `week_end` | derived | `week_start + 6 days`。 |
| `report_status` | derived | 按第 16 节规则。 |
| `ordered_product_sales` | `amazon_sales_traffic_daily.ordered_product_sales_amount` | SUM。 |
| `units_ordered` | `amazon_sales_traffic_daily.units_ordered` | SUM。 |
| `total_order_items` | `amazon_sales_traffic_daily.total_order_items` | SUM。 |
| `sessions` | `amazon_sales_traffic_daily.sessions` | SUM。 |
| `page_views` | `amazon_sales_traffic_daily.page_views` | SUM。 |
| `unit_session_percentage` | derived | `units_ordered / sessions`。 |
| `avg_selling_price` | derived | `ordered_product_sales / units_ordered`。 |
| `ads_spend` | `amazon_ads_sp_campaign_daily.cost` | SUM。 |
| `ads_sales_7d` | `amazon_ads_sp_campaign_daily.sales_7d` | SUM。 |
| `acos` | derived | `ads_spend / ads_sales_7d`。 |
| `roas` | derived | `ads_sales_7d / ads_spend`。 |
| `tacos` | derived | `ads_spend / ordered_product_sales`。 |
| `estimated_cogs` | Orders + SKU Cost | SUM units * cost。 |
| `gross_margin_before_ads` | derived | `ordered_product_sales - estimated_cogs`。 |
| `contribution_after_ads` | derived | `ordered_product_sales - estimated_cogs - ads_spend`。 |
| `settlement_net_preview` | `amazon_settlement_transaction.amount` | SUM by posted_date。 |
| `alert_count` | alerts | COUNT。 |

### 17.2 SKU 字段

| 输出字段 | 来源/公式 |
|---|---|
| `seller_sku` | Orders / Inventory / Ads SKU。 |
| `asin` | 优先 Orders ASIN，否则 Inventory/Listing ASIN。 |
| `product_name` | 优先 Orders product_name，否则 Inventory/Listing product_name。 |
| `units_ordered` | Orders `SUM(quantity)`。 |
| `order_item_sales` | Orders `SUM(item_price)`。 |
| `discount_total` | Orders `SUM(item_promotion_discount + ship_promotion_discount)`。 |
| `unit_standard_cost` | SKU Cost 生效记录。 |
| `estimated_cogs` | `units_ordered * unit_standard_cost`。 |
| `gross_margin_before_ads` | `order_item_sales - discount_total - estimated_cogs`。 |
| `ads_spend` | Advertised product `SUM(cost)`。 |
| `ads_sales_7d` | Advertised product `SUM(sales_7d)`。 |
| `contribution_after_ads` | `gross_margin_before_ads - ads_spend`。 |
| `fulfillable_quantity` | 最新 Inventory snapshot。 |
| `days_of_supply` | `fulfillable_quantity / (units_ordered / 7)`。 |
| `inventory_risk` | 按第 13 节分级。 |

---

## 18. 报告 Markdown 结构

`weekly_business_review.md` 建议结构：

```text
# Weekly Business Review - {marketplace_id} - {week_start} to {week_end}

## 1. Executive Summary
- 本周一句话结论
- 核心 KPI 表
- 主要风险和机会

## 2. Sales & Traffic
- 销售额、销量、订单数、sessions、转化率
- 环比变化
- 每日趋势表

## 3. Ads Overview
- Spend、Sales、ACOS、ROAS、TACOS
- Campaign top summary
- 广告风险提示

## 4. SKU Performance
- SKU 销量/销售额/毛利/广告后贡献
- Top / bottom SKU

## 5. Inventory Risk
- 可售库存、库存天数、低库存/滞销提醒

## 6. Finance Preview
- Settlement posted-date preview
- 退款/费用风险
- 明确提示：不是最终财务结算

## 7. Alerts & Recommended Actions
- 下周建议动作

## 8. Data Quality & Reconciliation
- 覆盖情况
- 缺失数据
- refresh/audit 时间
```

---

## 19. 处理流程

```text
CLI params
  -> validate week_start / week_end / stable cutoff
  -> query current week data
  -> query previous week data
  -> aggregate sales & traffic
  -> parse and aggregate orders by SKU
  -> match SKU costs
  -> aggregate ads summary and SKU ads
  -> attach latest inventory snapshot
  -> attach settlement finance preview
  -> compute KPI and week-over-week changes
  -> generate alerts and recommended actions
  -> write JSON / Markdown / CSV
```

失败处理：

| 阶段 | 失败场景 | 处理 |
|---|---|---|
| 参数校验 | `week_start` 不是周一 | fail fast。 |
| 日期解析 | Orders 日期解析失败 | 记录 warning，失败行不参与 SKU 汇总。 |
| 成本匹配 | SKU 无成本 | `needs_review`，不输出正式贡献结论。 |
| 数据缺失 | Sales & Traffic 缺天 | `needs_review`。 |
| Ads 缺失 | Ads 缺天 | Ads 模块 partial，WBR 仍可生成。 |
| Inventory 过旧 | 快照超过 7 天 | partial + warning。 |

---

## 20. 幂等性设计

WBR v1 不写数据库，只写 runtime 输出文件。

同一参数重复执行：

```text
覆盖同一输出目录下的文件；
不新增数据库记录；
不影响 normalized 表；
输出应只随源数据更新而变化。
```

推荐输出元数据：

```json
{
  "report_type": "weekly_business_review",
  "marketplace_id": "ATVPDKIKX0DER",
  "profile_id": "3917953989967300",
  "week_start": "2026-04-06",
  "week_end": "2026-04-12",
  "generated_at_utc": "...",
  "source_tables": [...],
  "report_status": "ok"
}
```

---

## 21. 验收标准

### 21.1 功能验收

第一版开发完成后，应能运行：

```powershell
python scripts/generate_weekly_business_review.py --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --week-start 2026-04-06 --dry-run
```

并输出：

```text
runtime/analysis_reports/weekly_business_review/ATVPDKIKX0DER/2026-04-06_2026-04-12/weekly_business_review.md
runtime/analysis_reports/weekly_business_review/ATVPDKIKX0DER/2026-04-06_2026-04-12/weekly_business_review.json
runtime/analysis_reports/weekly_business_review/ATVPDKIKX0DER/2026-04-06_2026-04-12/weekly_business_summary.csv
runtime/analysis_reports/weekly_business_review/ATVPDKIKX0DER/2026-04-06_2026-04-12/weekly_daily_trend.csv
runtime/analysis_reports/weekly_business_review/ATVPDKIKX0DER/2026-04-06_2026-04-12/weekly_sku_performance.csv
runtime/analysis_reports/weekly_business_review/ATVPDKIKX0DER/2026-04-06_2026-04-12/weekly_ads_summary.csv
runtime/analysis_reports/weekly_business_review/ATVPDKIKX0DER/2026-04-06_2026-04-12/weekly_inventory_risk.csv
runtime/analysis_reports/weekly_business_review/ATVPDKIKX0DER/2026-04-06_2026-04-12/weekly_alerts.csv
runtime/analysis_reports/weekly_business_review/ATVPDKIKX0DER/2026-04-06_2026-04-12/weekly_reconciliation_checks.csv
```

### 21.2 数字验收

1. `ordered_product_sales` 应等于 `amazon_sales_traffic_daily` 周内金额之和。
2. `units_ordered` 应等于 `amazon_sales_traffic_daily.units_ordered` 周内之和。
3. `ads_spend` 应等于 `amazon_ads_sp_campaign_daily.cost` 周内之和。
4. `acos`、`roas`、`tacos` 应由汇总值重算，不使用源表已算百分比。
5. SKU COGS 应能追溯到 `amazon_sku_cost` 生效记录。
6. 库存天数应能追溯到最新 `amazon_inventory_daily` 快照。
7. 同一周重复生成，若源数据不变，输出数值应一致。

### 21.3 人工复核样本

建议先用以下自然周验收：

```text
2026-03-23 .. 2026-03-29
2026-03-30 .. 2026-04-05
2026-04-06 .. 2026-04-12
2026-04-13 .. 2026-04-19
2026-04-20 .. 2026-04-26
```

这些周处于当前补数较完整范围内，适合验证 Sales & Traffic、Orders、Ads、SKU 成本和库存快照链路。

---

## 22. 后续版本

### v1.1

- 增加 xlsx 输出。
- 增加邮件草稿模板。
- 增加更完整的同比/月内累计对比。
- 增加 configurable thresholds 文件。

### v1.2

- 增加 SKU -> SPU / 产品线映射。
- 增加库存 Ledger movement 解释。
- 增加 Buy Box / Listing price 变化解释。

### v2.0

- 增加结果表落库。
- 接入 Azure Container Apps Jobs 自动生成。
- 自动生成每周邮件草稿。
- 与 Weekly Ads Optimization Report 联动生成广告动作清单。

---

## 23. 当前冻结结论

WBR v1 冻结为：

```text
每周自然周经营复盘；
主运营口径使用 Sales & Traffic；
SKU 维度使用 Orders + SKU Cost；
广告总览使用 Ads campaign daily；
SKU 广告贡献使用 Ads advertised product daily；
库存风险使用最新 Inventory snapshot；
Settlement 只做 posted-date finance preview，不作为最终周利润；
不新增数据库表；
不自动发邮件；
先输出 Markdown / JSON / CSV，人工复核稳定后再实现自动化。
```
