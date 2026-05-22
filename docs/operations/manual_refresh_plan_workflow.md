# Manual Refresh Plan Workflow

> 更新时间：2026-05-21  
> 文档定位：把“简单几个指令定期下载所有数据入库”固化为标准手动更新流程。后续 Azure Container Apps Jobs 自动化应复用这里定义的 plan、phase 和口径。

## 1. 标准原则

当前标准定期更新流程是：

```text
固定 plan -> submit -> collect -> ingest -> audit
```

规则：

```text
1. 不再临时拼一长串零散脚本作为日常流程。
2. 日常刷新使用固定 plan：core_rolling 或 weekly_full。
3. 每个 plan 拆成四个 phase：submit、collect、ingest、audit。
4. submit 只提交/发现报表请求，不入库。
5. collect 只收集已完成 raw report，不入库。
6. ingest 只把已下载 raw report upsert 入 normalized tables。
7. audit 只检查覆盖范围和 stable cutoff。
8. submit / ingest / collect / audit 都通过同一总控 CLI 执行，默认只打印计划；必须显式加 --execute 才实际运行。
```

该流程是未来自动化调度的标准来源。自动化只应调度这些稳定命令，不应重新发明另一套下载/入库逻辑。

## 2. Plan 定义

### 2.1 core_rolling

建议频率：每 1-2 天。

用途：刷新最近会变化的数据，用重叠窗口 + upsert 覆盖最近数据。

包含：

```text
Sales & Traffic：最近 10 天
Orders：最近 10 天
Amazon Ads：最近 14 天
Promotion/Coupon：采样计划窗口
Inventory snapshot：当前快照
```

### 2.2 weekly_full

建议频率：每周一次，或月报/周报复核前。

用途：在 core_rolling 基础上补财务、库存流水、赔偿和费用预估等慢源。

包含 core_rolling 全部内容，另加：

```text
Settlement V2 discovery：最近窗口 discovery
FBA Reimbursements：最近 60 天
Inventory Ledger summary/detail：最近窗口
Listing snapshot：当前快照
FBA Fee Preview：当前/近 4 天
```

## 3. 标准执行命令

### 3.1 每 1-2 天：core rolling refresh

提交请求：

```powershell
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase submit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
```

等待一段时间后收集 raw data：

```powershell
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase collect --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
```

如果仍有 `PENDING` / `IN_PROGRESS`，稍后重复 collect。全部或大部分下载完成后入库：

```powershell
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase ingest --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
```

最后审计：

```powershell
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase audit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --target-start-date 2026-03-01 --execute
```

### 3.2 每周：weekly full refresh

提交请求：

```powershell
python scripts/run_manual_refresh_plan.py --plan weekly_full --phase submit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
```

收集：

```powershell
python scripts/run_manual_refresh_plan.py --plan weekly_full --phase collect --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
```

入库：

```powershell
python scripts/run_manual_refresh_plan.py --plan weekly_full --phase ingest --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
```

审计：

```powershell
python scripts/run_manual_refresh_plan.py --plan weekly_full --phase audit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --target-start-date 2026-03-01 --execute
```

## 4. Dry-run / 预览

任何 phase 去掉 `--execute` 都只打印将执行的命令：

```powershell
python scripts/run_manual_refresh_plan.py --plan weekly_full --phase submit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300
```

上线新 plan 或改动 plan 后，先 dry-run 看命令列表，再 execute。

## 5. 与 historical backfill 的边界

`run_manual_refresh_plan.py` 是“定期刷新”入口，不替代历史补数。

历史补数仍用明确日期范围：

```powershell
python scripts/backfill_report_requests.py --marketplace-id ATVPDKIKX0DER --report-type GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL --start-date 2026-03-01 --end-date 2026-05-17 --chunk-days 30 --execute
python scripts/backfill_ads_reports.py --profile-id 3917953989967300 --start-date 2026-03-17 --end-date 2026-05-20 --chunk-days 14 --execute
```

历史 backfill 如果一次下载多个 chunk，仍需确认 ingestion 是否已经处理所有 chunk。当前经验是：Orders 历史 backfill 多 chunk 下载后，需要逐个 `--raw-file` 入库，或后续再开发批量 raw-file ingestion。

## 6. 验收标准

每次定期更新完成后，至少检查：

```text
1. submit phase 没有 failed command。
2. collect phase 下载了预期 raw files；若有 PENDING，可稍后重复 collect。
3. ingest phase status=success，requires_review=False。
4. audit phase 的核心数据源 stable_status 尽量达到 covers_stable_window。
5. 周报/月报加工前，只使用 stable cutoff 内的数据。
```

## 7. 未来自动化映射

Azure Container Apps Jobs 可按同样 phase 拆分：

```text
core_rolling_submit_job   -> 每 1-2 天
core_rolling_collect_job  -> submit 后延迟运行，可重复
core_rolling_ingest_job   -> collect 后运行
core_rolling_audit_job    -> ingest 后运行
weekly_full_submit_job    -> 每周
weekly_full_collect_job   -> submit 后延迟运行，可重复
weekly_full_ingest_job    -> collect 后运行
weekly_full_audit_job     -> ingest 后运行
```

自动化阶段需要额外补充失败告警、重试和运行日志汇总，但不改变这里的业务口径。
