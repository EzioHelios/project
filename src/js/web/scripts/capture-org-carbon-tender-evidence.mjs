import { chromium } from "@playwright/test"
import { createHash } from "node:crypto"
import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:18101"
const username = process.env.E2E_ADMIN_EMAIL
const password = process.env.E2E_ADMIN_PASSWORD
const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../..")
const outputDir = path.resolve(
  process.env.EVIDENCE_OUTPUT_DIR ?? path.join(repositoryRoot, "outputs/chery-bid-feature-decomposition-20260823/screenshots"),
)
const manifestPath = path.join(outputDir, "evidence-manifest.json")

const baseEvidenceMappings = {
  "EVD-OC-01": ["CHERY-CARBON-048-01", "CHERY-CARBON-048-02", "CHERY-CARBON-048-05", "CHERY-CARBON-049-02"],
  "EVD-OC-02": ["CHERY-CARBON-049-01"],
  "EVD-OC-03": ["CHERY-CARBON-050-01"],
  "EVD-OC-04": ["CHERY-CARBON-051-01", "CHERY-CARBON-051-03"],
  "EVD-OC-05": ["CHERY-CARBON-052-01", "CHERY-CARBON-053-01"],
}

const evidenceDefinitions = [
  {
    evidenceId: "EVD-OC-03E",
    route: "/carbon/organization/flow",
    state: "碳流总览与加权流向关系",
    featureIds: ["CHERY-CARBON-050-01"],
    filename: "EVD-OC-03E-carbon-flow-overview.png",
    requiredTexts: ["组织边界至区域设备碳流", "排放范围构成"],
  },
  {
    evidenceId: "EVD-OC-03F",
    route: "/carbon/organization/flow",
    state: "碳流核算异常独立状态",
    featureIds: ["CHERY-CARBON-050-04"],
    filename: "EVD-OC-03F-carbon-flow-anomalies.png",
    requiredTexts: ["核算异常", "证据缺失", "未归集区域/设备"],
  },
  {
    evidenceId: "EVD-OC-04B",
    route: "/carbon/organization/boundary",
    state: "运营控制法与边界版本口径",
    featureIds: ["CHERY-CARBON-051-02", "CHERY-CARBON-051-03"],
    filename: "EVD-OC-04B-boundary-method-version.png",
    requiredTexts: ["边界口径", "运营控制法", "ISO类别"],
  },
  {
    evidenceId: "EVD-OC-04C",
    route: "/carbon/organization/boundary",
    state: "边界版本差异对比",
    featureIds: ["CHERY-CARBON-051-04"],
    filename: "EVD-OC-04C-boundary-version-diff.png",
    requiredTexts: ["边界版本对比", "变更字段", "当前版本"],
  },
  {
    evidenceId: "EVD-OC-05B",
    route: "/carbon/organization/inventory",
    state: "盘查报告版本与状态台账",
    featureIds: ["CHERY-CARBON-052-01", "CHERY-CARBON-053-01"],
    filename: "EVD-OC-05B-inventory-report-ledger.png",
    requiredTexts: ["盘查报告台账", "报告版本", "状态"],
  },
  {
    evidenceId: "EVD-OC-05C",
    route: "/carbon/organization/inventory",
    state: "报告冻结快照、证据覆盖与审批轨迹",
    featureIds: ["CHERY-CARBON-052-02", "CHERY-CARBON-053-02", "CHERY-CARBON-053-04"],
    filename: "EVD-OC-05C-inventory-report-audit.png",
    requiredTexts: ["审批轨迹", "证据覆盖率", "报告版本"],
  },
  {
    evidenceId: "EVD-OC-06",
    route: "/carbon/verification",
    state: "核查项目工作台与项目状态",
    featureIds: ["CHERY-CARBON-053-01"],
    filename: "EVD-OC-06-verification-project-workbench.png",
    requiredTexts: ["核查项目", "DEMO-PARK-VER-2025-01"],
  },
  {
    evidenceId: "EVD-OC-06B",
    route: "/carbon/verification",
    state: "证据资料台账与文件关联",
    featureIds: ["CHERY-CARBON-054-01", "CHERY-CARBON-054-02"],
    filename: "EVD-OC-06B-verification-evidence.png",
    requiredTexts: ["证据资料", "DEMO-PARK-EVD-2025-C11"],
  },
  {
    evidenceId: "EVD-OC-06C",
    route: "/carbon/verification",
    state: "核查过程追溯",
    featureIds: ["CHERY-CARBON-053-03"],
    filename: "EVD-OC-06C-verification-trace.png",
    requiredTexts: ["核查工作", "RPT-62-65"],
  },
  {
    evidenceId: "EVD-OC-06D",
    route: "/carbon/verification",
    state: "核查发现与整改闭环",
    featureIds: ["CHERY-CARBON-053-03"],
    filename: "EVD-OC-06D-verification-findings.png",
    requiredTexts: ["质量问题", "DEMO-PARK-VF-2025-001"],
  },
  {
    evidenceId: "EVD-OC-06E",
    route: "/carbon/verification",
    state: "审核日志与责任人轨迹",
    featureIds: ["CHERY-CARBON-053-02", "CHERY-CARBON-053-04"],
    filename: "EVD-OC-06E-verification-audit.png",
    requiredTexts: ["审核日志", "组织碳复核专员"],
  },
  {
    evidenceId: "EVD-OC-06F",
    route: "/carbon/verification",
    state: "核查材料包组成与导出准备",
    featureIds: ["CHERY-CARBON-054-03"],
    filename: "EVD-OC-06F-verification-material-package.png",
    requiredTexts: ["报告与材料", "报告主体基本信息"],
  },
  {
    evidenceId: "EVD-OC-06G",
    route: "/carbon/verification",
    state: "组织盘查报告导出内容预览",
    featureIds: ["CHERY-CARBON-052-02"],
    filename: "EVD-OC-06G-verification-report-export.png",
    requiredTexts: ["报告导出", "固定源天然气燃烧"],
  },
  {
    evidenceId: "EVD-OC-06H",
    route: "/carbon/verification",
    state: "组织报告与核查材料包异步导出完成",
    featureIds: ["CHERY-CARBON-052-02", "CHERY-CARBON-054-03"],
    filename: "EVD-OC-06H-verification-export-completed.png",
    requiredTexts: ["导出记录", "已完成", "下载"],
  },
]

