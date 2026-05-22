# 大屏换肤系统蓝图

本文定义 `litestar-fullstack` 大屏模块的换肤系统架构、资源清单和复刻边界。

本文目标不是继续堆“专用页面切图”，而是把现有大屏重构成：

1. `业务布局` 与 `视觉皮肤` 解耦
2. 可复用的空壳组件优先
3. 只保留少量确实具有通用性的位图资源
4. 把旧大屏中的成品切图反解成一套 `SVG / CSS / 渐变 / 装饰原语`

## 一句话结论

当前项目已经有稳定的大屏业务骨架：

- 根布局：[src/js/web/src/components/bigscreen/layout.tsx](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/layout.tsx:58)
- 通用面板：[src/js/web/src/components/bigscreen/panel.tsx](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/panel.tsx:6)
- 场景主视觉区：[src/js/web/src/components/bigscreen/scene.tsx](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/scene.tsx:15)
- 滚动榜单与轮播：[src/js/web/src/components/bigscreen/motion.tsx](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/motion.tsx:61)
- 页面布局参考：
  [overview.tsx](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/routes/_app/bigscreen/overview.tsx:1)
  [power.tsx](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/routes/_app/bigscreen/power.tsx:1)
  [carbon.tsx](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/routes/_app/bigscreen/carbon.tsx:1)
  [intro.tsx](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/routes/_app/bigscreen/intro.tsx:1)

下一阶段不应重写页面数据结构，而应在这个骨架之上新增一套 `Skin System`。

## 范围

本文只覆盖：

- 四个正式大屏页面的视觉换肤
- 头部总标题、面板壳、侧栏卡、滚动榜单壳、轮播壳
- 资源分层和 SVG 复刻规格
- 可直接复用的底图与装饰图

本文不覆盖：

- 数据接口重构
- 新增图表类型
- GIS / Cesium / Three.js 技术选型
- 后台普通页面视觉风格

## 参考来源

本次换肤系统主要参考以下两套旧资源。

### 1. `taizhouwarehouse`

优势：

- 整体舞台感强
- 标题横幅、宽面板、竖面板的比例成熟
- 适合反向拆解视觉语法

主要资源目录：

- [taizhouwarehouse/static](</Users/eziohelios/Dev/xtck/taizhouwarehouse/static>)
- [2.01209f09.chunk.css](/Users/eziohelios/Dev/xtck/taizhouwarehouse/2.01209f09.chunk.css:1)

局限：

- 大部分是成品切图
- 很多标题直接烘焙进 PNG
- 不适合直接作为长期通用组件

### 2. `warehouse-forklift`

优势：

- 标题条与边框壳更接近组件皮肤思路
- 更适合做“空壳资源”参考

关键资源：

- [section-title-normal.png](/Users/eziohelios/Dev/warehouse-forklift/web/public/img/section-title-normal.png)
- [section-title-wide.png](/Users/eziohelios/Dev/warehouse-forklift/web/public/img/section-title-wide.png)
- [border-panel-normal.png](/Users/eziohelios/Dev/warehouse-forklift/web/public/img/border-panel-normal.png)
- [border-panel-wide.png](/Users/eziohelios/Dev/warehouse-forklift/web/public/img/border-panel-wide.png)

## 当前大屏骨架的换肤点

现有 `bigscreen` 结构已经天然适合做换肤系统。建议把换肤点固定为以下 5 层。

### Layer 1: Skin Tokens

职责：

- 管理颜色、发光、圆角、描边、尺寸分档
- 管理 1080 / 1440 / 2160 三档视觉 token

当前对应：

- [bigscreen.css](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/bigscreen.css:45)

建议沉淀：

- `src/js/web/src/components/bigscreen/skins/<skin-id>/tokens.css`

### Layer 2: Page Chrome

职责：

- 整页背景
- 顶部总标题壳
- 导航 tab 风格
- 时间 / 日期 / 天气区视觉

当前对应：

- [layout.tsx](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/layout.tsx:68)
- [bigscreen.css](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/bigscreen.css:238)

