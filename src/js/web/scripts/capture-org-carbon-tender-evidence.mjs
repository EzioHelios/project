import { chromium } from "@playwright/test"
import { execFileSync } from "node:child_process"
import { createHash } from "node:crypto"
import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:18101"
const username = process.env.E2E_ADMIN_EMAIL
const password = process.env.E2E_ADMIN_PASSWORD
const tenantSlug = process.env.E2E_TENANT_SLUG ?? "demo-industrial-park"
const tenantNameHint = process.env.E2E_TENANT_NAME ?? "华东综合能源示范园区"
const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../..")
const outputDir = path.resolve(
  process.env.EVIDENCE_OUTPUT_DIR ?? path.join(repositoryRoot, "outputs/chery-bid-feature-decomposition-20260823/screenshots"),
)
const manifestPath = path.join(outputDir, "evidence-manifest.json")
const indexPath = path.join(outputDir, "organization-carbon-evidence-index.json")

const viewport = { width: 1440, height: 900 }
const badStatusPattern = /^(401|403|5\d\d)$/
const emptyMarkers = ["当前筛选条件下没有活动记录", "当前分类暂无活动记录", "等待工作簿预检"]
const errorMarkers = ["加载失败", "数据加载失败", "活动台账加载失败", "权限不足", "Internal Server Error"]
const loadingMarkers = ["正在加载", "正在预检", "loading"]
const evidenceOnly = new Set(
  (process.env.EVIDENCE_ONLY ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean),
)

const baseEvidenceMappings = {
  "EVD-OC-01": ["CHERY-CARBON-048-01", "CHERY-CARBON-048-02", "CHERY-CARBON-048-05", "CHERY-CARBON-049-02"],
  "EVD-OC-02": ["CHERY-CARBON-049-01"],
  "EVD-OC-03": ["CHERY-CARBON-050-01"],
  "EVD-OC-04": ["CHERY-CARBON-051-01", "CHERY-CARBON-051-03"],
  "EVD-OC-05": ["CHERY-CARBON-052-01", "CHERY-CARBON-053-01"],
}

