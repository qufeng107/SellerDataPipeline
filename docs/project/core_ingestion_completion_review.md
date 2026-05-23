# Core Ingestion Completion Review

> 更新时间：2026-05-18  
> 文档定位：核心数据入库阶段的收尾检查。本文记录已经完成的真实入库闭环、已知限制和下一阶段计划。

## 1. 总结结论

截至本文件更新时间，SellerDataPipeline 的核心数据入库阶段已经基本完成。

已完成的标准不是“只写了 parser”，而是每条核心链路都完成了：

```text
dry-run
-> execute
-> 第二次 execute 幂等性验证
-> sync_run_log 记录
-> schema guard 无 blocking review
-> feature 文档同步
```

## 2. 已完成入库链路

| 数据域 | 入口 | 目标表 | 验收结果 |
|---|---|---|---|
| Ads | Amazon Ads SP reports | 4 张 Ads daily 表 | inserted=200；second run updated=200 |
| Listing | `GET_MERCHANT_LISTINGS_ALL_DATA` | `amazon_listing_snapshot` | inserted=6；second run updated=6 |
| Inventory snapshot | `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` | `amazon_inventory_daily` | inserted=5；second run updated=5 |
| Sales & Traffic | `GET_SALES_AND_TRAFFIC_REPORT` | `amazon_sales_traffic_daily`, `amazon_sales_traffic_asin_daily` | inserted=7；second run updated=7 |
| Settlement | `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` | `amazon_settlement_transaction` | inserted=4911；second run updated=4911 |
| Orders | `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` | `amazon_order_item` | inserted=112；second run updated=112 |
| FBA Reimbursements | `GET_FBA_REIMBURSEMENTS_DATA` | `amazon_fba_reimbursement` | inserted=19；second run updated=19 |
| FBA Fee Preview | `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` | `amazon_fba_fee_preview` | inserted=8；second run updated=8 |
| Promotion/Coupon | Promotion + Coupon reports | 4 张 Promotion/Coupon 表 | inserted=10；second run updated=10 |
| Inventory Ledger | Ledger summary + detail reports | `amazon_inventory_ledger_summary_daily`, `amazon_inventory_ledger_detail` | inserted=357；second run updated=357 |

## 3. 已执行 migration

```text
001_create_core_tables.sql
002_create_indexes.sql
003_add_listing_snapshot_business_key_hash.sql
004_add_inventory_daily_business_key_hash.sql
005_add_sales_traffic_business_key_hashes.sql
006_add_settlement_transaction_business_key.sql
007_add_order_item_business_key.sql
008_add_fba_reimbursement_business_key.sql
009_add_fba_fee_preview_business_key.sql
010_add_promotion_coupon_business_keys.sql
011_add_inventory_ledger_business_keys.sql
012_create_ingestion_job_config.sql
```

以上 migration 已执行成功，不允许再修改历史文件。后续从 `013_xxx.sql` 开始。`001_seed_ingestion_job_config_core_jobs.sql` 也已执行成功，当前 `pipeline_job_config` 有 13 条任务配置。

## 4. 当前已知限制

| 限制 | 影响 | 后续处理 |
|---|---|---|
| raw file 归档关联仍不完整 | 多数 normalized 表可追踪 `source_raw_file_path`，但 `source_raw_file_id` 仍可能为 NULL | 后续补 raw file registry 关联。 |
| 还没有自动下载调度 | 当前 raw data 仍依赖手动下载/收集 | 先建立 manual workflow，再上 Jobs。 |
| 利润核算口径已冻结但未实现 | 还不能直接输出正式利润周报 | 下一阶段按 Settlement-led Financial Profit v1.0 开发手动利润 preview。 |
| SKU 成本/头程成本仍需人工配置 | 缺少真实毛利计算关键输入 | 设计成本导入机制。 |
| 周报和邮件发送未实现 | 仍需人工整理输出 | 先实现手动生成，再做自动邮件。 |
| `requirements_to_be_deprecated/` 尚未删除 | 历史 sample docs 仍有引用 | 后续迁移 sample notes 后再删除。 |

## 5. 下一阶段建议

不要继续无限扩展 ingestion。下一阶段应转向：

```text
1. 手动运行流程和任务周期配置
2. 利润核算设计
3. SKU 成本和头程成本输入
4. 手动生成周报/月报
5. 手动邮件发送/邮件草稿
6. Azure Container Apps Jobs 自动化
```

## 6. 近期建议执行顺序

1. 按已冻结的 `feature_profit_calculation.md` 开发手动利润 preview。
2. 设计并录入 SKU 成本、包装成本和头程/海运成本。
3. 用真实周期人工复核利润计算结果。
4. 开发手动周报生成脚本。
5. 再评估自动化 Jobs。
