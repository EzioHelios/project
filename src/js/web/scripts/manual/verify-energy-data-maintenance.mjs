import assert from "node:assert/strict"
import { chromium, expect } from "@playwright/test"
import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const webRoot = path.resolve(scriptDir, "../..")
const repositoryRoot = path.resolve(webRoot, "../../..")
const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:18101"
const username = process.env.E2E_ADMIN_EMAIL ?? "codex.e2e@local.test"
const password = process.env.E2E_ADMIN_PASSWORD
if (!password) throw new Error("请通过 E2E_ADMIN_PASSWORD 提供验证账号密码")
const tenantSlug = process.env.E2E_TENANT_SLUG ?? "woheng-taizhou-production-base"
const phase = process.argv.find((arg) => /^(--)?phase=/.test(arg))?.split("=")[1] ?? process.env.E2E_ENERGY_PHASE ?? "crud"
assert.ok(["crud", "query"].includes(phase), "phase 仅支持 crud 或 query")
const outputDir = path.resolve(
  process.env.MANUAL_VERIFY_OUTPUT_DIR ?? path.join(repositoryRoot, `.storage/enterprise-entry-20261115/${phase === "query" && tenantSlug.includes("huzhou") ? "energy-huzhou" : "energy"}`),
)
const screenshotDir = path.join(outputDir, "screenshots")
const verificationDir = path.join(outputDir, "manual-verification")
const verificationPath = path.join(verificationDir, `energy-data-maintenance-${phase}.json`)
const viewport = { width: 1440, height: 900 }
const runId = Date.now().toString(36)
const testMonth = process.env.E2E_ENERGY_MONTH ?? "2026-10"
const sample = tenantSlug.includes("huzhou")
  ? { initialAmount: 348000, initialCost: 285360, amount: 352000, cost: 288640, gasAmount: 22400, gasCost: 71680 }
  : { initialAmount: 480000, initialCost: 393600, amount: 486000, cost: 398520, gasAmount: 18600, gasCost: 59520 }
const recordCode = `ENTRY-E2E-${runId}`
const importRecordCode = `IMPORT-E2E-${runId}`
let selectedAreaName = ""
let selectedDeviceName = ""
let selectedDevice = null
let importDevice = null
let importEnergyType = null
let createdRecord = null
let pendingRecordCode = null
const cleanupIds = new Set()
const importRows = []
const screenshots = {
  query: tenantSlug.includes("huzhou") ? "EV-WH-404-湖州十月天然气录后查询.png" : "EV-WH-403-泰州十月天然气录后查询.png",
  preview: "EV-WH-401-能源数据导入预检.png",
  duplicate: "EV-WH-402-能源数据重复导入.png",
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
const context = await browser.newContext({ viewport, deviceScaleFactor: 1, acceptDownloads: true, locale: "zh-CN", timezoneId: "Asia/Shanghai" })
const page = await context.newPage()
page.setDefaultTimeout(20_000)
page.setDefaultNavigationTimeout(40_000)

const apiFailures = []
const consoleErrors = []
const businessWrites = []
const expectedAuthProbes = []
const requestPhases = new WeakMap()
const sessionProbePaths = new Set(["/api/me", "/api/access/me"])
let authPhase = "session-probe"
let activeTeamId = null
let activeUser = null

page.on("request", (request) => {
  requestPhases.set(request, authPhase)
  const pathname = new URL(request.url()).pathname
  if (pathname.startsWith("/api/") && !pathname.startsWith("/api/access/") && !["GET", "HEAD", "OPTIONS"].includes(request.method())) {
    businessWrites.push({ method: request.method(), path: pathname })
  }
})

page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push({ text: message.text(), url: message.location().url, phase: authPhase, at: new Date().toISOString() })
})
page.on("response", (response) => {
  if (!response.url().includes("/api/")) return
  const status = response.status()
  if (status === 401 || status === 403 || status >= 500) {
    const entry = {
      status,
      method: response.request().method(),
      url: response.url().replace(baseURL, ""),
      phase: requestPhases.get(response.request()) ?? authPhase,
      at: new Date().toISOString(),
    }
    if (status === 401 && entry.method === "GET" && entry.phase === "session-probe" && sessionProbePaths.has(new URL(response.url()).pathname)) {
      expectedAuthProbes.push({ ...entry, note: "登录前会话探测未发现登录态，随后正常登录；不属于登录后的业务接口失败。" })
    } else apiFailures.push(entry)
  }
})

