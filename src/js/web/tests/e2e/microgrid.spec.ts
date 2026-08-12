import { expect, type Page, test } from "@playwright/test"

const now = "2026-08-12T08:00:00+08:00"

const assets = [
  asset(1, "PCC", "市电并网点", "grid", 720, 1000, false),
  asset(2, "PV-01", "屋顶光伏", "pv", 310, 600, false),
  { ...asset(3, "BESS-01", "储能系统", "storage", -120, 300, true), ratedEnergyKwh: 600, socPct: 62 },
  asset(4, "EVSE-GROUP", "充电桩群", "charger", 88, 240, true),
  asset(5, "LIGHTING", "仓库照明", "lighting", 42, 90, true),
  asset(6, "WAREHOUSE", "仓储作业负荷", "load", 600, 800, false),
]

const forecastPoints = Array.from({ length: 96 }, (_, index) => {
  const validAt = new Date(Date.parse(now) + index * 15 * 60 * 1000).toISOString()
  const load = 470 + 80 * Math.sin((index / 96) * Math.PI * 2)
  const pv = index > 22 && index < 70 ? 300 * Math.sin(((index - 22) / 48) * Math.PI) : 0
  return [
    { seriesCode: "load", validAt, p10: load * 0.92, p50: load, p90: load * 1.08, unit: "kW" },
    { seriesCode: "pv", validAt, p10: pv * 0.82, p50: pv, p90: pv * 1.12, unit: "kW" },
    { seriesCode: "soc", validAt, p10: 57, p50: 62, p90: 67, unit: "%" },
  ]
}).flat()

const schedule = Array.from({ length: 96 }, (_, index) => {
  const validAt = new Date(Date.parse(now) + index * 15 * 60 * 1000).toISOString()
  const loadKw = 470 + 80 * Math.sin((index / 96) * Math.PI * 2)
  const pvKw = index > 22 && index < 70 ? 300 * Math.sin(((index - 22) / 48) * Math.PI) : 0
  const batteryDischargeKw = index > 65 && index < 82 ? 110 : 0
  const batteryChargeKw = index > 35 && index < 55 ? 90 : 0
  return {
    validAt,
    loadKw,
    pvKw,
    gridImportKw: Math.max(loadKw - pvKw - batteryDischargeKw + batteryChargeKw, 0),
    gridExportKw: 0,
    batteryChargeKw,
    batteryDischargeKw,
    chargerKw: index > 4 && index < 30 ? 80 : 0,
    lightingKw: 38,
    generatorKw: 0,
    curtailedPvKw: 0,
    socPct: 62 + batteryChargeKw / 30 - batteryDischargeKw / 45,
    tariffCnyPerKwh: index > 64 && index < 84 ? 1.18 : 0.62,
    intervalCostCny: 65,
  }
})

const forecastRun = {
  id: 11,
  siteId: 1,
  scenarioId: 1,
  status: "completed",
  horizonStart: now,
  horizonEnd: "2026-08-13T08:00:00+08:00",
  intervalMinutes: 15,
  modelVersion: "hist-gradient-boosting-quantile-v1",
  metrics: { mae_kw: 18.4, rmse_kw: 22.8, mape_pct: 4.1, coverage: 0.82, model: "HistGradientBoosting-P10/P50/P90" },
  inputSnapshot: { scenarioVersion: 1, weatherProvider: "open-meteo" },
  completedAt: now,
  errorMessage: null,
  points: forecastPoints,
}

const optimizationRun = {
  id: 21,
  siteId: 1,
  scenarioId: 1,
  forecastRunId: 11,
  status: "optimal",
  solver: "HiGHS",
  solverSeconds: 0.428,
  mipGap: 0.004,
  objectiveCny: 4632.5,
  baselineCostCny: 5186.3,
  savingsCny: 553.8,
  peakReductionKw: 116,
  carbonReductionKg: 82.4,
  costBreakdown: { energy_cost_cny: 4210, demand_cost_cny: 350, battery_degradation_cny: 72.5 },
  diagnostics: [{ constraint: "power_balance", severity: "info", message: "96个时段功率平衡均满足" }],
  inputSnapshot: { scenarioVersion: 1, reserveMarginPct: 8 },
  completedAt: now,
  errorMessage: null,
  schedule,
}

