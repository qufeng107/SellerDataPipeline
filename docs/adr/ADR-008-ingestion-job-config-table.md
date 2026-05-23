# ADR-008: Store Job Cadence in a Database Table

> 状态：Accepted  
> 日期：2026-05-18

## Context

不同 Amazon 数据源的更新频率不同。比如库存快照和广告适合每日更新，Settlement 更适合 discovery，Promotion/Coupon 在活动期间需要更高频，Inventory Ledger 偏周度或异常排查。

如果把周期写死在脚本、文档或 GitHub Actions YAML 中，后续自动化会难维护，也不利于按 marketplace/profile 调整。

## Decision

新增数据库配置表：

```text
pipeline_job_config
```

用于记录：

```text
job_key
job_group
script_path
default_args_json
recommended_cadence_unit
recommended_cadence_value
default_lookback_days
data_window_lag_days
execution_phase
enabled
```

运行结果继续记录在已有的：

```text
amazon_sync_run_log
```

两者分工：

```text
pipeline_job_config = 应该怎么跑
amazon_sync_run_log = 实际跑得怎么样
```

## Consequences

正面影响：

1. 手动流程和未来自动化使用同一份任务配置。
2. 可以按任务逐步从 `manual_first` 升级到 `scheduled_candidate` / `scheduled_active`。
3. Scheduler 可以结合 config 和 run log 自动判断是否需要运行。
4. 避免把周期硬编码进多个脚本。

限制：

1. 第一版不实现复杂 cron；只记录 unit/value/lookback。
2. 配置表不是最终 scheduler，只是 scheduler 的输入。
3. 表结构变更仍必须走 migration 流程。
