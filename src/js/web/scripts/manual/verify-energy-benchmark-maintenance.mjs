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
const verificationPath = path.join(verificationDir, "energy-benchmark-maintenance.json")
const viewport = { width: 1440, height: 900 }
const stamp = process.env.MANUAL_VERIFY_STAMP ?? new Date().toISOString().replace(/\D/g, "").slice(0, 14)
const profileName = `手册验证能效对标方案-${stamp}`
const profileNameEdited = `${profileName}-已编辑`

const screenshots = {
  profileList: "EV-WH-120-能效对标配置方案列表.png",
  profileCreate: "EV-WH-121-能效对标配置新增方案.png",
  profileDetail: "EV-WH-122-能效对标配置方案详情.png",
  itemCreate: "EV-WH-123-能效对标配置新增标杆项.png",
  itemEdited: "EV-WH-124-能效对标配置标杆项编辑回显.png",
  baselineGenerate: "EV-WH-125-能效对标配置历史基线生成.png",
  analysisEntry: "EV-WH-126-能效对标分析维护入口.png",
  profileEdit: "EV-WH-167-能效对标配置编辑方案.png",
  itemDetail: "EV-WH-168-能效对标配置标杆项详情.png",
  itemDeleted: "EV-WH-169-能效对标配置标杆项删除结果.png",
  profileDeleted: "EV-WH-170-能效对标配置方案删除结果.png",
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
let createdProfileId = null
let createdItemId = null

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
  console.log("[ManualVerify] Preflight 100% | Auth 0% | Harness 0% | Navigate 0/2 | Interact 0/11 | Evidence 0/11 | Writeback 0/1")
  await ensureAuthenticated()
  await selectTenant()
  await cleanupCreatedRecords()
  apiFailures.length = 0
  consoleErrors.length = 0
  console.log("[ManualVerify] Preflight 100% | Auth 100% | Harness 100% | Navigate 0/2 | Interact 0/11 | Evidence 0/11 | Writeback 0/1")

  await verifyBenchmarkSettingsCrud()
  await verifyAnalysisEntry()
  await cleanupCreatedRecords()
  checks.push({ name: "cleanup", status: "passed", profileName })
  await writeVerification("passed")
  console.log("[ManualVerify] Preflight 100% | Auth 100% | Harness 100% | Navigate 2/2 | Interact 11/11 | Evidence 11/11 | Writeback 1/1")
} catch (error) {
  await writeVerification("failed", error)
  console.error(error)
  process.exitCode = 1
} finally {
  await browser.close()
}

