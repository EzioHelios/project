# 视觉作业识别接入

## 当前链路

推流和识别独立运行，共用视频源，不共用启停开关：

```text
只读 MP4 -> publisher 容器 (FFmpeg) -> MediaMTX
                                      |-- HLS -> 平台租户鉴权接口 -> 浏览器视频
                                      |-- RTSP -> 识别 Worker -> 观测记录 -> 作业草稿
```

推流容器只接受视频文件和 RTSP 发布地址，不持有平台账号、不连接业务数据库、不创建摄像头、设备或事件。MediaMTX 只负责媒体协议转换。识别 Worker 只读取摄像头配置、执行推理并上报观测，不管理推流进程。

- 大屏：`http://127.0.0.1:18101/bigscreen/vision`，顶部大屏序列新增“视觉作业”。
- 配置：设备与测点 > 视频监控 > 识别配置。继续使用原有摄像头台账，不另设摄像头主数据。
- 演示限定沃衡租户，不操作安方、祥泰现场数据。
- 复用 `warehouse-forklift` 的视频与 `best.pt` 权重；没有复制其演示统计、随机图表、独立账号或独立数据库。
- 大屏通过 HLS 连续播放原始视频，每两秒更新识别统计。检测框保留在观测证据图中，不叠加到独立的视频流。关闭识别、停止 Worker 均不影响视频播放。

## 启动

先启动本仓库前后端并完成迁移。当前本地前端固定 18101，后端 18100；识别工具经 18101 访问 API。

```sh
app database upgrade --no-prompt
```

### 1. 独立启动模拟摄像头

宿主机只需要 Docker，不需要安装 FFmpeg、Python 或登录平台即可推流。视频文件必须存在，Compose 不会创建空目录充当输入。

```sh
export VISION_VIDEO_FILE=/absolute/path/to/camera_b_smooth.mp4
docker compose -p warehouse-vision -f tools/vision/compose.yml up -d --build
docker compose -p warehouse-vision -f tools/vision/compose.yml ps
docker compose -p warehouse-vision -f tools/vision/compose.yml logs --tail 30 publisher rtsp
```

默认 RTSP 为 `rtsp://127.0.0.1:18115/woheng-forklift`，HLS 网关为 `http://127.0.0.1:18116`，都仅绑定本机。更换通道可设置 `VISION_PUBLISH_URL=rtsp://rtsp:8554/camera-2`，平台配置中的播放通道相应填写 `camera-2`。多个模拟摄像头可用多个同镜像 publisher 服务，分别挂载视频和发布到不同通道；无需复制平台业务代码。

本机 Docker 构建需要代理时，可通过标准 build 参数传入，不写入镜像或运行容器：

```sh
docker compose -p warehouse-vision -f tools/vision/compose.yml build \
  --build-arg http_proxy=http://host.docker.internal:10808 \
  --build-arg https_proxy=http://host.docker.internal:10808 publisher
docker compose -p warehouse-vision -f tools/vision/compose.yml up -d --no-build
```

停止推流使用 `docker compose -p warehouse-vision -f tools/vision/compose.yml stop publisher rtsp`。无需平台账号，亦不删除业务记录。演示结束通常只需关闭识别，可保留视频循环播放。

### 2. 配置平台播放与识别

后端设置 `VISION_HLS_ORIGIN` 为可信内部 MediaMTX HTTP 地址，修改后重启后端。本机 Docker 后端使用 `http://host.docker.internal:18116`；同一部署网络可使用服务名 `http://rtsp:8888`。不要把回环地址直接用于远端服务器，也不要向外开放无鉴权媒体端口。

视频监控台账的“识别配置”内维护“视频接入”：RTSP 地址供 Worker 使用，播放通道供平台 HLS 代理使用。两者指向同一摄像头，但播放不要求启用识别。浏览器所有播放列表、视频分片都经过平台登录和租户鉴权，不接收任意上游 URL，也不公开摄像头 RTSP 密码。

### 3. 独立容器运行识别 Worker

宿主机无需 Python、OpenCV 或模型运行环境。Worker 使用独立 CPU 镜像，不包含平台后端、视频文件或模型。摄像头、设备和物资仍在平台现有台账维护，不由容器启动过程写入。

```sh
export VISION_API_URL=http://host.docker.internal:18100
export VISION_TENANT=woheng-taizhou-production-base
export VISION_CAMERA_ID=1083
export VISION_MODEL_FILE=/absolute/path/to/best.pt
export VISION_USERNAME=admin@example.com
export VISION_PASSWORD_FILE=/absolute/private/directory/platform-password
docker compose -p warehouse-vision -f tools/vision/compose.worker.yml up -d --build
docker logs --tail 30 warehouse-vision-recognition-1
```

