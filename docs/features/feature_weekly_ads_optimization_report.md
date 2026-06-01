# Feature: Weekly Ads Optimization Report

> 文档状态：Implemented / pending live verification  
> 负责人：AI + Feng  
> 更新时间：2026-06-01  
> 功能状态：Implemented / v1.1 active-action 与 negative snapshot 已完成代码对齐，待新周期 live verification  
> 相关数据接入文档：`docs/data_access/amazon_ads_reports_catalog.md`, `docs/data_access/sp_api_reports_catalog.md`, `docs/data_access/seller_central_manual_exports.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`  
> 相关功能：`docs/features/feature_ads_ingestion.md`, `docs/features/feature_weekly_business_review.md`, `docs/features/feature_monthly_financial_close_report.md`, `docs/features/feature_profit_calculation.md`, `docs/operations/manual_refresh_plan_workflow.md`, `docs/operations/data_refresh_policy.md`  
> 相关 ADR：`docs/adr/ADR-010-overlapping-refresh-weekly-analysis.md`, `docs/adr/ADR-009-settlement-led-profit-policy.md`

---

## 1. 功能摘要

Weekly Ads Optimization Report（每周广告优化报表，简称 WAOR）是 SellerDataPipeline 第三类管理/运营报表，定位为 **广告动作清单**。它不回答“本周最终赚了多少钱”，也不替代 Weekly Business Review 的全局经营复盘，而是回答：

```text
广告钱花到哪里了？
哪些 campaign / keyword / search term 值得加码？
哪些 search term 花钱不出单，应该否词、降价或观察？
广告是否正在吞噬经营利润？
下周广告应该做哪些具体动作？
```

WAOR 与另外两类报表的关系：

```text
Monthly Financial Close Report：财务最终口径，回答月度赚没赚钱。
Weekly Business Review：经营全局口径，回答本周业务健康度。
Weekly Ads Optimization Report：广告动作口径，回答下周广告怎么调。
```

第一版 WAOR 不调用 Amazon Ads 写接口，不自动修改 campaign、bid、budget、negative keywords。它只读取已入库的 normalized Ads 表，生成 JSON + 单个 XLSX 多 sheet 文件，供人工复核后在 Amazon Ads Console 手动执行。

---

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认：三类管理报表为 Monthly Financial Close Report、Weekly Business Review、Weekly Ads Optimization Report。 |
| 设计状态 | 本文将 WAOR v1 输出形式优化为 JSON + 单个 XLSX 多 sheet，并冻结到指标、字段、公式和动作规则级别。 |
| 数据源可用性 | 足够支持 v1：Sponsored Products campaign、targeting、search term、advertised product 日表已入库；2026-05-11..2026-05-17 已通过 backfill/collect/ingest 验证 Ads 数据可加工。 |
| 数据刷新依赖 | 依赖 `core_rolling` 每 1-2 天刷新 Ads 最近 14 天；历史分析依赖 `backfill_ads_reports.py`。 |
| 数据库变更 | v1 不新增数据库表，不新增 migration。 |
| 代码实现 | 已完成 v1/v1.1：`scripts/generate_weekly_ads_optimization_report.py`、`weekly_ads_optimization_service.py`、`weekly_ads_optimization_repo.py`、unit tests；已支持 active action / historical paused lessons 拆分和 negative keyword snapshot 去重。 |
| 输出形式 | v1 默认输出 `weekly_ads_optimization_{week_start}_{week_end}.json` + `weekly_ads_optimization_{week_start}_{week_end}.xlsx`；不默认输出 Markdown 或多个 CSV。 |
| 验收样本 | 第一轮使用 `2026-05-11..2026-05-17`，该周 Ads campaign/targeting/search term/advertised product 已成功入库；必要时再用后续完整自然周复核。 |

### 2.1 与前两份报表一致的输出原则

Monthly Financial Close Report 和 Weekly Business Review 已调整为：

