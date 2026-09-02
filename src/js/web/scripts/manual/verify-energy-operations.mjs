import { chromium } from "@playwright/test"
import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const webRoot = path.resolve(scriptDir, "../..")
const repositoryRoot = path.resolve(webRoot, "../../..")
const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:18101"
const username = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com"
const password = process.env.E2E_ADMIN_PASSWORD ?? "Admin123!"
const tenantSlug = process.env.E2E_TENANT_SLUG ?? "woheng-taizhou-production-base"
const outputDir = path.resolve(process.env.MANUAL_VERIFY_OUTPUT_DIR ?? path.join(repositoryRoot, "outputs/woheng-showcase-woheng-full-evidence"))
const screenshotDir = path.join(outputDir, "screenshots")
const verificationDir = path.join(outputDir, "manual-verification")
const verificationPath = path.join(verificationDir, "energy-operations.json")
const viewport = { width: 1440, height: 900 }
const screenshots = {
  homeEnergyWorkbench: "EV-WH-117-首页工作台能源运营入口.png",
  platformEnergyEntries: "EV-WH-118-数据管理平台能源入口.png",
  sidebarEnergyMenu: "EV-WH-119-侧边栏能源运营菜单.png",
  consumptionSummary: "EV-WH-101-能耗查询汇总筛选与结果.png",
  consumptionFacts: "EV-WH-102-能耗查询明细追溯.png",
  consumptionExport: "EV-WH-103-能耗查询导出记录.png",
  intensitySummary: "EV-WH-104-能源强度消费量汇总.png",
  intensityArea: "EV-WH-105-能源强度面积强度.png",
  intensityHierarchy: "EV-WH-106-能源强度区域设备层级.png",
  intensityTrend: "EV-WH-107-能源强度趋势分析.png",
  analysisStructure: "EV-WH-108-用能结构分析.png",
  analysisCost: "EV-WH-109-用能成本分析.png",
  analysisPerformance: "EV-WH-110-用能能效分析.png",
  analysisAnomaly: "EV-WH-111-用能异常诊断.png",
  analysisStrategy: "EV-WH-112-用能策略建议.png",
  flowGraph: "EV-WH-113-能流图分析.png",
  flowBalance: "EV-WH-114-能流能量平衡表.png",
  flowLosses: "EV-WH-115-能流损耗诊断.png",
  flowReport: "EV-WH-116-能流分析报告.png",
}
const forbiddenBrandTexts = ["中汽信科", "奇瑞", "Chery", "安方", "祥泰", "华东绿色仓储"]
const screenshotCss = `
  .tsqd-parent-container,
  .tsqd-open-btn-container,
  [class*="tsqd-"],
  [aria-label*="React Query" i],
  [aria-label*="TanStack Query" i],
  [data-sonner-toast] {
    display: none !important;
    visibility: hidden !important;
  }
`

await fs.mkdir(screenshotDir, { recursive: true })
await fs.mkdir(verificationDir, { recursive: true })

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport, deviceScaleFactor: 1, acceptDownloads: true })
const page = await context.newPage()
page.setDefaultTimeout(25_000)
page.setDefaultNavigationTimeout(45_000)

const apiFailures = []
const consoleErrors = []
const checks = []
const artifacts = []
const startedAt = new Date().toISOString()
let activeTeamId = null
let activeUser = null
let exportFile = ""

await context.route("**/api/**", async (route) => {
  const headers = { ...route.request().headers() }
  if (activeTeamId) headers["x-team-id"] = activeTeamId
  await route.continue({ headers })
})

page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push({ text: message.text(), at: new Date().toISOString() })
})
page.on("response", (response) => {
  if (!response.url().includes("/api/")) return
  const status = response.status()
  if (status === 401 || status === 403 || status >= 500) {
    apiFailures.push({
      status,
      method: response.request().method(),
      url: response.url().replace(baseURL, ""),
      at: new Date().toISOString(),
    })
  }
})

try {
  console.log("[ManualVerify] Preflight 100% | Auth 0% | Harness 100% | Navigate 0/7 | Interact 0/19 | Evidence 0/19 | Writeback 0/1")
  await ensureAuthenticated()
  await selectTenant()
  await validateEnergyApis()
  console.log("[ManualVerify] Preflight 100% | Auth 100% | Harness 100% | Navigate 0/7 | Interact 0/19 | Evidence 0/19 | Writeback 0/1")

  await verifyNavigationPages()
  await verifyConsumptionPage()
  await verifyIntensityPage()
  await verifyAnalysisPage()
  await verifyFlowPage()

  await writeVerification("passed")
  console.log("[ManualVerify] Preflight 100% | Auth 100% | Harness 100% | Navigate 7/7 | Interact 19/19 | Evidence 19/19 | Writeback 1/1")
} catch (error) {
  await writeVerification("failed", error)
  console.error(error)
  process.exitCode = 1
} finally {
  await browser.close()
}

