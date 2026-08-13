# 能碳平台 V2 设计系统

本文定义登录后、非大屏后台页面的主题与业务域实现规范。公共认证页与 `/bigscreen/*` 不使用本规范的后台壳层。

## 1. 运行时模型

主题偏好与实际主题分开保存：

```ts
type ThemePreference = "system" | "light" | "dark"
type ResolvedTheme = "light" | "dark"
type DesignDomain = "neutral" | "energy" | "carbon"
```

- 新存储键为 `app-theme-preference`；首次访问为 `system`。
- 旧 `theme=light|dark` 会自动迁移。
- `index.html` 中的同步初始化脚本必须保留，用于避免首屏主题闪烁。
- `ThemeProvider` 负责监听系统主题变化、持久化用户偏好并设置根节点主题属性。
- `AppLayout` 只在普通后台页面设置业务域；公共页面及大屏不得遗留 `data-admin-domain`。

## 2. Token 分层

设计 token 统一维护在 `src/js/web/src/styles.css`，保留 HSL 空间分量格式以兼容 Tailwind v4 的透明度修饰符。

1. 基础层：后台画布、面板、边界、正文、弱文本、阴影。
2. 语义层：`background`、`foreground`、`primary`、`accent`、`ring` 等兼容别名。
3. 业务域层：`domain-accent`、`domain-accent-soft`、`domain-glow`、`domain-chart-*`。
4. 组件层：`admin-panel`、`admin-filter-bar`、`admin-metric-tile`、`admin-chart-frame` 等。

业务域基准色：

| 业务域 | 浅色 | 深色 |
|---|---|---|
| energy | `#007EA8` | `#22D3EE` |
| carbon | `#0A7D5E` | `#34D399` |
| neutral | `#3E6873` | `#77B8C4` |

后台采用“电气未来感”色卡：浅色模式使用冷白、钢蓝灰和高纯度业务信号色；深色模式使用蓝黑画布、分层青黑面板与高亮电气青/数字绿。高亮色只用于当前状态、关键数据、主操作和图表焦点，不得扩散为大面积霓虹表面。

浅色模式使用 `#F6FAFC` 应用壳层、`#F1F7FA` 页面画布和 `#FFFFFF` 内容面板。提亮应集中在画布层，侧边栏与面板不得同步漂白，以保留稳定的空间分区。

成功、警告、危险、信息使用独立的 `status-*` token。碳绿不得表达成功，能源蓝不得表达普通信息状态。

## 3. 路由业务域

所有映射集中在 `src/js/web/src/lib/design-domain.tsx`，禁止页面自行解析路径。

- `energy`：`/energy/*`、`/microgrid/*`、监测告警和点位监测；`/energy/budget` 除外。
- `carbon`：`/carbon/*`、`/carbon-mgmt/*`、因子、质量核查、能碳预算。
- `neutral`：工作台、组织与活动台账、设备基础数据、权限、任务、团队和账号。

中性页面需要局部切换时使用：

```tsx
<AdminDomainScope domain="energy">...</AdminDomainScope>
<AdminDomainScope domain="carbon">...</AdminDomainScope>
```

作用域允许嵌套；内部作用域覆盖外部作用域。

## 4. 共享组件

- `ProductBrand` 是后台唯一品牌头，读取 `displayName`、`shortName` 和可选 `brandMarkUrl`。
- `Button` 的默认动作继承业务域；`destructive` 始终使用危险红。
- `Badge` 的 `success / warning / info / destructive` 只使用状态 token。
- `AdminPanel emphasis` 支持 `default / accent / elevated / inset`。
- `MetricTile tone="domain"` 用于业务主指标；状态指标使用 `success / warning / danger / info`。
- 筛选行使用 `AdminFilterBar`；折叠态最多显示四个主要字段，搜索通常置于首位。
- 主 Tabs 使用底部分隔线和当前项业务域色，不使用完整外框；筛选栏使用纯色底分组，不叠加外框或容器投影。
- 筛选栏内的输入、下拉和按钮保留自身边界与焦点状态，容器层与控件层不得同时使用同重量描边。
- 表格、弹窗、抽屉、输入框和骨架屏的边界、焦点、悬停、禁用状态由共享组件控制。

### 4.1 后台侧边栏

- 侧边栏始终使用中性冷灰或深石墨色，不随能源、碳业务域整体染色。
- 展开态只有当前叶子菜单使用业务域软底色与文字色；展开父级只通过字重表达上下文，不显示第二个激活色块。
- 禁止使用左侧装饰条、子菜单竖线、渐变、辉光和投影作为导航选中信号。
- 折叠态无法显示叶子菜单时，允许当前父级图标继承对应业务域色，且必须仍是侧栏内唯一的业务域信号。
- 品牌区仅保留品牌标识和产品名称；不得增加状态灯、英文口号或装饰性信号线。

动效时长控制在 160–240ms，只对 `transform` 与 `opacity` 做页面动效。`prefers-reduced-motion` 下必须关闭 CSS 动效与 ECharts 动画。

## 5. 图表

页面不得直接构造视觉样式或定义局部调色板。调用顺序固定为：

```tsx
const chartTheme = useAdminChartTheme()
const option = createTrendChartOption(chartTheme, points, lines)
```

跨域图表可显式传入 `useAdminChartTheme("energy")` 或 `useAdminChartTheme("carbon")`。所有 builder 的第一个参数必须是 `AdminChartTheme`，由 TypeScript 保证调用点不会遗漏主题。

`getAdminChartTheme(domain, mode)` 统一提供文字、轴线、网格、Tooltip、状态色、业务语义色与序列色。成本为金色、告警为琥珀色、危险为红色；混合图表显式使用 `energy` 与 `carbon` color key。化石燃料、热量、成本和风险等具有天然业务联想的系列可使用克制的暖色，不得为了色谱整齐强制改成冷色。

桑基图的流程节点使用独立 `flowColors`，采用蓝、绿、紫、青和钢灰冷色谱；损失和异常仍显式使用危险红。该色谱不得扩散为全部图表的默认序列色。

## 6. 禁止事项

- 页面级硬编码主题色、阴影、Tooltip、ECharts 轴线和颜色数组。
- 后台画布、侧栏、面板、筛选栏、Tabs、指标卡和 SCADA 设备面板不得使用装饰性线性渐变；层级使用纯色明度差、边界和留白表达。
- 图表面积透明衰减、骨架屏加载扫光及带有明确数据含义的流向着色不属于装饰性渐变，但不得扩散到容器表面。
- 用碳绿表示成功，或用能源蓝表示普通信息状态。
- 在业务页裸用 `Card` 堆叠通用容器。
- 霓虹辉光、营销 hero、绿色环保海报风和高饱和渐变。
- 为单一路由创建独立皮肤或绕开共享组件。
- 将 React Query Devtools 打入生产运行路径。

提交前执行 `bun run test`、`bun run audit:admin-visual`、`bun run lint` 与 `bun run build`。视觉验收还需覆盖明暗模式、1440×900、1280×720、移动侧栏、键盘焦点和表格内部滚动。
