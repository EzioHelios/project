# 大屏优化蓝图

本文在既有大屏整合方案基础上，定义 `litestar-fullstack` 大屏模块的第二阶段优化方向。

本文聚焦四个页面：

- `企业介绍`
- `态势总览`
- `电量监控`
- `能碳协同`

本文不包含：

- 叉车页
- 旧项目兼容接口
- 业务数据模型重构

## 一句话结论

当前版本已经完成了“大屏模块接入”，但还没有完成“真正可上墙的大屏系统设计”。

下一阶段不应继续堆页面卡片，而应把大屏重构为三层体系：

1. `Background Canvas Layer`
2. `Central Visual Safe Zone`
3. `HUD Data Layer`

目标是让中间主视觉区服务 GIS / Cesium / Three.js / Pixel Streaming，四周才是关键信息带，同时保留旧仓库里已经验证过的轮播、滚动榜单、动态切换能力。

## 当前问题诊断

### 1. 分辨率适配仍然偏“后台页面缩放”

当前实现已经采用 `1920x1080` 基准缩放，这一步是正确的，但仍然属于“把整页按比例缩放”的范式。

问题在于：

- 1080p、2K、4K 只有同一套版式，缺少分档设计。
- 所有面板都争抢主舞台，没有清晰的主视觉留白区。
- 信息密度在 4K 下会显得过散，在 1080p 下又容易偏挤。
- 目前更像“好看的全屏后台页”，而不是“围绕主对象组织的信息 HUD”。

现有实现参考：

- [当前大屏布局](../../src/js/web/src/components/bigscreen/layout.tsx)
- [当前 overview 页面](../../src/js/web/src/routes/_app/bigscreen/overview.tsx)
- [当前 power 页面](../../src/js/web/src/routes/_app/bigscreen/power.tsx)

### 2. 中央主视觉区没有被制度化保留

现在四屏都采用“满画布铺格子”的方式，虽然规整，但没有为 GIS / 3D / 主对象留出制度化空间。

这会导致后续接入：

- Cesium 园区地图
- Three.js 仓储主对象
- Pixel Streaming 运行场景

时只能把画布当成背景贴图，而不是让它成为主叙事区域。

### 3. 信息筛选还不够“大屏化”

当前页面已经能显示数据，但还没有建立“哪些信息适合常驻大屏”的统一判断标准。

问题主要体现在：

- 页面里仍然保留了偏后台式的信息块分布
- 卡片数量略多于主观看屏所需
- 某些信息对持续观看价值不高
- 告警、排行、趋势、主流向之间还没有明确主次层级

### 4. 动态感没有系统设计

当前新版已经有一些光效、渐变和图表，但动态节奏仍然偏弱。

而旧仓库已经有可复用的动态能力：

- `Introduce` 页的 `Carousel autoplay`
- `ScrollBoard` 的自动滚动榜单
- `PixelStreamingWrapper` 的主视觉叠层

旧实现参考：

- [旧 Home 壳](</Users/eziohelios/Dev/warehouse-forklift/web/src/pages/Home/index.tsx>)
- [旧 Introduce](</Users/eziohelios/Dev/warehouse-forklift/web/src/pages/Introduce/index.tsx>)
- [旧 ScrollBoard](</Users/eziohelios/Dev/warehouse-forklift/web/src/components/common/ScrollBoard/index.tsx>)

## 优化目标

第二阶段的大屏目标不是“把现有页面做得更花”，而是建立一套稳定的展示体系。

必须同时满足：

- 适配 1080p / 2K / 4K 的主分辨率
- 始终保留中央主视觉安全区
- 保证信息只展示真正适合上墙的关键内容
- 在正确渲染的前提下保留动态节奏
- 为 GIS / Three.js / Cesium 接入预留清晰的技术边界

## 总体架构

建议将大屏重新定义为三层架构。

### Layer 1: Background Canvas Layer

职责：

- 全屏地图、三维场景、园区模型、主对象动画
- 主光效、空间感、路径感
- 少量高价值空间锚点

特点：

- 永远铺满整个屏幕
- 不承担复杂列表和密集文本
- 与页面 UI 解耦

建议实现：

- 新增 `BigscreenSceneHost`
- 通过路由或 page config 控制当前页面加载哪一种场景
- 先支持静态背景 / 伪画布占位，后续接入 Cesium 或 Three.js

### Layer 2: Central Visual Safe Zone

职责：

