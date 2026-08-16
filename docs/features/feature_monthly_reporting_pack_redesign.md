# Feature: Monthly Reporting Pack Redesign

> 文档状态：Design frozen / implementation pending  
> 负责人：AI + Feng  
> 更新时间：2026-08-16  
> 功能状态：Implemented locally / pending Azure validation  
> 相关数据接入文档：`docs/data_access/seller_central_manual_exports.md`, `docs/data_access/amazon_ads_reports_catalog.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`  
> 相关功能：`feature_monthly_financial_close_report.md`, `feature_finances_api_natural_month_ledger.md`, `feature_monthly_executive_pnl_landed_cogs.md`, `feature_sku_cost_management.md`  
> 相关 ADR：`ADR-015-natural-month-management-pnl.md`, `ADR-016-separate-monthly-operating-report-and-accounting-workbook.md`

---

## 1. 功能摘要

本功能重构 Monthly Financial Close 的**展示与交付层**，不修改 v1.90.3 已生产验证的自然月 Management P&L 财务公式。

新版月度交付拆成两个面向不同用户的 XLSX：

```text
月度经营报告 -> 给经营负责人 / 董事会
会计月度底稿 -> 给会计 / 做账辅助
```

目标是减少历史多 Sheet 大一统报表的重复与技术噪音，同时保持所有关键金额可追溯、可核验、可从 normalized ledger / raw transaction 找回。

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认 |
| 设计样表 | 已完成：2026-07 经营月报样例 + 2026-05 会计底稿样例 |
| May/Jun/Jul Seller Central reconciliation | 已完成，核心金额逐项可解释一致 |
| 数据库变更 | 不需要 |
| Report writer 代码 | 已实现：新增3-Sheet经营月报 writer |
| Accounting workbook generator | 已实现：新增4-Sheet会计底稿 writer |
| Delivery 两附件支持 | 已实现：月报优先发送经营月报 + 会计底稿 |
| 单元测试 | 已通过：完整 unit suite 372 passed |
| 本地 artifact 验收 | 已完成代码级生成/结构验证；待真实Azure数据preview |
| Azure monthly rollout | 待执行 |
| 文档同步 | 已同步本地实现状态 |

## 3. 业务目标

### 3.1 月度经营报告

使用者：公司经营负责人、董事会/股东。

必须快速回答：

1. 本月卖了多少、赚了多少？
2. 产品本身毛利有没有恶化？
3. 最终经营利润率是多少？
4. 广告负担、流量、转化率发生了什么变化？
5. 钱主要花在广告、商品成本、FBA、退款、促销还是账户费用？
6. 如果本月异常，最重要的 3-5 个原因是什么？

### 3.2 会计月度底稿

使用者：外部/内部会计。

必须快速回答：

1. Seller/Amazon 本月有哪些收入、退款和平台费用？
2. 每一类金额如何映射到源交易？
3. Transfer 为什么不进利润？
4. 广告账单金额和管理口径 Ads spend 为什么不同？
5. 商品成本、头程成本采用什么来源？
6. 是否能从分类明细追到源交易和 transaction id / raw data？

## 4. 范围与非范围

### 4.1 本功能包含

- 重构月度经营 XLSX 为 3 sheets。
- 新增/重构会计月度底稿 XLSX 为 4 sheets。
- 两份文件共用同一月度 financial-close calculation result。
- 使用 `amazon_finance_transaction` 作为自动会计分类主源。
- 使用 `amazon_sku_cost` effective-date 成本作为默认商品成本主源。
- 在经营首页加入 Product Gross Margin、Operating Margin、Ads Spend Ratio、Conversion Rate 的定义与解读。
- 显式负号显示。
- 保留 Seller Central Monthly Transaction 的外部 reconciliation 能力。
- 保留现有 JSON machine-readable artifact。

### 4.2 本功能不包含

- 不修改 ADR-015 的 Management P&L 公式。
- 不重新定义 Finances lifecycle inclusion。
- 不修改 Settlement ingestion。
- 不修改 Ads API ingestion。
- 不新增数据库表或 migration。
- 不把会计底稿定义为法定财务报表、税务申报表或正式会计凭证。
- 本轮不修改 Weekly Business Review / Weekly Ads Optimization Report。

## 5. 输入数据