建议资源组件：

- `ScreenBackdrop`
- `ScreenHeader`
- `HeaderTitlePlate`
- `HeaderNavTab`
- `HeaderClockWeather`

### Layer 3: Panel Frame Primitives

职责：

- 面板外轮廓
- 标题条
- 顶部高光线
- 角标装饰
- 内边距安全区

当前对应：

- [panel.tsx](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/panel.tsx:24)
- [bigscreen.css](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/bigscreen.css:182)

建议资源组件：

- `PanelFrame`
- `PanelTitleBar`
- `PanelAccentLine`
- `PanelCornerDecor`

### Layer 4: Content Shells

职责：

- 数值卡
- 信息卡
- 榜单壳
- 轮播壳
- 图表容器壳

当前对应：

- [BigscreenMetricCard](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/panel.tsx:38)
- [BigscreenInfoCard](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/panel.tsx:69)
- [BigscreenAutoCarousel](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/motion.tsx:61)
- [BigscreenScrollBoard](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/motion.tsx:103)

建议资源组件：

- `MetricStatCard`
- `SplitSummaryCard`
- `ListBoardShell`
- `MediaPanelShell`
- `ChartPanelShell`

### Layer 5: Scene Overlay

职责：

- 主视觉安全区
- 中心环形发光
- 场景锚点 chips
- 叠层网格与扫描线

当前对应：

- [scene.tsx](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/scene.tsx:39)
- [bigscreen.css](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/bigscreen.css:299)

建议资源组件：

- `SceneGridOverlay`
- `SceneCenterPlate`
- `SceneAnchorChip`
- `SceneGlowRings`

说明：

- 这一层继续优先使用 `CSS + SVG`，不建议回退成大位图

## 目标目录结构

建议新增：

```text
src/js/web/src/components/bigscreen/
  primitives/
    ScreenHeader.tsx
    PanelFrame.tsx
    PanelTitleBar.tsx
    PanelShell.tsx
    SceneOverlay.tsx
  skins/
    types.ts
    registry.ts
    taizhou/
      index.ts
      tokens.css
      assets/
        screen-header-base.svg
        screen-title-center-plate.svg
        panel-title-strip.svg
        panel-frame-wide.svg
        panel-frame-tall.svg
        panel-frame-narrow.svg
        collapse-left.svg
        collapse-right.svg
```

## 皮肤协议

建议皮肤配置最少包含以下字段。

```ts
export type BigscreenSkinDefinition = {
  id: string
  displayName: string
  tokenClassName: string
  assets: {
    backdropImage?: string
    headerBase?: string
    headerTitlePlate?: string
    panelTitleStrip?: string
    panelFrameWide?: string
    panelFrameTall?: string
    panelFrameNarrow?: string
    collapseLeft?: string
    collapseRight?: string
  }
  panelInsets: {
    wide: { top: number; right: number; bottom: number; left: number }
    tall: { top: number; right: number; bottom: number; left: number }
    narrow: { top: number; right: number; bottom: number; left: number }
  }
}
```

说明：

- `assets` 允许部分为空
- 空资源使用 CSS 渐变 fallback
- `panelInsets` 决定内容区安全边距，避免换壳后内容压到装饰

## 可直接保留复用的现成资源

下面这些资源本身就具有通用性，建议直接纳入皮肤包，不需要重画。

### 页级位图

1. 背景主图
- 文件： [bg.a064ede0.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/bg.a064ede0.png)
- 尺寸： `3840x2160`
- 用法：整页背景层
- 说明：深色园区俯视底图，通用性强，建议直接保留

2. 场景底图备选
- 文件： [beijingtu.fe54c882.jpg](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/beijingtu.fe54c882.jpg)
- 尺寸： `1920x1080`
- 用法：特殊页面的主视觉背景备选
- 说明：更偏场景底图，不作为默认皮肤主背景

### 装饰位图

