# Feature: Weekly Reporting Pack Redesign

> 文档状态：Design frozen / implementation pending  
> 负责人：AI + Feng  
> 更新时间：2026-08-16  
> 目标版本：weekly reporting v2  
> 相关功能：`feature_weekly_business_review.md`, `feature_weekly_ads_optimization_report.md`, `feature_report_delivery_email.md`, `feature_sku_cost_management.md`  
> 相关 ADR：`ADR-010-overlapping-refresh-weekly-analysis.md`, `ADR-017-weekly-operating-and-ads-action-reporting.md`

---

## 1. 功能摘要

本功能重构 SellerDataPipeline 的两份周度经营报表：

```text
Weekly Business Review (WBR)
-> 给经营负责人看：本周业务哪里变好/变差，下周先做什么

Weekly Ads Optimization Report (WAOR)
-> 给广告操作者看：钱花在哪里，哪些动作值得执行
```

v2 不追求更多 Sheet，而追求：

```text
更可信：先修口径与 reconciliation，再展示贡献指标
更精简：删除重复/技术型默认 Sheet
更有参考价值：加入 4 周趋势、驱动诊断、SKU+库存联动、成熟广告归因
更可行动：默认首页直接给优先级、原因和下一步动作
```

JSON 继续作为机器可读 source of truth；XLSX 继续作为人工经营复盘和执行文件。

## 2. 当前版本审计结论

### 2.1 值得保留

- Saturday-Friday 的完整周周期。
- Sales & Traffic 作为周度总销售/流量主源。
- `amazon_sku_cost` effective-date 成本。
- Ads API `report_date` spend 作为广告投入主源。
- SKU 级销售、成本、广告和库存联动分析。
- 库存 days-of-supply / low-stock / overstock 风险逻辑。
- WAOR 的 campaign / targeting / search-term 分析和动作规则。
- negative keyword snapshot 的去重能力。
- JSON + XLSX 双产物。
- reconciliation / warning / fail-on-review 安全思想。
- report delivery / artifact store / audit log 基础设施。

### 2.2 当前必须修复的可信度问题

#### A. Orders 周期按 UTC 日期截取，而 Sales & Traffic 按 marketplace-local business date

当前 `weekly_business_review_repo.py` 直接把 `purchase_date_raw` 转为 SQL `date`，没有先转换成 marketplace timezone。

对于 US marketplace：

```text
marketplace_timezone = America/Los_Angeles
```

已知历史样本 `2026-04-06..2026-04-12`：

```text
Sales & Traffic: $1,177 / 49 units
Orders direct UTC-date: $1,132 / 47 units
Orders converted to America/Los_Angeles: $1,177 / 49 units
```

因此 v2 必须使用 marketplace-local purchase date 做 Orders 周期过滤和 effective-date cost 匹配。

#### B. Orders 没有 sales_channel 过滤

`amazon_order_item` 存在 `sales_channel`，真实数据中可能出现非目标渠道行。

US WBR 应仅纳入 marketplace metadata 对应的 expected marketplace names，例如：

```text
ATVPDKIKX0DER -> Amazon.com
```

非 Amazon.com 行不得进入 US WBR 的 SKU / COGS / contribution 计算。

#### C. 只有“Orders 有数据”检查，没有 Sales & Traffic ↔ Orders 金额/销量 reconciliation

当前 reconciliation 只确认 `order_rows > 0`。

这不足以证明 SKU/COGS 可用于经营判断。

已知样本 `2026-05-16..2026-05-22`：

```text
Sales & Traffic: $577 / 23 units
旧 Orders context: 约 $400.38 / 16 units
```

当 Orders 与 Sales & Traffic 明显不一致时，v2 必须 fail closed：

```text
总销售/流量仍可展示；
SKU、COGS、贡献指标标记 needs_review；
不得把不完整 Orders 成本当成可信经营贡献。
```

#### D. Ads 7-day attribution 被过早当作稳定数据

当前 WBR / WAOR 用同一最近周的：

```text
spend + sales_7d + purchases_7d
```

并以约 T-3 stable cutoff 判断可用。

但 7-day attribution 的 conversion metrics 在周末之后仍可能继续回填。

v2 拆成两个广告窗口：

