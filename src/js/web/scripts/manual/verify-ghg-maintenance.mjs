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
const verificationPath = path.join(verificationDir, "ghg-maintenance.json")
const viewport = { width: 1440, height: 900 }
const stamp = new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 12)
const sourceCode = process.env.MANUAL_VERIFY_GHG_SOURCE_CODE ?? `MANUAL-GHG-SRC-${stamp}`
const recordCode = process.env.MANUAL_VERIFY_GHG_RECORD_CODE ?? `MANUAL-GHG-ACT-${stamp}`
const screenshots = {
  activityEntry: "EV-WH-144-活动数据台账入口.png",
  sourceCreate: "EV-WH-145-排放源新增表单.png",
  sourceEdit: "EV-WH-146-排放源编辑结果.png",
  activityCreate: "EV-WH-147-活动数据新增表单.png",
  activityDetail: "EV-WH-148-活动数据详情与归集.png",
  activityEdit: "EV-WH-149-活动数据编辑结果.png",
  generate: "EV-WH-150-组织碳活动数据生成结果.png",
  deleteResult: "EV-WH-151-活动与排放源删除结果.png",
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

const apiFailures = []
const consoleErrors = []
const checks = []
const artifacts = []
let activeTeamId = null
let activeUser = null
let catalog = null
let period = null
let area = null
let equipment = null

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

const startedAt = new Date().toISOString()

try {
  await ensureAuthenticated()
  await selectTenant()
  await loadCatalog()
  await cleanupActivity(recordCode)
  await cleanupSource(sourceCode)

  await openActivityLedger()
  await capture("activityEntry", "打开活动数据总账，确认总账用于只读查询、跨分类筛选和详情追溯。")

  await createSource()
  await editSource()

  await createActivity()
  await openActivityDetailAndSaveAllocation()
  await editActivity()

  await cleanupCreatedRows()
  await capture("deleteResult", "删除未引用活动数据和排放源后，台账查询结果不再显示验证记录。")

  await writeVerification("passed")
} catch (error) {
  await writeVerification("failed", error)
  console.error(error)
  process.exitCode = 1
} finally {
  await browser.close()
}

async function ensureAuthenticated() {
  await page.goto(`${baseURL}/login`, { waitUntil: "domcontentloaded" })
  const login = await fetchJson("/api/access/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ username, password }),
  })
  if (!login.ok) throw new Error(`登录失败：${login.data?.detail ?? login.data?.message ?? `HTTP ${login.status}`}`)
  if (login.data?.mfaRequired) throw new Error("验证账号开启了 MFA，无法用于自动化手册验证。")
  const profile = await fetchJson("/api/me")
  if (!profile.ok || !profile.data?.id) throw new Error(`登录态验证失败：/api/me 返回 ${profile.status}`)
  activeUser = profile.data
  checks.push({ name: "auth", status: "passed", user: username })
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
  checks.push({ name: "tenant", status: "passed", tenantSlug, tenantId: activeTeamId })
}

async function loadCatalog() {
  const response = await fetchJson("/api/ghg-inventory/catalog")
  if (!response.ok) throw new Error(`组织碳目录读取失败：HTTP ${response.status}`)
  catalog = response.data
  period = catalog.periods?.[0]
  area = catalog.areas?.[0]
  equipment = catalog.equipment?.find((item) => item.areaId) ?? catalog.equipment?.[0]
  if (!period?.code || !area?.code) throw new Error("组织碳维护验证需要报告期和区域主数据")
  checks.push({ name: "catalog", status: "passed", period: period.name, area: area.name, equipment: equipment?.name ?? "" })
}

async function openActivityLedger() {
  apiFailures.length = 0
  await page.goto(`${baseURL}/carbon-mgmt/activities`, { waitUntil: "domcontentloaded" })
  await injectScreenshotCss()
  await waitForPageReady()
  await assertBusinessPage(["温室气体活动总账", "只读查询", "盘查任务", "ISO 二级分类"])
}

async function createSource() {
  await page.goto(`${baseURL}/carbon-mgmt/sources`, { waitUntil: "domcontentloaded" })
  await waitForPageReady()
  await page.getByRole("button", { name: "新增排放源" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "新增排放源" })
  await dialog.waitFor({ state: "visible" })
  await fillInput(dialog, "排放源编号", sourceCode)
  await fillInput(dialog, "排放源名称", "手册验证购入电力排放源")
  await selectOption(dialog, "ISO 二级分类", "2.1")
  await selectOption(dialog, "默认区域", area.name)
  if (equipment?.name) await selectOption(dialog, "默认设备", equipment.name)
  await capture("sourceCreate", "新增排放源表单填写态，展示盘查任务、ISO 分类、组织、区域、设备和来源状态。")
  await dialog.getByRole("button", { name: "保存排放源" }).click()
  await expectVisible("排放源已保存")
  await searchSources(sourceCode)
  await expectVisible("手册验证购入电力排放源")
  checks.push({ name: "source-create", status: "passed", sourceCode })
}

