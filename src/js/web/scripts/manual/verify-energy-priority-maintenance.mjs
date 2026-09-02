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
const outputDir = path.resolve(
  process.env.MANUAL_VERIFY_OUTPUT_DIR ?? path.join(repositoryRoot, "outputs/woheng-showcase-woheng-full-evidence"),
)
const screenshotDir = path.join(outputDir, "screenshots")
const verificationDir = path.join(outputDir, "manual-verification")
const verificationPath = path.join(verificationDir, "energy-priority-maintenance.json")
const viewport = { width: 1440, height: 900 }
const suffix = new Date().toISOString().replace(/\D/g, "").slice(0, 14)
const benchmarkProfileName = `仓储设备能效对标方案-${suffix}`
const benchmarkProfileNameEdited = `${benchmarkProfileName}-更新`
const budgetPlanName = `2026年度仓储能碳预算目标-${suffix}`
const budgetPlanNameEdited = `${budgetPlanName}-更新`
const screenshots = {
  benchmarkProfiles: "EV-WH-120-能效对标配置方案列表.png",
  benchmarkProfileCreate: "EV-WH-121-能效对标配置新增方案.png",
  benchmarkProfileDetail: "EV-WH-122-能效对标配置方案详情.png",
  benchmarkItemCreate: "EV-WH-123-能效对标配置新增标杆项.png",
  benchmarkItemEdited: "EV-WH-124-能效对标配置标杆项编辑回显.png",
  benchmarkGenerate: "EV-WH-125-能效对标配置历史基线生成.png",
  benchmarkAnalysisEntry: "EV-WH-126-能效对标分析维护入口.png",
  budgetPlans: "EV-WH-127-能碳预算维护年度目标列表.png",
  budgetPlanCreate: "EV-WH-128-能碳预算维护新增年度目标.png",
  budgetAllocationEdited: "EV-WH-129-能碳预算维护月度分解编辑.png",
  budgetAdjustmentEdited: "EV-WH-130-能碳预算维护调整记录编辑.png",
  budgetAnalysisEntry: "EV-WH-131-能碳预算分析维护入口.png",
  budgetAdjustmentDeleted: "EV-WH-132-能碳预算维护调整记录删除.png",
}
const forbiddenBrandTexts = ["中汽信科", "奇瑞", "Chery", "安方", "祥泰", "华东绿色仓储"]
const screenshotCss = `
  .tsqd-parent-container,
  .tsqd-open-btn-container,
  [class*="tsqd-"],
  [aria-label*="React Query" i],
  [aria-label*="TanStack Query" i] {
    display: none !important;
    visibility: hidden !important;
  }
`

await fs.mkdir(screenshotDir, { recursive: true })
await fs.mkdir(verificationDir, { recursive: true })

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport, deviceScaleFactor: 1, acceptDownloads: true })
const page = await context.newPage()
page.setDefaultTimeout(20_000)
page.setDefaultNavigationTimeout(40_000)
page.on("dialog", (dialog) => dialog.accept())

const apiFailures = []
const consoleErrors = []
const checks = []
const artifacts = []
let activeTeamId = null
let activeUser = null
let createdBenchmarkProfileId = null
let createdBenchmarkItemId = null
let createdBudgetPlanId = null
let selectedDeviceName = ""

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
  console.log("[PriorityVerify] Auth 0% | Benchmark 0/7 | Budget 0/6 | Writeback 0/1")
  await ensureAuthenticated()
  await selectTenant()
  selectedDeviceName = await resolveDeviceName()
  await cleanupBenchmarkProfiles()
  await cleanupBudgetPlans()
  console.log("[PriorityVerify] Auth 100% | Benchmark 0/7 | Budget 0/6 | Writeback 0/1")

  await verifyBenchmarkMaintenance()
  await verifyBudgetMaintenance()

  await cleanupBenchmarkProfiles()
  await cleanupBudgetPlans()
  await writeVerification("passed")
  console.log("[PriorityVerify] Auth 100% | Benchmark 7/7 | Budget 6/6 | Writeback 1/1")
} catch (error) {
  await writeVerification("failed", error)
  console.error(error)
  process.exitCode = 1
} finally {
  await browser.close()
}

