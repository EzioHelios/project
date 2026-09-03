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
const verificationPath = path.join(verificationDir, "energy-balance-maintenance.json")
const viewport = { width: 1440, height: 900 }
const stamp = process.env.MANUAL_VERIFY_STAMP ?? new Date().toISOString().replace(/\D/g, "").slice(0, 14)
const boundaryCode = `MANUAL-BALANCE-${stamp}`
const boundaryName = "手册验证计量边界"
const boundaryNameEdited = "手册验证计量边界-已编辑"
const memberCode = `MANUAL-BALANCE-MEMBER-${stamp}`
const memberCodeEdited = `MANUAL-BALANCE-MEMBER-${stamp}-EDITED`

const screenshots = {
  calculation: "EV-WH-157-能量平衡计算结果.png",
  diagnostics: "EV-WH-158-能量平衡差异诊断.png",
  boundaryList: "EV-WH-159-能量平衡计量边界列表.png",
  boundaryCreate: "EV-WH-160-能量平衡新增计量边界.png",
  boundaryEdit: "EV-WH-161-能量平衡编辑计量边界.png",
  memberList: "EV-WH-162-能量平衡边界成员列表.png",
  memberCreate: "EV-WH-163-能量平衡新增边界成员.png",
  memberEdit: "EV-WH-164-能量平衡编辑边界成员.png",
  memberDeleted: "EV-WH-165-能量平衡边界成员删除结果.png",
  boundaryDeleted: "EV-WH-166-能量平衡计量边界删除结果.png",
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
let createdBoundaryId = null
let createdMemberId = null
let selectedEquipment = null

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
  console.log("[ManualVerify] Preflight 100% | Auth 0% | Harness 0% | Navigate 0/1 | Interact 0/10 | Evidence 0/10 | Writeback 0/1")
  await ensureAuthenticated()
  await selectTenant()
  await cleanupCreatedRecords()
  selectedEquipment = await resolveEquipment()
  apiFailures.length = 0
  consoleErrors.length = 0
  console.log("[ManualVerify] Preflight 100% | Auth 100% | Harness 100% | Navigate 0/1 | Interact 0/10 | Evidence 0/10 | Writeback 0/1")

  await verifyBalanceCalculationAndDiagnostics()
  await verifyBoundaryCrud()
  await verifyMemberCrud()
  await cleanupCreatedRecords()
  checks.push({ name: "cleanup", status: "passed", boundaryCode, memberCode })
  await writeVerification("passed")
  console.log("[ManualVerify] Preflight 100% | Auth 100% | Harness 100% | Navigate 1/1 | Interact 10/10 | Evidence 10/10 | Writeback 1/1")
} catch (error) {
  await writeVerification("failed", error)
  console.error(error)
  process.exitCode = 1
} finally {
  await browser.close()
}

async function verifyBalanceCalculationAndDiagnostics() {
  await gotoPage("/energy/balance", ["能量平衡", "边界输入", "已归集用能", "平衡误差率"])
  await expectVisible("沃衡汽车泰州生产基地外购电力计量边界")
  await expectVisible("已闭合")
  await capture("calculation", "平衡计算页展示边界输入、已归集用能、未归集差异和平衡误差率。")
  checks.push({ name: "calculation", status: "passed" })

  await page.getByRole("tab", { name: "差异诊断" }).click()
  await waitForPageReady()
  await assertBusinessPage(["差异诊断", "边界已闭合"])
  await capture("diagnostics", "差异诊断页展示当前计量边界的闭合状态。")
  checks.push({ name: "diagnostics", status: "passed" })
}

