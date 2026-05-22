# Historical Backfill Workflow

> 更新时间：2026-05-20  
> 文档定位：记录手动阶段如何按明确日期范围补历史数据，避免继续用 `--days` 人工倒推日期导致混乱。

## 1. 设计原则

历史补数采用：

```text
explicit date range -> chunked report requests -> collect ready reports -> ingestion upsert -> coverage audit
```

规则：

```text
1. Backfill 命令只负责提交 report request，不直接入库。
2. 默认 dry-run，只预览将要提交的日期分段。
3. 必须显式加 --execute 才会调用 Amazon API。
4. 每个日期分段使用 inclusive start/end，例如 2026-03-01..2026-03-31。
5. SP-API 底层 dataEndTime 会转换成 end_date 的下一天 00:00:00Z，以覆盖完整 end_date。
6. Amazon Ads Reporting v3 的 startDate/endDate 使用日期字段，按 inclusive 日期传递。
7. 如本地已有同 report type + 同日期窗口的 manifest，默认跳过；需要重提时使用 --force。
```

Normalized 表仍使用 upsert 覆盖当前业务行，不做多版本共存。

## 2. SP-API 历史补数

命令：

```powershell
python scripts/backfill_report_requests.py \
  --marketplace-id ATVPDKIKX0DER \
  --report-type GET_SALES_AND_TRAFFIC_REPORT \
  --start-date 2026-03-01 \
  --end-date 2026-04-30 \
  --chunk-days 31
```

先 dry-run 预览；确认无误后：

```powershell
python scripts/backfill_report_requests.py \
  --marketplace-id ATVPDKIKX0DER \
  --report-type GET_SALES_AND_TRAFFIC_REPORT \
  --start-date 2026-03-01 \
  --end-date 2026-04-30 \
  --chunk-days 31 \
  --execute
```

### Orders 历史补数

Amazon order tracking 类报表通常更适合 30 天窗口：

```powershell
python scripts/backfill_report_requests.py \
  --marketplace-id ATVPDKIKX0DER \
  --report-type GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL \
  --start-date 2026-03-01 \
  --end-date 2026-05-17 \
  --chunk-days 30
```

确认后加 `--execute`。

### Promotion / Coupon 报表

这类报表需要 reportOptions。示例：

```powershell
python scripts/backfill_report_requests.py \
  --marketplace-id ATVPDKIKX0DER \
  --report-type GET_PROMOTION_PERFORMANCE_REPORT \
  --start-date 2026-03-01 \
  --end-date 2026-05-17 \
  --chunk-days 89 \
  --report-option promotionStartDateFrom={data_start_time} \
  --report-option promotionStartDateTo={data_end_time}
```

Coupon：

```powershell
python scripts/backfill_report_requests.py \
  --marketplace-id ATVPDKIKX0DER \
  --report-type GET_COUPON_PERFORMANCE_REPORT \
  --start-date 2026-03-01 \
  --end-date 2026-05-17 \
  --chunk-days 89 \
  --report-option couponStartDateFrom={data_start_time} \
  --report-option couponStartDateTo={data_end_time}
```

## 3. Amazon Ads 历史补数

命令：

```powershell
python scripts/backfill_ads_reports.py \
  --profile-id 3917953989967300 \
  --start-date 2026-03-17 \
  --end-date 2026-05-20 \
  --chunk-days 14
```

默认提交核心 Sponsored Products 5 类报告：

```text
spCampaigns
spTargeting
spSearchTerm
spAdvertisedProduct
spPurchasedProduct
```

只补某一种 reportTypeId：

```powershell
python scripts/backfill_ads_reports.py \
  --profile-id 3917953989967300 \
  --start-date 2026-03-17 \
  --end-date 2026-05-20 \
  --chunk-days 14 \
  --only-report-type-id spSearchTerm
```

确认后加 `--execute`。

## 4. 收集与入库

SP-API：

```powershell
python scripts/collect_ready_reports.py --limit 50
```

Ads：

```powershell
python scripts/collect_ads_reports.py --limit 50
```

之后按数据源入库：

```powershell
python scripts/ingest_sales_traffic_report.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_sales_traffic_report.py --marketplace-id ATVPDKIKX0DER --execute

python scripts/ingest_orders_report.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_orders_report.py --marketplace-id ATVPDKIKX0DER --execute

python scripts/ingest_ads_reports.py --profile-id 3917953989967300 --marketplace-id ATVPDKIKX0DER
python scripts/ingest_ads_reports.py --profile-id 3917953989967300 --marketplace-id ATVPDKIKX0DER --execute
```

最后运行覆盖审计：

```powershell
python scripts/audit_data_coverage.py --marketplace-id ATVPDKIKX0DER --target-start-date 2026-03-01
```

## 5. 当前推荐补数范围

当前已经决定从 2026-03 开始核对与加工，1 月和 2 月暂不作为正式利润范围。因此推荐先补：

```text
Orders：2026-03-01..2026-05-17，chunk 30 days
Ads：2026-03-17..2026-05-20，chunk 14 days
Sales & Traffic：已通过 140 天补数核对，可按需重跑 2026-03-01..2026-05-17
```

Settlement 目前 2026-03 和 2026-04 已通过后台 Flat File V2 核对，可进入数据加工。5 月仍需要等 5/15–Present statement 关闭后再补最终财务口径。