| 来源 | 用途 | 关键字段/指标 |
|---|---|---|
| `amazon_finance_transaction` | 经营 P&L + 会计分类主源 | transaction type/status/local date/amount/raw breakdown |
| `amazon_sku_cost` | effective-date landed COGS | product/first-mile/packaging/other unit cost |
| `amazon_sales_traffic_daily` | 流量/销售趋势解释 | sales, units, sessions, unit session rate |
| Ads daily normalized tables | 当月实际广告消耗与广告效率 | cost, sales7d, clicks, impressions, purchases7d |
| Promotion/Coupon normalized data | 促销背景解释 | Coupon/Promotion metrics |
| Settlement normalized data | close/cash reconciliation reference | Settlement Close only |
| Seller Central Monthly Transaction | 可选人工官方核验源 | posted-date transaction rows, Released/Deferred, total |

### 5.1 Seller Central 手工导出的定位

生产自动化不得要求每个月先人工上传 CSV。

默认流程：

```text
normalized Finances ledger
-> 自动经营月报
-> 自动会计底稿
```

可选增强：

```text
Seller Central Monthly Transaction supplied
-> reconcile accounting categories
-> record reconciliation result
```

手工文件缺失不阻塞已通过 Finances data-quality gate 的正常月度报表生成。

## 6. 输出结果

### 6.1 Machine-readable source

保留：

```text
monthly_financial_close_{YYYY-MM}.json
```

JSON 继续承载完整 financial-close 计算、audit/reconciliation、source metadata 和兼容字段。

### 6.2 Monthly Operating Report

建议文件名：

```text
monthly_operating_report_{YYYY-MM}.xlsx
```

中文邮件可显示：

```text
月度经营报告_{YYYY-MM}.xlsx
```

默认 3 sheets：

```text
01_月度经营总览
02_经营损益
03_核验与口径
```

### 6.3 Accountant Workbook

建议文件名：

```text
accountant_monthly_workbook_{YYYY-MM}.xlsx
```

中文邮件可显示：

```text
会计月度底稿_{YYYY-MM}.xlsx
```

默认 4 sheets：

```text
01_会计汇总
02_分类明细
03_源交易明细
04_核验与说明
```

## 7. Monthly Operating Report 设计

## 7.1 `01_月度经营总览`

### A. 核心 KPI cards

必须展示：

| KPI | 公式/来源 |
|---|---|
| 商品销售额 | Natural-Month Finances Product Sales |
| 经营利润 | Management Operating Profit |
| 经营利润率 | Operating Profit / Product Sales |
| 商品毛利率 | `(Product Sales - Landed COGS) / Product Sales` |

### B. 最近三个月趋势

默认展示当前月及前两个月：

- 商品销售额
- 管理口径销量
- 商品毛利率
- 经营利润
- 经营利润率
- 广告费
- 广告费率
- Sessions
- Sales & Traffic 转化率
- 当前月环比

三个月数据必须使用同一 marketplace-local natural-month management口径。

### C. 主要支出结构

默认优先展示最有决策价值的类别：

- 广告费
- 到岸商品成本
- FBA履约费
- 退款净额
- 订单促销折扣
- 账户级费用（订阅 + Coupon + Deal + 仓储 + 退货处理 + 其他服务费）

每项至少展示：

```text
amount
amount / Product Sales
short interpretation
```

### D. 本月结论

生成 3-5 条 concise observations，优先解释：

- sales / units 的显著环比变化；
- gross margin 是否变化；
- operating margin 是否变化；
- sessions 与 conversion 是否同向；
- ads ratio 是否异常；
- Deal/Coupon/other account fees 是否有一次性大额项目。

v2 首期允许使用 deterministic rule-based observation，不要求 LLM 生成。

### E. “核心指标怎么读”

必须解释至少以下指标：

**商品毛利率**

```text
(Product Sales - Landed COGS) / Product Sales
```

只衡量产品本身售价 vs 到岸商品成本，不等于最终利润率。

**经营利润率**

```text
Management Operating Profit / Product Sales
```

衡量所有经营收入/费用和商品成本后的最终赚钱能力。

**广告费率**

```text
Ads API report-date spend / Product Sales
```

衡量广告支出对销售收入的负担。

**转化率**

```text
Sales & Traffic Units / Sessions
```

使用 Sales & Traffic 官方 conversion context；不要把 Management COGS units 直接除以 Sessions 冒充官方转化率。

