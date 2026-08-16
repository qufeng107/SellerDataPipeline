# Feature: Weekly Business Review

> **v2 redesign note (2026-08-16):** Default presentation and correctness gates are superseded by `feature_weekly_reporting_pack_redesign.md` and ADR-017. Existing v1 details remain implementation/history reference until v2 rollout.


> 文档状态：Implemented / pending live verification  
> 负责人：AI + Feng  
> 更新时间：2026-06-01  
> 功能状态：Implemented / v1.1 经营口径与 Saturday-Friday 周周期已完成代码对齐，待新周期 live verification  
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

第一版 WBR 不新增数据库结果表，不自动发送邮件，不生成正式 PDF。它读取已经入库的 normalized 表，默认输出一个结构化 JSON 和一个多 sheet XLSX，供人工复核、每周经营决策、后续邮件/PDF/Dashboard 自动化使用。

---

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认：报表体系为 Monthly Financial Close Report、Weekly Business Review、Weekly Ads Optimization Report 三类。 |
| 设计状态 | 本文已刷新并实现 WBR v1 到指标、字段、公式、JSON 结构和 XLSX sheet 级别。 |
| 数据源可用性 | 足够支持 v1：Sales & Traffic、Orders、SKU Cost、Inventory snapshot、Settlement preview 均已入库；Ads campaign daily 当前真实库只覆盖 2026-05-06 起，历史缺口应作为广告运营解释缺失 warning，不影响销售/库存/成本周报主体。 |
| 数据刷新依赖 | 依赖 `core_rolling` 每 1-2 天刷新；建议在周报生成前执行一次 `weekly_full` 或至少 `core_rolling`。 |
| 数据库变更 | v1 不新增数据库表，不新增 migration。 |
| 代码实现 | 已完成 v1/v1.1：`scripts/generate_weekly_business_review.py` + service/repo/unit tests；默认周期对齐 Saturday-Friday，贡献指标文案已标注未扣完整 Amazon 平台费。 |
| 默认输出形式 | `weekly_business_review_{week_start}_{week_end}.json` + `weekly_business_review_{week_start}_{week_end}.xlsx`。 |
| 不再默认输出 | 不默认输出 Markdown；不默认输出多个 CSV。 |
| 验收样本 | 先以 2026-03 起的完整自然周为主，尤其 2026-03-23、2026-03-30、2026-04-06、2026-04-13、2026-04-20 等周。对于 3/4 月样本，Ads API context 可能 partial；5 月 6 日之后样本可验证 Ads campaign daily 加工。 |

---

## 3. 业务目标

### 3.1 CEO / 运营负责人视角目标

WBR 应帮助回答：

1. **本周卖得怎么样**：销售额、销量、订单数、客单价是否提升。
2. **流量质量怎么样**：Sessions、Page Views、转化率是否变好。
3. **广告是否健康**：广告花费是否可控，ACOS / ROAS / TACOS 是否合理。
4. **SKU 贡献如何**：哪些 SKU 支撑销售，哪些 SKU 消耗预算或库存但贡献差。
5. **库存是否有风险**：是否有缺货、低库存、滞销或清仓压力。
6. **利润方向是否健康**：不是最终财务利润，而是广告和货本后贡献、广告压力和费用风险是否可接受。该贡献指标必须明确未扣完整 Amazon 平台费。
7. **下周该做什么**：列出广告、促销、价格、库存、listing、清仓等行动建议。

### 3.2 小公司阶段原则

当前公司体量小、资金有限，WBR 应优先服务实际经营，而不是做复杂 BI：

