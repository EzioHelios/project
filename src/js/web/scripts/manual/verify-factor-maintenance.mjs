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
const verificationPath = path.join(verificationDir, "factor-maintenance.json")
const viewport = { width: 1440, height: 900 }
const stamp = new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 12)
const manualSubCategory = "enterprise_electricity_taizhou_demo"
const importSubCategory = "enterprise_diesel_import_demo"
const verificationSourceCode = "WHG-FACTOR-SRC-01"
const verificationRecordCode = "WHG-FACTOR-ACT-01"
const screenshots = {
  list: "EV-WH-152-企业计算因子台账.png",
  create: "EV-WH-153-新增企业计算因子.png",
  edit: "EV-WH-154-编辑企业计算因子结果.png",
  importPreview: "EV-WH-155-企业计算因子模板导入预检.png",
  activitySelection: "EV-WH-156-活动数据采用计算因子结果.png",
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
let organization = null
let area = null
let targetActivity = null

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
  await cleanupVerificationActivity()
  await cleanupFactors()
  await ensureTargetActivity()
  await verifyCalculationFactorLedger()
  await createEnterpriseFactor()
  await editEnterpriseFactor()
  await verifyTemplateImport()
  await applyFactorToActivity()
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
  if (login.data?.mfaRequired) throw new Error("验证账号开启了 MFA，无法用于自动化验证。")
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
  organization = catalog.organizations?.[0]
  area = catalog.areas?.[0]
  if (!period?.code || !period.id || !organization?.code || !area?.code) throw new Error("缺少创建因子验证活动所需的报告期、组织或区域")
  checks.push({ name: "catalog", status: "passed", period: period.name, organization: organization.name, area: area.name })
}

async function verifyCalculationFactorLedger() {
  apiFailures.length = 0
  await page.goto(`${baseURL}/carbon-mgmt/calculation-factors`, { waitUntil: "domcontentloaded" })
  await waitForPageReady()
  await assertBusinessPage(["企业计算因子库", "下载模板", "模板导入", "新增因子"])
  await capture("list", "企业计算因子库列表，区分企业因子和共享因子，企业因子进入可维护主线。")
  checks.push({ name: "factor-ledger", status: "passed" })
}

async function createEnterpriseFactor() {
  await page.getByRole("button", { name: "新增因子" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "新增企业计算因子" })
  await dialog.waitFor({ state: "visible" })
  await fillInput(dialog, "子类编码", manualSubCategory)
  await fillInput(dialog, "因子值", "0.5012")
  await fillInput(dialog, "来源", "企业审定电力排放因子")
  await capture("create", "新增企业计算因子表单，维护范围、类别、子类、活动单位、因子值、来源和状态。")
  await dialog.getByRole("button", { name: "保存因子" }).click()
  await expectVisible("计算因子已保存")
  await searchFactors(manualSubCategory)
  await expectVisible(manualSubCategory)
  checks.push({ name: "factor-create", status: "passed", subCategory: manualSubCategory })
}

async function editEnterpriseFactor() {
  const row = rowFor(manualSubCategory)
  await row.getByRole("button").nth(1).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "编辑企业计算因子" })
  await dialog.waitFor({ state: "visible" })
  await fillInput(dialog, "因子值", "0.5025")
  await fillInput(dialog, "备注", "自动化验证编辑")
  await dialog.getByRole("button", { name: "更新因子" }).click()
  await expectVisible("计算因子已更新")
  await searchFactors(manualSubCategory)
  await expectVisible("0.5025")
  await capture("edit", "编辑企业计算因子后回到台账，因子值和企业归属回显。")
  checks.push({ name: "factor-update", status: "passed", subCategory: manualSubCategory })
}

async function verifyTemplateImport() {
  const csvPath = path.join(verificationDir, `calculation-factor-${stamp}.csv`)
  await fs.writeFile(
    csvPath,
    [
      "scope,category,sub_category,unit,factor_value,factor_unit,year,source,source_system,source_snapshot_id,raw_record_id,projection_status,review_status,is_active,note",
      `scope1,fuel,${importSubCategory},L,2.6300,kgCO2e/L,2026,企业审定柴油因子,enterprise,,,manual,approved,true,自动化导入验证`,
      "",
    ].join("\n"),
  )
  await page.getByRole("button", { name: "模板导入" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "导入企业计算因子" })
  await dialog.waitFor({ state: "visible" })
  await dialog.locator("input[type='file']").setInputFiles(csvPath)
  await dialog.getByRole("button", { name: "预检" }).click()
  await expectVisible("计算因子导入预检完成")
  await expectVisible("有效行")
  await capture("importPreview", "企业计算因子模板导入预检，展示有效行、新增、更新和错误统计。")
  await dialog.getByRole("button", { name: "提交导入" }).click()
  await expectVisible("计算因子已导入")
  await searchFactors(importSubCategory)
  await expectVisible(importSubCategory)
  checks.push({ name: "factor-import", status: "passed", subCategory: importSubCategory })
}

