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
const verificationPath = path.join(verificationDir, "area-device-maintenance.json")
const viewport = { width: 1440, height: 900 }
const startedAt = new Date().toISOString()

const stamp = process.env.MANUAL_VERIFY_STAMP ?? "20260901"
const areaCode = `MANUAL-AREA-${stamp}`
const areaName = "手册验证仓储分区"
const areaNameEdited = "手册验证仓储分区-已编辑"
const deviceCode = `MANUAL-DEVICE-${stamp}`
const deviceName = "手册验证电表"
const deviceNameEdited = "手册验证电表-已编辑"
const pointCode = "forward_active_total"
const pointName = "正向有功总电能"
const pointNameEdited = "正向有功总电能-已核对"
const gatewayKey = "WH-GW-01"
const meterKey = "m901"
const externalDeviceId = `WH-MANUAL-${stamp}`
const sourceTag = "EPI_TOTAL"
const meterPointCode = pointCode

const screenshots = {
  areaCreate: "EV-WH-066-区域新增表单.png",
  areaDetail: "EV-WH-067-区域详情与层级回显.png",
  deviceCreate: "EV-WH-068-设备新增表单与区域挂载.png",
  deviceDetail: "EV-WH-069-设备详情与采集配置.png",
  pointCreate: "EV-WH-070-测点新增表单.png",
  pointDetail: "EV-WH-071-测点编辑后回显.png",
  mqttBinding: "EV-WH-072-MQTT表计绑定表单.png",
  mqttMapping: "EV-WH-073-MQTT点位映射表单.png",
  mqttTest: "EV-WH-074-MQTT接入测试结果.png",
  areaEdit: "EV-WH-075-区域编辑表单.png",
  areaDisabled: "EV-WH-076-区域停用状态.png",
  areaDeleted: "EV-WH-077-区域删除后结果.png",
  deviceEdit: "EV-WH-078-设备编辑表单.png",
  deviceDisabled: "EV-WH-079-设备停用状态.png",
  deviceEnabled: "EV-WH-080-设备恢复状态.png",
  deviceDeleted: "EV-WH-081-设备删除后结果.png",
  pointEdit: "EV-WH-082-测点编辑表单.png",
  pointDeleted: "EV-WH-083-测点删除后结果.png",
  mqttBindingSaved: "EV-WH-084-MQTT表计绑定保存后回显.png",
  mqttBindingEdit: "EV-WH-085-MQTT表计绑定编辑表单.png",
  mqttMappingSaved: "EV-WH-086-MQTT点位映射保存后回显.png",
  mqttMappingEdit: "EV-WH-087-MQTT点位映射编辑表单.png",
  mqttMappingDeleted: "EV-WH-088-MQTT点位映射删除后结果.png",
  mqttBindingDeleted: "EV-WH-089-MQTT表计绑定删除后结果.png",
}

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
const notFoundResponses = []
const checks = []
const artifacts = []
let activeTeamId = null
let activeUser = null
let createdAreaId = null
let createdDeviceId = null
let createdPointId = null
let createdBindingId = null
let createdMappingId = null

await context.route("**/api/**", async (route) => {
  const headers = { ...route.request().headers() }
  if (activeTeamId) headers["x-team-id"] = activeTeamId
  await route.continue({ headers })
})

