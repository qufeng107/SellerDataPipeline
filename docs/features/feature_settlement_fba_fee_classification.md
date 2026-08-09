# Settlement FBA Fee Classification Coverage

> 文档状态：Implemented locally / Azure verification pending  
> 更新时间：2026-08-09  
> 迭代版本：v1.86  
> 相关功能：`feature_settlement_ingestion.md`、`feature_monthly_financial_close_report.md`

## 1. 功能摘要

2026-07 Monthly Financial Close preview 被 `unknown/unclassified` 金额 `-35.45 USD` 阻断。生产只读诊断确认该金额不是异常交易，而是两种正常 `FBAFees` 组合未被 Settlement parser 覆盖：`FBA Inventory Storage Fee / Base fee` 与带动态 ASIN/日期后缀的 `FBA Customer Returns Fee (...) / Base fee`。

v1.86 仅补充这两种已确认真实数据的保守分类规则，不修改 Settlement 金额、business key、JSON set-based MERGE、数据库结构或 Financial Close send guard。

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认 |
| 生产数据诊断 | 已完成 |
| Parser | 已完成 |
| Repository/upsert | 不变 |
| Azure SQL schema | 不变 |
| 单元测试 | 已完成 |
| Azure 重跑验证 | 待执行 |
| 文档同步 | 已完成 |

整体状态：`Implementing`，待 v1.86 main image 在 2026-07 `collect_ingest` + Financial Close preview 中完成生产验收后转为 `Implemented`。

## 3. 生产问题与证据

2026-07 Financial Close preview：

```text
settlement_rows=447
settlement_net=762.12
internal_cogs=333.60
estimated_profit=428.52
reconciliation_needs_review=2
unknown_bucket_amount=-35.45
unclassified_amount=-35.45
send_allowed=False
```

只读 SQL 诊断定位到：

```text
FBAFees | FBA Inventory Storage Fee
amount_description=Base fee
rows=1
amount_total=-32.75

FBAFees | FBA Customer Returns Fee (Non-Apparel and Non-Shoes)
          for ASIN: B0G1YF2W1D (2026-04-01 to 2026-06-30)
amount_description=Base fee
rows=1
amount_total=-2.70

sum=-35.45
```

两个 reconciliation error 是同一 `-35.45` 同时落入 `amount_category=unclassified` 与 `profit_bucket=unknown` 后被两项 guard 重复发现，不代表存在两笔额外差异。

## 4. 冻结分类规则

| transaction_type | amount_type | amount_description | amount_category | profit_bucket |
|---|---|---|---|---|
| `FBAFees` | `FBA Inventory Storage Fee` | `Base fee` | `storage_fee` | `fba_storage_fee` |
| `FBAFees` | `FBA Customer Returns Fee (...)` | `Base fee` | `fba_customer_returns_fee` | `fba_fee` |

实现原则：

- Storage Fee 同时支持已存在的 description-based 规则和本次真实数据中的 amount-type 规则。
- Customer Returns Fee 只在 `transaction_type=FBAFees` 且 normalized `amount_type` 以 `fbacustomerreturnsfee` 开头时匹配。
- 不使用宽泛的 `"fee" in amount_type`，避免未来未知 Amazon fee 被静默错误归类。
- Customer Returns Fee 后面的服装类别、ASIN、日期范围视为动态 suffix，不参与精确枚举。
- 未命中的新组合仍回落 `unclassified / unknown` 并由 send guard 阻断。

## 5. 代码变化

```text
src/seller_data_pipeline/parsers/amazon/settlement_report_parser.py
  storage:
    amount_kind == "fbainventorystoragefee"
    OR existing description contains "storagefee"
    -> storage_fee / fba_storage_fee

  customer returns:
    transaction == "fbafees"
    AND amount_kind.startswith("fbacustomerreturnsfee")
    -> fba_customer_returns_fee / fba_fee
```

新增两个真实字符串回归测试：

```text
FBA Inventory Storage Fee / Base fee / -32.75
FBA Customer Returns Fee (...) / Base fee / -2.70
```

## 6. 非范围

本迭代不做：

- 不重新 submit 2026-07 Amazon reports。
- 不手工 UPDATE Settlement 财务行。
- 不修改 v1.85 typed OPENJSON / MERGE 路径。
- 不新增 migration 或数据库字段。
- 不绕过 `send_guard`。
- 不扩大为“所有 FBAFees 自动归类为 fba_fee”。

## 7. 幂等性与财务影响

2026-07 Settlement 原始金额不变，重新 `collect_ingest` 时 v1.85 immutable business key + set-based MERGE 会幂等更新已有 normalized rows。

因此以下主值原则上不因本分类补丁改变：

```text
settlement_net=762.12
internal_cogs=333.60
settlement-led estimated_profit=428.52
```

预期变化仅是：

```text
-32.75 unclassified/unknown -> storage_fee/fba_storage_fee
-2.70  unclassified/unknown -> fba_customer_returns_fee/fba_fee
unknown/unclassified total  -> 0.00
```

## 8. 验收标准

本地：

- 两个真实 FBA fee regression tests 通过。
- 全量 pytest 通过。
- compileall 通过。
- CI Safety lint 通过。

Azure：

1. v1.86 main image 更新 monthly jobs。
2. 不重新 submit，直接重跑 `2026-07 collect_ingest`。
3. Settlement ingestion `status=success`，stage `commands=9 failed=0`。
4. 重新生成 2026-07 Financial Close preview。
5. `unknown_bucket_amount=0`、`unclassified_amount=0`，且无其他真实阻断项。
6. `Monthly Financial Close status=ok`、`send_allowed=True` 后才发送 7 月月报。