## 7.2 `02_经营损益`

默认展示“上月 vs 本月”，而不是大量 raw breakdown sheets。

建议栏目：

```text
经营项目
上月
本月
环比金额
本月占商品销售额
说明
```

建议行：

```text
收入与退款
  商品销售收入
  运费收入
  退款：商品金额
  退款：运费
  退款时促销返还
  库存清算/残值收入

Amazon订单级费用
  FBA单件履约费
  Shipping Chargeback
  订单促销折扣
  库存清算相关费用
  净销售佣金

账户级收入与费用
  FBA库存赔偿净额
  其他账务调整
  订阅费
  Coupon费用
  Deal费用
  仓储费
  客户退货处理费
  其他服务费

广告与商品成本
  广告费
  商品采购成本
  头程成本
  包装成本
  其他单位成本
  人工/工资成本

最终结果
  经营利润
  经营利润率
```

公司当前人工/工资成本为 `0`，应显式展示为 `0`，不虚构人工成本。

### 7.2.1 Commission Base / Promo

若 Amazon source breakdown 出现：

```text
Commission/Base
Commission/Promo
```

经营表默认展示二者真实净额：

```text
Net Commission = Base + Promo
```

不能只展示 Base 并把 Promo 忽略，否则会高估 Amazon 净佣金。

## 7.3 `03_核验与口径`

仅保留 blocking / high-value controls：

- Natural-Month Finances source status
- review-required count / amount
- COGS costed units vs expected units
- missing cost SKU
- marketplace timezone / currency
- Ads API spend source
- Seller Central reconciliation status（若提供手工文件）
- Settlement / Transfer = reference only
- Released + Deferred rule

不再复制 raw metadata 和长审计明细。

## 8. Accountant Workbook 设计

## 8.1 `01_会计汇总`

建议顶部元数据：

```text
month
marketplace
source = normalized Finances ledger
currency = USD
optional bookkeeping FX rate
source row count
seller-central reconciliation status
```

核心分类：

| 分类 | 建议说明 |
|---|---|
| 商品销售收入 | Order / Shipment product sales |
| 运费收入 | Shipping charge |
| 订单促销折扣 | promotional rebates |
| Order FBA/Amazon费用 | FBA fulfillment + chargebacks + other order fees |
| 净销售佣金 | Base + Promo net |
| 退款净额 | Refund transaction total / component view |
| 广告账单净额 | Finances posted-date ProductAdsPayment / corresponding billing timing |
| 店铺订阅费 | Subscription |
| Coupon费用 | participation + performance |
| Deal费用 | participation + performance |
| 仓储/退货/FBA服务费 | ServiceFee / related categories |
| 赔偿/Adjustment | reimbursement / misc adjustment |
| 库存清算净额 | liquidation revenue - liquidation fees |
| Amazon交易净额 | excluding Transfer |
| 商品采购成本 | SKU-effective product cost |
| 头程成本 | SKU-effective first-mile cost |
| 参考利润 | accounting/bookkeeping support only |

`Management Operating Profit` / Ads API spend 可作为清晰标注的备查行，但不能替代 posted-date accounting billing categories。

## 8.2 `02_分类明细`

所有 accounting-relevant transaction rows 统一放在一张可筛选表，不再为订单/退款/仓储/广告/租金/Coupon/赔偿/清算分别创建独立 sheet。

至少包含：

```text
财务分类
建议会计项目
是否计入损益
处理说明
local posted date
transaction type
transaction status
transaction id / order id when available
SKU / product context when available
description / breakdown path
amount
source transaction id
```

如果分类规则遇到未知非零类型：

```text
accounting_classification_status = needs_review
```

不得静默丢弃。

## 8.3 `03_源交易明细`

默认来源为 normalized Finances ledger + raw transaction trace identifiers，而不是要求人工 CSV。

至少保留可追溯字段：

```text
amazon_transaction_id
marketplace_id
posted_date_local
transaction_type
transaction_status
transaction_amount
currency
raw_transaction_json reference / relevant raw fields
source_ingested_at
```

如果本次提供了 Seller Central Monthly Transaction，可选择追加 manual-source reconciliation metadata，但不改变自动生成主源。

## 8.4 `04_核验与说明`

至少检查：

