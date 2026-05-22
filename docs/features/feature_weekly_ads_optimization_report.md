# Feature: Weekly Ads Optimization Report

> 文档状态：Design frozen / ready for implementation  
> 负责人：AI + Feng  
> 更新时间：2026-05-22  
> 功能状态：Design only  
> 相关数据接入文档：`docs/data_access/amazon_ads_reports_catalog.md`, `docs/data_access/sp_api_reports_catalog.md`, `docs/data_access/seller_central_manual_exports.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`  
> 相关功能：`docs/features/feature_ads_ingestion.md`, `docs/features/feature_weekly_business_review.md`, `docs/features/feature_monthly_financial_close_report.md`, `docs/features/feature_profit_calculation.md`, `docs/operations/manual_refresh_plan_workflow.md`, `docs/operations/data_refresh_policy.md`  
> 相关 ADR：`docs/adr/ADR-010-overlapping-refresh-weekly-analysis.md`, `docs/adr/ADR-009-settlement-led-profit-policy.md`

---

## 1. 功能摘要

Weekly Ads Optimization Report（每周广告优化报表，简称 WAOR）是 SellerDataPipeline 第三类管理层/运营报表，定位为广告投放动作清单。它不回答“本周最终赚了多少钱”，而是回答：

```text
广告钱花到哪里了？
哪些 campaign / keyword / search term 值得加码？
哪些 search term 花钱不出单，应该否词或降价？
广告是否正在吞噬经营利润？
下周广告应该做哪些具体动作？
```

WAOR 与另外两类报表的关系：

```text
Monthly Financial Close Report：财务最终口径，回答月度赚没赚钱。
Weekly Business Review：经营全局口径，回答本周业务健康度。
Weekly Ads Optimization Report：广告动作口径，回答下周广告怎么调。
```

第一版 WAOR 不调用 Amazon Ads 写接口，不自动修改 campaign、bid 或 negative keywords。它只读取已入库的 normalized Ads 表，生成 Markdown / JSON / CSV 文件，供人工复核后在 Amazon Ads Console 手动执行。

---

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认：三类管理报表为 Monthly Financial Close Report、Weekly Business Review、Weekly Ads Optimization Report。 |
| 设计状态 | 本文冻结 WAOR v1 设计到指标、字段、公式和动作规则级别。 |
| 数据源可用性 | 足够支持 v1：Sponsored Products campaign、targeting、search term、advertised product 日表已入库；2026-03-17 起 Ads 历史已完成 backfill。 |
| 数据刷新依赖 | 依赖 `core_rolling` 每 1-2 天刷新 Ads 最近 14 天；历史分析依赖 `backfill_ads_reports.py`。 |
| 数据库变更 | v1 不新增数据库表，不新增 migration。 |
| 代码实现 | 待开发。 |
| 输出形式 | v1 输出 Markdown / JSON / CSV；v1.1 可增加 xlsx。 |
| 验收样本 | 先以 `2026-03-17..2026-05-20` 的手动 Sponsored Products Search Term report 作为人工对照样本，再选 2026-04 起完整自然周做周报验收。 |

---

## 3. 业务目标

### 3.1 CEO / 运营负责人视角目标

WAOR 应帮助回答：

1. **广告整体是否健康**：Spend、Sales、ACOS、ROAS、TACOS 是否可接受。
2. **广告是否吃掉利润**：广告花费相对本周销售额、SKU 毛利和月度财务结果是否过高。
3. **哪些 campaign 应该加码**：低 ACOS、有订单、有稳定转化的 campaign / keyword / search term。
4. **哪些 campaign 应该降预算**：高花费、高 ACOS、无订单或低转化的对象。
5. **哪些 search term 应该否词**：花费达到阈值但无销售或无订单的真实搜索词。
6. **哪些 search term 应该收割为 exact keyword**：有稳定转化、ACOS 低、与现有 keyword 不完全相同的 search term。
7. **哪些 SKU 被广告消耗预算**：广告投放集中在哪些 ASIN/SKU，广告销售与 SKU 贡献是否匹配。
8. **下周广告动作是什么**：生成明确的 action candidates，人工确认后执行。

### 3.2 小公司阶段原则

当前公司体量小、资金有限，广告报表应以“少花冤枉钱”和“找到可复制的有效词”为第一目标：

```text
先减少明显浪费，再考虑扩大预算；
先做人工复核动作清单，不做自动调价/自动否词；
先分析 Sponsored Products，不扩 Sponsored Brands / Sponsored Display；
先用 SKU 标准成本做粗略利润视角，不做复杂广告归因利润模型；
先按自然周输出，避免日度噪声过大；
先服务美国站，再考虑其他 marketplace。
```

---

## 4. 范围与非范围

### 4.1 本功能包含

1. 生成指定自然周的 Sponsored Products 广告优化报表。
2. 汇总本周广告总览：Spend、Sales、Orders、ACOS、ROAS、CTR、CPC、CVR、TACOS。
3. 输出 campaign 级表现和动作建议。
4. 输出 targeting / keyword 级表现和动作建议。
5. 输出 search term 级 winner / loser / negative candidate / harvest candidate。
6. 输出 advertised SKU / ASIN 广告影响。
7. 输出广告与 Sales & Traffic 的交叉指标，例如 TACOS、广告销售占比。
8. 输出广告与 Settlement advertising fee 的财务口径差异提示。
9. 输出数据覆盖、稳定性、归因窗口和人工复核提醒。

