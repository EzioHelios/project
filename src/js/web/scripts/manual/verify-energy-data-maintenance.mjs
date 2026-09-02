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
const verificationPath = path.join(verificationDir, "energy-data-maintenance-crud.json")
const viewport = { width: 1440, height: 900 }
const recordCode = process.env.MANUAL_VERIFY_RECORD_CODE ?? "MANUAL-ENERGY-CRUD-20260901"
const importRecordCode = process.env.MANUAL_VERIFY_IMPORT_RECORD_CODE ?? "MANUAL-ENERGY-IMPORT-20260901"
const sourceSystem = "manual-verification"
let selectedAreaName = ""
let selectedDeviceName = ""
const screenshots = {
  list: "EV-WH-059-能源数据维护列表与查询.png",
  create: "EV-WH-060-能源数据新增表单.png",
  detail: "EV-WH-061-能源数据详情回显.png",
  editForm: "EV-WH-065-能源数据编辑表单.png",
  edit: "EV-WH-062-能源数据编辑后回显.png",
  importResult: "EV-WH-063-能源数据CSV导入结果.png",
  exportResult: "EV-WH-064-能源数据导出结果.png",
  deleteResult: "EV-WH-100-能源数据删除结果.png",
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

const startedAt = new Date().toISOString()
const checks = []
const artifacts = []

try {
  console.log("[ManualVerify] Preflight 100% | Auth 0% | Harness 100% | Navigate 0/1 | Interact 0/8 | Evidence 0/8 | Writeback 0/1")
  await ensureAuthenticated()
  await selectTenant()
  await resolveEnergyDataSelectors()
  await cleanupRecord(recordCode)
  await cleanupRecord(importRecordCode)
  console.log("[ManualVerify] Preflight 100% | Auth 100% | Harness 100% | Navigate 0/1 | Interact 0/8 | Evidence 0/8 | Writeback 0/1")

  await gotoEnergyPage()
  await capture("list", "打开能源数据维护页，列表非空并可见查询、新增、导入、导出入口。")

  await fillCreateFormAndCapture()
  await saveCreateForm()
  await searchRecord(recordCode)
  await expectVisible(recordCode)
  await expectVisible("1280.5")
  await expectVisible("外购电力")

  await openDetail()
  await expectVisible("能源数据维护详情")
  await expectVisible("外购电力")
  await expectVisible("手工录入验证")
  await capture("detail", "打开详情抽屉，核对新增记录字段回显。")
  await page.keyboard.press("Escape")

  await openEditFormAndCapture()
  await saveEditForm()
  await searchRecord(recordCode)
  await expectVisible("1368.75")
  await openDetail()
  await expectVisible("外购电力")
  await expectVisible("编辑后验证")
  await capture("edit", "通过编辑表单调整能源用量和备注，保存后在详情中回显更新值。")
  await page.keyboard.press("Escape")

  await importRecord()
  await expectVisible("服务端入库")
  await expectVisible("接收 1")
  await expectVisible("导入 1")
  await capture("importResult", "上传 CSV 并确认入库，页面显示接收、导入、跳过数量。")
  await page.keyboard.press("Escape")
  await searchRecord(importRecordCode)
  await expectVisible(importRecordCode)

  const download = await exportRecords()
  await capture("exportResult", "执行导出并校验下载 CSV 文件包含能源数据表头。")

  const deleteResult = await deleteCreatedRecords()
  checks.push(deleteResult)
  await writeVerification("passed")
  console.log("[ManualVerify] Preflight 100% | Auth 100% | Harness 100% | Navigate 1/1 | Interact 8/8 | Evidence 8/8 | Writeback 1/1")
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

async function gotoEnergyPage() {
  apiFailures.length = 0
  await page.goto(`${baseURL}/data/energy-consumption`, { waitUntil: "domcontentloaded" })
  await injectScreenshotCss()
  await waitForPageReady()
  await assertBusinessPage(["能源数据维护", "能源数据维护列表", "查询", "新增", "导入能源数据", "导出", "记录编码", "能源用量"])
  checks.push({ name: "open-list", status: "passed", route: "/data/energy-consumption" })
}

async function resolveEnergyDataSelectors() {
  const devicesResponse = await fetchJson("/api/master-data/devices?limit=100&offset=0")
  if (!devicesResponse.ok) throw new Error(`设备列表读取失败：HTTP ${devicesResponse.status}`)
  const devices = Array.isArray(devicesResponse.data?.items) ? devicesResponse.data.items : []
  const device = devices.find((item) => item.name && item.area_name) ?? devices.find((item) => item.name)
  if (!device) throw new Error("能源数据维护验证需要至少一台可选择设备")
  selectedDeviceName = String(device.name)
  selectedAreaName = String(device.area_name ?? "")
  if (!selectedAreaName && device.area_id) {
    const areasResponse = await fetchJson("/api/master-data/areas/tree")
    if (!areasResponse.ok) throw new Error(`区域树读取失败：HTTP ${areasResponse.status}`)
    const area = flattenRows(areasResponse.data?.items ?? []).find((item) => String(item.id) === String(device.area_id))
    selectedAreaName = String(area?.name ?? "")
  }
  if (!selectedAreaName) throw new Error("能源数据维护验证需要设备挂载到区域")
  checks.push({ name: "resolve-selectors", status: "passed", selectedAreaName, selectedDeviceName })
}

async function fillCreateFormAndCapture() {
  await page.getByRole("button", { name: "新增" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "新增能源数据维护" })
  await dialog.waitFor({ state: "visible" })
  await fillInput(dialog, "记录编码", recordCode)
  await selectOption(dialog, "能源种类", "外购电力")
  await fillInput(dialog, "能源用量", "1280.5")
  await fillInput(dialog, "单位", "kWh")
  await fillInput(dialog, "开始日期", "2026-09-01")
  await fillInput(dialog, "结束日期", "2026-09-01")
  await selectOption(dialog, "时间粒度", "日")
  await selectOption(dialog, "数据质量", "手工")
  await fillInput(dialog, "数据来源", sourceSystem)
  await selectOption(dialog, "区域", selectedAreaName)
  await selectOption(dialog, "设备", selectedDeviceName)
  await fillInput(dialog, "用能系统名称", "仓储照明")
  await fillInput(dialog, "备注", "手工录入验证")
  await scrollDialogToTop(dialog)
  await capture("create", "新增能源数据表单填写态，展示能源种类、用量、周期、区域、设备和用能系统。")
}

async function saveCreateForm() {
  const dialog = page.getByRole("dialog").filter({ hasText: "新增能源数据维护" })
  await dialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("新增成功")
  await waitForPageReady()
  checks.push({ name: "create", status: "passed", recordCode })
}

async function openDetail() {
  await rowFor(recordCode).getByRole("button", { name: "详情" }).click()
  checks.push({ name: "read-detail", status: "passed", recordCode })
}

async function openEditFormAndCapture() {
  await rowFor(recordCode).getByRole("button", { name: "编辑" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "编辑能源数据维护" })
  await dialog.waitFor({ state: "visible" })
  await fillInput(dialog, "能源用量", "1368.75")
  await fillInput(dialog, "备注", "编辑后验证")
  await scrollDialogToTop(dialog)
  await capture("editForm", "编辑能源数据表单填写态，展示原记录字段回填并修改能源用量和备注。")
}

async function saveEditForm() {
  const dialog = page.getByRole("dialog").filter({ hasText: "编辑能源数据维护" })
  await dialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("更新成功")
  await waitForPageReady()
  checks.push({ name: "update", status: "passed", recordCode })
}

async function importRecord() {
  await cleanupRecord(importRecordCode)
  const fixture = path.join(verificationDir, "energy-data-import.csv")
  await fs.writeFile(
    fixture,
    [
      "记录编码,能源种类编码,开始时间,结束时间,能源用量,单位,数据来源,设备编码,设备名称,区域名称,用能系统名称,时间粒度,数据质量,备注",
      `${importRecordCode},diesel,2026-09-01,2026-09-01,86.4,L,${sourceSystem},TZ-FORKLIFT-DIESEL-001,柴油叉车,泰州生产基地/装卸区,叉车作业,day,imported,CSV导入验证`,
      "",
    ].join("\n"),
  )
  await page.getByTestId("energy-interval-import-trigger").click()
  const dialog = page.getByRole("dialog").filter({ hasText: "导入能源数据" })
  await dialog.waitFor({ state: "visible" })
  await page.getByTestId("energy-interval-import-file").setInputFiles(fixture)
  await expectVisible("已读取 1 条记录")
  await page.getByTestId("energy-interval-import-submit").click()
  await expectVisible("导入完成")
  await waitForPageReady()
  checks.push({ name: "import", status: "passed", recordCode: importRecordCode })
}

async function exportRecords() {
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "导出" }).click()])
  const target = path.join(verificationDir, download.suggestedFilename())
  await download.saveAs(target)
  const text = await fs.readFile(target, "utf8")
  if (!text.includes("source_record_id") || !text.includes("energy_type_code") || !text.includes("amount")) {
    throw new Error("导出 CSV 缺少能源数据关键表头")
  }
  await expectVisible("导出成功")
  const result = { name: "export", status: "passed", file: target, size: Buffer.byteLength(text) }
  checks.push(result)
  return result
}

