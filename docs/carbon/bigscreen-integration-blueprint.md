# 大屏整合蓝图

本文定义 `warehouse-forklift` 前四个态势大屏并入 `litestar-fullstack` 的正式方案。

范围只包含四个页面：

- 企业介绍
- 态势总览
- 电量监控
- 能碳协同

不包含：

- 叉车监控页
- 旧项目的集成登录
- 旧项目 `/vscene/*`、`/vadmin/*` 兼容层
- 任何“双系统并行”过渡方案

## 目标

把大屏建设成当前平台中的一个正式模块，而不是外挂页面或临时子应用。

整合完成后的原则：

- 前端只有一套宿主 SPA，由当前 `src/js/web` 承担。
- 后端只有一套正式 API，由当前 Litestar 应用承担。
- 大屏拥有自己的一组路由、布局、查询 hooks 和 API 端点。
- 大屏复用现有业务数据模型，但不复用旧项目的页面组织方式。
- 大屏展示逻辑与后台运营页面解耦，避免把普通 CRUD 页硬拼成大屏。

## 总体决策

### 前端决策

建立独立路由组 `bigscreen`，而不是继续使用旧项目里“单页 + 本地 tab 切换”的模式。

建议路由：

- `/bigscreen`
- `/bigscreen/intro`
- `/bigscreen/overview`
- `/bigscreen/power`
- `/bigscreen/carbon`

说明：

- `/bigscreen` 默认重定向到 `/bigscreen/overview`
- 四屏共享一个“大屏专用布局”
- 该布局不复用普通后台的侧边栏、面包屑、表单页容器
- 保留平台登录态，但进入后是全屏展示体验

### 后端决策

建立独立 API 组 `bigscreen`，不直接让前端消费零散的历史接口。

建议 API 前缀：

- `/api/bigscreen/meta`
- `/api/bigscreen/intro`
- `/api/bigscreen/overview`
- `/api/bigscreen/power`
- `/api/bigscreen/carbon`

设计原则：

- 一个屏只消费 1 到 4 个聚合接口，不让页面自己拼十几个低层接口
- 聚合逻辑在后端完成，前端只负责展示
- 页面接口返回直接面向展示层，不暴露旧 Django 风格字段名

## 前端蓝图

### 路由结构

建议新增目录：

```text
src/js/web/src/routes/
  _app/
    bigscreen.tsx
    bigscreen.index.tsx
    bigscreen.intro.tsx
    bigscreen.overview.tsx
    bigscreen.power.tsx
    bigscreen.carbon.tsx
```

建议新增组件目录：

```text
src/js/web/src/components/bigscreen/
  layout/
  panels/
  cards/
  charts/
  shared/
```

建议新增数据访问目录：

```text
src/js/web/src/lib/bigscreen/
  api.ts
  hooks.ts
  types.ts
  transforms.ts
```

### 路由职责

`/_app/bigscreen.tsx`

- 大屏根布局
- 提供顶部主导航
- 提供统一背景、时间、天气、企业标题、全屏容器
- 管理“大屏模式”专属响应式缩放

`/_app/bigscreen.index.tsx`

- 仅做重定向
- 默认跳转到 `/bigscreen/overview`

`/_app/bigscreen.intro.tsx`

- 企业介绍页
- 只消费介绍类内容接口

`/_app/bigscreen.overview.tsx`

- 态势总览页
- 只消费总览类聚合接口

`/_app/bigscreen.power.tsx`

- 电量监控页
- 只消费电量、监测、预警类聚合接口

`/_app/bigscreen.carbon.tsx`

- 能碳协同页
- 只消费碳排、碳价、碳流、碳预警类聚合接口

### 布局原则

大屏布局和后台布局分离。

不要把当前这些后台组件直接当成大屏容器：

- `app-sidebar`
- `page-layout`
- 普通数据表单页页头

大屏布局应具备：

- 固定的视觉栅格系统
- 统一背景与装饰层
- 面向 16:9 的主设计稿
- 对窄屏只做“缩放适配”，不追求手机后台式响应布局

建议新增：

