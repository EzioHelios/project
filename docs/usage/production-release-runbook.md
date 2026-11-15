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
- 仓储系统的 React 前端随应用镜像发布。`tools/deploy/docker/Dockerfile` 在构建阶段生成接口类型、执行前端构建并将静态资源打包到运行镜像，更新 `app` 即更新对应前端；仓储业务页面不使用独立的 `fe-release` 渠道。
- `docs` 文档站独立发布，应在系统与演示数据就绪后切换匹配版本；文档站发布不能替代仓储应用镜像更新。
- 尽量使用新 tag 发布。
- 如果因为历史原因复用了同一个 tag，线上必须显式 `docker pull`，不能只 `docker compose up -d`。

### 1.2 数据发布原则

- 先备份线上数据库，再做恢复或导入。
- 普通代码发布不执行整库恢复，也不重置既有账号或客户业务数据。演示数据更新应限定租户并保留前后对比证据。
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

发布前核对实际服务清单，包括：

- `app`
- `migrator`
- `worker`、`mqtt-ingest-worker`、`metering-projection-worker`
- `emqx`（broker）、`cache`

以线上实际Compose配置为准。

### 3.3 先独立完成迁移，再更新应用和各 worker

仓储部署的五个应用镜像服务为 `migrator`、`app`、`worker`、`mqtt-ingest-worker`、`metering-projection-worker`。发布前确认这五项均引用 `${APP_IMAGE}`，且 `.env` 指向本次发布镜像；`migrator` 是一次性迁移服务，不要求持续运行。保留原配置及镜像信息，避免只更新 app 后后台进程仍运行旧代码。

以下命令仅用于已完成备份、确认迁移兼容性的发布窗口。使用 `--no-deps` 将更新限制在指定服务，不重建 `emqx`、`cache` 或数据库。不要将 migrator 与 app/worker 放在同一条 `up` 命令中。

```bash
cd /root/warehouse
set -e
docker compose config --quiet
docker compose pull migrator app worker mqtt-ingest-worker metering-projection-worker

# 必须等待独立迁移成功退出；失败即停止后续发布。
docker compose up --no-deps --force-recreate --exit-code-from migrator migrator
```

确认退出码为 0、迁移日志无错误且数据库 head 与目标代码 head 一致后，再更新应用：

```bash
docker compose up -d --no-deps --force-recreate app
curl -fsS --max-time 10 http://127.0.0.1:18100/health
```

健康检查通过后，按以下顺序逐个更新 worker。每次更新前重新只读检查对应队列，确认没有活跃任务；每次更新后核对镜像、worker 心跳和任务状态，再继续下一项。

| 顺序 | 服务 | SAQ队列 |
| --- | --- | --- |
| 1 | `worker` | `background-tasks` |
| 2 | `mqtt-ingest-worker` | `mqtt-ingest` |
| 3 | `metering-projection-worker` | `metering-projection` |

逐项执行的命令分别为：

```bash
docker compose up -d --no-deps --force-recreate worker
```

```bash
docker compose up -d --no-deps --force-recreate mqtt-ingest-worker
```

```bash
docker compose up -d --no-deps --force-recreate metering-projection-worker
```

更新worker前，应在现有应用容器内使用 `get_settings().saq.REDIS_URL` 创建对应队列客户端，通过 `Queue.info()` 检查活跃数、立即待执行数和worker心跳，必要时用 `Queue.jobs()` 只读核对任务状态。发现活跃任务应等待并复查，各worker分别确认无活跃任务后再更新。

只输出状态、数量及必要任务元信息，不输出连接地址、payload、结果或异常详情；检查后关闭客户端，不启动消费或执行取消、重试、排空。SAQ当前Redis实现的 `info["scheduled"]` 是未完成任务集合数量，应结合计划时间区分未来定时任务与立即待执行任务。

停止期限须同时核对已安装SAQ和容器配置。2026-11-15生产SAQ为 `0.26.1`，应用未映射 `shutdown_grace_period_s` 环境变量；单独增加env或延长Docker停止期限不能保证在途任务完成后退出。一次活跃数为0的快照也不是持续排空保证。

本次 `.storage/release-20261115/queue-check.py` 仅为发布取证脚本，位于Git忽略目录，不随代码或镜像分发。后续发布按上述接口方法检查，不依赖该文件存在。

### 3.4 镜像 digest 与发布结果核对

拉取前保留旧镜像及 digest；拉取后用以下只读命令记录目标镜像 digest，并与构建推送日志核对：

```bash
docker image inspect --format '{{json .RepoDigests}}' registry.xzzandzyc.store:5000/project/warehouse-carbon:<tag>
docker compose ps -a
```

随后按 3.3 的顺序执行发布。发布后核对五个服务使用的镜像引用与镜像 ID，其中 migrator 应成功退出，app 和三个 worker 应正常运行。复用 tag 时也必须先 pull，再逐项重建；不能根据 `.env` 的 tag 未变判断容器已更新。

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

恢复完成后，按 3.3 节独立运行目标版本 migrator，确认成功退出并核对数据库 head，再更新 app、检查健康状态，最后逐个检查队列并更新三个 worker。恢复前停止的写入服务应在数据库验证通过后恢复；不要在迁移尚未结束时启动业务服务。

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

至少人工检查：

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

仅代码存在问题时，先确认当前数据库 schema 与旧镜像兼容，再恢复备份中的 `APP_IMAGE` 及各服务镜像配置。拉取记录的旧镜像，按 3.3 节的应用健康检查和队列检查顺序，分别恢复 app 和三个 worker。

镜像回滚不会自动撤销数据库迁移。不要直接运行旧 migrator 代替迁移回退；只有明确需要且已验证的迁移方案才单独执行。若发布前 app 与 worker 版本不同，应使用备份记录逐项决定回退版本，不能猜测所有服务原先使用相同镜像。

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

恢复后先核对备份 schema 与目标镜像的兼容性；需要迁移时按 3.3 节独立完成迁移，再恢复 app 和三个 worker。

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
# 按 3.3 节独立完成 migrator，核对 head 后更新 app。
# app 健康后逐项检查队列，再更新三个 worker；不得跳过中间检查。
docker compose ps -a
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

# 按 5.5 和 3.3 节核对 schema，独立迁移成功后再逐项恢复应用与 worker。
```

## 10. 建议的后续优化

- 增加一个专用脚本：`scripts/deploy_prod.sh`
  统一执行 `pull + digest check + force recreate + health check`
- 增加一个专用脚本：`scripts/restore_prod_db.sh`
  包装 `pg_restore` 的高风险参数，减少误操作
- 在 CI 中自动生成唯一 tag，避免长期复用 `58165a3` 这种不变 tag
- 为发布文档再补一份“演示环境发布清单”，把演示数据准备单独列出
