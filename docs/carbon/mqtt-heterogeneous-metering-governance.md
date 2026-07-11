# 异构 MQTT 电表接入治理方案

## 目标与边界

平台应接收任意受授权 MQTT 数据源的原始报文，并在可配置、可审计、可回放的前提下投影为平台计量数据。外部报文不是平台领域模型：它可以脏、字段可变、质量标志不完整，不能直接写入电量账本或告警表。

本方案覆盖 MQTT 电表数据；HTTP 云集和红外采集继续通过各自适配器输出同一组计量领域字段。现有 `AmmeterIndexValue` 保持为四类总电能的兼容投影，不能承担任意测点的原始时序存储。

## 领域边界

不应建立一个把电表、光伏、BMS、相机和传感器业务规则混在一起的 `mqtt` 业务域。MQTT 是传输协议；平台应建立 `iot_ingestion`（物联网消息接入）有界上下文，负责外部消息从到达到可投影的全过程。

```text
MQTT Broker
    -> iot_ingestion：连接、订阅、原文、契约、质量、重放
    -> 领域投影处理器：metering / pv / storage / safety / environment
    -> 各领域自己的事实表、告警和分析
```

`iot_ingestion` 不理解“正向有功电能”或“电池 SOC”等业务含义；它只产出带来源、设备绑定候选、时间、质量和原始值的标准化消息。`metering` 领域负责把这类消息映射为电表读数，未来的光伏、BMS、环境监测和非电表事件只需增加自己的消息契约和投影处理器，不复制 Broker 连接和重连逻辑。

建议的新模块边界如下，现有 `carbon.collectors` 可逐步迁移，不要求一次重构旧 HTTP 适配器：

```text
app/domain/iot_ingestion/
  domain/           # SourceContract、InboundMessage、MessageQuality、ProjectionRequest
  usecases/         # ReceiveMessage、ValidateMessage、ReplayMessage、DispatchProjection
  infrastructure/   # MQTT client、SQLAlchemy repositories、SAQ tasks
  controllers/      # 数据源、订阅、契约、隔离报文和重放管理接口

app/domain/metering/
  usecases/         # ProjectMeterReadings、EvaluateMeterDataQuality
  infrastructure/   # szscada 电表投影处理器、AmmeterIndexValue / MeterPointReading 持久化
```

投影处理器通过 `ProjectionRequest` 协议注册在应用组合层。`iot_ingestion` 只依赖该协议，不反向依赖 `metering`、`carbon` 或具体 SQLAlchemy 模型；这保证新增非电表设备不需要修改接入核心。

## 现场报文事实

- 数据源：`szscada/xc`，约 5 分钟一条。
- 报文结构：`guid`、秒级 Unix 时间戳 `ts`、`devs[]`、`devs[].data[]`。
- 每个测点包含 `name`、`tag`、`valid`、`value`、`t`。
- 一条真实报文包含 8 块电表、每块 20 个点。相同 `tag` 在不同电表上重复，不能单独作为测点唯一键。
- 当前 `devName` 为 `noname1`，也不能唯一识别物理电表；报文只在 `name` 中带有“1号电表”等展示性前缀。
- 观测到 `valid=1,value=0`（有效零值）和 `valid=0,value=0,t=1`（无效值）同时存在。因此零值绝不能用于推断质量。
- `t` 的协议语义尚未由现场点表或厂家文档确认，只能原样保留，不应先行解释为数据类型、告警类型或状态码。

真实结构的脱敏回放样本见 `src/py/tests/fixtures/carbon/mqtt/szscada_xc_v1.json`。网关标识已替换，保留秒级时间戳和有效、无效、有效零值三种代表状态。

## 目标数据契约

MQTT 接入分为四层，前一层永远不依赖后一层成功。

```text
Broker -> 原始报文留存 -> 校验/去重/隔离 -> 配置化解析 -> 领域投影 -> 统计与告警
```

1. 原始报文留存
   每个到达的报文先写入 `MqttInboundMessage`（建议新增）。字段至少包括：`team_id`、`source_id`、`topic`、`received_at`、`published_at`、`payload`、`payload_hash`、`parse_status`、`error_code`、`error_detail`。`payload_hash` 用于幂等去重；原文不可被标准化过程覆盖。