async function verifyBenchmarkMaintenance() {
  await gotoPage("/data/energy-benchmark", ["能效对标配置", "标杆方案", "标杆项", "历史基线生成"])
  await capture("benchmarkProfiles", "能效对标配置页展示方案列表、查询、查看对标和新增方案入口。")

  await page.getByRole("button", { name: "新增方案" }).click()
  await expectVisible("新增标杆方案")
  await fillTextField("方案名称", benchmarkProfileName)
  await fillTextField("行业", "仓储物流")
  await fillTextField("适用范围", "生产基地仓储设施")
  await fillTextField("来源", "企业能效管理制度")
  await fillTextField("备注", "用于仓储照明、通风和分拣设备能效对标")
  await capture("benchmarkProfileCreate", "新增标杆方案表单，维护行业、适用范围、来源和备注。")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible(benchmarkProfileName)
  const profile = await findBenchmarkProfile(benchmarkProfileName)
  createdBenchmarkProfileId = profile.id
  checks.push({ name: "benchmark-profile-create", status: "passed", id: profile.id })

  await clickRowAction(benchmarkProfileName, "详情")
  await expectVisible("标杆方案详情")
  await expectVisible("仓储物流")
  await capture("benchmarkProfileDetail", "标杆方案详情抽屉回显已保存的方案字段。")
  await page.keyboard.press("Escape")

  await clickRowAction(benchmarkProfileName, "编辑")
  await fillTextField("方案名称", benchmarkProfileNameEdited)
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible(benchmarkProfileNameEdited)
  checks.push({ name: "benchmark-profile-edit", status: "passed" })

  await page.getByRole("tab", { name: "标杆项" }).click()
  await page.getByRole("button", { name: "新增标杆项" }).click()
  await expectVisible("新增标杆项")
  await chooseSelect("对象类型", "设备")
  await chooseSelect("对象", selectedDeviceName)
  await chooseSelect("指标", "单位运行小时用电")
  await fillTextField("标杆值", "86.5")
  await fillTextField("优秀值", "78.0")
  await fillTextField("来源", "仓储设备运行统计")
  await capture("benchmarkItemCreate", "新增标杆项表单，按设备选择指标并维护标杆值、优秀值和来源。")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible(selectedDeviceName)
  await expectVisible("86.5")
  const item = await findBenchmarkItem(createdBenchmarkProfileId)
  createdBenchmarkItemId = item.id
  checks.push({ name: "benchmark-item-create", status: "passed", id: item.id })

  await clickRowAction(selectedDeviceName, "编辑")
  await fillTextField("标杆值", "82.25")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible("82.25")
  await capture("benchmarkItemEdited", "标杆项编辑保存后，列表回显更新后的标杆值。")
  checks.push({ name: "benchmark-item-edit", status: "passed" })

  await page.getByRole("tab", { name: "历史基线生成" }).click()
  await expectVisible("历史基线生成")
  await page.getByRole("button", { name: "均值生成" }).click()
  await expectVisible("历史基线标杆已生成")
  await capture("benchmarkGenerate", "历史基线生成结果态，页面提示标杆已按历史数据生成。")
  checks.push({ name: "benchmark-generate", status: "passed" })

  await gotoPage("/energy/benchmark", ["能效对标", "维护标杆"])
  await capture("benchmarkAnalysisEntry", "能效对标分析页保留维护入口，可跳转到能效对标配置页。")
  await page.getByRole("link", { name: "维护标杆" }).click()
  await page.waitForURL("**/data/energy-benchmark")
  await waitForPageReady()
  checks.push({ name: "benchmark-analysis-entry", status: "passed" })
}