- 保护中间主对象显示区域
- 禁止普通卡片侵入
- 为地图、3D 仓库、主能流路径、关键设备高亮让位

建议按 1920x1080 基准定义：

- 中央安全区宽度占比：`44% ~ 50%`
- 中央安全区高度占比：`50% ~ 60%`
- 顶部标题栏单独占用，不计入中央安全区

这不是一个可选布局技巧，而是下一阶段必须固化的舞台规则。

### Layer 3: HUD Data Layer

职责：

- 页面标题
- 时间天气
- KPI
- 趋势
- 告警
- 排行
- 流向解读
- 说明文字

特点：

- 只贴边，不抢中心
- 更像战术 HUD，而不是后台卡片墙

## 分辨率与舞台适配方案

### 1. 保留固定 16:9 舞台

继续以 `1920x1080` 作为设计坐标系，但从“纯 transform 缩放”升级为“有比例约束的 stage shell”。

建议规则：

- 根舞台固定 `16 / 9`
- 视口始终居中
- 外部视口超出部分由背景层吞掉
- HUD 层和 Canvas 层都基于同一舞台坐标系

推荐使用：

- CSS `aspect-ratio` 固定舞台比例
- `ResizeObserver` 或 `window.resize` 驱动尺寸同步

资料：

- [MDN: aspect-ratio](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/aspect-ratio)

### 2. 建立分辨率分档，而不是只有一个 scale

建议定义三档视觉 token：

- `1080 tier`
- `1440 tier`
- `2160 tier`

需要分档的不是只有缩放倍率，还包括：

- 标题字号
- 数字字号
- panel padding
- gap
- 图表高度
- 描边粗细
- 阴影强度
- 动画幅度

建议原则：

- 1080p：优先可读性，控密度
- 2K：标准展示档
- 4K：增加留白、增强主对象表现，不线性增加信息量

### 3. 不让 Canvas 无脑吃满设备像素比

如果后续接入 Three.js 或 Cesium，需要明确控制渲染分辨率。

建议：

- 1080p：允许接近 `devicePixelRatio`
- 2K：视场景复杂度上限到 `1.5 ~ 2`
- 4K：必须有上限钳制，避免 GPU 压力过大

资料：

