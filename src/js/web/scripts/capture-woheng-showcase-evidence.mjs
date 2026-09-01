import { chromium } from "@playwright/test"
import { execFileSync } from "node:child_process"
import { createHash } from "node:crypto"
import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:18101"
const username = process.env.E2E_ADMIN_EMAIL
const password = process.env.E2E_ADMIN_PASSWORD
const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../..")
const outputDir = path.resolve(process.env.EVIDENCE_OUTPUT_DIR ?? path.join(repositoryRoot, "outputs/woheng-showcase-evidence"))
const screenshotDir = path.join(outputDir, "screenshots")
const manifestPath = path.join(outputDir, "evidence-manifest.json")
const planPath = path.join(outputDir, "screenshot-plan.json")
const indexPath = path.join(outputDir, "evidence-index.json")

const viewport = { width: 1440, height: 900 }
const brandProfile = {
  displayName: process.env.EVIDENCE_BRAND_NAME ?? "沃衡汽车能碳管理平台",
  shortName: process.env.EVIDENCE_BRAND_SHORT_NAME ?? "沃衡汽车",
}
const forbiddenBrandTexts = (process.env.EVIDENCE_FORBIDDEN_BRANDS ?? "中汽信科,奇瑞,Chery,安方,祥泰,华东绿色仓储")
  .split(",")
  .map((item) => item.trim())
  .filter(Boolean)
const badStatusPattern = /^(401|403|5\d\d)$/
const loadingMarkers = ["正在加载", "正在预检", "loading", "Loading"]
const errorMarkers = ["加载失败", "数据加载失败", "权限不足", "Internal Server Error"]
const genericEmptyMarkers = ["暂无数据", "暂无记录", "暂无可用", "等待工作簿预检"]
const chartReadyTimeoutMs = Number(process.env.EVIDENCE_CHART_READY_TIMEOUT_MS ?? "20000")
const chartStableFrames = Number(process.env.EVIDENCE_CHART_STABLE_FRAMES ?? "4")
const chartSettledDelayMs = Number(process.env.EVIDENCE_CHART_SETTLED_DELAY_MS ?? "450")
const screenshotCss = `
  [data-sonner-toast],
  .tsqd-parent-container,
  [class*="tsqd-"],
  [aria-label*="React Query" i],
  [aria-label*="TanStack Query" i] {
    display: none !important;
    visibility: hidden !important;
  }
`
const captureOnly = new Set(
  (process.env.EVIDENCE_ONLY ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean),
)

const tenants = {
  huzhou: {
    slug: "woheng-huzhou-production-base",
    nameHint: "沃衡汽车湖州生产基地",
    role: "零部件制造、经营活动台账、非电数据导入、组织碳核算、报告导出和减排绩效样板",
  },
  taizhou: {
    slug: "woheng-taizhou-production-base",
    nameHint: "沃衡汽车泰州生产基地",
    role: "整车装配、厂内物流、MQTT电表接入、分区分项用能监测和告警闭环样板",
  },
}

