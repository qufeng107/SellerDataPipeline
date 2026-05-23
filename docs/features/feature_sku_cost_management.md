# Feature: SKU 成本模板导出与导入

> 状态：Implemented / manual-first v1  
> 更新时间：2026-05-18  
> 设计原则：成本由人工确认，系统只负责生成待填模板、校验和写入 `amazon_sku_cost`。

## 1. 背景

利润核算已冻结为 `Settlement-led Financial Profit v1.0`。Amazon Settlement 能给出真实入账金额，但不会知道公司的真实采购价、包装费、头程/海运/清关/入仓分摊成本。

因此 SKU 成本必须作为独立的内部成本输入功能维护，不能在利润脚本里临时手写，也不能从 Amazon 报表中推断。

## 2. 功能目标

本功能提供两个手动脚本：

```powershell
python scripts/export_sku_cost_template.py --marketplace-id ATVPDKIKX0DER
python scripts/import_sku_cost_template.py --file runtime/sku_cost_templates/ATVPDKIKX0DER/sku_cost_template.xlsx
python scripts/import_sku_cost_template.py --file runtime/sku_cost_templates/ATVPDKIKX0DER/sku_cost_template.xlsx --execute
```

流程：

```text
数据库 SKU universe
-> 导出 xlsx 成本模板
-> 人工填写 new_* 成本列
-> dry-run 导入校验
-> execute 写入 dbo.amazon_sku_cost
-> 利润 preview 读取 amazon_sku_cost
```

## 3. 为什么不在亚马逊后台填写

`amazon_sku_cost` 是公司内部成本表。Amazon 后台通常没有采购价、包装成本、头程海运成本、清关/入仓分摊等真实内部成本；这些数据来自采购、物流、会计或人工估算。

亚马逊数据只用于确定哪些 SKU 需要成本：

| 来源表 | 用途 |
|---|---|
| `amazon_listing_snapshot` | SKU、ASIN、标题、listing 参考。 |
| `amazon_inventory_daily` | 有库存但未必近期售出的 SKU。 |
| `amazon_order_item` | 近期订单中出现的 SKU。 |
| `amazon_settlement_transaction` | Settlement 中出现、利润核算需要匹配成本的 SKU。 |
| `amazon_sku_cost` | 最近一次成本记录参考。 |

## 4. 表格设计

导出的 xlsx 默认路径：

```text
runtime/sku_cost_templates/{marketplace_id}/sku_cost_template.xlsx
```

导出脚本默认幂等：如果目标文件已存在，会先删除旧文件再生成新文件。避免人工误用过期模板。

主 sheet：

```text
sku_cost_input
```

另有说明 sheet：

```text
README
```

`sku_cost_input` 分两类列：

### 4.1 参考列

这些列由系统填充，不作为新成本写入来源：

```text
marketplace_id
seller_sku
asin
product_name
sku_sources
latest_source_date
current_product_cost
current_first_mile_cost
current_packaging_cost
current_other_unit_cost
current_currency
current_effective_from
current_effective_to
current_remark
current_updated_at
```

### 4.2 人工填写列

只有这些 `new_*` / note 列会被导入：

```text
new_product_cost
new_first_mile_cost
new_packaging_cost
new_other_unit_cost
new_currency
new_effective_from
new_effective_to
purchase_or_batch_note
new_remark
```

字段说明：

| 字段 | 含义 | 是否必填 |
|---|---|---|
| `new_product_cost` | 单件采购/货款成本 | 是，只要该行要导入。 |
| `new_first_mile_cost` | 单件头程、海运、清关、入仓分摊成本 | 否，空值导入为 0。 |
| `new_packaging_cost` | 单件包装、说明书、贴标等成本 | 否，空值导入为 0。 |
| `new_other_unit_cost` | 其他稳定可归属单件成本 | 否，空值导入为 0。 |
| `new_currency` | 成本币种 | 是。第一版建议与 marketplace 财务币种一致，例如美国站用 USD。 |
| `new_effective_from` | 成本生效日期 / 进货或批次开始日期 | 是。利润脚本按此日期匹配成本。 |
| `new_effective_to` | 成本结束日期 | 否，空值表示持续有效。 |
| `purchase_or_batch_note` | 进货时间、批次、换汇等备注 | 否，会合并进 `remark`。 |
| `new_remark` | 其他人工备注 | 否，会写入 `remark`。 |

## 5. 导入规则

### 5.1 默认 dry-run

导入脚本默认不写数据库：