async function editSource() {
  await rowFor(sourceCode).getByRole("button").first().click()
  const dialog = page.getByRole("dialog").filter({ hasText: "维护排放源" })
  await dialog.waitFor({ state: "visible" })
  await fillInput(dialog, "排放源名称", "手册验证购入电力排放源-已编辑")
  await dialog.getByRole("button", { name: "更新排放源" }).click()
  await expectVisible("排放源已更新")
  await searchSources(sourceCode)
  await expectVisible("已编辑")
  await capture("sourceEdit", "编辑排放源后回到列表，排放源名称、分类、组织区域和活动记录数回显。")
  checks.push({ name: "source-update", status: "passed", sourceCode })
}

async function createActivity() {
  await page.goto(`${baseURL}/carbon-mgmt/category/2.1`, { waitUntil: "domcontentloaded" })
  await waitForPageReady()
  await assertBusinessPage(["2.1 购入电力活动数据", "能源种类", "Scope 2 方法"])
  await page.getByRole("button", { name: "新增本类活动" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "新增活动数据" })
  await dialog.waitFor({ state: "visible" })
  await expectVisible("2.1 购入电力")
  await selectOption(dialog, "排放源", "已编辑")
  await fillInput(dialog, "记录编号", recordCode)
  await fillInput(dialog, "活动名称", "手册验证购入电力活动")
  await fillInput(dialog, "开始日期", period.periodStart)
  await fillInput(dialog, "结束日期", period.periodEnd)
  await fillInput(dialog, "活动量", "1688.5")
  await fillInput(dialog, "单位", "kWh")
  await selectOption(dialog, "数据来源", "实测")
  await fillOrSelect(dialog, "能源种类", "electricity", "电力")
  await fillInput(dialog, "供应商", "电网购电")
  await fillInput(dialog, "计量点", equipment?.code ?? "METER-MANUAL")
  await selectOption(dialog, "Scope 2 方法", "基于位置")
  await fillInput(dialog, "测量方法", "电表读数按报告期汇总")
  await fillInput(dialog, "备注", "活动数据维护验证")
  await capture("activityCreate", "新增活动数据表单填写态，展示活动量、期间、动态分类字段和测量方法。")
  await dialog.getByRole("button", { name: "保存活动数据" }).click()
  await expectVisible("活动数据已保存")
  await searchActivities(recordCode)
  await expectVisible("手册验证购入电力活动")
  checks.push({ name: "activity-create", status: "passed", recordCode })
}

async function openActivityDetailAndSaveAllocation() {
  await rowFor(recordCode).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "活动数据详情" })
  await dialog.waitFor({ state: "visible" })
  await expectVisible("分类字段")
  await dialog.getByRole("button", { name: "保存归集" }).click()
  await expectVisible("区域设备归集已保存")
  await capture("activityDetail", "活动数据详情中维护区域、设备、计量边界和归集比例，保存后形成活动数据归集关系。")
  await page.keyboard.press("Escape")
  checks.push({ name: "allocation-save", status: "passed", recordCode })
}

async function editActivity() {
  await searchActivities(recordCode)
  await rowFor(recordCode).getByRole("button").nth(1).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "编辑活动数据" })
  await dialog.waitFor({ state: "visible" })
  await fillInput(dialog, "活动量", "1777.25")
  await fillInput(dialog, "备注", "活动数据维护编辑验证")
  await dialog.getByRole("button", { name: "更新活动数据" }).click()
  await expectVisible("活动数据已更新")
  await searchActivities(recordCode)
  await expectVisible("1,777.25")
  await capture("activityEdit", "编辑活动数据后回到台账，活动量、来源、质量和归集状态回显。")
  checks.push({ name: "activity-update", status: "passed", recordCode })
}

async function generateActivities() {
  await page.goto(`${baseURL}/carbon-mgmt/activities`, { waitUntil: "domcontentloaded" })
  await waitForPageReady()
  await page.getByRole("button", { name: "生成活动数据" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "生成组织碳活动数据" })
  await dialog.waitFor({ state: "visible" })
  await dialog.getByRole("button", { name: "生成" }).click()
  await expectVisible("活动数据生成完成")
  await waitForPageReady()
  await capture("generate", "执行幂等生成后，购入电力和员工通勤活动数据进入统一台账。")
  checks.push({ name: "activity-generate", status: "passed", reportingPeriodCode: period.code })
}