const evidenceDefinitions = [
  {
    evidenceId: "EV-ORG-BASE-001",
    featureIds: ["CHERY-CARBON-052-01", "CHERY-CARBON-054-02"],
    title: "温室气体活动数据台账",
    route: "/carbon-mgmt/activities",
    filename: "EV-ORG-BASE-001-ghg-activity-ledger.png",
    requiredTexts: ["温室气体活动台账", "活动记录", "记录 / 活动", "DEMO-PARK"],
    expectedEvidenceLevel: "E3",
  },
  {
    evidenceId: "EV-ORG-BASE-002",
    featureIds: ["CHERY-CARBON-052-01", "CHERY-CARBON-054-02"],
    title: "活动数据导入提交结果态",
    route: "/carbon-mgmt/import",
    filename: "EV-ORG-BASE-002-ghg-import-commit-result.png",
    requiredTexts: ["活动数据导入", "已完成导入", "活动记录", "有效记录", "执行核算"],
    preActionTexts: ["活动数据导入", "上传与预检", "执行预检"],
    expectedEvidenceLevel: "E4",
    action: async ({ page }) => {
      const fixturePath = await createImportFixture()
      await page.locator('input[type="file"]').setInputFiles(fixturePath)
      await page.getByRole("button", { name: "执行预检" }).click()
      await page.getByText("活动数据预览", { exact: true }).waitFor({ timeout: 30_000 })
      await page.getByRole("button", { name: "确认导入" }).click()
      await page.getByRole("button", { name: "已完成导入" }).waitFor({ timeout: 30_000 })
      await page.getByRole("button", { name: "执行核算" }).waitFor({ timeout: 15_000 })
    },
  },
  {
    evidenceId: "EV-ORG-BASE-003",
    featureIds: ["CHERY-CARBON-052-01"],
    title: "排放因子库原始因子追溯",
    route: "/carbon-mgmt/factors",
    filename: "EV-ORG-BASE-003-factor-library-trace.png",
    requiredTexts: ["排放因子库", "官方原始因子", "因子追溯", "原始字段"],
    preActionTexts: ["排放因子库", "官方原始因子", "查看"],
    expectedEvidenceLevel: "E3",
    action: async ({ page }) => {
      await page.locator("tbody tr").first().getByRole("button", { name: "查看" }).click()
      await page.getByText("因子追溯", { exact: true }).waitFor({ timeout: 15_000 })
    },
  },
  {
    evidenceId: "EV-ORG-BASE-004",
    featureIds: ["CHERY-CARBON-052-01"],
    title: "计算因子库与范围因子选择",
    route: "/carbon-mgmt/calculation-factors",
    filename: "EV-ORG-BASE-004-calculation-factor-library.png",
    requiredTexts: ["计算因子库", "因子列表", "范围1", "启用"],
    expectedEvidenceLevel: "E3",
  },
  {
    evidenceId: "EV-ORG-BASE-005",
    featureIds: ["CHERY-CARBON-052-01", "CHERY-CARBON-054-02"],
    title: "排放源分类明细与核算方法",
    route: "/carbon-mgmt/category/1.1",
    filename: "EV-ORG-BASE-005-source-category-ledger.png",
    requiredTexts: ["1.1", "活动记录", "核算方法", "DEMO-PARK"],
    expectedEvidenceLevel: "E3",
  },
  {
    evidenceId: "EVD-OC-03E",
    featureIds: ["CHERY-CARBON-050-01"],
    title: "碳流总览与加权流向关系",
    route: "/carbon/organization/flow",
    filename: "EVD-OC-03E-carbon-flow-overview.png",
    requiredTexts: ["组织边界至区域设备碳流", "主要排放路径", "10,197.18"],
    expectedEvidenceLevel: "E3",
  },
  {
    evidenceId: "EVD-OC-03F",
    featureIds: ["CHERY-CARBON-050-04"],
    title: "碳流核算异常独立状态",
    route: "/carbon/organization/flow",
    filename: "EVD-OC-03F-carbon-flow-anomalies.png",
    requiredTexts: ["核算异常", "证据链缺失", "区域设备未归集"],
    expectedEvidenceLevel: "E3",
    locator: ({ page }) => page.locator("section").filter({ hasText: "核算异常" }).last(),
  },
  {
    evidenceId: "EVD-OC-04B",
    featureIds: ["CHERY-CARBON-051-02", "CHERY-CARBON-051-03"],
    title: "运营控制法与边界版本口径",
    route: "/carbon/organization/boundary",
    filename: "EVD-OC-04B-boundary-method-version.png",
    requiredTexts: ["边界口径", "运营控制法", "ISO 类别"],
    expectedEvidenceLevel: "E3",
  },
  {
    evidenceId: "EVD-OC-04C",
    featureIds: ["CHERY-CARBON-051-04"],
    title: "边界版本差异对比",
    route: "/carbon/organization/boundary",
    filename: "EVD-OC-04C-boundary-version-diff.png",
    requiredTexts: ["边界版本对比", "对比版本", "当前版本"],
    preActionTexts: ["边界口径", "运营控制法", "版本对比"],
    expectedEvidenceLevel: "E3",
    action: async ({ page }) => {
      await page.getByRole("button", { name: "创建工作草稿" }).click()
      await page.getByRole("button", { name: "放弃草稿" }).waitFor({ timeout: 15_000 })
      await page.locator('input[type="checkbox"]:not([disabled])').first().click()
      await page.getByRole("button", { name: "保存" }).click()
      await page.getByRole("button", { name: "版本对比" }).click()
      await page.getByText("边界版本对比", { exact: true }).waitFor({ timeout: 15_000 })
      await page.locator("[data-sonner-toast]").evaluateAll((nodes) => nodes.forEach((node) => node.remove())).catch(() => {})
    },
    cleanup: async ({ page }) => {
      await page.keyboard.press("Escape").catch(() => {})
      const discard = page.getByRole("button", { name: "放弃草稿" })
      if ((await discard.count()) > 0) await discard.click().catch(() => {})
    },
  },
  {
    evidenceId: "EVD-OC-05B",
    featureIds: ["CHERY-CARBON-052-01", "CHERY-CARBON-053-01"],
    title: "盘查报告版本与状态台账",
    route: "/carbon/organization/inventory",
    filename: "EVD-OC-05B-inventory-report-ledger.png",
    requiredTexts: ["盘查报告台账", "报告版本", "状态", "2025年度组织温室气体盘查报告"],
    expectedEvidenceLevel: "E3",
  },
  {
    evidenceId: "EVD-OC-05C",
    featureIds: ["CHERY-CARBON-052-02", "CHERY-CARBON-053-02", "CHERY-CARBON-053-04"],
    title: "报告冻结快照、证据覆盖与审批轨迹",
    route: "/carbon/organization/inventory",
    filename: "EVD-OC-05C-inventory-report-audit.png",
    requiredTexts: ["审批轨迹", "证据覆盖率", "报告版本", "发布"],
    preActionTexts: ["盘查报告台账", "2025年度组织温室气体盘查报告", "查看"],
    expectedEvidenceLevel: "E3",
    action: async ({ page }) => {
      const reportRow = page.locator("tr").filter({ hasText: "2025年度组织温室气体盘查报告" }).filter({ hasText: "v2" }).first()
      await reportRow.scrollIntoViewIfNeeded()
      await reportRow.getByRole("button", { name: "查看" }).first().click()
      await page.getByText("审批轨迹", { exact: true }).waitFor({ timeout: 15_000 })
      await page.getByText("发布", { exact: true }).last().waitFor({ timeout: 15_000 })
    },
    cleanup: async ({ page }) => {
      await page.keyboard.press("Escape").catch(() => {})
    },
  },
  {
    evidenceId: "EVD-OC-06",
    featureIds: ["CHERY-CARBON-053-01"],
    title: "核查项目工作台与项目状态",
    route: "/carbon/verification",
    filename: "EVD-OC-06-verification-project-workbench.png",
    requiredTexts: ["核查项目", "DEMO-PARK-VER-2025-01"],
    expectedEvidenceLevel: "E3",
    action: selectVerificationProject,
  },
  {
    evidenceId: "EVD-OC-06B",
    featureIds: ["CHERY-CARBON-054-01", "CHERY-CARBON-054-02"],
    title: "证据资料台账与文件关联",
    route: "/carbon/verification",
    filename: "EVD-OC-06B-verification-evidence.png",
    requiredTexts: ["证据资料", "凭证清单", "DEMO-PARK-EVD-2025-C61"],
    preActionTexts: ["碳核查支撑", "DEMO-PARK-VER-2025-01"],
    expectedEvidenceLevel: "E3",
    action: async (tools) => {
      await selectVerificationProject(tools)
      await tools.page.getByRole("tab", { name: "证据资料", exact: true }).click()
      await tools.page.getByText("DEMO-PARK-EVD-2025-C11", { exact: true }).first().waitFor({ timeout: 15_000 })
    },
  },
  {
    evidenceId: "EVD-OC-06C",
    featureIds: ["CHERY-CARBON-053-03"],
    title: "核查过程追溯",
    route: "/carbon/verification",
    filename: "EVD-OC-06C-verification-trace.png",
    requiredTexts: ["核查工作", "RPT-62-65"],
    preActionTexts: ["碳核查支撑", "DEMO-PARK-VER-2025-01"],
    expectedEvidenceLevel: "E3",
    action: async (tools) => {
      await selectVerificationProject(tools)
      await tools.page.getByRole("tab", { name: "核查工作", exact: true }).click()
      await tools.page.getByText("RPT-62-65", { exact: true }).waitFor({ timeout: 15_000 })
    },
  },
  {
    evidenceId: "EVD-OC-06D",
    featureIds: ["CHERY-CARBON-053-03"],
    title: "核查发现与整改闭环",
    route: "/carbon/verification",
    filename: "EVD-OC-06D-verification-findings.png",
    requiredTexts: ["质量问题", "DEMO-PARK-VF-2025-001"],
    preActionTexts: ["碳核查支撑", "DEMO-PARK-VER-2025-01"],
    expectedEvidenceLevel: "E3",
    action: async (tools) => {
      await selectVerificationProject(tools)
      await tools.page.getByRole("tab", { name: "核查工作", exact: true }).click()
      await tools.page.getByRole("tab", { name: "质量问题", exact: true }).click()
      await tools.page.getByText("DEMO-PARK-VF-2025-001", { exact: true }).waitFor({ timeout: 15_000 })
    },
  },
  {
    evidenceId: "EVD-OC-06E",
    featureIds: ["CHERY-CARBON-053-02", "CHERY-CARBON-053-04"],
    title: "审核日志与责任人轨迹",
    route: "/carbon/verification",
    filename: "EVD-OC-06E-verification-audit.png",
    requiredTexts: ["审核日志", "组织碳复核专员"],
    preActionTexts: ["碳核查支撑", "DEMO-PARK-VER-2025-01"],
    expectedEvidenceLevel: "E3",
    action: async (tools) => {
      await selectVerificationProject(tools)
      await tools.page.getByRole("tab", { name: "核查工作", exact: true }).click()
      await tools.page.getByRole("tab", { name: "审核日志", exact: true }).click()
      await tools.page.getByText("组织碳复核专员", { exact: true }).first().waitFor({ timeout: 15_000 })
    },
  },
  {
    evidenceId: "EVD-OC-06F",
    featureIds: ["CHERY-CARBON-054-03"],
    title: "核查材料包组成与导出准备",
    route: "/carbon/verification",
    filename: "EVD-OC-06F-verification-material-package.png",
    requiredTexts: ["报告与材料", "报告主体基本信息"],
    preActionTexts: ["碳核查支撑", "DEMO-PARK-VER-2025-01"],
    expectedEvidenceLevel: "E3",
    action: async (tools) => {
      await selectVerificationProject(tools)
      await tools.page.getByRole("tab", { name: "报告与材料", exact: true }).click()
      await tools.page.getByText("报告主体基本信息", { exact: true }).waitFor({ timeout: 15_000 })
    },
  },
  {
    evidenceId: "EVD-OC-06G",
    featureIds: ["CHERY-CARBON-052-02"],
    title: "组织盘查报告导出内容预览",
    route: "/carbon/verification",
    filename: "EVD-OC-06G-verification-report-export.png",
    requiredTexts: ["报告导出", "报告数据", "排放量(tCO2e)"],
    preActionTexts: ["碳核查支撑", "DEMO-PARK-VER-2025-01"],
    expectedEvidenceLevel: "E3",
    action: async (tools) => {
      await selectVerificationProject(tools)
      await tools.page.getByRole("tab", { name: "报告与材料", exact: true }).click()
      await tools.page.getByRole("tab", { name: "报告导出", exact: true }).click()
      await tools.page.getByText("报告数据", { exact: true }).waitFor({ timeout: 15_000 })
    },
  },
  {
    evidenceId: "EVD-OC-06H",
    featureIds: ["CHERY-CARBON-052-02", "CHERY-CARBON-054-03"],
    title: "组织报告与核查材料包异步导出完成",
    route: "/carbon/verification",
    filename: "EVD-OC-06H-verification-export-completed.png",
    requiredTexts: ["导出记录", "已完成", "下载"],
    preActionTexts: ["碳核查支撑", "DEMO-PARK-VER-2025-01"],
    expectedEvidenceLevel: "E4",
    action: async (tools) => {
      const { page } = tools
      await selectVerificationProject(tools)
      await page.getByRole("tab", { name: "报告与材料", exact: true }).click()
      await page.getByRole("tab", { name: "报告导出", exact: true }).click()
      await page.getByText("报告数据", { exact: true }).waitFor({ timeout: 15_000 })
      const project = await findDemoVerificationProject()
      const createdJob = await createVerificationExportJob({
        projectId: project.id,
        exportType: "organization_report",
        year: project.verification_year,
      })
      const createdJobId = Number(createdJob.id)
      const exportPanel = page.locator("section").filter({ hasText: "导出记录" }).last()
      await waitForCompletedVerificationExport(createdJobId)
      await page.reload({ waitUntil: "domcontentloaded" })
      await waitForPageReady()
      await selectVerificationProject(tools)
      await page.getByRole("tab", { name: "报告与材料", exact: true }).click()
      await page.getByRole("tab", { name: "报告导出", exact: true }).click()
      await page.getByText(String(createdJob.job_no ?? createdJob.jobNo ?? ""), { exact: false }).waitFor({ timeout: 30_000 })
      await exportPanel.getByRole("button", { name: "下载" }).first().waitFor({ timeout: 90_000 })
      tools.extra.locator = exportPanel
      tools.extra.download = await downloadLatestVerificationExport("EVD-OC-06H-export-download", {
        jobId: createdJobId,
      })
    },
  },
]