async function deleteCreatedRecords() {
  const deleted = []
  for (const code of [recordCode, importRecordCode]) {
    const row = await getRecordByCode(code)
    if (!row?.id) continue
    await searchRecord(code)
    await rowFor(code).getByRole("button", { name: "删除" }).click()
    await expectVisible("删除成功")
    await waitForRecordDeleted(code)
    if (code === recordCode) {
      await capture("deleteResult", "删除能源数据后按记录编码查询，列表不再显示该记录。")
    }
    deleted.push(code)
  }
  return { name: "delete-by-ui", status: "passed", deleted }
}

async function waitForRecordDeleted(code) {
  const deadline = Date.now() + 10_000
  while (Date.now() < deadline) {
    const exists = await getRecordByCode(code)
    if (!exists?.id) return
    await page.waitForTimeout(300)
  }
  throw new Error(`删除后仍可查到验证记录：${code}`)
}

async function cleanupRecord(code) {
  const row = await getRecordByCode(code)
  if (!row?.id) return
  const result = await fetchJson(`/api/energy/interval-facts/${row.id}`, { method: "DELETE" })
  if (!result.ok && result.status !== 404) throw new Error(`清理历史验证记录失败：${code} HTTP ${result.status}`)
}

async function getRecordByCode(code) {
  const response = await fetchJson(`/api/energy/interval-facts?search=${encodeURIComponent(code)}&limit=20`)
  if (!response.ok) throw new Error(`记录查询失败：${code} HTTP ${response.status}`)
  const items = Array.isArray(response.data?.items) ? response.data.items : []
  return items.find((item) => item.source_record_id === code) ?? null
}

