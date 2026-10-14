# 大屏性能修复与线上验收

日期：2026-10-14。环境：Huawei `/root/warehouse`，`https://warehouse.nexlca.com`。
前置诊断：[大屏接口性能诊断](bigscreen-performance-diagnosis-20261014.md)。

## 修复范围

- 开发提交：`50afd474`，当前 `project` 分支。通过已有 `scripts/build_push_multiarch.sh` 构建推送，显式使用与线上一致的 `tools/deploy/docker/Dockerfile`。
- 最新读数改为按启用设备执行 LATERAL 索引查询；保留租户、质量、测点、读数类型、演示来源排除、时间和ID排序条件，无读数设备仍保留原展示。
- 碳大屏主体仅等待碳接口；依赖运营数据的两个组件独立显示加载、失败和重试状态。截图就绪标记仍需所有请求完成，避免把部分加载截图当作完整页面。
- 没有新增台账、缓存旁路、数据库迁移或演示数据；没有更改能源聚合与碳核算算法。

## 数据等价验证

发布前在生产容器独立诊断进程中加载候选服务，原有服务不替换。在同一个 PostgreSQL REPEATABLE READ 只读事务中分别执行旧、新服务，完整返回对象逐字段断言相等。

| 租户 | 默认期间 | 最后一天按小时 | 按月 | 已配置区域 |
| --- | --- | --- | --- | --- |
| 安方中心库 | 完全相同 | 完全相同 | 完全相同 | 完全相同（HMAZ） |
| 祥泰仓库 | 完全相同 | 完全相同 | 完全相同 | 完全相同（P9） |

8/8组通过，设备分别16台、19台，包含有读数与无读数设备。详见 `equivalence.log`。

发布前后额外用 taizhou 重新登录，取得两个租户完整碳接口JSON并断言相等：

| 租户 | 核算期间 | 活动记录 | 页面排放量 | 前后相同的JSON SHA-256 |
| --- | --- | --- | --- | --- |
| 安方 | 2026-07-10 至 2026-08-10 | 8条 | 47.33 kgCO2e | `63fde51f3940d2d30036d95d5174e753a5a0e6dc4016d993c23a6f7ac58cf59c` |
| 祥泰 | 2026-01-01 至 2026-09-30 | 96条 | 33,880.65 kgCO2e | `cc018759c4bd5d96f4c05cc9982e1d425b1bb320f1fa1919fa4d33977c16d93c` |

两个租户页面均展示原有正式因子 0.5827 kgCO2/kWh。持续采集使不同时间点的最新读数、当日电量自然变化，因此能源等价验收采用同一数据库快照，不用跨时间响应字节数是否相同判断。

## 公网耗时对比

同一客户端、账号、租户、路径和请求顺序，HTTPS请求各3次，以下为中位数。不是容量压测、冷缓存对照实验或浏览器整屏渲染计时；没有人为清缓存。原诊断部分采样与后端剖析重叠，详见前置记录。

| 租户 | 接口 | 优化前 | 上线后 | 耗时下降 |
| --- | --- | --- | --- | --- |
| 安方 | overview | 2.445秒 | 0.179秒 | 92.7% |
| 祥泰 | overview | 23.369秒 | 0.314秒 | 98.7% |
| 安方 | power，紧随overview | 0.512秒 | 0.181秒 | 64.6% |
| 祥泰 | power，紧随overview | 1.829秒 | 0.286秒 | 84.4% |

上线后overview样本：安方0.280/0.178/0.179秒；祥泰0.737/0.271/0.314秒。交换顺序、先查power时，安方0.192秒、祥泰0.286秒；旧版对应3.511秒、21.743秒。旧版两个接口共享查询且受缓存影响明显，不能只用紧接overview后的power作为旧版一般表现。

carbon没有修改查询：顺序样本安方0.180/0.136/0.127秒，祥泰0.153/0.147/0.148秒。改善的是它不再等待overview才展示主体，不能把carbon自身采样波动归功于本次SQL修改。

两请求并发样本仍完整保留：安方overview 0.178秒、carbon 1.582秒；祥泰overview 0.360秒、carbon 0.228秒。安方有一次carbon延迟波动，不能宣称所有请求均稳定低于1秒。本轮30次主测试GET和8次换序GET全部200，没有401/403/5xx。