2. 配置化解析
   根据订阅配置选择解析器。当前保留 `szscada_scada_v1`（多电表点表报文）。解析器只负责结构展开、时间戳转换、产生来源测点和质量，不负责把 `tag` 写死为平台字段。

3. 领域投影
   - 四类总电能投影到 `AmmeterIndexValue`，以兼容现有能源、碳核算和报表。
   - 尖峰平谷及后续任意测点投影到通用 `MeterPointReading`，不能丢入固定字段遥测表。
   - 原始报文、通用测点读数和四类电能投影通过 `source_message_id` 关联，支持回放、重算和追溯。

4. 告警投影
   数据质量、设备通信、DL/T 645 事件和业务阈值是不同来源。先保留原始状态或事件，再映射为现有 `AlarmEvent`；不能把单次 `valid=0` 直接当作设备故障。

## 配置模型

连接密码必须作为环境变量或密钥服务引用保存，不能写入数据库普通字段或 fixture。连接与业务映射必须分开：同一个 Broker 可承载多个租户、主题和报文类型。

| 配置对象 | 关键字段 | 作用 |
| --- | --- | --- |
| MQTT 数据源 | `team_id`、名称、host、port、credential_ref、TLS、client_id、启用状态 | 一个可运维的 Broker 连接 |
| 订阅 | `source_id`、topic、QoS、解析器、预期周期、启用状态 | 一种外部报文契约 |
| 网关/设备绑定 | `source_id`、gateway_key、meter_selector、equipment_id、倍率策略 | 将外部物理表定位到 `MonitorEquipment` |
| 测点映射 | `binding_id`、source_tag、source_name_pattern、point_code、单位、倍率、质量规则、目标字段 | 将外部测点投影到标准测点 |

现有 `MonitorEquipment.external_device_id` 可作为绑定结果的一部分，现有 `DevicePoint.source_field` 可保存来源 tag。但这两个字段不足以表达当前报文：因为 `tag_010_p001` 在 1 至 8 号电表间重复，必须增加 `meter_selector`，例如临时的名称前缀规则 `^1号电表`。

临时名称规则只能作为过渡方案。现场应在每个电表对象或每个点上增加稳定的 `meter_id` 或 DL/T 645 电表通信地址；这是多表接入能够长期可靠运行的前置条件。

临时绑定使用完整地址 `TEMP-SZXC-{guid}-M001` 存入 `address`，并使用短代码 `SZXC-{gateway_hash}-M001` 存入遗留的 `ammeter_id`，以满足其 20 字符字段限制。

## 首批测点映射

以下映射来自本次真实报文的 `name` 和 `tag`，并与现有字段兼容。无功方向或象限组合的标准术语须由电表点表确认后固定，不能仅凭中文展示名替换。

| 来源 tag | 来源名称后缀 | 兼容字段 | 业务名称 | 单位 |
| --- | --- | --- | --- | --- |
| `tag_010_p001` | 正向有功总 | `zygdn` | 正向有功总电能 | kWh |
| `tag_010_p006` | 正向无功总 | `zwgdn` | 正向无功总电能 | kvarh，待确认 |
| `tag_010_p011` | 反向有功总 | `fygdn` | 反向有功总电能 | kWh |
| `tag_010_p016` | 反向无功总 | `fwgdn` | 反向无功总电能 | kvarh，待确认 |

`p002-p005`、`p007-p010`、`p012-p015`、`p017-p020` 分别为尖、峰、平、谷时段读数，应作为通用电表测点保存。它们不能塞进现有四个总电能字段，也不应因为首期报表暂不使用而丢弃。

## 数据质量规则

| 条件 | 原始报文 | 通用测点读数 | 四类电能投影 | 告警策略 |
| --- | --- | --- | --- | --- |
| `valid=1` | 留存 | `valid` | 允许投影，零值合法 | 按正常业务阈值判断 |
| `valid=0` | 留存 | `invalid`，保留原值 | 不更新账本读数 | 连续无效或超时后产生数据质量事件 |
| 缺字段/未知 tag/非数值 | 留存 | `rejected` 或 `unmapped` | 不投影 | 记录接入异常，待配置处理 |
| 重复报文 | 留存或标记重复 | 不重复写入 | 不重复写入 | 不告警 |
| 到达乱序 | 留存 | 标记乱序 | 不覆盖较新读数 | 仅在超出容忍窗口时提示 |
| 超过 15 分钟未收到数据 | 无新增 | 标记数据陈旧 | 不生成估算电量 | 产生通信/数据新鲜度事件 |