async function verifyBudgetMaintenance() {
  await gotoPage("/data/energy-budget", ["能碳预算维护", "年度目标", "月度分解", "调整记录"])
  await capture("budgetPlans", "能碳预算维护页展示年度目标列表、年度筛选、查看执行和新增目标入口。")

  await page.getByRole("button", { name: "新增目标" }).click()
  await expectVisible("新增预算目标")
  await fillTextField("目标名称", budgetPlanName)
  await fillTextField("年度", "2026")
  await chooseSelect("适用范围", "企业")
  await fillTextField("能耗预算(tce)", "16800")
  await fillTextField("碳排预算(tCO2e)", "40200")
  await fillTextField("分母计划", "286000")
  await fillTextField("分母单位", "m2")
  await fillTextField("来源", "年度经营计划")
  await fillTextField("备注", "用于仓储生产基地年度能碳预算跟踪")
  await capture("budgetPlanCreate", "新增预算目标表单，维护年度、适用范围、能耗预算、碳排预算和分母计划。")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible(budgetPlanName)
  const plan = await findBudgetPlan(budgetPlanName)
  createdBudgetPlanId = plan.id
  checks.push({ name: "budget-plan-create", status: "passed", id: plan.id })

  await clickRowAction(budgetPlanName, "编辑")
  await fillTextField("目标名称", budgetPlanNameEdited)
  await fillTextField("能耗预算(tce)", "17250")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible(budgetPlanNameEdited)
  checks.push({ name: "budget-plan-edit", status: "passed" })

  await page.getByRole("tab", { name: "月度分解" }).click()
  await page.getByRole("button", { name: "生成月度预算" }).click()
  await expectVisible("月度预算已生成")
  await expectVisible("2026-01")
  await clickRowAction("2026-01", "编辑")
  await fillTextField("能耗预算(tce)", "1500")
  await fillTextField("备注", "一月预算分解校准")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible("1,500")
  await capture("budgetAllocationEdited", "生成月度预算后编辑单月预算，列表回显更新值。")
  checks.push({ name: "budget-allocation-generate-edit", status: "passed" })

  await page.getByRole("tab", { name: "调整记录" }).click()
  await page.getByRole("button", { name: "新增调整" }).click()
  await expectVisible("新增预算调整")
  await chooseSelect("月份", "2026-01")
  await fillTextField("调整类型", "seasonal")
  await fillTextField("申请人", "运营管理员")
  await fillTextField("调整后能耗(tce)", "1520")
  await fillTextField("调整后碳排(tCO2e)", "3600")
  await fillTextField("原因", "春节前后作业量变化")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible("seasonal")
  await clickRowAction("seasonal", "编辑")
  await chooseSelect("状态", "批准")
  await fillTextField("批准人", "能源主管")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible("批准")
  await capture("budgetAdjustmentEdited", "新增预算调整并编辑审批状态后，调整记录列表回显。")
  checks.push({ name: "budget-adjustment-create-edit", status: "passed" })

  await clickRowAction("seasonal", "删除调整记录")
  await expectVisible("调整记录已删除")
  await expectVisible("暂无调整记录")
  await capture("budgetAdjustmentDeleted", "删除预算调整记录后，调整记录列表回显为空。")
  checks.push({ name: "budget-adjustment-delete", status: "passed" })

  await gotoPage("/energy/budget", ["能碳预算", "维护预算"])
  await capture("budgetAnalysisEntry", "能碳预算分析页保留维护入口，可跳转到能碳预算维护页。")
  await page.getByRole("link", { name: "维护预算" }).click()
  await page.waitForURL("**/data/energy-budget")
  await waitForPageReady()
  checks.push({ name: "budget-analysis-entry", status: "passed" })
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

async function resolveDeviceName() {
  const response = await fetchJson("/api/master-data/devices?limit=500&offset=0")
  if (!response.ok) throw new Error(`设备列表读取失败：HTTP ${response.status}`)
  const devices = Array.isArray(response.data?.items) ? response.data.items : []
  const device = devices.find((item) => item.name) ?? devices[0]
  if (!device?.name) throw new Error("能效对标配置验证需要至少一台设备。")
  checks.push({ name: "device-selector", status: "passed", deviceName: device.name })
  return String(device.name)
}

async function cleanupBenchmarkProfiles() {
  const response = await fetchJson(`/api/energy/benchmark/profiles?keyword=${encodeURIComponent("仓储设备能效对标方案-")}&limit=200`)
  if (!response.ok) return
  const profiles = response.data?.items ?? []
  for (const profile of profiles) {
    const items = await fetchJson(`/api/energy/benchmark/items?profile_id=${profile.id}&limit=200`)
    for (const item of items.data?.items ?? []) {
      await fetchJson(`/api/energy/benchmark/items/${item.id}`, { method: "DELETE" }).catch(() => null)
    }
    await fetchJson(`/api/energy/benchmark/profiles/${profile.id}`, { method: "DELETE" }).catch(() => null)
  }
  createdBenchmarkProfileId = null
  createdBenchmarkItemId = null
}

async function cleanupBudgetPlans() {
  const response = await fetchJson("/api/energy/budget/plans?budget_year=2026&limit=200")
  if (!response.ok) return
  for (const plan of response.data?.items ?? []) {
    if (String(plan.name ?? "").startsWith("2026年度仓储能碳预算目标-")) {
      await fetchJson(`/api/energy/budget/plans/${plan.id}`, { method: "DELETE" }).catch(() => null)
    }
  }
  createdBudgetPlanId = null
}

async function findBenchmarkProfile(name) {
  const response = await fetchJson(`/api/energy/benchmark/profiles?keyword=${encodeURIComponent(name)}&limit=20`)
  if (!response.ok) throw new Error(`标杆方案查询失败：HTTP ${response.status}`)
  const profile = response.data?.items?.find((item) => item.name === name)
  if (!profile?.id) throw new Error(`未找到标杆方案：${name}`)
  return profile
}

async function findBenchmarkItem(profileId) {
  const response = await fetchJson(`/api/energy/benchmark/items?profile_id=${profileId}&limit=20`)
  if (!response.ok) throw new Error(`标杆项查询失败：HTTP ${response.status}`)
  const item = response.data?.items?.find((entry) => entry.target_name === selectedDeviceName)
  if (!item?.id) throw new Error(`未找到标杆项：${selectedDeviceName}`)
  return item
}

async function findBudgetPlan(name) {
  const response = await fetchJson("/api/energy/budget/plans?budget_year=2026&limit=200")
  if (!response.ok) throw new Error(`预算目标查询失败：HTTP ${response.status}`)
  const plan = response.data?.items?.find((item) => item.name === name)
  if (!plan?.id) throw new Error(`未找到预算目标：${name}`)
  return plan
}

async function gotoPage(route, expectedTexts) {
  apiFailures.length = 0
  await page.goto(`${baseURL}${route}`, { waitUntil: "domcontentloaded" })
  await injectScreenshotCss()
  await waitForPageReady()
  await assertBusinessPage(expectedTexts)
  await assertNoApiFailures(route)
}

async function capture(key, title) {
  await waitForPageReady()
  await assertNoForbiddenBrands()
  await assertNoApiFailures(key)
  const filename = screenshots[key]
  const filepath = path.join(screenshotDir, filename)
  await page.screenshot({ path: filepath, fullPage: true })
  artifacts.push({ id: key, title, path: filepath, file: filename, route: new URL(page.url()).pathname })
}

async function fillTextField(label, value) {
  const field = page
    .locator(".grid.gap-2, .grid.gap-1\\.5")
    .filter({ has: page.getByText(label, { exact: true }) })
    .locator("input, textarea")
    .first()
  await field.fill(value)
}

async function chooseSelect(label, optionText) {
  const field = page
    .locator(".grid.gap-2, .grid.gap-1\\.5")
    .filter({ has: page.getByText(label, { exact: true }) })
    .locator('[role="combobox"]')
    .first()
  await field.click()
  await page.getByRole("option").filter({ hasText: optionText }).first().click()
}

async function clickRowAction(rowText, actionName) {
  const row = page.locator("tr", { hasText: rowText }).first()
  await row.getByRole("button", { name: actionName }).click()
}

async function expectVisible(text) {
  await page.getByText(text, { exact: false }).first().waitFor({ state: "visible" })
}

async function waitForNoDialog() {
  await page.locator('[role="dialog"]').waitFor({ state: "hidden", timeout: 20_000 })
  await waitForPageReady()
}

async function waitForPageReady() {
  await page.waitForLoadState("domcontentloaded")
  await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => null)
  await page.waitForFunction(
    () => {
      const text = document.body.innerText
      if (!text || text.includes("Loading...") || text.includes("加载中")) return false
      return !document.querySelector('[data-slot="skeleton"], .animate-pulse')
    },
    null,
    { timeout: 20_000 },
  )
}