```text
JSON = 机器可读、可用于后续 PDF / Email / Dashboard 的标准结构化结果。
XLSX = 人可读、可筛选、可人工复核和执行的多 sheet 文件。
```

WAOR v1 采用同一原则：

```text
默认只输出：weekly_ads_optimization_{week_start}_{week_end}.json + weekly_ads_optimization_{week_start}_{week_end}.xlsx。
不默认输出：weekly_ads_optimization.md 或多个 ads_*.csv。
```

如未来有外部系统需要单表 CSV，可通过后续 `--export-csv` 参数单独扩展，不作为 v1 默认行为。

---

## 3. 业务目标

### 3.1 CEO / 运营负责人视角目标

WAOR 应帮助回答：

1. **广告整体是否健康**：Spend、Sales、ACOS、ROAS、TACOS 是否可接受。
2. **广告是否吃掉利润**：广告花费相对本周销售额、SKU 标准毛利和月度财务结果是否过高。
3. **哪些 campaign 应该加码**：低 ACOS、有订单、有稳定转化的 campaign / keyword / search term。
4. **哪些 campaign 应该降预算**：高花费、高 ACOS、无订单或低转化对象。
5. **哪些 search term 应该否词**：花费达到阈值但无销售或无订单的真实搜索词。
6. **哪些 search term 应该收割为 exact keyword**：有稳定转化、ACOS 低、与现有 keyword 不完全相同的 search term。
7. **哪些 SKU 被广告消耗预算**：广告投放集中在哪些 ASIN/SKU，广告销售与 SKU 贡献是否匹配。
8. **下周广告动作是什么**：生成明确 action candidates，人工确认后执行。

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
5. 输出 search term 级 winners / losers / negative candidates / harvest candidates。
6. 输出 advertised SKU / ASIN 广告影响。
7. 输出广告与 Sales & Traffic 的交叉指标，例如 TACOS、广告销售占比。
8. 输出广告与 Settlement advertising fee 的财务口径差异提示。
9. 区分当前启用广告的可执行动作与已暂停广告的历史复盘，避免把已经停掉的 campaign 混入本周操作清单。
10. 接入 negative keyword / negative targeting 快照，避免重复建议已经加过的否定词。
9. 区分当前启用广告的可执行动作与已暂停广告的历史复盘，避免把已经停掉的 campaign 混入本周操作清单。
10. 接入 negative keyword / negative targeting 快照，避免重复建议已经加过的否定词。
9. 输出数据覆盖、稳定性、归因窗口和人工复核提醒。
10. 生成统一 action items sheet，方便运营逐条处理。

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
| SKU Cost | `amazon_sku_cost` | 单件标准成本 | SKU 广告贡献 proxy；缺失时 warning，不阻断整体广告动作 |
| Settlement | `amazon_settlement_transaction` | posted-date 财务广告费 | 用于财务广告费差异提示，不作为 Ads 优化主口径 |

### 5.2 Ads 表核心字段

#### 5.2.1 `amazon_ads_sp_campaign_daily`

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

### 5.3 当前已知限制