```text
Recent Spend Context
= 本周 report_date spend / impressions / clicks / CTR / CPC / TACOS

Mature Conversion Action Window
= 前一完整周（默认 week_start-7 .. week_end-7）
= 用于 sales_7d / purchases_7d / CVR / ACOS / ROAS / search-term actions
```

最近周的 attributed sales 可保留为 provisional context，但不得驱动正式加价、降价、否词等动作。

## 3. WBR v2 业务目标

首页必须能在 1-2 分钟内回答：

1. 本周销售、销量、流量、转化是涨还是跌？
2. 变化主要来自流量、转化、价格/产品组合，还是库存？
3. 广告投入是否同步变化，广告负担是否变重？
4. 产品本身 gross margin 是否变化？
5. 哪些 SKU 是增长来源，哪些 SKU 正在亏贡献或有库存风险？
6. 下周最重要的 3-5 个经营动作是什么？

WBR 不承担最终财务定账职责。

## 4. WBR v2 默认工作簿

文件名保持：

```text
weekly_business_review_{week_start}_{week_end}.xlsx
```

默认只保留 4 个 Sheet：

```text
01_周度经营总览
02_SKU经营与库存
03_日趋势与广告
04_核验与口径
```

删除默认独立 Sheet：

```text
00_Readme_说明
03_Sales_Traffic
05_Ads_Overview
06_Inventory_Risk
07_Alerts_Actions
08_Reconciliation_Checks
09_Raw_Metadata
```

删除的是默认展示，不删除 JSON / normalized table / audit evidence。

## 5. `01_周度经营总览`

### 5.1 核心 KPI

默认展示当前周、前一周、WoW，并在首页附最近 4 周趋势。

核心指标：

| 指标 | 口径 |
|---|---|
| 商品销售额 | Sales & Traffic ordered product sales |
| 销量 | Sales & Traffic units ordered |
| Sessions | Sales & Traffic |
| 转化率 | units / sessions |
| 平均售价 | sales / units |
| 退款件数 / 退款率 | Sales & Traffic |
| Ads Spend | Ads API report-date cost |
| 广告费率 | Ads Spend / Product Sales |
| Product Gross Margin | `(Sales - landed COGS) / Sales`，仅在 Orders reconciliation 通过时可信 |
| Operating Contribution Proxy | `Sales - landed COGS - Ads Spend`，明确标注未扣完整 Amazon fees / refunds / account fees |
| Contribution Proxy Margin | proxy / Sales |

`Operating Contribution Proxy` 不得叫“经营利润”或“净利润”。

### 5.2 经营驱动诊断

v2 新增 deterministic diagnosis：

```text
Traffic Driver      -> sessions 变化
Conversion Driver   -> conversion 变化
Price/Mix Driver    -> ASP 变化
Ads Pressure        -> ads spend ratio / spend trend
Inventory Constraint-> low-stock / zero-stock SKU
```

首页输出 3-5 条最有决策价值的结论，不输出技术 warning 文本。

示例：

```text
销售 -31%，Sessions 仅 -6%，主要问题来自转化率下降。
广告费基本持平，但销售下降，广告费率显著升高。
Top SKU A 贡献占比过高，且库存仅约 12 天，需要优先补货。
```

### 5.3 最近 4 周趋势

默认展示：

- Product Sales
- Units
- Sessions
- Conversion Rate
- ASP
- Ads Spend
- Ads Spend Ratio
- Product Gross Margin（仅可信周）
- Contribution Proxy（仅可信周）

4 周趋势比只看一周 WoW 更适合识别偶发波动与连续恶化。

### 5.4 经营动作

首页只输出最高优先级 3-5 项，例如：

- listing / conversion review
- price / coupon review
- ad budget efficiency review
- low-stock replenish
- overstock promotion / ad push
- SKU negative contribution review

完整技术检查不放首页。

## 6. `02_SKU经营与库存`

把原 `SKU_Performance` 与 `Inventory_Risk` 合并。

每 SKU 默认保留：

```text
seller_sku
asin
product_name
units
order_sales_estimate
ASP
product_cost
first_mile_cost
landed_cogs
gross_margin_before_ads
gross_margin_rate
recent_ads_spend
contribution_proxy_before_full_amazon_fees
fulfillable_qty
reserved_qty
unsellable_qty
days_of_supply
inventory_value_at_cost
inventory_risk
priority_action
```

排序原则：

