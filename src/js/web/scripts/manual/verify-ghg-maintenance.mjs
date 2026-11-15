import { execFileSync } from "node:child_process"
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
const caseProfiles = {
  taizhou: { tenantSlug: "woheng-taizhou-production-base", inventoryCode: "WOHENG-TZ-ENTRY-202610", recordCode: "WH-TZ-WX-20261012", amount: 2.4, co2eKg: 1620, totalCo2eKg: 327124.8, outputName: "ghg" },
  huzhou: { tenantSlug: "woheng-huzhou-production-base", inventoryCode: "WOHENG-HZ-ENTRY-202610", recordCode: "WH-HZ-WX-20261012", amount: 1.8, co2eKg: 1215, totalCo2eKg: 256348.76, outputName: "ghg-huzhou" },
}
const caseProfileName = process.env.GHG_CASE_PROFILE ?? "taizhou"
const caseProfile = caseProfiles[caseProfileName]
if (!caseProfile) throw new Error(`未知核算案例：${caseProfileName}`)
const tenantSlug = process.env.E2E_TENANT_SLUG ?? caseProfile.tenantSlug
const outputDir = path.resolve(
  process.env.MANUAL_VERIFY_OUTPUT_DIR ?? path.join(repositoryRoot, ".storage/enterprise-entry-20261115", caseProfile.outputName),
)
const screenshotDir = path.join(outputDir, "screenshots")
const verificationDir = path.join(outputDir, "manual-verification")
const verificationPath = path.join(verificationDir, "ghg-maintenance.json")
const viewport = { width: 1440, height: 900 }
const phase = process.env.GHG_VERIFY_PHASE ?? "import"
if (caseProfileName !== "taizhou" && !["calculation-only", "calculation-evidence"].includes(phase)) throw new Error("湖州案例仅运行核算及只读取证阶段")
const stamp = new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 12)
let sourceCode = ""
let recordCode = ""
const ownedActivities = new Map()
const ownedSources = new Map()
const screenshots = {
  importEntry: "EV-WH-012-非电活动数据导入入口.png",
  activityEntry: "EV-WH-144-活动数据台账入口.png",
  sourceCreate: "EV-WH-145-排放源新增表单.png",
  sourceEdit: "EV-WH-146-排放源编辑结果.png",
  activityCreate: "EV-WH-147-活动数据新增表单.png",
  activityCreateDetails: "EV-WH-174-活动数据分类字段与保存.png",
  activityDetail: "EV-WH-148-活动数据详情与归集.png",
  activityEdit: "EV-WH-149-活动数据编辑结果.png",
  deleteResult: "EV-WH-151-活动与排放源删除结果.png",
  gasForm: "EV-WH-301-锅炉天然气填报.png", gasResult: "EV-WH-302-锅炉天然气保存结果.png",
  dieselForm: "EV-WH-303-叉车柴油填报.png", dieselResult: "EV-WH-304-叉车柴油保存结果.png",
  refrigerantForm: "EV-WH-305-制冷剂维护填报.png", refrigerantResult: "EV-WH-306-制冷剂维护保存结果.png",
  commuteForm: "EV-WH-307-员工通勤填报.png", commuteResult: "EV-WH-308-员工通勤保存结果.png",
  transportForm: "EV-WH-309-上游运输填报.png", transportResult: "EV-WH-310-上游运输保存结果.png",
  importPreview: "EV-WH-311-制冷剂单表预检.png", importResult: "EV-WH-312-制冷剂实际导入结果.png",
  importBatch: "EV-WH-313-本批活动查询.png", generateForm: "EV-WH-314-能源活动生成选择.png",
  generateResult: "EV-WH-315-能源活动生成结果.png", generateRepeat: "EV-WH-316-重复生成结果.png",
  importConflict: "EV-WH-317-重复导入冲突结果.png",
  categoryEntry: "EV-WH-322-制冷剂中文任务与可用记录.png", archivedRecords: "EV-WH-323-归档活动筛选.png",
  refrigerantFormLower: "EV-WH-324-制冷剂表单下半页.png", commuteFormLower: "EV-WH-325-通勤表单下半页.png", transportFormLower: "EV-WH-326-运输表单下半页.png", importFilePicker: "EV-WH-327-中文工作簿选择.png",
  gwpSelection: "EV-WH-318-R32采用GWP.png", gwpApplied: "EV-WH-319-R32已采用因子.png",
  gwpResult: "EV-WH-320-R32实际核算结果.png", gwpDetail: "EV-WH-321-R32核算气体与参数.png",
  calculationReady: "EV-WH-030-排放清单与报告台账.png",
  calculationResults: "EV-WH-031-排放结果明细与核算公式.png",
  calculationDetail: "EV-WH-032-排放明细详情-活动与因子.png",
}
if (caseProfileName === "huzhou") Object.assign(screenshots, {
  calculationReady: "EV-WH-328-湖州十月核算上下文与总量.png",
  calculationResults: "EV-WH-329-湖州八条活动核算结果.png",
  calculationDetail: "EV-WH-330-湖州R32核算详情.png",
  gwpResult: "EV-WH-331-湖州R32核算结果.png",
  gwpDetail: "EV-WH-332-湖州R32核算参数.png",
})
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
const businessWrites = []
const consoleErrors = []
const checks = []
const artifacts = []
let activeTeamId = null
let activeUser = null
let catalog = null
let period = null
let area = null
let equipment = null
let meterPoint = null