async function ensureAuthenticated() {
  await page.goto(`${baseURL}/login`, { waitUntil: "domcontentloaded" })
  let profile = await fetchJson("/api/me").catch(() => null)
  if (!profile?.ok) {
    const login = await fetchJson("/api/access/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ username, password }),
    })
    if (!login.ok) throw new Error(`登录失败：${login.data?.detail ?? login.data?.message ?? `HTTP ${login.status}`}`)
    if (login.data?.mfaRequired) throw new Error("验证账号开启了 MFA，无法用于自动化手册验证。")
    profile = await fetchJson("/api/me")
  }
  if (!profile.ok || !profile.data?.id) throw new Error(`登录态验证失败：/api/me 返回 ${profile.status}`)
  activeUser = profile.data
}

async function selectTenant() {
  const response = await fetchJson("/api/teams?limit=200")
  if (!response.ok) throw new Error(`租户列表读取失败：HTTP ${response.status}`)
  const teams = Array.isArray(response.data?.items) ? response.data.items : response.data?.data?.items ?? response.data
  const team = teams?.find((item) => item.slug === tenantSlug)
  if (!team?.id) throw new Error(`未找到验证租户：${tenantSlug}`)
  activeTeamId = team.id
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
  checks.push({ name: "auth-and-tenant", status: "passed", tenantSlug, tenantId: activeTeamId })
}

async function validateEnergyApis() {
  const endpoints = [
    ["/api/energy/consumption/summary", (data) => data?.data?.totals?.record_count > 0],
    ["/api/energy/consumption/facts?limit=10", (data) => Array.isArray(data?.items) && data.items.length > 0],
    ["/api/energy/intensity/summary", (data) => data?.data?.totals?.record_count > 0 && data?.data?.by_energy_type?.length > 0],
    ["/api/energy/intensity/trend?granularity=month", (data) => Array.isArray(data?.data?.series) && data.data.series.length > 0],
    ["/api/energy/analysis/summary?granularity=month", (data) => data?.data?.totals?.record_count > 0 && data?.data?.by_system?.length > 0],
    ["/api/energy/analysis/anomalies?granularity=month", (data) => Array.isArray(data?.data?.items)],
    ["/api/energy/analysis/strategies?granularity=month", (data) => Array.isArray(data?.data?.items) && data.data.items.length > 0],
    ["/api/energy/flow/graph?granularity=month", (data) => data?.data?.nodes?.length > 0 && data?.data?.links?.length > 0],
    ["/api/energy/flow/balance?granularity=month", (data) => data?.data?.table?.length > 0],
    ["/api/energy/flow/losses?granularity=month", (data) => Array.isArray(data?.data?.items)],
    ["/api/energy/flow/report?granularity=month", (data) => Array.isArray(data?.data?.items) && data.data.items.length > 0],
  ]
  for (const [endpoint, assertData] of endpoints) {
    const result = await fetchJson(endpoint)
    if (!result.ok) throw new Error(`能源运营接口失败：${endpoint} HTTP ${result.status}`)
    if (!assertData(result.data)) throw new Error(`能源运营接口无有效数据：${endpoint}`)
    checks.push({ name: `api:${endpoint}`, status: "passed" })
  }
}

async function verifyNavigationPages() {
  await gotoPage("/home", ["工作台", "能源运营", "能耗查询", "能耗强度", "用能分析", "能效对标", "能流分析", "能效平衡"])
  await waitForCharts(2)
  await capture("homeEnergyWorkbench", "首页工作台能源运营入口，展示能源查询、强度、分析、对标、能流和平衡入口。")

  await gotoPage("/platform", ["平台入口", "能源运营", "能源种类", "单位换算", "能源数据维护", "能耗查询", "监测与告警", "设备台账", "电表电量"])
  await capture("platformEnergyEntries", "数据管理平台入口，展示能源主数据、能源事实数据和监测告警相关入口。")

  await gotoPage("/energy/consumption", ["能源运营", "能源种类", "单位换算", "能源数据维护", "能耗查询", "能耗强度", "用能分析", "能效对标", "能流分析", "能效平衡"])
  await capture("sidebarEnergyMenu", "侧边栏能源运营一级菜单展开态，展示能源运营二级菜单。")
}

