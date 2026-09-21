# 视频推流、播放与识别解耦验收

日期：2026-09-21。范围：本地 18101 前端、18100 后端，沃衡汽车泰州生产基地演示摄像头 1083。未操作安方、祥泰及线上环境。

## 实现边界

- `tools/vision/compose.yml` 运行独立 FFmpeg publisher 和 MediaMTX，视频只读挂载，publisher 不持有业务账号、不建数据、不运行模型。
- 删除混合启动器 `tools/vision/demo.py`，不保留兼容入口。操作步骤见 `tools/vision/README.md`。
- 摄像头现有配置增加 `playback_path`；平台全局配置 `VISION_HLS_ORIGIN` 指定可信内部媒体网关，不增加业务表或迁移。
- 视频经 `/api/vision/cameras/{id}/stream/{asset}` 播放，列表和分片均检查登录及当前租户。禁止路径穿越、外部播放列表引用和上游重定向。
- 大屏使用 HLS 视频，视频生命周期不依赖识别开关。原始视频无检测框，检测框在观测证据图中保留。
- Worker 关闭识别时待机，重新开启恢复推理。关闭后及旧版本的新增观测拒收，已接收观测可幂等查询，迟到片段保留于本地拒收队列。
- Worker 仍为独立 Python 进程，本轮只容器化推流，不引入模型调度平台。Worker 意外退出需由部署进程管理器重启。

## 自动化检查

| 项目 | 结果 |
| --- | --- |
| `pytest src/py/tests/integration/material_allocation --no-cov -q -n 0` | 29 passed |
| `pytest tools/vision/test_tracking.py --confcutdir=tools/vision -n 0 -q --no-cov` | 3 passed |
| `bunx tsc --noEmit` | 通过 |
| 视觉组件、接口类型、大屏路由 Biome | 通过 |
| 视觉后端、工具及相关测试 Ruff | 通过 |
| `git diff --check` | 通过 |

实际 API 验收使用 `tools/vision/verify_playback.py`，结果在 `.storage/vision/playback-verification.json`，不提交运行数据。

| 场景 | 实测结果 |
| --- | --- |
| 初始关闭识别，观察 10 秒 | 观测 1282 → 1282；视频分片 47 → 51，内容 hash 变化 |
| 启用识别 | 同一 Worker 推理 54 帧，观测 1282 → 1283 |
| 关闭识别，观察 10 秒 | 观测 1283 → 1283；视频分片 58 → 62 |
| 不重启 Worker 再次启用 | 新会话推理 100 帧，观测 1283 → 1284 |
| 再次关闭识别，观察 10 秒 | 观测 1284 → 1284；视频分片 70 → 74 |
| 匿名读取视频 | HTTP 401 |
| 湖州租户读取泰州摄像头视频 | HTTP 404 |

这些新增记录来自视频实时推理，不是接口造数；中断片段按原有质量规则保留，不自动确认为完整作业。

## 内置浏览器验证

1. 登录并切换沃衡泰州租户，选择“物资作业视频演示”。识别关闭时 `HTMLVideoElement.currentTime` 从 19.02 秒推进到 100.50 秒，`paused=false`、`readyState=4`，解码尺寸 1280×1280。
2. 在视频监控台账打开配置，确认“视频接入”与“视频识别”分区；启用开关、保存、重新打开核对，关闭开关并再次保存。两次均返回“识别配置已保存”。
3. 界面操作期间主视频继续播放，时间推进至 204.01 秒。此轮 UI 验证另产生 5 条真实观测，最终总数 1289，没有自动归入作业。
4. 结束 Worker 进程后视频保持运行。随后停止 publisher，页面明确显示“视频连接中断”和重新连接按钮。
5. 重启 publisher，点击重新连接，恢复真实视频；验收时 `currentTime=37.16`、`readyState=4`、`paused=false`，画面可见叉车运动。页面同时显示“视频播放中”及“事件识别：已停用”。

## 留存状态

- 两个媒体容器保持运行，监听本机 18115/18116；前端仍为 18101。
- 识别关闭，验证用 Worker 已退出，不会继续增加演示事件。
- 如需继续识别，按 README 启动独立 Worker，再从摄像头配置启用识别。
- 构建遇到本机 Docker Hub 镜像代理故障，使用已缓存且固定 digest 的官方 Alpine 基础镜像及标准小写 HTTP 代理 build 参数完成。未关闭 TLS 校验、未更改全局 Docker 配置。
- 未提交代码；工作区仍含此前物资作业与视觉接入的未提交改动，本记录不代表整个工作区已完成提交审查。