page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push({ text: message.text(), at: new Date().toISOString() })
})
page.on("request", (request) => {
  const pathname = new URL(request.url()).pathname
  if (pathname.startsWith("/api/") && !pathname.startsWith("/api/access/") && !["GET", "HEAD", "OPTIONS"].includes(request.method())) businessWrites.push({ method: request.method(), pathname })
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

let runError = null
try {
  await ensureAuthenticated()
  await selectTenant()
  await loadCatalog()
  if (phase === "calculation-evidence") await recaptureExistingCalculation()
  if (phase === "forms") await captureSupplementaryForms()
  if (["entry", "import", "full"].includes(phase)) await verifyCategoryEntry()
  if (["crud", "import", "full"].includes(phase)) {
    await openActivityLedger()
    await capture("activityEntry", "打开活动数据总账，确认总账只读查询、跨分类筛选和详情追溯。")
    await createSource()
    await editSource()
    await createActivity()
    await openActivityDetailAndSaveAllocation()
    await editActivity()
    await verifyAdditionalCategories()
  }
  if (["import", "import-only", "full"].includes(phase)) await verifyCategoryImport()
  if (["crud", "import", "import-only", "full"].includes(phase)) await cleanupCreatedRows()
  if (["generation", "full"].includes(phase)) await verifyGeneration()
  if (["calculation", "calculation-only", "full"].includes(phase)) await verifyRefrigerantCalculation()
} catch (error) {
  runError = error
  await page.screenshot({ path: path.join(screenshotDir, "failure.png"), fullPage: false, animations: "disabled" }).catch(() => {})
  console.error(error)
} finally {
  if (!runError && (ownedActivities.size || ownedSources.size)) runError = new Error("成功流程仍遗留临时记录，用户删除验证未完成")
  const cleanupErrors = []
  for (const row of [...ownedActivities.values()]) {
    try { await cleanupActivity(row.recordCode, row.inventoryCode); ownedActivities.delete(row.recordCode) }
    catch (error) { cleanupErrors.push(`活动${row.recordCode}：${error.message}`) }
  }
  for (const row of [...ownedSources.values()]) {
    try { await cleanupSource(row.sourceCode, row.inventoryCode); ownedSources.delete(row.sourceCode) }
    catch (error) { cleanupErrors.push(`排放源${row.sourceCode}：${error.message}`) }
  }
  if (cleanupErrors.length) {
    checks.push({ name: "failure-cleanup", status: "failed", errors: cleanupErrors })
    runError = new Error([runError?.message, ...cleanupErrors].filter(Boolean).join("；"))
  }
  if (apiFailures.length && !runError) runError = new Error(`验证期间发生 ${apiFailures.length} 个 401/403/5xx 响应，请检查 apiFailures`)
  if (phase === "calculation-evidence" && businessWrites.length) runError = new Error("只读取证阶段发出了业务写请求")
  await writeVerification(runError ? "failed" : "passed", runError)
  if (runError) process.exitCode = 1
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
  if (activeUser.isSuperuser !== false) throw new Error("最终验收必须使用非 superuser 账号")
  checks.push({ name: "auth", status: "passed", role: "tenant-user", isSuperuser: activeUser.isSuperuser })
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
  const matchingPeriods = (catalog.periods ?? []).filter((item) => item.code === caseProfile.inventoryCode)
  if (matchingPeriods.length !== 1) throw new Error(`盘查任务${caseProfile.inventoryCode}应唯一对应报告期，实际匹配${matchingPeriods.length}项`)
  period = matchingPeriods[0]
  equipment = catalog.equipment?.find((item) => item.code === "PCC-METER-01") ?? catalog.equipment?.find((item) => item.areaId) ?? catalog.equipment?.[0]
  area = catalog.areas?.find((item) => item.id === equipment?.areaId)
  meterPoint = catalog.meterPoints?.find((item) => item.equipmentId === equipment.id && item.unit === "kWh")
  if (!meterPoint) throw new Error("厂区电表缺少已启用的电量测点（kWh）")
  if (!period?.code || !area?.code) throw new Error("组织碳维护验证需要报告期和区域主数据")
  if (["crud", "import", "full"].includes(phase)) {
    const { boundary } = await resolveCalculationContext()
    const response = await fetchJson(`/api/carbon/organization-boundary/facilities?boundary_id=${boundary.id}&limit=200`)
    if (!response.ok) throw new Error("无法读取所选报告期的边界设施")
    const facilities = response.data.data ?? response.data
    if (facilities.total > facilities.items.length) throw new Error("边界设施未完整读取，不能判断归集范围")
    const ancestors = new Set()
    for (let current = area; current && !ancestors.has(current.id); current = catalog.areas.find((item) => item.id === current.parentId)) ancestors.add(current.id)
    const allowed = facilities.items.find((item) => item.included && (Number(item.equipmentId ?? item.equipment_id) === equipment.id || ancestors.has(Number(item.areaId ?? item.area_id))))
    if (!allowed) throw new Error("购电设备及所属区域不在所选报告期已发布边界内，不能进行归集验收")
    checks.push({ name: "allocation-boundary-context", status: "passed", reportingPeriodId: period.id, boundaryId: boundary.id, facilityId: allowed.id, areaId: area.id, equipmentId: equipment.id })
  }
  checks.push({ name: "catalog", status: "passed", period: period.name, area: area.name, equipment: equipment?.name ?? "" })
}

async function openActivityLedger() {
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
  await selectOption(dialog, "盘查任务", period.name)
  await fillInput(dialog, "排放源名称", "泰州基地厂区电力总表")
  await selectOption(dialog, "ISO 二级分类", "2.1")
  await selectOption(dialog, "默认区域", area.name)
  if (equipment?.name) await selectOption(dialog, "默认设备", equipment.name)
  await capture("sourceCreate", "新增排放源表单填写态，展示盘查任务、ISO 分类、组织、区域、设备和来源状态。")
  const sourceResponse = page.waitForResponse((response) => response.url().endsWith("/api/ghg-inventory/emission-sources") && response.request().method() === "POST")
  await dialog.getByRole("button", { name: "保存排放源" }).click()
  const createdSource = await assertUiResponse(await sourceResponse)
  sourceCode = createdSource.sourceCode
  if (!sourceCode) throw new Error("新增排放源未返回编号")
  ownedSources.set(sourceCode, createdSource)
  await expectVisible("排放源已保存")
  await searchSources(sourceCode)
  await expectVisible("泰州基地厂区电力总表")
  checks.push({ name: "source-create", status: "passed", sourceCode })
}

async function editSource() {
  await rowFor(sourceCode).getByRole("button").first().click()
  const dialog = page.getByRole("dialog").filter({ hasText: "维护排放源" })
  await dialog.waitFor({ state: "visible" })
  await fillInput(dialog, "排放源名称", "泰州基地厂区购电")
  await dialog.getByRole("button", { name: "更新排放源" }).click()
  await expectVisible("排放源已更新")
  await searchSources(sourceCode)
  await expectVisible("泰州基地厂区购电")
  await capture("sourceEdit", "编辑排放源后回到列表，排放源名称、分类、组织区域和活动记录数回显。")
  checks.push({ name: "source-update", status: "passed", sourceCode })
}

async function createActivity() {
  const row = await fillAndSaveCategory({ category: "2.1", name: "泰州基地十月外购电量", sourceName: "泰州基地厂区购电", amount: "485600", unit: "kWh", fields: { "能源种类": "电力", "供应商": "江苏电网", "计量点": meterPoint.name, "Scope 2 方法": "基于位置" }, formKey: "activityCreate", resultKey: "activityDetail", extraFormKey: "activityCreateDetails" })
  recordCode = row.recordCode
}

async function fillAndSaveCategory(testCase) {
  await page.goto(`${baseURL}/carbon-mgmt/category/${testCase.category}`, { waitUntil: "domcontentloaded" })
  await waitForPageReady()
  await selectOption(page, "盘查任务", period.name)
  await page.getByRole("button", { name: "新增本类活动" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "新增活动数据" })
  await dialog.waitFor({ state: "visible" })
  await selectOption(dialog, "排放源", testCase.sourceName)
  await fillInput(dialog, "活动名称", testCase.name)
  const startDate = testCase.periodStart ?? `${period.periodStart.slice(0,4)}-10-01`
  const endDate = testCase.periodEnd ?? `${period.periodStart.slice(0,4)}-10-31`
  await fillInput(dialog, "开始日期", startDate)
  await fillInput(dialog, "结束日期", endDate)
  await fillInput(dialog, "活动量", testCase.amount)
  for (const [label, value] of Object.entries(testCase.fields)) await fillOrSelect(dialog, label, value, value)
  const unitLabels = await selectOption(dialog, "单位", testCase.unit)
  if (testCase.category === "2.1" && unitLabels.some((label) => label === "t" || label.includes("吨"))) throw new Error("购电单位中存在吨")
  await selectOption(dialog, "数据来源", testCase.dataSource ?? "人工台账")
  await fillInput(dialog, "测量方法", testCase.method ?? "依据十月用量台账汇总")
  await dialog.evaluate((element) => { element.scrollTop = 0 })
  await capture(testCase.formKey, `${testCase.name}：填写对象、期间、数量和本类字段。`)
  if (testCase.extraFormKey) {
    await dialog.evaluate((element) => { element.scrollTop = element.scrollHeight })
    await capture(testCase.extraFormKey, "填写供应商、计量点与测量方法后保存。")
  }
  const responsePromise = page.waitForResponse((response) => response.url().endsWith("/api/ghg-inventory/activities") && response.request().method() === "POST")
  await dialog.getByRole("button", { name: "保存活动数据" }).click()
  const response = await responsePromise
  const row = await assertUiResponse(response)
  if (!row.recordCode) throw new Error(`分类${testCase.category}保存失败：${JSON.stringify(row)}`)
  ownedActivities.set(row.recordCode, row)
  const detail = page.getByRole("dialog").filter({ hasText: "活动数据详情" })
  await expect(detail).toBeVisible()
  await expect(detail).toContainText(testCase.name)
  if (testCase.dataSource) await expect(detail).toContainText(testCase.dataSource)
  await expect(detail).toContainText(Number(testCase.amount).toLocaleString("zh-CN"))
  if (row.periodStart !== startDate || row.periodEnd !== endDate) throw new Error("保存期间与填写期间不一致")
  if (Number(row.activityAmount) !== Number(testCase.amount) || row.activityUnit !== testCase.unit || row.isoCategoryCode !== testCase.category) throw new Error("保存值、单位或分类与输入不一致")
  const expectedChoices = { "电力": "electricity", "基于位置": "location", "天然气": "natural_gas", "柴油": "diesel", "员工通勤": "commute", "上游": "upstream", "公路运输": "road" }
  for (const field of catalog.categories.find((item) => item.code === testCase.category).activityFields) {
    const entered = testCase.fields[field.label]
    if (entered === undefined) continue
    const expected = ["facility_or_device", "vehicle_or_machine"].includes(field.code) ? catalog.equipment.find((item) => item.name === entered)?.code : field.code === "meter_point" ? meterPoint.code : expectedChoices[entered] ?? entered
    if (String(row.activityDetails[field.code] ?? "") !== String(expected)) throw new Error(`保存字段与填写值不一致：${field.code}，预期${expected}，实际${row.activityDetails[field.code]}`)
  }
  for (const field of catalog.categories.find((item) => item.code === testCase.category).activityFields.filter((field) => field.required)) {
    if (!String(row.activityDetails[field.code] ?? "").trim()) throw new Error(`分类必填字段未保存：${field.code}`)
  }
  await capture(testCase.resultKey, `${testCase.name}：保存后自动定位，详情显示${testCase.amount} ${testCase.unit}。`)
  const persisted = await getActivity(row.recordCode)
  if (persisted.activityAmount !== row.activityAmount || persisted.activityUnit !== row.activityUnit || JSON.stringify(persisted.activityDetails) !== JSON.stringify(row.activityDetails)) throw new Error("新增活动回查数值不一致")
  checks.push({ name: `category-${testCase.category}-create-detail`, status: "passed", recordCode: row.recordCode, activityName: row.activityName, amount: row.activityAmount, unit: row.activityUnit, fields: row.activityDetails })
  await page.keyboard.press("Escape")
  return row
}

async function verifyAdditionalCategories() {
  const equipmentByCode = (code) => {
    const item = catalog.equipment.find((row) => row.code === code)
    if (!item) throw new Error(`案例需要已有设备：${code}`)
    return item
  }
  const boiler = equipmentByCode("BOILER-01")
  const forklift = equipmentByCode("FORKLIFT-FLEET-01")
  const chiller = equipmentByCode("REFRIGERANT-01")
  const cases = [
    { category: "1.1", dataSource: "供应商台账", name: `${boiler.name}十月天然气用量`, sourceName: `${boiler.name}天然气燃烧`, equipment: boiler, amount: "18600", unit: "m3", fields: { "设备/设施": boiler.name, "燃料品种": "天然气" }, formKey: "gasForm", resultKey: "gasResult" },
    { category: "1.2", name: "叉车车队十月柴油用量", sourceName: "厂内叉车柴油燃烧", equipment: forklift, amount: "680", unit: "L", fields: { "车辆/机械": forklift.name, "燃料品种": "柴油", "车型/机械类型": "柴油叉车", "运行工时": "120" }, formKey: "dieselForm", resultKey: "dieselResult" },
    { category: "1.4", periodStart: "2026-10-12", periodEnd: "2026-10-12", name: `${chiller.name}十月制冷剂补充`, sourceName: `${chiller.name}制冷剂维护`, equipment: chiller, amount: "2.4", unit: "kg", fields: { "气体": "R32", "设备": chiller.name, "充注量": "2.4", "回收量": "0" }, method: "依据本次制冷维护补充及回收记录", formKey: "refrigerantForm", resultKey: "refrigerantResult" },
    { category: "3.3", name: "泰州基地十月员工自驾通勤", sourceName: "泰州基地员工自驾", amount: "792", unit: "person·km", fields: { "运输方向": "员工通勤", "运输方式": "汽油乘用车", "里程(km)": "792", "人数": "1", "起点": "泰州员工生活区", "终点": "沃衡汽车泰州生产基地" }, method: "单程18 km × 22个工作日 × 每日往返2次 × 1人", formKey: "commuteForm", resultKey: "commuteResult" },
    { category: "3.1", name: "泰州基地十月零部件入厂运输", sourceName: "泰州基地零部件上游运输", amount: "1920", unit: "t·km", fields: { "运输方向": "上游", "运输方式": "公路运输", "里程(km)": "160", "货物质量(t)": "12", "承运商": "泰州零部件物流公司", "起点": "泰州零部件配送中心", "终点": "沃衡汽车泰州生产基地" }, formKey: "transportForm", resultKey: "transportResult" },
  ]
  for (const testCase of cases) {
    const code = `ENTRY-${stamp}-${testCase.category.replace(".", "")}`
    const source = await fetchJson("/api/ghg-inventory/emission-sources", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ inventoryCode: period.code, reportingPeriodId: period.id, organizationCode: period.organizationCode, facilityCode: area.code, sourceCode: code, sourceName: testCase.sourceName, isoCategoryCode: testCase.category, defaultAreaId: testCase.equipment?.areaId ?? area.id, defaultEquipmentId: testCase.equipment?.id, sourceSystem: "manual", status: "active" }) })
    if (!source.ok) throw new Error(`分类排放源准备失败：${JSON.stringify(source.data)}`)
    ownedSources.set(code, source.data)
    await fillAndSaveCategory(testCase)
    const headings = await page.getByRole("columnheader").allTextContents()
    if (testCase.category === "1.4" && headings.some((text) => /期初|期末|购入|转移|回收/.test(text))) throw new Error("制冷剂主表仍显示库存明细列")
    if (testCase.category === "3.1" && headings.includes("人数")) throw new Error("货运主表不应显示人数")
    if (testCase.category === "3.3" && headings.includes("货物质量(t)")) throw new Error("通勤主表不应显示货物质量")
  }
}