| 限制 | 影响 | v1 处理 |
|---|---|---|
| Ads 归因销售会回填 | 最近几天 `sales_7d` / `purchases_7d` 可能变化 | 依赖 rolling refresh；周报建议周二或周三生成上一完整周 |
| 3/4 月 Ads campaign daily 可能缺历史数据 | 早期周不适合作为 WAOR 验收样本 | 第一轮验收优先使用 2026-05-11 起的完整周 |
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
runtime/analysis_reports/weekly_ads_optimization/3917953989967300/2026-05-11_2026-05-17/
```

### 6.2 默认输出文件

| 文件 | 用途 |
|---|---|
| `weekly_ads_optimization_{week_start}_{week_end}.json` | 完整结构化结果；后续 PDF、Email、BI、自动预警的 source of truth。 |
| `weekly_ads_optimization_{week_start}_{week_end}.xlsx` | 人工复核和运营执行文件；所有明细通过不同 sheet 承载。 |

v1 不默认输出 Markdown 或多个 CSV：

```text
不输出 weekly_ads_optimization.md
不输出 ads_overall_summary.csv / campaign_performance.csv / search_term_action_candidates.csv 等多个碎片 CSV
```

### 6.3 XLSX sheet 设计

| Sheet | 用途 | 典型粒度 |
|---|---|---|
| `01_Executive_Summary` | 本周广告总体健康度、核心 KPI、结论和阈值 | 指标行 |
| `02_Daily_Trend` | 周内每日 spend/sales/ACOS/ROAS/TACOS 走势 | date |
| `03_Campaigns` | Campaign 表现、排序和动作建议 | campaign |
| `04_Targeting` | Keyword / targeting 表现和动作建议 | campaign + ad group + keyword/target |
| `05_Search_Terms` | Search term 全量聚合表现 | campaign + ad group + search_term |
| `06_Search_Term_Actions` | 否词、加 exact、降价、观察等 search term 候选 | action candidate |
| `07_Advertised_Products` | advertised SKU/ASIN 广告影响和贡献 proxy | advertised_sku + advertised_asin |
| `08_Active_Action_Items` | 当前启用广告的统一动作清单 | action item |
| `09_Historical_Paused_Lessons` | 已暂停/已结束广告的历史复盘项 | lesson / wasted spend |
| `10_Reconciliation_Checks` | 数据覆盖、cross-table sanity、Ads vs Sales/Settlement 检查 | check |
| `11_Warnings` | 警告和人工复核提示 | warning |
| `12_Raw_Metadata` | 参数、生成时间、数据源、row counts、策略版本 | metadata |

### 6.4 CLI 设计

```powershell
python scripts/generate_weekly_ads_optimization_report.py `
  --marketplace-id ATVPDKIKX0DER `
  --profile-id 3917953989967300 `
  --week-start 2026-05-11 `
  --dry-run
```

可选参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--week-start` | 必填 | 7天报表周期起始日，格式 `YYYY-MM-DD`；自动化周报默认使用周六起始，统计周六到周五。 |
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

### 6.5 `--dry-run` 行为

v1 不写数据库、不调用外部写接口，因此 `--dry-run` 定义为：

```text
只读数据库、不执行任何外部副作用，但仍生成 weekly_ads_optimization_{week_start}_{week_end}.json 和 weekly_ads_optimization_{week_start}_{week_end}.xlsx，方便人工复核。
```

如未来需要只打印摘要不写文件，可另加 `--no-write-files`，不复用 `--dry-run`。

---

## 7. 周期与稳定性规则

### 7.1 自然周定义

WAOR 以 7 天为最小单位。自动化默认采用 Saturday–Friday，与 WBR 和 Report Delivery 对齐：

```text
week_start = Saturday
week_end = Friday
```

示例：

```text
2026-05-16 .. 2026-05-22
```

### 7.2 建议生成时间

推荐：

```text
每周一生成上一完整 Saturday–Friday 周期。
```

周一生成前应先跑 weekly_full 或至少 core_rolling，确保 Ads 最近回填已经入库。手动运行可以指定其他 7 天窗口，但 WAOR 必须和 WBR 使用同一窗口，便于一起复盘。

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
| `settlement_advertising_fee_abs` | Settlement posted-date 中 advertising bucket 绝对值 | 财务扣款提示，不要求等于 Ads spend。 |

防除零规则：

```text
分母为 0 或 NULL 时，比例字段输出 NULL，同时给出 flag：division_by_zero / no_sales / no_clicks。
```

### 8.2 Campaign 指标与动作

汇总粒度：`campaign_id + campaign_name`。来源：`amazon_ads_sp_campaign_daily`。