- source rows vs classified rows；
- accounting category sum vs included transaction sum；
- Transfer excluded from P&L；
- unknown non-zero classifications；
- COGS cost coverage；
- Seller Central reconciliation result（optional）；
- Ads posted billing vs Ads API spend timing distinction；
- negative numbers explicit `-` format。

## 9. 会计成本与汇率规则

### 9.1 商品成本

废止新版默认中的历史固定算法：

```text
30 RMB / unit
2.5 RMB first-mile / unit
```

默认读取 `amazon_sku_cost` effective-date data。

缺失成本仍遵循 ADR-015 fail-closed financial control。

### 9.2 Adjustment / Reimbursement cost rule

Adjustment/Reimbursement 有 quantity 不代表必须额外扣一次成本。

默认：

```text
Adjustment/Reimbursement -> no automatic COGS unit
```

只有明确独立库存损失证据时才可计入额外 inventory write-off / COGS，且必须留 audit reason。

### 9.3 FX

USD 是 source-of-truth currency。

如果会计需要 CNY 列：

```text
CNY amount = USD amount * explicit monthly bookkeeping FX
```

FX 必须：

- 显示在 `01_会计汇总`；
- 来自明确 configuration / user input / approved rate source；
- 缺失时不得静默使用历史 `6.9`；
- 可选择留空 CNY 或将 workbook 标记 `fx_rate_required`。

## 10. 符号与格式

所有报表：

```text
收入 / 正向调整 -> positive
费用 / refund / cost -> negative
亏损 -> negative
```

负数必须显式显示：

```text
-$114.89
-7.85%
```

禁止仅依赖红色或括号表达负数含义。

## 11. 数据质量与 send guard

本功能不放宽 ADR-015 financial controls。

### 11.1 Management report blocking

任一情况必须阻塞正式经营月报发送：

- source_status != ok；
- review_required non-zero unresolved；
- missing cost SKU；
- costed units mismatch；
- unexpected marketplace timezone/currency；
- unknown non-zero finance lifecycle/category that affects Management P&L。

### 11.2 Accountant workbook blocking / review

至少以下情况标记 `needs_review`：

- unknown non-zero accounting classification；
- included category total does not reconcile to source included transaction total；
- source trace missing for included non-zero row；
- explicit monthly FX requested but absent；
- Seller Central manual reconciliation provided and produces unexplained material mismatch。

Manual Monthly Transaction file **not provided** by itself不应阻塞正常自动 Accountant Workbook。

## 12. 兼容性与 legacy contract

### 12.1 JSON

v2 首期保留现有 JSON compatibility fields，避免下游 delivery/tests 一次性破坏。

### 12.2 XLSX

现有 `monthly_financial_close_{YYYY-MM}.xlsx` 多 Sheet 结构进入 legacy presentation contract。

实现阶段建议：

1. 先新增两个新 writer / two-artifact output；
2. 本地对比 May/Jun/Jul；
3. delivery 支持两个附件；
4. 验收后再决定 legacy all-in-one XLSX 是停止默认生成，还是保留 `--legacy-xlsx` opt-in。

不建议直接在第一步删除兼容代码。

## 13. 建议代码边界（实现阶段）

当前设计建议，不代表本轮已经修改代码：

```text
services/monthly_financial_close_service.py
  -> 继续负责统一计算结果

reporting/monthly_operating_report_writer.py
  -> 新增 / 提取管理月报 writer

reporting/accountant_monthly_workbook_writer.py
  -> 新增会计底稿 writer

reporting/monthly_financial_close_writer.py
  -> legacy compatibility / shared helpers 待实现时评估

report_delivery
  -> 同一 monthly delivery pack 附带两份 XLSX
```

应优先复用 calculation DTO / result dict，不允许两个 writer 各自重新计算利润公式。

## 14. 验收标准

### 14.1 May/Jun/Jul golden numbers

必须保持：

| Month | Product Sales | Landed COGS | Ads API Spend | Management Profit | Operating Margin |
|---|---:|---:|---:|---:|---:|
| 2026-05 | 2316.38 | 467.25 | 544.66 | 548.35 | 23.67% |
| 2026-06 | 2870.06 | 573.05 | 539.25 | 612.70 | 21.35% |
| 2026-07 | 1464.14 | 291.23 | 555.63 | -114.89 | -7.85% |

Product Gross Margin should be approximately:

```text
May 79.83%
Jun 80.03%
Jul 80.11%
```

### 14.2 Seller Central reconciliation anchors

