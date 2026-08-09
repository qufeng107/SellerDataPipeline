# Feature: Settlement Correctness & Late Discovery Recovery

> 状态：Implemented locally / Azure verification pending  
> 版本：v1.88  
> 更新时间：2026-08-09  
> 数据库影响：无 migration；只修改 ingestion guard、查询日期口径、历史 maintenance 和 monthly automation。

## 1. 背景与生产证据

2026-05 至 2026-07 Monthly Financial Close 与 Seller Central Monthly Transaction 人工对账暴露三类财务完整性问题：

1. 同一个 Amazon `source_report_id=115300020602` 曾从不同 collection-date raw path 再次进入历史数据，5 月出现 exact source identity duplicates；旧月报因此放大 sales / fees / refunds。
2. Amazon-generated Settlement 可能在月末交易之后数日才生成。2026-07 Seller Central 已存在 `settlement_id=27207351391`，但 8 月 5 日 discovery 时尚未入库，后续 collect-only rerun 也不会自动再次 discovery。
3. Amazon-generated Settlement raw file 已观察到 `DD.MM.YYYY`，例如 `07.03.2026`。SQL Server 无 style 的 `TRY_CONVERT(date, raw)` 会受 session 日期解释影响，把 7 March 错读为 July 3。
4. `getReports` 返回的 Amazon-generated Settlement 有时不带 `marketplaceIds`。旧 discovery 代码会把 request filter marketplace 直接当成已验证 marketplace，导致 CAD Settlement 被保存/标记到 US `ATVPDKIKX0DER` 路径并进入财务表。

这些问题说明“schema 正确 + upsert 成功”不等于“财务归属正确”。v1.88 的目标是对 Settlement 增加内容级 integrity guard，并让 late-generated report 可在月度 collect rerun 中自动发现。

## 2. 冻结规则

### 2.1 日期解析

Settlement 财务日期只接受显式、无歧义格式：

```text
YYYY-MM-DD[...]
DD.MM.YYYY[...]
```

SQL 查询禁止再使用无 style 的 `TRY_CONVERT(date, raw_value)` fallback。当前 SQL helper 显式使用：

```text
style 23  -> YYYY-MM-DD
style 104 -> DD.MM.YYYY
style 112 -> YYYYMMDD defensive compatibility
```

非空但无法解析的 Settlement 日期在 ingestion dry-run 阶段 fail closed / requires review。

### 2.2 Marketplace / Currency attribution

只对已人工验证的 marketplace 建立保守 currency contract。当前首个 contract：

```text
ATVPDKIKX0DER / Amazon US -> USD
```

US Settlement raw file 若只有一个明确的非 USD currency（例如 CAD），则可证明它属于其他市场：该文件被 `foreign_marketplace_report` 安全隔离，不进入 normalized preview/write，也不阻断同批其他有效 USD reports。若 currency 缺失或同报告混合 USD/其他币种，则无法安全归属，必须 `content_validation_requires_review` fail closed。非空 `marketplace-name` 若不符合已验证的 `Amazon.com` contract 也要求 review。

未知 marketplace 暂不猜币种，保持现有行为；后续市场上线时必须先补 marketplace metadata + regression test。

### 2.3 Duplicate raw report ID

同一 ingestion 输入中，按 Amazon immutable `report_id` 去重 raw file：

- report ID 相同、bytes 相同：仅处理 collection date 最新的一份。
- report ID 相同、bytes 不同：fail closed；禁止静默选择。

不改变 transaction business key。特别是同一个 Amazon raw file 内相同 `source_row_hash` 的多行仍保留，因为它们可能是 Amazon 原始文档中的合法重复 component；只有 immutable source identity 完全相同的历史行才由既有 `repair_settlement_idempotency.py` 清理。

### 2.4 Late Settlement discovery

Monthly `collect_ingest` 每次执行前先重新执行 Settlement V2 `getReports` discovery，然后再 collect + ingest；该 financial-close discovery 使用 `--fail-on-error`，任何 discovery item 失败都必须让 stage 非零退出，禁止把“未发现到数据”和“发现请求失败”混为一谈。

因此：

```text
monthly submit discovery
-> 初次 collect_ingest rediscovery
-> 若月末 Settlement 晚生成，后续 collect_ingest rerun 再次 rediscovery
```

