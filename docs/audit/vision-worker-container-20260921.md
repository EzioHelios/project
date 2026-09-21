# 视觉识别 Worker 容器化验收

日期：2026-09-21。范围仅为本地沃衡泰州演示租户、摄像头 1083；未更新线上、未修改安方或祥泰数据。

## 实现

- `tools/vision/worker.Dockerfile`：独立 Python 3.13 CPU 推理镜像，固定官方基础镜像 digest、PyTorch 2.11.0、torchvision 0.26.0、YOLO 和 OpenCV 版本。无宿主机 Python 或 FFmpeg 运行依赖。
- `tools/vision/compose.worker.yml`：非 root 用户 10001、只读根文件系统、只读模型、文件型 secret、临时缓存 tmpfs、事件持久化卷、自动重启和进程健康检查。
- `.dockerignore`：只允许运行代码和依赖清单进入构建上下文，不打包模型、视频、密码、SQLite 和本地运行产物。
- `outbox.py`：从推理循环中抽出已有 SQLite 事件投递职责。HTTP/网络失败保留待传事件，409 原子转入拒收表，成功后删除待传记录，沿用稳定事件键。
- `client.py`：统一读取 `VISION_PASSWORD_FILE`；401 后重新读取 secret 并登录，不保留明文密码环境变量旁路。
- Worker 启动时准备明确配置的临时缓存目录，启用识别时才加载 YOLO。关闭识别后继续轮询配置，不需要重启容器。
- 摄像头 RTSP 通过配置页改为 `rtsp://rtsp:8554/woheng-forklift`，平台地址配置为 `http://host.docker.internal:18100`；不在代码中猜测、改写回环地址。

本轮未新增业务实体、后端接口、消息队列或模型调度平台。每个摄像头使用一个明确配置的 Worker 实例，不采用同一配置横向扩容。

## 验证结果

| 检查 | 结果 |
| --- | --- |
| `pytest tools/vision --confcutdir=tools/vision -n 0 -q --no-cov` | 12 passed |
| `pytest src/py/tests/integration/material_allocation --no-cov -q -n 0` | 29 passed |
| Ruff / Compose 配置校验 / `git diff --check` | 通过 |
| 容器运行身份 | UID 10001，rootfs 只读 |
| 模型与密码挂载 | 均只读；容器环境无 `VISION_PASSWORD` |
| 实际依赖 | torch 2.11.0+cpu、CUDA None、OpenCV 4.11.0 |
| 首次启用识别 | 真实视频推理生成记录 1290 |
| 关闭后再启用同一 Worker | 生成记录 1291，无需重启推流或 Worker |
| 关闭识别期间 | 事件数量不变，HLS 分片继续变化 |
| 匿名 / 跨租户读取视频 | 401 / 404 |

### 断网、重建与补传

1. 真实目标移动时，仅断开 `warehouse-vision-recognition-1` 的 Compose 网络，不改媒体容器及后端。
2. 断网时已持久化待传事件 `d5fa50a9284e4931ad001034c6fedb49:1:3`，时长 5.711343 秒，结束原因 idle，配置版本 21。
3. 网络故障使进程退出，容器按策略重启；离线期间待传文件保留。
4. 使用 Compose 强制重建 Worker，挂载原 `warehouse-vision_outbox` 卷并恢复网络。旧容器 ID 前缀 `51a546c8526e`，新容器 ID 前缀 `76e47a124d62`。
5. 新容器补传原事件，服务端返回观测记录 **1294**，待传队列归零；原 2 条拒收记录和验收报告也保留。
6. 关闭识别后，用原事件再次请求两次，都返回 **1294**；观测总数 **1304 → 1304**，没有重复造数。

持久化保证针对已提交 SQLite 的事件。强制终止尚未结束、未落盘的内存片段不属于已提交事件；没有宣称任意断电都能保存正在进行的整段动作。

### 内置浏览器

- 在视频监控台账修改并保存容器 RTSP 地址，界面返回“识别配置已保存”。
- Worker 重建后，大屏显示“事件识别：识别中”，目标与移动计数为 1；补传的 5.7 秒片段可见且为待确认状态。
- 同时视频 `currentTime=605.39`、`paused=false`、`readyState=4`，播放未因识别容器重建而中断。
- 通过配置页关闭识别，最终保持媒体播放、Worker 健康待机，不自动确认作业。

## 产物与留存状态

- 启动、停止、配置、验证步骤：`tools/vision/README.md`。
- 容器启停播放验证：`.storage/vision/container-playback-verification.json`。
- 容器重建、补传与幂等验证：`.storage/vision/container-restart-verification.json`。
- 故障期间队列快照：`.storage/vision/restart-pending.sqlite`，仅作为本地验证产物，不提交。
- 原宿主机队列待传为 0，历史 3 条拒收仍保留原 SQLite 文件，没有删改。
- 最终平台观测数 1304，识别关闭，配置版本 22；新容器队列待传 0、拒收 3。
- publisher、MediaMTX、recognition 三个容器保持运行。publisher 容器 ID 和启动时间在故障测试前后不变。
- 仅验收 Linux arm64 CPU；未执行 amd64/GPU 环境验收、镜像推送或线上部署。

## 实测中处理的问题

当前 Docker Compose 不支持向只读服务创建环境变量型 secret，已改用权限受限目录内的文件型 secret，保留只读根文件系统和非 root 身份。密码未进入代码或构建上下文。

第三方模型库最初因缓存目录不存在而退回其他目录，已在加载库之前创建配置指定的 tmpfs 目录；后续启动不再依赖该回退行为。
