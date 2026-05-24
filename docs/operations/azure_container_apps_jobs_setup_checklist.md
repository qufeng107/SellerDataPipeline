# Azure Container Apps Jobs Setup Checklist

---

## 9. Git branch / image tag strategy

本项目采用 `dev` 与 `main` 分支分层发布：

```text
dev  branch -> GHCR image tag :dev
main branch -> GHCR image tags :latest and :main
all branches -> immutable tag :<git-sha>
```

规则：

1. `dev` 分支用于开发和云端手动 smoke test。Azure 测试 job 可临时使用：
   `ghcr.io/<owner>/seller-data-pipeline:dev`
2. `main` 分支代表可发布版本。正式 Azure jobs 应使用：
   `ghcr.io/<owner>/seller-data-pipeline:latest`
   或更稳的不可变 SHA tag。
3. `dev` 分支不再推送 `latest`，避免开发镜像覆盖生产 job 使用的镜像。
4. 第一阶段先手动创建 Azure jobs 并手动触发；等 jobs 稳定后，再新增 main-only GitHub Actions deploy workflow 更新 Azure jobs。