const startedAt = new Date().toISOString()
const checks = []
const artifacts = []

try {
  await ensureAuthenticated()
  await selectTenant()
  if (phase === "query") {
    await verifyConsumptionQuery()
    assert.deepEqual(businessWrites, [], "只读查询阶段不得调用业务写入接口")
  } else {
    await resolveEnergyDataSelectors()
    await gotoEnergyPage()
    await capture("list", "按指定月份查看中文区域、设备、能源和分单位合计。")
    await createEnergyRecord()
    await editEnergyRecord()
    await verifyImport()
    await exportRecords()
    await capture("exportResult", "导出文件包含实际新增及导入记录，期间和数值与接口一致。")
    await deleteCreatedRecords()
  }
  assert.deepEqual(apiFailures, [], "登录及登录后的接口不得出现未预期的 401/403/5xx")
  await writeVerification("passed")
  console.log(`能源数据验证通过：${verificationPath}`)
} catch (error) {
  await writeVerification("failed", error)
  console.error(error)
  process.exitCode = 1
} finally {
  const cleanupFailures = []
  if (pendingRecordCode && !createdRecord) {
    const response = await fetchJson(`/api/energy/interval-facts?search=${encodeURIComponent(pendingRecordCode)}`).catch(() => null)
    for (const row of response?.data?.items ?? []) if (row.source_record_id === pendingRecordCode) cleanupIds.add(row.id)
  }
  for (const id of cleanupIds) {
    const response = await fetchJson(`/api/energy/interval-facts/${id}`, { method: "DELETE" }).catch(() => null)
    if (!response?.ok && response?.status !== 404) cleanupFailures.push(id)
  }
  if (cleanupFailures.length) {
    checks.push({ name: "cleanup", status: "failed", recordIds: cleanupFailures })
    await writeVerification("failed", new Error("部分临时记录清理失败"))
    process.exitCode = 1
  }
  await browser.close()
}