```text
先做可读、可核、可行动的文件型周报；
先用 Amazon 美国站真实数据；
先按 SKU 维度，不强行建立复杂 SPU/产品线主数据；
先用标准 SKU 成本，不做 FIFO；
先 JSON/XLSX 稳定，再生成 PDF/邮件；
先人工复核，不自动发送给外部人员；
稳定后再做邮件草稿、自动化调度和可视化仪表盘。
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
8. 输出一个结构化 JSON 和一个多 sheet XLSX。

### 4.2 本功能不包含

1. 不替代 Monthly Financial Close Report，不用于最终财务定账。
2. 不做完整会计科目或资产负债表。
3. 不做广告搜索词级别深度优化；该内容归 `Weekly Ads Optimization Report`。
4. 不新增数据库结果表。
5. 不自动发送邮件。
6. 不做 FIFO / 批次成本 / 汇率重估。
7. 不做复杂 SPU 映射；v1 先按 `seller_sku` 分析。
8. 不把今天/昨天的不稳定数据作为正式周报结论。
9. 不默认生成 Markdown，因为股东、会计和管理层实际使用场景主要是 XLSX / PDF / Email。
10. 不默认生成多个 CSV；如调试需要，可后续增加 `--export-csv`。

---

## 5. 报表命名与使用场景

正式名称：

```text
Weekly Business Review
每周经营周报 / 每周运营复盘报表
```

| 使用者 | 用途 | 推荐文件 |
|---|---|---|
| CEO / 运营负责人 | 每周判断增长、流量、广告、库存和 SKU 优先级。 | XLSX + 后续 PDF 摘要。 |
| 广告/运营执行者 | 看 campaign 总览、SKU 贡献、异常提示和下周动作。 | XLSX。 |
| 股东 / 管理层 | 简洁理解业务趋势，不看过细搜索词。 | 后续由 JSON 生成 PDF / Email；必要时附 XLSX。 |
| 后续自动化 | 邮件正文、PDF、Dashboard、趋势分析、自动预警。 | JSON。 |

---

## 6. 周期口径

### 6.1 自然周定义

WBR 以 7 天为最小单位。自动化默认采用 Saturday–Friday：

```text
week_start = Saturday
week_end = Friday
```

示例：

```text
2026-05-16 .. 2026-05-22
```

建议每周一生成上一完整 Saturday–Friday 周期的周报：

```text
周六/周日：作为缓冲，等待 Sales & Traffic / Orders / Ads 回填；
周一：先运行 weekly_full 或至少 core_rolling，再生成 WBR 和广告优化周报；
周一发送 report delivery 给运营/管理层复核。
```

手动运行时可指定其他 7 天窗口，但 WBR、WAOR、Report Delivery 和自动化 job 必须使用同一周周期，避免周报之间无法对齐。

### 6.2 CLI 设计

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
| `--week-start` | 必填 | 7天报表周期起始日，格式 `YYYY-MM-DD`；自动化周报默认使用周六起始，统计周六到周五。 |
| `--week-end` | 自动 `week_start + 6 days` | v1 可不开放；内部自动计算。 |
| `--compare-previous-week` | true | 默认和前一自然周比较。 |
| `--target-acos` | `0.30` | 广告 ACOS 警戒阈值。 |
| `--target-tacos` | `0.20` | TACOS 警戒阈值。 |
| `--low-stock-days` | `14` | 低库存预警阈值。 |
| `--watch-stock-days` | `30` | 库存观察阈值。 |
| `--min-stable-lag-days` | `2` | Sales/Orders 最小稳定滞后天数。 |
| `--ads-stable-lag-days` | `3` | Ads 最小稳定滞后天数。 |
| `--output-dir` | 自动 | 自定义输出目录。 |

### 6.3 `--dry-run` 语义

WBR v1 不写数据库，因此 `--dry-run` 定义为：

```text
只读数据库；
不写数据库；
不发送邮件；
不触发任何外部动作；
但仍生成 runtime JSON/XLSX 文件，方便人工复核。
```

---

## 7. 输出设计

### 7.1 输出目录

```text
runtime/analysis_reports/weekly_business_review/{marketplace_id}/{week_start}_{week_end}/
```

示例：

```text
runtime/analysis_reports/weekly_business_review/ATVPDKIKX0DER/2026-04-06_2026-04-12/
```

### 7.2 默认输出文件

v1 默认只输出两个文件：

| 文件 | 用途 |
|---|---|
| `weekly_business_review_{week_start}_{week_end}.json` | 结构化 source of truth，供后续 PDF / Email / Dashboard / 自动预警使用。 |
| `weekly_business_review_{week_start}_{week_end}.xlsx` | 人工复核和每周经营会议使用的多 sheet 表格。 |

不再默认输出：

```text
weekly_business_review.md
weekly_business_summary.csv
weekly_daily_trend.csv
weekly_sku_performance.csv
weekly_ads_summary.csv
weekly_inventory_risk.csv
weekly_alerts.csv
weekly_reconciliation_checks.csv
```

如后续调试需要，可以新增 `--export-csv`，但 v1 默认不做，避免文件过碎。

### 7.3 JSON 与 XLSX 分工

```text
JSON = 机器可读的完整周报结果，是后续 PDF / Email / Dashboard 的 source of truth。
XLSX = 人可读、可筛选、可复核的表格版周报，适合运营会议和人工归档。
```

JSON 可以包含嵌套结构、状态、warnings、action recommendations、summary text seed；XLSX 应尽量扁平化，一张 sheet 对应一个分析主题。

### 7.4 XLSX sheets

默认 XLSX 包含：

| Sheet | 用途 |
|---|---|
| `01_Executive_Summary` | 本周核心 KPI、环比、状态、结论。 |
| `02_Daily_Trend` | 周内每日 Sales & Traffic + Ads 趋势。 |
| `03_Sales_Traffic` | 销售、销量、订单、sessions、page views、转化率细表。 |
| `04_SKU_Performance` | SKU 销售、成本、毛利、广告后贡献、库存摘要。 |
| `05_Ads_Overview` | Ads campaign daily 总览和 campaign 摘要。 |
| `06_Inventory_Risk` | SKU 库存天数、低库存、滞销、库存价值。 |
| `07_Alerts_Actions` | 异常、风险和下周建议动作。 |
| `08_Reconciliation_Checks` | 数据覆盖、稳定性和口径检查。 |
| `09_Raw_Metadata` | 报表参数、生成时间、源表、row counts、notes。 |

### 7.5 代码路径

v1 实现路径：

```text
scripts/generate_weekly_business_review.py
src/seller_data_pipeline/db/repositories/weekly_business_review_repo.py
src/seller_data_pipeline/services/weekly_business_review_service.py
tests/unit/db/test_weekly_business_review_repo.py
tests/unit/services/test_weekly_business_review_service.py
```

### 7.6 JSON 顶层结构

建议：

```json
{
  "report_type": "weekly_business_review",
  "version": "v1.0",
  "marketplace_id": "ATVPDKIKX0DER",
  "profile_id": "3917953989967300",
  "period": {
    "week_start": "2026-04-06",
    "week_end": "2026-04-12",
    "previous_week_start": "2026-03-30",
    "previous_week_end": "2026-04-05"
  },
  "status": "ok",
  "currency": "USD",
  "executive_summary": {},
  "kpi_summary": {},
  "daily_trend": [],
  "sales_traffic_summary": {},
  "sku_performance": [],
  "ads_overview": {},
  "inventory_risk": [],
  "settlement_finance_preview": {},
  "alerts": [],
  "reconciliation_checks": [],
  "warnings": [],
  "output_files": {}
}
```

---

## 8. 输入数据

### 8.1 读取表清单

| 数据域 | 表 | 用途 | v1 使用方式 |
|---|---|---|---|
| Sales & Traffic | `amazon_sales_traffic_daily` | 周度销售、销量、订单、sessions、page views、转化率 | 主运营口径 |
| Orders | `amazon_order_item` | SKU 级订单数量、订单销售、促销折扣、地区 | SKU 运营口径 |
| Ads campaign | `amazon_ads_sp_campaign_daily` | 广告总花费、点击、曝光、7日归因销售和订单 | 广告总览主表；缺失时 WBR partial，不阻塞销售周报 |
| Ads advertised product | `amazon_ads_sp_advertised_product_daily` | SKU/ASIN 维度广告花费与销售 | SKU 广告贡献；缺失时该列为空/0 并 warning |
| Ads search term | `amazon_ads_sp_search_term_daily` | 搜索词表现 | v1 只做 top warning；深度分析留给广告优化报表 |
| Settlement | `amazon_settlement_transaction` | posted-date 财务预览、退款/费用风险 | 辅助财务 preview，不作为 WBR 主销售口径 |
| SKU Cost | `amazon_sku_cost` | 单件标准成本 | 估算 COGS / 毛利 |
| Inventory snapshot | `amazon_inventory_daily` | 当前 FBA 可售、预留、不可售、总库存 | 库存风险 |
| Listing snapshot | `amazon_listing_snapshot` | 标题、价格、listing 状态 | SKU 名称/状态补充 |
| Promotion/Coupon | `amazon_promotion_performance`, `amazon_coupon_performance` | 活动概览 | v1 只做活动上下文，不做精确跨周归因 |
| FBA Reimbursements | `amazon_fba_reimbursement` | 赔偿异常 | v1 作为风险提示和财务背景 |

### 8.2 数据充分性判断

当前项目数据足够支持 WBR v1 主体：

```text
Sales & Traffic 可支撑周度销售/流量/转化。
Orders 已通过 historical backfill 补齐 2026-03 起主要历史，可支撑 SKU 级订单分析。
SKU Cost 已可通过 xlsx 维护，可支撑标准成本 COGS。
Inventory snapshot 已可定期刷新，可支撑库存风险。
Settlement 可作为 posted-date 财务 preview，但不适合作为 WBR 的唯一周度运营口径。
```

Ads 需要单独说明：

```text
当前真实库 amazon_ads_sp_campaign_daily 只有 2026-05-06 起数据。
因此 2026-03 / 2026-04 WBR 样本中 Ads API context 应被标记为 partial / missing context。
这不影响 WBR 的销售、流量、订单、SKU 成本和库存主体结论。
未来只要 core_rolling / weekly_full 按周期运行，5 月之后的 Ads campaign daily 应可进入周报加工。
```

### 8.3 当前已知限制

| 限制 | 影响 | v1 处理 |
|---|---|---|
| Settlement posted-date 不等于订单业务日期 | 周度财务金额不能视为最终利润 | WBR 只显示 `settlement_finance_preview`，不叫 final profit |
| Ads 归因会回填 | 最近几天广告销售可能变化 | 依赖 rolling refresh；WBR 使用上周完整自然周，建议周二生成 |
| Ads 历史报表可能存在可下载窗口限制 | 老月份 Ads API context 可能补不回来 | 不阻塞 WBR；对历史周标记 `ads_api_context_missing` |
| Sales & Traffic 最近 1-2 天可能延迟 | 今天/昨天不稳定 | WBR 只生成已过稳定截止日的周 |
| Orders `purchase_date_raw` 是 raw 字符串 | 周维度需要解析日期 | v1 按 ISO/UTC 解析；失败行进入 warning |
| SKU/SPU 主数据尚未建立 | 只能按 SKU 看，不按产品线 | v1 只按 `seller_sku`，未来可加 `product_group` 映射表 |
| 库存是快照，不是历史每日库存 | 周内库存变动不完整 | v1 使用最新 snapshot；Ledger 仅作补充说明 |

---

## 9. 稳定性规则

### 9.1 稳定截止日

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

### 9.2 建议生成前置动作

生成周报前应执行一次 `core_rolling`，完整周复盘前建议执行 `weekly_full`：

```powershell
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase submit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase collect --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase ingest --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase audit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --target-start-date 2026-03-01 --execute
```

每周完整复盘前建议运行 `weekly_full`，但 WBR v1 不强制要求所有慢源都完整。

---

## 10. 核心指标设计

### 10.1 Executive KPI Summary

| 指标 | 字段名 | 数据源 | 公式 | 说明 |
|---|---|---|---|---|
| Ordered Product Sales | `ordered_product_sales` | `amazon_sales_traffic_daily` | `SUM(ordered_product_sales_amount)` | 本周业务销售额主口径。 |
| Units Ordered | `units_ordered` | `amazon_sales_traffic_daily` | `SUM(units_ordered)` | 本周销售件数。 |
| Total Order Items | `total_order_items` | `amazon_sales_traffic_daily` | `SUM(total_order_items)` | 本周订单商品行/订单项数。 |
| Average Selling Price | `avg_selling_price` | Sales & Traffic | `ordered_product_sales / units_ordered` | 单件平均销售额。 |
| Sessions | `sessions` | `amazon_sales_traffic_daily` | `SUM(sessions)` | 本周访问 sessions。 |
| Page Views | `page_views` | `amazon_sales_traffic_daily` | `SUM(page_views)` | 本周页面浏览。 |
| Unit Session Percentage | `unit_session_percentage` | Sales & Traffic | `units_ordered / sessions` | 用汇总值重算转化率。 |
| Ads Spend | `ads_spend` | `amazon_ads_sp_campaign_daily` | `SUM(cost)` | 本周广告花费；无 Ads 数据时为 0/NULL 并 partial warning。 |
| Ads Sales 7d | `ads_sales_7d` | `amazon_ads_sp_campaign_daily` | `SUM(sales_7d)` | 7日归因广告销售。 |
| Ads Orders 7d | `ads_orders_7d` | `amazon_ads_sp_campaign_daily` | `SUM(purchases_7d)` | 7日归因购买数。 |
| ACOS | `acos` | Ads | `ads_spend / ads_sales_7d` | 广告销售成本比。 |
| ROAS | `roas` | Ads | `ads_sales_7d / ads_spend` | 广告投入产出比。 |
| TACOS | `tacos` | Sales + Ads | `ads_spend / ordered_product_sales` | 全店广告压力。 |
| Estimated COGS | `estimated_cogs` | Orders + SKU Cost | `SUM(order_units_by_sku * unit_standard_cost)` | 标准成本估算。 |
| Gross Margin Before Ads | `gross_margin_before_ads` | Sales + COGS | `ordered_product_sales - estimated_cogs` | 不含 Amazon 平台费/广告费。 |
| Contribution After COGS & Ads, before Amazon platform fees | `contribution_after_cogs_ads_before_amazon_fees` | Sales + COGS + Ads | `ordered_product_sales - estimated_cogs - ads_spend` | 广告和货本后贡献，未扣完整 Amazon referral/FBA/storage/other platform fees，不是净利润。 |
| Contribution Margin After COGS & Ads, before Amazon platform fees | `contribution_margin_after_cogs_ads_before_amazon_fees` | derived | `contribution_after_cogs_ads_before_amazon_fees / ordered_product_sales` | 用于周度趋势，不得称为最终净利率。 |
| Settlement Net Preview | `settlement_net_preview` | `amazon_settlement_transaction` | `SUM(amount)` by posted_date | posted-date 财务预览。 |

### 10.2 环比指标

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

## 11. 销售与流量模块

### 11.1 读取条件

```sql
FROM dbo.amazon_sales_traffic_daily
WHERE marketplace_id = @marketplace_id
  AND report_date BETWEEN @week_start AND @week_end