1. 左右收起按钮参考
- 文件：
  [close_btn_left@2x.e54d4299.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/close_btn_left@2x.e54d4299.png)
  [close_btn_right@2x.8d52b820.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/close_btn_right@2x.8d52b820.png)
- 用法：抽屉收起按钮
- 说明：可以直接保留，也可以按其视觉重绘成 SVG

2. 球体装饰参考
- 文件： [yuanqiu.d77992d8.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/yuanqiu.d77992d8.png)
- 用法：汇总球形装饰或中心 KPI 氛围层
- 说明：建议先保留参考，再视需要重绘

3. 终端 / 状态图标参考
- 文件：
  [yongdianzhongduanzongshu.9f537936.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/yongdianzhongduanzongshu.9f537936.png)
  [yongdianzhongduanzaixian.791eb30d.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/yongdianzhongduanzaixian.791eb30d.png)
  [yongdianzhongduanguzhang.b9d3e33b.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/yongdianzhongduanguzhang.b9d3e33b.png)
  [fadianzhongduanzongshu.636bd929.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/fadianzhongduanzongshu.636bd929.png)
  [fadianzhongduanzaixian.a5bcee55.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/fadianzhongduanzaixian.a5bcee55.png)
  [fadianzhongduanguzhang.49af1207.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/fadianzhongduanguzhang.49af1207.png)
- 用法：状态统计卡图标
- 说明：可先直接保留，后续如果要统一线性风格再重绘

### 可复用空壳参考资源

1. 标题条 / 边框参考
- 文件：
  [section-title-normal.png](/Users/eziohelios/Dev/warehouse-forklift/web/public/img/section-title-normal.png)
  [section-title-wide.png](/Users/eziohelios/Dev/warehouse-forklift/web/public/img/section-title-wide.png)
  [border-panel-normal.png](/Users/eziohelios/Dev/warehouse-forklift/web/public/img/border-panel-normal.png)
  [border-panel-wide.png](/Users/eziohelios/Dev/warehouse-forklift/web/public/img/border-panel-wide.png)
- 用法：作为 SVG 重绘时的结构参考
- 说明：不建议直接混用到 `taizhou` 皮肤里，但非常适合作为空壳设计参考

## 必须复刻的资源清单

这些资源是 `taizhou` 风格换肤系统的核心。目标不是照搬带字 PNG，而是做出无文案、可复用的空壳版。

### 1. `screen-header-base`

- 类型：`SVG`
- 建议尺寸：`3840x194`
- 目标用途：整页顶部总标题底板
- 参考来源：
  [title-bg-new.506ebd4e.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/title-bg-new.506ebd4e.png)
  [top.7e54c69e.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/top.7e54c69e.png)
- 结构描述：
  左侧保留一团透镜型蓝青发光
  整体为深海军蓝长条
  中段靠右有一个向下内凹的弧切转折
  顶边和底边各有一条高亮蓝线
  右侧保留时间 / 天气空白区
- SVG 分层建议：
  `base-fill`
  `top-highlight`
  `bottom-highlight`
  `left-lens-glow`
  `center-curve-stroke`
  `noise-overlay`

### 2. `screen-title-center-plate`

- 类型：`SVG`
- 建议尺寸：`1880x94`
- 目标用途：总标题文字承托层
- 参考来源： [title.88d4e459.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/title.88d4e459.png)
- 结构描述：
  中部横向浅蓝雾化发光
  上沿有一层较窄的高亮扫光
  下方有轻镜像反射区
  不包含任何文字
- 说明：标题必须作为 DOM 文字放在其上层

### 3. `panel-title-strip`

- 类型：`SVG`
- 建议尺寸：
  `420x56`
  `560x56`
  `720x56`
- 目标用途：所有面板统一标题条
- 参考来源：
  [shipingailan-bg.c56b643f.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/shipingailan-bg.c56b643f.png)
  [tanpaifangxinxigailan-bg.119e2e46.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/tanpaifangxinxigailan-bg.119e2e46.png)
  [yujingtongji-bg.9999bcba.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/yujingtongji-bg.9999bcba.png)