async function cleanupCreatedRows() {
  await cleanupActivity(recordCode)
  await cleanupSource(sourceCode)
  await page.goto(`${baseURL}/carbon-mgmt/activities`, { waitUntil: "domcontentloaded" })
  await waitForPageReady()
  await searchActivities(recordCode, false)
  checks.push({ name: "cleanup", status: "passed", sourceCode, recordCode })
}

async function cleanupActivity(code) {
  const row = await getActivity(code)
  if (!row?.recordCode) return
  const result = await fetchJson(`/api/ghg-inventory/activities/${encodeURIComponent(code)}?inventory_code=${encodeURIComponent(row.inventoryCode)}`, { method: "DELETE" })
  if (!result.ok && result.status !== 404) throw new Error(`清理活动数据失败：${code} HTTP ${result.status}`)
}

async function cleanupSource(code) {
  const row = await getSource(code)
  if (!row?.sourceCode) return
  const result = await fetchJson(`/api/ghg-inventory/emission-sources/${encodeURIComponent(code)}?inventory_code=${encodeURIComponent(row.inventoryCode)}`, { method: "DELETE" })
  if (!result.ok && result.status !== 404) throw new Error(`清理排放源失败：${code} HTTP ${result.status}`)
}

async function getActivity(code) {
  const response = await fetchJson("/api/ghg-inventory/activities?limit=500")
  if (!response.ok) throw new Error(`活动数据查询失败：HTTP ${response.status}`)
  return (response.data?.items ?? []).find((item) => item.recordCode === code) ?? null
}

async function getSource(code) {
  const response = await fetchJson(`/api/ghg-inventory/emission-sources?keyword=${encodeURIComponent(code)}&limit=20`)
  if (!response.ok) throw new Error(`排放源查询失败：HTTP ${response.status}`)
  return (response.data?.items ?? []).find((item) => item.sourceCode === code) ?? null
}

async function searchSources(text) {
  const input = page.getByPlaceholder("排放源编号或名称")
  await input.fill(text)
  await waitForPageReady()
}

async function searchActivities(text, expectRecord = true) {
  const input = page.getByPlaceholder("记录、活动或排放源")
  await input.fill(text)
  await waitForPageReady()
  if (expectRecord) await expectVisible(text)
}

function rowFor(text) {
  return page.locator("tbody tr").filter({ hasText: text }).first()
}

async function fillInput(scope, label, value) {
  const labelLocator = scope.locator("label", { hasText: label }).first()
  const control = labelLocator.locator("xpath=ancestor::div[contains(@class, 'space-y-1.5')][1]//*[self::input or self::textarea]").first()
  const readonly = await control.evaluate((element) => element instanceof HTMLInputElement && element.readOnly).catch(() => false)
  if (readonly) return
  await control.fill(String(value))
}

async function fillOrSelect(scope, label, inputValue, optionText) {
  const labelLocator = scope.locator("label", { hasText: label }).first()
  const container = labelLocator.locator("xpath=ancestor::div[contains(@class, 'space-y-1.5')][1]")
  const trigger = container.locator("button[role='combobox']").first()
  if (await trigger.isVisible().catch(() => false)) {
    await trigger.click()
    await page.getByRole("option", { name: optionText, exact: false }).first().click()
    return
  }
  await fillInput(scope, label, inputValue)
}

async function selectOption(scope, label, option) {
  const labelLocator = scope.locator("label", { hasText: label }).first()
  const trigger = labelLocator.locator("xpath=ancestor::div[contains(@class, 'space-y-1.5')][1]//button[@role='combobox']").first()
  await trigger.click()
  await page.getByRole("option", { name: option, exact: false }).first().click()
}

async function capture(key, note) {
  await injectScreenshotCss()
  await waitForPageReady()
  await assertBusinessPage()
  const file = path.join(screenshotDir, screenshots[key])
  const toastStyle = await hideToastForScreenshot()
  try {
    await page.screenshot({ path: file, fullPage: false })
  } finally {
    await toastStyle.evaluate((element) => element.remove()).catch(() => {})
  }
  artifacts.push({ key, note, screenshotPath: file, viewport: `${viewport.width}x${viewport.height}` })
  checks.push({ name: `screenshot-${key}`, status: "passed", screenshotPath: file })
}

async function injectScreenshotCss() {
  await page.addStyleTag({ content: screenshotCss }).catch(() => {})
}

async function hideToastForScreenshot() {
  return page.addStyleTag({ content: "[data-sonner-toast]{display:none!important;visibility:hidden!important;}" })
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
  await page.waitForTimeout(120)
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
        title: "组织碳排放源与活动数据维护验证",
        status,
        startedAt,
        finishedAt: new Date().toISOString(),
        baseURL,
        tenantSlug,
        sourceCode,
        recordCode,
        viewport: `${viewport.width}x${viewport.height}`,
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