async function ensureAuthenticated() {
  await page.goto(`${baseURL}/login`, { waitUntil: "domcontentloaded" })
  let profile = await fetchJson("/api/me").catch(() => null)
  if (!profile?.ok) {
    authPhase = "login"
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
  assert.equal(activeUser.isSuperuser, false, "最终验收必须使用非 superuser 账号")
  authPhase = "authenticated"
  checks.push({ name: "authentication", status: "passed", isSuperuser: activeUser.isSuperuser, expectedProbe401Count: expectedAuthProbes.length })
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
  await page.goto(`${baseURL}/data/energy-consumption`, { waitUntil: "domcontentloaded" })
  await injectScreenshotCss()
  await expect(page.getByRole("button", { name: "新增能源数据", exact: true })).toBeEnabled()
  await expectVisible("沃衡")
  await page.getByLabel("筛选月份", { exact: true }).fill(testMonth)
  await page.getByRole("button", { name: "查询", exact: true }).click()
  await waitForPageReady()
  await assertBusinessPage(["能源数据维护", "能源记录", "查询", "新增能源数据", "导入能源数据", "导出全部", "能源用量"])
  await expect(page.getByRole("columnheader", { name: "记录编码", exact: true })).toHaveCount(0)
  await expect(page.getByText("meter_projection", { exact: true })).toHaveCount(0)
  checks.push({ name: "open-list", status: "passed", route: "/data/energy-consumption", month: testMonth })
}

async function resolveEnergyDataSelectors() {
  const response = await fetchJson("/api/master-data/devices?limit=500&offset=0")
  assert.equal(response.ok, true, "设备列表读取失败")
  const devices = response.data?.items ?? response.data?.data?.items ?? []
  const suitable = devices.filter((item) => item.name && item.area_name && !/储能|光伏|BESS|PV|演示|测试|验证/i.test(`${item.name} ${item.code}`))
  selectedDevice = suitable.find((item) => /总表|总进线|厂区.*电|车间.*电/.test(item.name))
    ?? suitable.find((item) => /电表|空压|照明/.test(item.name))
  assert.ok(selectedDevice, "需要已配置区域的正常工厂用电设备，不能使用储能或测试设备替代")
  selectedAreaName = String(selectedDevice.area_name)
  selectedDeviceName = String(selectedDevice.name)
  const typeResponse = await fetchJson("/api/energy/types?limit=500")
  const types = typeResponse.data?.data?.items ?? typeResponse.data?.items ?? []
  const gasDevice = suitable.find((item) => /BOILER-01$/i.test(item.code) && /锅炉/.test(item.name))
  assert.ok(gasDevice, "天然气案例需要已有 BOILER-01 锅炉，不得以天然气计量表代替用能设备")
  importDevice = gasDevice
  importEnergyType = types.find((item) => item.code === "natural_gas")
  assert.ok(importEnergyType?.original_unit, "能源种类及单位必须已配置")
  checks.push({ name: "resolve-selectors", status: "passed", selectedAreaName, selectedDeviceName,
    importDevice: importDevice.name, energy: importEnergyType.name, month: testMonth })
}

async function selectOption(scope, label, option) {
  await scope.getByRole("combobox", { name: label, exact: true }).click()
  await page.getByRole("option", { name: option, exact: false }).first().click()
}

async function verifyConsumptionQuery() {
  const summaryPath = "/api/energy/consumption/summary"
  const initial = await captureResponse("GET", summaryPath, () => page.goto(`${baseURL}/energy/consumption`))
  await expect(page.getByText("按能源品种查看", { exact: true })).toBeVisible()
  assert.ok(new Set(initial.items.flatMap((item) => item.groups.filter((group) => group.dimension === "energy_type").map((group) => group.key))).size > 1)
  checks.push({ name: "mixed-energy-kpi", status: "passed", records: initial.totals.record_count, tenantHeader: activeTeamId })

  async function filterOption(label, name) {
    await page.getByText(label, { exact: true }).locator("..").getByRole("combobox").click()
    await page.getByRole("option", { name, exact: typeof name === "string" }).click()
  }
  await filterOption("统计粒度", "月")
  const monthly = await captureResponse("GET", summaryPath, () => page.getByRole("button", { name: "查询", exact: true }).click())
  assert.ok(monthly.totals.record_count > 0)
  await expect(page.getByText("按能源品种查看", { exact: true })).toBeVisible()
  await filterOption("能源品种", /^天然气/)
  const [year, month] = testMonth.split("-").map(Number)
  const lastDay = new Date(year, month, 0).getDate()
  await chooseQueryDate("开始日期", year, month, 1)
  await chooseQueryDate("结束日期", year, month, lastDay)
  const result = await captureResponse("GET", summaryPath, () => page.getByRole("button", { name: "查询", exact: true }).click())
  assert.equal(result.filters.granularity, "month")
  assert.equal(result.filters.period_start, `${testMonth}-01`)
  assert.equal(result.filters.period_end, `${testMonth}-${lastDay}`)
  assert.equal(result.filters.energy_type_code, "natural_gas")
  assert.equal(result.totals.record_count, 1)
  assert.equal(result.totals.original_amount, sample.gasAmount)
  assert.equal(result.items[0].original_unit, "m3")
  await expect(page.getByRole("button", { name: "查询", exact: true })).toBeEnabled()
  const quantity = page.getByText("原始消费量", { exact: true }).locator("..")
  await expect(quantity).toContainText(sample.gasAmount.toLocaleString("zh-CN"))
  await expect(quantity).toContainText("m3")
  const persisted = await fetchJson(`/api/energy/interval-facts?${new URLSearchParams({ granularity: "month", energy_type_code: "natural_gas", period_start: `${testMonth}-01`, period_end: `${testMonth}-${lastDay}` })}`)
  assert.ok(persisted.ok)
  assert.equal(persisted.data.total, 1)
  assert.equal(persisted.data.items[0].amount, sample.gasAmount)
  assert.equal(persisted.data.items[0].cost_cny, sample.gasCost)
  checks.push({ name: "monthly-natural-gas-query", status: "passed", month: testMonth, amount: sample.gasAmount, unit: "m3", tenantHeader: activeTeamId, filters: result.filters, sourceRecordId: persisted.data.items[0].source_record_id })
  await capture("query", "月度天然气查询与原始事实一致；单品种KPI显示数量与单位，混合品种不相加。")
}

async function chooseQueryDate(label, year, month, day) {
  const field = page.getByText(label, { exact: true }).locator("..")
  await field.getByRole("combobox").click()
  const current = await page.evaluate(() => ({ year: new Date().getFullYear(), month: new Date().getMonth() + 1 }))
  const delta = (year - current.year) * 12 + month - current.month
  assert.ok(Math.abs(delta) <= 120, "查询月份超出手册日历选择范围")
  for (let index = 0; index < Math.abs(delta); index++) await field.getByRole("button", { name: delta < 0 ? "上个月" : "下个月", exact: true }).click()
  await expect(field.getByText(`${year}年${month}月`, { exact: true })).toBeVisible()
  // The first occurrence is in this month; any second occurrence is next month.
  await field.getByRole("button", { name: String(day), exact: true }).first().click()
  await expect(field.getByRole("combobox")).toHaveValue(`${year}年${String(month).padStart(2, "0")}月${String(day).padStart(2, "0")}日`)
}
async function captureResponse(method, path, action) {
  const pending = page.waitForResponse((response) => response.request().method() === method && new URL(response.url()).pathname === path)
  await action()
  const response = await pending
  if (method === "POST" && path === "/api/energy/interval-facts") pendingRecordCode = response.request().postDataJSON()?.source_record_id
  const text = await response.text()
  let body = {}
  try { body = text ? JSON.parse(text) : {} } catch { body = { detail: text.slice(0, 200) } }
  assert.equal(response.request().headers()["x-team-id"], activeTeamId, "产品请求必须自然携带当前租户")
  assert.ok(response.ok(), `${method} ${path} HTTP ${response.status()} ${body.detail ?? body.msg ?? ""}`)
  return body.data ?? body
}
async function createEnergyRecord() {
  await page.getByRole("button", { name: "新增能源数据", exact: true }).click()
  const dialog = page.getByRole("dialog", { name: "新增能源数据", exact: true })
  await selectOption(dialog, "区域", selectedAreaName)
  await selectOption(dialog, "设备", selectedDeviceName)
  await selectOption(dialog, "能源种类", "外购电力")
  await selectOption(dialog, "单位", "kWh")
  await dialog.getByLabel("月份", { exact: true }).fill(testMonth)
  await dialog.getByLabel("能源用量", { exact: true }).fill(String(sample.initialAmount))
  await dialog.getByLabel("费用（元）", { exact: true }).fill(String(sample.initialCost))
  await dialog.getByLabel("备注", { exact: true }).fill("厂区购电月结，按当月电费账单登记。")
  await expect(dialog.getByLabel("开始时间", { exact: true })).toHaveValue(`${testMonth}-01T00:00`)
  await capture("create", "选择工厂设备和实际月份，填写购电量与费用。")
  createdRecord = await captureResponse("POST", "/api/energy/interval-facts", () => dialog.getByRole("button", { name: "保存", exact: true }).click())
  cleanupIds.add(createdRecord.id)
  assert.equal(createdRecord.amount, sample.initialAmount)
  assert.equal(createdRecord.cost_cny, sample.initialCost)
  assert.equal(createdRecord.equipment_id, selectedDevice.id)
  assert.equal(createdRecord.period_start.slice(0, 7), testMonth)
  await assertRecordAndTotals(createdRecord.id, sample.initialAmount, sample.initialCost)
  await expect(page.getByRole("dialog", { name: "能源数据详情" })).toBeVisible()
  await expectVisible(sample.initialAmount.toLocaleString("zh-CN"))
  await capture("detail", "保存后直接打开记录详情，中文对象、月份、用量和费用与 API 回查一致。")
  await page.keyboard.press("Escape")
  checks.push({ name: "create-and-read", status: "passed", id: createdRecord.id, period_start: createdRecord.period_start, period_end: createdRecord.period_end, amount: createdRecord.amount })
}
async function editEnergyRecord() {
  await page.locator(`tr[data-record-id="${createdRecord.id}"]`).getByRole("button", { name: "编辑", exact: true }).click()
  const dialog = page.getByRole("dialog", { name: "编辑能源数据", exact: true })
  await expect(dialog.getByLabel("能源用量", { exact: true })).toHaveValue(String(sample.initialAmount))
  await dialog.getByLabel("能源用量", { exact: true }).fill(String(sample.amount))
  await dialog.getByLabel("费用（元）", { exact: true }).fill(String(sample.cost))
  await dialog.getByLabel("备注", { exact: true }).fill("厂区购电月结，已按补充电费账单修正。")
  await capture("editForm", "修改本月购电量和费用，保留相同区域、设备和期间。")
  const saved = await captureResponse("PATCH", `/api/energy/interval-facts/${createdRecord.id}`, () => dialog.getByRole("button", { name: "保存", exact: true }).click())
  assert.equal(saved.amount, sample.amount)
  assert.equal(saved.period_start, createdRecord.period_start)
  await assertRecordAndTotals(saved.id, sample.amount, sample.cost)
  await expectVisible(sample.amount.toLocaleString("zh-CN"))
  await capture("edit", "修改后详情和筛选合计同步更新，反馈显示修改前后的用量和费用。")
  await page.keyboard.press("Escape")
  checks.push({ name: "update", status: "passed", id: saved.id, before: sample.initialAmount, after: saved.amount, month: testMonth })
}
async function assertRecordAndTotals(id, amount, cost) {
  const response = await fetchJson(`/api/energy/interval-facts?ids=${id}`)
  assert.ok(response.ok)
  assert.equal(response.data.total, 1)
  assert.equal(response.data.items[0].id, id)
  assert.equal(response.data.items[0].amount, amount)
  assert.equal(response.data.totals[0].amount, amount)
  assert.equal(response.data.totals[0].cost_cny, cost)
}
async function verifyImport() {
  const fixture = path.join(verificationDir, "车间月度能源台账.csv")
  const secondMonth = testMonth.slice(0, 4) + "-11"
  const amount = sample.gasAmount
  const headers = "记录编码,区域,设备,能源种类,月份,能源用量,单位,费用,备注"
  const lines = [headers]
  for (const [index, month] of [testMonth, secondMonth].entries()) {
    const row = { source_record_id: `${importRecordCode}-${index}`, area_name: importDevice.area_name, equipment_name: importDevice.name,
      energy_type_name: importEnergyType.name, month, amount: String(index ? 0 : amount), unit: importEnergyType.original_unit,
      cost_cny: String(index ? 0 : sample.gasCost), remark: index ? "设备停机，本月无能源消耗。" : "按车间能源月度台账登记。" }
    importRows.push(row)
    lines.push([row.source_record_id, row.area_name, row.equipment_name, row.energy_type_name, row.month, row.amount, row.unit, row.cost_cny, row.remark].map(csvCell).join(","))
  }
  await fs.writeFile(fixture, `﻿${lines.join("\n")}
`)
  await page.getByTestId("energy-interval-import-trigger").click()
  const precheck = await captureResponse("POST", "/api/energy/imports/datasets", () => page.getByTestId("energy-interval-import-file").setInputFiles(fixture))
  assert.equal(precheck.imported_count, 0)
  assert.equal(precheck.records.filter((row) => row.status === "ready").length, 2, JSON.stringify(precheck.errors))
  assert.equal((await fetchJson(`/api/energy/interval-facts?search=${importRecordCode}`)).data.total, 0)
  await capture("preview", "预检显示两条中文设备记录和分单位合计，零值记录有效，预检不写库。")
  const imported = await captureResponse("POST", "/api/energy/imports/datasets", () => page.getByTestId("energy-interval-import-submit").click())
  for (const id of imported.imported_ids) cleanupIds.add(id)
  assert.equal(imported.imported_count, 2)
  assert.equal(imported.skipped_count, 0)
  await expectVisible("实际导入 2")
  await capture("importResult", "导入结果显示实际入库记录和合计，可返回仅包含本次记录的列表。")
  await page.getByRole("button", { name: "查看本次导入记录", exact: true }).click()
  await expect(page.locator("tbody tr[data-record-id]")).toHaveCount(2)
  const resultPage = await fetchJson(`/api/energy/interval-facts?ids=${imported.imported_ids.join(",")}`)
  assert.equal(resultPage.data.total, 2)
  assert.equal(resultPage.data.totals[0].amount, amount)
  assert.equal(resultPage.data.totals[0].cost_cny, sample.gasCost)
  assert.equal(resultPage.data.items.filter((row) => row.amount === 0).length, 1)
  assert.equal(resultPage.data.items.find((row) => row.amount !== 0).period_start.slice(0, 7), testMonth)
  await page.getByTestId("energy-interval-import-trigger").click()
  const duplicatePreview = await captureResponse("POST", "/api/energy/imports/datasets", () => page.getByTestId("energy-interval-import-file").setInputFiles(fixture))
  assert.equal(duplicatePreview.skipped_count, 2)
  await expect(page.getByTestId("energy-interval-import-submit")).toBeDisabled()
  await expectVisible("未覆盖")
  await capture("duplicate", "重复文件逐行提示冲突，确认导入不可用，已有数据保持不变。")
  await page.keyboard.press("Escape")
  const duplicate = await fetchJson("/api/energy/imports/datasets", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ dataset: "energy_interval_facts", rows: precheck.records.map((row) => ({ ...row, amount: 999999 })) }) })
  assert.ok(duplicate.ok)
  assert.equal(duplicate.data.data.imported_count, 0)
  assert.equal(duplicate.data.data.skipped_count, 2)
  const unchanged = await fetchJson(`/api/energy/interval-facts?ids=${imported.imported_ids.join(",")}`)
  assert.equal(unchanged.data.totals[0].amount, amount)
  checks.push({ name: "import-preview-result-zero-and-duplicate", status: "passed", ids: imported.imported_ids, amount, month: testMonth, duplicateImported: 0 })
}
function csvCell(value) { return `"${String(value).replaceAll('"', '""')}"` }
async function exportRecords() {
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "导出全部", exact: true }).click()])
  const target = path.join(verificationDir, download.suggestedFilename())
  await download.saveAs(target)
  const text = await fs.readFile(target, "utf8")
  assert.ok(text.includes("source_record_id") && text.includes("energy_type_code") && text.includes("amount"))
  assert.ok(text.includes(createdRecord.source_record_id) && text.includes(importRecordCode))
  assert.ok(text.includes(String(sample.amount)) && text.includes(testMonth))
  checks.push({ name: "export", status: "passed", file: target, size: Buffer.byteLength(text) })
}
async function deleteCreatedRecords() {
  await page.getByRole("button", { name: "返回全部记录", exact: true }).click()
  await page.getByLabel("搜索能源数据", { exact: true }).fill(createdRecord.source_record_id)
  await page.getByRole("button", { name: "查询", exact: true }).click()
  const row = page.locator(`tr[data-record-id="${createdRecord.id}"]`)
  await expect(row).toBeVisible()
  await row.getByRole("button", { name: "删除", exact: true }).click()
  await captureResponse("DELETE", `/api/energy/interval-facts/${createdRecord.id}`, () => page.getByRole("button", { name: "确认删除", exact: true }).click())
  await expect(row).toHaveCount(0)
  const empty = await fetchJson(`/api/energy/interval-facts?ids=${createdRecord.id}`)
  assert.equal(empty.data.total, 0)
  assert.deepEqual(empty.data.totals, [])
  cleanupIds.delete(createdRecord.id)
  await capture("deleteResult", "删除确认后保留当前筛选，API 回查记录和合计均已移除。")
  const deleted = []
  for (const id of cleanupIds) {
    const response = await fetchJson(`/api/energy/interval-facts/${id}`, { method: "DELETE" })
    assert.ok(response.ok, `临时导入记录 ${id} 清理失败`)
    deleted.push(id)
  }
  cleanupIds.clear()
  checks.push({ name: "delete-and-cleanup", status: "passed", id: createdRecord.id, importedIds: deleted })
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
  await expectVisible("沃衡")
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
        title: phase === "query" ? "能源录后查询只读验证" : "能源数据维护 CRUD 与导入导出验证",
        phase,
        status,
        startedAt,
        finishedAt: new Date().toISOString(),
        baseURL,
        route: phase === "query" ? "/energy/consumption" : "/data/energy-consumption",
        tenantSlug,
        month: testMonth,
        ...(phase === "crud" ? { recordCode: createdRecord?.source_record_id ?? recordCode, importRecordCode } : {}),
        viewport: `${viewport.width}x${viewport.height}`,
        checks,
        artifacts,
        apiFailures,
        expectedAuthProbes,
        consoleErrors: consoleErrors.map((entry) => ({
          ...entry,
          classification: entry.phase !== "authenticated" && /401/.test(entry.text) && expectedAuthProbes.some((probe) => entry.url === new URL(probe.url, baseURL).href)
            ? "expected-session-probe-401-before-login"
            : "console-error",
        })),
        businessWrites,
        failureReason: error instanceof Error ? error.message : error ? String(error) : "",
      },
      null,
      2,
    )}\n`,
  )
}