const deferredEvidence = []

if (!username || !password) {
  throw new Error("E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD are required")
}

await fs.mkdir(outputDir, { recursive: true })

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport, deviceScaleFactor: 1, acceptDownloads: true })
const page = await context.newPage()
page.setDefaultTimeout(15_000)
page.setDefaultNavigationTimeout(30_000)
let activeTeamId = null
let activeTeam = null
let activeUser = null
const consoleErrors = []
const apiFailures = []

await context.route("**/api/**", async (route) => {
  const headers = { ...route.request().headers() }
  if (activeTeamId) headers["x-team-id"] = activeTeamId
  await route.continue({ headers })
})

page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text())
})
page.on("response", (response) => {
  const url = response.url()
  if (!url.includes("/api/")) return
  const status = response.status()
  if (badStatusPattern.test(String(status))) {
    apiFailures.push({
      status,
      url: url.replace(baseURL, ""),
      method: response.request().method(),
      at: new Date().toISOString(),
    })
  }
})

try {
  activeUser = await ensureAuthenticated()
  activeTeam = await selectDemoTenant()
  consoleErrors.length = 0
  apiFailures.length = 0
  await page.addStyleTag({ content: "[data-sonner-toast] { display: none !important; }" }).catch(() => {})

  const manifest = await readManifest()
  const capturedRecords = []
  const rejectedRecords = []

  for (const definition of evidenceDefinitions) {
    if (evidenceOnly.size > 0 && !evidenceOnly.has(definition.evidenceId)) continue
    console.log(`[evidence:start] ${definition.evidenceId} ${definition.route}`)
    const result = await captureEvidence(definition)
    console.log(`[evidence:${result.status}] ${definition.evidenceId}${result.failureReason ? ` ${result.failureReason}` : ""}`)
    if (result.status === "有效" || result.status === "部分有效") capturedRecords.push(result)
    else rejectedRecords.push(result)
  }

  await fs.writeFile(path.join(outputDir, "browser-console-errors.json"), `${JSON.stringify(consoleErrors, null, 2)}\n`)
  await fs.writeFile(path.join(outputDir, "api-failures.json"), `${JSON.stringify(apiFailures, null, 2)}\n`)
  await updateManifest(manifest, capturedRecords, rejectedRecords)
  await writeEvidenceIndex(manifest)
} finally {
  await browser.close()
}