```

### 11.2 每日趋势字段

`02_Daily_Trend` sheet 应包含：

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
| `ads_spend` | Ads campaign daily 当日 `SUM(cost)` |
| `ads_sales_7d` | Ads campaign daily 当日 `SUM(sales_7d)` |
| `tacos` | `ads_spend / ordered_product_sales` |

### 11.3 质量检查

| 场景 | 处理 |
|---|---|
| 7 天不完整 | `needs_review`，列出 missing dates。 |
| `sessions = 0` | 转化率置 NULL，生成 warning。 |
| 销售额为 0 但 sessions > 0 | 生成 conversion warning。 |
| 单日销售额较前 7 日均值跌幅超过 50% | 生成 sales_drop warning。 |

---

## 12. Orders 与 SKU 模块

### 12.1 读取条件

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

### 12.2 SKU 销售字段

`04_SKU_Performance` sheet 应包含：

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

### 12.3 SKU 成本匹配规则

对于每个 `seller_sku`，用逐行订单日期匹配：

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

## 13. Ads 总览模块

### 13.1 读取条件

```sql
FROM dbo.amazon_ads_sp_campaign_daily
WHERE profile_id = @profile_id
  AND marketplace_id = @marketplace_id
  AND report_date BETWEEN @week_start AND @week_end