async function searchRecord(code) {
  const input = page.getByPlaceholder("搜索记录编码、能源种类、区域、设备")
  await input.fill(code)
  await page.getByRole("button", { name: "查询" }).click()
  await waitForPageReady()
  await expectVisible(code)
}

function rowFor(text) {
  return page.locator("tbody tr").filter({ hasText: text }).first()
}

async function fillInput(scope, label, value) {
  const labelLocator = scope.locator("label", { hasText: label }).first()
  const control = labelLocator.locator("xpath=ancestor::div[contains(@class, 'grid')][1]//*[self::input or self::textarea]").first()
  const readonly = await control.evaluate((element) => element instanceof HTMLInputElement && element.readOnly).catch(() => false)
  const placeholder = await control.getAttribute("placeholder").catch(() => null)
  if (readonly && placeholder === "选择日期") {
    await selectDate(control, value)
    return
  }
  await control.fill(value)
}

async function selectDate(control, value) {
  const match = /^\d{4}-\d{2}-(\d{2})$/.exec(value)
  if (!match) throw new Error(`日期值格式无效：${value}`)
  await control.click()
  const day = String(Number(match[1]))
  await page.locator(".rounded-lg.border.border-border.bg-popover").last().getByRole("button", { name: day, exact: true }).first().click()
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

function flattenRows(rows) {
  return rows.flatMap((row) => [row, ...flattenRows(Array.isArray(row.children) ? row.children : [])])
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
        title: "能源数据维护 CRUD 与导入导出验证",
        status,
        startedAt,
        finishedAt: new Date().toISOString(),
        baseURL,
        route: "/data/energy-consumption",
        tenantSlug,
        recordCode,
        importRecordCode,
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