### 4.2 本功能不包含

1. 不自动修改广告 campaign、bid、budget、negative keyword。
2. 不替代 Monthly Financial Close Report 的财务广告费口径。
3. 不把 Ads API `cost` 当作最终财务扣款；财务扣款仍看 Settlement。
4. 不做 Sponsored Brands / Sponsored Display。
5. 不做完整 bid optimization algorithm。
6. 不做预算 forecast 或库存约束下的自动分配。
7. 不新增数据库结果表。
8. 不自动发送邮件。
9. 不做复杂 SKU/SPU 主数据映射；v1 只按 `advertised_sku` / `advertised_asin` 和现有 SKU 成本辅助分析。
10. 不依赖 `spPurchasedProduct` 入库；当前项目尚未建立 purchased-product normalized 表。

---

## 5. 输入数据

### 5.1 读取表清单

| 数据域 | 表 | 用途 | v1 使用方式 |
|---|---|---|---|
| Ads campaign | `amazon_ads_sp_campaign_daily` | Campaign 日维度广告表现 | 广告总览与 campaign 主分析表 |
| Ads targeting | `amazon_ads_sp_targeting_daily` | Keyword / targeting 日维度广告表现 | keyword / target 动作建议 |
| Ads search term | `amazon_ads_sp_search_term_daily` | Shopper search term 日维度广告表现 | 否词、加 exact、观察词动作建议 |
| Ads advertised product | `amazon_ads_sp_advertised_product_daily` | Advertised SKU/ASIN 日维度表现 | SKU 广告影响与预算集中度 |
| Sales & Traffic | `amazon_sales_traffic_daily` | 周度总销售额、订单、sessions | TACOS、广告销售占比、经营上下文 |
| Orders | `amazon_order_item` | SKU 级订单数量和销售 | 辅助判断 SKU 总销量；不作为广告归因主口径 |
| SKU Cost | `amazon_sku_cost` | 单件标准成本 | SKU 广告贡献 proxy；非必需但建议可用 |
| Settlement | `amazon_settlement_transaction` | posted-date 财务广告费 | 用于财务广告费差异提示，不作为 Ads 优化主口径 |

### 5.2 Ads 表字段

#### 5.2.1 `amazon_ads_sp_campaign_daily`

核心字段：

```text
profile_id
marketplace_id
report_date
campaign_id
campaign_name
campaign_status
impressions
clicks
cost
sales_7d
purchases_7d
units_sold_clicks_7d
source_report_id
source_raw_file_path
updated_at
```

用途：

```text
本报表的广告总览主口径。
同一周期内 overall ads spend / sales / purchases / impressions / clicks 优先从 campaign 表汇总。
```

#### 5.2.2 `amazon_ads_sp_targeting_daily`

核心字段：

```text
profile_id
marketplace_id
report_date
campaign_id
campaign_name
ad_group_id
ad_group_name
keyword_id
keyword
match_type
targeting
impressions
clicks
cost
sales_7d
purchases_7d
units_sold_clicks_7d
```

用途：

```text
keyword / target 层分析。
用于判断哪些 keyword / target 应加价、降价、暂停或观察。
```

#### 5.2.3 `amazon_ads_sp_search_term_daily`

核心字段：

```text
profile_id
marketplace_id
report_date
campaign_id
campaign_name
ad_group_id
ad_group_name
keyword_id
keyword
match_type
targeting
search_term
impressions
clicks
cost
sales_7d
purchases_7d
units_sold_clicks_7d
```

用途：

```text
真实用户搜索词分析。
用于 negative candidate、harvest-to-exact candidate、winners、losers。
```

#### 5.2.4 `amazon_ads_sp_advertised_product_daily`

核心字段：

```text
profile_id
marketplace_id
report_date
campaign_id
campaign_name
ad_group_id
ad_group_name
advertised_asin
advertised_sku
impressions
clicks
cost
sales_7d
purchases_7d
units_sold_clicks_7d
```

用途：

```text
SKU/ASIN 广告影响。
用于判断广告预算是否集中在某些 SKU，以及 advertised SKU 的广告后贡献 proxy。
```

### 5.3 数据充分性判断

当前项目数据足够支持 WAOR v1：

```text
spCampaigns：可支撑整体广告总览与 campaign 排名。
spTargeting：可支撑 keyword / target 级调价和观察建议。
spSearchTerm：可支撑否词、加 exact、搜索词 winners/losers。
spAdvertisedProduct：可支撑 advertised SKU/ASIN 广告影响。
Sales & Traffic：可支撑 TACOS 和总销售上下文。
SKU Cost：可支撑 SKU 广告贡献粗略 proxy。
Settlement：可支撑财务广告费差异提示。
```

### 5.4 当前已知限制