page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push({ text: message.text(), at: new Date().toISOString() })
})
page.on("response", (response) => {
  const status = response.status()
  if (status === 404) {
    notFoundResponses.push({
      method: response.request().method(),
      url: response.url().replace(baseURL, ""),
      at: new Date().toISOString(),
    })
  }
  if (!response.url().includes("/api/")) return
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
  console.log("[AreaDeviceVerify] Preflight 100% | Auth 0% | Area 0/5 | Device 0/8 | Point 0/3 | MQTT 0/7 | Cleanup 0/1")
  await ensureAuthenticated()
  await selectTenant()
  await cleanupAll()
  apiFailures.length = 0
  consoleErrors.length = 0
  notFoundResponses.length = 0
  console.log("[AreaDeviceVerify] Preflight 100% | Auth 100% | Area 0/5 | Device 0/8 | Point 0/3 | MQTT 0/7 | Cleanup 0/1")

  await verifyAreaMaintenance()
  await verifyDeviceMaintenance()
  await verifyPointMaintenance()
  await verifyMqttMaintenance()
  await verifyLifecycleCleanup()
  await cleanupAll()
  checks.push({ name: "cleanup", status: "passed", areaCode, deviceCode, pointCode })
  await writeVerification("passed")
  console.log("[AreaDeviceVerify] Preflight 100% | Auth 100% | Area 5/5 | Device 8/8 | Point 3/3 | MQTT 7/7 | Cleanup 1/1")
} catch (error) {
  await writeVerification("failed", error)
  console.error(error)
  process.exitCode = 1
} finally {
  await browser.close()
}

async function verifyAreaMaintenance() {
  await page.goto(`${baseURL}/data/monitor-area`, { waitUntil: "domcontentloaded" })
  await injectScreenshotCss()
  await waitForPageReady()
  await assertBusinessPage(["区域主数据工作台", "区域树", "新增子区域", "新增同级", "基础信息", "本区域设备"])
  checks.push({ name: "open-area-workbench", status: "passed" })

  await page.getByRole("button", { name: "新增子区域" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "新增区域" })
  await dialog.waitFor({ state: "visible" })
  await fillInput(dialog, "区域编码", areaCode)
  await fillInput(dialog, "区域名称", areaName)
  await selectOption(dialog, "区域类型", "仓库")
  await fillInput(dialog, "负责人", "区域管理员")
  await fillInput(dialog, "归属部门", "仓储运维部")
  await fillInput(dialog, "位置说明", "泰州生产基地总装仓储区")
  await fillInput(dialog, "备注", "区域维护验证")
  await capture("areaCreate", "区域新增表单填写态。")
  await dialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("区域已创建")
  await waitForPageReady()
  createdAreaId = (await getAreaByCode(areaCode))?.id ?? null
  if (!createdAreaId) throw new Error("区域新增后接口未能回读记录")
  checks.push({ name: "area-create", status: "passed", areaCode, areaId: createdAreaId })

  await selectAreaInTree(areaName)
  await page.getByRole("button", { name: "编辑" }).click()
  const editDialog = page.getByRole("dialog").filter({ hasText: "编辑区域" })
  await editDialog.waitFor({ state: "visible" })
  await fillInput(editDialog, "区域名称", areaNameEdited)
  await fillInput(editDialog, "备注", "区域维护编辑验证")
  await capture("areaEdit", "区域编辑表单填写态。")
  await editDialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("区域已更新")
  await waitForPageReady()
  await selectAreaInTree(areaNameEdited)
  await expectVisible(areaCode)
  await expectVisible("仓库")
  await expectVisible("区域维护编辑验证")
  await capture("areaDetail", "区域编辑后详情、层级和设备统计回显。")
  checks.push({ name: "area-update-and-detail", status: "passed", areaCode, areaId: createdAreaId })

  await page.getByRole("button", { name: "停用" }).click()
  await expectVisible("区域已停用")
  await waitForPageReady()
  await capture("areaDisabled", "区域停用后的详情状态。")
  const disabled = await getAreaByCode(areaCode)
  if (disabled?.is_enabled !== false && disabled?.is_enable !== false) throw new Error("区域停用后接口回读状态不是停用")
  checks.push({ name: "area-disable", status: "passed", areaCode, areaId: createdAreaId })
  await fetchJson(`/api/master-data/areas/${createdAreaId}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ is_enabled: true }),
  })
}

async function verifyDeviceMaintenance() {
  await page.goto(`${baseURL}/data/terminals`, { waitUntil: "domcontentloaded" })
  await injectScreenshotCss()
  await waitForPageReady()
  await assertBusinessPage(["设备台账", "设备列表", "新增设备", "区域", "设备类型"])
  checks.push({ name: "open-device-workbench", status: "passed" })

  await page.getByRole("button", { name: "新增设备" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "新增设备" })
  await dialog.waitFor({ state: "visible" })
  await fillInput(dialog, "设备编码", deviceCode)
  await fillInput(dialog, "设备名称", deviceName)
  await selectOption(dialog, "所属区域", areaNameEdited)
  await selectOption(dialog, "设备类型", "电表")
  await fillInput(dialog, "资产编码", `ASSET-${stamp}`)
  await fillInput(dialog, "采集标识", externalDeviceId)
  await fillInput(dialog, "厂家", "沃衡演示")
  await fillInput(dialog, "型号", "WH-METER-1")
  await fillInput(dialog, "归属部门", "仓储运维部")
  await fillInput(dialog, "维护负责人", "设备管理员")
  await selectOption(dialog, "能源类型", "外购电力")
  await selectOption(dialog, "采集协议", "MQTT")
  await selectOption(dialog, "在线状态", "在线")
  await selectOption(dialog, "投运状态", "投运")
  await fillInput(dialog, "位置说明", "手册验证区域配电箱")
  await fillInput(dialog, "备注", "设备维护验证")
  await capture("deviceCreate", "设备新增表单填写态，设备挂载到刚创建的区域。")
  await dialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("设备已创建")
  await waitForPageReady()
  createdDeviceId = (await getDeviceByCode(deviceCode))?.id ?? null
  if (!createdDeviceId) throw new Error("设备新增后接口未能回读记录")
  checks.push({ name: "device-create", status: "passed", deviceCode, deviceId: createdDeviceId, areaId: createdAreaId })

  await searchDevice(deviceCode)
  await selectDeviceRow(deviceCode)
  await expectVisible(deviceName)
  await expectVisible(areaNameEdited)
  await expectVisible("电表")
  await page.getByRole("tab", { name: "接入" }).click()
  await expectVisible("采集配置")
  await expectVisible("MQTT")
  await expectVisible("外购电力")
  await capture("deviceDetail", "设备详情和采集配置回显。")
  checks.push({ name: "device-detail", status: "passed", deviceCode })

  await page.getByRole("button", { name: "编辑" }).click()
  const editDialog = page.getByRole("dialog").filter({ hasText: "编辑设备" })
  await editDialog.waitFor({ state: "visible" })
  await fillInput(editDialog, "设备名称", deviceNameEdited)
  await fillInput(editDialog, "维护负责人", "设备管理员-已编辑")
  await fillInput(editDialog, "备注", "设备维护编辑验证")
  await capture("deviceEdit", "设备编辑表单填写态。")
  await editDialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("设备已更新")
  await waitForPageReady()
  await searchDevice(deviceCode)
  await selectDeviceRow(deviceCode)
  await page.getByRole("tab", { name: "基础" }).click()
  await expectVisible(deviceNameEdited)
  await expectVisible("设备管理员-已编辑")
  checks.push({ name: "device-update-and-detail", status: "passed", deviceCode, deviceId: createdDeviceId })
}

async function verifyPointMaintenance() {
  await page.getByRole("tab", { name: "测点" }).click()
  await page.getByRole("button", { name: "新增测点" }).click()
  const dialog = page.getByRole("dialog").filter({ hasText: "新增测点" })
  await dialog.waitFor({ state: "visible" })
  await fillInput(dialog, "测点编码", pointCode)
  await fillInput(dialog, "测点名称", pointName)
  await selectOption(dialog, "数值类型", "浮点数")
  await fillInput(dialog, "单位", "kWh")
  await fillInput(dialog, "来源字段", "EPI")
  await fillInput(dialog, "采样周期", "300")
  await selectOption(dialog, "启用", "启用")
  await selectOption(dialog, "告警启用", "启用")
  await fillInput(dialog, "上限", "9999")
  await fillInput(dialog, "下限", "0")
  await fillInput(dialog, "备注", "测点维护验证")
  await capture("pointCreate", "测点新增表单填写态，测点挂载在当前设备。")
  await dialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("测点已创建")
  await waitForPageReady()
  createdPointId = (await getPointByCode(pointCode))?.id ?? null
  if (!createdPointId) throw new Error("测点新增后接口未能回读记录")
  checks.push({ name: "point-create", status: "passed", pointCode, pointId: createdPointId, deviceId: createdDeviceId })

  await pointRow(pointCode).getByRole("button", { name: "编辑" }).click()
  const editDialog = page.getByRole("dialog").filter({ hasText: "编辑测点" })
  await editDialog.waitFor({ state: "visible" })
  await fillInput(editDialog, "测点名称", pointNameEdited)
  await fillInput(editDialog, "来源字段", sourceTag)
  await fillInput(editDialog, "备注", "测点维护编辑验证")
  await capture("pointEdit", "测点编辑表单填写态。")
  await editDialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("测点已更新")
  await waitForPageReady()
  await expectVisible(pointNameEdited)
  await expectVisible(sourceTag)
  await capture("pointDetail", "测点编辑后在设备详情测点页签回显。")
  checks.push({ name: "point-update-and-detail", status: "passed", pointCode, pointId: createdPointId })
}

async function verifyMqttMaintenance() {
  await page.getByRole("tab", { name: "接入" }).click()
  await waitForPageReady()
  await expectVisible("MQTT接入")
  await page.getByRole("button", { name: "配置表计绑定" }).click()
  const bindingDialog = page.getByRole("dialog").filter({ hasText: "配置MQTT表计绑定" })
  await bindingDialog.waitFor({ state: "visible" })
  await fillInput(bindingDialog, "网关标识", gatewayKey)
  await fillInput(bindingDialog, "表计编号", meterKey)
  await fillInput(bindingDialog, "匹配名称", externalDeviceId)
  await fillInput(bindingDialog, "外部设备号", externalDeviceId)
  await fillInput(bindingDialog, "临时地址", "配电箱-A1")
  await selectOption(bindingDialog, "绑定状态", "已确认")
  await fillInput(bindingDialog, "倍率", "1")
  await capture("mqttBinding", "MQTT表计绑定表单填写态。")
  await bindingDialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("MQTT绑定已创建")
  await waitForPageReady()
  const binding = await getMqttBindingByDevice(createdDeviceId)
  if (!binding?.id) throw new Error("MQTT绑定新增后接口未能回读记录")
  createdBindingId = binding.id
  await expectVisible(`${gatewayKey} / ${meterKey}`)
  await capture("mqttBindingSaved", "MQTT表计绑定保存后的设备接入页回显。")
  checks.push({ name: "mqtt-binding-create", status: "passed", bindingId: createdBindingId, deviceId: createdDeviceId })

  await page.getByRole("button", { name: "编辑绑定" }).click()
  const bindingEditDialog = page.getByRole("dialog").filter({ hasText: "编辑MQTT表计绑定" })
  await bindingEditDialog.waitFor({ state: "visible" })
  await fillInput(bindingEditDialog, "临时地址", "配电箱-A1-已核对")
  await capture("mqttBindingEdit", "MQTT表计绑定编辑表单填写态。")
  await bindingEditDialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("MQTT绑定已更新")
  await waitForPageReady()
  const updatedBinding = await getMqttBindingByDevice(createdDeviceId)
  if (updatedBinding?.temporary_address !== "配电箱-A1-已核对") throw new Error("MQTT绑定编辑后接口未能回读临时地址")
  checks.push({ name: "mqtt-binding-update", status: "passed", bindingId: createdBindingId })

  await page.getByRole("button", { name: "新增映射" }).click()
  const mappingDialog = page.getByRole("dialog").filter({ hasText: "新增点位映射" })
  await mappingDialog.waitFor({ state: "visible" })
  const meterPoint = await getDevicePointByCode(meterPointCode)
  if (!meterPoint) throw new Error(`当前设备缺少电表标准测点：${meterPointCode}`)
  await fillInput(mappingDialog, "来源Tag", sourceTag)
  await selectOption(mappingDialog, "平台测点", `${meterPoint.point_name} / ${meterPoint.point_code}`)
  await fillInput(mappingDialog, "测点名称", meterPoint.point_name)
  await fillInput(mappingDialog, "来源名称", meterPoint.point_name)
  await fillInput(mappingDialog, "单位", meterPoint.unit ?? "kWh")
  await fillInput(mappingDialog, "倍率", "1")
  await fillInput(mappingDialog, "版本", "v1")
  await capture("mqttMapping", "MQTT来源Tag映射到当前设备测点。")
  await mappingDialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("点位映射已创建")
  await waitForPageReady()
  const mapping = await getMqttMappingByBinding(createdBindingId, sourceTag)
  if (!mapping?.id) throw new Error("MQTT点位映射新增后接口未能回读记录")
  createdMappingId = mapping.id
  await expectVisible(`${sourceTag} -> ${meterPointCode}`)
  await capture("mqttMappingSaved", "MQTT点位映射保存后的接入页回显。")
  checks.push({ name: "mqtt-mapping-create", status: "passed", mappingId: createdMappingId, bindingId: createdBindingId })

  await mqttMappingRow(sourceTag, meterPointCode).getByRole("button", { name: "编辑" }).click()
  const mappingEditDialog = page.getByRole("dialog").filter({ hasText: "编辑点位映射" })
  await mappingEditDialog.waitFor({ state: "visible" })
  await fillInput(mappingEditDialog, "来源名称", `${meterPoint.point_name}-已核对`)
  await fillInput(mappingEditDialog, "版本", "v2")
  await capture("mqttMappingEdit", "MQTT点位映射编辑表单填写态。")
  await mappingEditDialog.getByRole("button", { name: "保存" }).click()
  await expectVisible("点位映射已更新")
  await waitForPageReady()
  const updatedMapping = await getMqttMappingByBinding(createdBindingId, sourceTag)
  if (updatedMapping?.mapping_version !== "v2") throw new Error("MQTT点位映射编辑后接口未能回读版本")
  checks.push({ name: "mqtt-mapping-update", status: "passed", mappingId: createdMappingId })

  await page.getByRole("button", { name: "发送测试报文" }).click()
  await expectVisible("MQTT测试报文已处理")
  await waitForPageReady()
  await capture("mqttTest", "MQTT绑定、映射和测试报文结果态。")
  checks.push({ name: "mqtt-test-message", status: "passed", bindingId: createdBindingId, mappingId: createdMappingId })
}

async function verifyLifecycleCleanup() {
  await mqttMappingRow(sourceTag, meterPointCode).getByRole("button", { name: "删除" }).click()
  await expectVisible("点位映射已删除")
  await waitForPageReady()
  await capture("mqttMappingDeleted", "MQTT点位映射删除后的接入页结果态。")
  if (await getMqttMappingByBinding(createdBindingId, sourceTag)) throw new Error("MQTT映射删除后接口仍能回读记录")
  checks.push({ name: "mqtt-mapping-delete", status: "passed", mappingId: createdMappingId })
  createdMappingId = null

  page.once("dialog", (dialog) => dialog.accept())
  await page.getByRole("button", { name: "删除绑定" }).click()
  await expectVisible("MQTT绑定已删除")
  await waitForPageReady()
  await capture("mqttBindingDeleted", "MQTT表计绑定删除后的接入页结果态。")
  if (await getMqttBindingByDevice(createdDeviceId)) throw new Error("MQTT绑定删除后接口仍能回读记录")
  checks.push({ name: "mqtt-binding-delete", status: "passed", bindingId: createdBindingId })
  createdBindingId = null

  await page.getByRole("tab", { name: "测点" }).click()
  await pointRow(pointCode).getByRole("button", { name: "删除" }).click()
  await expectVisible("测点已删除")
  await waitForPageReady()
  await capture("pointDeleted", "测点删除后的设备测点列表结果态。")
  if (await getPointByCode(pointCode)) throw new Error("测点删除后接口仍能回读记录")
  checks.push({ name: "point-delete", status: "passed", pointCode, pointId: createdPointId })
  createdPointId = null

  await page.getByRole("tab", { name: "基础" }).click()
  await page.getByRole("button", { name: "停用" }).click()
  await expectVisible("设备已停用")
  await waitForPageReady()
  await capture("deviceDisabled", "设备停用后的详情状态。")
  const disabledDevice = await getDeviceByCode(deviceCode)
  if (disabledDevice?.is_enabled !== false && disabledDevice?.is_enable !== false) throw new Error("设备停用后接口回读状态不是停用")
  checks.push({ name: "device-disable", status: "passed", deviceCode, deviceId: createdDeviceId })

  await page.getByRole("button", { name: "恢复" }).click()
  await expectVisible("设备已恢复")
  await waitForPageReady()
  await capture("deviceEnabled", "设备恢复后的详情状态。")
  const enabledDevice = await getDeviceByCode(deviceCode)
  if (enabledDevice?.is_enabled === false || enabledDevice?.is_enable === false) throw new Error("设备恢复后接口回读状态不是启用")
  checks.push({ name: "device-enable", status: "passed", deviceCode, deviceId: createdDeviceId })

  await page.getByRole("tab", { name: "测点" }).click()
  await deleteRemainingDevicePoints()
  checks.push({ name: "default-point-cleanup", status: "passed", deviceId: createdDeviceId })
  await page.getByRole("tab", { name: "基础" }).click()

  page.once("dialog", (dialog) => dialog.accept())
  await page.getByRole("button", { name: "删除", exact: true }).click()
  await expectVisible("设备已删除")
  await waitForPageReady()
  await capture("deviceDeleted", "设备删除后设备台账结果态。")
  if (await getDeviceByCode(deviceCode)) throw new Error("设备删除后接口仍能回读记录")
  checks.push({ name: "device-delete", status: "passed", deviceCode, deviceId: createdDeviceId })
  createdDeviceId = null

  await page.goto(`${baseURL}/data/monitor-area`, { waitUntil: "domcontentloaded" })
  await injectScreenshotCss()
  await waitForPageReady()
  await selectAreaInTree(areaNameEdited)
  page.once("dialog", (dialog) => dialog.accept())
  await page.getByRole("button", { name: "删除", exact: true }).click()
  await expectVisible("区域已删除")
  await waitForPageReady()
  await capture("areaDeleted", "区域删除后工作台结果态。")
  if (await getAreaByCode(areaCode)) throw new Error("区域删除后接口仍能回读记录")
  checks.push({ name: "area-delete", status: "passed", areaCode, areaId: createdAreaId })
  createdAreaId = null
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
    if (login.data?.mfaRequired) throw new Error("验证账号开启了 MFA，无法用于自动化验证。")
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

async function cleanupAll() {
  for (const binding of await getManualMqttBindings()) {
    await fetchJson(`/api/iot-ingestion/mqtt-device-bindings/${binding.id}`, { method: "DELETE" })
  }
  const device = await getDeviceByCode(deviceCode)
  if (device?.id) {
    const detail = await fetchJson(`/api/master-data/devices/${device.id}`)
    for (const point of detail.data?.points ?? []) {
      await fetchJson(`/api/master-data/device-points/${point.id}`, { method: "DELETE" })
    }
    await fetchJson(`/api/master-data/devices/${device.id}`, { method: "DELETE" })
  }
  const area = await getAreaByCode(areaCode)
  if (area?.id) await fetchJson(`/api/master-data/areas/${area.id}`, { method: "DELETE" })
  createdAreaId = null
  createdDeviceId = null
  createdPointId = null
  createdBindingId = null
  createdMappingId = null
}

async function getAreaByCode(code) {
  const response = await fetchJson(`/api/master-data/areas?search=${encodeURIComponent(code)}&limit=20`)
  if (!response.ok) throw new Error(`区域查询失败：${code} HTTP ${response.status}`)
  return (response.data?.items ?? []).find((item) => item.code === code) ?? null
}

async function getDeviceByCode(code) {
  const response = await fetchJson(`/api/master-data/devices?search=${encodeURIComponent(code)}&limit=20`)
  if (!response.ok) throw new Error(`设备查询失败：${code} HTTP ${response.status}`)
  return (response.data?.items ?? []).find((item) => item.code === code) ?? null
}

async function getPointByCode(code) {
  if (!createdDeviceId) return null
  const response = await fetchJson(`/api/master-data/device-points?device_id=${createdDeviceId}&search=${encodeURIComponent(code)}&limit=20`)
  if (!response.ok) throw new Error(`测点查询失败：${code} HTTP ${response.status}`)
  return (response.data?.items ?? []).find((item) => item.point_code === code) ?? null
}

async function getDevicePointByCode(code) {
  if (!createdDeviceId) return null
  const response = await fetchJson(`/api/master-data/devices/${createdDeviceId}`)
  if (!response.ok) throw new Error(`设备详情查询失败：HTTP ${response.status}`)
  return (response.data?.points ?? response.data?.data?.points ?? []).find((item) => item.point_code === code) ?? null
}

async function getManualMqttBindings() {
  const response = await fetchJson("/api/iot-ingestion/mqtt-device-bindings?limit=200")
  if (!response.ok) throw new Error(`MQTT绑定查询失败：HTTP ${response.status}`)
  return pageItems(response.data).filter((item) => {
    if (createdDeviceId && item.equipment_id === createdDeviceId) return true
    if (item.gateway_key === gatewayKey && item.meter_key === meterKey) return true
    return item.external_device_id === externalDeviceId
  })
}

async function getMqttBindingByDevice(deviceId) {
  const response = await fetchJson("/api/iot-ingestion/mqtt-device-bindings?limit=200")
  if (!response.ok) throw new Error(`MQTT绑定查询失败：HTTP ${response.status}`)
  return pageItems(response.data).find((item) => item.equipment_id === deviceId && item.gateway_key === gatewayKey && item.meter_key === meterKey) ?? null
}

async function getMqttMappingByBinding(bindingId, tag) {
  if (!bindingId) return null
  const response = await fetchJson(`/api/iot-ingestion/mqtt-point-mappings?binding_id=${bindingId}&limit=200`)
  if (!response.ok) throw new Error(`MQTT映射查询失败：HTTP ${response.status}`)
  return pageItems(response.data).find((item) => item.source_tag === tag && item.point_code === meterPointCode) ?? null
}

function pageItems(data) {
  if (Array.isArray(data?.items)) return data.items
  if (Array.isArray(data?.data?.items)) return data.data.items
  if (Array.isArray(data?.data)) return data.data
  return []
}

async function searchDevice(code) {
  await page.getByPlaceholder("搜索设备名称、编码、资产编码").fill(code)
  await waitForPageReady()
  await expectVisible(code)
}

async function selectDeviceRow(code) {
  await page.locator("tbody tr").filter({ hasText: code }).first().click()
  await waitForPageReady()
}

async function selectAreaInTree(name) {
  await page.getByRole("button").filter({ hasText: name }).first().click()
  await waitForPageReady()
}

function pointRow(code) {
  return page.locator("tbody tr").filter({ hasText: code }).first()
}

function mqttMappingRow(tag, code) {
  return page.getByText(`${tag} -> ${code}`, { exact: true }).locator("xpath=ancestor::div[contains(@class, 'rounded-md')][1]")
}

async function deleteRemainingDevicePoints() {
  if (!createdDeviceId) return
  for (let index = 0; index < 20; index += 1) {
    const detail = await fetchJson(`/api/master-data/devices/${createdDeviceId}`)
    const points = detail.data?.points ?? detail.data?.data?.points ?? []
    if (points.length === 0) return
    const firstPoint = points[0]
    const row = pointRow(firstPoint.point_code)
    if ((await row.count()) > 0) {
      await row.getByRole("button", { name: "删除" }).click()
      await expectVisible("测点已删除")
      await waitForPageReady()
    } else {
      await fetchJson(`/api/master-data/device-points/${firstPoint.id}`, { method: "DELETE" })
      await waitForPageReady()
    }
  }
  throw new Error("默认测点清理超过预期次数")
}

async function fillInput(scope, label, value) {
  const labelLocator = scope.locator("label", { hasText: label }).first()
  const control = labelLocator.locator("xpath=ancestor::div[contains(@class, 'grid')][1]//*[self::input or self::textarea]").first()
  await control.fill(value)
}

async function selectOption(scope, label, option) {
  const labelLocator = scope.locator("label", { hasText: label }).first()
  await labelLocator.locator("xpath=ancestor::div[contains(@class, 'grid')][1]//button[@role='combobox']").first().click()
  await page.getByRole("option", { name: option, exact: true }).click()
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
      const text = await response.text()
      let data = null
      try {
        data = text ? JSON.parse(text) : null
      } catch {
        data = text
      }
      return { ok: response.ok && !(data?.code && data.code >= 400), status: response.status, data }
    },
    { url, options, activeTeamId },
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
        tenantId: activeTeamId,
        startedAt,
        checks,
        artifacts,
        apiFailures,
        consoleErrors,
        notFoundResponses,
        error: error
          ? {
              name: error.name,
              message: error.message,
              stack: error.stack,
            }
          : null,
      },
      null,
      2,
    ),
  )
}
