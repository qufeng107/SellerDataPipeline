# CI Quality Gate Policy

> 状态：Implemented  
> 日期：2026-08-08  
> 适用范围：GitHub Actions CI、Ruff、本地代码质量检查

## 1. 背景

项目 CI 原配置使用 Ruff：

```toml
select = ["E", "F", "I", "UP", "B"]
```

并在每次 push / pull request 执行：

```bash
ruff check src tests
```

实际迭代中，`I001`（import block 未排序/格式化）这类可由 `ruff --fix` 自动处理的纯风格问题，会让整个 CI 退出码为 1。2026-08-08 的 schema guard resilience 更新即因 `ads_ingestion_dry_run.py` import block 的格式差异触发失败；该问题不影响 Python 运行、业务逻辑、数据库写入或 Azure 自动化。

对于当前小团队、自动化运营型项目，CI 应优先保护**运行正确性和回归风险**，而不是把低风险格式差异升级成发布阻断。

## 2. 需求

CI 必须满足：

1. 继续保留静态检查，不能因为一次风格误报就完全取消 Ruff。
2. 会明显影响运行正确性的错误必须阻断合并/发布。
3. import 排序、语法现代化等可自动修复的维护规则不应阻断 CI。
4. 本地仍提供一条简单命令自动整理 import / pyupgrade / format。
5. 规则集中维护在 `pyproject.toml`，避免 workflow 与本地规则漂移。

## 3. 冻结规则

### 3.1 CI blocking rules

`pyproject.toml` 的默认 Ruff selection 调整为：

```toml
select = ["E4", "E7", "E9", "F", "B"]
```

含义：

- `E4`：import / module 结构中的高信号 pycodestyle 错误；
- `E7`：statement 结构错误；
- `E9`：运行前即可发现的语法/缩进/IO 类严重错误；
- `F`：Pyflakes，例如 undefined name、无效引用、明显静态错误；
- `B`：flake8-bugbear，捕获常见潜在 bug。

CI 继续执行：

```bash
ruff check src tests
```

### 3.2 Non-blocking maintenance rules

以下规则不再属于 CI blocking gate：

- `I`：isort/import sorting；
- `UP`：pyupgrade。

本地需要整理时执行：

```bash
ruff check src tests scripts --select I,UP --fix
ruff format src tests scripts
```

它们仍然有维护价值，但失败不代表生产代码不可运行。

## 4. 为什么不直接删除 Ruff

完全取消 lint 会丢失很多低成本、高价值的静态保护，例如：

- 拼错变量名但测试没有覆盖；
- undefined name；
- 无效 import/reference；
- 某些异常处理、默认参数、循环/闭包等潜在 bug；
- 基础语法/结构问题。

因此本次不是“降低质量”，而是把 CI 从**风格一致性 gate**调整为**正确性 gate**。

## 5. 为什么不让 CI 自动 `--fix`

CI 运行在远端临时 checkout。即使执行 `ruff --fix`，修复后的文件也不会自然回写开发分支，而且会让“CI 到底检查的是提交内容还是临时修改后的内容”变得不清晰。

自动修复应发生在本地开发/生成交付包阶段；远端 CI 只负责判断提交是否满足 blocking contract。

## 6. 验收

本次验收标准：

- `I001` 不再导致 GitHub Action failure；
- `F` / `B` / E4/E7/E9 类问题仍会返回非零退出码；
- pytest gate 保持不变；
- 当前已知 `ads_ingestion_dry_run.py` import block 同时手工整理，避免遗留明显格式问题；
- 不修改业务逻辑、数据库 schema 或 Azure Job 配置。

## 7. 后续规则调整原则

新增 Ruff 规则前先问两个问题：

1. 该规则失败是否很可能意味着运行错误、数据错误或难以发现的 bug？
2. 如果只是格式/偏好，是否可以由 formatter 或 `--fix` 在本地自动处理？

只有第一类默认进入 blocking gate；第二类优先作为 non-blocking maintenance。