| 指标 | 公式 |
|---|---|
| `spend` | `SUM(cost)` |
| `sales_7d` | `SUM(sales_7d)` |
| `purchases_7d` | `SUM(purchases_7d)` |
| `units_7d` | `SUM(units_sold_clicks_7d)` |
| `impressions` | `SUM(impressions)` |
| `clicks` | `SUM(clicks)` |
| `ctr` | `clicks / impressions` |
| `cpc` | `spend / clicks` |
| `cvr` | `purchases_7d / clicks` |
| `acos` | `spend / sales_7d` |
| `roas` | `sales_7d / spend` |
| `spend_share` | `spend / total_ads_spend` |
| `sales_share` | `sales_7d / total_ads_sales_7d` |

Campaign 动作建议：

| 动作 | 条件 |
|---|---|
| `scale_candidate` | `purchases_7d >= min_purchases_to_scale` 且 `acos <= effective_target_acos` 且 `sales_7d >= min_sales_to_scale` |
| `reduce_budget_or_bid_review` | `sales_7d > 0` 且 `acos > watch_acos` |
| `waste_review` | `sales_7d = 0` 且 `spend >= no_sale_cost_threshold` |
| `relevance_review` | `impressions >= 1000` 且 `ctr < low_ctr_threshold` |
| `conversion_review` | `clicks >= no_order_click_threshold` 且 `purchases_7d = 0` |
| `keep_observing` | 数据量不足，不给强动作。 |

### 8.3 Targeting / Keyword 指标与动作

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
| `increase_bid_review` | `purchases_7d >= min_purchases_to_scale` 且 `acos <= effective_target_acos` | 建议加价或提高预算，但需看库存与利润。 |
| `decrease_bid_review` | `sales_7d > 0` 且 `acos > watch_acos` | 有转化但效率差，先降价而非直接否。 |
| `pause_or_negative_review` | `purchases_7d = 0` 且 `cost >= no_sale_cost_threshold` 且 `clicks >= no_order_click_threshold` | 需人工确认相关性。 |
| `listing_check` | `clicks >= no_order_click_threshold` 且 `ctr` 正常但 `purchases_7d = 0` | 可能是价格、主图、review、listing 问题。 |
| `low_relevance_check` | `impressions` 高但 `ctr` 低 | 可能关键词相关性弱。 |

### 8.4 Search Term 指标与动作

汇总粒度：

```text
campaign_id + ad_group_id + keyword_id + search_term + keyword + match_type
```

来源：`amazon_ads_sp_search_term_daily`。

核心指标：

| 指标 | 公式 |
|---|---|
| `spend` | `SUM(cost)` |
| `sales_7d` | `SUM(sales_7d)` |
| `purchases_7d` | `SUM(purchases_7d)` |
| `clicks` | `SUM(clicks)` |
| `impressions` | `SUM(impressions)` |
| `ctr` | `clicks / impressions` |
| `cpc` | `spend / clicks` |
| `cvr` | `purchases_7d / clicks` |
| `acos` | `spend / sales_7d` |
| `roas` | `sales_7d / spend` |
| `waste_cost` | `spend` if `sales_7d = 0` else 0 |
| `potential_sales_efficiency` | `sales_7d - spend`，仅作粗略排序，不是利润 |

Search Term 动作建议：

| 动作 | 条件 | 输出位置 |
|---|---|---|
| `negative_candidate` | `sales_7d = 0` 且 `purchases_7d = 0` 且 `cost >= no_sale_cost_threshold`，且未被 negative snapshot 覆盖 | `06_Search_Term_Actions` / `08_Active_Action_Items` |
| `negative_candidate_clicks` | `purchases_7d = 0` 且 `clicks >= no_order_click_threshold`，且未被 negative snapshot 覆盖 | `06_Search_Term_Actions` / `08_Active_Action_Items` |
| `harvest_to_exact_candidate` | `purchases_7d >= min_purchases_to_scale` 且 `acos <= effective_target_acos` 且 `search_term` 与 `keyword` 不完全一致，且未被 negative snapshot 覆盖 | `06_Search_Term_Actions` / `08_Active_Action_Items` |
| `increase_bid_candidate` | `purchases_7d >= min_purchases_to_scale` 且 `acos <= effective_target_acos` 且 `match_type = exact` | `06_Search_Term_Actions` / `08_Active_Action_Items` |
| `reduce_bid_candidate` | `sales_7d > 0` 且 `acos > watch_acos` | `06_Search_Term_Actions` / `08_Active_Action_Items` |
| `relevance_review` | `impressions >= 1000` 且 `ctr < low_ctr_threshold` | `06_Search_Term_Actions` / `08_Active_Action_Items` |
| `conversion_review` | `clicks >= no_order_click_threshold` 且 `purchases_7d = 0` | `06_Search_Term_Actions` / `08_Active_Action_Items` |
| `keep_monitoring` | 数据不足或表现中性 | `05_Search_Terms` |

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

