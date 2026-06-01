# Feature: Profit Calculation

> 文档状态：Policy frozen / preview implemented  
> 负责人：AI + Feng  
> 更新时间：2026-05-19  
> 功能状态：Preview implemented  
> 相关数据接入文档：`docs/data_access/sp_api_reports_catalog.md`, `docs/data_access/amazon_ads_reports_catalog.md`, `docs/data_access/seller_central_manual_exports.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`  
> 相关 ADR：`docs/adr/ADR-009-settlement-led-profit-policy.md`, `docs/adr/ADR-010-overlapping-refresh-weekly-analysis.md`

---

## 1. 功能摘要

本功能负责在核心 Amazon normalized ingestion 完成后，基于 Settlement 主财务口径计算周度/月度利润，并为周报、月报、会计核对和清仓判断提供稳定指标。分析产物最短周期为一周；数据刷新可以更高频，但不产生正式日报结论。

当前阶段只冻结利润核算口径，不立即新增数据库表、不立即自动发送报表。第一版目标是用最不容易混乱、最适合小体量团队人工复核的方式，先产出可解释、可复核的利润结果。

核心原则：

```text
财务利润以 Settlement 实际入账/扣费为主；
Orders、Sales & Traffic、Ads、Promotion/Coupon 用于运营解释和归因分析，不能反向覆盖 Settlement 财务结果。
```

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认 |
| 口径冻结 | 财务/会计口径已冻结：Settlement-led Financial Profit v1.0；管理经营口径新增 report-date Ads adjustment |
| 数据源取样 | 已完成，核心 ingestion 已入库 |
| Parser | 不适用，读取 normalized SQL |
| Dry-run preview | 已实现：`scripts/calculate_profit_report.py` |
| Schema guard | 不适用；依赖上游 ingestion guard |
| Repository/upsert | 第一版输出文件，不落利润结果表 |
| Azure SQL execute | 不适用；读取 normalized SQL，输出本地 preview 文件 |
| 幂等性验证 | 文件输出可重复生成；利润结果不写库 |
| 单元测试 | 已补充核心 service/repo 测试 |
| 文档同步 | 已完成本口径冻结文档 |

功能整体状态：`Preview implemented`。

说明：本功能已完成业务口径冻结和第一版利润 preview 实现；后续重点是基于 coverage audit 补齐数据、人工复核多期结果，再开发周报/月报。

## 3. 业务目标

本功能服务公司当前最急需的四类运营问题：

1. **知道真实赚不赚钱**：以 Amazon 实际结算和内部 SKU 成本为基础，估算周度/月度净利润。
2. **给会计稳定口径**：利润结果应能解释 Settlement、广告扣费、促销扣减、退款、赔偿、清算等项目。
3. **支持运营复盘**：结合 Orders、Sales & Traffic、Ads、Promotion/Coupon 解释销量、广告、促销对利润的影响。
4. **支持清仓和广告决策**：按 SKU/ASIN 看销售、费用、成本和毛利，判断是否应降价、停广告、清仓或补货。

当前公司小体量、人手有限，因此第一版优先追求：

```text
稳定 > 可复核 > 可解释 > 可逐步自动化 > 复杂会计精确分摊
```

## 4. 范围与非范围

### 4.1 本功能包含

- 冻结利润核算主口径。
- 定义各数据源在利润计算中的优先级和用途。
- 定义退款、赔偿、清算、广告费、促销扣减的处理原则。
- 定义 SKU 标准成本和生效日期的使用方式。
- 设计并实现第一版手动利润计算脚本的输入、输出和验收标准。
- 为后续周报/月报提供统一利润指标。

### 4.2 本功能不包含

- 不在第一版做 FIFO、批次库存成本、复杂加权库存成本。
- 不用 Orders 直接替代 Settlement 作为财务收入。
- 不用 Ads API spend 覆盖 Settlement 中实际广告扣费。
- 不用 Promotion/Coupon 预算或后台预估值替代 Settlement 实扣促销成本。
- 不把退款强行追溯回原订单月份，第一版按实际发生期入账。
- 不在利润脚本未人工复核前自动发送正式邮件。
- 不在本口径文档中修改已执行 migration。

## 5. 利润口径总原则

口径名称：

```text
Profit Calculation Policy v1.0 — Settlement-led Financial Profit
```

冻结规则：