async function installApiMocks(page: Page) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname
    if (!path.startsWith("/api/")) {
      await route.continue()
      return
    }
    let body: unknown = { items: [] }
    if (path === "/api/me") {
      body = {
        id: "00000000-0000-0000-0000-000000000001",
        email: "demo@example.com",
        name: "祥泰演示管理员",
        isActive: true,
        isVerified: true,
        isSuperuser: true,
        createdAt: now,
        updatedAt: now,
      }
    } else if (path === "/api/config/public") {
      body = { displayName: "能碳管理平台", shortName: "EC", authMode: "cookie-session", captchaEnabled: false }
    } else if (path === "/api/teams") {
      body = { items: [] }
    } else if (path === "/api/microgrid/overview") {
      body = {
        configured: true,
        mode: "shadow",
        site: { id: 1, code: "xiangtai-taizhou", name: "祥泰仓库微电网", pccCapacityKw: 1000, status: "shadow", sourceName: "祥泰演示V1" },
        scenario: { id: 1, name: "祥泰演示V1", version: 1, sourceKind: "enterprise_assumption", sourceName: "祥泰演示V1", confidenceLevel: 0.5 },
        metrics: { pccPowerKw: 720, pvPowerKw: 310, socPct: 62, onlineAssets: 6, totalAssets: 6, savingsCny: 553.8, peakReductionKw: 116, carbonReductionKg: 82.4, alarmCount: 0 },
        trend: schedule.map((point) => ({ period: point.validAt, loadKw: point.loadKw, pvKw: point.pvKw, gridImportKw: point.gridImportKw, socPct: point.socPct })),
        assets,
        forecastRun,
        optimizationRun,
      }
    } else if (path === "/api/microgrid/topology") {
      body = {
        configured: true,
        mode: "shadow",
        schemaVersion: 3,
        topologyVersion: 1,
        canvas: { width: 1440, height: 1020 },
        layout: { algorithm: "dagre", direction: "TB", rankSeparation: 80, nodeSeparation: 34, edgeSeparation: 18 },
        site: { id: 1, code: "xiangtai-taizhou", name: "祥泰仓库微电网", pccCapacityKw: 1000, status: "shadow", sourceName: "祥泰演示V1" },
        nodes: [
          { id: "grid", kind: "utility", assetCode: "PCC", label: "10kV市电", ports: [{ id: "out", side: "bottom", direction: "output" }] },
          {
            id: "isolator",
            kind: "isolator",
            label: "高压隔离开关",
            ports: [
              { id: "in", side: "top", direction: "input" },
              { id: "out", side: "bottom", direction: "output" },
            ],
          },
          {
            id: "breaker",
            kind: "breaker",
            label: "高压进线断路器",
            ports: [
              { id: "in", side: "top", direction: "input" },
              { id: "out", side: "bottom", direction: "output" },
            ],
          },
          {
            id: "transformer",
            kind: "transformer",
            label: "10/0.4kV变压器",
            ports: [
              { id: "in", side: "top", direction: "input" },
              { id: "out", side: "bottom", direction: "output" },
            ],
          },
          {
            id: "bus",
            kind: "busbar",
            label: "0.4kV主母线",
            ports: [
              { id: "main-in", side: "top", direction: "input", offset: 0.15 },
              { id: "pv-in", side: "top", direction: "input", offset: 0.32 },
              { id: "storage-out", side: "bottom", direction: "output", offset: 0.12 },
              { id: "charger-out", side: "bottom", direction: "output", offset: 0.38 },
              { id: "lighting-out", side: "bottom", direction: "output", offset: 0.64 },
              { id: "load-out", side: "bottom", direction: "output", offset: 0.9 },
            ],
          },
          { id: "pv", kind: "pv", assetCode: "PV-01", label: "屋顶光伏", ports: [{ id: "out", side: "bottom", direction: "output" }] },
          {
            id: "pv-inverter",
            kind: "inverter",
            assetCode: "PV-01",
            label: "光伏逆变器",
            ports: [
              { id: "in", side: "top", direction: "input" },
              { id: "out", side: "bottom", direction: "output" },
            ],
          },
          { id: "bess", kind: "storage", assetCode: "BESS-01", label: "储能系统", ports: [{ id: "in", side: "top", direction: "input" }] },
          { id: "charger", kind: "charger", assetCode: "EVSE-GROUP", label: "充电桩群", ports: [{ id: "in", side: "top", direction: "input" }] },
          { id: "lighting", kind: "lighting", assetCode: "LIGHTING", label: "仓库照明", ports: [{ id: "in", side: "top", direction: "input" }] },
          { id: "load", kind: "load", assetCode: "WAREHOUSE", label: "仓储作业负荷", ports: [{ id: "in", side: "top", direction: "input" }] },
        ],
        edges: [
          { id: "grid-isolator", source: "grid", target: "isolator", sourceHandle: "out", targetHandle: "in", assetCode: "PCC" },
          { id: "isolator-breaker", source: "isolator", target: "breaker", sourceHandle: "out", targetHandle: "in", assetCode: "PCC" },
          { id: "breaker-transformer", source: "breaker", target: "transformer", sourceHandle: "out", targetHandle: "in", assetCode: "PCC" },
          { id: "transformer-bus", source: "transformer", target: "bus", sourceHandle: "out", targetHandle: "main-in", assetCode: "PCC" },
          { id: "pv-inverter", source: "pv", target: "pv-inverter", sourceHandle: "out", targetHandle: "in", assetCode: "PV-01" },
          { id: "inverter-bus", source: "pv-inverter", target: "bus", sourceHandle: "out", targetHandle: "pv-in", assetCode: "PV-01" },
          { id: "bus-bess", source: "bus", target: "bess", sourceHandle: "storage-out", targetHandle: "in", assetCode: "BESS-01" },
          { id: "bus-charger", source: "bus", target: "charger", sourceHandle: "charger-out", targetHandle: "in", assetCode: "EVSE-GROUP" },
          { id: "bus-lighting", source: "bus", target: "lighting", sourceHandle: "lighting-out", targetHandle: "in", assetCode: "LIGHTING" },
          { id: "bus-load", source: "bus", target: "load", sourceHandle: "load-out", targetHandle: "in", assetCode: "WAREHOUSE" },
        ],
        assets,
      }
    } else if (/\/api\/microgrid\/assets\/\d+\/series/.test(path)) {
      body = {
        items: Array.from({ length: 24 }, (_, index) => ({
          observedAt: new Date(Date.parse(now) - (23 - index) * 60 * 60 * 1000).toISOString(),
          value: 280 + 35 * Math.sin(index / 4),
          unit: "kW",
          sourceKind: "simulated",
          quality: "simulated",
        })),
      }
    } else if (path === "/api/microgrid/assets") {
      body = { items: assets }
    } else if (path === "/api/microgrid/scenarios") {
      body = {
        items: [
          {
            id: 1,
            siteId: 1,
            code: "xiangtai-demo",
            name: "祥泰演示V1",
            version: 1,
            status: "published",
            sourceKind: "enterprise_assumption",
            sourceName: "祥泰仓库台账 + 待确认铭牌参数",
            confidenceLevel: 0.5,
            validFrom: now,
            publishedAt: now,
            parameters: {},
          },
        ],
      }
    } else if (path === "/api/microgrid/flexibility-contracts") {
      body = {
        items: [
          {
            id: 1,
            scenarioId: 1,
            assetId: 4,
            assetCode: "EVSE-GROUP",
            assetName: "充电桩群",
            assetType: "charger",
            contractType: "energy_deadline",
            startMinute: 420,
            endMinute: 1320,
            minimumPowerKw: 0,
            maximumPowerKw: 240,
            targetEnergyKwh: 720,
            priority: 80,
            penaltyCnyPerKwh: 8,
            enabled: true,
          },
          {
            id: 2,
            scenarioId: 1,
            assetId: 5,
            assetCode: "LIGHTING",
            assetName: "仓库照明",
            assetType: "lighting",
            contractType: "minimum_service",
            startMinute: 0,
            endMinute: 1440,
            minimumPowerKw: 44,
            maximumPowerKw: 80,
            targetEnergyKwh: null,
            priority: 95,
            penaltyCnyPerKwh: 12,
            enabled: true,
          },
        ],
      }
    } else if (path === "/api/microgrid/forecast-runs") {
      body = { items: [forecastRun] }
    } else if (path === "/api/microgrid/forecast-runs/11") {
      body = forecastRun
    } else if (path === "/api/microgrid/optimization-runs") {
      body = { items: [optimizationRun] }
    } else if (path === "/api/microgrid/optimization-runs/21") {
      body = optimizationRun
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) })
  })
}