### 9.4 Active actions 与历史复盘分离

WAOR v1.1 起，动作清单必须分为两类：

```text
Active Campaign Action Items = 当前 enabled / delivering / out of budget 的 campaign、ad group、target、search term，作为本周优先执行清单。
Historical / Paused Campaign Lessons = 已 paused / archived / ended 的对象，仅作为复盘，不要求本周操作。
```

原因：广告优化执行者通常只想处理当前仍在花钱的广告；已暂停 campaign 的历史亏损词如果混进 Action Items，会干扰执行优先级。

### 9.5 Negative keyword snapshot 去重

WAOR v1.1 起，应读取或导入 negative keyword / negative targeting 快照，包括：

```text
Campaign negative keywords
Ad group negative keywords
Campaign negative product targeting / if available
Ad group negative product targeting / if available
```

第一阶段可以支持 Amazon Ads 手动导出的 CSV；后续再接 Ads API 只读快照。

Search term action 输出必须增加：

```text
already_negative = true/false
negative_scope = campaign/ad_group/none
negative_match_type = negative_exact/negative_phrase/none
recommended_action = already_done / add_negative_exact / add_negative_phrase / reduce_bid / harvest_to_exact / observe
```

如果 `already_negative = true`，则不再重复建议添加否定词，只在备注中说明该动作已完成。

### 9.6 Target ACOS 与 break-even ACOS

`target_acos = 30%` 只能作为临时默认值。长期应按 SKU 或产品的广告前利润空间决定：

```text
break_even_acos = pre_ad_unit_profit / selling_price
pre_ad_unit_profit = selling_price - unit_cogs - estimated_amazon_platform_fees - expected_promotion_or_refund_reserve
effective_target_acos = MIN(config_target_acos, sku_break_even_acos * safety_ratio)
```

在 SKU 成本和平台费估算未完全接入前，报表可先展示默认阈值，并在 notes 中标记 `target_acos_is_default=true`。

---

## 10. JSON 结构设计

`weekly_ads_optimization_{week_start}_{week_end}.json` 是后续 PDF / Email / Dashboard 的结构化 source of truth。建议结构：

```json
{
  "metadata": {
    "report_type": "weekly_ads_optimization",
    "version": "v1.0",
    "marketplace_id": "ATVPDKIKX0DER",
    "profile_id": "3917953989967300",
    "week_start": "2026-05-11",
    "week_end": "2026-05-17",
    "generated_at_utc": "...",
    "report_status": "ok",
    "policy_version": "weekly_ads_optimization.v1"
  },
  "thresholds": {
    "target_acos": "0.30",
    "watch_acos": "0.40",
    "target_acos_is_default": true,
    "effective_target_acos_policy": "min(config_target_acos, sku_break_even_acos * safety_ratio) when available",
    "target_acos_is_default": true,
    "effective_target_acos_policy": "min(config_target_acos, sku_break_even_acos * safety_ratio) when available",
    "target_tacos": "0.20",
    "no_sale_cost_threshold": "10.00",
    "no_order_click_threshold": 12,
    "min_purchases_to_scale": 2,
    "min_sales_to_scale": "40.00"
  },
  "executive_summary": {
    "headline": "...",
    "key_points": [],
    "recommended_next_steps": []
  },
  "overall_summary": {},
  "daily_trend": [],
  "campaign_performance": [],
  "targeting_performance": [],
  "search_term_performance": [],
  "search_term_action_candidates": [],
  "advertised_product_performance": [],
  "negative_keyword_snapshot": {
    "campaign_negative_keywords": [],
    "ad_group_negative_keywords": [],
    "coverage_status": "missing|partial|ok"
  },
  "negative_keyword_snapshot": {
    "campaign_negative_keywords": [],
    "ad_group_negative_keywords": [],
    "coverage_status": "missing|partial|ok"
  },
  "action_items": [],
  "reconciliation_checks": [],
  "warnings": [],
  "output_files": {}
}
```