async function openActivityDetailAndSaveAllocation() {
  await page.getByRole("button", { name: "查看保存值" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "活动数据详情" })
  await dialog.waitFor({ state: "visible" })
  await expectVisible("分类字段")
  await selectOption(dialog, "区域", area.name)
  await selectOption(dialog, "设备", equipment.name)
  const allocationResponse = page.waitForResponse((response) => response.url().includes("/allocations") && response.request().method() === "PUT")
  await dialog.getByRole("button", { name: "保存归集" }).click()
  await assertUiResponse(await allocationResponse)
  const allocationQuery = await fetchJson(`/api/ghg-inventory/activities/${encodeURIComponent(recordCode)}/allocations?inventory_code=${encodeURIComponent(period.code)}`)
  if (!allocationQuery.ok || !allocationQuery.data.items?.length) throw new Error("归集保存后回查为空")
  if (!allocationQuery.data.items.some((item) => item.areaId === area.id && item.equipmentId === equipment.id && Number(item.allocationRatio) === 1)) throw new Error("归集回查与所选区域、设备或比例不一致")
  await capture("activityDetail", "活动数据详情中维护区域、设备、计量边界和归集比例，保存后形成活动数据归集关系。")
  await page.keyboard.press("Escape")
  checks.push({ name: "allocation-save", status: "passed", recordCode })
}

async function editActivity() {
  await searchActivities("泰州基地十月外购电量")
  await rowFor("泰州基地十月外购电量").getByRole("button", { name: "编辑泰州基地十月外购电量" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "编辑活动数据" })
  await dialog.waitFor({ state: "visible" })
  await fillInput(dialog, "活动量", "486000")
  await fillInput(dialog, "备注", "依据修订后的十月电量台账更新")
  const updateResponse = page.waitForResponse((response) => response.url().includes("/api/ghg-inventory/activities/") && response.request().method() === "PATCH")
  await dialog.getByRole("button", { name: "更新活动数据" }).click()
  await assertUiResponse(await updateResponse)
  await expect(page.getByRole("dialog").filter({ hasText: "活动数据详情" })).toContainText("486,000")
  await capture("activityEdit", "编辑活动数据后回到台账，活动量、来源、质量和归集状态回显。")
  const updated = await getActivity(recordCode)
  if (Number(updated.activityAmount) !== 486000) throw new Error("更新值未保存")
  await page.keyboard.press("Escape")
  checks.push({ name: "activity-update", status: "passed", recordCode, before: "485600", after: updated.activityAmount })
}