```text
critical risk
-> negative contribution
-> low stock
-> high sales contribution
-> overstock
-> normal
```

如果 Sales & Traffic ↔ Orders reconciliation 未通过：

- SKU 行仍可用于排查；
- monetary contribution 字段明确标记 provisional / needs_review；
- 首页不得引用其 contribution 作为可靠结论。

## 7. `03_日趋势与广告`

合并原 Daily Trend + Ads Overview 的决策信息。

每日默认：

```text
date
sales
units
sessions
conversion
ASP
ads_spend
ads_spend_ratio
impressions
clicks
CTR
CPC
```

不在“最近周日趋势”中把未成熟 `sales_7d / ACOS / ROAS` 当正式结论。

下方可附 Top campaigns recent-spend context：

```text
campaign
status
spend
spend_share
impressions
clicks
CTR
CPC
```

深度 action 归 WAOR。

## 8. `04_核验与口径`

集中承载原来的 Readme / Reconciliation / Warnings / Raw Metadata。

必须包含：

### 8.1 核心 reconciliation gates

```text
sales_traffic_date_coverage
orders_local_date_timezone
orders_sales_channel_filter
orders_vs_sales_traffic_sales
orders_vs_sales_traffic_units
sku_cost_coverage
ads_recent_date_coverage
inventory_snapshot_freshness
stable_cutoff
```

### 8.2 Orders ↔ Sales & Traffic gate

默认建议：

```text
Sales amount:
abs(diff) <= max($5, 1% of S&T sales)

Units:
abs(diff) <= 1 unit
```

超过容差：

```text
status = needs_review
SKU/COGS/contribution = not trusted
--fail-on-review => non-zero
```

容差应集中配置并可测试，不散落在 writer。

### 8.3 口径说明

必须明确：

- marketplace timezone；
- expected sales channel；
- Sales & Traffic 是总销售/流量主源；
- Orders 仅在 reconciliation 通过后用于 SKU/COGS；
- Ads spend 使用 recent report_date；
- contribution proxy 未扣完整 Amazon fees；
- Settlement 不再作为 WBR 默认首页指标。

## 9. WAOR v2 业务目标

WAOR 首页必须回答：

1. 最近一周广告花费是否上升？
2. 广告负担占总销售多少？
3. 成熟归因窗口里的 ACOS / ROAS / CVR 是否健康？
4. 本周最值得执行的 5-10 个动作是什么？
5. 哪些词应否定、哪些词应收割 exact、哪些 targeting 应降价/加价？
6. 哪些建议已经通过 negative snapshot 判定为“已做”，避免重复操作？

## 10. WAOR v2 双窗口

### 10.1 Recent Spend Window

```text
recent_start = WBR week_start
recent_end   = WBR week_end
```

用于：

- spend
- impressions
- clicks
- CTR
- CPC
- recent spend by campaign
- TACOS / Ads Spend Ratio（相对同周 S&T sales）

### 10.2 Mature Conversion Window

默认：

```text
mature_start = recent_start - 7 days
mature_end   = recent_end - 7 days
```

用于：

- attributed sales_7d
- purchases_7d
- CVR
- ACOS
- ROAS
- targeting/search-term action rules
- scale / reduce / negative / harvest recommendations

报告必须同时显示两个窗口日期，避免把不同时间口径混在一起。

## 11. WAOR v2 默认工作簿

默认压缩为 5 个 Sheet：

```text
01_广告周度总览
02_优先动作
03_Campaign与Targeting
04_SearchTerms
05_核验与口径
```

不再默认独立展示：

```text
00_Readme_说明
02_Daily_Trend（recent trend 合并进总览）
07_Advertised_Products（关键 SKU 广告信息在 WBR SKU sheet 和总览体现）
09_Historical_Paused_Lessons
10_Reconciliation_Checks
11_Warnings
12_Negative_Snapshot
13_Raw_Metadata
```

Historical paused lessons、negative snapshot、raw metadata 继续保留在 JSON / audit context；negative snapshot 继续参与去重。

## 12. `01_广告周度总览`

### Recent Spend Context

- Spend
- WoW Spend
- Total Sales
- Ads Spend Ratio / TACOS
- Impressions
- Clicks
- CTR
- CPC

### Mature Conversion Context

- Mature attributed sales
- Purchases
- CVR
- ACOS
- ROAS

