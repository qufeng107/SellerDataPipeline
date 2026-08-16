# ADR-009: Settlement-led Profit Calculation Policy
> 2026-08-10 status note: ADR-015 supersedes this ADR as the sole Management P&L policy. Settlement-led logic remains valid for Settlement Close / accounting / cash reconciliation.

> 状态：Accepted  
> 日期：2026-05-18；更新：2026-06-01  
> 决策范围：利润核算口径、周报/月报财务主口径、后续利润计算脚本设计

## 1. 背景

SellerDataPipeline 已完成核心 Amazon SP-API / Ads normalized ingestion，包括 Ads、Listing、Inventory snapshot、Sales & Traffic、Settlement、Orders、FBA Reimbursements、FBA Fee Preview、Promotion/Coupon 和 Inventory Ledger。

下一阶段需要进入利润核算和周报/月报设计。不同 Amazon 报表存在天然口径差异：

- Orders 更适合看订单和 SKU 销量，但不是最终入账结果。
- Sales & Traffic 更适合看流量、转化率和销售表现，但不适合作为会计利润来源。
- Ads API 更适合看广告投放效果，但实际扣费最终体现在结算里。
- Promotion/Coupon 报表更适合看活动效果，但活动实际成本应以结算扣减为准。
- Settlement 最接近实际入账、费用、退款、赔偿和调整项。

公司当前是小体量团队，优先目标是稳定、可复核、能给会计和运营使用，而不是一开始实现复杂会计系统。

## 2. 决策

采用：

```text
Profit Calculation Policy v1.0 — Settlement-led Financial Profit
```

核心决策：

1. 财务利润以 `amazon_settlement_transaction` 为主，不以 Orders / Sales & Traffic / Ads / Promotion 作为最终财务金额来源。
2. Orders 用于销量、SKU、订单结构和促销 ID 辅助解释。
3. Sales & Traffic 用于 sessions、conversion rate、Buy Box、ASIN 表现等运营解释。
4. Ads API 用于广告表现分析；利润表广告费优先使用 Settlement 实扣广告费。
5. Promotion/Coupon 报表用于活动配置和效果复盘；利润表促销成本优先使用 Settlement 实扣扣减。
6. 退款、赔偿、清算、调整项按 Settlement 实际发生期计入，不在第一版强行追溯原订单期。
7. 商品采购成本、包装成本、头程/海运/清关/入仓成本来自 `amazon_sku_cost`，不从 Amazon 报表推断。
8. 第一版采用 SKU 级标准成本 + 生效日期，不做 FIFO 或复杂批次库存成本。
9. 第一版优先输出人工复核文件；利润结果表待连续几期复核稳定后再考虑 migration。

### 2.1 2026-06-01 补充决策：双利润展示，不改变财务主口径

Amazon Ads 广告费可能按账单阈值或结算批次集中 posted 到 Seller Central Payments，导致 Settlement posted-date 的广告费与 Ads API report-date 的实际投放发生额跨月不一致。为避免管理层误判单月经营利润，月报新增第二个管理口径：

```text
management_estimated_profit_report_date_ads
= settlement_net_amount
- internal_cogs
+ settlement_advertising_fee_abs
- ads_api_report_date_spend
```

该指标只用于经营复盘和广告费跨期解释，不替代 `settlement_led_estimated_profit`，也不作为会计结账主口径。

周报默认使用 Ads API report-date spend 计算广告压力和经营贡献；Settlement advertising fee 只作为 posted-date 账单/现金流提醒。

## 3. 理由

### 3.1 最不容易混乱

Settlement 是实际结算明细，天然包含多种收入、费用、退款、赔偿和调整项。以它作为财务主口径，可以避免同时从 Orders、Ads、Promotion 等多张表重复拼金额，减少双算和漏算风险。

### 3.2 最适合当前团队

当前公司人手有限，第一版需要快速产出可用利润周报。SKU 标准成本 + 生效日期已经能覆盖大部分经营判断，不需要一开始投入 FIFO、批次成本、库存估值等复杂能力。

### 3.3 方便会计复核

Settlement 与 Amazon 实际结算更接近，会计更容易追溯。Orders、Ads、Promotion 等作为解释性口径单独展示，可以帮助说明利润变化，但不会干扰财务主结果。管理经营口径单独展示 Ads report-date adjustment，可以解释广告费跨期，但不覆盖会计主结果。

## 4. 影响

### 4.1 对利润计算脚本

`scripts/calculate_profit_report.py` 应优先读取：

```text
amazon_settlement_transaction
amazon_sku_cost
```

再读取 Orders / Sales & Traffic / Ads / Promotion/Coupon 作为辅助说明和差异解释。

### 4.2 对周报/月报

周报/月报必须明确区分：

```text
Financial profit period: Settlement posted date
Operational performance period: order/report/ad activity date
Management P&L ads period: Ads API report_date
```

不要把两个周期的金额混算；如需管理经营口径，必须显式加回 Settlement posted-date advertising fee 再扣除 Ads API report-date spend，并与 Settlement-led 结果并列展示。

### 4.3 对数据库设计

当前不新增利润结果表。等第一版人工复核稳定后，再评估是否新增：

```text
profit_calculation_run
profit_summary_period
profit_sku_period
```

如未来新增，必须从 `013_xxx.sql` 或更后 migration 开始，并在真实执行后同步 `database_current_schema_spec.md`。

## 5. 被否决方案

| 方案 | 否决原因 | 替代方案 |
|---|---|---|
| Orders-led profit | 订单口径与结算、退款、广告扣费、调整项不一致。 | Settlement-led。 |
| Ads API spend 覆盖财务广告费 | Ads API 是投放归因口径，不一定等于当期结算实扣。 | Ads 用于运营分析；Settlement 用于财务/会计利润；月报可另列 Management P&L。 |
| Promotion/Coupon 报表金额直接作为促销成本 | 活动报表适合效果分析，实际扣减应看结算。 | Promotion/Coupon 用于解释，Settlement 用于财务成本。 |
| 第一版 FIFO/批次成本 | 复杂度过高，容易拖慢落地。 | SKU 标准成本 + 生效日期。 |
| 缺成本时默认按 0 成本 | 会高估利润。 | 缺成本阻塞正式净利润，只允许 preview。 |

## 6. 后续行动

1. 维护 `docs/features/feature_profit_calculation.md` 为利润功能设计入口。
2. 补充真实 SKU 成本到 `amazon_sku_cost`。
3. 开发 `scripts/calculate_profit_report.py` 的 dry-run / preview。
4. 先用真实 3月/4月或 5月上旬数据人工复核。
5. 复核稳定后，再设计周报和可选利润结果表。
6. 在 Monthly Financial Close Report 中实现双利润口径和 Ads Timing Reconciliation。
