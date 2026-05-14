# Amazon 数据样例记录目录

本目录只用于保存**脱敏后的字段说明、header 清单、样例分析结论**，不要提交 Amazon 原始报表文件、真实订单数据、真实财务明细或任何密钥。

原始下载文件应保存到本地未提交目录，例如：

```text
reports/raw/amazon/...
```

字段确认流程：

```text
下载 raw file
  ↓
生成本地 manifest
  ↓
提取 header / 少量脱敏样例
  ↓
更新本目录中的样例分析记录
  ↓
更新 requirements/database_spec.md
  ↓
再更新 SQL migration
```