async function cleanupCreatedRows() {
  // Every successful run proves deletion through the product UI. API cleanup is reserved for failures.
  for (const row of [...ownedActivities.values()]) {
    await page.goto(`${baseURL}/carbon-mgmt/category/${row.isoCategoryCode}?inventory=${encodeURIComponent(row.inventoryCode)}&record=${encodeURIComponent(row.recordCode)}`, { waitUntil: "domcontentloaded" })
    await expect(page.getByRole("dialog").filter({ hasText: "活动数据详情" })).toBeVisible()
    await page.keyboard.press("Escape")
    await searchActivities(row.recordCode, false)
    const tableRow = page.locator("tbody tr").filter({ hasText: row.activityName }).first()
    await expect(tableRow).toBeVisible()
    page.once("dialog", (confirmation) => confirmation.accept())
    const responsePromise = page.waitForResponse((response) => response.url().includes(encodeURIComponent(row.recordCode)) && response.request().method() === "DELETE")
    await tableRow.getByRole("button", { name: `删除${row.activityName}`, exact: true }).click()
    const deleted = await assertUiResponse(await responsePromise)
    if (!deleted.deleted) throw new Error(`临时活动未被删除：${row.recordCode}`)
    await expect(tableRow).toHaveCount(0)
    const after = await fetchJson(`/api/ghg-inventory/activities/${encodeURIComponent(row.recordCode)}?inventory_code=${encodeURIComponent(row.inventoryCode)}`)
    if (after.status !== 404) throw new Error(`已删除活动仍可回查：${row.recordCode}`)
    ownedActivities.delete(row.recordCode)
    checks.push({ name: "activity-delete-ui", status: "passed", recordCode: row.recordCode, deleteStatus: "deleted", queryStatus: after.status })
  }
  for (const row of [...ownedSources.values()]) {
    await page.goto(`${baseURL}/carbon-mgmt/sources`, { waitUntil: "domcontentloaded" })
    await waitForPageReady()
    await searchSources(row.sourceCode)
    const tableRow = rowFor(row.sourceCode)
    await expect(tableRow).toBeVisible()
    page.once("dialog", (confirmation) => confirmation.accept())
    const responsePromise = page.waitForResponse((response) => response.url().includes(encodeURIComponent(row.sourceCode)) && response.request().method() === "DELETE")
    await tableRow.getByRole("button", { name: /^删除/ }).click()
    const deleted = await assertUiResponse(await responsePromise)
    if (!deleted.deleted) throw new Error(`临时排放源未被删除：${row.sourceCode}`)
    await expect(tableRow).toHaveCount(0)
    const after = await fetchJson(`/api/ghg-inventory/emission-sources/${encodeURIComponent(row.sourceCode)}?inventory_code=${encodeURIComponent(row.inventoryCode)}`)
    if (after.status !== 404) throw new Error(`已删除排放源仍可回查：${row.sourceCode}`)
    ownedSources.delete(row.sourceCode)
    checks.push({ name: "source-delete-ui", status: "passed", sourceCode: row.sourceCode, deleteStatus: "deleted", queryStatus: after.status })
  }
  await capture("deleteResult", "已逐条通过分类页与排放源页执行删除并确认，DELETE返回成功，接口回查均为404后截图。")
}

async function cleanupActivity(code, inventoryCode) {
  if (!ownedActivities.has(code)) return
  const row = { recordCode: code, inventoryCode: inventoryCode ?? ownedActivities.get(code)?.inventoryCode }
  if (!row?.recordCode) return
  const result = await fetchJson(`/api/ghg-inventory/activities/${encodeURIComponent(code)}?inventory_code=${encodeURIComponent(row.inventoryCode)}`, { method: "DELETE" })
  if ((!result.ok && result.status !== 404) || (result.ok && !result.data.deleted)) throw new Error(`清理活动数据失败：${code} HTTP ${result.status}`)
}

async function cleanupSource(code, inventoryCode) {
  if (!ownedSources.has(code)) return
  const row = { sourceCode: code, inventoryCode: inventoryCode ?? ownedSources.get(code)?.inventoryCode }
  if (!row?.sourceCode) return
  const result = await fetchJson(`/api/ghg-inventory/emission-sources/${encodeURIComponent(code)}?inventory_code=${encodeURIComponent(row.inventoryCode)}`, { method: "DELETE" })
  if ((!result.ok && result.status !== 404) || (result.ok && !result.data.deleted)) throw new Error(`清理排放源失败：${code} HTTP ${result.status}`)
}

async function getActivity(code) {
  const response = await fetchJson(`/api/ghg-inventory/activities/${encodeURIComponent(code)}?inventory_code=${encodeURIComponent(ownedActivities.get(code)?.inventoryCode ?? period.code)}`)
  if (response.status === 404) return null
  if (!response.ok) throw new Error(`活动数据查询失败：HTTP ${response.status}`)
  return response.data
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
  const input = page.getByPlaceholder("搜索本页活动、设备或排放源")
  await input.fill(text)
  await waitForPageReady()
  if (expectRecord) await expect(rowFor(text)).toBeVisible()
}

function rowFor(text) {
  return page.locator("tbody tr").filter({ hasText: text }).first()
}

async function assertUiResponse(response) {
  const headers = await response.request().allHeaders()
  if (headers["x-team-id"] !== activeTeamId) throw new Error(`产品请求未携带当前租户：${response.request().method()} ${new URL(response.url()).pathname}`)
  const data = await response.json()
  if (!response.ok()) throw new Error(`页面操作失败：HTTP ${response.status()} ${JSON.stringify(data)}`)
  return data
}

async function listAll(endpoint, filters = {}) {
  const items = []
  for (let offset = 0; ; offset += 200) {
    const query = new URLSearchParams({ ...filters, limit: "200", offset: String(offset) })
    const result = await fetchJson(`${endpoint}?${query}`)
    if (!result.ok) throw new Error(`读取${endpoint}失败：HTTP ${result.status}`)
    items.push(...(result.data.items ?? []))
    if (items.length >= result.data.total || result.data.items.length === 0) return items
  }
}

async function trackNewResultRecords(records, priorRecords, priorSources) {
  for (const row of records) {
    if (!priorRecords.has(`${row.inventoryCode}:${row.recordCode}`)) ownedActivities.set(row.recordCode, row)
    if (!priorSources.has(`${row.inventoryCode}:${row.sourceCode}`)) {
      ownedSources.set(row.sourceCode, { sourceCode: row.sourceCode, inventoryCode: row.inventoryCode })
    }
  }
}

