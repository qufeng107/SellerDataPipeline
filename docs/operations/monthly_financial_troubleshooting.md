# Monthly Financial Close Troubleshooting Runbook

> 更新时间：2026-08-10  
> 适用版本：v1.90.3+  
> 适用范围：Amazon US monthly `collect_ingest` / Natural-Month Finances / Settlement Close / Monthly Financial Close / automation audit。

## 1. 先判断失败发生在哪一层

按下面顺序看，不要一看到月报异常就直接 repair 数据：

```text
Azure Job execution status
-> stage commands=... failed=...
-> Finances natural-month summary
-> Settlement ingestion summary
-> coverage/reconciliation guards
-> COGS cost identity
-> artifact save/audit tail
-> report send_guard
```

生产月度 `collect_ingest` 当前应为 fail-closed：

```text
python scripts/run_automation_stage.py \
  --workflow monthly \
  --phase collect_ingest \
  --marketplace-id ATVPDKIKX0DER \
  --profile-id 3917953989967300 \
  --execute
```

正式配置不应包含 `--continue-on-error`。

## 2. Azure execution 最终状态

某次 execution 必须最终确认：

```bash
az containerapp job execution show \
  --name sdp-monthly-collect-ingest \
  --resource-group rg-amazon-ops \
  --job-execution-name <EXECUTION_NAME> \
  --query "{name:name,status:properties.status,start:properties.startTime,end:properties.endTime}" \
  -o table
```

业务命令已经打印 `commands=N failed=0` 仍不等于 execution 最终成功；v1.90.2 曾出现业务命令全部成功后，artifact audit 尾处理抛异常导致 execution 失败。

## 3. Azure SQL `HYT00` warm-up

当前 Azure SQL 为 Serverless，冷启动时可能出现：

```text
Azure SQL connection warm-up attempt 1/6 ... HYT00
Azure SQL connection warm-up attempt 2/6 ... HYT00
```

如果后续连接成功、业务命令完成且 execution 最终 `Succeeded`，这是可接受的 cold-start telemetry，不要当作数据修复信号。

只有 6 次重试耗尽、最终命令失败时才按 `docs/database/azure_sql_connection_runbook.md` 排查。

## 4. Finances Natural-Month 异常

正常 July 基准示例：

```text
month=2026-07
timezone=America/Los_Angeles
local_rows=161
review_required=0
shipment_unit_count=58
liquidation_unit_count=4
management_unit_count=62
```

### 4.1 金额与 Seller Central Monthly Transaction 对不上

优先检查：

1. marketplace timezone 是否仍为 `America/Los_Angeles`；
2. 是否错误按 UTC 月份筛选；
3. lifecycle status/type 是否出现新组合；
4. 是否把 prior-period release (`RELEASED Shipment` non-zero 等) 重复计入；
5. 是否把 `Transfer` 或 `ProductAdsPayment` 当作 Management operating amount。

不要为了强行闭合而修改金额符号或把所有 status 合并。

### 4.2 `review_required > 0`

查看 `summary.json` / compact log 的 status/type，确认是：

- unknown non-zero lifecycle；
- SKU/quantity context 不完整；
- currency/timezone 冲突。

未知非零事件默认阻断 execute，先取真实 transaction 样本再定义规则。

### 4.3 units 比 Seller Central 少

先区分金额 unit 与 COGS unit。2026-06 的 2 个缺口来自：

```text
RELEASED Shipment amount=0
```

它们不进 revenue，但必须进 COGS。不要直接用 Orders 总销量覆盖 Finances units，否则会造成双计。

## 5. Missing cost / FNSKU 问题

Monthly Financial Close 出现：

```text
missing_cost_skus=[...]
costed_units < expected_units
finances_natural_month_coverage=needs_review
```

按顺序检查：

```text
1. source SKU 是否直接存在 amazon_sku_cost
2. 若不存在，source SKU 是否其实是 FNSKU
3. amazon_inventory_daily 中截至目标月末是否能唯一映射 seller_sku
4. canonical seller_sku 是否存在目标日期有效成本
5. 若映射歧义或无成本，继续 fail closed
```

禁止给未知商品套用相似商品成本。

历史已验证：