实际倍率必须配置在设备绑定中，明确为“上游已折算”或“采集值乘 CT/PT 倍率”。平台应同时保存原始值和折算值。现有代码中 `zygdn` 与 `zygdnsz` 在不同计算中被分别使用，接入前必须统一该口径，避免重复乘倍率或漏乘倍率。

## 运行与生效方式

不拆新的微服务。MQTT 接入作为本系统 SAQ 的专用队列运行，队列名建议为 `mqtt-ingest`，并固定为一个 worker 进程。该 worker 在 SAQ 启动钩子中启动 `iot_ingestion` 的订阅运行器；运行器负责持久订阅、重连和将消息投递给原始报文持久化任务，后续解析和领域投影仍通过 SAQ 任务执行。

```text
SAQ queue: mqtt-ingest (worker_processes=1)
  subscription runner -> persist_inbound_message -> validate_and_dispatch
                                              -> metering projection task
                                              -> other domain projection tasks

Web / normal background-tasks queues
  只读接入状态、管理订阅配置、执行非 MQTT 业务任务
```

这样仍是同一个仓库、同一套配置、同一数据库和同一部署单元；区别只是将长连接的运行责任从 Web 进程移至一个受控的 SAQ worker。Web 横向扩容、热更新或重启不会造成多实例重复订阅。需要具备：连接状态、最近接收时间、接收数、解析失败数、未映射数、无效点数、入库延迟和积压量监控。

部署时保留现有 `background-tasks` worker，并以同一镜像新增一个单副本 worker，设置 `SAQ_WORKER_QUEUE=mqtt-ingest` 后执行：

```bash
saq app.lib.worker.saq_worker_settings --workers 1
```

MQTT 数据源记录只保存用户名、密码的环境变量名，例如 `SZSCADA_MQTT_USERNAME` 和 `SZSCADA_MQTT_PASSWORD`，不保存凭据本身。首个 SZSCADA 数据源的订阅配置为 `szscada/xc`、`szscada_scada_v1`、QoS 1、预期周期 300 秒。

管理员通过以下接口配置和审计接入：`/api/iot-ingestion/mqtt-sources`、`/mqtt-subscriptions`、`/mqtt-device-bindings`、`/mqtt-point-mappings` 和只读的 `/mqtt-messages`。所有接口按企业租户隔离，写入和原文状态查询要求超级管理员权限；原始 `payload` 不在列表接口返回，避免将外部报文作为普通业务数据暴露。

旧的 `carbon.collectors.mqtt_adapter` 常驻线程、独立脚本、`carbon_telemetry_v1` 解析器和 `dataapp_iottelemetry` 投影已移除；所有 MQTT 数据统一由 `iot_ingestion` 的数据源配置、SAQ 专用队列和版本化解析器承载。

## 实施验收顺序

1. 为 `szscada_xc_v1.json` 编写 `iot_ingestion` 的解析、质量和投影分派单元测试，先不连现场 Broker。
2. 建立 MQTT 数据源、订阅、设备绑定、测点映射和原始报文表的迁移及管理接口。
3. 增加单副本 `mqtt-ingest` SAQ 专用队列，先只落原始报文和质量结果，连续观察一个采集周期。
4. 配好 8 块表的稳定标识、单位、倍率后，在 `metering` 中开启四类总电能到 `AmmeterIndexValue` 的投影。
5. 开启尖峰平谷通用测点投影，再接入数据质量和通信异常告警；新增其他设备类型时仅新增领域投影处理器。

## 现场待确认项

- 每块电表的稳定唯一标识：优先 DL/T 645 通信地址。
- `value` 的单位、小数位、是否已按 CT/PT 倍率折算。
- “正向/反向无功”与组合无功、四象限无功的准确对应关系。
- `valid` 和 `t` 的枚举定义、错误码及恢复语义。
- MQTT QoS、retain、离线缓存及重发策略。

## 参考

- 用户提供的 DL/T 645-2007 协议资料：<https://www.dlt698.com/sg64507pro.pdf>
- 现有四类电能兼容模型：`src/py/app/domain/carbon/models.py::AmmeterIndexValue`
- 现有测点配置模型：`src/py/app/domain/carbon/models.py::DevicePoint`