```

### 13.2 广告总览字段

`05_Ads_Overview` sheet 应包含总览区和 campaign 摘要区。总览字段：

| 字段 | 公式 |
|---|---|
| `ads_row_count` | `COUNT(*)` |
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

### 13.3 Campaign 摘要

按 `campaign_id + campaign_name` 聚合：

| 字段 | 公式 |
|---|---|
| `campaign_id` | `campaign_id` |
| `campaign_name` | `campaign_name` |
| `campaign_status` | 最新状态；如字段存在。 |
| `campaign_spend` | `SUM(cost)` |
| `campaign_sales_7d` | `SUM(sales_7d)` |
| `campaign_orders_7d` | `SUM(purchases_7d)` |
| `campaign_acos` | `campaign_spend / campaign_sales_7d` |
| `campaign_roas` | `campaign_sales_7d / campaign_spend` |
| `campaign_cpc` | `SUM(cost) / SUM(clicks)` |

WBR v1 只输出 campaign top summary。搜索词级 winners/losers 归 `Weekly Ads Optimization Report`。

### 13.4 广告质量检查

| 场景 | 默认阈值 | warning |
|---|---:|---|
| `ads_row_count = 0` 且本周处于 Ads 已知覆盖期之后 | - | `ads_api_context_missing` |
| `acos > target_acos` | 30% | `high_acos` |
| `tacos > target_tacos` | 20% | `high_tacos` |
| `ads_spend > 0 and ads_sales_7d = 0` | 任意 | `ads_spend_without_sales` |
| `clicks > 30 and purchases_7d = 0` | 30 clicks | `clicks_without_orders` |
| 广告花费环比上升 > 30%，销售额环比未上升 | 30% | `spend_up_sales_not_up` |

Ads 数据缺失时：

```text
不把 WBR 整体改成 no_data；
如果销售/订单/SKU 成本完整，则 status 可为 partial；
XLSX 05_Ads_Overview 写明 Ads API context missing；
07_Alerts_Actions 增加 warning；
08_Reconciliation_Checks 记录 ads coverage check。
```

---

## 14. SKU 广告与贡献模块

### 14.1 数据源

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

### 14.2 SKU 贡献字段

合并到 `04_SKU_Performance`：

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

### 14.3 SKU 排名

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

## 15. Inventory 风险模块

### 15.1 快照选择规则

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

### 15.2 库存指标

`06_Inventory_Risk` sheet 应包含：

| 字段 | 来源/公式 |
|---|---|
| `seller_sku` | Inventory / Orders SKU |
| `asin` | Inventory / Orders / Listing |
| `afn_fulfillable_quantity` | `amazon_inventory_daily.afn_fulfillable_quantity` |
| `afn_reserved_quantity` | `amazon_inventory_daily.afn_reserved_quantity` |
| `afn_unsellable_quantity` | `amazon_inventory_daily.afn_unsellable_quantity` |
| `afn_total_quantity` | `amazon_inventory_daily.afn_total_quantity` |
| `weekly_units_ordered` | Orders SKU units |
| `avg_daily_units_ordered_7d` | `weekly_units_ordered / 7` |
| `days_of_supply` | `afn_fulfillable_quantity / avg_daily_units_ordered_7d` |
| `inventory_value_at_cost` | `afn_total_quantity * unit_standard_cost` |
| `inventory_risk` | 按第 15.3 节分级 |

如果 `avg_daily_units_ordered_7d = 0`：

```text
days_of_supply = NULL
inventory_velocity_status = no_recent_sales
```

### 15.3 库存风险分级

| 风险 | 条件 |
|---|---|
| `stockout` | `afn_fulfillable_quantity = 0` 且 `weekly_units_ordered > 0` |
| `urgent_low_stock` | `days_of_supply < 14` |
| `watch_low_stock` | `14 <= days_of_supply < 30` |
| `healthy` | `30 <= days_of_supply <= 120` |
| `overstock_watch` | `days_of_supply > 120` 或 `weekly_units_ordered = 0 and afn_fulfillable_quantity > 0` |

---

## 16. Settlement 财务 preview 模块

### 16.1 读取条件

```sql
FROM dbo.amazon_settlement_transaction
WHERE marketplace_id = @marketplace_id
  AND is_settlement_summary = 0
  AND amount IS NOT NULL
  AND posted_date BETWEEN @week_start AND @week_end