媒体和 Worker 使用同一 Compose 项目名，共享默认网络，但两份部署文件可独立运行。摄像头 RTSP 配置填写 `rtsp://rtsp:8554/woheng-forklift`，不是 `127.0.0.1`。远端真实摄像头填写 Worker 可达的内网地址。平台地址来自 `VISION_API_URL`，同网部署可改为后端服务名；不在代码中猜测或改写地址。

非敏感变量模板见 `worker.env.example`，可复制为被 Git 忽略的 `.env.worker.local` 并使用 `--env-file`。密码文件仅包含密码，放在权限 0700 的专用目录；文件需对容器用户可读，可设为 0444，目录权限负责限制其他宿主机用户访问。不要提交、打包或把密码文件放在共享目录中。Compose 以文件型 secret 只读挂载到 `/run/secrets/vision_password`，密码不放进镜像、命令参数或容器环境变量。这里使用文件型 secret，是因为当前 Compose 不支持向只读服务创建环境变量型 secret。

本地密码文件已置于 `.storage/vision/secrets/platform-password`，目录权限 0700，文件被 Git 和镜像构建上下文排除。重建时仍需保留该 secret 文件，普通 `docker restart` 不需要重新输入密码。

两份 Compose 文件同项目分别启动时，Compose 可能将另一份清单的容器提示为 orphan；不要使用 `--remove-orphans` 删除仍在运行的媒体服务。已有 `VISION_VIDEO_FILE` 配置时，可以合并清单执行 `docker compose -p warehouse-vision -f tools/vision/compose.yml -f tools/vision/compose.worker.yml up -d recognition`。

Worker 每三秒读取配置；关闭识别时待机，不运行推理；重新启用后自动打开 RTSP。容器以非 root 用户、只读根文件系统运行，模型只读挂载。`outbox` 命名卷保存已落盘的待传及拒收事件，容器重建后继续使用原事件键；临时缓存和健康心跳位于 tmpfs。进程退出由 `restart: unless-stopped` 恢复，健康检查表示配置轮询仍在推进，不等同于识别已启用。

```sh
# 仅停止识别，保留推流和视频播放。
docker stop --time 90 warehouse-vision-recognition-1
docker start warehouse-vision-recognition-1
```

不要使用 `down -v` 清理仍有待传事件的部署。优雅停止会结束当前片段并落盘；强制终止仅保证已提交 SQLite 的事件不丢失，尚在内存中的片段不是已落盘事件。平台关闭识别或修改配置后，旧事件进入拒收记录，不会强行重放到新任务。

多摄像头在部署清单中显式增加同镜像的 Worker 服务，为每个实例分别配置摄像头、租户和持久化卷；无需复制源代码。不要用 `--scale recognition=N` 复制同一摄像头的配置。一个摄像头只部署一个活动 Worker，本轮不建设动态调度。当前镜像仅验收 CPU 推理，不宣称已经完成 GPU 部署。

容器化前若已有宿主机 SQLite 队列，应先停止旧 Worker 并检查待传数量。有待传记录时将该租户和摄像头对应的 SQLite 文件复制到持久化卷，并赋予容器用户 10001 读写权限，再启用新 Worker；不要同时运行新旧实例。没有待传记录的旧文件可作为历史记录保留。本次本地旧队列待传为 0，3 条拒收记录仍保留在原文件中。

## 配置与操作

1. 登录并切换到沃衡泰州生产基地，打开视频监控台账。
2. 选择演示摄像头的“识别配置”，维护 RTSP、检测置信度、位移阈值、观察窗口、静止结束和丢失时长。
3. 选择当前租户的区域和设备。仅在摄像头监控范围确实限定一个设备时勾选单设备关联。
4. 填写物资任务编号，选择已有物资，名称与单位自动带出；维护批次、数量。重量可留空，本轮不提供重量分配法。
5. 保存配置后，Worker 结束旧会话并按新配置恢复识别；关闭识别时进入待机。旧记录保留原快照，不随新任务改写。关闭后或旧配置版本的迟到片段返回 409，保留在 Worker 的 `rejected_events` 中，不新增平台观测。重新启用无需重启视频或 Worker。
6. 返回“视觉作业”大屏，检查摄像头为“识别中”、画面持续更新、识别记录增长。
7. 查看片段画面，核对设备和物资任务，使用“归入作业”形成或补充草稿。在“经营活动台账 > 物资作业”检查有效时段后单独确认。重叠时段取并集，间隙不计作业时间。列表展示最近 24 小时中的最新 100 条；统计针对最近 24 小时全部观测记录。
8. 同一任务只生成一条正式作业；换任务时维护新的任务编号，不能把循环视频的每个重复片段都计作一批新物资。

## 业务边界