| 限制 | 影响 | v1 处理 |
|---|---|---|
| Ads 归因销售会回填 | 最近几天 `sales_7d` / `purchases_7d` 可能变化 | 依赖 rolling refresh；周报建议周二或周三生成上一完整周 |
| Ads API cost 与 Settlement advertising fee 口径不同 | 不能直接对账完全一致 | 报表区分 `ads_api_spend` 与 `settlement_advertising_fee` |
| 四张 Ads 表是不同聚合粒度 | 不能把 campaign + search term + targeting 相加 | Overall 只用 campaign 表；其他表只做各自维度分析 |
| Search term 不能稳定映射到 SKU | 无法按 search term 精确算 SKU 利润 | v1 不做 search-term SKU 利润，只做广告效率 |
| `spPurchasedProduct` 未入库 | 无法分析“广告带来的实际购买 ASIN” | v1 不依赖；未来有非空样例后单独设计 |
| 报告中没有 bid / budget 字段 | 不能给出精确 bid 调整值 | v1 只给动作方向：increase / decrease / pause / add negative / harvest |
| 没有自动读取当前 negative keyword 列表 | 可能重复建议已否掉的词 | v1 标记为 candidate，需要人工复核；未来接入 negative list 后去重 |
| SKU 成本是标准成本 | SKU 广告贡献是估算，不是会计利润 | 明确标注为 proxy，不作为财务结论 |

---

## 6. 输出结果

### 6.1 输出目录

```text
runtime/analysis_reports/weekly_ads_optimization/{profile_id}/{week_start}_{week_end}/
```

示例：

```text
runtime/analysis_reports/weekly_ads_optimization/3917953989967300/2026-04-06_2026-04-12/
```

### 6.2 输出文件

| 文件 | 用途 |
|---|---|
| `weekly_ads_optimization.md` | 人工阅读主报告，包含总览、结论和动作建议。 |
| `weekly_ads_optimization.json` | 完整结构化结果，供后续 xlsx/email/BI 使用。 |
| `ads_overall_summary.csv` | 本周广告总览 KPI，一行或少量行。 |
| `campaign_performance.csv` | Campaign 级表现、排序和动作建议。 |
| `targeting_performance.csv` | Keyword / target 级表现和动作建议。 |
| `search_term_performance.csv` | Search term 全量聚合表现。 |
| `search_term_action_candidates.csv` | 否词、加 exact、观察词等动作候选。 |
| `advertised_product_performance.csv` | advertised SKU/ASIN 广告影响。 |
| `ads_daily_trend.csv` | 周内每日 spend、sales、ACOS、ROAS、clicks、impressions。 |
| `ads_reconciliation_checks.csv` | 数据覆盖、Ads vs Settlement、Ads vs Sales & Traffic 口径检查。 |
| `ads_action_items.csv` | 面向运营执行的统一动作清单。 |

### 6.3 CLI 设计

```powershell
python scripts/generate_weekly_ads_optimization_report.py `
  --marketplace-id ATVPDKIKX0DER `
  --profile-id 3917953989967300 `
  --week-start 2026-04-06 `
  --dry-run
```

