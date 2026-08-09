# Feature: Monthly Executive P&L with Landed COGS

> 状态：Implemented locally / Azure verification pending  
> 版本：v1.87  
> 更新时间：2026-08-09  
> 相关功能：`feature_monthly_financial_close_report.md`, `feature_sku_cost_management.md`, `feature_report_delivery_email.md`  
> 数据库影响：无 migration；复用现有 `dbo.amazon_sku_cost.first_mile_cost` 等字段。

## 1. 背景

2026-05 至 2026-07 月报生产复核确认：现有 Monthly Financial Close 的金额和对账链路已恢复稳定，但首页仍把 Settlement-led profit 以 `Estimated Operating Profit` legacy alias 形式突出展示，容易被经营者误读成“本月真正经营利润”。

同时 `amazon_sku_cost` 已经包含：

```text
product_cost
first_mile_cost
packaging_cost
other_unit_cost
```

但当前实际成本记录中的 `first_mile_cost` 尚未补录，因此此前月报的 `Internal COGS` 实际主要只有商品货款成本，没有体现头程海运。

本轮业务确认的当前批次基础成本：

```text
factory product cost = 30 RMB / unit
first-mile freight total = 3,656 + 1,339 + 5,206.46 = 10,201.46 RMB
FBA received units = 2,688
estimated first-mile freight = 10,201.46 / 2,688 = 3.7952 RMB / unit
```

现有美国站 SKU 成本以 USD 维护，当前 30 RMB 商品货款对应 `4.17 USD/unit`；在未引入独立历史 FX 表前，本轮 first-mile manual estimate 应采用同一隐含换算口径，约为 `0.5275 USD/unit`，并在 `remark` 中保留计算来源。

## 2. 目标

1. 让月报首页把 **Management Operating Profit** 作为经营主指标。
2. Settlement-led profit 保留为 **Settlement Close Profit**，用于会计/月结解释，不再以“Estimated Operating Profit”名称在 XLSX 首页重复突出。
3. 将总 COGS 拆成：
   - Product Cost COGS
   - First-Mile Freight COGS
   - Packaging COGS
   - Other Unit COGS
   - Total Landed COGS
4. `02_Management_PnL` 展开 Settlement bucket 结构，并显式展示：
   - Settlement Net Excluding Posted Ads
   - Ads API Report-date Spend
   - Contribution After Ads Before Landed COGS
   - Landed COGS component breakdown
   - Management Operating Profit / Margin
5. `06_SKU_Profit` 增加单位成本和 COGS component breakdown，方便人工核对头程是否真实进入 SKU 成本。
6. 邮件标题和正文改用 Management Operating Profit，不再默认发送 Settlement-led profit 作为“Profit”。
7. JSON 保留原有字段以兼容已有消费者，同时新增清晰别名：
   - `management_operating_profit`
   - `management_operating_margin`
   - `settlement_close_profit`
   - `landed_cogs`
   - COGS components

## 3. 非目标

- 不新增数据库表或 migration。
- 不自动推断采购成本或物流费用。
- 不把尚未售出的库存成本一次性计入当月损益。
- 不实现 FIFO / 批次级移动加权。
- 不把 Management Operating Profit 解释为法定税后净利润。
- 不自动把公司级人工、软件、银行、税费等非 SKU 成本归入月报；这些仍需后续独立成本输入设计。

## 4. 成本口径

单位到岸成本继续使用现有冻结公式：

```text
unit_standard_cost
= product_cost
+ first_mile_cost
+ packaging_cost
+ other_unit_cost
```

月度 COGS 仍按 Settlement product-sales unit 的 posted date 匹配有效成本行，只对当月已售件数确认成本。未售库存对应商品货款和头程继续留在库存成本，不进入当月损益。

本轮新增的只是 component aggregation 和 presentation，不改变成本匹配业务键、effective date 逻辑或币种保护。

## 5. 经营利润口径

```text
Settlement Net Excluding Posted Ads
- Ads API Report-date Spend
- Product Cost COGS
- First-Mile Freight COGS
- Packaging COGS
- Other Unit COGS
= Management Operating Profit
```

其中：

```text
Settlement Net Excluding Posted Ads
= Settlement Net Amount - Settlement Advertising Fee
```

Settlement Advertising Fee 通常为负值，因此该式等价于先把 posted-date settlement Ads 扣费加回，再用 report-date Ads spend 替换。

会计/月结参考仍为：

```text
Settlement Close Profit
= Settlement Net Amount - Total Landed COGS
```

## 6. 数据质量展示

`01_Summary` 增加以下明确状态：

- SKU Cost Coverage
- First-Mile Cost Included
- Unknown Settlement Classification
- Bank Payout Reconciliation

其中 First-Mile Cost Included 只做信息提示，不作为通用 blocking rule，因为某些业务可能真实没有 first-mile；银行实收仍需 `14_Payout_Recon` 人工闭环。

## 7. 兼容性

为了避免破坏已有 report delivery / downstream JSON consumer：

- 保留 `estimated_operating_profit` legacy JSON 字段，语义仍为 Settlement-led profit。
- 保留 `management_estimated_profit_report_date_ads`。
- 新增更清晰的 alias，而不是删除旧字段。
- XLSX 首页不再展示 legacy `Estimated Operating Profit` / `Profit Margin` alias。
- 邮件模板优先读取新 alias；旧 JSON 缺少新字段时回退旧字段。

## 8. 验收标准

本地：

```text
PYTHONPATH=src pytest -q
python -m compileall -q src scripts tests
```

生产：

1. 先只读确认 4 个正式 SKU 当前 `amazon_sku_cost` 记录和 effective date。
2. 以白名单 + 原值检查方式将 `first_mile_cost ≈ 0.5275 USD/unit` 写入覆盖 2026-05 至 2026-07 的有效成本记录；remark 保留 `10,201.46 RMB / 2,688 units = 3.7952 RMB/unit` 来源。
3. 重新生成 2026-05、2026-06、2026-07 monthly preview，不需要重新 submit/collect Amazon 数据。
4. 确认每月 `First-Mile Freight COGS > 0`，且 `Total Landed COGS = component sum`。
5. 管理经营利润应比原月报 Management Profit 分别下降当月已售件数 × first-mile unit cost。
6. `status=ok`、`reconciliation_needs_review=0`，不能因 presentation 改造引入新的财务阻断。
7. 邮件 subject 中的 `Operating Profit` 必须等于 Management Operating Profit，而不是 Settlement Close Profit。