```

`posted_date` 解析规则沿用 Monthly Financial Close / Profit Preview 的 Settlement posted-date 逻辑。

### 16.2 字段

| 字段 | 公式 | 说明 |
|---|---|---|
| `settlement_net_preview` | `SUM(amount)` | posted-date 维度本周净额。 |
| `settlement_product_sales` | `SUM(amount WHERE profit_bucket='product_sales')` | 如 bucket 可用。 |
| `settlement_advertising_fee` | `SUM(amount WHERE profit_bucket='advertising_cost')` 或对应 advertising bucket | 财务扣费口径广告费。 |
| `settlement_fba_fee` | `SUM(amount WHERE profit_bucket='fba_fee')` 或对应 fba bucket | FBA 配送/仓储相关。 |
| `settlement_refund_amount` | `SUM(amount WHERE transaction_type='Refund' OR profit_bucket='refund')` | posted-date 退款。 |
| `settlement_promotion_amount` | `SUM(amount WHERE profit_bucket IN ('promotion_cost','promotion_fee'))` | posted-date 促销。 |

### 16.3 使用原则

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

同时，WBR 必须额外解释广告费双口径：

```text
Ads API spend = 本周广告实际投放 report_date 口径，用于经营指标和 TACOS。
Settlement advertising fee = 本周 Seller Central posted-date 广告账单扣款，只做现金/账单提醒。
```

当某周出现大额 Settlement advertising fee，但 Ads API spend 不高时，应提示这是历史广告账单集中入账，不代表本周实际投放突然失控。

---

## 17. Alerts 与行动建议

### 17.1 默认阈值

| 阈值 | 默认值 | 说明 |
|---|---:|---|
| `target_acos` | 30% | 临时默认值；后续应由 SKU break-even ACOS / 产品毛利空间决定。 |
| `target_tacos` | 20% | 超过说明广告压力较大。 |
| `sales_drop_pct` | -20% | 销售额环比下降超过 20%。 |
| `conversion_drop_pct` | -20% | 转化率环比下降超过 20%。 |
| `high_refund_rate` | 10% | posted-date 退款占销售额。 |
| `low_stock_days` | 14 | 低库存紧急阈值。 |
| `watch_stock_days` | 30 | 库存观察阈值。 |
| `stale_inventory_days` | 7 | 库存快照过期。 |

### 17.2 Alert 规则

| Alert | 条件 | 建议动作 |
|---|---|---|
| `sales_drop` | 本周销售额环比下降 > 20% | 检查广告、价格、优惠券、库存、Buy Box。 |
| `conversion_drop` | 转化率环比下降 > 20% | 检查 listing、价格、评论、优惠券、图片。 |
| `high_tacos` | `tacos > target_tacos` | 降低低效广告预算，检查搜索词。 |
| `high_acos` | `acos > target_acos` | 下调高 ACOS campaign/target。 |
| `ads_spend_without_sales` | 广告花费 > 0 且广告销售为 0 | 检查投放词，必要时否定。 |
| `ads_api_context_missing` | Ads campaign daily 在本周无数据 | 检查 Ads rolling refresh / backfill，不影响 Sales & Traffic 主体周报。 |
| `sku_negative_contribution` | SKU 广告和货本后贡献 < 0 | 检查广告、促销、价格和成本；注意该指标未扣完整 Amazon 平台费。 |
| `missing_sku_cost` | SKU 无成本 | 先补 `amazon_sku_cost`，否则不输出成本结论。 |
| `stockout` | 可售库存为 0 且近期有销量 | 补货/关广告/避免浪费流量。 |
| `urgent_low_stock` | 库存天数 < 14 | 调整广告预算，准备补货或清仓策略。 |
| `overstock_watch` | 库存天数 > 120 或无销量 | 考虑促销、清仓、移除或降广告。 |
| `stale_inventory_snapshot` | 库存快照超过 7 天 | 先跑 inventory refresh。 |
| `settlement_refund_spike` | posted-date refund rate > 10% | 检查退货原因、质量、listing 误导。 |

### 17.3 Action List 输出格式

`07_Alerts_Actions` sheet 字段：

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

## 18. 数据质量与状态规则

### 18.1 报告状态

| 状态 | 条件 | 是否可用于运营决策 |
|---|---|---|
| `ok` | 核心数据覆盖完整，无缺 SKU 成本，无严重异常。 | 是 |
| `preview_unstable` | 周期未过稳定截止日，或 Ads/Sales 最近数据可能回填。 | 只做观察 |
| `needs_review` | 缺核心数据、缺 SKU 成本、关键字段解析失败。 | 需人工修复后再用 |
| `partial` | 非核心模块缺失，如 Ads context 缺失、库存快照过旧、Settlement preview 缺失。 | 可用，但需看 warning |
| `no_data` | 核心销售数据为空。 | 不可用 |

### 18.2 核心数据必需性

| 数据 | 必需性 | 缺失影响 |
|---|---|---|
| Sales & Traffic | 必需 | 没有销售/流量总览，报告 `no_data` 或 `needs_review`。 |
| Orders | 必需 | 无法做 SKU 和 COGS，报告 `needs_review`。 |
| SKU Cost | 必需 | 无法输出成本和贡献，报告 `needs_review`。 |
| Ads campaign | 重要 | 可生成销售周报，但广告模块 `partial`。 |
| Inventory snapshot | 重要 | 可生成周报，但库存模块 `partial`。 |
| Settlement | 可选 | 财务 preview 缺失，不阻塞 WBR。 |
| Promotion/Coupon | 可选 | 活动上下文缺失，不阻塞 WBR。 |

### 18.3 数据覆盖检查

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

## 19. 字段映射与公式总表

### 19.1 Summary 字段

| 输出字段 | 来源表/字段 | 公式/规则 |
|---|---|---|
| `marketplace_id` | 参数 | 原样输出。 |
| `profile_id` | 参数 | 原样输出。 |
| `week_start` | 参数 | 自动化默认必须为 Saturday；手动运行可指定其他 7 天窗口，但需与 WAOR 同步。 |
| `week_end` | derived | `week_start + 6 days`。 |
| `report_status` | derived | 按第 18 节规则。 |
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

### 19.2 SKU 字段

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
| `inventory_risk` | 按第 15 节分级。 |

---

## 20. 处理流程

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
  -> write JSON / XLSX
```