const evidenceDefinitions = [
  shot("EV-WH-001", "首页工作台与功能入口", "/home", "huzhou", ["工作台", "能源运营", "碳排放管理", "态势大屏"], "A", "平台开场"),
  shot("EV-WH-002", "生产基地介绍大屏", "/bigscreen/intro", "huzhou", ["企业图集", "企业信息摘要", "运营项目轮播"], "C", "大屏展示"),
  shot("EV-WH-003", "能碳态势总览大屏", "/bigscreen/overview", "huzhou", ["能耗主指标", "碳排主指标", "月度经营趋势", "区域能耗速览"], "A", "大屏展示"),
  shot("EV-WH-004", "碳排专题大屏", "/bigscreen/carbon", "huzhou", ["碳排指标", "范围对比", "贡献构成", "碳排预警滚动榜"], "A", "大屏展示"),
  shot("EV-WH-005", "电力专题大屏", "/bigscreen/power", "huzhou", ["运行指标", "区域电量流图", "账期电量趋势", "用电排行"], "B", "大屏展示", { allowPartial: true }),

  shot("EV-WH-006", "泰州设备主数据与采集协议配置", "/data/terminals", "taizhou", ["编辑设备", "采集标识", "采集协议", "在线状态"], "A", "数据维护与治理", {
    action: openFirstDeviceEditor,
  }),
  shot("EV-WH-007", "泰州设备测点配置", "/data/device-points", "taizhou", ["设备测点工作台", "筛选树", "测点"], "A", "数据维护与治理"),
  shot("EV-WH-008", "泰州电表电量采集结果", "/data/meter", "taizhou", ["电表电量", "最新采集", "电表数量", "采样数", "用电趋势"], "A", "数据维护与治理"),
  shot("EV-WH-009", "泰州点位监测与来源追溯", "/data/point-monitoring", "taizhou", ["点位监测", "总点位", "点位列表", "最近读数", "来源追溯"], "A", "数据维护与治理", {
    action: prepareTaizhouPointMonitoringTrend,
    rejectTexts: ["暂无时序数据"],
  }),
  shot("EV-WH-010", "湖州区域主数据", "/data/monitor-area", "huzhou", ["区域主数据工作台", "区域树", "基础信息", "本区域设备"], "A", "数据维护与治理"),
  shot("EV-WH-011", "湖州设备测点主数据", "/data/device-points", "huzhou", ["设备测点工作台", "筛选树", "测点"], "A", "数据维护与治理", { allowPartial: true }),
  shot("EV-WH-012", "非电活动数据导入入口", "/carbon-mgmt/import", "huzhou", ["活动数据导入", "盘查期", "组织", "活动分类", "下载分类模板"], "B", "数据维护与治理", {
    allowPartial: true,
    allowedEmptyMarkers: ["等待工作簿预检"],
  }),
  shot("EV-WH-013", "非电活动数据预检结果", "/carbon-mgmt/import", "huzhou", ["活动数据导入", "活动数据预览", "区域设备归集", "方法与参数", "证据覆盖"], "A", "数据维护与治理", {
    action: uploadAndPreviewGhgWorkbook,
    rejectTexts: ["预检未通过"],
  }),
  shot("EV-WH-014", "温室气体活动台账", "/carbon-mgmt/activities", "huzhou", ["温室气体活动台账", "活动记录", "记录 / 活动"], "A", "数据维护与治理"),
  shot("EV-WH-015", "监测告警事件", "/data/alarm-events", "huzhou", ["告警", "状态"], "B", "数据维护与治理", { allowPartial: true }),
  shot("EV-WH-016", "系统审计留痕", "/admin/audit", "huzhou", ["审计", "用户", "操作"], "B", "数据维护与治理", { allowPartial: true }),

  shot("EV-WH-017", "官方排放因子库概览", "/carbon-mgmt/factors", "huzhou", ["排放因子库", "官方库", "分类节点", "原始记录", "校验状态"], "A", "因子维护与计算"),
  shot("EV-WH-018", "官方因子分类与原始记录", "/carbon-mgmt/factors", "huzhou", ["分类树", "官方原始因子", "因子名称"], "A", "因子维护与计算", {
    allowPartial: true,
  }),
  shot("EV-WH-019", "计算因子库", "/carbon-mgmt/calculation-factors", "huzhou", ["计算因子库", "因子列表", "因子值", "因子单位", "导入方式"], "A", "因子维护与计算"),
  shot("EV-WH-020", "活动数据方法与参数解析", "/carbon-mgmt/import", "huzhou", ["方法与参数解析", "参数集", "采用值", "来源 / 版本", "标准 / 条款"], "A", "因子维护与计算", {
    action: async (tools) => {
      await uploadAndPreviewGhgWorkbook(tools)
      await tools.page.getByRole("tab", { name: "方法与参数" }).click()
      await tools.page.getByText("方法与参数解析", { exact: true }).waitFor({ timeout: 20_000 })
    },
  }),

  shot("EV-WH-021", "能耗查询", "/energy/consumption", "huzhou", ["能耗查询", "记录数", "能源品种"], "A", "能源管理"),
  shot("EV-WH-022", "能源消费量和强度计算", "/energy/intensity", "huzhou", ["能源消费量和强度计算", "综合能耗", "能源品种汇总"], "A", "能源管理"),
  shot("EV-WH-023", "用能分析", "/energy/analysis", "huzhou", ["用能分析", "总用电量", "用能系统"], "A", "能源管理"),
  shot("EV-WH-024", "能效对标", "/energy/benchmark", "huzhou", ["能效对标", "设备/工序对标", "对标对象"], "A", "能源管理", {
    action: async ({ page }) => {
      await page.getByRole("tab", { name: "设备/工序对标" }).click()
      await page.getByText("对标对象", { exact: true }).waitFor({ timeout: 20_000 })
    },
  }),
  shot("EV-WH-025", "能流分析", "/energy/flow", "huzhou", ["能流分析", "计量用电", "分项用电", "关键链路贡献"], "A", "能源管理"),
  shot("EV-WH-026", "能效平衡与优化", "/energy/balance", "huzhou", ["能效平衡与优化", "能量平衡表", "来源类型", "来源"], "A", "能源管理"),
  shot("EV-WH-027", "用能与碳排放预算管理", "/energy/budget", "huzhou", ["能碳预算", "年度目标", "月度预算"], "A", "能源管理", { allowPartial: true }),

  shot("EV-WH-028", "组织碳排放总览", "/carbon/organization/overview", "huzhou", ["组织碳总览", "Scope 1", "Scope 2", "Scope 3", "报告期排放趋势"], "A", "组织碳与ISO 14064"),
  shot("EV-WH-029", "组织边界与核算边界", "/carbon/organization/boundary", "huzhou", ["核算边界", "边界口径", "区域与设备边界", "ISO 14064-1 六类别"], "A", "组织碳与ISO 14064"),
  shot("EV-WH-030", "排放清单与报告台账", "/carbon/organization/inventory", "huzhou", ["碳盘查", "核算准备检查", "盘查报告台账"], "A", "组织碳与ISO 14064"),
  shot("EV-WH-031", "排放结果明细与核算公式", "/carbon/organization/records", "huzhou", ["碳排放查询", "查询结果", "排放结果明细", "排放源帕累托分析"], "A", "组织碳与ISO 14064"),
  shot("EV-WH-032", "排放明细详情：活动与因子", "/carbon/organization/records", "huzhou", ["活动与核算公式", "参数与因子", "区域与设备归集", "证据文件"], "A", "组织碳与ISO 14064", {
    action: openFirstOrganizationCarbonRecord,
  }),
  shot("EV-WH-033", "组织碳流向与结构分析", "/carbon/organization/flow", "huzhou", ["碳流分析", "组织边界至区域设备碳流", "主要排放路径", "核算异常"], "B", "组织碳与ISO 14064"),
  shot("EV-WH-034", "碳核查支撑工作台", "/carbon/verification", "huzhou", ["碳核查支撑", "核查项目"], "A", "组织碳与ISO 14064"),
  shot("EV-WH-035", "产品碳足迹核算", "/carbon/product-footprint", "huzhou", ["产品碳足迹核算", "产品与研究", "研究数", "已核算", "活动数据", "核算结果"], "A", "绿色工厂评分项", {
    focus: "产品碳足迹研究、生命周期活动数据、供应链引用数据和核算结果",
    rejectTexts: ["暂无产品碳足迹研究", "暂无已核算产品排行", "暂无总分结构数据"],
  }),
  shot("EV-WH-036", "供应链碳管理", "/carbon/supply-chain", "huzhou", ["供应链碳管理", "供应商档案", "供应商", "填报任务", "数据审核", "供应链分析"], "A", "绿色工厂评分项", {
    focus: "供应商档案、场站、填报任务、审核数据、披露记录和供应链分析",
    rejectTexts: ["暂无供应商", "暂无任务", "暂无场站", "暂无供应链排行数据"],
  }),

  shot("EV-WH-037", "核查凭证与材料", "/carbon/verification", "huzhou", ["证据资料", "凭证清单", "凭证数", "下载"], "A", "其他碳管理能力", {
    allowedEmptyMarkers: ["暂无数据"],
    preserveScroll: true,
    action: async ({ page }) => {
      await ensureVerificationProjectSelected(page)
      await page.getByRole("tab", { name: "证据资料", exact: true }).click()
      await page.getByText("凭证清单", { exact: true }).waitFor({ timeout: 20_000 })
      const evidenceRow = page.locator("tbody tr").filter({ hasNotText: "暂无" }).first()
      await evidenceRow.waitFor({ state: "visible", timeout: 20_000 })
      await evidenceRow.scrollIntoViewIfNeeded()
    },
  }),
  shot("EV-WH-038", "报告导出", "/carbon/verification", "huzhou", ["报告与材料", "报告导出", "导出记录"], "A", "其他碳管理能力", {
    action: async ({ page }) => {
      await ensureVerificationProjectSelected(page)
      await page.getByRole("tab", { name: "报告与材料", exact: true }).click()
      await page.getByRole("tab", { name: "报告导出", exact: true }).click()
    },
  }),

  shot("EV-WH-040", "公开碳价行情", "/carbon/assets/market", "huzhou", ["碳市场行情", "行情记录", "最新价格", "月K线与成交量"], "B", "碳资产与公开碳价模拟", { allowPartial: true }),
  shot("EV-WH-041", "碳价模拟测算", "/carbon/assets/simulation", "huzhou", ["碳成本测算", "测算情景", "成本情景", "冻结测算结果", "预计成本"], "B", "碳资产与公开碳价模拟", { allowPartial: true }),
  shot("EV-WH-042", "减排项目绩效跟踪", "/carbon/reduction/projects", "huzhou", ["减排项目", "锁定基准线", "实际减排计算", "基准排放", "项目排放", "实际减排"], "A", "减排绩效与公开碳价模拟", {
    focus: "减排项目清单、锁定基准线、项目排放和实际减排计算结果",
    rejectTexts: ["暂无数据", "暂无记录"],
  }),

  shot("EV-WH-043", "ISO 14064 类别1固定燃烧分类填报", "/carbon-mgmt/category/1.1", "huzhou", ["1.1 固定燃烧", "类别1", "活动记录", "记录 / 活动", "活动量", "质量", "归集"], "A", "碳数据分类填报补充", {
    focus: "类别1固定燃烧分类台账的筛选区、指标卡和活动记录表",
    rejectTexts: ["当前分类暂无活动记录", "该分类尚未配置可执行核算方法"],
  }),
  shot("EV-WH-044", "ISO 14064 类别2购入电力分类填报", "/carbon-mgmt/category/2.1", "huzhou", ["2.1 购入电力", "类别2", "活动记录", "记录 / 活动", "活动量", "质量", "归集"], "A", "碳数据分类填报补充", {
    focus: "类别2购入电力分类台账的筛选区、指标卡和活动记录表",
    rejectTexts: ["当前分类暂无活动记录", "该分类尚未配置可执行核算方法"],
  }),
  shot("EV-WH-045", "ISO 14064 类别3员工通勤分类填报", "/carbon-mgmt/category/3.3", "huzhou", ["3.3 员工通勤", "类别3", "活动记录", "记录 / 活动", "活动量", "质量", "归集"], "A", "碳数据分类填报补充", {
    focus: "类别3员工通勤分类台账的筛选区、指标卡和活动记录表",
    rejectTexts: ["当前分类暂无活动记录", "该分类尚未配置可执行核算方法"],
  }),
  shot("EV-WH-046", "ISO 14064 类别4采购商品分类填报", "/carbon-mgmt/category/4.1", "huzhou", ["4.1 采购商品与服务", "类别4", "活动记录", "记录 / 活动", "活动量", "质量", "归集"], "B", "碳数据分类填报补充", {
    allowPartial: true,
    focus: "类别4采购商品与服务分类台账的筛选区、指标卡和活动记录表",
    rejectTexts: ["当前分类暂无活动记录"],
  }),
  shot("EV-WH-047", "ISO 14064 类别5售出产品加工分类填报", "/carbon-mgmt/category/5.1", "huzhou", ["5.1 售出产品加工", "类别5", "活动记录", "记录 / 活动", "活动量", "质量", "归集"], "B", "碳数据分类填报补充", {
    allowPartial: true,
    focus: "类别5售出产品加工分类台账的筛选区、指标卡和活动记录表",
    rejectTexts: ["当前分类暂无活动记录"],
  }),
  shot("EV-WH-048", "ISO 14064 类别6其他间接排放分类填报", "/carbon-mgmt/category/6.1", "huzhou", ["6.1 其他经确认的间接排放", "类别6", "活动记录", "记录 / 活动", "活动量", "质量", "归集"], "A", "碳数据分类填报补充", {
    focus: "类别6其他间接排放分类台账的筛选区、指标卡和活动记录表",
    rejectTexts: ["当前分类暂无活动记录", "该分类尚未配置可执行核算方法"],
  }),

  shot("EV-WH-049", "数据采集与监测中心", "/energy-carbon/monitor", "huzhou", ["数据采集与监测", "运行概况", "区域风险分布", "设备近时段测点趋势", "设备工作列表", "设备编码", "协议"], "A", "监测告警补充", {
    focus: "监测中心运行概况、区域风险、设备列表和设备详情",
    rejectTexts: ["当前筛选条件下没有设备。", "选择一台设备", "暂无趋势数据"],
  }),
  shot("EV-WH-050", "碳告警与预警中心", "/energy-carbon/alerts", "huzhou", ["碳告警与预警", "总告警", "告警新增与处理趋势", "来源分布", "告警列表", "告警类型", "风险等级"], "A", "监测告警补充", {
    focus: "告警中心指标、趋势图、告警列表和处理详情",
    rejectTexts: ["当前筛选条件下没有告警。"],
  }),
  shot("EV-WH-051", "预警规则配置台账", "/data/alarm-rules", "huzhou", ["预警规则", "规则名称", "告警名称", "事件类型", "来源表/视图"], "A", "监测告警补充", {
    focus: "预警规则列表、规则名称、事件类型和来源表字段",
  }),
  shot("EV-WH-052", "视频监控预警事件", "/data/video-alarm-events", "huzhou", ["视频监控预警事件", "事件列表", "类型", "说明", "时间", "状态", "处理"], "A", "监测告警补充", {
    focus: "视频预警事件列表和处理状态",
    rejectTexts: ["暂无事件"],
  }),

  shot("EV-WH-053", "员工通勤经营活动台账", "/data/commute", "huzhou", ["员工通勤", "员工通勤列表", "姓名 / 标识", "通勤类别", "车辆动力类型", "平均单次里程"], "A", "经营活动台账补充", {
    focus: "员工通勤列表、通勤类别、车辆动力类型和里程/能耗字段",
  }),
  shot("EV-WH-054", "入库经营活动台账", "/data/inbound", "huzhou", ["入库管理", "入库管理台账", "入库单号", "供应商", "物料编号", "数量", "金额"], "A", "经营活动台账补充", {
    focus: "入库业务单据台账和物料、数量、金额字段",
  }),
  shot("EV-WH-055", "出库经营活动台账", "/data/outbound", "huzhou", ["出库管理", "出库管理台账", "出库单号", "项目名称", "物料编码", "数量", "金额"], "A", "经营活动台账补充", {
    focus: "出库业务单据台账和项目、物料、数量、金额字段",
  }),
  shot("EV-WH-056", "产品价格经营活动台账", "/data/product-prices", "huzhou", ["产品价格", "产品编码", "价格口径", "单价", "币种", "生效日期"], "A", "经营活动台账补充", {
    focus: "产品价格台账和价格口径、单价、生效日期字段",
  }),
  shot("EV-WH-057", "产品批次产量经营活动台账", "/data/production-output", "huzhou", ["产品批次产量", "产品编码", "产品名称", "批次", "产量", "产线"], "A", "经营活动台账补充", {
    focus: "产品批次产量台账、批次、产量和产线字段",
  }),
  shot("EV-WH-058", "产品产线关联台账", "/data/product-resource-bindings", "huzhou", ["产品产线关联", "产品编码", "工作中心", "产线", "关联类型", "置信等级"], "A", "经营活动台账补充", {
    focus: "产品与产线/设备绑定关系及置信等级字段",
  }),
]