不再依赖“submit 阶段 discovery 一次后永久不变”。

生产调度仍建议在月末后保留 grace period，并在 final close 前至少执行一次较晚的 collect_ingest。

## 3. Historical Repair

v1.88 不自动删除历史财务数据。提供两条显式 maintenance path：

```text
python scripts/repair_settlement_idempotency.py \
  --marketplace-id ATVPDKIKX0DER --json
```

用于 exact source identity duplicates；以及：

```text
python scripts/repair_settlement_marketplace_integrity.py \
  --marketplace-id ATVPDKIKX0DER --json
```

用于 audit foreign-currency source reports。

后者只有在“整个 source report 的所有非空 currency 都是同一个、且明确不等于 marketplace verified currency”时才标为 repairable；缺 currency 或 mixed currency 一律 conflict / fail closed。`--execute` 有任何 conflict 时不删除任何行。

## 4. Reporting Query Guard

Monthly Financial Close、legacy Finance preview、WBR Settlement preview、WAOR Settlement Ads reconciliation 使用同一 explicit Settlement date SQL helper。

对已验证 marketplace，财务查询额外限制 expected currency。这样即使历史 foreign-currency rows 尚未 maintenance 删除，也不会继续进入 US profit calculation。

Monthly report version 从：

```text
v1.3-landed-cogs-executive-pnl
```

升级为：

```text
v1.4-settlement-correctness
```

## 5. Discovery Manifest Auditability

当 Amazon `getReports` item 自己提供 `marketplaceIds` 时：

```text
marketplace_ids_source = amazon_response
```

当 response 不提供，只能沿用 API request filter 以便完成下载时：

```text
marketplace_ids_source = request_filter_fallback_unverified
response_marketplace_ids = []
```

这明确区分“Amazon 响应证明的 marketplace”与“仅为下载路径/筛选使用的 fallback”。最终财务归属必须由 raw Settlement currency content guard 再验证。

## 6. 非目标

- 不新增 normalized date columns / migration。
- 不按 `source_row_hash` 单独去重 Amazon raw file 内的合法多行。
- 不使用 Seller Central 手工 Monthly Transaction 作为自动 ingestion source；它继续作为人工 reconciliation benchmark。
- 不在代码中猜测所有全球 marketplace currency；新增市场时逐个验证并补 metadata。
- 不自动发送历史修正版邮件。

## 7. 本地验收

必须通过：

```text
PYTHONPATH=src pytest -q
python -m compileall -q src scripts tests
ruff check src scripts tests
```

关键 regression：

- `07.03.2026` -> 2026-03-07，不得进入 July。
- US raw Settlement 单一 currency=CAD -> `foreign_marketplace_report` 安全隔离 / no prepared rows / 不阻断其他 USD files；mixed/missing currency 或非 `Amazon.com` marketplace name -> ingestion requires_review。
- 相同 report ID + 相同 bytes 多路径 -> 只处理 1 份。
- 相同 report ID + 不同 bytes -> fail closed。
- Monthly collect_ingest 第一条 command 必须重新 discovery Settlement V2。
- discovery response 缺 marketplaceIds 时 manifest 必须标记 fallback unverified。
- foreign-currency historical repair 默认 dry-run，mixed currency conflict 阻断 execute。

## 8. Azure 升级/恢复顺序

1. CI 通过后构建 v1.88 main image。
2. 更新 `sdp-monthly-collect-ingest` 和 `sdp-monthly-report-delivery`；monthly submit 同步更新可保持镜像一致。
3. 先运行 marketplace integrity repair dry-run；只在 `conflicts=0` 且计划符合预期时 execute。
4. 再运行 existing idempotency repair dry-run；确认 5 月 multi-path exact duplicates 后 execute，并二次 dry-run 验证 `duplicate_group_count=0`。
5. 对 2026-07 重新运行 monthly `collect_ingest`；新的第一步 rediscovery 应发现 late Settlement `27207351391`，随后 collect + ingest。
6. 对 2026-05 / 06 / 07 重新生成 report preview，不发送邮件。
7. 用 Seller Central 5/6/7 Monthly Transaction CSV 做逐月 reconciliation；在 sales / refund / FBA fee / promotion / subscription / reimbursement 等关键 bucket 解释清楚前，不恢复董事会正式数字。