```text
X004Q3AKFX -> HU-4XAJ-PYLD -> Trading Card Binder -> USD 6.94 all-in
X004WU7DSH -> SC-9HC3-5TFL -> Grey Neck Wallet -> USD 4.6971 landed
```

## 6. Settlement 异常

Settlement 是 Settlement Close / Amazon cash reconciliation，不是 Natural-Month Management P&L 的月份主源。

异常时分别检查：

- explicit date parsing (`YYYY-MM-DD`, `DD.MM.YYYY`)；
- US expected currency = USD；
- same report ID same content duplicate collection path；
- same report ID different content conflict；
- late-generated Settlement 是否重新 discovery；
- exact immutable source identity repair 是否需要 dry-run。

不要按 `source_row_hash` 单独删重；同一原始文件中不同 `source_row_index` 可以合法拥有相同 row hash。

## 7. Ads timing reconciliation

Management P&L 使用 Ads API report-date spend。Finances/Settlement 中的 Amazon Ads charge 只作 posted-charge reference。

因此：

```text
Settlement/Finances Ads vs Ads API spend 大差异
```

可以是 warning，不应仅凭 timing difference 阻断月报。真正阻断项是数据缺失、unknown/unclassified、成本缺失/币种冲突等 correctness 问题。

## 8. Artifact / automation audit 尾处理

v1.90.3 修复了 Finances `raw_pages.json` / `prepared_rows.json` 这类 JSON array root 被 audit helper 当 dict 调用 `.get()` 的问题。

若业务命令 `commands=N failed=0` 后仍出现 Traceback：

1. 先确认数据库业务写入是否已经完成；
2. 查 `artifact_save` / `artifact_audit`；
3. 区分 telemetry 尾处理错误与 ingestion 错误；
4. 不要因为 audit 尾处理失败就重复 repair 财务数据。

v1.90.3 July 生产基准：

```text
artifact_save scanned=169 saved=169 skipped=0
execution = Succeeded
```

## 9. Report send_guard

历史 2026-05 / 06 / 07 已发送过的 delivery pack 不重发。

出现：

```text
This delivery pack already has status=sent
```

属于正常保护。不要使用 `--force-resend`，除非业务负责人明确要求重新发送并已确认内容/收件人。

出现 `needs_review` / `no_data` 也不要用 `--allow-blocked` 绕过财务正确性检查。

## 10. Azure Container Apps Job 配置变更注意事项

### 10.1 一次性 smoke/debug

优先：

```text
job show -> 导出 properties.template -> 修改本次 template -> job start --yaml
```

这样不改永久 Job 配置。

### 10.2 永久 command/args

Cloud Shell / Azure CLI 对 `--args "-c" ...` 可能把 `-c` 误解析成 CLI 参数。已验证更稳妥的方式是：

1. 导出当前 `properties.template`；
2. 用 `jq` 修改 `containers[0].command/args`；
3. 只 PATCH `properties.template`；
4. `az rest --body @file`，让 CLI 使用 `application/json`；
5. PATCH 后必须 `job show` 验证。

不要使用 `application/merge-patch+json`：当前 Jobs endpoint 实测只接受 `application/json`。

也不要用通用 `az resource update` 回写整个 Job：它可能重新校验仅有 secret reference 的现有 secrets，并报 `value or keyVaultUrl and identity should be provided`。

### 10.3 成功标记必须绑定命令退出码

不要写：

```bash
az rest ...
echo PATCH_COMPLETE
```

应写：

```bash
az rest ... -o none \
&& echo PATCH_COMPLETE \
|| { echo PATCH_FAILED; exit 1; }
```

## 11. 当前生产基线

```text
Version: v1.90.3
Image SHA: 2fa19ad316720742d1871765fa0c1149c6b9fb9a
Monthly jobs:
  sdp-monthly-submit
  sdp-monthly-collect-ingest
  sdp-monthly-report-delivery
```

正式 `collect_ingest` 无 `--continue-on-error`。

July production smoke：

```text
execution=sdp-monthly-collect-ingest-cbacfwp
status=Succeeded
commands=11 failed=0
Finances attempted=161 inserted=0 updated=161 review_required=0
Settlement attempted=1628 inserted=0 updated=1628
artifact_save scanned=169 saved=169 skipped=0
```