可选参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--week-start` | 必填 | 自然周周一，格式 `YYYY-MM-DD`。 |
| `--week-end` | 自动 `week_start + 6 days` | v1 可内部计算，不必开放。 |
| `--target-acos` | `0.30` | 目标 ACOS；用于动作规则。 |
| `--watch-acos` | `0.40` | 观察 ACOS；超过进入 watch / reduce。 |
| `--target-tacos` | `0.20` | 目标 TACOS；用于整体周度健康检查。 |
| `--no-sale-cost-threshold` | `10.00` | 花费达到该值且无销售时进入否词/降价候选。 |
| `--no-order-click-threshold` | `12` | 点击达到该值且无订单时进入观察/否词候选。 |
| `--min-purchases-to-scale` | `2` | 进入加码候选的最小订单数。 |
| `--min-sales-to-scale` | `40.00` | 进入加码候选的最小广告销售额。 |
| `--low-ctr-threshold` | `0.002` | CTR 低于 0.2% 且曝光足够时提示相关性问题。 |
| `--low-cvr-threshold` | `0.03` | CVR 低于 3% 且点击足够时提示 listing / 价格 / 词相关性问题。 |
| `--high-cpc-multiplier` | `1.5` | CPC 高于整体均值该倍数时标记高 CPC。 |
| `--stable-lag-days` | `3` | Ads 最小稳定滞后天数；不足则 warning。 |
| `--output-dir` | 自动 | 自定义输出目录。 |

---

## 7. 周期与稳定性规则

### 7.1 自然周定义

WAOR 以自然周为最小单位：

```text
week_start = Monday
week_end = Sunday
```

示例：

```text
2026-04-06 .. 2026-04-12
```

### 7.2 建议生成时间

推荐：

```text
每周二或周三生成上一完整自然周。
```

原因：

```text
Ads API 的 sales_7d / purchases_7d 会随归因窗口回填；
周一立刻生成可能会低估周末广告销售；
周二/周三更适合运营决策，但仍应允许后续 rolling refresh 覆盖。
```

### 7.3 报表状态

| 状态 | 条件 | 含义 |
|---|---|---|
| `ok` | campaign/search term/targeting/advertised product 均覆盖 week_start..week_end，且 week_end <= today - stable_lag_days | 可用于运营动作。 |
| `reviewable_with_warnings` | 核心 Ads 表覆盖，但部分辅助数据缺失或 stable lag 不足 | 可看趋势，但动作需更谨慎。 |
| `needs_backfill` | campaign 或 search term 未覆盖完整周 | 不建议生成正式动作清单。 |
| `no_ads_data` | 指定周没有 Ads 数据 | 可能未投广告或数据缺失，需人工判断。 |

---

## 8. 指标、字段与公式

### 8.1 总览指标

汇总粒度：本周，来源 `amazon_ads_sp_campaign_daily`。

过滤条件：

```text
profile_id = 参数 profile_id
marketplace_id = 参数 marketplace_id
report_date between week_start and week_end
```

| 指标 | 字段/公式 | 说明 |
|---|---|---|
| `ads_spend` | `SUM(cost)` | Ads API 运营口径广告花费。 |
| `ads_sales_7d` | `SUM(sales_7d)` | 7 天归因广告销售额。 |
| `ads_purchases_7d` | `SUM(purchases_7d)` | 7 天归因购买次数。 |
| `ads_units_7d` | `SUM(units_sold_clicks_7d)` | 7 天点击归因售出件数。 |
| `impressions` | `SUM(impressions)` | 曝光。 |
| `clicks` | `SUM(clicks)` | 点击。 |
| `ctr` | `clicks / impressions` | 曝光到点击。 |
| `cpc` | `ads_spend / clicks` | 平均点击成本。 |
| `cvr` | `ads_purchases_7d / clicks` | 点击到购买。 |
| `acos` | `ads_spend / ads_sales_7d` | 花费销售比；sales=0 时为 null / infinite flag。 |
| `roas` | `ads_sales_7d / ads_spend` | 广告销售产出。 |
| `ordered_product_sales` | `SUM(amazon_sales_traffic_daily.ordered_product_sales)` | 同周总运营销售额。 |
| `tacos` | `ads_spend / ordered_product_sales` | 广告花费占总销售额。 |
| `ads_sales_share` | `ads_sales_7d / ordered_product_sales` | 广告销售额占总销售额，注意不同口径。 |
| `settlement_advertising_fee` | Settlement posted-date 中 advertising bucket 金额 | 财务扣款提示，不要求等于 Ads spend。 |

防除零规则：

```text
分母为 0 或 NULL 时，比例字段输出 NULL，同时给出 flag：division_by_zero / no_sales / no_clicks。
```

### 8.2 Campaign 指标

汇总粒度：`campaign_id + campaign_name`。

来源：`amazon_ads_sp_campaign_daily`。

| 指标 | 公式 |
|---|---|
| `campaign_spend` | `SUM(cost)` |
| `campaign_sales_7d` | `SUM(sales_7d)` |
| `campaign_purchases_7d` | `SUM(purchases_7d)` |
| `campaign_impressions` | `SUM(impressions)` |
| `campaign_clicks` | `SUM(clicks)` |
| `campaign_ctr` | `clicks / impressions` |
| `campaign_cpc` | `spend / clicks` |
| `campaign_cvr` | `purchases_7d / clicks` |
| `campaign_acos` | `spend / sales_7d` |
| `campaign_roas` | `sales_7d / spend` |
| `spend_share` | `campaign_spend / total_ads_spend` |
| `sales_share` | `campaign_sales_7d / total_ads_sales_7d` |

Campaign 级动作建议：

| 动作 | 条件 |
|---|---|
| `scale_candidate` | `purchases_7d >= min_purchases_to_scale` 且 `acos <= target_acos` 且 `sales_7d >= min_sales_to_scale` |
| `reduce_budget_or_bid_review` | `sales_7d > 0` 且 `acos > watch_acos` |
| `waste_review` | `sales_7d = 0` 且 `spend >= no_sale_cost_threshold` |
| `relevance_review` | `impressions >= 1000` 且 `ctr < low_ctr_threshold` |
| `conversion_review` | `clicks >= no_order_click_threshold` 且 `purchases_7d = 0` |
| `keep_observing` | 数据量不足，不给强动作。 |

### 8.3 Targeting / Keyword 指标

汇总粒度：

```text
campaign_id + ad_group_id + keyword_id + keyword + match_type + targeting
```

来源：`amazon_ads_sp_targeting_daily`。

字段和公式同 campaign，但增加：

| 指标 | 说明 |
|---|---|
| `keyword_text` | 优先 `keyword`，为空时用 `targeting`。 |
| `match_type` | broad / phrase / exact / targeting expression。 |
| `parent_campaign_name` | 用于人工在 Ads Console 定位。 |
| `parent_ad_group_name` | 用于人工在 Ads Console 定位。 |

Targeting 动作建议：

| 动作 | 条件 | 说明 |
|---|---|---|
| `increase_bid_review` | `purchases_7d >= min_purchases_to_scale` 且 `acos <= target_acos` | 建议加价或提高预算，但需看库存与利润。 |
| `decrease_bid_review` | `sales_7d > 0` 且 `acos > watch_acos` | 有转化但效率差，先降价而非直接否。 |
| `pause_or_negative_review` | `purchases_7d = 0` 且 `cost >= no_sale_cost_threshold` 且 `clicks >= no_order_click_threshold` | 需人工确认相关性。 |
| `listing_check` | `clicks >= no_order_click_threshold` 且 `ctr` 正常但 `purchases_7d = 0` | 可能是价格、主图、review、listing 问题。 |
| `low_relevance_check` | `impressions` 高但 `ctr` 低 | 可能关键词相关性弱。 |

### 8.4 Search Term 指标

汇总粒度：

```text
campaign_id + ad_group_id + keyword_id + search_term + keyword + match_type
```

来源：`amazon_ads_sp_search_term_daily`。

核心指标：

| 指标 | 公式 |
|---|---|
| `search_term_spend` | `SUM(cost)` |
| `search_term_sales_7d` | `SUM(sales_7d)` |
| `search_term_purchases_7d` | `SUM(purchases_7d)` |
| `search_term_clicks` | `SUM(clicks)` |
| `search_term_impressions` | `SUM(impressions)` |
| `search_term_ctr` | `clicks / impressions` |
| `search_term_cpc` | `spend / clicks` |
| `search_term_cvr` | `purchases_7d / clicks` |
| `search_term_acos` | `spend / sales_7d` |
| `search_term_roas` | `sales_7d / spend` |
| `waste_cost` | `spend` if `sales_7d = 0` else 0 |
| `potential_sales_efficiency` | `sales_7d - spend` | 仅作为粗略排序，不是利润。 |

Search Term 动作建议：

| 动作 | 条件 | 输出位置 |
|---|---|---|
| `negative_candidate` | `sales_7d = 0` 且 `purchases_7d = 0` 且 `cost >= no_sale_cost_threshold` | `search_term_action_candidates.csv` |
| `negative_candidate_clicks` | `purchases_7d = 0` 且 `clicks >= no_order_click_threshold` | `search_term_action_candidates.csv` |
| `harvest_to_exact_candidate` | `purchases_7d >= min_purchases_to_scale` 且 `acos <= target_acos` 且 `search_term` 与 `keyword` 不完全一致 | `search_term_action_candidates.csv` |
| `increase_bid_candidate` | `purchases_7d >= min_purchases_to_scale` 且 `acos <= target_acos` 且 `match_type = exact` | `search_term_action_candidates.csv` |
| `reduce_bid_candidate` | `sales_7d > 0` 且 `acos > watch_acos` | `search_term_action_candidates.csv` |
| `relevance_review` | `impressions >= 1000` 且 `ctr < low_ctr_threshold` | `search_term_action_candidates.csv` |
| `conversion_review` | `clicks >= no_order_click_threshold` 且 `purchases_7d = 0` | `search_term_action_candidates.csv` |
| `keep_monitoring` | 数据不足或表现中性 | `search_term_performance.csv` |

排序规则：

```text
negative candidates：先按 waste_cost DESC，再按 clicks DESC。
harvest candidates：先按 purchases_7d DESC，再按 acos ASC，再按 sales_7d DESC。
reduce candidates：先按 spend DESC，再按 acos DESC。
```

### 8.5 Advertised Product 指标

汇总粒度：

```text
advertised_sku + advertised_asin
```

来源：`amazon_ads_sp_advertised_product_daily`。

核心指标：

| 指标 | 公式 |
|---|---|
| `sku_ads_spend` | `SUM(cost)` |
| `sku_ads_sales_7d` | `SUM(sales_7d)` |
| `sku_ads_purchases_7d` | `SUM(purchases_7d)` |
| `sku_ads_units_7d` | `SUM(units_sold_clicks_7d)` |
| `sku_ads_acos` | `sku_ads_spend / sku_ads_sales_7d` |
| `sku_ads_roas` | `sku_ads_sales_7d / sku_ads_spend` |
| `unit_standard_cost` | `amazon_sku_cost.product_cost + first_mile_cost + packaging_cost + other_unit_cost` |
| `estimated_ads_cogs` | `sku_ads_units_7d * unit_standard_cost` |
| `ads_contribution_proxy` | `sku_ads_sales_7d - estimated_ads_cogs - sku_ads_spend` |

注意：

```text
ads_contribution_proxy 只是粗略经营 proxy。
它不是最终 SKU 广告利润，因为 Ads attribution sales 可能不是完全等于 advertised SKU 实际销售，也不包含 Amazon fulfillment/referral fees。
```

### 8.6 Ads 与经营上下文指标

来源：`amazon_sales_traffic_daily` + campaign table。

| 指标 | 公式 | 说明 |
|---|---|---|
| `ordered_product_sales` | Sales & Traffic `SUM(ordered_product_sales)` | 本周总销售额运营口径。 |
| `units_ordered` | Sales & Traffic `SUM(units_ordered)` | 总销量。 |
| `sessions` | Sales & Traffic `SUM(sessions)` | 总 sessions。 |
| `unit_session_percentage` | `units_ordered / sessions` | 转化率。 |
| `tacos` | `ads_spend / ordered_product_sales` | 广告对整体销售压力。 |
| `ads_sales_to_total_sales_ratio` | `ads_sales_7d / ordered_product_sales` | 广告销售占比，仅作趋势参考。 |
| `ads_spend_per_unit_ordered` | `ads_spend / units_ordered` | 每件销售承受广告费。 |

---

## 9. 口径规则与防重复规则

### 9.1 Overall Ads 只使用 Campaign 表

四张 Ads 表是同一广告数据的不同维度，不可相加。

错误做法：

```text
总广告费 = campaign.cost + search_term.cost + targeting.cost + advertised_product.cost
```

正确做法：

```text
总广告费 = SUM(amazon_ads_sp_campaign_daily.cost)
```

其他表只用于对应维度的明细分析。

### 9.2 Ads API 与 Settlement 的关系

WAOR 以 Ads API 为运营主口径：

```text
ads_api_spend = campaign table cost
ads_api_sales = campaign table sales_7d
```

Settlement advertising fee 只作为财务提示：

```text
settlement_advertising_fee = posted-date settlement 中 advertising 相关 bucket 金额
```

二者不要求完全一致，原因包括：

```text
账单入账时间不同；
广告归因窗口不同；
财务扣款周期不同；
Settlement 是 posted-date，Ads 是 report_date。
```

### 9.3 Search Term 动作不是自动执行

所有动作候选都必须人工复核：

```text
negative_candidate 不等于立即加否词；
harvest_to_exact_candidate 不等于立即新建 keyword；
increase_bid_candidate 不等于立即提价。
```

人工复核要考虑：

```text
搜索词是否与产品真实相关；
是否是品牌词、竞品词或宽泛词；
库存是否足够；
当前清仓目标是否允许更高 ACOS；
该词是否已有 exact keyword；
是否已在后台否定过。
```

---

## 10. 报告 Markdown 结构

`weekly_ads_optimization.md` 建议结构：

```text
# Weekly Ads Optimization Report