- 结构描述：
  左侧一段青蓝渐变亮块
  后接点阵纹理区
  再接深蓝长条
  下边缘有一条蓝色辉光线
  右端不做文字，不做尖角，便于复用

### 4. `panel-frame-wide`

- 类型：`SVG`
- 建议尺寸：
  `960x402`
  `1160x396`
  `1480x396`
- 目标用途：主内容宽面板
- 参考来源：
  [shipingailan-bg.c56b643f.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/shipingailan-bg.c56b643f.png)
  [tanpaifangxinxigailan-bg.119e2e46.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/tanpaifangxinxigailan-bg.119e2e46.png)
  [yongdian&fadiantongji-bg.36373639.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/yongdian&fadiantongji-bg.36373639.png)
  [chunengzonglan-bg.ea664e7b.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/chunengzonglan-bg.ea664e7b.png)
- 结构描述：
  深蓝近黑底
  顶边高亮蓝线
  左上标题条承接区
  左下和右下各有一个小型机械角标
  内容区要保持纯净，不加业务文字
- 建议内容安全区：
  `top: 56`
  `right: 20`
  `bottom: 16`
  `left: 20`

### 5. `panel-frame-tall`

- 类型：`SVG`
- 建议尺寸：`496x656`
- 目标用途：竖向列表 / 总览面板
- 参考来源： [yujingzonglan-bg.893e331b.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/yujingzonglan-bg.893e331b.png)
- 结构描述：
  左上有斜切角
  顶部有标题条和高亮线
  底部右下有外翻斜切角
  主体是内凹深蓝底
- 建议内容安全区：
  `top: 58`
  `right: 14`
  `bottom: 18`
  `left: 14`

### 6. `panel-frame-narrow`

- 类型：`SVG`
- 建议尺寸：`356x672`
- 目标用途：左侧窄栏 KPI 卡 / 导航摘要卡
- 参考来源：
  [mianban.4458098f.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/mianban.4458098f.png)
  [cangkuquyuAndguangfuquyu-bg.4458098f.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/cangkuquyuAndguangfuquyu-bg.4458098f.png)
- 结构描述：
  左上和右下有大斜切角
  左边缘预留装饰槽位
  底边有细亮边
  主体不带文字和图标
- 建议内容安全区：
  `top: 28`
  `right: 18`
  `bottom: 22`
  `left: 40`

### 7. `collapse-left` / `collapse-right`

- 类型：`SVG`
- 目标用途：左右侧栏折叠按钮
- 参考来源：
  [close_btn_left@2x.e54d4299.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/close_btn_left@2x.e54d4299.png)
  [close_btn_right@2x.8d52b820.png](/Users/eziohelios/Dev/xtck/taizhouwarehouse/static/close_btn_right@2x.8d52b820.png)
- 结构描述：
  细长悬浮条
  中心有方向箭头或折角
  边缘有蓝色辉光

### 8. `scene-anchor-chip`

- 类型：`SVG` 或 `纯 CSS`
- 目标用途：主视觉区四周的数据锚点
- 参考来源：当前 [scene.tsx](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/scene.tsx:57) 加 `taizhou` 风格语言
- 结构描述：
  深蓝透明底
  左侧小亮点
  外边框较轻
  允许悬浮发光
- 说明：这类更适合程序化，不要做位图

## 建议保留为程序化效果的部分

以下内容不建议继续做成 PNG。

1. 面板正文背景
- 用 CSS 渐变即可

2. 细描边和高亮线
- 用 SVG stroke 或 CSS border 即可

3. 发光扫线
- 用线性渐变和 blur 即可

4. 点阵纹理
- 用 SVG pattern 即可

5. 主视觉网格、扫描线、安全区
- 当前 [bigscreen.css](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/bigscreen.css:341) 已具备程序化基础

## 资源与组件的映射表