function shot(evidenceId, title, route, tenantKey, requiredTexts, expectedEvidenceLevel, section, options = {}) {
  const slug = slugify(title)
  return {
    evidenceId,
    title,
    route,
    tenantKey,
    tenantSlug: tenants[tenantKey].slug,
    tenantNameHint: tenants[tenantKey].nameHint,
    section,
    filename: `${evidenceId}-${slug}.png`,
    requiredTexts,
    expectedEvidenceLevel,
    focus: options.focus ?? "页面标题、筛选条件、指标卡、图表或表格的首屏业务数据",
    timing: options.timing ?? "页面加载完成且图表稳定后",
    viewport: "desktop-wide",
    successSignal: options.successSignal ?? `可见 ${requiredTexts.join("、")}，且无登录页、报错页、空数据页、加载态。`,
    allowPartial: options.allowPartial ?? false,
    allowedEmptyMarkers: options.allowedEmptyMarkers ?? [],
    rejectTexts: options.rejectTexts ?? [],
    preserveScroll: options.preserveScroll ?? false,
    action: options.action,
  }
}

function slugify(value) {
  return value
    .normalize("NFKD")
    .replace(/[^\p{Letter}\p{Number}]+/gu, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase()
}

await fs.mkdir(screenshotDir, { recursive: true })
await writePlan()

if (process.env.EVIDENCE_PLAN_ONLY === "1") {
  console.log(`[plan:written] ${planPath}`)
  process.exit(0)
}

if (!username || !password) {
  throw new Error("E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD are required. Do not use expired storageState for this capture.")
}

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport, deviceScaleFactor: 1, acceptDownloads: true })
const page = await context.newPage()
page.setDefaultTimeout(20_000)
page.setDefaultNavigationTimeout(40_000)

