# 第一阶段 A：区域与设备维护专项验证

## 审查边界

本次只检查区域、设备、测点和接入配置之间的维护关系，不检查告警处理、工单、能耗分析和组织碳核算。

主线按以下对象判断：

`区域树 -> 设备台账 -> 设备测点 -> 采集配置 -> 点位监测`

## 页面和接口

| 对象 | 主页面/接口 | 当前判断 |
| --- | --- | --- |
| 区域 | `/data/monitor-area`, `/api/master-data/areas*` | 已闭环 |
| 设备 | `/data/terminals`, `/api/master-data/devices*` | 已闭环 |
| 测点 | `/data/terminals` 测点页签, `/api/master-data/device-points*` | 已闭环 |
| MQTT 表计绑定与点位映射 | `/data/terminals` 接入页签, `/api/iot-ingestion/mqtt-*` | 已闭环 |

## 实测结果

验证环境：本地 `18101` 前端，沃衡汽车泰州生产基地租户，验证脚本运行前重新登录。

验证脚本：

`bun run docs:manual:verify:area-device`

输出文件：

`outputs/woheng-showcase-woheng-full-evidence/manual-verification/area-device-maintenance.json`

最近一次验证结果：`passed`，49 项检查通过，24 张操作截图产出，`apiFailures`、`consoleErrors`、`notFoundResponses` 均为空。

| 验证项 | 结果 | 结论 |
| --- | --- | --- |
| 登录态和租户 | 登录成功，租户头注入成功 | 有效 |
| 区域新增 | 页面创建临时区域 `MANUAL-AREA-20260901`，接口可回读 | 有效 |
| 区域编辑 | 页面编辑区域名称、负责人、部门、位置、备注，详情可回显 | 有效 |
| 区域停用 | 页面可停用区域，接口回读为停用状态 | 有效 |
| 区域删除 | 清空设备后页面删除临时区域，接口回读为空 | 有效 |
| 设备新增 | 页面创建临时设备 `MANUAL-DEVICE-20260901`，挂载到临时区域 | 有效 |
| 设备编辑 | 页面编辑设备名称、负责人、备注，详情可回显 | 有效 |
| 设备详情 | 基础信息、区域、设备类型、投运状态、采集配置可展示 | 有效 |
| 设备停用/恢复 | 页面停用和恢复临时设备，接口状态可回读 | 有效 |
| 设备删除 | 删除测点和 MQTT 绑定后页面删除临时设备，接口回读为空 | 有效 |
| 测点新增 | 页面创建标准电表测点 `forward_active_total`，自动挂到当前设备 | 有效 |
| 测点编辑 | 页面编辑测点名称、来源字段、备注，测点列表可回显 | 有效 |
| 测点删除 | 页面删除临时测点，接口回读为空 | 有效 |
| MQTT 表计绑定 | 页面将 `WH-GW-01 / m901` 绑定到临时设备，接口可回读 | 有效 |
| MQTT 点位映射 | 页面将 `EPI_TOTAL` 映射到 `forward_active_total`，接口可回读 | 有效 |
| MQTT 测试报文 | 页面发送测试报文，生成平台电表读数 | 有效 |
| MQTT 绑定和映射删除 | 页面删除点位映射和表计绑定，接口回读为空 | 有效 |
| 临时数据清理 | 临时测点、设备、区域按编码清理 | 有效 |

## 证据截图