async function ensureAuthenticated() {
  await page.goto(`${baseURL}/login`, { waitUntil: "domcontentloaded" })
  let profile = await fetchJson("/api/me").catch(() => null)
  if (!profile?.ok) {
    await page.locator('input[name="username"]').fill(username)
    await page.locator('input[name="password"]').fill(password)
    await page.getByRole("button", { name: /登录|Login/i }).click()
    await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 })
    profile = await fetchJson("/api/me")
  }
  if (!profile.ok || !profile.data?.id) {
    throw new Error(`登录态验证失败：/api/me 返回 ${profile.status}`)
  }
  return profile.data
}

async function selectDemoTenant() {
  const teamsResponse = await fetchJson("/api/teams?limit=200")
  const teams = Array.isArray(teamsResponse.data?.items) ? teamsResponse.data.items : teamsResponse.data
  const team = teams?.find((item) => item.slug === tenantSlug || item.name === tenantNameHint)
  if (!team?.id) {
    throw new Error(`未找到演示租户：${tenantSlug}`)
  }
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
  const catalog = await fetchJson("/api/ghg-inventory/catalog")
  if (!catalog.ok) throw new Error(`演示租户接口验证失败：/api/ghg-inventory/catalog 返回 ${catalog.status}`)
  return team
}

async function fetchJson(url, options = {}) {
  return page.evaluate(
    async ({ url, options, activeTeamId }) => {
      const headers = new Headers(options.headers ?? {})
      if (activeTeamId) headers.set("X-Team-Id", activeTeamId)
      const response = await fetch(url, { ...options, headers, credentials: "include" })
      const data = await response.json().catch(() => null)
      return { ok: response.ok, status: response.status, data }
    },
    { url, options, activeTeamId },
  )
}