| 组件 | 资源 | 当前落点 | 建议结果 |
| --- | --- | --- | --- |
| `ScreenBackdrop` | `bg.a064ede0.png` | `bigscreen-root` 背景 | 直接保留位图 |
| `ScreenHeader` | `screen-header-base.svg` | `layout.tsx` 头部 | 重构为通用头壳 |
| `HeaderTitlePlate` | `screen-title-center-plate.svg` | `layout.tsx` 标题区 | SVG 承托，文字真实渲染 |
| `PanelTitleBar` | `panel-title-strip.svg` | `panel.tsx` header | 新增统一标题条组件 |
| `PanelFrameWide` | `panel-frame-wide.svg` | `BigscreenPanel` | 做通用宽面板壳 |
| `PanelFrameTall` | `panel-frame-tall.svg` | `BigscreenPanel` | 做通用高面板壳 |
| `PanelFrameNarrow` | `panel-frame-narrow.svg` | `BigscreenMetricCard` / 侧栏 | 做通用窄卡壳 |
| `ListBoardShell` | 复用 `panel-frame-tall` 或 `wide` | `BigscreenScrollBoard` | 换壳，不换逻辑 |
| `MediaPanelShell` | 复用 `panel-frame-wide` | `BigscreenAutoCarousel` | 换壳，不换逻辑 |
| `SceneAnchorChip` | SVG / CSS | `scene.tsx` | 程序化绘制 |

## 分阶段实施顺序

### 第一阶段

- 新建 `skins/` 目录和皮肤协议
- 抽离 `tokens.css`
- 接入 `ScreenBackdrop`
- 接入 `ScreenHeader`
- 接入 `PanelTitleBar`

目标：

- 首页第一眼气质完成切换

### 第二阶段

- 实现 `PanelFrameWide`
- 实现 `PanelFrameTall`
- 实现 `PanelFrameNarrow`
- 替换 `BigscreenPanel` 默认壳

目标：

- 四个页面的大面板风格统一

### 第三阶段

- 替换 `BigscreenMetricCard`
- 替换 `BigscreenInfoCard`
- 替换 `BigscreenScrollBoard`
- 替换 `BigscreenAutoCarousel`

目标：

- 内容壳与面板壳风格一致

### 第四阶段

- 补充 `collapse-left/right`
- 调整 `scene-anchor-chip`
- 细化发光、点阵、边角、切角装饰

目标：

- 进入精修阶段

## 验收标准

完成换肤系统后，应满足：

1. 页面业务 JSX 基本不需要改标题和数据结构
2. 不同页面可以共享同一套 `PanelFrame`
3. 标题文字全部使用真实 DOM，不再烘入图片
4. 至少支持一套 `taizhou` 皮肤和一套默认 fallback 皮肤
5. 页面仍保持现有 `1920x1080` 舞台缩放逻辑
6. 未来新增皮肤时，只需新增 `tokens.css + assets + registry`

## 本阶段推荐的最小交付包

首批必须交付以下资源：

- `screen-header-base.svg`
- `screen-title-center-plate.svg`
- `panel-title-strip.svg`
- `panel-frame-wide.svg`
- `panel-frame-tall.svg`
- `panel-frame-narrow.svg`
- `collapse-left.svg`
- `collapse-right.svg`
- `bg.a064ede0.png` 直接作为 `taizhou` 皮肤背景保留

首批必须改造以下代码：

- [layout.tsx](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/layout.tsx:58)
- [panel.tsx](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/panel.tsx:6)
- [bigscreen.css](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/bigscreen.css:45)
- [motion.tsx](/Users/eziohelios/Dev/litestar-fullstack/src/js/web/src/components/bigscreen/motion.tsx:61)

## 后续动作

基于本文，下一步可以直接开展：

1. 搭建 `skins/registry.ts` 和 `taizhou` 皮肤目录
2. 先画 `screen-header-base.svg` 与 `panel-title-strip.svg`
3. 让 `layout.tsx` 和 `panel.tsx` 切到新皮肤协议
4. 再逐步替换 `MetricCard / ScrollBoard / Carousel` 的壳
