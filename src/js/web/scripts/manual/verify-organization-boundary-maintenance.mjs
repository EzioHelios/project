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
const verificationPath = path.join(verificationDir, "organization-boundary-maintenance.json")
const viewport = { width: 1440, height: 900 }
const suffix = new Date().toISOString().replace(/\D/g, "").slice(0, 14)
const displaySuffix = suffix.slice(8, 12)
const organizationCode = `WH-OP-ORG-${suffix}`
const organizationName = `沃衡汽车泰州生产基地盘查主体-${displaySuffix}`
const organizationNameEdited = `${organizationName}-更新`
const periodCode = `WH-OP-RP-${suffix}`
const periodName = `2026年9月组织温室气体盘查期-${displaySuffix}`
const periodNameEdited = `${periodName}-更新`
const boundaryNo = `WH-OP-BND-${suffix}`
const boundaryName = `泰州生产基地组织边界-${displaySuffix}`
const boundaryNameEdited = `${boundaryName}-更新`
const facilityCode = `WH-OP-FAC-${suffix}`
const facilityName = `泰州生产基地运营边界设施-${displaySuffix}`
const facilityNameEdited = `${facilityName}-更新`
const screenshots = {
  page: "EV-WH-133-组织与核算边界维护页.png",
  organizationCreate: "EV-WH-134-报告主体新增表单.png",
  organizationEdited: "EV-WH-135-报告主体编辑回显.png",
  periodCreate: "EV-WH-136-报告期新增表单.png",
  periodEdited: "EV-WH-137-报告期编辑回显.png",
  boundaryCreate: "EV-WH-138-组织边界版本新增表单.png",
  boundaryEdited: "EV-WH-139-组织边界版本编辑回显.png",
  facilityCreate: "EV-WH-140-边界设施维护表单.png",
  facilityEdited: "EV-WH-141-边界设施编辑回显.png",
  boundaryPublished: "EV-WH-142-组织边界发布结果.png",
  boundaryDeleted: "EV-WH-143-组织边界删除结果.png",
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
const context = await browser.newContext({ viewport, deviceScaleFactor: 1 })
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
let createdOrganizationId = null
let createdPeriodId = null
let createdBoundaryId = null
let createdFacilityId = null

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
  console.log("[BoundaryVerify] Auth 0% | Maintenance 0/12 | Evidence 0/11 | Cleanup 0/1")
  await ensureAuthenticated()
  await selectTenant()
  await cleanupVerificationData()
  console.log("[BoundaryVerify] Auth 100% | Maintenance 0/12 | Evidence 0/11 | Cleanup 0/1")

  await gotoBoundaryPage()
  await capture("page", "核算边界页面展示报告主体、报告期、组织边界版本、边界设施和核算边界配置。")

  await createOrganization()
  await editOrganization()
  await createPeriod()
  await editPeriod()
  await createBoundary()
  await editBoundary()
  await createFacility()
  await editFacility()
  await deleteFacilityByUi()
  await generateSourceFacilityAndPublish()
  await archiveAndDeleteBoundary()
  await deletePeriodAndOrganization()

  await cleanupVerificationData()
  await writeVerification("passed")
  console.log("[BoundaryVerify] Auth 100% | Maintenance 12/12 | Evidence 11/11 | Cleanup 1/1")
} catch (error) {
  await writeVerification("failed", error)
  console.error(error)
  process.exitCode = 1
} finally {
  await browser.close()
}

async function gotoBoundaryPage() {
  apiFailures.length = 0
  await page.goto(`${baseURL}/carbon/organization/boundary`, { waitUntil: "domcontentloaded" })
  await injectScreenshotCss()
  await waitForPageReady()
  await assertBusinessPage(["核算边界", "报告主体", "报告期", "组织边界版本", "边界设施"])
  checks.push({ name: "open-boundary-page", status: "passed", route: "/carbon/organization/boundary" })
}