async function ensureTargetActivity() {
  const source = await fetchJson("/api/ghg-inventory/emission-sources", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      inventoryCode: period.code,
      reportingPeriodId: period.id,
      organizationCode: organization.code,
      facilityCode: area.code,
      sourceCode: verificationSourceCode,
      sourceName: "沃衡购入电力排放源",
      isoCategoryCode: "2.1",
      sourceMechanism: "energy",
      originKind: "internal",
      defaultAreaId: area.id,
      defaultAllocationRole: "responsibility",
      sourceSystem: "manual-verification",
      status: "active",
    }),
  })
  if (!source.ok) throw new Error(`创建验证排放源失败：HTTP ${source.status}`)
  const activity = await fetchJson("/api/ghg-inventory/activities", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      recordCode: verificationRecordCode,
      inventoryCode: period.code,
      reportingPeriodId: period.id,
      organizationCode: organization.code,
      facilityCode: area.code,
      sourceCode: verificationSourceCode,
      activityCode: "purchased-electricity",
      activityName: "沃衡购入电力活动",
      periodStart: period.periodStart,
      periodEnd: period.periodEnd,
      isoCategoryCode: "2.1",
      activityAmount: "1688.50",
      activityUnit: "kWh",
      dataSourceType: "measured",
      measurementMethod: "电表月结数据",
      qualityStatus: "pass",
      status: "approved",
      sourceSystem: "manual-verification",
      sourcePayload: {
        energy_type: "electricity",
        supplier_name: "电网购电",
        meter_point: "WHG-PCC-METER-01",
        scope2_method: "location",
      },
      remarks: "计算因子采用验证",
    }),
  })
  if (!activity.ok) throw new Error(`创建验证活动数据失败：HTTP ${activity.status}`)
  targetActivity = activity.data
  checks.push({ name: "activity-context", status: "passed", recordCode: targetActivity.recordCode })
}

async function applyFactorToActivity() {
  await page.goto(`${baseURL}/carbon-mgmt/activities?category=2.1`, { waitUntil: "domcontentloaded" })
  await waitForPageReady()
  await searchActivities(targetActivity.recordCode)
  await rowFor(targetActivity.recordCode).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "活动数据详情" })
  await dialog.waitFor({ state: "visible" })
  await expectVisible("因子参数")
  const trigger = dialog.locator("label", { hasText: "候选因子" }).locator("xpath=ancestor::div[contains(@class, 'space-y-1.5')][1]//button[@role='combobox']").first()
  await trigger.click()
  await page.getByRole("option", { name: manualSubCategory, exact: false }).click()
  await dialog.getByRole("button", { name: "采用因子" }).click()
  await expectVisible("活动数据采用因子已更新")
  await expectVisible("企业审定电力排放因子")
  await capture("activitySelection", "活动数据详情中采用企业计算因子，当前参数值回显并进入核算参数集。")
  checks.push({ name: "activity-factor-selection", status: "passed", recordCode: targetActivity.recordCode, subCategory: manualSubCategory })
}

async function cleanupFactors() {
  for (const keyword of [manualSubCategory, importSubCategory, "manual_electricity_", "imported_diesel_"]) {
    const response = await fetchJson(`/api/carbon/emission-factors?owner=enterprise&keyword=${encodeURIComponent(keyword)}&limit=200`)
    if (!response.ok) continue
    for (const factor of response.data?.items ?? []) {
      await fetchJson(`/api/carbon/emission-factors/${factor.id}`, { method: "DELETE" }).catch(() => null)
    }
  }
}

async function cleanupVerificationActivity() {
  await fetchJson(`/api/ghg-inventory/activities/${encodeURIComponent(verificationRecordCode)}?inventory_code=${encodeURIComponent(period.code)}`, { method: "DELETE" }).catch(() => null)
  await fetchJson(`/api/ghg-inventory/emission-sources/${encodeURIComponent(verificationSourceCode)}?inventory_code=${encodeURIComponent(period.code)}`, { method: "DELETE" }).catch(() => null)
}

async function searchFactors(text) {
  await page.goto(`${baseURL}/carbon-mgmt/calculation-factors`, { waitUntil: "domcontentloaded" })
  await waitForPageReady()
  const input = page.getByPlaceholder("类别、子类、单位、来源")
  await input.fill(text)
  await waitForPageReady()
}

async function searchActivities(text) {
  const input = page.getByPlaceholder("记录、活动或排放源")
  await input.fill(text)
  await waitForPageReady()
  await expectVisible(text)
}

function rowFor(text) {
  return page.locator("tbody tr").filter({ hasText: text }).first()
}

async function fillInput(scope, label, value) {
  const labelLocator = scope.locator("label", { hasText: label }).first()
  const control = labelLocator.locator("xpath=ancestor::div[contains(@class, 'space-y-1.5')][1]//*[self::input or self::textarea]").first()
  await control.fill(String(value))
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
        title: "企业计算因子维护与采用验证",
        status,
        startedAt,
        finishedAt: new Date().toISOString(),
        baseURL,
        tenantSlug,
        manualSubCategory,
        importSubCategory,
        verificationSourceCode,
        verificationRecordCode,
        targetActivity,
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
