# 祥泰仓库数据管理平台

这是一个基于 Litestar + React 的仓库碳数据收集与管理系统。项目从 Litestar Fullstack 模板演进而来，但当前仓库已经按业务项目重新整理：后端提供 API、认证、权限、碳排放与仓库数据管理能力，前端使用 Vite + React + TanStack Router，开发阶段推荐在本机裸跑前后端，Docker 只负责基础设施。

## 技术栈

- 后端：Litestar、SQLAlchemy 2.0、Advanced Alchemy、Alembic、SAQ
- 前端：React、Vite、TanStack Router、TanStack Query、Tailwind CSS
- 数据：PostgreSQL、Redis/Valkey
- 开发工具：uv、bun、Ruff、Biome、Pyright、mypy
- 本地基础设施：Docker Compose 管理 Postgres、Redis、Mailpit、RustFS

## 本地端口

项目使用一组连续端口，避免和其他本机服务冲突：

| 服务 | 地址 |
| --- | --- |
| 后端 API | `http://localhost:18100` |
| 前端 Vite | `http://127.0.0.1:18101` |
| PostgreSQL | `localhost:18102` |
| Redis/Valkey | `localhost:18103` |
| Mailpit UI | `http://localhost:18104` |
| SMTP | `localhost:18105` |
| S3 API | `http://localhost:18106` |
| S3 Console | `http://localhost:18107` |

## 快速启动

首次安装：

```bash
make install
```

启动基础设施、迁移数据库、创建开发账号：

```bash
make start-infra
make db-upgrade
make create-root-user
```

裸跑前后端：

```bash
make dev
```

也可以拆成两个终端：

```bash
make dev-api
make dev-web
```

打开前端：

```text
http://127.0.0.1:18101/login
```

开发账号：

```text
root@example.com
12345678
```

## 发布到私有 Registry

项目已经支持直接构建并推送单镜像到私有 Registry，`app / worker / migrator` 三个服务复用同一镜像。

完整线上发布、数据库恢复、验收与回滚流程见：

- [docs/usage/production-release-runbook.md](/Users/eziohelios/Dev/litestar-fullstack/docs/usage/production-release-runbook.md)

### 1. 本机构建并推送

```bash
IMAGE_REPO=registry.xzzandzyc.store:5000/project/warehouse-carbon \
IMAGE_TAG=$(git rev-parse --short HEAD) \
PLATFORM=linux/amd64 \
./scripts/build_push_multiarch.sh

This script now uses local `docker build` for `linux/amd64`, then tags and pushes the built image to the registry.
```

如果要同时推送 `latest`，脚本默认会附带 `:latest`。

### 2. 服务器拉取并启动

服务器准备好 `.env.docker` 后，设置镜像地址：

```bash
export APP_IMAGE=registry.xzzandzyc.store:5000/project/warehouse-carbon:latest
docker compose -f tools/deploy/docker/docker-compose.yml pull
docker compose -f tools/deploy/docker/docker-compose.yml up -d
```

如果你要固定版本，把 `latest` 换成具体 tag 即可。

### 3. Nginx 反向代理

Nginx 只需要把域名代理到容器暴露的应用端口，例如 `127.0.0.1:18100` 或你服务器映射的 80xx 端口。前后端无需分离部署。

## 常用命令

```bash
make help              # 查看所有命令
make start-infra       # 启动本地基础设施
make stop-infra        # 停止本地基础设施
make infra-logs        # 查看基础设施日志
make db-upgrade        # 执行 Alembic 迁移
make create-root-user  # 创建本地 root 用户
make dev-api           # 启动后端
make dev-web           # 启动前端
make dev               # 同时启动前后端
make types             # 导出 OpenAPI 并生成 TS client
make build-emails      # 构建邮件模板 HTML
make build-assets      # 构建前端静态资源
make ruff              # Python lint/format
make biome             # 前端 lint/format
make test              # 后端测试
```

## 生成物策略

以下内容不提交到 Git，由本地或 CI 生成：

- `src/js/web/src/lib/generated/`
- `src/js/web/src/routeTree.gen.ts`
- `src/py/app/server/static/email/`
- `src/py/app/server/static/web/`
- 前端 `node_modules`
- 本地 `.env`

需要生成时运行：

```bash
make types
make build-emails
make build-assets
```

## 旧库数据导入

仓库内保留了迁移工具：

```text
tools/legacy_migration/
tools/diagnostics/db/
```

旧库 SQL dump 不提交到 Git。当前本机已验证过的 dump 路径是：

```text
/Users/eziohelios/Dev/xtck_deploy/db_xtck_20260203.sql
```

推荐流程是先把 dump 恢复到临时旧库，再通过迁移脚本导入当前开发库：

```bash
docker exec fullstack-spa-db-1 psql -U app -d postgres -c "DROP DATABASE IF EXISTS legacy_xtck;"
docker exec fullstack-spa-db-1 psql -U app -d postgres -c "CREATE DATABASE legacy_xtck;"
cat /path/to/db_xtck_20260203.sql | docker exec -i fullstack-spa-db-1 psql -U app -d legacy_xtck

OLD_DB_URL='postgresql+psycopg://app:app@localhost:18102/legacy_xtck' \
NEW_DB_URL='postgresql+psycopg://app:app@localhost:18102/app' \
TARGET_TEAM_SLUG='default-tenant' \
uv run python tools/legacy_migration/migrate_all.py
```

迁移入口只读旧库：区域和设备按业务编码进行租户内幂等映射，累计电表读数直接写入 `MeterReadingFact`；若源库包含旧 Scope 台账，则规范化为 `GhgActivityRecord`，随后通过新盘查用例生成参数、组织边界、计算运行和报告。迁移按来源表和来源 ID 幂等更新，不再清空目标表，也不再创建旧 Scope 表旁路。

## 目录结构

```text
src/
├── py/
│   ├── app/          # Litestar 后端应用
│   └── tests/        # 后端测试
└── js/
    ├── web/          # React SPA
    └── templates/    # React Email 模板

tools/
├── legacy_migration/ # 旧库迁移工具
├── diagnostics/db/   # 数据库诊断脚本
└── dev/              # 本地开发辅助脚本
```

## Git 分支

当前项目主开发分支是：

```text
project
```

远程 `main` 保留 fork 来源历史；本项目后续开发建议基于 `project`。