JSON 与 XLSX 的关系：

```text
JSON 保留完整嵌套结构和文本摘要，供程序生成 PDF/邮件。
XLSX 将 JSON 中的核心数组扁平化到多个 sheet，供人工筛选、排序、执行。
两者来自同一个内存结果对象，不应互相反推。
```

---

## 11. XLSX 字段设计

### 11.1 `01_Executive_Summary`

字段：

| 字段 | 说明 |
|---|---|
| `metric_group` | overall / sales_context / actions / status / thresholds。 |
| `metric_name` | 指标名称。 |
| `value` | 指标值。 |
| `unit` | USD / ratio / count / status。 |
| `notes` | 说明。 |

必须包含：

```text
report_status
ads_spend
ads_sales_7d
ads_purchases_7d
acos
roas
ordered_product_sales
tacos
settlement_advertising_fee_abs
campaign_count
action_item_count
negative_candidate_count
harvest_candidate_count
warning_count
```

### 11.2 `02_Daily_Trend`

字段：

```text
report_date
ads_spend
ads_sales_7d
ads_purchases_7d
ads_units_7d
impressions
clicks
ctr
cpc
cvr
acos
roas
ordered_product_sales
tacos
```

### 11.3 `03_Campaigns`

字段：

```text
campaign_id
campaign_name
campaign_status
spend
sales_7d
purchases_7d
units_7d
impressions
clicks
ctr
cpc
cvr
acos
roas
spend_share
sales_share
action_label
action_priority
action_reason
```

### 11.4 `04_Targeting`

字段：

```text
campaign_id
campaign_name
ad_group_id
ad_group_name
keyword_id
keyword
match_type
targeting
keyword_text
spend
sales_7d
purchases_7d
units_7d
impressions
clicks
ctr
cpc
cvr
acos
roas
action_label
action_priority
action_reason
manual_review_note
```

### 11.5 `05_Search_Terms`

字段：

```text
campaign_id
campaign_name
ad_group_id
ad_group_name
keyword_id
keyword
match_type
targeting
search_term
spend
sales_7d
purchases_7d
units_7d
impressions
clicks
ctr
cpc
cvr
acos
roas
waste_cost
potential_sales_efficiency
action_label
action_reason
```

### 11.6 `06_Search_Term_Actions`

字段：

```text
action_type
priority
campaign_name
ad_group_name
keyword
match_type
search_term
spend
sales_7d
purchases_7d
clicks
impressions
acos
roas
reason
suggested_manual_action
manual_review_note
do_not_auto_apply
```

### 11.7 `07_Advertised_Products`

字段：

```text
advertised_sku
advertised_asin
ads_spend
ads_sales_7d
ads_purchases_7d
ads_units_7d
ads_acos
ads_roas
unit_standard_cost
estimated_ads_cogs
ads_contribution_proxy
cost_status
action_label
action_reason
```

### 11.8 `08_Active_Action_Items`

当前启用广告动作清单，供人工逐条处理：

```text
priority
action_type
entity_type
campaign_name
ad_group_name
entity_id
entity_text
metric_summary
reason
suggested_manual_action
manual_review_note
do_not_auto_apply
```

`do_not_auto_apply` 在 v1 固定为 true。

字段应增加：

```text
entity_status
already_negative
negative_scope
negative_match_type
```

### 11.9 `09_Historical_Paused_Lessons`