async function captureEvidence(definition) {
  const startedAt = new Date().toISOString()
  const failureOffset = apiFailures.length
  const tools = { page, context, extra: {} }
  try {
    await page.goto(`${baseURL}${definition.route}`, { waitUntil: "domcontentloaded" })
    await waitForPageReady()
    for (const text of definition.preActionTexts ?? definition.requiredTexts) {
      await page.getByText(text, { exact: false }).first().waitFor({ timeout: 20_000 })
    }
    if (definition.action) {
      await definition.action(tools)
      await waitForPageReady()
      for (const text of definition.requiredTexts) {
        await page.getByText(text, { exact: false }).first().waitFor({ timeout: 20_000 })
      }
    }
    await assertBusinessEvidence(definition, failureOffset)
    const locator = tools.extra.locator ?? definition.locator?.(tools)
    const screenshotPath = path.join(outputDir, definition.filename)
    if (locator) {
      await locator.scrollIntoViewIfNeeded()
      await page.evaluate(() => {
        window.scrollTo({ top: Math.max(0, window.scrollY - 80), left: 0, behavior: "instant" })
        document.documentElement.scrollLeft = 0
        document.body.scrollLeft = 0
      })
    } else {
      await page.evaluate(() => {
        window.scrollTo({ top: 0, left: 0, behavior: "instant" })
        document.documentElement.scrollLeft = 0
        document.body.scrollLeft = 0
      })
    }
    await page.screenshot({ path: screenshotPath, fullPage: false })
    const bytes = await fs.readFile(screenshotPath)
    const status = tools.extra.download?.status === "部分有效" ? "部分有效" : "有效"
    return {
      evidenceId: definition.evidenceId,
      functionIds: definition.featureIds,
      featureIds: definition.featureIds,
      title: definition.title,
      route: definition.route,
      actualUrl: `${baseURL}${definition.route}`,
      screenshotPath,
      status,
      expectedEvidenceLevel: definition.expectedEvidenceLevel,
      acceptanceConclusion:
        status === "部分有效"
          ? "页面通过登录态、演示租户、关键接口、非空数据、无错误状态校验；截图可证明导出任务台账和下载入口，但本轮未验证到可落盘 ZIP 文件，不能作为完整 E4 文件闭环证据。"
          : "页面通过登录态、演示租户、关键接口、非空数据、无错误状态校验，可作为标书截图证据。",
      failureReason: "",
      reshootSuggestion: "运行 qa:evidence:organization-carbon 并保持 E2E_TENANT_SLUG=demo-industrial-park。",
      mustVisibleContents: definition.requiredTexts,
      tenantSlug,
      tenantName: activeTeam?.name,
      tenantId: activeTeamId,
      viewport: `${viewport.width}x${viewport.height}`,
      capturedAt: startedAt,
      sha256: createHash("sha256").update(bytes).digest("hex"),
      apiFailures: apiFailures.slice(failureOffset),
      consoleErrorCount: consoleErrors.length,
      emptyMarkers: [],
      download: tools.extra.download,
    }
  } catch (error) {
    return {
      evidenceId: definition.evidenceId,
      functionIds: definition.featureIds,
      featureIds: definition.featureIds,
      title: definition.title,
      route: definition.route,
      actualUrl: `${baseURL}${definition.route}`,
      screenshotPath: "",
      status: "待取证",
      expectedEvidenceLevel: definition.expectedEvidenceLevel,
      acceptanceConclusion: "未形成有效业务截图。",
      failureReason: error instanceof Error ? error.message : String(error),
      reshootSuggestion: "先确认演示租户数据和关键接口返回非空，再重跑截图脚本。",
      mustVisibleContents: definition.requiredTexts,
      tenantSlug,
      tenantName: activeTeam?.name,
      tenantId: activeTeamId,
      capturedAt: startedAt,
      apiFailures: apiFailures.slice(failureOffset),
    }
  } finally {
    if (definition.cleanup) await definition.cleanup(tools).catch(() => {})
  }
}