async function verifyConsumptionPage() {
  await gotoPage("/energy/consumption", ["能耗查询", "汇总查询", "明细追溯", "导出记录", "能源品种", "记录数"])
  await capture("consumptionSummary", "能耗查询汇总页，显示统一筛选条件、指标卡和按能源品种汇总结果。")
  await switchTab("明细追溯")
  await assertBusinessPage(["能源消费明细", "来源", "能源品种", "折标煤", "追溯"])
  await capture("consumptionFacts", "能耗查询明细页，显示来源记录、Scope、能源品种、折标量、期间和区域设施。")
  await switchTab("导出记录")
  await assertBusinessPage(["导出", "导出 CSV"])
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "导出 CSV" }).click()])
  exportFile = path.join(verificationDir, download.suggestedFilename())
  await download.saveAs(exportFile)
  const content = await fs.readFile(exportFile, "utf8")
  if (!content.includes("source_record_id") || !content.includes("energy_type_code")) throw new Error("能耗查询导出 CSV 缺少关键表头")
  await capture("consumptionExport", "能耗查询导出页，导出 CSV 后保留当前筛选条件与导出入口。")
}

async function verifyIntensityPage() {
  await gotoPage("/energy/intensity", ["能源消费量和强度计算", "消费量汇总", "面积强度", "区域设备", "趋势分析"])
  await waitForCharts(1)
  await capture("intensitySummary", "能源强度消费量汇总页，显示综合能耗、折标煤、外购电力和能源品种汇总。")
  await switchTab("面积强度")
  await waitForCharts(1)
  await assertBusinessPage(["仓储面积折标强度", "园区面积折标强度", "面积分母"])
  await capture("intensityArea", "能源强度面积页，显示仓储面积、园区面积和面积强度指标。")
  await switchTab("区域设备")
  await assertBusinessPage(["区域设备层级", "综合能耗(tce)", "外购电力(kWh)"])
  await capture("intensityHierarchy", "能源强度区域设备页，显示企业、区域、设备/设施的层级能耗。")
  await switchTab("趋势分析")
  await waitForCharts(2)
  await assertBusinessPage(["综合能耗和面积折标强度趋势", "外购电力专项强度趋势"])
  await capture("intensityTrend", "能源强度趋势页，显示综合能耗、面积强度和外购电力专项趋势。")
}

async function verifyAnalysisPage() {
  await gotoPage("/energy/analysis", ["用能分析", "结构分析", "成本分析", "能效分析", "异常诊断", "策略建议"])
  await waitForCharts(2)
  await capture("analysisStructure", "用能分析结构页，显示总用电量、用能系统、区域和设备排行。")
  await switchTab("成本分析")
  await waitForCharts(2)
  await assertBusinessPage(["估算电费", "平均电价", "分时成本结构", "分时电量排行"])
  await capture("analysisCost", "用能分析成本页，显示分时成本结构、平均电价和计费记录。")
  await switchTab("能效分析")
  await waitForCharts(1)
  await assertBusinessPage(["运行小时", "单位运行小时电耗", "设备能效排行"])
  await capture("analysisPerformance", "用能分析能效页，显示运行小时、单位电耗、能耗成本趋势和设备能效排行。")
  await switchTab("异常诊断")
  await assertBusinessPage(["异常时段", "能源告警", "异常时段明细"])
  await capture("analysisAnomaly", "用能分析异常页，显示异常时段、告警数量和异常明细。")
  await switchTab("策略建议")
  await assertBusinessPage(["策略数", "证据电量", "实施步骤"])
  await capture("analysisStrategy", "用能分析策略页，显示策略证据、目标对象和实施步骤。")
}

async function verifyFlowPage() {
  await gotoPage("/energy/flow", ["能流分析", "能流图", "能量平衡表", "损耗诊断", "分析报告"])
  await waitForCharts(1)
  await capture("flowGraph", "能流图页，显示计量用电、分项用电、损耗率和关键链路贡献。")
  await switchTab("能量平衡表")
  await assertBusinessPage(["能量平衡表", "平衡诊断"])
  await capture("flowBalance", "能流平衡页，显示能量输入、利用、损耗和诊断字段。")
  await switchTab("损耗诊断")
  await assertBusinessPage(["损耗诊断", "输入(kWh)", "损耗(kWh)", "损耗率", "建议"])
  await capture("flowLosses", "能流损耗页，显示链路损耗率、状态和处理建议。")
  await switchTab("分析报告")
  await assertBusinessPage(["证据", "动作"])
  await capture("flowReport", "能流分析报告页，显示分析条目、证据字段和动作建议。")
}

async function gotoPage(route, requiredTexts) {
  apiFailures.length = 0
  await page.goto(`${baseURL}${route}`, { waitUntil: "domcontentloaded" })
  await injectScreenshotCss()
  await waitForPageReady()
  await assertBusinessPage(requiredTexts)
  checks.push({ name: `navigate:${route}`, status: "passed" })
}

async function switchTab(name) {
  await page.getByRole("tab", { name, exact: true }).click()
  await waitForPageReady()
  checks.push({ name: `tab:${name}`, status: "passed" })
}