async function assertBusinessPage(expectedTexts) {
  if (page.url().includes("/login")) throw new Error("页面仍停留在登录页")
  const bodyText = await page.locator("body").innerText()
  for (const text of expectedTexts) {
    if (!bodyText.includes(text)) throw new Error(`页面缺少关键内容：${text}`)
  }
}

async function assertNoForbiddenBrands() {
  const bodyText = await page.locator("body").innerText()
  const hit = forbiddenBrandTexts.find((text) => bodyText.includes(text))
  if (hit) throw new Error(`页面出现禁用品牌文本：${hit}`)
}

async function assertNoApiFailures(contextLabel) {
  if (apiFailures.length > 0) throw new Error(`${contextLabel} 出现接口失败：${JSON.stringify(apiFailures.slice(-5), null, 2)}`)
}

async function injectScreenshotCss() {
  await page.addStyleTag({ content: screenshotCss }).catch(() => null)
}

async function fetchJson(url, init = {}) {
  return page.evaluate(
    async ({ url, init, activeTeamId }) => {
      const headers = { ...(init.headers ?? {}) }
      if (activeTeamId) headers["x-team-id"] = activeTeamId
      const response = await fetch(url, { ...init, headers, credentials: "include" })
      const text = await response.text()
      let data = null
      try {
        data = text ? JSON.parse(text) : null
      } catch {
        data = text
      }
      return { ok: response.ok, status: response.status, data }
    },
    { url: `${baseURL}${url}`, init, activeTeamId },
  )
}

async function writeVerification(status, error = null) {
  await fs.writeFile(
    verificationPath,
    JSON.stringify(
      {
        status,
        baseURL,
        tenantSlug,
        viewport,
        checks,
        artifacts,
        cleanup: {
          benchmarkProfileId: createdBenchmarkProfileId,
          benchmarkItemId: createdBenchmarkItemId,
          budgetPlanId: createdBudgetPlanId,
        },
        apiFailures,
        consoleErrors,
        error: error ? String(error?.stack ?? error?.message ?? error) : null,
        completedAt: new Date().toISOString(),
      },
      null,
      2,
    ),
  )
}