## 1. Executive Summary
- 本周广告是否健康
- Spend / Sales / ACOS / ROAS / TACOS
- 最大风险和最大机会
- 本周建议动作数量

## 2. Data Coverage & Status
- Ads 数据覆盖
- Sales & Traffic 覆盖
- Settlement advertising fee 差异提示
- 报表状态 ok / reviewable / needs_backfill

## 3. Ads Overall Performance
- 总花费、销售、订单、点击、曝光
- CTR / CPC / CVR / ACOS / ROAS / TACOS
- 与上一周对比

## 4. Campaign Performance
- Top spend campaigns
- Top sales campaigns
- High ACOS campaigns
- No-sales spend campaigns
- Scale / reduce / watch candidates

## 5. Search Term Optimization
- Winners: 有订单且低 ACOS
- Losers: 高花费无订单
- Negative candidates
- Harvest-to-exact candidates
- Relevance/conversion review candidates

## 6. Targeting / Keyword Optimization
- Keyword / target winners
- Keyword / target losers
- Bid review candidates

## 7. Advertised Product Impact
- SKU/ASIN 广告花费和广告销售
- 广告预算集中度
- SKU 广告贡献 proxy

## 8. Action Items for Next Week
- Add negative candidates
- Add exact candidates
- Decrease bid / pause review
- Increase bid / scale review
- Listing / price / image review