本 sheet 用于复盘已 paused / archived / ended 的 campaign、ad group、target 或 search term。它帮助理解历史浪费来自哪里，但默认不作为本周操作清单。

建议列：

```text
entity_type
campaign_name
ad_group_name
keyword_or_search_term
match_type
status
spend
sales_7d
purchases_7d
acos
lesson_type
recommended_future_guardrail
notes
```

### 11.10 `10_Reconciliation_Checks`

字段：

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

### 11.11 `11_Warnings`

字段：

```text
warning_code
severity
message
related_entity_type
related_entity_id
related_source
```

### 11.12 `12_Raw_Metadata`

字段：

```text
report_type
version
marketplace_id
profile_id
week_start
week_end
generated_at_utc
source_tables
row_counts
thresholds
output_files
```

---

## 12. 数据覆盖和对账检查

### 12.1 Ads coverage checks

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

### 12.2 Cross-table sanity checks

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

### 12.3 Ads vs Sales & Traffic checks

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

### 12.4 Ads vs Settlement checks

计算：

```text
settlement_advertising_fee_abs = ABS(SUM(settlement advertising fee))
ads_api_spend = SUM(campaign cost)
diff = settlement_advertising_fee_abs - ads_api_spend
```

输出说明：

```text
该差异不用于修正 Ads API spend，只用于财务口径提醒。若 Settlement advertising fee 本周大幅高于 Ads API spend，应提示可能是历史广告账单集中 posted，不代表本周投放突然失控。若 Settlement advertising fee 本周大幅高于 Ads API spend，应提示可能是历史广告账单集中 posted，不代表本周投放突然失控。
```

---

## 13. 实现设计

### 13.1 代码入口

新增脚本：

```text
scripts/generate_weekly_ads_optimization_report.py
```

职责：

```text
argparse
参数校验
dry-run 语义说明
调用 service
打印 report_status、核心 KPI、warning/action 计数和输出路径
```

### 13.2 服务层

建议新增：

```text
src/seller_data_pipeline/services/weekly_ads_optimization_service.py
```

职责：

```text
日期窗口计算
读取 Ads/Sales/Settlement/SKU Cost 数据
聚合指标
计算动作标签
生成 warnings/reconciliation checks
构造 WeeklyAdsOptimizationResult
写出 JSON/XLSX
```

### 13.3 Repository 层

建议新增：

```text
src/seller_data_pipeline/db/repositories/weekly_ads_optimization_repo.py
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

### 13.4 输出层

v1 输出：

```text
write_json(path, result)
write_xlsx(path, result)
```

不要让 XLSX 反推 JSON，也不要让 JSON 再反推 XLSX。推荐流程：

```text
数据库查询
  -> WeeklyAdsOptimizationResult 内存对象
  -> 同时输出 weekly_ads_optimization_{week_start}_{week_end}.json 和 weekly_ads_optimization_{week_start}_{week_end}.xlsx