| 维度 | 冻结口径 |
|---|---|
| 财务金额主来源 | `amazon_settlement_transaction` |
| 销量/SKU/订单结构 | `amazon_order_item` 辅助解释 |
| 流量/转化率 | `amazon_sales_traffic_daily` / `amazon_sales_traffic_asin_daily` 辅助解释 |
| 广告表现 | Ads daily tables 辅助分析；财务利润广告费优先 Settlement 实扣；管理经营利润可用 Ads API report-date spend 重列广告发生额 |
| 促销效果 | Promotion/Coupon tables 辅助分析；利润表促销成本优先 Settlement 实扣 |
| 成本来源 | `amazon_sku_cost` 手工维护/会计输入 |
| 时间口径 | 财务利润按 Settlement posted date / posted datetime；运营分析按各自 report/order 日期 |
| 退款/赔偿/清算 | 按实际发生期计入，不第一版追溯原订单期 |
| 第一版成本方法 | SKU 级标准成本 + 生效日期，不做 FIFO |

## 6. 利润公式

### 6.1 周期级经营净利润估算

第一版利润公式：

```text
经营净利润估算
= Settlement 财务净额
- 商品采购成本
- 包装成本
- 头程/海运/清关/入仓分摊成本
- 其他 SKU 级单位成本
```

其中：

```text
Settlement 财务净额
= Settlement 中同一期间内所有非汇总交易金额按 profit_bucket/amount_category 汇总后的净额
```

说明：Settlement 通常已包含商品销售收入、平台费、FBA 配送费、广告扣费、促销扣减、退款、赔偿、调整项等 Amazon 侧金额。因此第一版不再从 Orders/Ads/Promotion 重新拼一遍财务收入和费用。

### 6.2 SKU 级成本

SKU 单件标准成本：

```text
unit_standard_cost
= product_cost
+ packaging_cost
+ first_mile_cost
+ other_unit_cost
```

对应当前已有表：

```text
dbo.amazon_sku_cost
```

字段含义：

| 字段 | 冻结含义 |
|---|---|
| `product_cost` | 单件采购成本/货款成本。 |
| `packaging_cost` | 单件包装、吊牌、说明书等可归属包装成本。 |
| `first_mile_cost` | 单件头程、海运、清关、入仓等分摊成本。 |
| `other_unit_cost` | 其他可稳定归属到单件的成本。 |
| `currency` | 成本币种；第一版应尽量与 marketplace 财务币种一致，跨币种换算后再入库。 |
| `effective_from` / `effective_to` | 成本生效区间，支持未来不同批次/价格变化。 |

### 6.3 成本匹配日期

第一版成本匹配规则：

```text
按 Settlement posted date 匹配 amazon_sku_cost 的 effective_from/effective_to。
```

原因：财务利润主口径以 Settlement 发生期为准，成本也按同一财务期间匹配，最不容易混乱。

## 7. 输入数据

| 来源系统 | 表/Report | 用途 | 财务优先级 | 备注 |
|---|---|---|---|---|
| SP-API Reports | `amazon_settlement_transaction` | 财务收入、费用、退款、赔偿、调整项主来源 | 主口径 | 利润计算核心表。 |
| 手工/会计输入 | `amazon_sku_cost` | SKU 单件采购、包装、头程和其他单位成本 | 主口径 | 当前已存在，需录入真实成本。 |
| SP-API Reports | `amazon_order_item` | SKU 销量、订单结构、促销 ID 辅助解释 | 辅助 | 不直接覆盖财务收入。 |
| SP-API Reports | `amazon_sales_traffic_daily`, `amazon_sales_traffic_asin_daily` | Sessions、转化率、销售额运营解释 | 辅助 | 用于周报运营分析。 |
| Amazon Ads | Ads SP daily tables | spend、sales、ACOS、ROAS、点击、曝光分析 | 辅助 | 广告表现分析用；财务广告费优先 Settlement。 |
| SP-API Reports | Promotion/Coupon tables | 活动配置与效果复盘 | 辅助 | 促销成本财务主口径优先 Settlement。 |
| SP-API Reports | FBA Reimbursements | 赔偿明细解释 | 辅助 | 财务金额优先 Settlement；明细用于说明。 |
| SP-API Reports | Inventory snapshot / ledger | 库存和异常解释 | 辅助 | 不直接参与利润公式，除非后续做库存成本。 |

## 8. 输出结果

第一版输出建议先以文件为主，避免在口径未经过人工复核前新增过多结果表。