- 当前权重仅识别叉车。旋转吊、行吊、堆垛机需要相应模型和验证视频，不能用叉车模型宣称已支持。
- 视觉负责目标跟踪、移动片段、观测时间及证据画面；物资编码、批次、数量、重量来自明确配置的业务任务，不是视觉自动读取。
- 单目标、完整绑定且以静止结束的片段可归入作业草稿。多目标不自动绑定设备；出画、流中断、主动停止及配置切换的片段保留状态，不自动成为完整作业。
- 24 像素/1 秒是本视频的演示参数，不是行业标准或现场精度承诺。换摄像头、镜头角度或模型需重新验证阈值。
- 物资作业保存真实观测时长，数据质量标记为 `simulated`，表示演示视频来源。与现场实测数据区分。
- 摄像头配置、事件上报和观测归入沿用本平台管理员权限；作业维护与确认使用 `material_operations:write`，小时计算使用 `material_allocation:calculate`，PCF 引用使用 `product_footprint:write`。查看受账号和租户权限控制。凭据通过环境变量传入，401 时重新登录，不依赖过期 storageState。
- 当前仅落地识别接入及正式作业输入，不将这条链路等同于设备能耗计量、物资碳排分摊或产品碳足迹计算已全部验收。

## 一致性与存储

`VideoMonitor` 扩展识别配置、运行状态与最新画面；新增租户隔离的 `VisionObservation` 保存摄像头、会话、目标、时段、置信度、模型 hash、配置快照、证据与正式作业关联。

事件以 `(team_id, event_key)` 去重；相同键不同内容返回冲突。识别端 SQLite outbox 先持久化再投递，API 中断时保留待传事件。已接收事件的相同请求在关闭识别后仍返回原记录；尚未接收的旧配置事件进入拒收记录，不绑定到新任务。循环视频重新识别会产生新的观测，幂等键不等于视频内容去重；不希望重复识别时关闭识别开关，不应自动归入正式作业。

作业复用 `MaterialHandlingOperation`，来源为 `vision`，来源记录键为租户内唯一任务编号。归入使用事务锁，重复归入不新增记录；作业确认后拒绝追加片段。当前画面和证据接口校验租户；普通摄像头列表不返回识别凭据或图像二进制。

小时分配明确选择设备、来源、整小时期间、电力因子及适用依据，按小时平均强度估算，保留未归属电量。同一设备小时仅保留一组当前结果。PCF 页面“活动数据清单 > 引用物资作业”负责引用、同步和取消引用；计算不自动写入 PCF。引用结果仅为仓储阶段输入，不直接当作完整产品的单位碳足迹。

## 验证

```sh
uv run pytest src/py/tests/integration/material_allocation/test_vision*.py -n 0 -q --no-cov
uv run pytest tools/vision --confcutdir=tools/vision -n 0 -q --no-cov
```

页面归入一条真实观测后，可验证画面更新、作业关联、重复归入、租户隔离和登录态自动刷新：

```sh
docker exec warehouse-vision-recognition-1 python verify.py \
  --api http://host.docker.internal:18100 \
  --camera CAMERA_ID --observation OBSERVATION_ID \
  --output /var/lib/vision/verification.json
```

该工具会归入指定观测，需明确选择可归入的演示记录，不能用于只读检查。接口失败直接报错，不补造事件、替换接口响应或隐藏失败。

独立播放验收需先启动媒体容器和 Worker，再执行以下命令。它会启停所选演示摄像头的识别两次，确认新观测来自运行中的 Worker，并检查关闭期间观测数不变、真实视频分片继续变化、匿名及跨租户播放被拒绝。结束时保持识别关闭，视频继续播放，不自动确认作业。

```sh
docker exec warehouse-vision-recognition-1 python verify_playback.py \
  --api http://host.docker.internal:18100 \
  --tenant woheng-taizhou-production-base \
  --other-tenant woheng-huzhou-production-base \
  --camera CAMERA_ID --output /var/lib/vision/playback-verification.json
```

结果写入持久化卷，可用 `docker cp warehouse-vision-recognition-1:/var/lib/vision/playback-verification.json .storage/vision/container-playback-verification.json` 提取。浏览器实际解码和画面检查仍需在大屏完成，不以分片接口成功替代浏览器验收。

验收必须分别检查：关闭识别后视频时间继续前进且观测数量不变；重新启用后同一 Worker 恢复真实识别；停止 Worker 后视频仍可播放；其他租户及未登录请求无法读取分片；停止推流后页面显示中断而不是把静止图当直播。

协议参考：[MediaMTX 发布](https://mediamtx.org/docs/features/publish)、[读取](https://mediamtx.org/docs/features/read)、[HLS.js API](https://github.com/video-dev/hls.js/blob/master/docs/API.md)。

部署参考：[Docker Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/)、[PyTorch 安装](https://pytorch.org/get-started/locally/)。
