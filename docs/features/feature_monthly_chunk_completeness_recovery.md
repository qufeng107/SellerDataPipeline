# Monthly Chunk Completeness Recovery

> 文档状态：Implemented locally; Azure verification pending  
> 迭代版本：v1.83  
> 日期：2026-08-08

## 1. 背景

2026-06 月度恢复验证发现，Monthly submit 会将长月份窗口拆成多个请求分片，但部分 ingestion CLI 在未显式传入 raw file 时只选择最新文件：

- Sales & Traffic：30 天按 14 天拆成 3 个 SP-API report requests，但 ingestion 只处理最新 raw file。
- All Orders：同样拆成 3 个 requests，但 ingestion 只处理最新 raw file。
- Amazon Ads：5 个 report type 各按 14 天拆分；当前 table-ready 的 4 个 report type ingestion 每类只处理最新 raw file。

因此 `collect_ingest commands failed=0` 不能等价于“月度全部请求分片均已入库”。2026-06 的现场证据为 Sales & Traffic 仅准备 4 rows（3 date rows + 1 ASIN row），Orders 仅 8 rows，而 submit 已明确创建 3 个分片。

同时发现两个相关保护问题：

1. Monthly data coverage audit 只传 `target_start_date`，默认 `target_end_date=today`，历史月份补跑时审核窗口会超出目标月份。
2. `settlement_ads_fee_vs_ads_api_spend` 明知比较的是 Settlement posted-date 与 Ads API report-date 两种时间口径，却在差额较大时升级为 `needs_review` 并阻断邮件；这与 Settlement-led + Management P&L 的冻结口径不一致。

## 2. 目标

v1.83 必须保证：

1. Monthly chunked source ingestion 按目标月份选择并处理**全部已下载分片**，而不是“最新一个文件”。
2. 选择基于 submit/collect manifest 的业务日期窗口，不通过文件 mtime 猜测月份。
3. 同一日期分片若存在重复请求，选择最新一份已下载 manifest，避免重复工作。
4. 在 ingestion 前验证 selected manifests 的日期区间可完整覆盖目标月份；存在缺口时 fail closed，不生成“看似成功但数据不完整”的月报。
5. Monthly data coverage audit 明确限定 `target_start_date..target_end_date` 为目标月。
6. Settlement vs Ads timing reconciliation 保留为 timing warning/context，不因时间口径差异单独阻断 shareholder delivery。
7. 不使用 `--allow-blocked` 绕过 send guard；修复数据与规则后让 guard 自然通过。
8. 保持 Weekly/manual 现有“未指定 period 时使用 latest raw file”的行为，避免扩大变更面。

## 3. 设计

### 3.1 Manifest-bound raw selection

新增共享选择器：

- SP-API：读取 `runtime/sampling/report_requests/*.json`。
- Ads：读取 `runtime/sampling/ads_report_requests/*.json`。
- 仅选择目标 marketplace/profile + report type + `download_status=DOWNLOADED` + raw file 实际存在的 manifest。
- SP-API `data_end_time` 按 exclusive end 解释；Ads `data_end_date` 按 inclusive end 解释。
- period 模式要求 selected intervals 完整覆盖目标月份。
- 相同 `(report_type, start, end)` 多份 manifest 时，保留 `updated_at_utc/submitted_at_utc` 最新者。

### 3.2 Monthly ingestion

Monthly automation 对以下命令显式传入：

```text
--start-date YYYY-MM-DD --end-date YYYY-MM-DD
```

- Sales & Traffic：逐个 selected raw file 执行现有 guarded ingestion/upsert。
- Orders：逐个 selected raw file 执行现有 guarded ingestion/upsert。
- Ads：每个 table-ready report type 处理 period 内全部 selected raw files；preview 文件名包含 report id，避免多分片互相覆盖。

每个 CLI 输出：

```text
period_file_selection ... files_selected=N coverage_complete=True
file[i/N] ...
period_ingestion_summary files_processed=N failed=0 prepared_rows=... written_rows=...
```

任一分片 schema/privacy/DB 写入失败，则命令非零退出。

### 3.3 Coverage audit

Monthly automation 改为：

```text
audit_data_coverage.py --target-start-date <month start> --target-end-date <month end>
```

Weekly 暂不改变。

### 3.4 Ads timing reconciliation

`settlement_ads_fee_vs_ads_api_spend`：

- 完全一致/小差异：`ok/info`。
- 存在显著 timing difference：`warning/warning`。
- 不再仅凭金额/比例差异返回 `needs_review/error`。

原因：二者业务日期语义不同，Management P&L 已明确用 Ads API report-date spend 替换 posted-date settlement ads；Settlement-led 财务口径仍保留原 Settlement 金额。

真正阻断条件仍包括 Settlement self-check、unknown/unclassified amount、missing SKU cost、currency mismatch 等财务完整性问题。

## 4. 非目标

- v1.83 本身不修改 Settlement 正常 ingestion DML；该性能项已在后续 v1.84 `feature_settlement_ingestion_batch_upsert.md` 独立实现，可与 v1.83 一起部署验收。
- 不修改 SQL schema，不新增 migration。
- 不改变财务主口径，不以 Ads API 覆盖 Settlement-led accounting close。
- 不强制要求 Orders/Ads 每个自然日必须有业务行；完整性以 request-manifest 分片覆盖为主，避免把“无订单/无投放日”误判为缺失。

## 5. 验收标准

1. 单测覆盖 SP-API/Ads manifest period selection、重复 interval 去重、缺口 fail closed。
2. Monthly automation tests 确认 Sales/Orders/Ads ingestion 均带 month start/end，coverage audit 带 target end。
3. Ads ingestion 多 raw files 时每份均被解析/upsert，preview 不覆盖。
4. Ads timing 大额差异只产生 warning，不再令 Monthly Financial Close 仅因此变为 needs_review。
5. 全量 pytest、compileall、CI Safety lint 通过。
6. Azure 重新运行 2026-06 collect_ingest 后，Sales/Orders/Ads 日志显示多个分片被处理；随后 report_delivery dry-run 自然通过 send guard（若不存在其他真实财务问题）。

## 6. 本地实现结果

- 新增 manifest-bound period raw selector，SP-API/Ads 均支持 interval 去重与 coverage gap fail-closed。
- Monthly Sales & Traffic / Orders / Ads ingestion 均显式传目标月 start/end。
- Ads dry-run 可处理同 report type 多个 raw files，preview 文件按 report id 隔离。
- Monthly coverage audit 显式传 target end。
- Ads timing reconciliation 大差异降为 warning，不再单独阻断 shareholder delivery。
- Sales & Traffic / Orders 写入异常路径补充 rollback-before-failure-audit，避免 partial DML 被失败审计 commit。
- 本地：`330 passed`；`compileall` 通过；当前环境未安装 Ruff，Safety lint 交由 CI。