失败处理：

| 阶段 | 失败场景 | 处理 |
|---|---|---|
| 参数校验 | `week_start` 日期格式错误 | fail fast；自动化 wrapper 要求周六起始。 |
| 日期解析 | Orders 日期解析失败 | 记录 warning，失败行不参与 SKU 汇总。 |
| 成本匹配 | SKU 无成本 | `needs_review`，不输出正式贡献结论。 |
| 数据缺失 | Sales & Traffic 缺天 | `needs_review`。 |
| Ads 缺失 | Ads 缺天 | Ads 模块 partial，WBR 仍可生成。 |
| Inventory 过旧 | 快照超过 7 天 | partial + warning。 |

---

## 21. 幂等性设计

WBR v1 不写数据库，只写 runtime 输出文件。

同一参数重复执行：

```text
覆盖同一输出目录下的 JSON/XLSX 文件；
不新增数据库记录；
不影响 normalized 表；
输出应只随源数据更新而变化。
```

---

## 22. 验收标准

### 22.1 功能验收

第一版开发完成后，应能运行：

```powershell
python scripts/generate_weekly_business_review.py --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --week-start 2026-04-06 --dry-run
```

并输出：

```text
runtime/analysis_reports/weekly_business_review/ATVPDKIKX0DER/2026-04-06_2026-04-12/weekly_business_review_2026-04-06_2026-04-12.json
runtime/analysis_reports/weekly_business_review/ATVPDKIKX0DER/2026-04-06_2026-04-12/weekly_business_review_2026-04-06_2026-04-12.xlsx
```