```powershell
python scripts/import_sku_cost_template.py --file runtime/sku_cost_templates/ATVPDKIKX0DER/sku_cost_template.xlsx
```

只有加 `--execute` 才会写入：

```powershell
python scripts/import_sku_cost_template.py --file runtime/sku_cost_templates/ATVPDKIKX0DER/sku_cost_template.xlsx --execute
```

### 5.2 幂等键

默认按以下组合判断重复：

```text
marketplace_id + seller_sku + new_effective_from
```

如果同一成本记录已经存在，默认跳过，不重复插入。

### 5.3 更新已有记录

如果确实要修正同一天已经导入的成本，可显式使用：

```powershell
python scripts/import_sku_cost_template.py --file <xlsx> --execute --update-existing
```

不建议频繁使用该模式。正常成本变化应新增一条更晚的 `new_effective_from` 记录，而不是改历史成本。

### 5.4 关闭上一条开放成本

执行导入时，如果同一 SKU 之前存在 `effective_to IS NULL` 且 `effective_from` 早于新成本日期，脚本默认会把上一条 open-ended 成本关闭到新成本日期前一天，避免成本区间重叠。

可通过以下参数关闭这个行为：

```powershell
python scripts/import_sku_cost_template.py --file <xlsx> --execute --no-close-previous-open
```

第一版推荐保持默认行为。

## 6. 数据库写入

目标表：

```text
dbo.amazon_sku_cost
```

写入字段：

```text
marketplace_id
seller_sku
asin
product_cost
first_mile_cost
packaging_cost
other_unit_cost
currency
effective_from
effective_to
remark
```

不新增表，不新增 migration。

## 7. CLI 输出示例

导出：

```text
SKU cost template exported.
marketplace=ATVPDKIKX0DER
rows=1
generated_at_utc=2026-05-18T15:00:00+00:00
xlsx=runtime/sku_cost_templates/ATVPDKIKX0DER/sku_cost_template.xlsx
```

导入 dry-run：

```text
SKU cost import status=dry_run_ok dry_run=True
file=runtime/sku_cost_templates/ATVPDKIKX0DER/sku_cost_template.xlsx
candidate_rows=1 inserted=1 updated=0 skipped_existing=0 closed_previous=0
Dry-run only. Re-run with --execute after reviewing the summary.
```

导入 execute：

```text
SKU cost import status=executed dry_run=False
file=runtime/sku_cost_templates/ATVPDKIKX0DER/sku_cost_template.xlsx
candidate_rows=1 inserted=1 updated=0 skipped_existing=0 closed_previous=1
```

## 8. 与利润核算的关系

利润 preview 脚本只读取 `amazon_sku_cost`。如果某个 Settlement SKU 没有成本，利润 preview 应保持 `needs_review`，不能把缺失成本当作 0 生成正式利润。

本功能解决的是利润核算前置输入问题：

```text
先导入 SKU 成本
-> 再运行 calculate_profit_report.py
-> 人工复核 Settlement + COGS + warnings
```

## 9. 验收标准

功能完成需满足：

1. 能从数据库导出 SKU 成本 xlsx 模板。
2. 导出模板包含 SKU 参考信息和最近一次成本参考。
3. 导出默认删除旧 xlsx，保证幂等生成。
4. 导入脚本默认 dry-run，不写数据库。
5. 只有填写了人工成本输入列的行会被导入。
6. 缺少 `new_product_cost`、`new_currency`、`new_effective_from` 时阻塞导入。
7. 重复导入同一 `marketplace_id + seller_sku + effective_from` 默认跳过。
8. 可通过 `--update-existing` 显式更新已有记录。
9. execute 模式默认关闭上一条 open-ended 成本，避免有效期重叠。
10. 单元测试覆盖模板生成、读取、校验、跳过重复、更新已有、repository SQL。

## 10. 当前实现状态

| 日期 | 状态 | 证据 |
|---|---|---|
| 2026-05-18 | Implemented v1 | 新增 `scripts/export_sku_cost_template.py`、`scripts/import_sku_cost_template.py`、`sku_cost_service.py`、`sku_cost_repo.py` 和单元测试。 |

## 11. 后续优化

1. 加入模板版本号，避免旧模板结构被误导入。
2. 加入汇率表后支持 CNY 成本自动换算为 USD。
3. 对同 SKU 成本区间重叠做更严格数据库侧检查。
4. 增加导入审计日志到 `amazon_sync_run_log` 或独立 cost import log。
5. 如果 SKU 数量扩大，可增加管理后台页面替代 Excel。