if (!username || !password) {
  throw new Error("E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD are required")
}

await fs.mkdir(outputDir, { recursive: true })

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
const page = await context.newPage()
const consoleErrors = []
page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text())
})

async function settle() {
  await page.evaluate(async () => {
    await document.fonts.ready
    window.scrollTo({ top: 0, left: 0, behavior: "instant" })
    document.documentElement.scrollLeft = 0
    document.body.scrollLeft = 0
  })
  await page.waitForTimeout(500)
}

async function capture(name) {
  await settle()
  await page.screenshot({ path: `${outputDir}/${name}`, fullPage: false })
}

async function captureAt(name, locator) {
  await locator.scrollIntoViewIfNeeded()
  await page.waitForTimeout(350)
  await page.evaluate(() => {
    document.documentElement.scrollLeft = 0
    document.body.scrollLeft = 0
  })
  await page.screenshot({ path: `${outputDir}/${name}`, fullPage: false })
}

async function selectVerificationProject() {
  const row = page.locator("tr").filter({ hasText: "DEMO-PARK-VER-2025-01" }).first()
  await row.waitFor({ state: "visible" })
  await row.click()
  await page.waitForTimeout(400)
}

await page.goto(`${baseURL}/login`, { waitUntil: "domcontentloaded" })
await page.locator('input[name="username"]').fill(username)
await page.locator('input[name="password"]').fill(password)
await page.getByRole("button", { name: /登录|Login/i }).click()
await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 })
await page.addStyleTag({ content: '[data-sonner-toast] { display: none !important; }' })

await page.goto(`${baseURL}/carbon/organization/boundary`, { waitUntil: "domcontentloaded" })
await page.getByText("边界口径", { exact: true }).waitFor()
await page.getByText("运营控制法", { exact: true }).waitFor()
await capture("EVD-OC-04B-boundary-method-version.png")

await page.getByRole("button", { name: "创建工作草稿" }).click()
await page.getByRole("button", { name: "放弃草稿" }).waitFor()
const editableCheckbox = page.locator('input[type="checkbox"]:not([disabled])').first()
await editableCheckbox.click()
await page.getByRole("button", { name: "保存" }).click()
await page.waitForTimeout(700)
await page.getByRole("button", { name: "版本对比" }).click()
await page.getByText("边界版本对比", { exact: true }).waitFor()
await page.waitForTimeout(350)
await page.getByText("当前版本无差异", { exact: true }).waitFor({ state: "detached", timeout: 10_000 }).catch(() => {})
await page.locator("[data-sonner-toast]").evaluateAll((nodes) => nodes.forEach((node) => node.remove()))
await page.screenshot({ path: `${outputDir}/EVD-OC-04C-boundary-version-diff.png`, fullPage: false })
await page.keyboard.press("Escape")
await page.getByRole("button", { name: "放弃草稿" }).click()
await page.getByRole("button", { name: "创建工作草稿" }).waitFor()

