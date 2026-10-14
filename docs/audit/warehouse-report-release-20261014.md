# 组织碳报告与演示隔离发布记录

## 提交和范围

本轮在现有 `project` 分支直接提交，未创建工作树，未推送 Git 远端：

- `dffe761b`：演示写入限于两个沃衡租户，删除旧客户演示安装入口。
- `c55f5f05`：安方正式因子、祥泰真实逐表活动与核算的受控维护工具、测试和依据记录。
- `307e5bd9`：企业资料和报告正文填写入口、组织关联校验、正文快照、完整报告模板和设备月份附表。

无关的20260928数据集研究、`tools/datasets/`、`output/`报告产物保留在本地，未提交或进入镜像。本次不执行演示安装、维护数据脚本、重算、客户权限修改或本地数据库覆盖。

## 发布

- 服务器：华为，`/root/warehouse`；站点：`https://warehouse.nexlca.com`。
- 从 `git archive 307e5bd9` 的干净源码归档，执行 `scripts/build_push_multiarch.sh`，指定生产沿用的 `tools/deploy/docker/Dockerfile`，`PUSH_LATEST=false`。
- 镜像：`registry.xzzandzyc.store:5000/project/warehouse-carbon:307e5bd-20261014-report`。
- Registry digest：`sha256:ac6bec29645934ef10876230019403781e5e4d48a499bbf19e1a18cfa7960df9`。
- 线上运行镜像ID：`sha256:71770d165893d5f7f55faaa547ad4c5b532c6e34d86df2df20e7f2ded05394b2`。
- 执行 Compose pull、独立迁移容器 `litestar database upgrade --no-prompt`，仅重建 app、worker、mqtt-ingest-worker；三个容器正常运行，验收时重启次数0。
- 数据库版本仍为 `f9a0b1c2d3e4`，本轮无新增迁移。CLI需显式 `PYTHONPATH=/workspace/app`。首次通过SSH标准输入运行的迁移容器消费了后续脚本输入，因此尚未切换应用；加入标准输入隔离后重跑完成，迁移仍无变更。
- 前端随镜像发布，此站点不使用独立 fe-release。新版入口脚本 `/static/web/assets/main-HBcn1J7B.js` 返回200，SHA256 `0d10abd9e625b991ce01f56ef482a7a3bb536500a04343210b279efe9af72faf`。
- 原仓库图片只读挂载 `/root/warehouse/assets/sector-photos` 保留；未重建EMQX、缓存、其他项目服务或启动视觉识别服务。

## 备份与回滚

- 目录：`/root/warehouse/backups/report-release-20261014-307e5bd`，0700；配置及数据库备份0600。
- `before.dump`：230220638字节，SHA256 `e43dbeb8f818294db7423af1e0ec0b8e2f0e2bb1572d995a63f1c1debcff12d4`，通过完整 `pg_restore -f /dev/null` 解码校验。
- 原镜像：`registry.xzzandzyc.store:5000/project/warehouse-carbon:2e990cdd-20261013-report-fix2`，服务器保留别名 `warehouse-carbon:rollback-20261014`。
- 回滚只需恢复原 APP_IMAGE，并重建上述三个应用服务。本轮不需要数据库回退；不要整库恢复覆盖持续采集的数据。

## 验证

- 98项集中单元/集成测试通过；初次1项因宿主SOCKS代理缺少socksio在测试启动前失败，清除该次测试进程代理变量后98项全部通过。仍有1条Pyomo输出捕获线程清理warning，未宣称全仓测试通过。
- TypeScript、三个前端文件Biome、相关Python Ruff和diff检查通过。测试自动生成的本地端口配置已恢复18101。
- `/health`为200、数据库online；客户重新登录成功，仍只拥有安方、祥泰两租户。
- 两租户总览、电量、碳排大屏API、企业资料、报告台账及详情均200；三维模型GLB按源码哈希校验。内置浏览器实际检查两租户报告台账、祥泰新正文栏目及两个大屏模型/祥泰实景。
- 上线前后两租户活动记录、核算结果、报告的逐行聚合指纹完全一致：祥泰156条活动/156条结果/2份草稿；安方8条活动/16条含历史的结果/2份报告（1草稿、1归档）。
- 从线上真实租户会话调用原生报告导出用例：祥泰 `RPT-7-11`、`RPT-7-12`，安方 `RPT-6-10` 均成功生成Word。验证草稿、期间、无内部编码/参数对应表、设备月份汇总。祥泰2025为10设备、60条活动、31380.66 kWh、18.2855 tCO2e。
- 三份Word用本机原生soffice渲染为9、10、10页A4 PDF，无空文本页，检查分页概览、结果及汇总表。此处为发布冒烟验证，不替代前一轮本地样本逐格/逐页验收。
- 验证产物位于gitignored `.storage/release-report-20261014/`，不提交线上数据文件或凭据。

## 保留事项

1. 客户 `taizhou` 没有 `carbon.inventory.export`，报告导出API仍403；本轮没有扩大权限。服务端导出成功不能表述为客户浏览器下载成功。
2. 线上报告正文11项尚未填写，本地样本填写内容未自动覆盖线上；导出对应资料仍以【待补充】呈现。编制责任、组织概况、监测和质量管理资料需经确认后在新入口维护。
3. 沃衡6份已发布、2份已提交旧演示报告，以及安方1份已归档旧报告，缺少完整正文快照。新版拒绝以当前资料伪造历史正文；原记录保留，需从原运行建立新版本。发布前已提示此行为变化。
4. 2026-10-14 11:00左右的云集数据拉取收到外部HTTP429，按既有逻辑停止该轮剩余电表拉取；安方MQTT在11:02仍入库成功。未将限流当作发布已修复事项，也未增加重试压力。
5. 华为系统盘约93%已用、剩余7.4GiB；本次未清理镜像、卷或备份，后续应按保留策略整理。