async function capture(key, note) {
  await injectScreenshotCss()
  await waitForPageReady()
  await waitForUiSettled()
  await assertBusinessPage()
  const file = path.join(screenshotDir, screenshots[key])
  await page.screenshot({ path: file, fullPage: false })
  artifacts.push({ key, note, screenshotPath: file, viewport: `${viewport.width}x${viewport.height}` })
  checks.push({ name: `screenshot:${key}`, status: "passed", screenshotPath: file })
}

async function waitForCharts(minNonBlankCount) {
  await page.waitForFunction(
    (minCount) => {
      const canvases = [...document.querySelectorAll("canvas")]
      const visibleCanvases = canvases.filter((canvas) => {
        const style = window.getComputedStyle(canvas)
        const rect = canvas.getBoundingClientRect()
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 40 && rect.height > 40
      })
      const nonBlank = visibleCanvases.filter((canvas) => {
        const context = canvas.getContext("2d")
        if (!context) return false
        const { width, height } = canvas
        if (width === 0 || height === 0) return false
        const sample = context.getImageData(0, 0, Math.min(width, 80), Math.min(height, 80)).data
        for (let index = 3; index < sample.length; index += 4) {
          if (sample[index] !== 0) return true
        }
        return false
      })
      return nonBlank.length >= minCount
    },
    minNonBlankCount,
    { timeout: 20_000 },
  )
}

async function injectScreenshotCss() {
  await page.addStyleTag({ content: screenshotCss }).catch(() => {})
}

async function assertBusinessPage(requiredTexts = []) {
  if (page.url().includes("/login")) throw new Error("页面仍停留在登录页")
  const failures = apiFailures.filter((item) => item.status === 401 || item.status === 403 || item.status >= 500)
  if (failures.length > 0) throw new Error(`关键接口失败：${failures[0].method} ${failures[0].url} HTTP ${failures[0].status}`)
  for (const forbiddenText of forbiddenBrandTexts) {
    if (await hasVisibleText(forbiddenText)) throw new Error(`品牌串扰：页面出现 ${forbiddenText}`)
  }
  const loading = await visibleLoadingArtifacts()
  if (loading.length > 0) throw new Error(`页面仍存在加载态：${loading.join(", ")}`)
  for (const text of requiredTexts) await expectVisible(text)
}

async function waitForPageReady() {
  await page.waitForLoadState("domcontentloaded")
  await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => {})
  await page.evaluate(async () => {
    await document.fonts.ready
  })
  await waitForUiSettled()
}

async function waitForUiSettled() {
  await page.evaluate(
    () =>
      new Promise((resolve) => {
        const animations = document.getAnimations().filter((animation) => animation.playState !== "finished")
        if (animations.length === 0) {
          resolve(undefined)
          return
        }
        const timeout = window.setTimeout(() => resolve(undefined), 900)
        Promise.all(animations.map((animation) => animation.finished.catch(() => undefined))).then(() => {
          window.clearTimeout(timeout)
          resolve(undefined)
        })
      }),
  )
  await page.waitForTimeout(150)
}

async function visibleLoadingArtifacts() {
  return page.evaluate(() => {
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
    return selectors.filter((selector) => [...document.querySelectorAll(selector)].some(visible))
  })
}

async function hasVisibleText(text) {
  const locator = page.getByText(text, { exact: false })
  const count = Math.min(await locator.count(), 20)
  for (let index = 0; index < count; index += 1) {
    if (await locator.nth(index).isVisible().catch(() => false)) return true
  }
  return false
}

async function expectVisible(text) {
  await page.getByText(text, { exact: false }).first().waitFor({ state: "visible", timeout: 20_000 })
}

async function fetchJson(url, options = {}) {
  return page.evaluate(
    async ({ url, options, activeTeamId }) => {
      const headers = new Headers(options.headers ?? {})
      if (activeTeamId) headers.set("X-Team-Id", activeTeamId)
      if (window.__LITESTAR_CSRF__ && !headers.has("X-XSRF-TOKEN")) headers.set("X-XSRF-TOKEN", window.__LITESTAR_CSRF__)
      const response = await fetch(url, { ...options, headers, credentials: "include" })
      const data = await response.json().catch(() => null)
      return { ok: response.ok, status: response.status, data }
    },
    { url, options, activeTeamId },
  )
}

async function writeVerification(status, error = null) {
  await fs.writeFile(
    verificationPath,
    `${JSON.stringify(
      {
        title: "能源运营查询、分析与能流页面验证",
        status,
        startedAt,
        finishedAt: new Date().toISOString(),
        baseURL,
        tenantSlug,
        viewport: `${viewport.width}x${viewport.height}`,
        exportFile,
        checks,
        artifacts,
        apiFailures,
        consoleErrors,
        failureReason: error instanceof Error ? error.message : error ? String(error) : "",
      },
      null,
      2,
    )}\n`,
  )
}