async function createOrganization() {
  await page.getByRole("button", { name: "新增主体" }).click()
  const dialog = currentDialog("新增报告主体")
  await fillInput(dialog, "主体编号", organizationCode)
  await fillInput(dialog, "主体名称", organizationName)
  await fillInput(dialog, "统一社会信用代码", "91320000MANUAL2026X")
  await selectOption(dialog, "边界方法", "运营控制权")
  await capture("organizationCreate", "新增报告主体表单填写态，包含主体编号、名称、统一社会信用代码和控制方法。")
  await dialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("报告主体已创建")
  await waitForPageReady()
  await expectVisible(organizationName)
  const organization = await findOrganization()
  createdOrganizationId = organization.id
  checks.push({ name: "organization-create", status: "passed", id: createdOrganizationId })
}

async function editOrganization() {
  await rowFor(organizationCode).getByRole("button", { name: "编辑" }).click()
  const dialog = currentDialog("编辑报告主体")
  await fillInput(dialog, "主体名称", organizationNameEdited)
  await dialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("报告主体已更新")
  await waitForPageReady()
  await expectVisible(organizationNameEdited)
  await capture("organizationEdited", "报告主体编辑后列表回显更新后的主体名称和控制方法。")
  checks.push({ name: "organization-edit", status: "passed" })
}

async function createPeriod() {
  await page.getByRole("button", { name: "新增报告期" }).click()
  const dialog = currentDialog("新增报告期")
  await selectOption(dialog, "报告主体", organizationNameEdited)
  await fillInput(dialog, "报告期编号", periodCode)
  await fillInput(dialog, "报告期名称", periodName)
  await fillInput(dialog, "开始日期", "2026-09-01")
  await fillInput(dialog, "结束日期", "2026-09-30")
  await capture("periodCreate", "新增报告期表单填写态，报告期挂接到已维护的报告主体。")
  await dialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("报告期已创建")
  await waitForPageReady()
  await expectVisible(periodName)
  const period = await findPeriod()
  createdPeriodId = period.id
  checks.push({ name: "period-create", status: "passed", id: createdPeriodId })
}

async function editPeriod() {
  await rowFor(periodCode).getByRole("button", { name: "编辑" }).click()
  const dialog = currentDialog("编辑报告期")
  await fillInput(dialog, "报告期名称", periodNameEdited)
  await dialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("报告期已更新")
  await waitForPageReady()
  await expectVisible(periodNameEdited)
  await capture("periodEdited", "报告期编辑后列表回显更新后的期间名称和起止日期。")
  checks.push({ name: "period-edit", status: "passed" })
}

async function createBoundary() {
  await page.getByRole("button", { name: "新增边界" }).click()
  const dialog = currentDialog("新增边界版本")
  await selectOption(dialog, "报告主体", organizationNameEdited)
  await selectOption(dialog, "报告期", periodNameEdited)
  await fillInput(dialog, "边界编号", boundaryNo)
  await fillInput(dialog, "边界名称", boundaryName)
  await selectOption(dialog, "边界方法", "运营控制权")
  await capture("boundaryCreate", "新增组织边界版本表单填写态，边界版本挂接到报告主体和报告期。")
  await dialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("边界版本已创建")
  await waitForPageReady()
  await expectVisible(boundaryName)
  const boundary = await findBoundary()
  createdBoundaryId = boundary.id
  checks.push({ name: "boundary-create", status: "passed", id: createdBoundaryId })
}

async function editBoundary() {
  await rowFor(boundaryNo).getByRole("button", { name: "编辑" }).click()
  const dialog = currentDialog("编辑边界版本")
  await fillInput(dialog, "边界名称", boundaryNameEdited)
  await dialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("边界版本已更新")
  await waitForPageReady()
  await expectVisible(boundaryNameEdited)
  await capture("boundaryEdited", "组织边界版本编辑后列表回显更新后的边界名称。")
  checks.push({ name: "boundary-edit", status: "passed" })
}