- `BigscreenLayout`
- `BigscreenHeader`
- `BigscreenTabs`
- `BigscreenPanel`
- `BigscreenMetricCard`

### 状态管理原则

不沿用旧项目的 `activeTab` 全局 store。

采用当前项目已有的路由驱动模式：

- 当前屏由 URL 决定
- 页内筛选由路由 search params 或局部 state 决定
- 数据请求由 `react-query` 管理

禁止继续保留以下旧结构作为主控制模式：

- `Home.tsx` 统一渲染四屏
- `useHomeStore().activeTab`
- 通过 store 控制“当前是哪一屏”

## 后端蓝图

### 控制器分组

建议新增控制器文件：

```text
src/py/app/domain/carbon/controllers/
  _bigscreen.py
```

或如果当前 `carbon/controllers.py` 仍为单文件，可先拆出：

```text
src/py/app/domain/carbon/controllers/
  _bigscreen_intro.py
  _bigscreen_overview.py
  _bigscreen_power.py
  _bigscreen_carbon.py
```

建议最终按职责拆分，不建议继续向现有超大 `controllers.py` 追加大段大屏逻辑。

### API 设计

建议接口如下。

#### 1. 元信息

`GET /api/bigscreen/meta`

返回：

- 大屏标题
- 企业简称
- 天气显示开关
- 默认首页
- 顶部导航项

用途：

- 驱动大屏布局的固定元配置

#### 2. 企业介绍页

`GET /api/bigscreen/intro`

返回：

- 企业介绍主文案
- 企业图集
- 运营项目图集
- 成功案例图集
- 宣传视频 URL
- 企业信息摘要

说明：

- 这是当前项目里最明确缺失的一块
- 不建议从零散 `EnterpriseInfo` 表硬拼出“企业介绍大屏”
- 应新增一套面向大屏内容的配置模型

建议新增模型：

- `BigscreenContent`
- `BigscreenContentSection`
- `BigscreenMediaAsset`

最小字段建议：

- `page_key`
- `section_key`
- `title`
- `description`
- `media_url`
- `sort_index`
- `is_enabled`

#### 3. 态势总览页

`GET /api/bigscreen/overview`

返回：

- 能源概览 KPI
- 碳排概览 KPI
- 能流图数据
- 生产时序图数据
- 顶部筛选项默认值

这个接口应聚合当前已有能力：

- 能碳经营概览
- 能流分析
- 设备时序或生产时序

不要求页面自己再分别请求：

- `energyOverviewNums`
- `carbonOverviewNums`
- `energyFlowChartData`
- `statis/chart`

#### 4. 电量监控页

`GET /api/bigscreen/power`

返回：

- 用电预警列表
- 用电结构图
- 用电排行
- 电量流图
- 用电时序图
- 筛选后的区域信息

这个接口主要聚合：

- 监测区域
- 监控终端
- 电表历史
- 设备告警

建议复用现有领域：

- `MonitorSector`
- `MonitorEquipment`
- `AmmeterIndexValue`
- `AlarmEvent`

#### 5. 能碳协同页

`GET /api/bigscreen/carbon`

返回：

- 碳排对比
- 产量占比或结构
- 碳流图
- 碳排预警
- 碳价走势
- 文本解读

建议复用现有领域：

- Scope1/2/3 业务表
- `AlarmEvent`
- `VedioAlarmEvent` 里与碳页无关的内容不进入此接口
- 因子和核算结果服务

### 服务层原则

不要在控制器里直接写大段 SQL 拼装页面结构。

建议新增服务层：

```text
src/py/app/domain/carbon/services/
  _bigscreen.py
```

服务拆分建议：

- `BigscreenMetaService`
- `BigscreenIntroService`
- `BigscreenOverviewService`
- `BigscreenPowerService`
- `BigscreenCarbonService`

控制器负责：

- 参数接收
- 调用 service
- 返回统一响应

service 负责：

- 聚合多表数据
- 组织展示 DTO
- 处理默认筛选逻辑

## 数据模型边界

### 可以直接复用的现有模型

- `EnterpriseInfo`
- `MonitorSector`
- `MonitorEquipment`
- `MonitorSectorPhoto`
- `VideoMonitor`
- `AlarmEvent`
- `AmmeterIndexValue`
- Scope1/2/3 碳核算表