async function verifyCategoryImport() {
  const priorRecords = new Set((await listAll("/api/ghg-inventory/activities")).map((row) => `${row.inventoryCode}:${row.recordCode}`))
  const priorSources = new Set((await listAll("/api/ghg-inventory/emission-sources")).map((row) => `${row.inventoryCode}:${row.sourceCode}`))
  const device = catalog.equipment.find((row) => row.code === "REFRIGERANT-01")
  const deviceArea = catalog.areas.find((row) => row.id === device.areaId)
  await page.goto(`${baseURL}/carbon-mgmt/import?category=%221.4%22`, { waitUntil: "domcontentloaded" })
  await waitForPageReady()
  // Resolve the target site's period instead of trusting catalog ordering.
  const periodControl = page.getByText("盘查期", { exact: true }).locator("..").getByRole("combobox")
  await periodControl.click()
  await page.getByRole("option", { name: period.name, exact: true }).click()
  await expect(periodControl).toContainText(period.name)
  await capture("importEntry", "选择逸散排放分类、报告期与工厂后下载单表模板。")
  const downloadPromise = page.waitForEvent("download")
  await page.getByRole("button", { name: "下载分类模板" }).click()
  const download = await downloadPromise
  const templatePath = path.join(outputDir, "制冷剂维修填报模板.xlsx")
  const workbookPath = path.join(outputDir, "泰州基地十月办公楼R32维修.xlsx")
  await download.saveAs(templatePath)
  const payload = {
    source_name: `${device.name}维修补充复核`, area_name: deviceArea.name, equipment_name: device.name,
    period_start: `${period.periodStart.slice(0,4)}-10-12`, period_end: `${period.periodStart.slice(0,4)}-10-12`,
    activity_amount: 2.4, activity_unit: "kg", facility_or_device: device.name,
    gas_code: "R32", charges: 2.4, recovery: 0, measurement_method: "依据10月12日维修工单记录实际补充量", remarks: `查漏修复后补充冷媒；本事件无回收。独立导入复核 ${stamp}`,
  }
  execFileSync(path.join(repositoryRoot, ".venv/bin/python"), ["-c", `
import json, sys
from openpyxl import load_workbook
w=load_workbook(sys.argv[1]); data=json.loads(sys.argv[3])
visible=[s.title for s in w.worksheets if s.sheet_state == 'visible']
assert visible == ['03_活动数据'], visible
s=w['03_活动数据']; codes=[str(c.value or '') for c in s[2]]
if s.max_row > 2: s.delete_rows(3, s.max_row-2)
s.append([data.get(k) for k in codes]); w.save(sys.argv[2])
`, templatePath, workbookPath, JSON.stringify(payload)], { cwd: repositoryRoot })
  await page.getByLabel("分类工作簿").setInputFiles(workbookPath)
  const previewPromise = page.waitForResponse((response) => response.url().endsWith("/api/ghg-inventory/import/preview") && response.request().method() === "POST")
  await page.getByRole("button", { name: "执行预检" }).click()
  const preview = await assertUiResponse(await previewPromise)
  if (preview.errorCount || preview.rowCount !== 1) throw new Error(`单表预检失败：${JSON.stringify(preview.preview.issues)}`)
  await expect(page.getByText("活动数据预览", { exact: true })).toBeVisible()
  await expect(page.getByRole("tabpanel").filter({ hasText: "活动数据预览" })).toContainText(device.name)
  await capture("importPreview", "单表预检显示办公楼空调、区域、10月12日、R32补充2.4 kg 和将新增状态。")
  if (preview.warningCount > 0) {
    await page.getByRole("checkbox", { name: "确认保留警告" }).check()
    await page.getByPlaceholder("填写确认原因").fill("已核对维修工单的实际补充量和回收量，先保存活动台账。")
  }
  const commitPromise = page.waitForResponse((response) => response.url().endsWith("/api/ghg-inventory/import/commit") && response.request().method() === "POST")
  await page.getByRole("button", { name: "确认导入", exact: true }).click()
  const committed = await assertUiResponse(await commitPromise)
  await trackNewResultRecords(committed.committedRows ?? [], priorRecords, priorSources)
  if (committed.committedCount !== 1 || committed.committedRows?.length !== 1) throw new Error("导入未返回一条实际保存的记录")
  const saved = committed.committedRows[0]
  if (saved.inventoryCode !== period.code) throw new Error("导入结果未归入所选十月盘查任务")
  if (Number(saved.activityAmount) !== 2.4 || saved.activityUnit !== "kg") throw new Error("导入实际数值不符")
  const persisted = await getActivity(saved.recordCode, saved.inventoryCode)
  if (Number(persisted.activityAmount) !== 2.4 || persisted.activityDetails?.gas_code !== "R32" || Number(persisted.activityDetails?.charges) !== 2.4 || Number(persisted.activityDetails?.recovery) !== 0 || !persisted.periodStart.startsWith("2026-10-12")) throw new Error("制冷剂导入回查与维修原表不一致")
  if (!saved.sourceName || !saved.facilityName) throw new Error("实际保存记录缺少中文对象名称")
  await expect(page.getByText("本次导入结果", { exact: true })).toBeVisible()
  await expect(page.getByText("已入库 1 条", { exact: false })).toBeVisible()
  await capture("importResult", "实际提交后展示一条入库记录、分单位合计及查看本批数据入口。")
  const repeat = await fetchJson("/api/ghg-inventory/import/commit", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ batchCode: committed.batchCode, acknowledgeWarnings: true, warningAcknowledgement: "重复提交核对" }) })
  if (!repeat.ok || repeat.data.committedCount !== committed.committedCount) throw new Error("同批重复提交未返回原结果")
  await page.getByRole("link", { name: "查看本批数据" }).click()
  await expect(page).toHaveURL(new RegExp(encodeURIComponent(committed.batchCode)))
  await expect(rowFor(saved.activityName)).toBeVisible()
  const filtered = await fetchJson(`/api/ghg-inventory/activities?inventory_code=${encodeURIComponent(committed.inventoryCode)}&batch_code=${encodeURIComponent(committed.batchCode)}`)
  if (!filtered.ok || filtered.data.total !== 1 || filtered.data.items[0].recordCode !== saved.recordCode) throw new Error("本批筛选返回非本批记录")
  await capture("importBatch", "分类台账按导入批次定位，显示本批办公楼R32维修记录。")
  await page.getByRole("button", { name: `查看${saved.activityName}`, exact: true }).click()
  await expect(page.getByRole("dialog").filter({ hasText: "活动数据详情" })).toContainText("2.4")
  await page.keyboard.press("Escape")
  await page.goto(`${baseURL}/carbon-mgmt/import?category=%221.4%22`, { waitUntil: "domcontentloaded" })
  await waitForPageReady()
  await page.getByLabel("分类工作簿").setInputFiles(workbookPath)
  const conflictPromise = page.waitForResponse((response) => response.url().endsWith("/api/ghg-inventory/import/preview") && response.request().method() === "POST")
  await page.getByRole("button", { name: "执行预检" }).click()
  const conflict = await assertUiResponse(await conflictPromise)
  if (conflict.errorCount < 1) throw new Error("重复文件未识别记录冲突")
  await page.getByRole("tab", { name: /校验问题/ }).click()
  await expect(page.getByRole("button", { name: "确认导入", exact: true })).toBeDisabled()
  await capture("importConflict", "同一文件再次预检出现重复记录冲突，禁止覆盖或新增重复数据。")
  checks.push({ name: "category-import-commit-batch-duplicate", status: "passed", batchCode: committed.batchCode, committedCount: committed.committedCount, rows: committed.committedRows, summary: committed.summary, workbookPath })
}

async function verifyGeneration() {
  if (period.code !== "WOHENG-TZ-ENTRY-202610") throw new Error("生成验收需要已安装的泰州十月正式案例")
  await page.goto(`${baseURL}/carbon-mgmt/category/2.1`, { waitUntil: "domcontentloaded" })
  await waitForPageReady()
  await page.getByRole("button", { name: "从现有台账生成" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "从现有台账生成活动" })
  await expect(dialog).toBeVisible()
  await selectOption(dialog, "报告期", period.name)
  await capture("generateForm", "选择实际报告期、工厂和能源用电台账。")
  const generate = async (label) => {
    const promise = page.waitForResponse((response) => response.url().endsWith("/api/ghg-inventory/activities/generate") && response.request().method() === "POST")
    await dialog.getByRole("button", { name: label, exact: true }).click()
    return assertUiResponse(await promise)
  }
  const first = await generate("生成活动")
  if (first.failedCount || !first.records?.length) throw new Error(`无可验证生成结果：${JSON.stringify(first.messages)}`)
  await expect(dialog.getByText("本次生成结果", { exact: true })).toBeVisible()
  await assertResultTableFits(dialog)
  await capture("generateResult", "生成实际能源活动后，显示新增、更新、跳过数量、单位合计及记录。")
  const beforeRepeat = await listAll("/api/ghg-inventory/activities", { inventory_code: first.inventoryCode })
  const second = await generate("重新生成")
  const afterRepeat = await listAll("/api/ghg-inventory/activities", { inventory_code: first.inventoryCode })
  if (second.createdCount !== 0 || second.failedCount || beforeRepeat.length !== afterRepeat.length) throw new Error("重复生成增加记录或发生失败")
  const beforeCodes = beforeRepeat.map((row) => `${row.inventoryCode}:${row.recordCode}`).sort()
  const afterCodes = afterRepeat.map((row) => `${row.inventoryCode}:${row.recordCode}`).sort()
  if (JSON.stringify(beforeCodes) !== JSON.stringify(afterCodes)) throw new Error("重复生成改变了已有活动记录标识")
  // Updated rows are valid even when an earlier calculation references them; only identity and uniqueness must remain stable.
  const firstCodes = first.records.map((row) => row.recordCode).sort()
  const secondCodes = second.records.map((row) => row.recordCode).sort()
  if (JSON.stringify(firstCodes) !== JSON.stringify(secondCodes) || new Set(secondCodes).size !== secondCodes.length) throw new Error("重复生成结果记录不稳定或重复")
  await assertResultTableFits(dialog)
  await capture("generateRepeat", "重复生成新增为零，记录编号集合与台账数量均不增加。")
  checks.push({ name: "generate-and-repeat", retainedDemoRecords: true, status: "passed", first: { createdCount: first.createdCount, updatedCount: first.updatedCount, summary: first.summary, records: first.records }, second: { createdCount: second.createdCount, updatedCount: second.updatedCount, skippedCount: second.skippedCount, recordCodes: second.recordCodes }, stableActivityCodes: afterCodes, countBeforeRepeat: beforeRepeat.length, countAfterRepeat: afterRepeat.length })
  await dialog.getByRole("button", { name: "查看记录" }).first().click()
  await expect(page.getByRole("dialog").filter({ hasText: "活动数据详情" })).toBeVisible()
  await page.keyboard.press("Escape")
}

async function assertResultTableFits(scope) {
  const table = scope.locator("table").last()
  const width = await table.evaluate((element) => {
    const container = element.closest('[data-slot="table-container"]')
    const dialog = element.closest('[role="dialog"]')
    return { client: container.clientWidth, content: container.scrollWidth, right: element.getBoundingClientRect().right, dialogRight: dialog.getBoundingClientRect().right }
  })
  if (width.content > width.client + 1 || width.right > width.dialogRight) throw new Error(`生成结果表被抽屉裁切：${JSON.stringify(width)}`)
  await expect(table.getByRole("button", { name: "查看记录" }).first()).toBeVisible()
}

