# 线上发布 Runbook

本文档总结了当前项目从本地开发环境发布到线上环境的标准流程，覆盖：

- 代码镜像发布
- 线上容器更新
- 数据库备份与恢复
- 将本地数据发布到线上
- 发布后的验收与回滚思路

当前确认过的线上环境信息：

- 服务器 SSH：`ssh -i ~/.ssh/huawei.pem root@116.63.218.160`
- 部署目录：`/root/warehouse`
- 线上域名：[https://warehouse.nexlca.com/](https://warehouse.nexlca.com/)
- 应用镜像仓库：`registry.xzzandzyc.store:5000/project/warehouse-carbon`

## 1. 发布前原则

### 1.1 代码发布原则

- 线上只运行容器镜像，不直接在服务器上同步本地源码。
- 本地完成构建、推送镜像，线上只做 `pull + recreate`。
- 尽量使用新 tag 发布。
- 如果因为历史原因复用了同一个 tag，线上必须显式 `docker pull`，不能只 `docker compose up -d`。

### 1.2 数据发布原则

- 先备份线上数据库，再做恢复或导入。
- 本地数据推线上前，必须明确这是“覆盖恢复”还是“增量导入”。
- 如果是整库恢复，默认会覆盖线上现有数据，必须先确认风险。

### 1.3 变更分离原则

建议把一次发布拆成三类动作独立执行和记录：

- 镜像发布
- 数据迁移 / 数据恢复
- 线上验收

## 2. 本地镜像构建与推送

项目当前已收敛为单平台 `linux/amd64` 本地构建，再推送到私有仓库。

### 2.1 标准命令

```bash
IMAGE_REPO=registry.xzzandzyc.store:5000/project/warehouse-carbon \
IMAGE_TAG=$(git rev-parse --short HEAD) \
PUSH_LATEST=true \
DOCKERFILE=tools/deploy/docker/Dockerfile \
./scripts/build_push_multiarch.sh
```

说明：

- `IMAGE_TAG` 建议使用 commit short sha，或者人工版本号，例如 `20260614-fix-bigscreen-csp`
- `PUSH_LATEST=true` 会同时推送 `:latest`
- 当前脚本内部实际使用本地 `docker build --platform linux/amd64`

### 2.2 构建成功的判断

以脚本输出为准，成功时应看到：

```text
[OK] Image pushed successfully
  - registry.xzzandzyc.store:5000/project/warehouse-carbon:<tag>
  - registry.xzzandzyc.store:5000/project/warehouse-carbon:latest
```

### 2.3 如果复用了已有 tag

即使 tag 没变，只要 push 后 digest 变了，线上仍然可以更新。但要注意：

- 不能只修改 `.env`，因为 `.env` 中 tag 可能没变
- 必须在服务器上先执行 `docker pull <image:tag>`
- 然后再 `docker compose up -d --force-recreate ...`

## 3. 线上代码发布

### 3.1 登录服务器

```bash
ssh -i ~/.ssh/huawei.pem root@116.63.218.160
cd /root/warehouse
```

### 3.2 查看当前部署状态

```bash
grep -E '^APP_IMAGE=' .env
docker compose ps
docker compose config --services
```

建议先确认线上到底有哪些服务，例如是否包含：

- `app`
- `migrator`
- `worker`
- `cache`

不要想当然地假设线上 compose 一定和本地完全一致。

### 3.3 标准发布命令

如果 `.env` 里的 `APP_IMAGE` 已经指向正确 tag，标准流程是：

```bash
docker pull registry.xzzandzyc.store:5000/project/warehouse-carbon:<tag>
docker compose up -d --force-recreate migrator app
```

如果线上还运行 `worker`，改为：

```bash
docker pull registry.xzzandzyc.store:5000/project/warehouse-carbon:<tag>
docker compose up -d --force-recreate migrator app worker
```

### 3.4 推荐的“带 digest 核对”流程

这个流程最稳，尤其适用于“tag 没变但镜像内容变了”的情况：

```bash
cd /root/warehouse

printf "[before] %s\n" "$(docker inspect --format='{{index .RepoDigests 0}}' registry.xzzandzyc.store:5000/project/warehouse-carbon:<tag> 2>/dev/null || echo missing)"

docker pull registry.xzzandzyc.store:5000/project/warehouse-carbon:<tag>

printf "[after] %s\n" "$(docker inspect --format='{{index .RepoDigests 0}}' registry.xzzandzyc.store:5000/project/warehouse-carbon:<tag>)"

docker compose up -d --force-recreate migrator app
docker compose ps
```

通过 `before / after` 可以直接确认是否真的拉到了新 digest。

## 4. 线上数据库备份

在执行数据库恢复、覆盖、导入之前，先备份线上库。

### 4.1 找到数据库连接信息

先查看线上 `.env`：

```bash
cd /root/warehouse
grep -E 'POSTGRES|DB|DATABASE' .env
```

如果 compose 里数据库不在当前服务器，而是外部数据库，优先按 `.env` 中连接串执行备份。

### 4.2 逻辑备份示例

如果已经有 `DATABASE_URL`，可在服务器上执行：

```bash
pg_dump --format=custom --file /tmp/warehouse-backup-$(date +%Y%m%d%H%M).dump "<DATABASE_URL>"
```

或者使用显式参数：

```bash
PGPASSWORD='<password>' pg_dump \
  -h <host> \
  -p <port> \
  -U <user> \
  -d warehouse \
  --format=custom \
  --file /tmp/warehouse-backup-$(date +%Y%m%d%H%M).dump
```

## 5. 将本地数据库数据发布到线上

### 5.1 适用场景

适用于：

- 本地已整理了最新主数据 / 演示数据
- 线上希望直接替换成当前本地数据状态
- 允许覆盖线上现有数据

不适用于：

- 线上已有真实业务数据且不能覆盖
- 只想做增量同步

### 5.2 本地生成 dump

建议使用 custom format：

```bash
pg_dump --format=custom --file /path/to/localhost-app-YYYYMMDDHHMM.dump "<LOCAL_DATABASE_URL>"
```

### 5.3 上传到服务器

```bash
scp -i ~/.ssh/huawei.pem /path/to/localhost-app-YYYYMMDDHHMM.dump root@116.63.218.160:/tmp/
```

### 5.4 线上恢复到 `warehouse` 数据库

恢复前先确认目标库存在，并且已经做过备份。

标准恢复命令示例：

```bash
PGPASSWORD='<password>' pg_restore \
  -h <host> \
  -p <port> \
  -U <user> \
  -d warehouse \
  --clean \
  --if-exists \
  /tmp/localhost-app-YYYYMMDDHHMM.dump
```

说明：

- `--clean --if-exists` 表示恢复前先删除已有对象，再重建
- 这属于“覆盖式恢复”，不是增量合并

### 5.5 恢复后的动作

恢复完成后建议重跑一次应用迁移：

```bash
cd /root/warehouse
docker compose up -d --force-recreate migrator app
```

如果有后台任务进程，也一起重建：

```bash
docker compose up -d --force-recreate migrator app worker
```

## 6. 发布后的标准验收

### 6.1 容器状态

```bash
cd /root/warehouse
docker compose ps
docker compose logs --tail=100 app migrator
```

重点看：

- `migrator` 是否成功退出
- `app` 是否正常启动
- 是否出现明显的导入、迁移、静态资源错误

### 6.2 站点可用性

```bash
curl -I -s https://warehouse.nexlca.com/
```

至少确认：

- HTTP 状态码 `200`
- 核心安全响应头正常返回

### 6.3 静态资源检查

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://warehouse.nexlca.com/static/web/manifest.json
curl -s -o /dev/null -w '%{http_code}\n' https://warehouse.nexlca.com/static/web/maps/bigscreen/scene.json
curl -s -o /dev/null -w '%{http_code}\n' https://warehouse.nexlca.com/static/web/cesium/Assets/Images/ion-credit.png
```

### 6.4 页面级验收

建议至少人工检查：

- 登录页
- 首页
- 大屏页面
- 本次改动涉及的业务页面

如果浏览器控制台有报错，优先判断是：

- CSP 限制
- 静态资源 404
- 前端代码仍在访问隐式第三方服务
- 接口返回异常

## 7. 回滚方案

### 7.1 镜像回滚

如果只是代码问题，没有做破坏性数据恢复，最简单：

1. 把 `.env` 中的 `APP_IMAGE` 改回上一版 tag
2. 执行：

```bash
docker pull <old-image:tag>
docker compose up -d --force-recreate migrator app
```

### 7.2 数据回滚

如果做过覆盖式 `pg_restore`，代码回滚不够，必须恢复备份：

```bash
pg_restore \
  -h <host> \
  -p <port> \
  -U <user> \
  -d warehouse \
  --clean \
  --if-exists \
  /tmp/warehouse-backup-YYYYMMDDHHMM.dump
```

然后重建应用容器：

```bash
cd /root/warehouse
docker compose up -d --force-recreate migrator app
```

## 8. 常见坑

### 8.1 tag 没变，线上看起来“没更新”

根因通常是：

- 镜像仓库里同一个 tag 的 digest 已变
- 但服务器没有主动 `docker pull`
- `docker compose up -d` 直接复用了本地已有旧镜像

解决方法：

- 先 `docker pull`
- 再 `docker compose up -d --force-recreate`

### 8.2 构建成功，但线上静态资源 404

优先检查：

- 前端静态资源是否已被拷入运行镜像
- `manifest.json` 是否可访问
- Cesium 的 `Workers / Assets / ThirdParty / Widgets` 是否完整复制

### 8.3 数据恢复后应用异常

优先检查：

- 恢复的库是否和当前迁移版本兼容
- `migrator` 日志是否报错
- 恢复后是否重新跑过应用迁移

## 9. 一次标准发布的最小操作清单

### 代码发布

```bash
# 本地
IMAGE_REPO=registry.xzzandzyc.store:5000/project/warehouse-carbon \
IMAGE_TAG=$(git rev-parse --short HEAD) \
PUSH_LATEST=true \
DOCKERFILE=tools/deploy/docker/Dockerfile \
./scripts/build_push_multiarch.sh

# 线上
ssh -i ~/.ssh/huawei.pem root@116.63.218.160
cd /root/warehouse
docker pull registry.xzzandzyc.store:5000/project/warehouse-carbon:<tag>
docker compose up -d --force-recreate migrator app
docker compose ps
docker compose logs --tail=100 app migrator
```

### 数据覆盖发布

```bash
# 本地导出
pg_dump --format=custom --file /path/to/local.dump "<LOCAL_DATABASE_URL>"

# 上传
scp -i ~/.ssh/huawei.pem /path/to/local.dump root@116.63.218.160:/tmp/

# 线上备份
pg_dump --format=custom --file /tmp/warehouse-backup-$(date +%Y%m%d%H%M).dump "<ONLINE_DATABASE_URL>"

# 线上恢复
pg_restore --clean --if-exists -d warehouse /tmp/local.dump

# 重建应用
cd /root/warehouse
docker compose up -d --force-recreate migrator app
```

## 10. 建议的后续优化

- 增加一个专用脚本：`scripts/deploy_prod.sh`
  统一执行 `pull + digest check + force recreate + health check`
- 增加一个专用脚本：`scripts/restore_prod_db.sh`
  包装 `pg_restore` 的高风险参数，减少误操作
- 在 CI 中自动生成唯一 tag，避免长期复用 `58165a3` 这种不变 tag
- 为发布文档再补一份“演示环境发布清单”，把演示数据准备单独列出
