# ADR-014: CI 静态检查采用“高信号正确性阻断，纯风格非阻断”策略

> 状态：Accepted  
> 日期：2026-08-08  
> 决策范围：GitHub Actions、Ruff、代码合并/发布质量门禁

## 背景

项目此前的 Ruff 默认规则同时启用了 `E/F/I/UP/B`。其中 `I`（import sorting）和 `UP`（pyupgrade）主要承担代码整理与现代化职责，但它们与 undefined name、潜在 bug 等 correctness 问题一样都会让 CI 直接失败。

在高频 AI-assisted 迭代中，这会造成低价值重复修复：代码和测试逻辑正确，但仅因 import block 顺序/空行等问题无法通过 CI。

## 决策

CI 保留 Ruff，但 blocking gate 只保留高信号规则：

```toml
select = ["E4", "E7", "E9", "F", "B"]
```

`I` 与 `UP` 从默认 blocking selection 中移除，改为本地非阻断维护：

```bash
ruff check src tests scripts --select I,UP --fix
ruff format src tests scripts
```

pytest 继续作为独立 blocking gate。

## 原因

1. 静态检查仍能在测试覆盖之外捕获真实代码风险。
2. import sorting/pyupgrade 具有维护价值，但不值得造成生产交付中断。
3. 对小团队而言，CI 的信噪比比规则数量更重要。
4. 自动修复应发生在本地/交付前，而不是依赖远端 CI 修改 checkout。
5. 规则分层后，开发者更容易理解“红灯意味着可能有 bug”，减少对 CI 的疲劳和忽略。

## 后果

正面：

- `I001` 等纯风格差异不再阻断合并。
- CI 红灯更聚焦于真正需要人工判断的问题。
- Ruff 与 pytest 都继续保留，没有取消质量门禁。

代价：

- import 顺序和部分现代化写法可能短期不完全一致。
- 本地 formatter/auto-fix 需要在交付前按需执行。

## 约束

- 不得为了“让 CI 绿”而大范围 ignore `F` 或关闭 pytest。
- 如果 `B` 中某一条规则被证明确有持续误报，应针对单条规则评估/ignore，而不是移除整个 `B` 类别。
- 新增 blocking lint 规则必须能够说明其运行/数据正确性价值。

## 相关文档

- `docs/project/ci_quality_gate_policy.md`
- `docs/project/development_rules.md`
- `docs/project/iteration_workflow.md`
- `pyproject.toml`
- `.github/workflows/ci.yml`