async function captureSupplementaryForms() {
  const rows = await listAll("/api/ghg-inventory/activities", { inventory_code: period.code, status: "available" })
  const cases = [
    { category: "1.4", amount: 2.4, key: "refrigerantFormLower", fields: { "设备": catalog.equipment.find((item) => item.code === "REFRIGERANT-01").name, "气体": "R32", "充注量": "2.4", "回收量": "0" }, method: "依据10月12日维修工单，补充R32为2.4 kg，本次无回收" },
    { category: "3.3", amount: 792, key: "commuteFormLower", fields: { "运输方式": "汽油乘用车", "里程(km)": "792", "人数": "1" }, method: "单程18 km × 22个工作日 × 每日往返2次 × 1人" },
    { category: "3.1", amount: 1920, key: "transportFormLower", fields: { "运输方式": "公路运输", "里程(km)": "160", "货物质量(t)": "12" }, method: "依据十月运输原表，160 km × 12 t" },
  ]
  for (const testCase of cases) {
    const row = rows.find((item) => item.isoCategoryCode === testCase.category && Number(item.activityAmount) === testCase.amount)
    if (!row) throw new Error(`缺少分类${testCase.category}正式案例，不创建替代数据`)
    await page.goto(`${baseURL}/carbon-mgmt/category/${testCase.category}?${new URLSearchParams({ inventory: row.inventoryCode, record: row.recordCode })}`, { waitUntil: "domcontentloaded" })
    await page.getByRole("button", { name: "编辑本条活动", exact: true }).click()
    const dialog = page.getByRole("dialog").filter({ hasText: "编辑活动数据" })
    await expect(dialog).toBeVisible()
    await waitForPageReady()
    await fillInput(dialog, "活动量", String(testCase.amount))
    for (const [label, value] of Object.entries(testCase.fields)) await fillOrSelect(dialog, label, value, value)
    await fillInput(dialog, "测量方法", testCase.method)
    await dialog.getByRole("button", { name: "更新活动数据", exact: true }).scrollIntoViewIfNeeded()
    await expect(dialog.getByRole("button", { name: "更新活动数据", exact: true })).toBeEnabled()
    await expect(dialog.locator("textarea").first()).toHaveValue(testCase.method)
    await capture(testCase.key, "固定1440×900，滚动实际编辑抽屉展示下半页分类字段、测量方法与保存按钮；填写后取消。")
    await page.keyboard.press("Escape")
    const unchanged = await getActivity(row.recordCode)
    if (JSON.stringify(unchanged) !== JSON.stringify(row)) throw new Error("取消编辑后正式活动发生变化")
    checks.push({ name: `category-${testCase.category}-form-lower-cancel`, status: "passed", recordCode: row.recordCode, saved: false })
  }
  await page.goto(`${baseURL}/carbon-mgmt/import?category=%221.4%22`, { waitUntil: "domcontentloaded" })
  await waitForPageReady()
  const chooserPromise = page.waitForEvent("filechooser")
  await page.getByRole("button", { name: "选择文件", exact: true }).click()
  const chooser = await chooserPromise
  const workbook = path.join(outputDir, "泰州基地十月办公楼R32维修.xlsx")
  await chooser.setFiles(workbook)
  await expect(page.getByText(path.basename(workbook), { exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "执行预检" })).toBeEnabled()
  await capture("importFilePicker", "点击中文选择文件按钮加载真实工作簿并回显中文文件名；本步骤不提交。")
  checks.push({ name: "localized-file-picker", status: "passed", submitted: false })
}

async function verifyCategoryEntry() {
  await page.goto(`${baseURL}/carbon-mgmt/category/1.4`, { waitUntil: "domcontentloaded" })
  await waitForPageReady()
  await expect(page.getByText("请选择盘查任务", { exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "新增本类活动" })).toBeDisabled()
  const labels = await selectOption(page, "盘查任务", period.name)
  if (labels.some((label) => /WOHENG-/.test(label))) throw new Error("盘查任务选项仍显示原始编号")
  await expect(page.getByRole("button", { name: "新增本类活动" })).toBeEnabled()
  const downloadButton = page.getByRole("button", { name: "下载本类模板" })
  if (await downloadButton.isDisabled()) {
    checks.push({ name: "category-template-context", status: "failed", period, organizations: catalog.organizations, profiles: catalog.reportingProfiles, areas: catalog.areas, methods: catalog.methods, category: catalog.categories.find((item) => item.code === "1.4") })
    throw new Error("选择中文十月任务后分类模板仍不可下载，见category-template-context")
  }
  await capture("categoryEntry", "按中文选择十月盘查任务，可用记录默认排除归档数据，新增与模板下载均可用。")
  const downloadPromise = page.waitForEvent("download")
  await downloadButton.click()
  const download = await downloadPromise
  await download.saveAs(path.join(outputDir, "分类入口制冷剂模板.xlsx"))
  const activityResponse = await fetchJson(`/api/ghg-inventory/activities?${new URLSearchParams({ inventory_code: period.code, category_code: "1.4", status: "available" })}`)
  if (!activityResponse.ok || activityResponse.data.items.some((row) => row.status === "archived")) throw new Error("可用记录筛选混入归档记录")
  await selectOption(page, "盘查任务", "全部盘查任务")
  const stateControl = page.getByRole("combobox", { name: "记录状态", exact: true })
  if (!(await stateControl.isVisible())) await page.getByRole("button", { name: "显示全部", exact: false }).click()
  const archivePromise = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/ghg-inventory/activities" && new URL(response.url()).searchParams.get("status") === "archived")
  await stateControl.click()
  await page.getByRole("option", { name: "已归档", exact: true }).click()
  const archived = await assertUiResponse(await archivePromise)
  if (!archived.total || archived.items.some((row) => row.status !== "archived")) throw new Error("归档筛选未保留旧核算引用记录")
  await capture("archivedRecords", "通过记录状态筛选查看保留的归档活动，旧核算引用未删除。")
  checks.push({ name: "category-template-and-active-status", status: "passed", availableCount: activityResponse.data.total, archivedCount: archived.total, taskLabels: labels })
}

