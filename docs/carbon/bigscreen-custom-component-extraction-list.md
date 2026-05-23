# Bigscreen Custom Component Extraction List

本清单记录从 `xtck/taizhouwarehouse/static` 提取出的可复用业务资源，以及在当前 `bigscreen` 中对应的定制组件落点。

## 已提取并已接入

### `EnergyAssetOverviewPanel`
- 资源
  - `yongdiantu.a4bf1067.png`
  - `fadiantu.56d2c826.png`
- 适用场景
  - 光伏发电
  - 用电 / 发电总览
- 当前落点
  - `huayi` 页“光伏发电”
- 替代对象
  - `BigscreenMetricCard`
  - 部分 `BigscreenInfoCard`

### `TerminalStatusTriplet`
- 资源
  - `yongdianzhongduanzongshu.9f537936.png`
  - `yongdianzhongduanzaixian.791eb30d.png`
  - `yongdianzhongduanguzhang.b9d3e33b.png`
  - `fadianzhongduanzongshu.636bd929.png`
  - `fadianzhongduanzaixian.a5bcee55.png`
  - `fadianzhongduanguzhang.49af1207.png`
- 适用场景
  - 总量 / 在线 / 异常三态终端状态
  - 电表 / 监测点 / 终端在线情况
- 当前落点
  - `power` 页“运行指标”
  - `huayi` 页“设备状态”
- 替代对象
  - `BigscreenMetricCard`
  - 普通四宫格状态卡

### `StorageOverviewPanel`
- 资源
  - `chunengzonglan-bg.ea664e7b.png`
- 适用场景
  - 储能概览
  - 数字翻牌式状态展示
- 当前落点
  - `huayi` 页“储能系统”
- 替代对象
  - 纯文本 KPI 卡

## 已提取但尚未接入

### `MonitorPointStatusPanel`
- 资源
  - `jiancedianweizaixiantongji-bg.54f1fb48.png`
- 适用场景
  - 监测点 / 电表 / 终端在线统计
- 推荐替代
  - `BigscreenPieChart`
  - `BigscreenBarChart`
- 推荐页面
  - `power`

### `WarehousePvAreaPanel`
- 资源
  - `cangkuquyuAndguangfuquyu-bg.4458098f.png`
- 适用场景
  - 仓库区域 / 光伏区域 tab 切换统计
  - 窄侧栏多指标概览
- 推荐替代
  - 侧栏 KPI 纵向堆叠
- 推荐页面
  - `overview`
  - `power`

### `PowerGenerationStatsPanel`
- 资源
  - `yongdian&fadiantongji-bg.36373639.png`
- 适用场景
  - 用电 / 发电趋势统计
- 推荐替代
  - `BigscreenLineChart`
  - `BigscreenBarChart`
- 推荐页面
  - `power`

### `EnergyGenerationOverviewPanel`
- 资源
  - `yongdian&fadianzonglan-bg.7ba9a31f.png`
  - `yongdianAndfadianzonglan-bg.3b15d926.png`
- 适用场景
  - 左图示 + 右指标说明的能源总览
- 推荐替代
  - `BigscreenInfoCard`
  - `BigscreenPieChart`
- 推荐页面
  - `power`
  - `overview`

## 当前实现原则

- 外层仍保持统一 `BigscreenPanel`，不再引入第二层 panel 壳。
- 提取的资源优先用于业务图示、终端状态图标、数字翻牌样式。
- 原始大面积带标题边框壳图仅作为后续专用业务组件候选，暂不在通用 panel 内嵌套使用。