async function verifyBenchmarkSettingsCrud() {
  await gotoPage("/data/energy-benchmark", ["能效标准与标杆库", "政策资料", "标准方案", "标杆指标", "模板导入", "历史基准"])
  await capture("profileList", "政策资料页展示资料来源、标准编号、来源网页、附件和已同步政策库。")
  checks.push({ name: "policy-and-profile-list", status: "passed" })

  await page.getByRole("button", { name: "同步政策库" }).click()
  await expectVisible("政策资料已同步")
  await waitForPageReady()
  checks.push({ name: "policy-sync", status: "passed" })

  await page.getByRole("tab", { name: "标准方案" }).click()
  await waitForPageReady()
  await page.getByRole("button", { name: "新增方案" }).last().click()
  await expectVisible("新增标准方案")
  await fillField("方案名称", profileName)
  await chooseSelect("库类型", "企业内部标准库")
  await fillField("行业", "汽车零部件制造")
  await fillField("适用范围", "生产基地仓储与公辅设备")
  await fillField("来源名称", "企业能源管理制度")
  await fillField("标准编号", "WOHENG-VERIFY-ENPI")
  await fillField("备注", "能效对标维护 CRUD 验证")
  await capture("profileCreate", "新增标准方案表单维护库类型、行业、适用范围、来源、标准编号和备注。")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible(profileName)
  const profile = await findProfile(profileName)
  createdProfileId = profile.id
  checks.push({ name: "profile-create", status: "passed", profileId: createdProfileId })

  await clickRowAction(profileName, "详情")
  await expectVisible("标准方案详情")
  await expectVisible("汽车零部件制造")
  await capture("profileDetail", "标准方案详情抽屉回显已保存字段。")
  await page.keyboard.press("Escape")
  checks.push({ name: "profile-detail", status: "passed", profileId: createdProfileId })

  await clickRowAction(profileName, "编辑")
  await expectVisible("编辑标准方案")
  await fillField("方案名称", profileNameEdited)
  await fillField("备注", "能效对标方案编辑验证")
  await capture("profileEdit", "编辑标准方案表单回显并修改方案名称和备注。")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible(profileNameEdited)
  checks.push({ name: "profile-edit", status: "passed", profileId: createdProfileId })

  await page.getByRole("tab", { name: "标杆指标" }).click()
  await waitForPageReady()
  await chooseSelect("选择标杆方案", profileNameEdited)
  await page.getByRole("button", { name: "新增指标" }).click()
  await expectVisible("新增标杆指标")
  await chooseSelect("对象层级", "设备类型")
  await fillField("对象编码", "air_compressor")
  await fillField("对象名称", "空气压缩机")
  await chooseSelect("指标", "设备能效等级")
  await fillField("标杆值", "2")
  await fillField("先进水平", "1")
  await fillField("节能水平", "2")
  await fillField("准入/基准水平", "3")
  await fillField("标准编号", "GB 19153-2019")
  await fillField("适用行业", "重点用能产品设备")
  await fillField("适用分类", "容积式空气压缩机")
  await fillField("适用条件", "同功率及冷却方式")
  await fillField("参考标准", "GB 19153-2019")
  await fillField("预警阈值 %", "10")
  await fillField("严重阈值 %", "20")
  await fillField("来源名称", "企业设备检测记录")
  await fillField("备注", "标杆指标维护 CRUD 验证")
  await capture("itemCreate", "新增标杆指标表单维护对象层级、对象编码、等级值、适用条件和标准来源。")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible("空气压缩机")
  const item = await findItem(createdProfileId, "空气压缩机")
  createdItemId = item.id
  checks.push({ name: "item-create", status: "passed", itemId: createdItemId })

  await clickRowAction("空气压缩机", "详情")
  await expectVisible("标杆指标详情")
  await expectVisible("设备能效等级")
  await capture("itemDetail", "标杆指标详情抽屉回显对象、指标、等级值、适用条件和来源。")
  await page.keyboard.press("Escape")
  checks.push({ name: "item-detail", status: "passed", itemId: createdItemId })

  await clickRowAction("空气压缩机", "编辑")
  await expectVisible("编辑标杆指标")
  await fillField("节能水平", "2")
  await fillField("备注", "标杆指标编辑验证")
  await page.getByRole("button", { name: "保存" }).click()
  await waitForNoDialog()
  await expectVisible("GB 19153-2019")
  await capture("itemEdited", "编辑标杆指标后列表回显更新后的来源和等级值。")
  checks.push({ name: "item-edit", status: "passed", itemId: createdItemId })

  await page.getByRole("tab", { name: "模板导入" }).click()
  await waitForPageReady()
  await chooseSelect("选择导入目标方案", profileNameEdited)
  await page.getByRole("button", { name: "预检" }).click()
  await expectVisible("可导入")
  checks.push({ name: "import-preview", status: "passed", profileId: createdProfileId })

  await page.getByRole("tab", { name: "历史基准" }).click()
  await waitForPageReady()
  await expectVisible("内部基准生成")
  await fillField("方案名称", `${profileName}-历史基准`)
  await page.getByRole("button", { name: "生成基准" }).click()
  await expectVisible("已生成")
  await capture("baselineGenerate", "历史基准生成结果态提示内部基准已按历史能源和分母数据生成。")
  checks.push({ name: "baseline-generate", status: "passed" })

  await page.getByRole("tab", { name: "标杆指标" }).click()
  await waitForPageReady()
  await chooseSelect("选择标杆方案", profileNameEdited)
  await clickIconOnlyDeleteInRow("空气压缩机")
  await waitForPageReady()
  await expectVisible("标杆指标已删除")
  await capture("itemDeleted", "删除标杆指标后，当前方案不再显示该指标。")
  checks.push({ name: "item-delete", status: "passed", itemId: createdItemId })
  createdItemId = null

  await page.getByRole("tab", { name: "标准方案" }).click()
  await waitForPageReady()
  await clickIconOnlyDeleteInRow(profileNameEdited)
  await waitForPageReady()
  await expectVisible("标准方案已删除")
  await page.locator("tr", { hasText: profileNameEdited }).waitFor({ state: "detached", timeout: 20_000 })
  await capture("profileDeleted", "删除标准方案后，标准方案列表不再显示该方案。")
  checks.push({ name: "profile-delete", status: "passed", profileId: createdProfileId })
  createdProfileId = null
}