| 输出类型 | 输出位置 | 用途 |
|---|---|---|
| Markdown/CSV/Excel preview | `runtime/profit_reports/...` | 人工核对利润结果。 |
| 周期汇总 | 文件内 summary sheet / section | 给老板和会计看总利润。 |
| SKU 明细 | 文件内 sku detail sheet / section | 判断哪些 SKU 赚钱/亏钱。 |
| 差异提示 | 文件内 reconciliation section | 展示 Settlement vs Ads/Orders/Promotion 的解释性差异。 |
| 审计日志 | `amazon_sync_run_log` 或脚本日志 | 记录脚本运行状态。 |

后续如果连续几期人工复核稳定，再考虑新增结果表，例如：

```text
profit_calculation_run
profit_summary_period
profit_sku_period
```

这些表尚未存在，不得写入 `database_current_schema_spec.md`，除非未来 migration 真实执行成功。

## 9. 处理流程

第一版手动流程：

```text
按 data_refresh_policy 完成滚动刷新或周度完整刷新
  -> 运行 coverage audit 并确认 stable cutoff 前核心源覆盖
  -> 确认 raw data 已下载并入库
  -> 检查 Settlement / Orders / Ads / Promotion / Cost 数据完整性
  -> 按期间读取 Settlement posted date 财务交易
  -> 按 profit_bucket / amount_category 汇总 Amazon 侧净额
  -> 按 SKU + posted date 匹配 amazon_sku_cost
  -> 计算 SKU 级和周期级成本
  -> 生成利润 preview 文件
  -> 人工复核异常项和差异项
  -> 确认后用于周报/月报/会计准备
```

注意：利润 preview 可以按指定期间运行，但正式经营分析输出最短按周/月，不设计日报利润结论。

失败处理：

| 场景 | 处理方式 | 是否阻塞正式利润输出 |
|---|---|---|
| 期间无 Settlement 数据 | 提示数据不足，只允许生成 draft/preview | 是 |
| SKU 成本缺失 | 列入 missing cost section；该 SKU 利润标记为不完整 | 是，除非用户明确接受估算 |
| 同一 SKU 成本区间重叠 | 报错，要求修正 `amazon_sku_cost` | 是 |
| Settlement 金额币种混杂 | 报错或按 marketplace 分开输出 | 是 |
| Ads API spend 与 Settlement 广告费不一致 | 展示差异，不覆盖财务利润 | 否 |
| Orders 销量与 Settlement 数量不一致 | 展示差异，不覆盖财务利润 | 否 |

## 10. Settlement 分类使用规则

`amazon_settlement_transaction` 已有：

```text
amount_category
profit_bucket
```

第一版利润计算使用 `profit_bucket` 做保守汇总，但不能把当前分类视为最终会计科目。建议第一版至少输出：

| bucket | 用途 |
|---|---|
| `revenue` | 商品销售收入、配送收入等正向收入。 |
| `amazon_fee` | Referral fee、commission、closing fee 等平台费用。 |
| `fba_fee` | FBA fulfillment / shipping / storage 等费用。 |
| `advertising` / `advertising_cost` | Amazon 广告实扣费用，财务/会计口径按 Settlement posted-date；管理经营口径可加回后用 Ads API report-date spend 替换。 |
| `promotion` | Coupon、promotion、deal 等实际扣减。 |
| `refund` | 退款、退货相关扣减或返还。 |
| `reimbursement` | FBA 赔偿等正向调整。 |
| `reconciliation` | settlement summary / deposit / transfer 等对账项。 |
| `other` | 未归类或需人工复核项目。 |

注意：

```text
profit_bucket 是利润计算的第一版分类辅助，不是不可变会计科目。
遇到 other/reconciliation 大额异常时，周报必须提示人工复核。
```

## 11. 时间口径

| 报表类型 | 日期字段 | 说明 |
|---|---|---|
| 财务利润 | Settlement `posted_date_raw` / `posted_date_time_raw` 解析后的 posted date | 主口径。 |
| 订单销量 | Orders purchase date / order date | 运营分析口径。 |
| 流量转化 | Sales & Traffic report date | 运营分析口径。 |
| 广告表现 | Ads report_date | 广告归因分析口径；周报和月报 Management P&L 的广告发生额来源。 |
| 促销效果 | Promotion/Coupon activity date / report period | 活动分析口径。 |

报表必须明确提示：

```text
财务利润周期与订单销量周期可能不完全一致，原因包括结算延迟、退款滞后、广告扣费延迟、促销扣减延迟和时区差异。
```

## 12. 目标数据表设计

### 12.1 当前涉及表

