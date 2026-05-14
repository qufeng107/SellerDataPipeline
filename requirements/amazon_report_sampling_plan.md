# Amazon Report Sampling Plan

> 文档版本：v0.2  
> 更新日期：2026-05-14  
> 状态：接口取样阶段使用；不代表最终数据库表结构。  
> 原则：先尽量拿 raw 样例，后解析字段，再更新 `requirements/database_spec.md`，最后才建库。

---

## 1. 目标

当前阶段目标不是马上写入 Azure SQL，而是系统性取样 Amazon 可用数据源：

```text
Reports API / getReports / 后续 Ads API
    ↓
本地 raw 文件归档
    ↓
字段结构分析与脱敏样例文档
    ↓
parser 草案
    ↓
database_spec.md 更新
    ↓
最终 SQL schema
```

已完成取样的数据域：

| 数据域 | report/API | 状态 |
|---|---|---|
| Listing | `GET_MERCHANT_LISTINGS_ALL_DATA` | downloaded + analyzed |
| FBA 库存 | `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` | downloaded + analyzed |
| 销售与流量 | `GET_SALES_AND_TRAFFIC_REPORT` | downloaded + analyzed |
| Settlement 财务 | `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` | discovered + downloaded + analyzed |

下一阶段要尽量补齐：

| 数据域 | 候选 report/API | 目的 |
|---|---|---|
| 订单明细 | `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` | 订单、SKU、ASIN、订单状态、促销折扣、渠道 |
| 退货 | `GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE` | RMA、退货原因、退货状态 |
| FBA 退货 | `GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA` | FBA 收到的退货、处置、原因、状态 |
| 赔偿 | `GET_FBA_REIMBURSEMENTS_DATA` | 库存赔偿、case id、原因、现金/库存赔偿 |
| 费用预估 | `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` | referral fee / FBA fulfillment fee 预估 |
| 仓储费 | `GET_FBA_STORAGE_FEE_CHARGES_DATA` | 月度仓储费、平均库存、体积、尺寸层级 |
| 库存健康 | `GET_FBA_INVENTORY_PLANNING_DATA` | 库龄、周转、冗余、建议动作 |
| 库存流水 | `GET_LEDGER_SUMMARY_VIEW_DATA` / `GET_LEDGER_DETAIL_VIEW_DATA` | 收货、发货、退货、丢失、损坏、盘点差异 |
| 促销/Coupon | `GET_PROMOTION_PERFORMANCE_REPORT` / `GET_COUPON_PERFORMANCE_REPORT` | 如果账号可用，用于活动效果取样 |

---

## 2. 敏感数据规则

部分报告可能包含客户相关字段或自由文本评论。当前默认批量取样脚本会避开这些报告，除非显式使用：

```powershell
python scripts/run_sampling_plan.py --include-sensitive
```

敏感或半敏感报告包括：

| report_type | 原因 |
|---|---|
| `GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL` | 可能包含买家联系方式/地址相关字段 |
| `GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA` | 可能包含 customer-comments |

即使本地下载这些报告，也必须继续遵守：

```text
reports/raw/
runtime/
```

不得提交到 GitHub。只允许提交脱敏后的 `requirements/data_samples/*.md`。

---

## 3. 批量取样脚本

新增：

```text
scripts/run_sampling_plan.py
src/seller_data_pipeline/sampling/report_sampling_plan.py
```

先查看计划，不调用 Amazon：

```powershell
python scripts/run_sampling_plan.py --dry-run
```

执行默认非敏感取样计划：

```powershell
python scripts/run_sampling_plan.py
```

执行指定 report type：

```powershell
python scripts/run_sampling_plan.py --only-report-type GET_FBA_REIMBURSEMENTS_DATA
```

强制重新提交已有样例：

```powershell
python scripts/run_sampling_plan.py --force --only-report-type GET_FBA_REIMBURSEMENTS_DATA
```

控制调用间隔，减少 throttling 风险：

```powershell
python scripts/run_sampling_plan.py --pause-seconds 5
```

提交/发现完成后，继续下载：

```powershell
python scripts/collect_ready_reports.py --limit 50
```

---

## 4. 取样后处理流程

每次批量下载后：

1. 查看 `collect_ready_reports.py` 输出，确认哪些 report 下载成功。
2. 对普通单文件报告运行：

```powershell
python scripts/analyze_raw_report.py `
  --raw-file <raw_file_path> `
  --report-type <REPORT_TYPE> `
  --marketplace-id ATVPDKIKX0DER `
  --output-md requirements/data_samples/<REPORT_TYPE>.md
```

3. 对多份 settlement 报告继续使用：

```powershell
python scripts/analyze_settlement_reports.py `
  --raw-dir reports/raw/amazon/ATVPDKIKX0DER/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2/2026-05-14 `
  --marketplace-id ATVPDKIKX0DER `
  --output-md requirements/data_samples/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2.md
