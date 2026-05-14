# GET_PROMOTION_PERFORMANCE_REPORT diagnostic sample

> 取样日期：2026-05-14  
> 文件类型：Amazon FATAL diagnostic document  
> 结论：该报告不能只靠 `dataStartTime` / `dataEndTime`，必须提供专用 `reportOptions`。

## Diagnostic message

```text
Please provide report options promotionStartDateFrom and promotionStartDateTo in the standard ISO-8601 zoned date and time format. For example: "2011-12-03T10:15:30Z".
```

## 后续处理

批量取样计划已更新为自动传入：

```text
promotionStartDateFrom = {data_start_time}
promotionStartDateTo   = {data_end_time}
```

该报告仍属于补充运营效果数据源。第一版促销成本口径优先来自 Settlement V2。