XLSX 至少包含：

```text
01_Executive_Summary
02_Daily_Trend
03_Sales_Traffic
04_SKU_Performance
05_Ads_Overview
06_Inventory_Risk
07_Alerts_Actions
08_Reconciliation_Checks
09_Raw_Metadata
```

### 22.2 数字验收

1. `ordered_product_sales` 应等于 `amazon_sales_traffic_daily` 周内金额之和。
2. `units_ordered` 应等于 `amazon_sales_traffic_daily.units_ordered` 周内之和。
3. `ads_spend` 应等于 `amazon_ads_sp_campaign_daily.cost` 周内之和；若该周无 Ads API 数据，应明确 partial/warning。
4. `acos`、`roas`、`tacos` 应由汇总值重算，不使用源表已算百分比。
5. SKU COGS 应能追溯到 `amazon_sku_cost` 生效记录。
6. 库存天数应能追溯到最新 `amazon_inventory_daily` 快照。
7. 同一周重复生成，若源数据不变，输出数值应一致。

### 22.3 人工复核样本

建议先用以下自然周验收：

```text
2026-03-23 .. 2026-03-29
2026-03-30 .. 2026-04-05
2026-04-06 .. 2026-04-12
2026-04-13 .. 2026-04-19
2026-04-20 .. 2026-04-26
```

