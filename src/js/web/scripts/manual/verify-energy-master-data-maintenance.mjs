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
const verificationPath = path.join(verificationDir, "energy-master-data-maintenance.json")
const viewport = { width: 1440, height: 900 }
const stamp = process.env.MANUAL_VERIFY_STAMP ?? "20260902"
const energyCode = `manual_energy_${stamp}`
const energyName = "手册验证低压电力"
const energyNameEdited = "手册验证低压电力-已编辑"
const sourceName = "GB/T 2589-2020"
const screenshots = {
  energyTypeList: "EV-WH-090-能源种类列表与查询.png",
  energyTypeCreate: "EV-WH-091-能源种类新增表单.png",
  energyTypeDetail: "EV-WH-092-能源种类详情回显.png",
  energyTypeEdit: "EV-WH-093-能源种类编辑表单.png",
  energyTypeDelete: "EV-WH-094-能源种类删除结果.png",
  conversionList: "EV-WH-095-单位换算列表与查询.png",
  conversionCreate: "EV-WH-096-单位换算新增表单.png",
  conversionDetail: "EV-WH-097-单位换算详情回显.png",
  conversionEdit: "EV-WH-098-单位换算编辑表单.png",
  conversionDelete: "EV-WH-099-单位换算删除结果.png",
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
const startedAt = new Date().toISOString()
let activeTeamId = null
let activeUser = null

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
  console.log("[ManualVerify] Preflight 100% | Auth 0% | Harness 100% | Navigate 0/2 | Interact 0/10 | Evidence 0/10 | Writeback 0/1")
  await ensureAuthenticated()
  await selectTenant()
  await cleanupMasterData()
  console.log("[ManualVerify] Preflight 100% | Auth 100% | Harness 100% | Navigate 0/2 | Interact 0/10 | Evidence 0/10 | Writeback 0/1")
  await verifyEnergyTypeMaintenance()
  await verifyUnitConversionMaintenance()
  await cleanupMasterData()
  await writeVerification("passed")
  console.log("[ManualVerify] Preflight 100% | Auth 100% | Harness 100% | Navigate 2/2 | Interact 10/10 | Evidence 10/10 | Writeback 1/1")
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

async function verifyEnergyTypeMaintenance() {
  await gotoPage("/data/energy-types", ["能源种类", "能源种类列表", "能源编码", "能源名称", "新增"])
  await capture("energyTypeList", "能源种类列表展示编码、名称、类别、默认范围、单位、折标系数和状态。")
  await page.getByRole("button", { name: "新增" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "新增能源种类" })
  await dialog.waitFor({ state: "visible" })
  await fillInput(dialog, "能源编码", energyCode)
  await fillInput(dialog, "能源名称", energyName)
  await selectOption(dialog, "类别", "外购能源")
  await selectOption(dialog, "默认范围", "范围二")
  await fillInput(dialog, "原始单位", "kWh")
  await fillInput(dialog, "折标单位", "kgce")
  await fillInput(dialog, "折标系数", "0.1229")
  await fillInput(dialog, "标准依据", sourceName)
  await fillInput(dialog, "系数来源", "手册验证能源种类维护")
  await fillInput(dialog, "备注", "能源种类新增验证")
  await scrollDialogToTop(dialog)
  await capture("energyTypeCreate", "能源种类新增表单填写态。")
  await dialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("新增成功")
  await search("搜索能源编码、名称、类别或标准", energyCode)
  await expectVisible(energyName)
  await rowFor(energyCode).getByRole("button", { name: "详情" }).click()
  await expectVisible("能源种类详情")
  await expectVisible(sourceName)
  await capture("energyTypeDetail", "能源种类保存后详情回显。")
  await page.keyboard.press("Escape")

  await rowFor(energyCode).getByRole("button", { name: "编辑" }).click()
  const editDialog = page.getByRole("dialog").filter({ hasText: "编辑能源种类" })
  await editDialog.waitFor({ state: "visible" })
  await fillInput(editDialog, "能源名称", energyNameEdited)
  await fillInput(editDialog, "备注", "能源种类编辑验证")
  await scrollDialogToTop(editDialog)
  await capture("energyTypeEdit", "能源种类编辑表单回填并修改名称和备注。")
  await editDialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("更新成功")
  await search("搜索能源编码、名称、类别或标准", energyCode)
  await expectVisible(energyNameEdited)
  checks.push({ name: "energy-type-crud-before-delete", status: "passed", energyCode })
}

async function verifyUnitConversionMaintenance() {
  await gotoPage("/data/energy-unit-conversions", ["单位换算", "单位换算列表", "能源种类", "换算系数", "新增"])
  await capture("conversionList", "单位换算列表展示能源种类、来源单位、目标单位、换算系数、标准依据和状态。")
  await page.getByRole("button", { name: "新增" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "新增单位换算" })
  await dialog.waitFor({ state: "visible" })
  await selectOption(dialog, "能源种类", energyNameEdited)
  await fillInput(dialog, "来源单位", "kWh")
  await fillInput(dialog, "目标单位", "kgce")
  await fillInput(dialog, "换算系数", "0.1229")
  await fillInput(dialog, "标准依据", sourceName)
  await fillInput(dialog, "系数来源", "手册验证单位换算维护")
  await fillInput(dialog, "备注", "单位换算新增验证")
  await scrollDialogToTop(dialog)
  await capture("conversionCreate", "单位换算新增表单填写态。")
  await dialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("新增成功")
  await search("搜索能源编码、单位或标准", energyCode)
  await expectVisible("0.1229")
  await rowFor(energyCode).getByRole("button", { name: "详情" }).click()
  await expectVisible("单位换算详情")
  await expectVisible(sourceName)
  await capture("conversionDetail", "单位换算保存后详情回显。")
  await page.keyboard.press("Escape")

  await rowFor(energyCode).getByRole("button", { name: "编辑" }).click()
  const editDialog = page.getByRole("dialog").filter({ hasText: "编辑单位换算" })
  await editDialog.waitFor({ state: "visible" })
  await fillInput(editDialog, "换算系数", "0.1230")
  await fillInput(editDialog, "备注", "单位换算编辑验证")
  await capture("conversionEdit", "单位换算编辑表单回填并修改换算系数和备注。")
  await editDialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("更新成功")
  await search("搜索能源编码、单位或标准", energyCode)
  await expectVisible("0.123")
  checks.push({ name: "unit-conversion-crud-before-delete", status: "passed", energyCode })

  await rowFor(energyCode).getByRole("button", { name: "删除" }).click()
  await expectVisible("删除成功")
  await waitForRowAbsent(energyCode)
  await capture("conversionDelete", "单位换算删除后查询结果。")

  await gotoPage("/data/energy-types", ["能源种类", "能源种类列表"])
  await search("搜索能源编码、名称、类别或标准", energyCode)
  await rowFor(energyCode).getByRole("button", { name: "删除" }).click()
  await expectVisible("删除成功")
  await waitForRowAbsent(energyCode)
  await capture("energyTypeDelete", "能源种类删除后查询结果。")
  checks.push({ name: "cleanup-by-ui", status: "passed", energyCode })
}

async function cleanupMasterData() {
  const conversions = await fetchJson(`/api/energy/unit-conversions?include_disabled=true&search=${encodeURIComponent(energyCode)}&limit=100`)
  if (conversions.ok) {
    for (const item of listItems(conversions.data)) {
      if (item.id) await fetchJson(`/api/energy/unit-conversions/${item.id}`, { method: "DELETE" })
    }
  }
  const types = await fetchJson(`/api/energy/types?include_disabled=true&search=${encodeURIComponent(energyCode)}&limit=20`)
  if (types.ok) {
    for (const item of listItems(types.data)) {
      if (item.code === energyCode && item.id) await fetchJson(`/api/energy/types/${item.id}`, { method: "DELETE" })
    }
  }
}

function listItems(payload) {
  if (Array.isArray(payload?.items)) return payload.items
  if (Array.isArray(payload?.data?.items)) return payload.data.items
  return []
}

async function gotoPage(route, requiredTexts = []) {
  apiFailures.length = 0
  await page.goto(`${baseURL}${route}`, { waitUntil: "domcontentloaded" })
  await injectScreenshotCss()
  await waitForPageReady()
  await assertBusinessPage(requiredTexts)
  checks.push({ name: "open-page", status: "passed", route })
}

async function search(placeholder, value) {
  const input = page.getByPlaceholder(placeholder)
  await input.fill(value)
  await page.getByRole("button", { name: "查询" }).click()
  await waitForPageReady()
}

function rowFor(text) {
  return page.locator("tbody tr").filter({ hasText: text }).first()
}

async function waitForRowAbsent(text) {
  const deadline = Date.now() + 10_000
  while (Date.now() < deadline) {
    if ((await rowFor(text).count()) === 0 || !(await rowFor(text).isVisible().catch(() => false))) return
    await page.waitForTimeout(300)
  }
  throw new Error(`删除后列表仍显示：${text}`)
}

async function fillInput(scope, label, value) {
  const labelLocator = scope.locator("label", { hasText: label }).first()
  const control = labelLocator.locator("xpath=ancestor::div[contains(@class, 'grid')][1]//*[self::input or self::textarea]").first()
  await control.fill(value)
}

async function selectOption(scope, label, option) {
  const labelLocator = scope.locator("label", { hasText: label }).first()
  const trigger = labelLocator.locator("xpath=ancestor::div[contains(@class, 'grid')][1]//button[@role='combobox']").first()
  await trigger.click()
  await page.getByRole("option", { name: option, exact: false }).first().click()
}

async function capture(key, note) {
  await injectScreenshotCss()
  await waitForPageReady()
  await waitForUiSettled()
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
  return page.addStyleTag({
    content: `
        [data-sonner-toast] {
          display: none !important;
          visibility: hidden !important;
        }
      `,
  })
}

async function scrollDialogToTop(dialog) {
  await dialog.evaluate((element) => {
    element.scrollTop = 0
    for (const child of element.querySelectorAll("*")) {
      if (child instanceof HTMLElement && child.scrollHeight > child.clientHeight) child.scrollTop = 0
    }
  })
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
        title: "能源主数据维护 CRUD 验证",
        status,
        startedAt,
        finishedAt: new Date().toISOString(),
        baseURL,
        routes: ["/data/energy-types", "/data/energy-unit-conversions"],
        tenantSlug,
        energyCode,
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