async function verifyRefrigerantCalculation() {
  if (period.code !== caseProfile.inventoryCode || ownedActivities.size || ownedSources.size) throw new Error("核算验收仅可在临时数据全部清理后对十月正式演示案例执行")
  const officialRows = await listAll("/api/ghg-inventory/activities", { inventory_code: period.code, status: "available" })
  if (officialRows.length !== 8) throw new Error(`正式十月案例应为8条活动，实际${officialRows.length}条；禁止混入临时记录核算`)
  const rows = officialRows.filter((row) => row.isoCategoryCode === "1.4")
  const matches = []
  for (const row of rows) {
    if (Number(row.activityAmount) !== caseProfile.amount || !row.periodStart.startsWith("2026-10-12")) continue
    const detail = await getActivity(row.recordCode)
    if (detail?.activityDetails?.gas_code === "R32") matches.push(detail)
  }
  if (matches.length !== 1) throw new Error(`正式R32补充事件应唯一，实际${matches.length}条；不能随意选择或计算临时记录`)
  const activity = matches[0]
  if (activity.recordCode !== caseProfile.recordCode) throw new Error(`GWP验收仅核算正式维修工单${caseProfile.recordCode}`)
  const query = new URLSearchParams({ inventory_code: period.code })
  const candidatePath = `/api/ghg-inventory/activities/${encodeURIComponent(activity.recordCode)}/factor-candidates?${query}`
  const candidateResponse = await fetchJson(candidatePath)
  if (!candidateResponse.ok) throw new Error(`读取GWP候选失败：HTTP ${candidateResponse.status}`)
  const candidates = candidateResponse.data.data ?? candidateResponse.data
  const factor = candidates.items.find((item) => item.subCategory?.toLowerCase() === "r32" && Number(item.factorValue) === 675 && item.factorUnit === "kgCO2e/kg")
  if (!factor) throw new Error("缺少R32演示GWP因子675 kgCO2e/kg，不能以其他气体因子替代")
  let applied = null
  if (phase !== "calculation-only") {
  const location = new URLSearchParams({ inventory: period.code, record: activity.recordCode })
  await page.goto(`${baseURL}/carbon-mgmt/category/1.4?${location}`, { waitUntil: "domcontentloaded" })
  const dialog = page.getByRole("dialog").filter({ hasText: "活动数据详情" })
  await expect(dialog).toBeVisible()
  await selectOption(dialog, "候选因子", /R32.*675/i)
  await dialog.getByRole("button", { name: "采用因子", exact: true }).scrollIntoViewIfNeeded()
  await capture("gwpSelection", "在正式R32维修活动中选择演示GWP因子675 kgCO2e/kg。")
  const appliedPromise = page.waitForResponse((response) => response.url().includes(`/activities/${encodeURIComponent(activity.recordCode)}/factor-selection`) && response.request().method() === "PUT")
  await dialog.getByRole("button", { name: "采用因子", exact: true }).click()
  const appliedResponse = await appliedPromise
  applied = await assertUiResponse(appliedResponse)
  const refreshed = await fetchJson(candidatePath)
  if (!refreshed.ok) throw new Error("采用因子后回查失败")
  const parameters = (refreshed.data.data ?? refreshed.data).currentParameters
  const gwp = parameters.find((item) => item.parameterCode === "GWP")
  const saved = await getActivity(activity.recordCode)
  if (Number(gwp?.value) !== 675 || saved.activityDetails.gas_code !== "R32") throw new Error("采用GWP后参数值或真实气体不符")
  await expect(dialog.locator("tbody tr").filter({ hasText: "675" })).toBeVisible()
  await capture("gwpApplied", "页面采用后回查确认GWP为675，活动气体仍为R32。")
  checks.push({ name: "refrigerant-ui-gwp-selection", status: "passed", recordCode: activity.recordCode, factorId: factor.id, gwp: gwp.value, gasCode: saved.activityDetails.gas_code, applied })
  await page.keyboard.press("Escape")

  } else {
    if (Number(candidates.currentParameters.find((item) => item.parameterCode === "GWP")?.value) !== 675) throw new Error("正式活动现有GWP不是675；核算阶段不更改因子")
    checks.push({ name: "existing-refrigerant-gwp", status: "passed", recordCode: activity.recordCode, gwp: 675, changed: false })
  }
  const runs = await listAll("/api/ghg-inventory/calculation-runs", { status: "completed" })
  const contextRun = runs.find((run) => run.inventoryCode === period.code && run.reportingPeriodId === period.id)
  await page.goto(`${baseURL}/carbon/organization/records?${new URLSearchParams(contextRun ? { run: contextRun.runCode } : {})}`, { waitUntil: "domcontentloaded" })
  await waitForPageReady()
  const { boundary, organization } = await resolveCalculationContext()
  for (const [label, option] of [["报告组织", organization.name], ["报告期", period.name], ["核算边界", boundary.boundaryName ?? boundary.boundary_name]]) {
    const control = page.getByRole("combobox", { name: label, exact: true })
    await control.click()
    await page.getByRole("option", { name: option, exact: false }).click()
    await expect(control).toContainText(option)
  }
  const calculateButton = page.getByRole("button", { name: /^(重新核算|执行核算)$/ })
  await expect(calculateButton).toBeEnabled()
  const calculatePromise = page.waitForResponse((response) => response.url().endsWith("/api/ghg-inventory/calculation-runs") && response.request().method() === "POST")
  await capture("calculationReady", "已选定十月正式案例的核算上下文，页面准备检查允许执行核算。")
  await calculateButton.click()
  const calculatedResponse = await calculatePromise
  const calculated = await assertUiResponse(calculatedResponse)
  const runCode = calculated.runCode ?? calculated.data?.runCode
  if (!runCode) throw new Error("实际核算未返回运行编号")
  const runResponse = await fetchJson(`/api/ghg-inventory/calculation-runs/${encodeURIComponent(runCode)}`)
  if (!runResponse.ok) throw new Error("新核算运行回查失败")
  assertRunContext(runResponse.data, { boundary, organization })
  if (Number(runResponse.data.totalCo2EKg) !== caseProfile.totalCo2eKg || new Set(runResponse.data.results.map((row) => row.recordCode)).size !== 8) throw new Error(`正式八条活动总量应为${caseProfile.totalCo2eKg} kgCO2e`)
  const result = runResponse.data.results.find((row) => row.recordCode === activity.recordCode)
  if (result?.gasCode !== "R32" || Number(result.gasMassKg) !== caseProfile.amount || Number(result.co2eKg) !== caseProfile.co2eKg) throw new Error(`R32新核算结果错误：${JSON.stringify(result)}`)
  const resultDetail = await captureCalculationResult(runCode, activity)
  checks.push({ name: "refrigerant-ui-factor-and-calculation", status: "passed", retainedDemoRecords: true, caseKind: "official-demo", officialActivityCount: officialRows.length, totalCo2EKg: runResponse.data.totalCo2EKg, recordCode: activity.recordCode, factorId: factor.id, gwp: 675, factorSource: factor.source, applied, runCode, reportingPeriodId: runResponse.data.reportingPeriodId, organizationBoundaryId: runResponse.data.organizationBoundaryId, result, resultDetail })
  await page.keyboard.press("Escape")
}

async function resolveCalculationContext() {
  const organizations = catalog.organizations.filter((item) => Number(item.id) === Number(period.reportingOrgId))
  if (organizations.length !== 1 || (period.organizationCode && organizations[0].code !== period.organizationCode)) throw new Error("报告期所属组织不唯一或组织代码不一致")
  const organization = organizations[0]
  const boundaries = []
  for (let offset = 0; ; offset += 100) {
    const response = await fetchJson(`/api/carbon/organization-boundary/boundaries?limit=100&offset=${offset}`)
    if (!response.ok) throw new Error(`月度边界列表读取失败：HTTP ${response.status}`)
    const payload = response.data.data ?? response.data
    const rows = Array.isArray(payload) ? payload : payload.items ?? payload.data ?? []
    boundaries.push(...rows.map((row) => ({
      ...row,
      id: Number(row.id),
      reportingOrgId: Number(row.reportingOrgId ?? row.reporting_org_id),
      periodId: Number(row.periodId ?? row.period_id),
      boundaryNo: row.boundaryNo ?? row.boundary_no,
      boundaryName: row.boundaryName ?? row.boundary_name,
    })))
    if (rows.length < 100 || (payload.total != null && boundaries.length >= Number(payload.total))) break
  }
  const matching = boundaries.filter((item) => item.reportingOrgId === Number(organization.id) && item.periodId === Number(period.id) && item.status === "published")
  const stableCodeMatches = matching.filter((item) => item.boundaryNo === `${caseProfile.inventoryCode}-BOUNDARY`)
  const candidates = stableCodeMatches.length ? stableCodeMatches : matching
  if (candidates.length !== 1) throw new Error(`任务${period.code}、组织${organization.name}的已发布月度边界不唯一：${candidates.length}项`)
  const boundary = candidates[0]
  checks.push({ name: "resolve-calculation-context", status: "passed", inventoryCode: period.code, reportingPeriodId: period.id, reportingPeriodName: period.name, reportingOrgId: organization.id, organizationCode: organization.code, organizationBoundaryId: boundary.id, boundaryNo: boundary.boundaryNo, boundaryName: boundary.boundaryName, boundaryStatus: boundary.status })
  return { boundary, organization }
}

function assertRunContext(run, { boundary, organization }) {
  if (run.inventoryCode !== period.code || Number(run.reportingPeriodId) !== Number(period.id) || Number(run.reportingOrgId) !== Number(organization.id) || Number(run.organizationBoundaryId) !== boundary.id) throw new Error("核算运行与动态解析的盘查任务、报告期、组织或已发布边界不一致")
}

async function recaptureExistingCalculation() {
  const report = JSON.parse(await fs.readFile(path.join(verificationDir, caseProfileName === "huzhou" ? "ghg-maintenance-calculation-only.json" : "ghg-maintenance-calculation.json"), "utf8"))
  const check = report.checks.find((item) => item.name === "refrigerant-ui-factor-and-calculation" && item.status === "passed")
  if (report.status !== "passed" || report.inventoryCode !== period.code || !check) throw new Error("没有本轮实际核算通过的运行，不能仅展示种子结果")
  const context = await resolveCalculationContext()
  const existingRun = await fetchJson(`/api/ghg-inventory/calculation-runs/${encodeURIComponent(check.runCode)}`)
  if (!existingRun.ok) throw new Error("本轮已验证运行无法回查")
  assertRunContext(existingRun.data, context)
  const activity = await getActivity(check.recordCode)
  await captureCalculationResult(check.runCode, activity)
  checks.push({ name: "calculation-result-screenshot-review", status: "passed", readOnly: true, runCode: check.runCode, recordCode: check.recordCode })
  await page.keyboard.press("Escape")
}