- [Three.js WebGLRenderer.setSize](https://threejs.org/docs/pages/WebGLRenderer.html)
- [Cesium Viewer.useBrowserRecommendedResolution](https://cesium.com/learn/cesiumjs/ref-doc/Viewer.html)

## 空间布局蓝图

下一阶段不建议继续使用“24 栅格铺满”的思路，而应改成“环绕主视觉”的结构。

## 基础布局骨架

建议基准结构：

- 顶部 Header Band：`10% ~ 12%`
- 左侧 Information Rail：`23% ~ 26%`
- 右侧 Information Rail：`23% ~ 26%`
- 底部 Status Band：`18% ~ 22%`
- 中央 Main Visual Safe Zone：剩余中部核心区域

示意：

```text
┌────────────────────────── Header Band ──────────────────────────┐
│ 标题 / 时间 / 天气 / 当前场景 / 顶部导航                        │
├──────────── Left Rail ───────────┬──────── Main Visual ────────┬──────────── Right Rail ───────────┤
│ KPI / 趋势 / 结构                 │ GIS / Cesium / Three.js     │ 告警 / 排行 / 事件 / 说明         │
│                                   │ 主对象 / 主线路 / 空间锚点  │                                   │
├──────────────────────────── Bottom Status Band ────────────────────────────┤
│ 时间序列 / 滚动榜单 / 状态条 / 页面级辅助指标                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 四屏布局建议

### 1. 企业介绍

中央主视觉区：

- 企业主形象视频或品牌主画面
- 可兼容后续 3D 园区形象

左侧：

- 企业摘要
- 规模指标
- 企业图集轮播

右侧：

- 运营项目轮播
- 成功案例轮播
- 关键资质 / 核心能力

底部：

- 企业信息摘要条
- 重点能力标签

动态机制：

- 保留旧 `Carousel autoplay`
- 视频保持低频动势
- 轮播与视频不要同时抢节奏

### 2. 态势总览

中央主视觉区：

- 总能流 / 园区 GIS / 3D 运行主场景

左侧：

- 能耗 KPI
- 碳排 KPI
- 核心趋势概览

右侧：

- 当前筛选摘要
- 关键异常摘要
- 区域占比

底部：

- 月度趋势
- 简版排行 / 区域对比

要求：

- 这是全套大屏的母版页
- 后续 `power` 和 `carbon` 的 HUD 结构优先沿用这里的舞台范式

### 3. 电量监控

中央主视觉区：

- 配电路径 / 园区电力流向 / 主区域用电热区

左侧：

- 运行 KPI
- 预警滚动榜

右侧：

- 用电结构
- 用电排行

底部：

- 用电时间序列
- 状态带 / 事件摘要

动态机制：

- 告警区采用滚动列表
- 排行区允许分组切换或自动翻页

### 4. 能碳协同

中央主视觉区：

- 范围级碳流 / 设备-区域-范围关系图 / 园区碳热点对象

左侧：

- 范围 1/2/3 对比
- 总碳排 KPI

右侧：

- 碳预警
- 说明性 commentary
- 因子或碳价状态

底部：

- 碳价趋势
- 历史时序

要求：

- 说明文字必须短句化
- 不允许大段阅读型文案挤占主屏

## 信息组件筛选规则

大屏不等于“把后台图表放大”。

建议只保留四类常驻组件。

### 1. 一眼看懂状态的 KPI

适合：

- 总量
- 占比
- 环比
- 活跃设备数
- 在线区域数

不适合：

- 需要解释前置条件的复杂业务值

### 2. 有节奏判断价值的趋势图

适合：

- 月度
- 日内
- 最近 N 周期

要求：

- 趋势图必须短而强，不堆过多序列

### 3. 有空间表达价值的流向或地图

适合：

- 能流
- 碳流
- 设施热点
- 区域分布

要求：

- 中央主对象优先
- 侧边图只做辅助解读

### 4. 需要持续盯看的事件流

适合：

- 告警
- 排行
- 风险事件

要求：

- 使用滚动组件
- 限制同时展示条数
- 明确优先级颜色

## 动态机制蓝图

下一阶段的大屏动态不应仅靠“边框发光”和“背景粒子”。

建议建立三种明确的动态来源。

### 1. 媒体轮播

用于：

- 企业介绍
- 项目图集
- 成功案例

保留旧项目能力：

- `Carousel autoplay`

要求：

- 轮播周期稳定
- 不出现手风琴式频繁闪切
- 图片与文案切换保持同步

### 2. 榜单滚动

用于：

- 告警列表
- 排行榜
- 事件流

保留旧项目能力：

- `ScrollBoard`

要求：

- 悬停可暂停
- 非交互场景下自动滚动
- 单屏展示条数受控

### 3. 数据过渡动画

用于：

- 图表更新
- 数字翻动
- 结构切换

建议优先用图表原生 transition，不手搓大段动画逻辑。

资料：

- [Apache ECharts Data Transition](https://echarts.apache.org/handbook/en/how-to/animation/transition/)

## 动画纪律

必须建立统一纪律，避免同时乱动。

建议：

- 同屏同时强运动模块不超过 `2 ~ 3` 个
- 中央主视觉正在运动时，边缘面板尽量稳
- 告警滚动和大轮播不要同时抢节奏
- 首屏动画只在进入页时触发一次

## GIS / Three.js / Cesium 接入蓝图

### 背景层接入原则

建议新增：

- `BigscreenSceneHost`
- `BigscreenSceneController`
- `BigscreenOverlayAnchors`

职责划分：

- `SceneHost` 只管挂载画布和生命周期
- `SceneController` 只管场景配置、相机、主对象
- `OverlayAnchors` 只管 DOM 锚点和 HUD 联动

### DOM 锚点策略

不建议把大量 HTML 面板直接压进 GIS / 3D 场景中心。

只保留：

- 主对象标签
- 极少量关键实体提示
- 当前选中实体卡片

如果走 Cesium：

- 使用世界坐标到窗口坐标映射来放置 HTML 锚点

资料：

- [Cesium SceneTransforms.worldToWindowCoordinates](https://cesium.com/learn/cesiumjs/ref-doc/SceneTransforms.html?classFilter=SceneTransforms)

如果走 Mapbox：

- 少量交互点位可用 Marker
- 大量点位必须走 layer，而不是 DOM marker

资料：

- [Mapbox Markers](https://docs.mapbox.com/mapbox-gl-js/guides/add-your-data/markers/)
- [Mapbox Markers vs Layers](https://docs.mapbox.com/help/dive-deeper/markers-vs-layers/)

### 渲染性能边界

建议：

- 3D 背景和 HUD 分层
- HUD 面板启用局部 containment
- 图表刷新频率按业务优先级分层
- 主视觉引擎独立控制帧率和像素比

资料：

- [MDN: contain](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/contain)

## 内容正确渲染策略

下一阶段不能只做 layout，还要保证“放上去的内容是正确、完整、可读的”。

建议建立以下规则。

### 1. 页面级数据契约稳定

- 列表统一返回空数组
- 图表统一返回空结构
- 数字缺失统一有占位规则

### 2. 文案长度受控

- 标题限制字数
- 说明文字以短句为主
- 长文本不直接上大屏

### 3. 图片与媒体容错

- 图片缺失有统一空态
- 视频缺失有 poster 占位
- 轮播位为空时不应破版

### 4. 图表显示策略

- 标签过长要截断或换层显示
- 同图序列数必须受控
- 图例不宜堆满主屏

## 建议的代码重构方向

建议新增或重构以下前端结构：

```text
src/js/web/src/components/bigscreen/
  layout/
    stage-shell.tsx
    header-band.tsx
    side-rail.tsx
    bottom-band.tsx
    scene-host.tsx
  motion/
    auto-carousel.tsx
    scroll-board.tsx
    count-up.tsx
  overlay/
    anchor-layer.tsx
    anchor-tag.tsx
  panels/
    metric-cluster.tsx
    alert-feed.tsx
    rank-board.tsx
    trend-panel.tsx
```

建议重构现有页面：

- [当前 layout.tsx](../../src/js/web/src/components/bigscreen/layout.tsx)
- [当前 overview.tsx](../../src/js/web/src/routes/_app/bigscreen/overview.tsx)
- [当前 power.tsx](../../src/js/web/src/routes/_app/bigscreen/power.tsx)
- [当前 carbon.tsx](../../src/js/web/src/routes/_app/bigscreen/carbon.tsx)
- [当前 intro.tsx](../../src/js/web/src/routes/_app/bigscreen/intro.tsx)

## 分阶段实施顺序

### Phase 1: 舞台与分辨率系统

目标：

- 先把“中空主视觉 + HUD 环绕”定下来

工作：

- 重构 `BigscreenLayout`
- 引入分辨率分档 token
- 把现有 `24-grid` 改为“Header + Left + Right + Bottom + Center Safe Zone”

### Phase 2: 动态组件层

目标：

- 恢复大屏动态感基础设施

工作：

- 迁入轮播组件
- 迁入滚动榜单组件
- 统一数字跳动和图表过渡策略

### Phase 3: Overview 母版页重构

目标：

- 做出真正的中空主视觉母版

工作：

- 优先改 `overview`
- 中央区先用静态场景占位或伪 GIS 占位

### Phase 4: Power / Carbon 空间化

目标：

- 让 `power` 与 `carbon` 都围绕主视觉组织信息

工作：

- 告警、排行、流图重新布边
- 保留趋势和榜单动态

### Phase 5: Intro 媒体化

目标：

- 把 `intro` 做成品牌展示页，而不是普通信息页

工作：

- 恢复轮播、视频、企业信息联动
- 控制文本密度

### Phase 6: 真正接入 GIS / Three.js

目标：

- 背景层成为主叙事层

工作：

- 接入场景引擎
- 建立 DOM 锚点桥接
- 验证 1080p / 2K / 4K 性能

## 验收标准

下一阶段完成后，应满足以下验收标准。

### 视觉与舞台

- 1080p、2K、4K 下均保持 16:9 主舞台稳定
- 中央主视觉区始终不被普通卡片侵入
- 左右下三条信息带层级清晰

### 内容

- 每屏只保留高价值组件
- 空数据不破版
- 文案不超长、不堆叠

### 动态

- 至少具备轮播、滚动榜单、图表平滑过渡三类动态能力
- 动态节奏克制，不出现满屏同时运动

### 技术

- GIS / 3D 背景层可独立接入
- HUD 层与背景层清晰分离
- 主对象锚点可扩展

## 结论

第二阶段的关键不是继续美化单个 panel，而是把大屏从“卡片网格页面”升级成“围绕主视觉组织信息的展示系统”。

真正优先级如下：

1. 先定舞台结构
2. 再定中央安全区
3. 再筛选页面信息
4. 再恢复动态机制
5. 最后接 GIS / Three.js

如果按这个蓝图推进，后续不管接的是 Cesium、Three.js、Mapbox 还是 Pixel Streaming，都不会再推翻页面结构。
