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
const tenantSlug = process.env.E2E_TENANT_SLUG ?? "woheng-huzhou-production-base"
const outputDir = path.resolve(process.env.MANUAL_VERIFY_OUTPUT_DIR ?? path.join(repositoryRoot, "outputs/woheng-showcase-woheng-full-evidence"))
const screenshotDir = path.join(outputDir, "screenshots")
const verificationDir = path.join(outputDir, "manual-verification")
const verificationPath = path.join(verificationDir, "inventory-report-management.json")
const viewport = { width: 1440, height: 900 }
const screenshots = {
  list: "EV-WH-171-盘查报告台账.png",
  detail: "EV-WH-172-盘查报告详情.png",
  exportResult: "EV-WH-173-Word报告导出结果.png",
}
const demoBrand = { displayName: "沃衡汽车能碳管理平台", shortName: "WH" }
const forbiddenBrandTexts = ["中汽信科", "奇瑞", "Chery", "安方", "祥泰", "华东绿色仓储", "碳数据收集与管理系统"]
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
let report = null
let downloadedReport = null

await context.route("**/api/**", async (route) => {
  if (route.request().url().endsWith("/api/config/public")) {
    const response = await route.fetch()
    const data = await response.json().catch(() => ({}))
    await route.fulfill({
      response,
      json: {
        ...data,
        displayName: demoBrand.displayName,
        shortName: demoBrand.shortName,
        brandMarkUrl: null,
      },
    })
    return
  }
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
  await resolveReport()
  await captureReportList()
  await captureReportDetail()
  await captureReportExport()
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

async function resolveReport() {
  const response = await fetchJson("/api/ghg-inventory/reports?limit=100")
  if (!response.ok) throw new Error(`盘查报告列表读取失败：HTTP ${response.status}`)
  const reports = response.data?.items ?? []
  report =
    reports.find((item) => item.status === "published") ??
    reports.find((item) => item.status === "approved") ??
    reports.find((item) => item.status === "submitted") ??
    reports[0]
  if (!report?.reportCode || !report.version) throw new Error(`当前租户没有可用于手册验证的盘查报告：${tenantSlug}`)
  checks.push({ name: "report-context", status: "passed", reportCode: report.reportCode, version: report.version, reportStatus: report.status })
}

async function captureReportList() {
  apiFailures.length = 0
  await page.goto(`${baseURL}/carbon/organization/reports`, { waitUntil: "domcontentloaded" })
  await injectScreenshotCss()
  await waitForPageReady()
  await assertBusinessPage(["核算报告", "历史核算报告", report.reportCode, "导出 Word"])
  await capture("list", "盘查报告台账展示报告编号、版本、状态、核算运行、排放量和导出入口。")
}

async function captureReportDetail() {
  apiFailures.length = 0
  await page.goto(`${baseURL}/carbon/organization/reports/${encodeURIComponent(report.reportCode)}/${report.version}`, { waitUntil: "domcontentloaded" })
  await injectScreenshotCss()
  await waitForPageReady()
  await assertBusinessPage([report.reportCode, "报告信息", "报告快照", "流转记录", "导出 Word"])
  await capture("detail", "盘查报告详情展示报告信息、核算快照、证据覆盖和状态流转记录。")
}

async function captureReportExport() {
  apiFailures.length = 0
  const downloadPromise = page.waitForEvent("download", { timeout: 30_000 })
  await page.getByRole("button", { name: "导出 Word" }).first().click()
  const download = await downloadPromise
  const filename = download.suggestedFilename()
  const savePath = path.join(verificationDir, filename)
  await download.saveAs(savePath)
  downloadedReport = savePath
  await expectVisible("Word报告已导出")
  await capture("exportResult", `Word 报告已导出，文件名：${filename}`, { keepToast: true })
  checks.push({ name: "report-export", status: "passed", filename, path: savePath })
}

async function capture(key, note, options = {}) {
  await injectScreenshotCss()
  await waitForPageReady()
  await assertBusinessPage()
  const file = path.join(screenshotDir, screenshots[key])
  const toastStyle = options.keepToast ? null : await hideToastForScreenshot()
  try {
    await page.screenshot({ path: file, fullPage: false })
  } finally {
    await toastStyle?.evaluate((element) => element.remove()).catch(() => {})
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
        title: "盘查报告管理与导出验证",
        status,
        startedAt,
        finishedAt: new Date().toISOString(),
        baseURL,
        tenantSlug,
        report,
        downloadedReport,
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