async function createFacility() {
  await page.getByRole("button", { name: "维护设施" }).click()
  const dialog = currentDialog("维护边界设施")
  await selectOption(dialog, "组织边界", boundaryNameEdited)
  await selectOption(dialog, "设施类型", "区域")
  await fillInput(dialog, "设施编号", facilityCode)
  await fillInput(dialog, "设施名称", facilityName)
  await fillInput(dialog, "设施角色", "运营边界")
  await selectOption(dialog, "纳入边界", "纳入")
  await capture("facilityCreate", "边界设施维护表单填写态，设施挂接到组织边界版本并设置纳入状态。")
  await dialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("边界设施已维护")
  await waitForPageReady()
  await expectVisible(facilityName)
  const facility = await findFacility()
  createdFacilityId = facility.id
  checks.push({ name: "facility-create", status: "passed", id: createdFacilityId })
}

async function editFacility() {
  await rowFor(facilityCode).getByRole("button", { name: "编辑" }).click()
  const dialog = currentDialog("编辑边界设施")
  await fillInput(dialog, "设施名称", facilityNameEdited)
  await dialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("边界设施已更新")
  await waitForPageReady()
  await expectVisible(facilityNameEdited)
  await capture("facilityEdited", "边界设施编辑后列表回显更新后的设施名称。")
  checks.push({ name: "facility-edit", status: "passed" })
}

async function deleteFacilityByUi() {
  await rowFor(facilityCode).getByRole("button", { name: "删除" }).click()
  await expectVisible("边界设施已删除")
  await waitForFacilityDeleted()
  checks.push({ name: "facility-delete", status: "passed" })
}

async function generateSourceFacilityAndPublish() {
  const boundaryRow = rowFor(boundaryNo)
  await boundaryRow.getByRole("button", { name: "生成设施" }).click()
  await expectVisible("来源边界设施已生成")
  await waitForPageReady()
  await expectVisible("1 纳入")
  await boundaryRow.getByRole("button", { name: "发布" }).click()
  await expectVisible("组织边界已发布")
  await waitForPageReady()
  await expectVisible("已发布")
  await capture("boundaryPublished", "组织边界生成来源设施后发布，列表显示已发布状态和纳入设施数量。")
  checks.push({ name: "boundary-publish", status: "passed" })
}

async function archiveAndDeleteBoundary() {
  const boundaryRow = rowFor(boundaryNo)
  await boundaryRow.getByRole("button", { name: "归档" }).click()
  await expectVisible("边界版本已归档")
  await waitForPageReady()
  await rowFor(boundaryNo).getByRole("button", { name: "删除" }).click()
  await expectVisible("边界版本已删除")
  await waitForBoundaryDeleted()
  await capture("boundaryDeleted", "组织边界归档并删除后，按边界编号查询不到该验证边界。")
  checks.push({ name: "boundary-archive-delete", status: "passed" })
}

async function deletePeriodAndOrganization() {
  await rowFor(periodCode).getByRole("button", { name: "删除" }).click()
  await expectVisible("报告期已删除")
  await waitForPeriodDeleted()
  await rowFor(organizationCode).getByRole("button", { name: "删除" }).click()
  await expectVisible("报告主体已删除")
  await waitForOrganizationDeleted()
  checks.push({ name: "period-and-organization-delete", status: "passed" })
}