async function verifyBoundaryCrud() {
  await page.getByRole("tab", { name: "计量边界" }).click()
  await waitForPageReady()
  await assertBusinessPage(["计量边界", "外购电力计量边界", "新增边界"])
  await capture("boundaryList", "计量边界列表展示已有边界、输入表、区域、状态和操作。")
  checks.push({ name: "boundary-list", status: "passed" })

  await page.getByRole("button", { name: "新增边界" }).click()
  await expectVisible("新增计量边界")
  await fillLabeledField("边界编码", boundaryCode)
  await fillLabeledField("边界名称", boundaryName)
  await chooseSelect("边界类型", "分项边界")
  await chooseSelect("输入表", selectedEquipment.name)
  await chooseSelect("覆盖区域", selectedEquipment.sectorName)
  await fillLabeledField("用能系统编码", "manual_balance")
  await fillLabeledField("来源", "手册验证")
  await fillLabeledField("备注", "计量边界 CRUD 验证")
  await capture("boundaryCreate", "新增计量边界表单填写边界编码、名称、类型、输入表和覆盖区域。")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible(boundaryName)
  const created = await findBoundary(boundaryCode)
  createdBoundaryId = created.id
  checks.push({ name: "boundary-create", status: "passed", boundaryId: createdBoundaryId })

  await clickRowAction(boundaryName, "编辑")
  await expectVisible("编辑计量边界")
  await fillLabeledField("边界名称", boundaryNameEdited)
  await fillLabeledField("备注", "计量边界编辑验证")
  await capture("boundaryEdit", "编辑计量边界表单回显已保存字段并修改名称。")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible(boundaryNameEdited)
  checks.push({ name: "boundary-edit", status: "passed", boundaryId: createdBoundaryId })
}

async function verifyMemberCrud() {
  await clickRowAction(boundaryNameEdited, "选择")
  await page.getByRole("tab", { name: "边界成员" }).click()
  await waitForPageReady()
  await assertBusinessPage(["边界成员", "新增成员"])
  await capture("memberList", "边界成员列表展示当前计量边界的成员维护入口。")
  checks.push({ name: "member-list", status: "passed" })

  await page.getByRole("button", { name: "新增成员" }).click()
  await expectVisible("新增边界成员")
  await fillLabeledField("成员编码", memberCode)
  await chooseSelect("成员类型", "设备")
  await chooseSelect("成员角色", "归集成员")
  await chooseSelect("设备", selectedEquipment.name)
  await chooseSelect("区域", selectedEquipment.sectorName)
  await fillLabeledField("归集权重", "1")
  await fillLabeledField("来源", "手册验证")
  await fillLabeledField("备注", "边界成员 CRUD 验证")
  await capture("memberCreate", "新增边界成员表单选择成员类型、角色、设备、区域和归集权重。")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible(memberCode)
  const created = await findMember(memberCode)
  createdMemberId = created.id
  checks.push({ name: "member-create", status: "passed", memberId: createdMemberId })

  await clickRowAction(memberCode, "编辑")
  await expectVisible("编辑边界成员")
  await fillLabeledField("成员编码", memberCodeEdited)
  await fillLabeledField("备注", "边界成员编辑验证")
  await capture("memberEdit", "编辑边界成员表单回显已保存字段并修改成员编码。")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible(memberCodeEdited)
  checks.push({ name: "member-edit", status: "passed", memberId: createdMemberId })

  await clickIconOnlyDeleteInRow(memberCodeEdited)
  await waitForPageReady()
  await page.locator("tr", { hasText: memberCodeEdited }).waitFor({ state: "detached", timeout: 20_000 })
  await capture("memberDeleted", "删除边界成员后，列表中不再显示该成员。")
  checks.push({ name: "member-delete", status: "passed", memberId: createdMemberId })
  createdMemberId = null

  await page.getByRole("tab", { name: "计量边界" }).click()
  await waitForPageReady()
  await clickIconOnlyDeleteInRow(boundaryNameEdited)
  await waitForPageReady()
  await page.locator("tr", { hasText: boundaryNameEdited }).waitFor({ state: "detached", timeout: 20_000 })
  await capture("boundaryDeleted", "删除未被能源事实引用的临时计量边界后，列表中不再显示该边界。")
  checks.push({ name: "boundary-delete", status: "passed", boundaryId: createdBoundaryId })
  createdBoundaryId = null
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

async function resolveEquipment() {
  const [devicesResponse, areasResponse] = await Promise.all([
    fetchJson("/api/master-data/devices?limit=500&offset=0"),
    fetchJson("/api/master-data/areas/tree"),
  ])
  if (!devicesResponse.ok) throw new Error(`设备列表读取失败：HTTP ${devicesResponse.status}`)
  if (!areasResponse.ok) throw new Error(`区域树读取失败：HTTP ${areasResponse.status}`)
  const devices = extractItems(devicesResponse.data)
  const areas = flattenRows(extractItems(areasResponse.data)).filter((item) => item.name && String(item.code ?? "").toUpperCase() !== "ROOT")
  const device =
    devices.find((item) => item.name && readableText(item.area_name ?? item.sector_name)) ??
    devices.find((item) => item.name && item.sector_id) ??
    devices.find((item) => item.name)
  if (!device?.name) throw new Error("能量平衡验证需要至少一台设备。")
  const sectorName = readableText(device.area_name ?? device.sector_name) ? (device.area_name ?? device.sector_name) : areas[0]?.name
  if (!sectorName) throw new Error("能量平衡验证需要至少一个已维护的区域。")
  checks.push({ name: "device-and-area-options", status: "passed", deviceName: device.name, sectorName })
  return { id: device.id, name: String(device.name), sectorName: String(sectorName) }
}

function extractItems(payload) {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.items)) return payload.items
  if (Array.isArray(payload?.data?.items)) return payload.data.items
  return []
}