await page.goto(`${baseURL}/carbon/organization/inventory`, { waitUntil: "domcontentloaded" })
await page.getByText("盘查报告台账", { exact: true }).waitFor()
await page.getByText("2025年度组织温室气体盘查报告", { exact: true }).first().waitFor()
await capture("EVD-OC-05B-inventory-report-ledger.png")
const reportRow = page.locator("tr").filter({ hasText: "2025年度组织温室气体盘查报告" }).filter({ hasText: "v2" }).first()
await reportRow.getByRole("button", { name: "查看" }).click()
await page.getByText("审批轨迹", { exact: true }).waitFor()
await page.waitForTimeout(350)
await page.getByText("发布", { exact: true }).last().waitFor()
await page.screenshot({ path: `${outputDir}/EVD-OC-05C-inventory-report-audit.png`, fullPage: false })
await page.keyboard.press("Escape")

await page.goto(`${baseURL}/carbon/organization/flow`, { waitUntil: "domcontentloaded" })
await page.getByText("10,197.18", { exact: true }).waitFor()
await page.getByText("组织边界至区域设备碳流", { exact: false }).waitFor()
await capture("EVD-OC-03E-carbon-flow-overview.png")
const anomalyPanel = page.locator("section").filter({ hasText: "核算异常" }).last()
await captureAt("EVD-OC-03F-carbon-flow-anomalies.png", anomalyPanel)

await page.goto(`${baseURL}/carbon/verification`, { waitUntil: "domcontentloaded" })
await page.getByText("DEMO-PARK-VER-2025-01", { exact: true }).waitFor()
await selectVerificationProject()
await capture("EVD-OC-06-verification-project-workbench.png")

await page.getByRole("tab", { name: "证据资料", exact: true }).click()
await page.getByText("DEMO-PARK-EVD-2025-C11", { exact: true }).first().waitFor()
await capture("EVD-OC-06B-verification-evidence.png")

await page.getByRole("tab", { name: "核查工作", exact: true }).click()
await page.getByText("RPT-62-65", { exact: true }).waitFor()
await capture("EVD-OC-06C-verification-trace.png")
await page.getByRole("tab", { name: "质量问题", exact: true }).click()
await page.getByText("DEMO-PARK-VF-2025-001", { exact: true }).waitFor()
await capture("EVD-OC-06D-verification-findings.png")
await page.getByRole("tab", { name: "审核日志", exact: true }).click()
await page.getByText("组织碳复核专员", { exact: true }).first().waitFor()
await capture("EVD-OC-06E-verification-audit.png")

await page.getByRole("tab", { name: "报告与材料", exact: true }).click()
await page.getByText("报告主体基本信息", { exact: true }).waitFor()
await capture("EVD-OC-06F-verification-material-package.png")
await page.getByRole("tab", { name: "报告导出", exact: true }).click()
await page.getByText("固定源天然气燃烧", { exact: true }).waitFor()
await capture("EVD-OC-06G-verification-report-export.png")

const exportPanel = page.locator("section").filter({ hasText: "导出记录" }).last()
if ((await exportPanel.getByRole("button", { name: "下载" }).count()) < 2) {
  await page.getByRole("button", { name: "生成核查材料包", exact: true }).click()
  await page.waitForTimeout(700)
  await page.getByRole("button", { name: "生成盘查报告", exact: true }).click()
}
await exportPanel.getByRole("button", { name: "下载" }).nth(1).waitFor({ timeout: 90_000 })
await captureAt("EVD-OC-06H-verification-export-completed.png", exportPanel)

await fs.writeFile(`${outputDir}/browser-console-errors.json`, JSON.stringify(consoleErrors, null, 2))

const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"))
const capturedAt = new Date().toISOString()
for (const evidence of manifest.cases) {
  if (baseEvidenceMappings[evidence.evidenceId]) evidence.featureIds = baseEvidenceMappings[evidence.evidenceId]
}
for (const definition of evidenceDefinitions) {
  const bytes = await fs.readFile(path.join(outputDir, definition.filename))
  const record = {
    ...definition,
    actualUrl: `${baseURL}${definition.route}`,
    viewport: "1440x900",
    capturedAt,
    sha256: createHash("sha256").update(bytes).digest("hex"),
    emptyMarkers: [],
  }
  const existingIndex = manifest.cases.findIndex((item) => item.evidenceId === definition.evidenceId)
  if (existingIndex >= 0) manifest.cases[existingIndex] = { ...manifest.cases[existingIndex], ...record }
  else manifest.cases.push(record)
}
manifest.rejectedEvidence = manifest.rejectedEvidence.filter((item) => item.evidenceId !== "EVD-OC-06")
const successfulEvidenceIds = new Set(manifest.cases.map((item) => item.evidenceId))
manifest.rejectedCandidates = manifest.rejectedCandidates.filter(
  (item) => !successfulEvidenceIds.has(item.evidenceId),
)
manifest.updatedAt = capturedAt
await fs.writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`)
await browser.close()