线上独立只读SQL剖析，新版最新读数SQL：祥泰2.2/1.1毫秒，安方1.2/1.1毫秒；旧版首次剖析分别17.6619秒、4.7446秒。总SQL条数仍为36/35，没有增加逐设备多次数据库往返。

## 浏览器验收

内置浏览器重新登录 taizhou，切换安方、祥泰，实际访问4种大屏，共8个租户页面。保存1280×720完整视口截图，检查 `data-screen-ready=true`、所有ECharts `data-chart-ready=true`、无业务加载错误、无损坏图片。模型和卫星底图在最终截图正常显示。

| 租户 | 页面 | 完成图表数 | 截图文件 |
| --- | --- | --- | --- |
| 安方 | 总览 | 2 | `anfang-overview-after.png` |
| 安方 | 运行监测 | 4 | `anfang-monitor-after.png` |
| 安方 | 电量监控 | 4 | `anfang-power-after.png` |
| 安方 | 碳排管理 | 5 | `anfang-carbon-after.png` |
| 祥泰 | 总览 | 3 | `xiangtai-overview-after.png` |
| 祥泰 | 运行监测 | 4 | `xiangtai-monitor-after.png` |
| 祥泰 | 电量监控 | 4 | `xiangtai-power-after.png` |
| 祥泰 | 碳排管理 | 5 | `xiangtai-carbon-after.png` |

同时验证主动刷新和租户反复切换。一次切租户期间浏览器工具3秒等待超时，随后检查和截图全部就绪；此工具超时不等同于API超时，也不据此宣称整屏始终在3秒内完成。发布前浏览器曾出现卫星底图加载失败，最终刷新恢复；外部地图资源耗时不属于本轮接口优化结果。

## 自动化检查

- 后端：`test_bigscreen_operations.py`和`test_bigscreen_data.py`，18项通过；包括最新值筛选、同时间ID决胜、空读数、停用设备、非电表设备与跨租户隔离。
- 前端：`bun run test tests/bigscreen`，11个文件40项通过；新增4项碳页面独立加载/失败/重试/原组件保持测试。
- `bunx tsc --noEmit`通过；本轮Python Ruff检查和格式检查通过；两个生产前端文件Biome通过；`git diff --check`通过。
- 第一次定向pytest使用默认全局覆盖率阈值，18项功能测试通过但因仅运行子集、总体覆盖率14.55%未达65%而退出1；随后使用`--no-cov`明确运行同一子集，18项通过。本轮不声称已通过全库覆盖率门槛。

## 发布与回滚

- 镜像：`registry.xzzandzyc.store:5000/project/warehouse-carbon:50afd47-20261014-bigscreen`。
- registry digest：`sha256:69c59c35a27601cbd6de2146be97938a78909289782516b0f94901bfef1a2009`。
- app、worker、mqtt-ingest-worker实际image ID均为 `sha256:a0692a68a1c0b9448086369924b77b8c377cdaa42158965c128794339836f4cd`；运行正常，重启计数0。
- 配置备份：`/root/warehouse/backups/bigscreen-release-20261014-50afd47/`；回滚镜像别名 `warehouse-carbon:rollback-20261014-bigscreen`，原版本 `307e5bd-20261014-report`。
- Compose pull后仅重建app、worker、mqtt-ingest-worker；未更动数据库、Redis、EMQX、图片挂载和账号权限。无迁移，无数据回滚需要。
- 公网`/health`数据库online；应用和两个worker日志未发现新增ERROR/Traceback，MQTT重试定时任务正常完成。
- 发布后根分区剩余约6.8GB（使用率93%），没有擅自删除旧镜像、数据或日志。后续发布需关注容量。
- Git提交在当前`project`分支，未额外推送Git远端；镜像已推送并部署。

## 证据位置

仓库本地 `.storage/bigscreen-release-20261014/`：

- `equivalence.log`：8组同快照新旧完整响应比对。
- `carbon-payloads-before.json`、`carbon-payloads-after.json`：线上碳接口完整响应。
- `after/public-http.json`、`after/order-confirmation.json`：38次公网GET计时。
- `backend-after.log`：新版本逐SQL剖析。
- `browser-checks.json`和上述8张`*-after.png`：浏览器验收。
- `build.log`、`deploy.log`及应用/worker日志：构建、发布、运行检查。

发布前原始计时仍保留于 `.storage/bigscreen-performance-20261014/`，没有覆盖。