这些周适合验证 Sales & Traffic、Orders、SKU 成本和库存快照链路。由于当前 Ads campaign daily 真实覆盖从 2026-05-06 起，3/4 月样本的 Ads 模块应允许 partial。另建议额外用 2026-05-11 之后的完整周验证 Ads campaign daily 加工。

---

## 23. v1 实现与验证记录

本轮已实现 WBR v1 文件型报表：

```text
python scripts/generate_weekly_business_review.py \
  --marketplace-id ATVPDKIKX0DER \
  --profile-id 3917953989967300 \
  --week-start 2026-04-06 \
  --dry-run
```

默认输出：

```text
runtime/analysis_reports/weekly_business_review/{marketplace_id}/{week_start}_{week_end}/weekly_business_review_{week_start}_{week_end}.json
runtime/analysis_reports/weekly_business_review/{marketplace_id}/{week_start}_{week_end}/weekly_business_review_{week_start}_{week_end}.xlsx
```

验证命令：

```text
PYTHONPATH=src pytest tests/unit -q
python -m compileall -q scripts src tests
```

当前 sandbox 未安装 ruff，因此 `ruff check src tests scripts` 需在本地或 GitHub Action 中执行。

## 24. 后续版本

### v1.1

- 增加邮件草稿模板。
- 增加 PDF 摘要生成。
- 增加更完整的同比/月内累计对比。
- 增加 configurable thresholds 文件。

### v1.2

- 增加 SKU -> SPU / 产品线映射。
- 增加库存 Ledger movement 解释。
- 增加 Buy Box / Listing price 变化解释。
- 增加可选 `--export-csv` 调试输出。

### v2.0

- 增加结果表落库。
- 接入 Azure Container Apps Jobs 自动生成。
- 自动生成每周邮件草稿。
- 与 Weekly Ads Optimization Report 联动生成广告动作清单。

---

## 23.1 v1.1 口径更新实现记录

v1.1 已把 WBR 与月报 v1.2 对齐：

```text
1. 周期统一为 Saturday–Friday，周一生成和发送。
2. `contribution_after_ads` 重命名为 `contribution_after_cogs_ads_before_amazon_fees`，避免被误读为净利润。
3. 保留 Ads API report-date spend 作为广告经营指标主口径。
4. 新增 Settlement posted-date advertising fee 作为账单/现金流提醒，不参与本周经营贡献计算。
5. 后续 v2 再引入 estimated Amazon platform fees，形成更接近真实利润的 weekly operating contribution。
```

## 24. 当前冻结结论

WBR v1 冻结为：

```text
每周 Saturday–Friday 经营复盘；
主运营口径使用 Sales & Traffic；
SKU 维度使用 Orders + SKU Cost；
广告总览使用 Ads campaign daily；
SKU 广告贡献使用 Ads advertised product daily；
库存风险使用最新 Inventory snapshot；
Settlement 只做 posted-date finance preview 和广告账单提醒，不作为最终周利润；
不新增数据库表；
不自动发邮件；
默认输出 JSON + 单个 XLSX 多 sheet；
不默认输出 Markdown 或多个 CSV；
人工复核稳定后再实现 PDF / Email / Dashboard 自动化。
```

---

## Presentation language requirement

Default presentation artifacts must be bilingual:

```text
1. JSON keeps stable machine-readable English field names.
2. XLSX includes `00_Readme_说明` and bilingual fixed headers/labels.
3. Report delivery emails are Chinese-first with English reference text.
4. Amazon-native raw values such as campaign names, search terms, keywords, SKU/ASIN and raw IDs stay unchanged.
```