async function captureCalculationResult(runCode, activity) {
  await page.goto(`${baseURL}/carbon/organization/records?${new URLSearchParams({ run: runCode })}`, { waitUntil: "domcontentloaded" })
  const resultTable = page.locator("table").filter({ has: page.getByRole("columnheader", { name: "活动/排放源", exact: true }) })
  await expect(resultTable.locator("tbody tr")).toHaveCount(8)
  await expect(page.getByRole("combobox", { name: "报告期", exact: true })).toContainText(period.name)
  await capture("calculationReady", "本月正式运行的核算上下文、8条活动与全量排放总量。", page.getByRole("heading", { name: "组织碳核算", exact: true }))
  await capture("calculationResults", "清除关键词筛选，本次正式运行8条活动的活动量、方法、区域设备与排放结果。")
  await page.goto(`${baseURL}/carbon/organization/records?${new URLSearchParams({ run: runCode, keyword: activity.recordCode })}`, { waitUntil: "domcontentloaded" })
  const resultRow = rowFor(activity.recordCode)
  await expect(resultRow).toContainText("R32")
  await expect(resultRow).toContainText(String(caseProfile.amount))
  await expect(resultRow).toContainText((caseProfile.co2eKg / 1000).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
  await resultRow.scrollIntoViewIfNeeded()
  await capture("gwpResult", `页面实际核算的新运行：R32活动量${caseProfile.amount} kg，排放量${caseProfile.co2eKg} kgCO₂e。`, resultRow.locator("xpath=ancestor::table"))
  const detailPromise = page.waitForResponse((response) => response.url().includes(`/api/ghg-inventory/results/${encodeURIComponent(activity.recordCode)}?`) && response.request().method() === "GET")
  await resultRow.click()
  const resultDetail = await assertUiResponse(await detailPromise)
  if (Number(resultDetail.result.activityAmount) !== caseProfile.amount || resultDetail.result.gasCode !== "R32" || Number(resultDetail.result.calculatedCo2EKg) !== caseProfile.co2eKg) throw new Error("页面结果详情与新运行结果不一致")
  const gwpAssignment = resultDetail.assignments.find((item) => item.parameterCode === "GWP")
  if (Number(gwpAssignment?.value) !== 675 || gwpAssignment.parameterRole !== "characterization") throw new Error("核算快照未按表征参数保存GWP")
  const resultDialog = page.getByRole("dialog")
  await expect(resultDialog.getByText("参数与因子", { exact: true })).toBeVisible()
  await capture("calculationDetail", "本次新运行的R32结果详情与实际采用的GWP参数。")
  await capture("gwpDetail", "新运行详情保留R32、实际活动量和GWP参数快照。")
  return resultDetail
}

async function fillInput(scope, label, value) {
  const labelLocator = scope.locator("label", { hasText: label }).first()
  const control = labelLocator.locator("xpath=ancestor::div[contains(@class, 'space-y-1.5')][1]//*[self::input or self::textarea]").first()
  const readonly = await control.evaluate((element) => element instanceof HTMLInputElement && element.readOnly).catch(() => false)
  if (readonly && /^\d{4}-\d{2}-\d{2}$/.test(String(value))) {
    const container = labelLocator.locator("xpath=ancestor::div[contains(@class, 'space-y-1.5')][1]")
    const [year, month, day] = String(value).split("-").map(Number)
    const current = (await control.inputValue()).match(/(\d{4})年(\d{2})月/)
    if (!current) throw new Error(`日期控件缺少可识别月份：${label}`)
    await control.click()
    const delta = (year - Number(current[1])) * 12 + month - Number(current[2])
    for (let index = 0; index < Math.abs(delta); index += 1) await container.getByRole("button", { name: delta > 0 ? "下个月" : "上个月", exact: true }).click()
    const dates = container.getByRole("button", { name: String(day), exact: true })
    await (day > 20 ? dates.last() : dates.first()).click()
    await expect(control).toHaveValue(`${year}年${String(month).padStart(2, "0")}月${String(day).padStart(2, "0")}日`)
    return
  }
  if (readonly) throw new Error(`不能填写只读字段：${label}`)
  await control.fill(String(value))
  await expect(control).toHaveValue(String(value))
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
  const optionLabels = await page.getByRole("option").allTextContents()
  try { await page.getByRole("option", { name: option, exact: false }).first().click({ timeout: 8000 }); await expect(trigger).toContainText(option) }
  catch { throw new Error(`未找到${label}选项“${option}”，实际选项：${JSON.stringify(await page.getByRole("option").allTextContents())}`) }
  return optionLabels
}

async function capture(key, note, anchor) {
  await injectScreenshotCss()
  await waitForPageReady()
  await assertBusinessPage()
  if (anchor) {
    await anchor.scrollIntoViewIfNeeded()
    await expect(anchor).toBeInViewport({ ratio: 1 })
  }
  if (key === "calculationResults") {
    const table = page.locator("table").filter({ has: page.getByRole("columnheader", { name: "活动/排放源", exact: true }) })
    await table.scrollIntoViewIfNeeded()
    const rows = table.locator("tbody tr")
    await expect(rows).toHaveCount(8)
    for (let index = 0; index < 8; index += 1) {
      await expect(rows.nth(index).locator("td").nth(2)).toBeInViewport({ ratio: 1 })
      await expect(rows.nth(index).locator("td").nth(5)).toBeInViewport({ ratio: 1 })
    }
  }
  const file = path.join(screenshotDir, screenshots[key])
  const toastStyle = await hideToastForScreenshot()
  try {
    await page.screenshot({ path: file, fullPage: false, animations: "disabled" })
    console.log(`截图完成：${key}`)
  } finally {
    await toastStyle.evaluate((element) => element.remove()).catch(() => {})
  }
  const previous = artifacts.findIndex((item) => item.key === key)
  const artifact = { key, note, screenshotPath: file, viewport: `${viewport.width}x${viewport.height}` }
  if (previous < 0) artifacts.push(artifact)
  else artifacts[previous] = artifact
  const priorCheck = checks.findIndex((item) => item.name === `screenshot-${key}`)
  const screenshotCheck = { name: `screenshot-${key}`, status: "passed", screenshotPath: file }
  if (priorCheck < 0) checks.push(screenshotCheck)
  else checks[priorCheck] = screenshotCheck
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
  // Radix transitions are finished above; screenshots disable remaining animations.
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
  const report = {
    title: "组织碳排放源与活动数据维护验证", phase, status, startedAt, finishedAt: new Date().toISOString(),
    baseURL, tenantSlug, caseProfile: caseProfileName, inventoryCode: period?.code, sourceCode, recordCode, viewport: `${viewport.width}x${viewport.height}`,
    isSuperuser: activeUser?.isSuperuser ?? null, locale: "zh-CN", timezoneId: "Asia/Shanghai",
    checks, artifacts, apiFailures, consoleErrors, businessWrites,
    remainingOwnedActivities: [...ownedActivities.keys()], remainingOwnedSources: [...ownedSources.keys()],
    failureReason: error instanceof Error ? error.message : error ? String(error) : "",
  }
  const phasePath = path.join(verificationDir, `ghg-maintenance-${phase}.json`)
  await fs.writeFile(phasePath, `${JSON.stringify(report, null, 2)}\n`)
  const priorPhases = phase === "calculation-evidence" ? (caseProfileName === "huzhou" ? ["calculation-only"] : ["import", "forms", "import-only", "generation", "calculation"]) : phase === "forms" ? ["import"] : phase === "import-only" ? ["import", "forms"] : phase === "generation" ? ["import", "forms", "import-only", "calculation"] : phase === "calculation" ? ["import", "forms", "import-only", "generation"] : []
  const priorReports = []
  for (const priorPhase of priorPhases) {
    const priorPath = path.join(verificationDir, `ghg-maintenance-${priorPhase}.json`)
    let prior = null
    try { prior = JSON.parse(await fs.readFile(priorPath, "utf8")) } catch { /* Missing phases remain absent, never implied passed. */ }
    if (prior?.status === "passed" && prior.isSuperuser === false && prior.tenantSlug === tenantSlug && prior.inventoryCode === period?.code) priorReports.push({ ...prior, reportPath: priorPath })
  }
  if (priorReports.length) {
    report.phase = [...priorReports.map((prior) => prior.phase), phase].join("-and-")
    report.phaseReports = [...priorReports.map((prior) => prior.reportPath), phasePath]
    report.checks = [...priorReports.flatMap((prior) => prior.checks), ...checks]
    report.artifacts = [...new Map([...priorReports.flatMap((prior) => prior.artifacts), ...artifacts].map((item) => [item.key, item])).values()]
    report.apiFailures = [...priorReports.flatMap((prior) => prior.apiFailures), ...apiFailures]
    report.consoleErrors = [...priorReports.flatMap((prior) => prior.consoleErrors), ...consoleErrors]
  }
  await fs.writeFile(verificationPath, `${JSON.stringify(report, null, 2)}\n`)
}