```

这样可以保证 JSON 和 XLSX 数字一致，后续 PDF / Email 也可直接复用同一个结果对象。

---

## 14. 验收标准

### 14.1 单元测试

应覆盖：

1. CTR/CPC/CVR/ACOS/ROAS/TACOS 计算。
2. 除零和 null 处理。
3. Campaign action label 规则。
4. Targeting action label 规则。
5. Search term negative / harvest / reduce / watch 规则。
6. Advertised product contribution proxy。
7. Cross-table spend sanity check。
8. 缺 Ads coverage 时 report_status。
9. JSON/XLSX 输出字段稳定。

### 14.2 手动验收

第一轮使用完整自然周：

```text
2026-05-11..2026-05-17
```

该周已完成数据链路验证：

```text
Sales & Traffic backfill/collect/ingest 成功；
Ads spCampaigns / spTargeting / spSearchTerm / spAdvertisedProduct / spPurchasedProduct backfill/collect 成功；
Ads normalized ingestion 成功写入 campaign/targeting/search term/advertised product daily 表；
Weekly Business Review 对该周生成 status=ok，说明 5 月后 Ads context 已可用于周度加工。
```

WAOR 验收：

```text
能生成 weekly_ads_optimization_{week_start}_{week_end}.json 和 weekly_ads_optimization_{week_start}_{week_end}.xlsx；
overall spend 与 campaign 表汇总一致；
search_term_action_candidates 有合理排序；
不会把四张 Ads 表重复相加；
有高花费无销售搜索词时能进入 negative_candidate；
有低 ACOS 有订单搜索词时能进入 harvest_to_exact_candidate；
缺数据时状态不是 ok，而是 needs_backfill / reviewable_with_warnings。
```

### 14.3 运行命令验收

示例：

```powershell
python scripts/generate_weekly_ads_optimization_report.py --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --week-start 2026-05-11 --dry-run
```

应输出：

```text
runtime/analysis_reports/weekly_ads_optimization/3917953989967300/2026-05-11_2026-05-17/weekly_ads_optimization_2026-05-11_2026-05-17.json
runtime/analysis_reports/weekly_ads_optimization/3917953989967300/2026-05-11_2026-05-17/weekly_ads_optimization_2026-05-11_2026-05-17.xlsx
```

---

## 15. 后续版本规划

### v1.1 Active action 与 Negative keyword 去重（已实现）

- Action Items 已拆分为 `08_Active_Action_Items` 和 `09_Historical_Paused_Lessons`。
- 已支持 Amazon Ads negative keyword / negative targeting 数据或手动 CSV 快照，避免重复建议已否定的 search term。
- Search term actions 已增加 `already_negative`、`negative_scope`、`negative_match_type`、`recommended_action` 字段。
- CLI 已支持 `--negative-keyword-csv`，可重复传入多个 Amazon Ads negative keyword 导出文件。

### v1.2 Bid / Budget 当前值与 break-even ACOS

接入 campaign budget、keyword bid、target bid，并引入 SKU break-even ACOS / effective target ACOS，用于给出更具体的 bid adjustment suggestion。

### v1.3 自动生成 Ads Console 操作清单

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

## 16. v1 / v1.1 实现结果

本轮已完成 WAOR v1/v1.1 代码实现：

```text
scripts/generate_weekly_ads_optimization_report.py
src/seller_data_pipeline/services/weekly_ads_optimization_service.py
src/seller_data_pipeline/db/repositories/weekly_ads_optimization_repo.py
tests/unit/services/test_weekly_ads_optimization_service.py
tests/unit/db/test_weekly_ads_optimization_repo.py
```

实现结果：

```text
默认输出 weekly_ads_optimization_{week_start}_{week_end}.json + weekly_ads_optimization_{week_start}_{week_end}.xlsx；
XLSX 使用 12 个 sheet 承载总览、daily trend、campaign、targeting、search term、active 动作清单、历史复盘、对账和 metadata；
不新增数据库表，不新增 migration，不调用 Ads 写接口；
单元测试 fixture 使用 2026-05-11 起自然周；
本地验证：PYTHONPATH=src pytest tests/unit -q 通过，python -m compileall -q scripts src tests 通过；
当前 sandbox 未安装 ruff，需在本地/CI 继续执行 ruff check。
```

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
5. 下周可执行的人工动作清单；
6. 当前启用广告的 action 与历史暂停广告复盘分开展示；
7. 已存在否定词不重复建议。
```

v1 默认输出 JSON + 单个 XLSX 多 sheet，不默认输出 Markdown 或多个 CSV。实现时不新增数据库表，不新增 migration，不调用任何 Ads 写接口。

---

## Presentation language requirement

Default presentation artifacts must be bilingual:

```text
1. JSON keeps stable machine-readable English field names.
2. XLSX includes `00_Readme_说明` and bilingual fixed headers/labels.
3. Report delivery emails are Chinese-first with English reference text.
4. Amazon-native raw values such as campaign names, search terms, keywords, SKU/ASIN and raw IDs stay unchanged.
```