let activeTeamId = null
let activeTeam = null
let activeUser = null
let activeEvidence = null
const teamCache = new Map()
const consoleErrors = []
const apiFailures = []

await context.route("**/api/**", async (route) => {
  const headers = { ...route.request().headers() }
  if (activeTeamId) headers["x-team-id"] = activeTeamId
  await route.continue({ headers, url: rewriteEvidenceApiUrl(route.request().url()) })
})

page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push({ text: message.text(), at: new Date().toISOString() })
})
page.on("response", (response) => {
  const url = response.url()
  if (!url.includes("/api/")) return
  const status = response.status()
  if (badStatusPattern.test(String(status))) {
    apiFailures.push({
      status,
      url: url.replace(baseURL, ""),
      method: response.request().method(),
      at: new Date().toISOString(),
    })
  }
})

try {
  activeUser = await ensureAuthenticated()
  apiFailures.length = 0
  consoleErrors.length = 0

  const previousManifest = await readExistingManifest()
  const cases = captureOnly.size > 0 ? [...(previousManifest.cases ?? [])] : []
  const rejectedCandidates = captureOnly.size > 0 ? [...(previousManifest.rejectedCandidates ?? [])] : []
  for (const definition of evidenceDefinitions) {
    if (captureOnly.size > 0 && !captureOnly.has(definition.evidenceId)) continue
    console.log(`[evidence:start] ${definition.evidenceId} ${definition.tenantSlug} ${definition.route}`)
    await selectTenant(definition)
    const result = await captureEvidence(definition)
    console.log(`[evidence:${result.status}] ${definition.evidenceId}${result.failureReason ? ` ${result.failureReason}` : ""}`)
    removeByEvidenceId(cases, result.evidenceId)
    removeByEvidenceId(rejectedCandidates, result.evidenceId)
    if (result.status === "有效" || result.status === "部分有效") cases.push(result)
    else rejectedCandidates.push(result)
  }

  const manifest = {
    title: "沃衡汽车能碳管理平台统一演示截图证据清单",
    updatedAt: new Date().toISOString(),
    environment: {
      baseURL,
      loginMode: "profile-check-then-form-login",
      user: maskEmail(username),
      viewport: `${viewport.width}x${viewport.height}`,
      brandProfile,
      forbiddenBrandTexts,
      tenants,
    },
    cases: cases.toSorted((left, right) => left.evidenceId.localeCompare(right.evidenceId)),
    rejectedCandidates: rejectedCandidates.toSorted((left, right) => left.evidenceId.localeCompare(right.evidenceId)),
  }
  await fs.writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`)
  await fs.writeFile(path.join(outputDir, "api-failures.json"), `${JSON.stringify(apiFailures, null, 2)}\n`)
  await fs.writeFile(path.join(outputDir, "browser-console-errors.json"), `${JSON.stringify(consoleErrors, null, 2)}\n`)
  await writeIndex(manifest)
} finally {
  await browser.close()
}

async function writePlan() {
  const plan = {
    title: "沃衡汽车能碳管理平台统一演示截图需求列表",
    updatedAt: new Date().toISOString(),
    scope: "从首页/大屏出发，重点说明MQTT电表接入、非电活动数据导入、碳因子维护、ISO 14064组织碳核算、工信部能碳管理平台12项能力，以及公开碳价模拟。",
    numbering: "EV-WH-001...",
    outputDir,
    screenshotDir,
    brandProfile,
    forbiddenBrandTexts,
    acceptanceRules: [
      "每张截图运行前验证登录态，失败自动表单登录刷新会话。",
      `截图前校验项目品牌态：后台页面应可见“${brandProfile.displayName}”，且不得出现 ${forbiddenBrandTexts.join("、") || "旧品牌文案"}。`,
      "按截图定义切换湖州或泰州租户，并通过 X-Team-Id 调用关键接口。",
      "禁止交付登录页、空页面、报错页、半加载页和纯入口页。",
      "截图前检查 401/403/5xx、可见 loading/skeleton、空数据文案和必须可见内容。",
      "交互类功能截结果态，例如导入预检结果、因子参数解析、报告导出页签。",
    ],
    sections: groupDefinitions().map(([section, items]) => ({
      section,
      items: items.map((item) => ({
        evidenceId: item.evidenceId,
        title: item.title,
        route: item.route,
        tenantSlug: item.tenantSlug,
        tenantNameHint: item.tenantNameHint,
        mustVisibleContents: item.requiredTexts,
        focus: item.focus,
        timing: item.timing,
        viewport: item.viewport,
        successSignal: item.successSignal,
        expectedEvidenceLevel: item.expectedEvidenceLevel,
        plannedFilename: path.join(screenshotDir, item.filename),
      })),
    })),
  }
  await fs.writeFile(planPath, `${JSON.stringify(plan, null, 2)}\n`)
}

async function readExistingManifest() {
  try {
    return JSON.parse(await fs.readFile(manifestPath, "utf8"))
  } catch {
    return { cases: [], rejectedCandidates: [] }
  }
}

function removeByEvidenceId(items, evidenceId) {
  const index = items.findIndex((item) => item.evidenceId === evidenceId)
  if (index >= 0) items.splice(index, 1)
}

function groupDefinitions() {
  const groups = new Map()
  for (const item of evidenceDefinitions) {
    if (!groups.has(item.section)) groups.set(item.section, [])
    groups.get(item.section).push(item)
  }
  return [...groups.entries()]
}

async function ensureAuthenticated() {
  await page.goto(`${baseURL}/login`, { waitUntil: "domcontentloaded" })
  let profile = await fetchJson("/api/me").catch(() => null)
  if (!profile?.ok) {
    const login = await fetchJson("/api/access/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    })
    if (!login.ok) {
      const detail = login.data?.detail || login.data?.message || `HTTP ${login.status}`
      throw new Error(`登录失败：${detail}`)
    }
    if (login.data?.mfaRequired) {
      throw new Error("登录账号开启了 MFA，截图脚本需要使用非 MFA 的演示专用账号")
    }
    profile = await fetchJson("/api/me")
  }
  if (!profile.ok || !profile.data?.id) {
    throw new Error(`登录态验证失败：/api/me 返回 ${profile.status}`)
  }
  return profile.data
}

async function selectTenant(definition) {
  if (teamCache.has(definition.tenantSlug)) {
    activeTeam = teamCache.get(definition.tenantSlug)
    activeTeamId = activeTeam.id
    await setAuthTeam(activeTeam)
    return activeTeam
  }
  activeTeamId = null
  const teamsResponse = await fetchJson("/api/teams?limit=200")
  const teams = Array.isArray(teamsResponse.data?.items) ? teamsResponse.data.items : teamsResponse.data?.data?.items ?? teamsResponse.data
  const team = teams?.find((item) => item.slug === definition.tenantSlug || item.name === definition.tenantNameHint || item.name?.includes(definition.tenantNameHint))
  if (!team?.id) throw new Error(`未找到截图租户：${definition.tenantSlug}`)
  teamCache.set(definition.tenantSlug, team)
  activeTeam = team
  activeTeamId = team.id
  await setAuthTeam(team)
  return team
}

async function setAuthTeam(team) {
  await page.evaluate(
    ({ team, user }) => {
      const current = JSON.parse(localStorage.getItem("auth-storage") || '{"state":{},"version":0}')
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          ...current,
          state: {
            ...(current.state ?? {}),
            isAuthenticated: true,
            user,
            currentTeam: team,
          },
        }),
      )
    },
    { team, user: activeUser },
  )
}

async function captureEvidence(definition) {
  const startedAt = new Date().toISOString()
  const failureOffset = apiFailures.length
  const tools = { page, context, extra: {} }
  activeEvidence = definition
  try {
    await page.goto(`${baseURL}${definition.route}`, { waitUntil: "domcontentloaded" })
    await injectScreenshotCss()
    await waitForPageReady()
    if (definition.action) {
      await definition.action(tools)
      await waitForPageReady()
    }
    const chartReadiness = await waitForStableCharts(definition)
    await assertBusinessEvidence(definition, failureOffset)
    if (!definition.preserveScroll) {
      await page.evaluate(() => {
        window.scrollTo({ top: 0, left: 0, behavior: "instant" })
        document.documentElement.scrollLeft = 0
        document.body.scrollLeft = 0
      })
    }
    const screenshotPath = path.join(screenshotDir, definition.filename)
    await page.screenshot({ path: screenshotPath, fullPage: false })
    const bytes = await fs.readFile(screenshotPath)
    const recentFailures = apiFailures.slice(failureOffset)
    const partialReasons = definition.allowPartial ? collectPartialReasons(definition) : []
    return {
      evidenceId: definition.evidenceId,
      section: definition.section,
      title: definition.title,
      route: definition.route,
      actualUrl: page.url(),
      screenshotPath,
      status: partialReasons.length > 0 ? "部分有效" : "有效",
      acceptanceConclusion:
        partialReasons.length > 0
          ? `页面可作为辅助展示，但需复核：${partialReasons.join("；")}`
          : "页面通过登录态、租户、关键接口、非空业务内容、无错误状态校验，可作为平台介绍截图证据。",
      failureReason: "",
      reshootSuggestion: `设置 E2E_TENANT_SLUG 不需要；脚本会自动切换 ${definition.tenantSlug}。可用 EVIDENCE_ONLY=${definition.evidenceId} 单张重拍。`,
      mustVisibleContents: definition.requiredTexts,
      expectedEvidenceLevel: definition.expectedEvidenceLevel,
      tenantSlug: definition.tenantSlug,
      tenantName: activeTeam?.name,
      tenantId: activeTeamId,
      tenantRole: tenants[definition.tenantKey].role,
      brandProfile,
      viewport: `${viewport.width}x${viewport.height}`,
      capturedAt: startedAt,
      sha256: createHash("sha256").update(bytes).digest("hex"),
      apiFailures: recentFailures,
      consoleErrorCount: consoleErrors.length,
      chartReadiness,
    }
  } catch (error) {
    return {
      evidenceId: definition.evidenceId,
      section: definition.section,
      title: definition.title,
      route: definition.route,
      actualUrl: page.url(),
      screenshotPath: "",
      status: "待取证",
      acceptanceConclusion: "未形成满足要求的有效业务截图。",
      failureReason: error instanceof Error ? error.message : String(error),
      reshootSuggestion: "检查页面数据、必需可见内容、交互结果态和接口状态后重拍；必要时补充对应租户演示数据。",
      mustVisibleContents: definition.requiredTexts,
      expectedEvidenceLevel: definition.expectedEvidenceLevel,
      tenantSlug: definition.tenantSlug,
      tenantName: activeTeam?.name,
      tenantId: activeTeamId,
      tenantRole: tenants[definition.tenantKey].role,
      brandProfile,
      viewport: `${viewport.width}x${viewport.height}`,
      capturedAt: startedAt,
      apiFailures: apiFailures.slice(failureOffset),
    }
  } finally {
    activeEvidence = null
    await page.keyboard.press("Escape").catch(() => {})
  }
}

function rewriteEvidenceApiUrl(url) {
  if (!activeEvidence) return url
  const next = new URL(url)
  if (activeEvidence.evidenceId === "EV-WH-008") {
    const targets = new Set([
      "/api/metering/energy/summary",
      "/api/metering/energy/trend",
      "/api/metering/energy/ranking",
    ])
    if (targets.has(next.pathname)) {
      next.searchParams.set("start_time", "2026-07-10T00:00:00")
      next.searchParams.set("end_time", "2026-07-10T23:59:59")
    }
  }
  if (activeEvidence.evidenceId === "EV-WH-009" && next.pathname === "/api/iot-monitoring/point-series") {
    next.searchParams.set("start_time", "2026-07-10T00:00:00")
    next.searchParams.set("end_time", "2026-07-10T23:59:59")
    next.searchParams.set("limit", "1000")
  }
  return next.toString()
}

async function injectScreenshotCss() {
  await page.addStyleTag({ content: screenshotCss }).catch(() => {})
}

function collectPartialReasons(definition) {
  const reasons = []
  if (definition.section === "碳资产与公开碳价模拟") reasons.push("碳资产本次定位为扩展能力和公开碳价模拟，不作为核心主线能力")
  if (definition.evidenceId === "EV-WH-005") reasons.push("大屏专题作为展示补充，需确认数据丰富度和视觉完整度")
  if (definition.evidenceId === "EV-WH-011") reasons.push("设备测点页用于主数据支撑，是否足以证明MQTT完整配置需结合泰州截图")
  if (definition.evidenceId === "EV-WH-015" || definition.evidenceId === "EV-WH-016") reasons.push("运维/审计页为支撑材料，需按实际可见记录判定")
  if (definition.evidenceId === "EV-WH-027") reasons.push("预算页需确认年度目标和月度预算数据是否完整")
  if (definition.evidenceId === "EV-WH-046" || definition.evidenceId === "EV-WH-047") reasons.push("页面可证明分类填报台账与活动记录；F10价值链方法当前显示为方法待配置，不能单独证明核算闭环")
  return reasons
}

async function waitForPageReady() {
  await page.waitForLoadState("domcontentloaded")
  await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => {})
  await page.evaluate(async () => {
    await document.fonts.ready
  })
}

async function waitForStableCharts(definition) {
  const deadline = Date.now() + chartReadyTimeoutMs
  let lastSnapshot = null
  while (Date.now() < deadline) {
    const first = await readChartSnapshot()
    lastSnapshot = first
    if (first.stable && first.reason === "no-visible-chart") return first
    if (first.allPainted) {
      let stableCounts = true
      let previous = first
      for (let index = 0; index < chartStableFrames; index += 1) {
        await page.waitForTimeout(80)
        const next = await readChartSnapshot()
        lastSnapshot = next
        if (!next.allPainted || !sameChartCounts(previous, next)) {
          stableCounts = false
          break
        }
        previous = next
      }
      if (stableCounts) {
        await page.waitForTimeout(chartSettledDelayMs)
        const settled = await readChartSnapshot()
        lastSnapshot = settled
        if (settled.allPainted && sameChartCounts(previous, settled)) {
          return {
            ...settled,
            stable: true,
            reason: "charts-painted-after-settle",
            signatureStable: settled.signature === previous.signature,
          }
        }
      }
    }
    await page.waitForTimeout(250)
  }
  throw new Error(`图表未达到稳定可截图状态：${definition.evidenceId} ${JSON.stringify(lastSnapshot)}`)
}

async function readChartSnapshot() {
  return page.evaluate(() => {
    const visible = (element) => {
      const style = window.getComputedStyle(element)
      const box = element.getBoundingClientRect()
      return style.visibility !== "hidden" && style.display !== "none" && Number(style.opacity || 1) > 0 && box.width >= 80 && box.height >= 60
    }
    const chartPanels = [...document.querySelectorAll("[data-chart-panel]")].filter(visible)
    const echartsContainers = [...document.querySelectorAll("[_echarts_instance_]")].filter(visible)
    const chartCanvases = [...document.querySelectorAll("canvas")].filter((canvas) => {
      const box = canvas.getBoundingClientRect()
      return (
        visible(canvas) &&
        canvas.width > 0 &&
        canvas.height > 0 &&
        box.width >= 80 &&
        box.height >= 60 &&
        Boolean(canvas.closest("[_echarts_instance_], [data-chart-panel]"))
      )
    })
    const chartSvgs = [...document.querySelectorAll("svg")].filter((svg) => {
      const box = svg.getBoundingClientRect()
      return (
        visible(svg) &&
        box.width >= 80 &&
        box.height >= 60 &&
        Boolean(svg.closest("[_echarts_instance_], [data-chart-panel]")) &&
        svg.querySelector("path, line, rect, circle, polyline, polygon, text")
      )
    })
    const canvasStats = (canvas) => {
      const context = canvas.getContext("2d", { willReadFrequently: true })
      if (!context) return { nonTransparent: 0, colorVariance: 0, signature: `no-context:${canvas.width}x${canvas.height}` }
      const data = context.getImageData(0, 0, canvas.width, canvas.height).data
      const step = Math.max(16, Math.floor((canvas.width * canvas.height * 4) / 3000) * 4)
      let nonTransparent = 0
      let colorVariance = 0
      let signature = 0
      for (let index = 0; index < data.length; index += step) {
        const r = data[index]
        const g = data[index + 1]
        const b = data[index + 2]
        const alpha = data[index + 3]
        if (alpha > 8) nonTransparent += 1
        if (alpha > 8 && (Math.abs(r - 248) > 8 || Math.abs(g - 250) > 8 || Math.abs(b - 252) > 8)) colorVariance += 1
        signature = (signature * 31 + r * 3 + g * 5 + b * 7 + alpha * 11) >>> 0
      }
      return { nonTransparent, colorVariance, signature: `${canvas.width}x${canvas.height}:${signature}` }
    }
    const canvases = chartCanvases.map(canvasStats)
    const svgs = chartSvgs.map((svg) => ({
      nodeCount: svg.querySelectorAll("path, line, rect, circle, polyline, polygon, text").length,
      text: svg.textContent?.trim().length ?? 0,
      signature: `${Math.round(svg.getBoundingClientRect().width)}x${Math.round(svg.getBoundingClientRect().height)}:${svg.innerHTML.length}`,
    }))
    const chartCount = chartCanvases.length + chartSvgs.length
    const panelCount = chartPanels.length + echartsContainers.length
    if (panelCount === 0 && chartCount === 0) {
      return { chartCount: 0, panelCount: 0, canvasCount: 0, svgCount: 0, stable: true, reason: "no-visible-chart" }
    }
    return {
      chartCount,
      panelCount,
      canvasCount: chartCanvases.length,
      svgCount: chartSvgs.length,
      stable: false,
      reason: chartCount === 0 ? "chart-container-without-renderer" : "chart-renderer-observed",
      allPainted:
        chartCount > 0 &&
        canvases.every((item) => item.nonTransparent > 8 && item.colorVariance > 8) &&
        svgs.every((item) => item.nodeCount > 0),
      signature: JSON.stringify({ canvases: canvases.map((item) => item.signature), svgs: svgs.map((item) => item.signature) }),
    }
  })
}

function sameChartCounts(left, right) {
  return left.chartCount === right.chartCount && left.canvasCount === right.canvasCount && left.svgCount === right.svgCount
}

async function assertBusinessEvidence(definition, failureOffset) {
  if (page.url().includes("/login")) throw new Error("截图目标仍停留在登录页")
  await assertBrandIsolation(definition)
  const recentFailures = apiFailures.slice(failureOffset)
  if (recentFailures.length > 0) {
    throw new Error(`关键接口出现 ${recentFailures.map((item) => item.status).join(",")}：${recentFailures[0].url}`)
  }
  const loadingArtifacts = await visibleLoadingArtifacts()
  if (loadingArtifacts.length > 0) throw new Error(`页面仍存在加载态：${loadingArtifacts.join(", ")}`)
  for (const marker of errorMarkers) {
    if (await hasVisibleText(marker)) throw new Error(`页面存在错误状态文案：${marker}`)
  }
  for (const marker of genericEmptyMarkers) {
    if (definition.allowedEmptyMarkers.includes(marker)) continue
    if (await hasVisibleText(marker)) throw new Error(`页面目标数据为空或仅为入口态：${marker}`)
  }
  for (const marker of definition.rejectTexts) {
    if (await hasVisibleText(marker)) throw new Error(`页面存在不满足证据要求的结果态：${marker}`)
  }
  for (const text of definition.requiredTexts) {
    if (!(await hasVisibleText(text))) throw new Error(`缺少必须可见内容：${text}`)
  }
}

async function assertBrandIsolation(definition) {
  for (const forbiddenText of forbiddenBrandTexts) {
    if (await hasVisibleText(forbiddenText)) {
      throw new Error(`品牌态串扰：页面仍出现旧品牌文案“${forbiddenText}”`)
    }
  }

  if (!definition.route.startsWith("/bigscreen")) {
    const hasDisplayName = await hasVisibleText(brandProfile.displayName)
    const hasShortName = await hasVisibleText(brandProfile.shortName)
    if (!hasDisplayName && !hasShortName) {
      throw new Error(`品牌态未生效：页面未出现“${brandProfile.displayName}”或“${brandProfile.shortName}”`)
    }
  }
}

async function visibleLoadingArtifacts() {
  return page.evaluate((markers) => {
    const visible = (element) => {
      const style = window.getComputedStyle(element)
      const box = element.getBoundingClientRect()
      return style.visibility !== "hidden" && style.display !== "none" && Number(style.opacity || 1) > 0 && box.width > 0 && box.height > 0
    }
    const selectors = [
      '[role="progressbar"]',
      '[aria-busy="true"]',
      '[class*="loading" i]',
      '[class*="loader" i]',
      '[class*="spinner" i]',
      '[class*="skeleton" i]',
      '[data-loading="true"]',
    ]
    const hits = []
    for (const selector of selectors) {
      if ([...document.querySelectorAll(selector)].some(visible)) hits.push(selector)
    }
    const bodyText = document.body.innerText || ""
    for (const marker of markers) {
      if (bodyText.includes(marker)) hits.push(marker)
    }
    return [...new Set(hits)].slice(0, 8)
  }, loadingMarkers)
}

async function hasVisibleText(text) {
  const locator = page.getByText(text, { exact: false })
  const count = Math.min(await locator.count(), 20)
  for (let index = 0; index < count; index += 1) {
    if (await locator.nth(index).isVisible().catch(() => false)) return true
  }
  return false
}

async function uploadAndPreviewGhgWorkbook({ page }) {
  const fixturePath = await createGhgImportFixture()
  await page.locator('input[type="file"]').setInputFiles(fixturePath)
  await page.getByRole("button", { name: "执行预检" }).click()
  await page.getByText("活动数据预览", { exact: true }).waitFor({ timeout: 40_000 })
}

async function createGhgImportFixture() {
  const catalogResponse = await fetchJson("/api/ghg-inventory/catalog")
  if (!catalogResponse.ok) throw new Error(`无法读取温室气体导入目录：${catalogResponse.status}`)
  const catalog = catalogResponse.data ?? {}
  const period =
    catalog.periods?.find((item) => String(item.code ?? "").includes("2026")) ??
    catalog.periods?.[0] ??
    null
  const organization =
    catalog.organizations?.find((item) => item.code === period?.organizationCode) ??
    catalog.organizations?.[0] ??
    null
  const facility = catalog.areas?.find((item) => Number(item.level ?? 0) === 0) ?? catalog.areas?.[0] ?? null
  const equipment =
    catalog.equipment?.find((item) => String(item.name ?? "").includes("天然气")) ??
    catalog.equipment?.find((item) => String(item.name ?? "").includes("备用")) ??
    catalog.equipment?.[0] ??
    null
  const area =
    catalog.areas?.find((item) => item.code === equipment?.areaCode) ??
    catalog.areas?.find((item) => item.code !== facility?.code) ??
    facility
  const category = catalog.categories?.find((item) => item.code === "1.1") ?? catalog.categories?.[0] ?? null
  const methodCode =
    category?.defaultMethods?.find((code) => catalog.methods?.find((item) => item.code === code && item.executable)) ??
    "F01_NCV"
  const reportingProfile = catalog.reportingProfiles?.[0] ?? null
  if (!period?.code || !organization?.code || !facility?.code || !category?.code || !methodCode || !reportingProfile?.code) {
    throw new Error("温室气体导入目录缺少盘查期、组织、设施、分类、方法或报告配置")
  }

  const fixturePath = path.join(outputDir, "fixtures", `woheng-ghg-import-${Date.now()}.xlsx`)
  await fs.mkdir(path.dirname(fixturePath), { recursive: true })
  execFileSync(
    "uv",
    ["run", "python", path.join(repositoryRoot, "src/js/web/scripts/build-ghg-import-fixture.py"), "--output", fixturePath],
    {
      cwd: repositoryRoot,
      stdio: "pipe",
      env: {
        ...process.env,
        GHG_FIXTURE_PREFIX: "HD-WH",
        GHG_FIXTURE_INVENTORY_CODE: period.code,
        GHG_FIXTURE_ORGANIZATION_CODE: organization.code,
        GHG_FIXTURE_FACILITY_CODE: facility.code,
        GHG_FIXTURE_CATEGORY_CODE: category.code,
        GHG_FIXTURE_REPORTING_PROFILE_CODE: reportingProfile.code,
        GHG_FIXTURE_METHOD_CODE: methodCode,
        GHG_FIXTURE_AREA_CODE: area?.code ?? facility.code,
        GHG_FIXTURE_AREA_CODES: [facility.code, area?.code].filter(Boolean).join(","),
        GHG_FIXTURE_EQUIPMENT_CODE: equipment?.code ?? "",
        GHG_FIXTURE_EQUIPMENT_CODES: equipment?.code ?? "",
        GHG_FIXTURE_EQUIPMENT_NAME: equipment?.name ?? "固定燃烧设备",
        GHG_FIXTURE_METER_POINT: equipment?.code ?? "GAS-METER-01",
      },
    },
  )
  return fixturePath
}

async function openFirstOrganizationCarbonRecord({ page }) {
  await page.getByText("排放结果明细", { exact: true }).waitFor({ timeout: 20_000 })
  const rows = page.locator("tbody tr").filter({ hasNotText: "当前筛选条件下无核算结果" })
  await rows.first().scrollIntoViewIfNeeded()
  await rows.first().click()
  await page.getByText("活动与核算公式", { exact: true }).waitFor({ timeout: 20_000 })
}

async function prepareTaizhouPointMonitoringTrend({ page }) {
  const search = page.getByPlaceholder("搜索设备、点位、来源编码")
  await search.fill("正向有功总电能")
  await page.getByRole("button", { name: "查询" }).click()
  await page.getByText("正向有功总电能", { exact: false }).first().waitFor({ timeout: 20_000 })
  await page.getByText("最近读数", { exact: true }).waitFor({ timeout: 20_000 })
}

async function ensureVerificationProjectSelected(page) {
  await page.getByRole("tab", { name: "核查项目", exact: true }).click()
  const rows = page.locator("tbody tr").filter({ hasNotText: "暂无" })
  await rows.first().waitFor({ state: "visible", timeout: 20_000 })
  const preferred = rows.filter({ hasText: /沃衡|湖州|WH-/ })
  const selected = (await preferred.count()) > 0 ? preferred.first() : rows.first()
  await selected.click()
  await page.waitForFunction(() => document.querySelector('tbody tr[data-state="selected"]'), null, { timeout: 5_000 }).catch(() => {})
}

async function openFirstDeviceEditor({ page }) {
  await page.getByText("设备列表", { exact: true }).waitFor({ timeout: 20_000 })
  const rows = page.locator("tbody tr").filter({ hasNotText: "暂无设备" })
  await rows.first().waitFor({ state: "visible", timeout: 20_000 })
  await rows.first().click()
  await page.getByRole("button", { name: "编辑" }).click()
  await page.getByText("编辑设备", { exact: true }).waitFor({ timeout: 20_000 })
}

async function fetchJson(url, options = {}) {
  return page.evaluate(
    async ({ url, options, activeTeamId }) => {
      const headers = new Headers(options.headers ?? {})
      if (activeTeamId) headers.set("X-Team-Id", activeTeamId)
      if (window.__LITESTAR_CSRF__ && !headers.has("X-XSRF-TOKEN")) {
        headers.set("X-XSRF-TOKEN", window.__LITESTAR_CSRF__)
      }
      const response = await fetch(url, { ...options, headers, credentials: "include" })
      const data = await response.json().catch(() => null)
      return { ok: response.ok, status: response.status, data }
    },
    { url, options, activeTeamId },
  )
}

async function writeIndex(manifest) {
  const rows = [...manifest.cases, ...manifest.rejectedCandidates].map((record) => ({
    evidenceId: record.evidenceId,
    section: record.section,
    title: record.title,
    route: record.route,
    tenantSlug: record.tenantSlug,
    screenshotPath: record.screenshotPath,
    status: record.status,
    expectedEvidenceLevel: record.expectedEvidenceLevel,
    acceptanceConclusion: record.acceptanceConclusion,
    failureReason: record.failureReason,
    reshootSuggestion: record.reshootSuggestion,
  }))
  await fs.writeFile(
    indexPath,
    `${JSON.stringify(
      {
        title: "沃衡汽车能碳管理平台统一演示截图索引",
        updatedAt: new Date().toISOString(),
        rows,
      },
      null,
      2,
    )}\n`,
  )
}

function maskEmail(value) {
  if (!value || !value.includes("@")) return "configured"
  const [name, domain] = value.split("@")
  return `${name.slice(0, 2)}***@${domain}`
}