function readableText(value) {
  return Boolean(value && value !== "未选择" && value !== "none")
}

function flattenRows(rows) {
  const result = []
  const visit = (row) => {
    result.push(row)
    for (const child of row.children ?? []) visit(child)
  }
  for (const row of rows) visit(row)
  return result
}

async function cleanupCreatedRecords() {
  const members = await fetchJson(`/api/energy/balance/boundary-members?limit=200`)
  for (const member of members.data?.items ?? []) {
    if (String(member.member_code ?? "").startsWith("MANUAL-BALANCE-MEMBER-")) {
      await fetchJson(`/api/energy/balance/boundary-members/${member.id}`, { method: "DELETE" }).catch(() => null)
    }
  }
  const response = await fetchJson(`/api/energy/balance/boundaries?keyword=${encodeURIComponent("MANUAL-BALANCE")}&limit=200`)
  for (const boundary of response.data?.items ?? []) {
    await fetchJson(`/api/energy/balance/boundaries/${boundary.id}`, { method: "DELETE" }).catch(() => null)
  }
  createdBoundaryId = null
  createdMemberId = null
}

async function findBoundary(code) {
  const response = await fetchJson(`/api/energy/balance/boundaries?keyword=${encodeURIComponent(code)}&limit=20`)
  if (!response.ok) throw new Error(`计量边界查询失败：HTTP ${response.status}`)
  const boundary = response.data?.items?.find((item) => item.code === code)
  if (!boundary?.id) throw new Error(`未找到计量边界：${code}`)
  return boundary
}

async function findMember(code) {
  const response = await fetchJson(`/api/energy/balance/boundary-members?boundary_id=${createdBoundaryId}&limit=200`)
  if (!response.ok) throw new Error(`边界成员查询失败：HTTP ${response.status}`)
  const member = response.data?.items?.find((item) => item.member_code === code)
  if (!member?.id) throw new Error(`未找到边界成员：${code}`)
  return member
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
  await page.screenshot({ path: filepath, fullPage: false })
  artifacts.push({ id: key, title, path: filepath, file: filename, route: new URL(page.url()).pathname })
}

async function fillLabeledField(label, value) {
  const field = page.getByLabel(label).first()
  await field.fill(value)
}

async function chooseSelect(label, optionText) {
  const field = page.getByLabel(label).first()
  await field.click()
  await page.getByRole("option").filter({ hasText: optionText }).first().click()
}

async function clickRowAction(rowText, actionName) {
  const row = page.locator("tr", { hasText: rowText }).first()
  await row.getByRole("button", { name: actionName }).click()
}

async function clickIconOnlyDeleteInRow(rowText) {
  const row = page.locator("tr", { hasText: rowText }).first()
  await row.getByRole("button").last().click()
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
      const loadingSelectors = [
        '[role="progressbar"]',
        '[aria-busy="true"]',
        '[data-slot="skeleton"]',
        ".animate-pulse",
        '[class*="loading" i]',
        '[class*="spinner" i]',
        '[class*="skeleton" i]',
      ]
      return !loadingSelectors.some((selector) => [...document.querySelectorAll(selector)].some((element) => element.checkVisibility?.() ?? true))
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
        cleanup: { boundaryId: createdBoundaryId, memberId: createdMemberId },
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