## 9. Appendix
- 口径说明
- 重要公式
- 文件清单
```

---

## 11. CSV 字段设计

### 11.1 `ads_overall_summary.csv`

| 字段 | 说明 |
|---|---|
| `marketplace_id` | Marketplace。 |
| `profile_id` | Ads profile。 |
| `week_start` | 周一。 |
| `week_end` | 周日。 |
| `report_status` | ok / reviewable / needs_backfill / no_ads_data。 |
| `ads_spend` | Campaign table cost。 |
| `ads_sales_7d` | Campaign table sales_7d。 |
| `ads_purchases_7d` | Campaign table purchases_7d。 |
| `ads_units_7d` | Campaign table units_sold_clicks_7d。 |
| `impressions` | Campaign table impressions。 |
| `clicks` | Campaign table clicks。 |
| `ctr` | clicks / impressions。 |
| `cpc` | spend / clicks。 |
| `cvr` | purchases / clicks。 |
| `acos` | spend / sales。 |
| `roas` | sales / spend。 |
| `ordered_product_sales` | Sales & Traffic 同周销售。 |
| `units_ordered` | Sales & Traffic 同周销量。 |
| `tacos` | spend / ordered_product_sales。 |
| `ads_sales_to_total_sales_ratio` | ads_sales_7d / ordered_product_sales。 |
| `settlement_advertising_fee` | Settlement posted-date advertising fee。 |
| `settlement_ads_diff` | settlement_advertising_fee + ads_spend，符号需在报表说明。 |
| `warning_count` | 警告数量。 |
| `action_count` | 动作候选数量。 |

### 11.2 `campaign_performance.csv`

| 字段 | 说明 |
|---|---|
| `campaign_id` | Campaign ID。 |
| `campaign_name` | Campaign name。 |
| `campaign_status` | 最新 campaign status。 |
| `spend` | 汇总 cost。 |
| `sales_7d` | 汇总 sales。 |
| `purchases_7d` | 汇总 purchases。 |
| `units_7d` | 汇总 units。 |
| `impressions` | 汇总 impressions。 |
| `clicks` | 汇总 clicks。 |
| `ctr` | click / impression。 |
| `cpc` | spend / click。 |
| `cvr` | purchase / click。 |
| `acos` | spend / sales。 |
| `roas` | sales / spend。 |
| `spend_share` | campaign spend / total spend。 |
| `sales_share` | campaign sales / total sales。 |
| `action_label` | scale_candidate / reduce_budget_or_bid_review / waste_review / keep_observing。 |
| `action_reason` | 触发原因。 |

### 11.3 `search_term_action_candidates.csv`

| 字段 | 说明 |
|---|---|
| `action_type` | negative_candidate / harvest_to_exact_candidate / reduce_bid_candidate / increase_bid_candidate / review。 |
| `priority` | high / medium / low。 |
| `campaign_name` | 定位用。 |
| `ad_group_name` | 定位用。 |
| `keyword` | 触发搜索词的 keyword。 |
| `match_type` | 匹配类型。 |
| `search_term` | 用户真实搜索词。 |
| `spend` | 搜索词花费。 |
| `sales_7d` | 搜索词销售。 |
| `purchases_7d` | 搜索词订单。 |
| `clicks` | 搜索词点击。 |
| `impressions` | 搜索词曝光。 |
| `acos` | 搜索词 ACOS。 |
| `roas` | 搜索词 ROAS。 |
| `reason` | 建议原因。 |
| `manual_review_note` | 人工复核提示。 |

### 11.4 `advertised_product_performance.csv`

| 字段 | 说明 |
|---|---|
| `advertised_sku` | Seller SKU。 |
| `advertised_asin` | ASIN。 |
| `ads_spend` | SKU 广告花费。 |
| `ads_sales_7d` | SKU 广告销售。 |
| `ads_purchases_7d` | SKU 广告订单。 |
| `ads_units_7d` | SKU 广告件数。 |
| `ads_acos` | ads_spend / ads_sales。 |
| `ads_roas` | ads_sales / ads_spend。 |
| `unit_standard_cost` | SKU 标准成本。 |
| `estimated_ads_cogs` | ads_units * unit cost。 |
| `ads_contribution_proxy` | ads_sales - estimated_cogs - ads_spend。 |
| `cost_status` | ok / missing_sku_cost / no_sku。 |
| `action_label` | scale / reduce / watch。 |

### 11.5 `ads_action_items.csv`

统一动作清单，供人工逐条处理：

| 字段 | 说明 |
|---|---|
| `priority` | high / medium / low。 |
| `action_type` | add_negative / add_exact / decrease_bid_review / increase_bid_review / pause_review / listing_review / monitor。 |
| `entity_type` | campaign / targeting / search_term / advertised_product。 |
| `campaign_name` | 定位字段。 |
| `ad_group_name` | 定位字段。 |
| `entity_text` | keyword/search term/SKU。 |
| `metric_summary` | 关键指标摘要。 |
| `reason` | 为什么建议。 |
| `suggested_manual_action` | 人工操作建议。 |
| `do_not_auto_apply` | v1 固定 true。 |

---

## 12. JSON 结构设计

`weekly_ads_optimization.json` 建议结构：

```json
{
  "metadata": {
    "marketplace_id": "ATVPDKIKX0DER",
    "profile_id": "3917953989967300",
    "week_start": "2026-04-06",
    "week_end": "2026-04-12",
    "generated_at_utc": "...",
    "report_status": "ok",
    "policy_version": "weekly_ads_optimization.v1"
  },
  "thresholds": {
    "target_acos": "0.30",
    "watch_acos": "0.40",
    "target_tacos": "0.20",
    "no_sale_cost_threshold": "10.00",
    "no_order_click_threshold": 12
  },
  "overall_summary": {},
  "daily_trend": [],
  "campaign_performance": [],
  "targeting_performance": [],
  "search_term_performance": [],
  "search_term_action_candidates": [],
  "advertised_product_performance": [],
  "action_items": [],
  "reconciliation_checks": [],
  "warnings": []
}
```

---

## 13. 数据覆盖和对账检查

### 13.1 Ads coverage checks

每张核心 Ads 表检查：

```text
min(report_date)
max(report_date)
distinct report_date count
是否覆盖 week_start..week_end
```

检查对象：

```text
amazon_ads_sp_campaign_daily
amazon_ads_sp_search_term_daily
amazon_ads_sp_targeting_daily
amazon_ads_sp_advertised_product_daily
```

如果 campaign 表缺失，本报表 `needs_backfill`。如果 search term 缺失，则仍可生成总览，但动作清单状态为 `needs_search_term_backfill`。

### 13.2 Cross-table sanity checks

由于四张表是不同维度，不要求金额完全相等，但应做 sanity check：

```text
campaign spend 与 search term spend 差异比例
campaign spend 与 targeting spend 差异比例
campaign spend 与 advertised product spend 差异比例
```

建议规则：

```text
如果差异 <= 2%，标记 ok。
如果差异 > 2% 且 <= 10%，标记 warning。
如果差异 > 10%，标记 needs_review。
```

注意：这只是数据完整性提示，不用任意一张表覆盖另一张表。

### 13.3 Ads vs Sales & Traffic checks

检查：

```text
ordered_product_sales 是否存在；
tacos 是否可计算；
ads_sales_7d 是否明显大于 total sales。
```

如果 `ads_sales_7d > ordered_product_sales * 1.2`，给 warning：

```text
Ads attributed sales may use a different attribution/date window from Sales & Traffic.
```

### 13.4 Ads vs Settlement checks

计算：

```text
settlement_advertising_fee_abs = ABS(SUM(settlement advertising fee))
ads_api_spend = SUM(campaign cost)
diff = settlement_advertising_fee_abs - ads_api_spend
```

输出说明：

```text
该差异不用于修正 Ads API spend，只用于财务口径提醒。
```

---

## 14. 实现设计

### 14.1 代码入口

新增脚本：

```text
scripts/generate_weekly_ads_optimization_report.py
```

职责：

```text
只负责 argparse、日志初始化、调用 service、打印输出路径。
```

### 14.2 服务层

建议新增：

```text
src/seller_data_pipeline/services/weekly_ads_optimization_service.py
```

职责：

```text
参数校验
日期窗口计算
读取 Ads/Sales/Settlement/SKU Cost 数据
聚合指标
计算动作标签
生成 warnings/reconciliation checks
写出 md/json/csv
```

### 14.3 Repository 层

v1 可先在 service 中用现有 DB helper 查询；如果查询变复杂，再新增：

```text
src/seller_data_pipeline/db/repositories/ads_analysis_repo.py
```

建议方法：

```text
fetch_campaign_daily(profile_id, marketplace_id, start_date, end_date)
fetch_targeting_daily(profile_id, marketplace_id, start_date, end_date)
fetch_search_term_daily(profile_id, marketplace_id, start_date, end_date)
fetch_advertised_product_daily(profile_id, marketplace_id, start_date, end_date)
fetch_sales_traffic_daily(marketplace_id, start_date, end_date)
fetch_sku_costs(marketplace_id, as_of_date)
fetch_settlement_advertising_fee(marketplace_id, start_date, end_date)
```

### 14.4 输出层

v1 可使用简单 writer：

```text
write_json(path, result)
write_csv(path, rows)
write_markdown(path, result)
```

未来如果月报、WBR、WAOR 都需要统一风格，可以抽象：

```text
src/seller_data_pipeline/reports/management_report_writer.py
```

---

## 15. 验收标准

### 15.1 单元测试

应覆盖：

1. CTR/CPC/CVR/ACOS/ROAS/TACOS 计算。
2. 除零和 null 处理。
3. Campaign action label 规则。
4. Targeting action label 规则。
5. Search term negative / harvest / reduce / watch 规则。
6. Advertised product contribution proxy。
7. Cross-table spend sanity check。
8. 缺 Ads coverage 时 report_status。
9. 输出 CSV 字段稳定。

### 15.2 手动验收

第一轮使用：

```text
2026-03-17..2026-05-20 手动 Sponsored Products Search Term report
```

核对：

```text
spSearchTerm 汇总 spend / clicks / impressions / sales / purchases 与手动报告一致或差异可解释。
```

第二轮使用完整自然周：

```text
2026-04-06..2026-04-12
2026-04-13..2026-04-19
2026-04-20..2026-04-26
```

验收：

```text
能生成 weekly_ads_optimization.md/json/csv；
overall spend 与 campaign 表汇总一致；
search_term_action_candidates 有合理排序；
不会把四张 Ads 表重复相加；
有高花费无销售搜索词时能进入 negative_candidate；
有低 ACOS 有订单搜索词时能进入 harvest_to_exact_candidate；
缺数据时状态不是 ok，而是 needs_backfill / reviewable_with_warnings。
```

### 15.3 运行命令验收

示例：

```powershell
python scripts/generate_weekly_ads_optimization_report.py --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --week-start 2026-04-06 --dry-run
```

应输出：

```text
runtime/analysis_reports/weekly_ads_optimization/3917953989967300/2026-04-06_2026-04-12/weekly_ads_optimization.md
runtime/analysis_reports/weekly_ads_optimization/3917953989967300/2026-04-06_2026-04-12/weekly_ads_optimization.json
runtime/analysis_reports/weekly_ads_optimization/3917953989967300/2026-04-06_2026-04-12/*.csv
```

---

## 16. 后续版本规划

### v1.1 xlsx 输出

增加：

```text
weekly_ads_optimization.xlsx
```

Sheet：

```text
Summary
Campaigns
Targeting
Search Terms
Action Items
Advertised Products
Reconciliation
```

### v1.2 Negative keyword 去重

接入 Amazon Ads negative keyword / negative targeting 列表，避免重复建议已否定的 search term。

### v1.3 Bid / Budget 当前值

接入 campaign budget、keyword bid、target bid，用于给出更具体的 bid adjustment suggestion。

### v1.4 自动生成 Ads Console 操作清单

输出人工可复制的操作表：

```text
Campaign
Ad group
Entity
Action
Suggested value
Reason
```

仍然不自动执行。

### v2.0 半自动广告调整

只有在人工流程稳定后，才考虑通过 Ads API 写入 negative keywords / bid changes。该阶段需要单独 ADR 和安全审批。

---

## 17. 当前结论

WAOR v1 的最佳实践口径冻结为：

```text
Campaign table = overall ads truth for this report.
Search term table = query optimization truth.
Targeting table = keyword/target optimization truth.
Advertised product table = SKU/ASIN ads impact truth.
Sales & Traffic = TACOS and business context.
Settlement = financial advertising-fee context only.
```

第一版最重要的交付不是复杂算法，而是稳定地产出：

```text
1. 广告整体健康度；
2. 高花费无销售 search term；
3. 低 ACOS 有订单 search term；
4. 需要降价/暂停/观察的 keyword/campaign；
5. 下周可执行的人工动作清单。
```