### Action Summary

- high priority actions
- negative candidates
- harvest-to-exact candidates
- reduce-bid candidates
- scale candidates
- estimated waste spend covered by action candidates

首页最多给 5 条核心广告结论。

## 13. `02_优先动作`

统一 campaign / targeting / search-term / SKU action 为一张执行清单。

字段：

```text
priority
entity_type
campaign
ad_group
entity_text
action_type
recent_spend_context
mature_metric_summary
reason
suggested_manual_action
already_done_flag
confidence
```

排序：

```text
high -> medium -> low
then estimated waste / impact descending
```

默认只纳入 active/currently actionable entity；paused historical lesson 不占默认动作列表。

## 14. `03_Campaign与Targeting`

保留 campaign 和 targeting 的详细复核能力，但突出成熟窗口的 conversion metrics。

建议统一字段并增加 `entity_type`，便于筛选。

## 15. `04_SearchTerms`

保留全量 search term 明细，因为它对否词/收割仍有直接执行价值。

默认优先排序：

```text
actionable first
-> spend descending
-> sales descending
```

保留：

- keyword/targeting context
- search term
- spend
- clicks
- sales_7d
- purchases_7d
- ACOS
- CVR
- action
- negative snapshot matched flag

## 16. `05_核验与口径`

合并：

- recent window coverage
- mature window coverage
- campaign vs targeting/search-term spend sanity
- Ads profile/marketplace
- attribution-window explanation
- warnings
- source row counts
- generated time

fail-on-review 的核心原则：

```text
Recent spend data incomplete -> report needs_review
Mature action data incomplete -> action list needs_review / do not execute
Cross-table material spend mismatch -> needs_review
```

## 17. 周报 delivery 原则

第一阶段不改变现有 recipient routing 和防重复发送机制。

继续生成两个独立 report type：

```text
weekly_business_review
weekly_ads_optimization
```

先保证内容和口径正确，再评估是否合并成“一封周报邮件 + 两附件”。

这避免把展示重构和邮件路由变更一次性耦合。

## 18. 不进入本次 v2 的内容

- 不做自动 Ads API 写操作。
- 不自动修改 bid / budget / negative keyword。
- 不做复杂库存预测模型。
- 不做 FIFO。
- 不把 Settlement 变成周度经营利润主源。
- 不做 LLM 自动文本生成；首期用 deterministic rules。
- 不新增数据库表，除非实现阶段证明无法通过现有 normalized 数据支持。

## 19. 实施顺序

```text
1. 修 Orders marketplace-local date
2. 加 expected sales_channel filter
3. 加 S&T vs Orders sales/units reconciliation gate
4. 重构 WBR v2 数据模型和 4-sheet writer
5. WAOR recent/mature 双窗口
6. 重构 WAOR v2 5-sheet writer/action list
7. 更新 delivery template 文案
8. 单元测试
9. 历史 golden validation
10. Azure preview
11. production rollout
```

## 20. Golden validation

至少使用以下样本：

### WBR timezone golden

```text
2026-04-06..2026-04-12
S&T expected: $1,177 / 49 units
Orders marketplace-local should reconcile to same period
```

### WBR fail-closed golden

```text
2026-05-16..2026-05-22
必须验证旧版 Orders mismatch 被新 reconciliation gate 正确识别/解释；
不得在 mismatch 未解决时静默信任 SKU/COGS contribution。
```

### WAOR attribution golden

选取 Ads campaign/targeting/search-term/advertised-product 数据均完整的周：

```text
recent window -> spend/traffic context
previous mature window -> conversion/action metrics
```

必须确认 action 不再由未成熟 recent `sales_7d/purchases_7d` 驱动。

## 21. 验收标准

v2 只有在以下条件全部满足后才能切生产：

- marketplace-local Orders date 已测试；
- expected sales channel 已测试；
- Sales & Traffic ↔ Orders reconciliation gate 已测试；
- missing cost 仍 fail closed；
- WBR 4 Sheet contract 固定；
- WAOR 5 Sheet contract 固定；
- recent/mature Ads window 在 JSON/XLSX 中显式；
- negative action dedupe 不回归；
- existing report delivery / artifact store / duplicate-send guard 不回归；
- historical golden weeks 通过；
- Azure preview 通过后才改 production image。