| 表 | 当前是否存在 | 用途 | 写入方式 |
|---|---|---|---|
| `dbo.amazon_settlement_transaction` | yes | 财务主口径来源 | read-only |
| `dbo.amazon_sku_cost` | yes | SKU 标准成本 | 手工/seed/后续导入维护 |
| `dbo.amazon_order_item` | yes | 订单和 SKU 辅助解释 | read-only |
| Ads daily tables | yes | 广告效果辅助解释 | read-only |
| Promotion/Coupon tables | yes | 促销效果辅助解释 | read-only |
| Sales & Traffic tables | yes | 流量和转化辅助解释 | read-only |
| `dbo.amazon_sync_run_log` | yes | 记录运行 | optional write |

### 12.2 新 migration 需求

当前口径冻结阶段：**不需要新增 migration**。

| 变化 | 原因 | migration 文件 | 状态 |
|---|---|---|---|
| 新增利润结果表 | 待第一版文件输出连续复核稳定后再决定 | `013_xxx.sql` 或更后 | not planned for first implementation |

## 13. 幂等性设计

第一版如果只输出文件：

```text
同一 marketplace_id + period_start + period_end + generated_at 会生成独立文件；
不写利润结果表，因此没有数据库重复写入风险。
```

如果后续写入利润结果表，应使用：

```text
business_key = marketplace_id + period_type + period_start + period_end + policy_version + result_grain + sku/asin/null
```

并通过 MERGE/upsert 保证同一口径同一周期重复计算时更新而不是重复插入。

## 14. Schema guard 与异常处理

本功能读取已经入库的 normalized 表，不直接解析 Amazon raw file。因此字段漂移由上游 ingestion schema guard 负责。

本功能自身需要做业务完整性检查：

| 场景 | 处理方式 | 是否阻塞 |
|---|---|---|
| `amazon_settlement_transaction` 无期间数据 | 阻塞正式输出，只生成错误提示。 | yes |
| `amount` / `currency` 关键字段为空 | 报告异常行并阻塞。 | yes |
| `seller_sku` 为空但金额需要 SKU 成本 | 进入 unallocated section，阻塞 SKU 级毛利。 | yes for SKU profit |
| 缺少 SKU 成本 | 输出 missing cost list，默认阻塞正式净利润。 | yes |
| 成本币种与 Settlement 币种不一致 | 第一版要求人工先换算后录入；否则阻塞。 | yes |
| `other` bucket 金额超过阈值 | 输出 review warning。 | no/conditional |

## 15. 审计与可追溯性

| 审计对象 | 表/字段 | 说明 |
|---|---|---|
| 上游入库任务 | `amazon_sync_run_log` | 利润计算前应检查关键 ingestion 是否成功。 |
| Settlement 来源行 | `amazon_settlement_transaction.source_*`, `raw_data` | 可追溯每一笔金额来源。 |
| 成本来源 | `amazon_sku_cost.remark`, `effective_from`, `effective_to` | 说明成本输入依据。 |
| 利润计算运行 | 脚本日志；后续可写 `amazon_sync_run_log` | 第一版至少写本地日志。 |
| 输出文件 | `runtime/profit_reports/...` | 保留人工复核文件。 |

## 16. 命令行入口

已实现入口：

```powershell
python scripts/calculate_profit_report.py --marketplace-id ATVPDKIKX0DER --period weekly --start-date YYYY-MM-DD --end-date YYYY-MM-DD --dry-run
python scripts/calculate_profit_report.py --marketplace-id ATVPDKIKX0DER --period monthly --start-date YYYY-MM-DD --end-date YYYY-MM-DD --output-dir runtime/profit_reports
```

参数设计：

| 参数 | 是否必需 | 默认值 | 说明 |
|---|---|---|---|
| `--marketplace-id` | yes | n/a | Amazon marketplace id。 |
| `--period` | yes | n/a | `weekly` / `monthly` / `custom`。 |
| `--start-date` | yes | n/a | 财务利润期间开始日期，含当天。 |
| `--end-date` | yes | n/a | 财务利润期间结束日期，含当天。 |
| `--dry-run` | no | true for first implementation | 只生成 preview，不写结果表。 |
| `--output-dir` | no | `runtime/profit_reports` | 输出目录。 |
| `--allow-missing-cost` | no | false | 第一版默认不允许缺成本时输出正式净利润。 |

## 17. 相关代码路径