for (const [path, heading, mode, evidence] of [
  ["/microgrid/overview", "微电网运行总览", "影子运行", "未来24小时功率计划"],
  ["/microgrid/operations", "运行监控", "影子运行", "一次系统运行图"],
  ["/microgrid/forecast", "微电网预测分析", "实测负荷优先", "仓库负荷分位数预测"],
  ["/microgrid/optimization", "微电网智能优化", "模拟闭环", "资源调度计划"],
  ["/microgrid/settings/assets", "微电网设备与场景", "已发布 / 不可修改", "资源参数与来源"],
  ["/microgrid/settings/flexibility", "微电网柔性契约", "安全下限优先", "调度边界"],
] as const) {
  test(`${heading} renders the configured Xiangtai shadow workflow`, async ({ page }) => {
    await installApiMocks(page)
    await page.goto(path)
    await expect(page.getByRole("heading", { name: heading })).toBeVisible()
    await expect(page.getByText(mode, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(evidence, { exact: true })).toBeVisible()
  })
}

function asset(id: number, code: string, name: string, assetType: string, activePowerKw: number, ratedPowerKw: number, controllable: boolean) {
  return {
    id,
    siteId: 1,
    code,
    name,
    assetType,
    ratedPowerKw,
    ratedEnergyKwh: null,
    controllable,
    parameters: {},
    sourceKind: "enterprise_assumption",
    sourceName: "祥泰演示V1",
    confidenceLevel: 0.5,
    online: true,
    operatingMode: "shadow",
    activePowerKw,
    socPct: null,
    temperatureC: 27,
    alarmLevel: "normal",
    observedAt: now,
    stateSourceKind: "simulated",
  }
}

test("SCADA runtime opens the device faceplate", async ({ page }) => {
  await installApiMocks(page)
  await page.goto("/microgrid/operations")
  await expect(page.getByTestId("microgrid-scada-runtime")).toBeVisible()
  await page.getByText("屋顶光伏", { exact: true }).first().click()
  await expect(page.getByRole("heading", { name: "屋顶光伏" })).toBeVisible()
  await expect(page.getByText("最近24小时功率", { exact: true })).toBeVisible()
})