async function waitForPageReady() {
  await page.waitForLoadState("domcontentloaded")
  await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => {})
  await page.evaluate(async () => {
    await document.fonts.ready
  })
}

async function assertBusinessEvidence(definition, failureOffset) {
  if (page.url().includes("/login")) throw new Error("截图目标仍停留在登录页")
  const recentFailures = apiFailures.slice(failureOffset)
  if (recentFailures.length > 0) {
    throw new Error(`关键接口出现 ${recentFailures.map((item) => item.status).join(",")}：${recentFailures[0].url}`)
  }
  for (const marker of [...loadingMarkers, ...errorMarkers]) {
    if (await hasVisibleText(marker)) throw new Error(`页面仍存在无效状态文案：${marker}`)
  }
  for (const marker of emptyMarkers) {
    if (await hasVisibleText(marker)) throw new Error(`页面目标数据为空或仅为入口态：${marker}`)
  }
  for (const text of definition.requiredTexts) {
    if (!(await hasVisibleText(text))) throw new Error(`缺少必须可见内容：${text}`)
  }
}

async function hasVisibleText(text) {
  const locator = page.getByText(text, { exact: false })
  const count = Math.min(await locator.count(), 20)
  for (let index = 0; index < count; index += 1) {
    if (await locator.nth(index).isVisible().catch(() => false)) return true
  }
  return false
}

async function selectVerificationProject({ page }) {
  const row = page.locator("tr").filter({ hasText: "DEMO-PARK-VER-2025-01" }).first()
  await row.waitFor({ state: "visible", timeout: 20_000 })
  await row.click()
  await page.getByText("DEMO-PARK-VER-2025-01", { exact: true }).waitFor({ timeout: 15_000 })
}

async function findDemoVerificationProject() {
  const response = await fetchJsonFromNode("/api/carbon/verification/projects?limit=100")
  if (!response.ok) throw new Error(`核查项目接口返回 ${response.status}`)
  const projects = response.data?.data?.items ?? response.data?.items ?? []
  const project = projects.find((item) => item.project_no === "DEMO-PARK-VER-2025-01") ?? projects[0]
  if (!project?.id) throw new Error("未找到可用于导出 Word 报告的核查项目")
  return project
}

async function createVerificationExportJob({ projectId, exportType, year }) {
  const response = await fetchJsonFromNode("/api/carbon/verification/export-jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      export_type: exportType,
      year,
    }),
  })
  if (!response.ok) throw new Error(`创建 Word 版盘查报告导出任务失败：${response.status}`)
  const job = response.data?.data ?? response.data
  if (!job?.id) throw new Error("创建 Word 版盘查报告导出任务未返回 job id")
  return job
}