async function verifyAnalysisEntry() {
  await gotoPage("/energy/benchmark", ["对标覆盖率", "偏差排行", "达标等级分布", "对标结果", "标准库"])
  await page.getByRole("button", { name: "显示全部" }).click()
  await chooseSelectByIndex(0, "设备能效等级库")
  await chooseSelectByIndex(2, "设备类型")
  await chooseSelectByIndex(3, "设备能效等级")
  await waitForPageReady()
  await expectVisible("电力变压器")
  await expectVisible("设备能效等级")
  await capture("analysisEntry", "能效对标分析页展示设备能效等级库筛选、图表、结果表和标准库入口。")
  await page.getByRole("link", { name: "标准库" }).first().click()
  await page.waitForURL("**/data/energy-benchmark")
  await waitForPageReady()
  checks.push({ name: "analysis-entry", status: "passed" })
}

async function ensureAuthenticated() {
  await page.goto(`${baseURL}/login`, { waitUntil: "domcontentloaded" })
  let profile = await fetchJson("/api/me").catch(() => null)
  apiFailures.length = 0
  consoleErrors.length = 0
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
  const teams = extractItems(response.data)
  const team = teams.find((item) => item.slug === tenantSlug)
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

async function cleanupCreatedRecords() {
  const response = await fetchJson(`/api/energy/benchmark/profiles?keyword=${encodeURIComponent("手册验证能效对标方案-")}&limit=200`)
  if (!response.ok) return
  for (const profile of extractItems(response.data)) {
    const items = await fetchJson(`/api/energy/benchmark/items?profile_id=${profile.id}&limit=200`)
    for (const item of extractItems(items.data)) {
      await fetchJson(`/api/energy/benchmark/items/${item.id}`, { method: "DELETE" }).catch(() => null)
    }
    await fetchJson(`/api/energy/benchmark/profiles/${profile.id}`, { method: "DELETE" }).catch(() => null)
  }
  createdProfileId = null
  createdItemId = null
}

async function findProfile(name) {
  const response = await fetchJson(`/api/energy/benchmark/profiles?keyword=${encodeURIComponent(name)}&limit=20`)
  if (!response.ok) throw new Error(`标杆方案查询失败：HTTP ${response.status}`)
  const profile = extractItems(response.data).find((item) => item.name === name)
  if (!profile?.id) throw new Error(`未找到标杆方案：${name}`)
  return profile
}

async function findItem(profileId, targetName) {
  const response = await fetchJson(`/api/energy/benchmark/items?profile_id=${profileId}&limit=200`)
  if (!response.ok) throw new Error(`标杆项查询失败：HTTP ${response.status}`)
  const item = extractItems(response.data).find((entry) => entry.target_name === targetName)
  if (!item?.id) throw new Error(`未找到标杆项：${targetName}`)
  return item
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

async function fillField(label, value) {
  const field = page
    .locator(".grid.gap-2, .grid.gap-1\\.5")
    .filter({ has: page.getByText(label, { exact: true }) })
    .locator("input, textarea")
    .first()
  await field.fill(value)
}

async function chooseSelect(labelOrPlaceholder, optionText) {
  const wrapper = page
    .locator(".grid.gap-2, .grid.gap-1\\.5")
    .filter({ has: page.getByText(labelOrPlaceholder, { exact: true }) })
    .locator('[role="combobox"]')
    .first()
  const fallback = page.getByRole("combobox", { name: labelOrPlaceholder }).first()
  const field = (await wrapper.count()) > 0 ? wrapper : (await fallback.count()) > 0 ? fallback : page.locator('[role="combobox"]:visible').first()
  await field.click()
  await page.getByRole("option").filter({ hasText: optionText }).first().click()
}

async function chooseSelectByIndex(index, optionText) {
  await page.locator('button[role="combobox"]:visible').nth(index).click()
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

function extractItems(payload) {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.items)) return payload.items
  if (Array.isArray(payload?.data?.items)) return payload.data.items
  return []
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
        cleanup: {
          profileId: createdProfileId,
          itemId: createdItemId,
        },
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