```

4. 把新生成的脱敏字段样例发给 ChatGPT 继续更新 `database_spec.md` 和 parser。

---

## 5. 暂不覆盖的方向

暂不优先：

| 方向 | 原因 |
|---|---|
| Restricted tax/invoicing reports | 可能需要 RDT/额外安全权限，当前阶段收益低 |
| Vendor reports | 当前是 Seller/FBA 场景，不是 Vendor |
| 印度 GST 报告 | 当前主站点是美国站 |
| Seller Fulfilled Prime / MFN shipping 报告 | 当前业务以 FBA 为主 |
| Ads API | 需要 profile/auth 流程，建议在 Reports API 主要样例补齐后单独做 |

---

## 6. 2026-05-14 批量取样结果记录

本轮默认计划执行结果：

| report_type | 状态 | 说明 |
|---|---|---|
| `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` | downloaded | 30 天订单样例，112 行 |
| `GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE` | downloaded | 60 天退货样例，header-only |
| `GET_FBA_REIMBURSEMENTS_DATA` | downloaded | 90 天赔偿样例，19 行 |
| `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` | downloaded | 费用预估样例，8 行 |
| `GET_FBA_STORAGE_FEE_CHARGES_DATA` | cancelled | 当前窗口无可生成数据或 report 不适用，暂不阻塞 |
| `GET_FBA_INVENTORY_PLANNING_DATA` | downloaded | 库存健康样例，4 行，字段较多 |
| `GET_LEDGER_SUMMARY_VIEW_DATA` | downloaded | COUNTRY + DAILY 库存流水汇总，150 行 |
| `GET_LEDGER_DETAIL_VIEW_DATA` | failed before submit | 显式空 `eventType` 被 SP-API 校验拒绝，后续改为不传 `reportOptions` |
| `GET_PROMOTION_PERFORMANCE_REPORT` | fatal / diagnostic downloaded | 诊断显示必须提供 `promotionStartDateFrom` / `promotionStartDateTo` reportOptions |
| `GET_COUPON_PERFORMANCE_REPORT` | fatal / diagnostic downloaded | 诊断显示必须提供 `couponStartDateFrom` / `couponStartDateTo` reportOptions |

后续计划已补充更多非敏感库存/FBA 相关报告：

```text
GET_RESERVED_INVENTORY_DATA
GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT
GET_STRANDED_INVENTORY_UI_DATA
GET_FBA_RECOMMENDED_REMOVAL_DATA
GET_FBA_FULFILLMENT_LONGTERM_STORAGE_FEE_CHARGES_DATA
GET_FBA_OVERAGE_FEE_CHARGES_DATA
```

下一轮建议：

```powershell
python scripts/collect_ready_reports.py --limit 50
python scripts/run_sampling_plan.py --dry-run
python scripts/run_sampling_plan.py
python scripts/collect_ready_reports.py --limit 50
```

---

## 7. 2026-05-14 第二轮批量取样结果记录

第二轮新增结果：

| report_type | 状态 | 说明 |
|---|---|---|
| `GET_LEDGER_DETAIL_VIEW_DATA` | downloaded | 不传空 `eventType` 后成功，207 行库存流水明细 |
| `GET_RESERVED_INVENTORY_DATA` | downloaded | 预留库存，5 行 |
| `GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT` | downloaded | 补货建议，5 行 |
| `GET_STRANDED_INVENTORY_UI_DATA` | cancelled | 当前无可生成样例，暂不阻塞 |
| `GET_FBA_RECOMMENDED_REMOVAL_DATA` | cancelled | 当前无可生成样例，暂不阻塞 |
| `GET_FBA_FULFILLMENT_LONGTERM_STORAGE_FEE_CHARGES_DATA` | cancelled | 当前无长期仓储费样例，暂不阻塞 |
| `GET_FBA_OVERAGE_FEE_CHARGES_DATA` | cancelled | 当前无超量仓储费样例，暂不阻塞 |
| `GET_COUPON_PERFORMANCE_REPORT` | fatal | 后续 collect 会下载 diagnostic document；业务口径先依赖 settlement |
| `GET_PROMOTION_PERFORMANCE_REPORT` | in_progress | 可继续 collect；如最终 FATAL，只保存诊断，不阻塞 |

处理原则：失败/取消的运营型报告不影响当前建库主线。销售、库存、订单、settlement、赔偿、FBA fee preview、库存流水已经足够支撑第一版 normalized 数据库设计。


## 8. 2026-05-14 促销 / Coupon diagnostic 结果

新版 collect 已成功下载 `FATAL` diagnostic document。诊断结论：

| report_type | 诊断结果 | 后续处理 |
|---|---|---|
| `GET_PROMOTION_PERFORMANCE_REPORT` | 缺少 `promotionStartDateFrom` / `promotionStartDateTo` | 批量计划改为自动生成这两个 reportOptions |
| `GET_COUPON_PERFORMANCE_REPORT` | 缺少 `couponStartDateFrom` / `couponStartDateTo` | 批量计划改为自动生成这两个 reportOptions |

后续 dry-run 应显示：

```text
GET_PROMOTION_PERFORMANCE_REPORT days=89 options={...promotionStartDateFrom..., ...promotionStartDateTo...}
GET_COUPON_PERFORMANCE_REPORT days=89 options={...couponStartDateFrom..., ...couponStartDateTo...}
```

旧的空 `reportOptions` diagnostic manifest 不再作为“已有有效样例”匹配，下一次运行
`run_sampling_plan.py` 会提交带日期 reportOptions 的新请求。