async function waitForCompletedVerificationExport(jobId) {
  const deadline = Date.now() + 90_000
  while (Date.now() < deadline) {
    const response = await fetchJsonFromNode(`/api/carbon/verification/export-jobs/${jobId}`)
    const job = response.data?.data ?? response.data
    if (job?.download_url ?? job?.downloadUrl) return job
    if (job?.status === "failed") throw new Error(`Word 版盘查报告导出失败：${job.error_message ?? ""}`)
    await new Promise((resolve) => setTimeout(resolve, 1200))
  }
  throw new Error("本次 Word 版盘查报告导出任务未在限定时间内完成")
}

async function downloadLatestVerificationExport(basename, { jobId } = {}) {
  try {
    const jobsResponse = await fetchJsonFromNode("/api/carbon/verification/export-jobs?limit=100")
    const jobs = jobsResponse.data?.data?.items ?? jobsResponse.data?.items ?? []
    const completed = jobs.filter((item) => item.status === "completed" && (item.download_url ?? item.downloadUrl))
    const candidates = completed.filter((item) => (item.export_type ?? item.exportType) === "organization_report")
    if (jobId) candidates.sort((left, right) => (Number(left.id) === jobId ? -1 : Number(right.id) === jobId ? 1 : Number(right.id) - Number(left.id)))
    if (candidates.length === 0) throw new Error("未找到已完成且带 download_url 的 Word 版盘查报告导出任务")

    const skipped = []
    for (const job of candidates) {
      const response = await fetchFromNode(job.download_url ?? job.downloadUrl)
      if (!response.ok) {
        skipped.push(`${job.id}:${response.status}`)
        continue
      }
      const bytes = Buffer.from(await response.arrayBuffer())
      if (bytes.length === 0) {
        skipped.push(`${job.id}:empty`)
        continue
      }
      if (bytes[0] !== 0x50 || bytes[1] !== 0x4b) {
        skipped.push(`${job.id}:not-zip`)
        continue
      }

      const suggested = filenameFromDisposition(response.headers.get("content-disposition")) ?? `${job.job_no ?? basename}.zip`
      const downloadPath = path.join(outputDir, "downloads", `${basename}-${suggested}`)
      await fs.mkdir(path.dirname(downloadPath), { recursive: true })
      await fs.writeFile(downloadPath, bytes)
      const archive = inspectVerificationArchive(downloadPath)
      if ((job.export_type ?? job.exportType) === "organization_report" && archive.docxFiles.length === 0) {
        skipped.push(`${job.id}:missing-docx`)
        continue
      }
      return {
        status: "有效",
        path: downloadPath,
        suggestedFilename: suggested,
        sha256: createHash("sha256").update(bytes).digest("hex"),
        sizeBytes: bytes.length,
        jobId: job.id,
        jobNo: job.job_no ?? job.jobNo,
        exportType: job.export_type ?? job.exportType,
        downloadUrl: job.download_url ?? job.downloadUrl,
        archive,
        skippedCandidates: skipped,
      }
    }
    throw new Error(`导出记录均不可下载：${skipped.join(", ")}`)
  } catch (error) {
    return {
      status: "部分有效",
      failureReason: error instanceof Error ? error.message : String(error),
      reshootSuggestion: "检查导出任务是否已完成并具备 download_url，必要时先在演示租户重新生成核查材料包和盘查报告。",
    }
  }
}

function inspectVerificationArchive(downloadPath) {
  const fileList = execFileSync("unzip", ["-Z1", downloadPath], { encoding: "utf8" })
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
  const docxFiles = fileList
    .filter((item) => item.toLowerCase().endsWith(".docx"))
    .map((archivePath) => {
      const content = execFileSync("unzip", ["-p", downloadPath, archivePath])
      return {
        path: archivePath,
        sizeBytes: content.length,
        sha256: createHash("sha256").update(content).digest("hex"),
      }
    })
  return {
    fileCount: fileList.length,
    files: fileList,
    docxFiles,
  }
}

async function fetchJsonFromNode(url, options = {}) {
  const response = await fetchFromNode(url, options)
  const data = await response.json().catch(() => null)
  return { ok: response.ok, status: response.status, data }
}