async function cleanupVerificationData() {
  const boundaries = await listBoundaries()
  for (const boundary of boundaries.filter((item) => String(item.boundary_no ?? "").startsWith("MANUAL-BND-") || String(item.boundary_no ?? "").startsWith("WH-OP-BND-"))) {
    if (boundary.status === "published") {
      await fetchJson(`/api/carbon/organization-boundary/boundaries/${boundary.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ status: "archived" }),
      })
    }
    await fetchJson(`/api/carbon/organization-boundary/boundaries/${boundary.id}`, { method: "DELETE" })
  }
  for (const period of (await listPeriods()).filter((item) => String(item.code ?? "").startsWith("MANUAL-RP-") || String(item.code ?? "").startsWith("WH-OP-RP-"))) {
    await fetchJson(`/api/carbon/organization-boundary/periods/${period.id}`, { method: "DELETE" })
  }
  for (const organization of (await listOrganizations()).filter((item) => String(item.code ?? "").startsWith("MANUAL-ORG-") || String(item.code ?? "").startsWith("WH-OP-ORG-"))) {
    await fetchJson(`/api/carbon/organization-boundary/organizations/${organization.id}`, { method: "DELETE" })
  }
}

async function waitForOrganizationDeleted() {
  await waitUntil(async () => !(await findOrganization(false)), `删除后仍可查到报告主体：${organizationCode}`)
}

async function waitForPeriodDeleted() {
  await waitUntil(async () => !(await findPeriod(false)), `删除后仍可查到报告期：${periodCode}`)
}

async function waitForBoundaryDeleted() {
  await waitUntil(async () => !(await findBoundary(false)), `删除后仍可查到组织边界：${boundaryNo}`)
}

async function waitForFacilityDeleted() {
  await waitUntil(async () => !(await findFacility(false)), `删除后仍可查到边界设施：${facilityCode}`)
}

async function waitUntil(predicate, failureMessage) {
  const deadline = Date.now() + 10_000
  while (Date.now() < deadline) {
    if (await predicate()) return
    await page.waitForTimeout(300)
  }
  throw new Error(failureMessage)
}

async function findOrganization(required = true) {
  const item = (await listOrganizations()).find((row) => row.code === organizationCode)
  if (required && !item) throw new Error(`未找到报告主体：${organizationCode}`)
  return item ?? null
}

async function findPeriod(required = true) {
  const item = (await listPeriods()).find((row) => row.code === periodCode)
  if (required && !item) throw new Error(`未找到报告期：${periodCode}`)
  return item ?? null
}

async function findBoundary(required = true) {
  const item = (await listBoundaries()).find((row) => row.boundary_no === boundaryNo)
  if (required && !item) throw new Error(`未找到组织边界：${boundaryNo}`)
  return item ?? null
}

async function findFacility(required = true) {
  const item = (await listFacilities()).find((row) => row.facility_code === facilityCode)
  if (required && !item) throw new Error(`未找到边界设施：${facilityCode}`)
  return item ?? null
}

async function listOrganizations() {
  const response = await fetchJson("/api/carbon/organization-boundary/organizations?limit=200")
  if (!response.ok) throw new Error(`报告主体查询失败：HTTP ${response.status}`)
  return pageItems(response.data)
}

async function listPeriods() {
  const response = await fetchJson("/api/carbon/organization-boundary/periods?limit=200")
  if (!response.ok) throw new Error(`报告期查询失败：HTTP ${response.status}`)
  return pageItems(response.data)
}

async function listBoundaries() {
  const response = await fetchJson("/api/carbon/organization-boundary/boundaries?limit=200")
  if (!response.ok) throw new Error(`组织边界查询失败：HTTP ${response.status}`)
  return pageItems(response.data)
}

async function listFacilities() {
  if (!createdBoundaryId) return []
  const response = await fetchJson(`/api/carbon/organization-boundary/facilities?boundary_id=${createdBoundaryId}&limit=200`)
  if (!response.ok) throw new Error(`边界设施查询失败：HTTP ${response.status}`)
  return pageItems(response.data)
}

function pageItems(data) {
  return data?.data?.items ?? data?.items ?? []
}

function currentDialog(title) {
  return page.getByRole("dialog").filter({ hasText: title })
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
        title: "组织边界与核算边界维护验证",
        status,
        startedAt,
        finishedAt: new Date().toISOString(),
        baseURL,
        route: "/carbon/organization/boundary",
        tenantSlug,
        organizationCode,
        periodCode,
        boundaryNo,
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