| 类型 | 路径 | 说明 |
|---|---|---|
| script | `scripts/calculate_profit_report.py` | 已实现，手动生成利润 preview/report。 |
| service | `src/seller_data_pipeline/services/calculate_profit_service.py` | 已实现 Settlement-led preview service。 |
| db/repository | `src/seller_data_pipeline/db/repositories/finance_repo.py` | 读取 Settlement、SKU cost 和辅助运营数据。 |
| tests | `tests/unit/services/test_calculate_profit_service.py` | 已补充核心利润 preview 测试。 |
| docs | `docs/adr/ADR-009-settlement-led-profit-policy.md`; `docs/adr/ADR-010-overlapping-refresh-weekly-analysis.md` | 利润口径与刷新/分析节奏 ADR。 |

## 18. 测试计划

当前第一版测试重点：

```bash
PYTHONPATH=src pytest tests/unit/services/test_calculate_profit_service.py -q
PYTHONPATH=src pytest tests/unit/common/test_date_windows.py -q
ruff check src tests scripts
python -m compileall -q scripts src tests
```

建议测试场景：

1. Settlement 收入/费用/退款/广告/促销/赔偿汇总。
2. SKU 成本按 `effective_from/effective_to` 正确匹配。
3. 缺少 SKU 成本时默认阻塞正式净利润。
4. Ads API spend 与 Settlement advertising 不一致时，财务利润不覆盖；管理经营利润可以用 report-date Ads adjustment 另行展示。
5. Orders 数量与 Settlement 数量不一致时只提示差异，不覆盖财务利润。
6. 同一周期重复生成文件不修改数据库。

## 19. 验收标准

功能完成必须满足：

1. 能基于真实 `amazon_settlement_transaction` 生成指定期间利润 preview。
2. 能读取 `amazon_sku_cost` 并按 posted date 匹配单位成本。
3. 缺成本、成本区间重叠、币种不一致等场景能明确报错或 warning。
4. 能输出周期级 summary 和 SKU 级 detail。
5. 能单独列出 settlement bucket 汇总和需要人工复核的 `other/reconciliation` 项。
6. 不用 Orders / Ads / Promotion 覆盖 Settlement 财务金额。
7. 单元测试通过。
8. 文档状态从 `Preview implemented` 更新为 `Implemented` 前，必须至少用多个真实周期人工复核过。

## 20. 当前实现状态

| 日期 | 进展 | 证据/命令 | 备注 |
|---|---|---|---|
| 2026-05-18 | 冻结利润核算口径为 Settlement-led Financial Profit v1.0。 | 本文档 + ADR-009。 | 暂不新增 migration。 |
| 2026-06-01 | 新增管理经营口径：在 Settlement-led 基础上加回 posted-date 广告扣费并扣除 Ads API report-date spend。 | 本文档 + ADR-009 + Monthly Financial Close v1.2。 | 先更新文档，不新增 migration。 |
| 2026-05-18 | 实现第一版利润 preview。 | `scripts/calculate_profit_report.py`。 | 只输出本地文件，不落库。 |
| 2026-05-19 | 冻结重叠窗口刷新 + 周度最小分析产物。 | ADR-010 + data_refresh_policy。 | 数据可高频刷新，分析不做日报。 |

## 21. 后续优化

- 连续几期人工复核稳定后，评估新增利润结果表。
- 成本导入模板已拆分为独立功能：`docs/features/feature_sku_cost_management.md`，通过 Excel -> `amazon_sku_cost` 维护。
- 加入汇率表或汇率快照，但第一版要求成本先换算为 marketplace 财务币种。
- 加入清仓建议：结合 SKU 利润、库存余额、动销和广告效果。
- 加入邮件草稿生成，但第一阶段不自动发送正式邮件。
- 后续根据会计要求补充 VAT/sales tax/公司侧费用处理。

## 22. 弃置记录

| 日期 | 弃置内容 | 原因 | 替代方案 |
|---|---|---|---|
| 2026-05-18 | 用 Orders 作为最终销售收入口径。 | Orders 是运营口径，不能稳定反映实际结算、退款、费用和调整。 | Settlement 作为财务主口径，Orders 仅辅助解释。 |
| 2026-05-18 | 用 Ads API spend 覆盖利润表广告费。 | Ads API 适合投放分析，财务实扣以 Settlement 为准。 | Ads API 用于差异解释和广告效果分析。 |
| 2026-05-18 | 第一版做 FIFO/批次库存成本。 | 对小体量团队实现和维护成本过高，容易拖慢利润周报落地。 | SKU 级标准成本 + 生效日期。 |
| 2026-05-18 | 缺 SKU 成本时自动用 0 成本输出正式利润。 | 会严重高估利润，误导经营决策。 | 缺成本默认阻塞正式净利润，只允许 preview。 |