async function fetchFromNode(url, options = {}) {
  const target = new URL(url, baseURL)
  const cookies = await context.cookies(baseURL)
  const headers = new Headers(options.headers ?? {})
  const cookieHeader = cookies.map((cookie) => `${cookie.name}=${cookie.value}`).join("; ")
  if (cookieHeader) headers.set("Cookie", cookieHeader)
  if (activeTeamId) headers.set("X-Team-Id", activeTeamId)
  return fetch(target, { ...options, headers })
}

function filenameFromDisposition(disposition) {
  if (!disposition) return null
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (encoded) return decodeURIComponent(encoded)
  const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1]
  return plain || null
}

async function createImportFixture() {
  const fixturePath = path.join(outputDir, "fixtures", `EV-ORG-BASE-002-ghg-import-${Date.now()}.xlsx`)
  execFileSync(
    "uv",
    [
      "run",
      "python",
      path.join(repositoryRoot, "src/js/web/scripts/build-ghg-import-fixture.py"),
      "--output",
      fixturePath,
    ],
    {
      cwd: repositoryRoot,
      stdio: "pipe",
      env: process.env,
    },
  )
  return fixturePath
}

async function readManifest() {
  const fallback = {
    title: "奇瑞绿能综合能碳管理平台采购项目-组织碳截图证据清单",
    cases: [],
    rejectedEvidence: [],
    rejectedCandidates: [],
  }
  try {
    return { ...fallback, ...JSON.parse(await fs.readFile(manifestPath, "utf8")) }
  } catch {
    return fallback
  }
}

async function updateManifest(manifest, capturedRecords, rejectedRecords) {
  const capturedAt = new Date().toISOString()
  manifest.environment = {
    baseURL,
    tenantSlug,
    tenantName: activeTeam?.name,
    tenantId: activeTeamId,
    username,
    loginMode: "profile-check-then-form-login",
    viewport: `${viewport.width}x${viewport.height}`,
  }
  manifest.cases = Array.isArray(manifest.cases) ? manifest.cases : []
  manifest.rejectedEvidence = Array.isArray(manifest.rejectedEvidence) ? manifest.rejectedEvidence : []
  manifest.rejectedCandidates = Array.isArray(manifest.rejectedCandidates) ? manifest.rejectedCandidates : []
  for (const evidence of manifest.cases) {
    if (baseEvidenceMappings[evidence.evidenceId]) evidence.featureIds = baseEvidenceMappings[evidence.evidenceId]
  }
  for (const record of capturedRecords) {
    const existingIndex = manifest.cases.findIndex((item) => item.evidenceId === record.evidenceId)
    if (existingIndex >= 0) manifest.cases[existingIndex] = { ...manifest.cases[existingIndex], ...record }
    else manifest.cases.push(record)
  }
  const rejectedById = [...rejectedRecords, ...deferredEvidence]
  const rejectedIds = new Set(rejectedById.map((item) => item.evidenceId))
  manifest.cases = manifest.cases.filter((item) => !rejectedIds.has(item.evidenceId))
  const validIds = new Set(manifest.cases.map((item) => item.evidenceId))
  manifest.rejectedCandidates = [
    ...manifest.rejectedCandidates.filter((item) => !validIds.has(item.evidenceId) && !rejectedById.some((next) => next.evidenceId === item.evidenceId)),
    ...rejectedById.filter((item) => !validIds.has(item.evidenceId)),
  ]
  manifest.rejectedEvidence = manifest.rejectedEvidence.filter((item) => !validIds.has(item.evidenceId))
  manifest.updatedAt = capturedAt
  await fs.writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`)
}

async function writeEvidenceIndex(manifest) {
  const cases = Array.isArray(manifest.cases) ? manifest.cases : []
  const rejected = Array.isArray(manifest.rejectedCandidates) ? manifest.rejectedCandidates : []
  const rows = [...cases, ...rejected].flatMap((record) =>
    (record.featureIds ?? record.functionIds ?? []).map((functionId) => ({
      functionId,
      subFunction: record.title,
      evidenceId: record.evidenceId,
      route: record.route,
      screenshotPath: record.screenshotPath || record.filename || "",
      status: record.status,
      expectedEvidenceLevel: record.expectedEvidenceLevel,
      acceptanceConclusion: record.acceptanceConclusion,
      failureReason: record.failureReason,
      reshootSuggestion: record.reshootSuggestion,
    })),
  )
  const payload = {
    title: "组织碳功能序号到截图证据索引",
    updatedAt: new Date().toISOString(),
    tenantSlug,
    tenantName: activeTeam?.name,
    rows: rows.sort((a, b) => `${a.functionId}${a.evidenceId}`.localeCompare(`${b.functionId}${b.evidenceId}`)),
  }
  await fs.writeFile(indexPath, `${JSON.stringify(payload, null, 2)}\n`)
}