### 不建议直接复用为大屏内容源的部分

- `EnterpriseInfo` 不能直接代替“企业介绍图文配置”
- `VideoMonitor` 不能代替“大屏宣传视频配置”
- 普通后台路由 DTO 不应直接作为大屏 DTO

### 建议新增的内容模型

新增一个面向展示配置的轻量域，建议先放在 `carbon` 域内，后续如内容增多可再独立。

建议新增：

- `BigscreenSetting`
- `BigscreenSection`
- `BigscreenAsset`

用于存储：

- 页面标题
- 区块说明文案
- 图集
- 视频资源
- 排序
- 启停状态

## 页面映射

旧四屏到新四屏的映射关系如下。

| 旧页面 | 新路由 | 新接口 |
|---|---|---|
| 企业介绍 | `/bigscreen/intro` | `/api/bigscreen/intro` |
| 态势总览 | `/bigscreen/overview` | `/api/bigscreen/overview` |
| 电量监控 | `/bigscreen/power` | `/api/bigscreen/power` |
| 能碳协同 | `/bigscreen/carbon` | `/api/bigscreen/carbon` |

## 与当前平台的关系

### 导航关系

建议在当前侧边栏增加一个一级入口：

- `大屏中心`

其子项：

- `态势总览`
- `企业介绍`
- `电量监控`
- `能碳协同`

不建议把四屏继续挂在当前 `/carbon` 下。

原因：

- 当前 `/carbon` 更像分析工作台
- 大屏是独立展示子系统
- 视觉风格、布局目标、交互方式都不同

### 权限关系

初版建议保持在 `_app` 路由下，复用现有登录态。

后续如有需要，再单独增加：

- 大屏查看权限
- 电视墙只读账号
- 只读展示 token

但这些不属于本轮蓝图范围。

## 文件落点建议

### 前端

```text
src/js/web/src/routes/_app/bigscreen.tsx
src/js/web/src/routes/_app/bigscreen.index.tsx
src/js/web/src/routes/_app/bigscreen.intro.tsx
src/js/web/src/routes/_app/bigscreen.overview.tsx
src/js/web/src/routes/_app/bigscreen.power.tsx
src/js/web/src/routes/_app/bigscreen.carbon.tsx

src/js/web/src/components/bigscreen/*
src/js/web/src/lib/bigscreen/api.ts
src/js/web/src/lib/bigscreen/hooks.ts
src/js/web/src/lib/bigscreen/types.ts
```

### 后端

```text
src/py/app/domain/carbon/controllers/_bigscreen.py
src/py/app/domain/carbon/services/_bigscreen.py
src/py/app/domain/carbon/schemas/_bigscreen.py
src/py/app/db/models/_bigscreen.py
src/py/app/db/migrations/versions/<new_bigscreen_tables>.py
```

## 实施顺序

按正式方案，建议顺序如下：

1. 先建大屏前端路由组和专用布局。
2. 建大屏后端 API 分组和 DTO。
3. 补“企业介绍页”所需的内容配置模型。
4. 先完成 `/bigscreen/overview`，验证路由、布局、查询模式。
5. 再完成 `/bigscreen/power` 和 `/bigscreen/carbon`。
6. 最后完成 `/bigscreen/intro` 的内容管理与展示联动。

原因：

- `overview` 最适合先验证整合骨架
- `intro` 依赖新增内容配置模型，反而不是最快闭环

## 本轮明确不做的事

- 不保留旧项目的 `Home.tsx + Tabs + activeTab` 架构
- 不新增 `/vscene/*` 兼容接口
- 不新增 `/vadmin/loginForIntegrate/`
- 不把旧前端整个目录直接搬进当前项目运行
- 不把叉车页混入这组大屏路由

## 最终形态

最终的大屏模块应当是：

- 前端上是一组正式路由
- 后端上是一组正式聚合 API
- 数据上复用平台主数据与核算数据
- 展示内容上拥有自己的配置模型

它属于平台的一部分，不是平台旁边再挂一个项目。