May/Jun/Jul manual export validation has established the following key mapping expectations:

- Product Sales matches natural-month Finances ProductCharges;
- Shipping matches;
- promotional rebates match;
- Order FBA fee total can be explained by FBA fulfillment + Shipping Chargeback in the verified months;
- Refund product/shipping/promo components match;
- liquidation revenue/fees match;
- account-level Coupon/Deal/storage/return fees match;
- Adjustment/reimbursement net can be explained;
- Transfer remains excluded from P&L;
- Released + Deferred must both be retained in posted-date reconciliation.

### 14.3 Presentation acceptance

- management workbook has exactly 3 default sheets;
- accountant workbook has exactly 4 default sheets;
- no formula errors (`#REF!`, `#VALUE!`, `#DIV/0!`, `#NAME?`);
- all negative values show explicit minus sign;
- ratios include concise interpretation on the first management sheet;
- no current raw/audit technical sheet is duplicated without a user-facing reason.

### 14.4 Tests

Implementation must add tests for:

- gross margin formula;
- ads spend ratio;
- current-vs-previous-month comparison;
- Commission Base + Promo netting;
- accounting category aggregation;
- Transfer exclusion;
- unknown accounting category `needs_review`;
- explicit negative number formats where writer API allows deterministic inspection;
- May/Jun/Jul golden report totals.

## 15. Migration 需求

```text
No migration required.
```

Current Azure SQL schema already supports this presentation redesign.

## 16. 实现顺序（下一步代码迭代）

```text
1. inventory current monthly calculation DTO / writer / delivery code
2. add shared monthly presentation helpers
3. implement Monthly Operating Report writer
4. implement Accountant Workbook writer
5. keep legacy XLSX behind compatibility path during first iteration
6. add tests + May/Jun/Jul local golden artifact generation
7. compare with approved sample layouts
8. update report delivery to attach both XLSX
9. local send/dry-run
10. Azure preview only
11. production rollout after manual review
```

## 17. 设计冻结项

截至 2026-08-12，以下不应在下一步编码时随意改动：

1. 两个独立 XLSX，而不是继续一个 all-in-one workbook。
2. 经营月报 3 sheets。
3. 会计底稿 4 sheets。
4. Management P&L 继续使用 ADR-015 自然月口径。
5. Seller Central Monthly Transaction 是 reconciliation/accounting reference，不是自动化硬依赖。
6. 商品成本使用 effective-date SKU cost，不回退到永久固定 30/2.5/6.9。
7. Adjustment quantity 不自动重复扣 COGS。
8. Transfer 不进利润。
9. Ads billing timing 与 Ads API spend 分开。
10. 所有负数显式 `-`。

## 17. 2026-08-16 本地实现记录

本轮实现遵循“计算主链不改、展示/交付层新增”的兼容策略。

新增：

```text
src/seller_data_pipeline/reports/monthly_reporting_common.py
src/seller_data_pipeline/reports/monthly_operating_report_writer.py
src/seller_data_pipeline/reports/accountant_monthly_workbook_writer.py
```

`MonthlyFinancialCloseService.write_report_files()` 现在同时生成：

```text
monthly_financial_close_{YYYY-MM}.json
monthly_financial_close_{YYYY-MM}.xlsx              # legacy compatibility
monthly_operating_report_{YYYY-MM}.xlsx             # new management artifact
accountant_monthly_workbook_{YYYY-MM}.xlsx           # new accountant artifact
```

月度 delivery 在新字段存在时：

```text
primary attachment   = monthly_operating_report_{YYYY-MM}.xlsx
supplemental          = accountant_monthly_workbook_{YYYY-MM}.xlsx
legacy workbook       = generated but not attached by default
```

经营月报最近三个月趋势通过现有 repository 对当前月及前两个月使用同一 calculation service 计算，避免 writer 自行复制利润公式。

会计底稿的分类明细和源交易明细直接读取 `amazon_finance_transaction` normalized rows；repository 查询补充 raw hash / business key / lifecycle identifiers，用于追溯和 Commission Base/Promo 净额识别。

本地验收：

```text
pytest -q tests/unit
372 passed
```

下一步仍需在 Azure preview 对 2026-05 / 2026-06 / 2026-07 运行 golden-number 验收，并检查 delivery pack 实际包含两份 XLSX 后，再进入生产 rollout。