| 证据 ID | 内容 | 路径 |
| --- | --- | --- |
| EV-WH-066 | 区域新增表单 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-066-区域新增表单.png` |
| EV-WH-067 | 区域详情与层级回显 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-067-区域详情与层级回显.png` |
| EV-WH-068 | 设备新增表单与区域挂载 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-068-设备新增表单与区域挂载.png` |
| EV-WH-069 | 设备详情与采集配置 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-069-设备详情与采集配置.png` |
| EV-WH-070 | 测点新增表单 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-070-测点新增表单.png` |
| EV-WH-071 | 测点编辑后回显 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-071-测点编辑后回显.png` |
| EV-WH-072 | MQTT 表计绑定表单 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-072-MQTT表计绑定表单.png` |
| EV-WH-073 | MQTT 点位映射表单 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-073-MQTT点位映射表单.png` |
| EV-WH-074 | MQTT 接入测试结果 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-074-MQTT接入测试结果.png` |
| EV-WH-075 | 区域编辑表单 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-075-区域编辑表单.png` |
| EV-WH-076 | 区域停用状态 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-076-区域停用状态.png` |
| EV-WH-077 | 区域删除后结果 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-077-区域删除后结果.png` |
| EV-WH-078 | 设备编辑表单 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-078-设备编辑表单.png` |
| EV-WH-079 | 设备停用状态 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-079-设备停用状态.png` |
| EV-WH-080 | 设备恢复状态 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-080-设备恢复状态.png` |
| EV-WH-081 | 设备删除后结果 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-081-设备删除后结果.png` |
| EV-WH-082 | 测点编辑表单 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-082-测点编辑表单.png` |
| EV-WH-083 | 测点删除后结果 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-083-测点删除后结果.png` |
| EV-WH-084 | MQTT 表计绑定保存后回显 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-084-MQTT表计绑定保存后回显.png` |
| EV-WH-085 | MQTT 表计绑定编辑表单 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-085-MQTT表计绑定编辑表单.png` |
| EV-WH-086 | MQTT 点位映射保存后回显 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-086-MQTT点位映射保存后回显.png` |
| EV-WH-087 | MQTT 点位映射编辑表单 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-087-MQTT点位映射编辑表单.png` |
| EV-WH-088 | MQTT 点位映射删除后结果 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-088-MQTT点位映射删除后结果.png` |
| EV-WH-089 | MQTT 表计绑定删除后结果 | `outputs/woheng-showcase-woheng-full-evidence/screenshots/EV-WH-089-MQTT表计绑定删除后结果.png` |

## 已修复问题

| 问题 | 修复方式 | 状态 |
| --- | --- | --- |
| 区域树和区域详情显示 `zone` 等后端枚举 | 复用区域类型选项，显示“仓库”“区域/库区”等中文标签 | 已完成 |
| 设备详情显示 `active` 等投运状态编码 | 复用投运状态选项，显示“投运”“调试中”“停用” | 已完成 |
| 测点列表显示 `float` 等数值类型编码 | 复用测点类型选项，显示“浮点数”等中文标签 | 已完成 |
| 区域页面没有硬删除入口 | 区域详情补删除动作；无子区域、无设备时可删除 | 已完成 |
| 设备页面没有删除/停用入口 | 设备详情补停用、恢复、删除动作；有子设备、测点或 MQTT 绑定时阻断删除 | 已完成 |
| 新建设备不能在页面内创建 MQTT 绑定和点位映射 | 设备详情接入页签补表计绑定、映射新增/编辑/删除和测试报文动作 | 已完成 |
| MQTT 投影配置错误返回 500 | 投影异常标记为报文拒收和配置错误，页面显示“测试未通过”而不是服务端错误 | 已完成 |
| 删除设备后仍请求已删除设备详情，产生 404 控制台噪音 | 设备详情查询接入 abort signal；删除前取消并移除详情查询，删除失败时恢复选中设备 | 已完成 |

## 手册入册情况

操作手册页面：

`docs/manual/woheng-showcase/pages/03-data-maintenance-mqtt.md`

生成页面：

`src/js/web/public/help/woheng-showcase/pages/data-maintenance-mqtt.html`

本章已经按对象边界重排为区域、设备、设备测点、MQTT 表计绑定、MQTT 点位映射、接入测试与采集结果。手册正文补入 24 张操作截图，覆盖新增、编辑、保存后回显、状态流转和删除后结果。手册站点生成审计显示 88 项证据截图全部可用，无缺图。

## 缺口

| 缺口 | 当前影响 | 建议处理 |
| --- | --- | --- |
| MQTT 接入通道源和订阅主题维护不在本轮页面动作内 | 本轮验证复用租户已有 MQTT 接入通道；可以完成新设备绑定、映射和测试报文，但没有验证数据源/订阅主题新增编辑 | 后续审查“接入通道配置”时，再决定是否在设备接入页签补通道新增/编辑 |

## 当前结论

区域维护达到“新增、编辑、停用、删除、层级展示、设备统计”闭环。删除动作受子区域和设备关联保护。

设备维护达到“新增、编辑、区域挂载、停用、恢复、删除、设备详情、测点新增、测点编辑、测点删除”闭环。删除动作受子设备、测点和 MQTT 绑定关联保护。

基于已有 MQTT 接入通道，新建设备可以在设备详情页签内完成“表计绑定、点位映射、测试报文、读数生成、映射和绑定删除”。测点维护本身已经闭环，可作为当前阶段有效能力。
