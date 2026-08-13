import { expect, type Page, test } from "@playwright/test"

type ThemeMode = "light" | "dark"

const representativeRoutes = [
  { path: "/home", slug: "workbench", heading: "工作台" },
  { path: "/energy/consumption", slug: "energy-consumption", heading: "能耗查询" },
  { path: "/energy/benchmark", slug: "energy-benchmark", heading: "能效对标" },
  { path: "/microgrid/overview", slug: "microgrid-overview", heading: "运行总览" },
  { path: "/carbon/accounting", slug: "carbon-accounting", heading: "碳排放核算" },
  { path: "/carbon-mgmt/factors", slug: "factor-library", heading: "排放因子库" },
] as const

const trend = Array.from({ length: 24 }, (_, index) => ({
  period: `08-${String(index + 1).padStart(2, "0")}`,
  loadKw: 420 + index * 9,
  pvKw: Math.max(0, 260 - Math.abs(12 - index) * 18),
  gridImportKw: 280 + index * 6,
}))

async function installDesignSystemMocks(page: Page) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    if (!path.startsWith("/api/")) {
      await route.continue()
      return
    }
    let body: unknown = { items: [] }

    if (path === "/api/me") {
      body = {
        id: "00000000-0000-0000-0000-000000000001",
        email: "design-system@example.com",
        name: "设计系统验收员",
        isActive: true,
        isVerified: true,
        isSuperuser: true,
        teams: [],
        createdAt: "2026-08-12T08:00:00+08:00",
        updatedAt: "2026-08-12T08:00:00+08:00",
      }
    } else if (path === "/api/config/public") {
      body = { displayName: "能碳管理平台", shortName: "EC", brandMarkUrl: null, faviconUrl: null, authMode: "cookie-session", captchaEnabled: false }
    } else if (path === "/api/teams") {
      body = { items: [] }
    } else if (path === "/api/energy/benchmark/profiles") {
      body = { items: [], total: 0, limit: 200, offset: 0 }
    } else if (path === "/api/energy/benchmark/baseline") {
      body = { code: 200, data: { items: [] } }
    } else if (path === "/api/energy/benchmark/comparisons") {
      body = { code: 200, data: { items: [], total: 0 } }
    } else if (path === "/api/energy/benchmark/conclusions") {
      body = {
        code: 200,
        data: {
          summary: { total: 0, status_counts: {}, saving_potential: 0, unit: "kgce/unit" },
          top_deviations: [],
          missing_benchmarks: [],
        },
      }
    } else if (path === "/api/energy/benchmark/recommendations") {
      body = { code: 200, data: { items: [] } }
    } else if (path === "/api/energy/consumption/summary") {
      body = {
        code: 200,
        data: {
          totals: { record_count: 128, original_amount: 486320, standard_amount: 59740, tce_amount: 59.74, co2e_amount: 38420 },
          items: [
            {
              group_key: "electricity",
              group_label: "电力",
              record_count: 96,
              original_amount: 428600,
              original_unit: "kWh",
              factor_amount: 428600,
              factor_unit: "kWh",
              standard_amount: 52.66,
              standard_unit: "tce",
              tce_amount: 52.66,
              co2e_amount: 32680,
            },
            {
              group_key: "gas",
              group_label: "天然气",
              record_count: 32,
              original_amount: 57720,
              original_unit: "m³",
              factor_amount: 57720,
              factor_unit: "m³",
              standard_amount: 7.08,
              standard_unit: "tce",
              tce_amount: 7.08,
              co2e_amount: 5740,
            },
          ],
        },
      }
    } else if (path === "/api/energy/consumption/facts") {
      body = { items: [], total: 0, limit: 20, offset: 0 }
    } else if (path === "/api/energy/types") {
      body = {
        code: 200,
        data: {
          items: [
            {
              code: "electricity",
              name: "电力",
              category: "purchased",
              default_scope: "scope2",
              original_unit: "kWh",
              standard_unit: "tce",
              standard_factor: 0.0001229,
              standard_code: "GB/T 2589-2020",
            },
          ],
        },
      }
    } else if (path === "/api/energy/unit-conversions") {
      body = { code: 200, data: { items: [] } }
    } else if (path === "/api/microgrid/overview") {
      body = {
        configured: true,
        mode: "shadow",
        site: { id: 1, code: "demo", name: "示范园区微电网", pccCapacityKw: 1200, status: "shadow", sourceName: "运营台账" },
        scenario: { id: 1, name: "日前运行场景", version: 3, sourceKind: "enterprise_assumption", sourceName: "运营台账", confidenceLevel: 0.8 },
        metrics: {
          pccPowerKw: 618,
          pvPowerKw: 286,
          socPct: 67,
          onlineAssets: 18,
          totalAssets: 19,
          savingsCny: 842.6,
          peakReductionKw: 126,
          carbonReductionKg: 96.4,
          alarmCount: 1,
        },
        trend,
        assets: [],
        forecastRun: { id: 11, status: "completed", modelVersion: "forecast-v3", completedAt: "2026-08-12T08:00:00+08:00" },
        optimizationRun: { id: 12, status: "optimal", solver: "HiGHS", completedAt: "2026-08-12T08:05:00+08:00" },
      }
    } else if (path === "/api/carbon/factor-library/overview") {
      body = {
        code: 200,
        data: {
          batch: { snapshot_id: "CN-EF-2026-08", source_system: "国家标准与官方指南", checksum_verified: true, xlsx_count: 12 },
          library_count: 6,
          category_count: 138,
          leaf_category_count: 96,
          raw_record_count: 2840,
        },
      }
    } else if (path === "/api/carbon/factor-library/category-tree") {
      body = {
        code: 200,
        data: {
          groups: [
            {
              library_year: "2026",
              library_code: "CN-EF",
              library_name: "中国排放因子库",
              institution: "官方来源",
              children: [
                {
                  id: 1,
                  source_category_id: "energy",
                  category_code: "ENERGY",
                  library_year: "2026",
                  library_code: "CN-EF",
                  category_name: "能源活动",
                  category_path: "能源活动",
                  depth: 0,
                  is_leaf: false,
                  children: [
                    {
                      id: 2,
                      source_category_id: "electricity",
                      parent_source_category_id: "energy",
                      category_code: "ELECTRICITY",
                      library_year: "2026",
                      library_code: "CN-EF",
                      category_name: "外购电力",
                      category_path: "能源活动/外购电力",
                      depth: 1,
                      is_leaf: true,
                      children: [],
                    },
                  ],
                },
              ],
            },
          ],
        },
      }
    } else if (path === "/api/carbon/factor-library/records") {
      body = {
        code: 200,
        data: {
          items: [
            {
              id: 1,
              snapshot_id: "CN-EF-2026-08",
              library_year: "2026",
              library_code: "CN-EF",
              library_name: "中国排放因子库",
              category_path: "能源活动/外购电力",
              factor_name: "全国电网平均排放因子",
              display_factor_name: "全国电网平均排放因子",
              factor_value_raw: "0.5366",
              factor_unit_raw: "kgCO2e/kWh",
              region_raw: "中国",
              gas_raw: "CO2e",
              provider: "官方来源",
              projection_status: "candidate",
            },
          ],
          total: 1,
          limit: 50,
          offset: 0,
        },
      }
    }

    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) })
  })
}

async function openRepresentativePage(page: Page, path: string, heading: string, mode: ThemeMode) {
  await page.emulateMedia({ colorScheme: mode, reducedMotion: "reduce" })
  await page.addInitScript(() => {
    localStorage.clear()
    localStorage.setItem("app-theme-preference", "system")
  })
  await installDesignSystemMocks(page)
  await page.goto(path)
  await expect(page.locator("html")).toHaveAttribute("data-theme", mode)
  await expect(page.getByRole("heading", { name: heading, exact: true }).first()).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  await page.addStyleTag({ content: ".tsqd-parent-container { display: none !important; }" })
}

async function expectSharedSurfaceHierarchy(page: Page) {
  const surfaces = await page.locator(".admin-tabs-list, .admin-filter-bar").evaluateAll((elements) =>
    elements.map((element) => {
      const style = getComputedStyle(element)
      return {
        kind: element.classList.contains("admin-tabs-list") ? "tabs" : "filters",
        borderTopWidth: style.borderTopWidth,
        borderBottomWidth: style.borderBottomWidth,
        boxShadow: style.boxShadow,
      }
    }),
  )

  for (const surface of surfaces) {
    expect(surface.borderTopWidth).toBe("0px")
    expect(surface.boxShadow).toBe("none")
    if (surface.kind === "tabs") expect(surface.borderBottomWidth).toBe("1px")
  }
}

for (const route of representativeRoutes) {
  for (const mode of ["light", "dark"] as const) {
    test(`${route.slug} renders the ${mode} V2 design system`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 })
      await openRepresentativePage(page, route.path, route.heading, mode)
      await expectSharedSurfaceHierarchy(page)
      await expect(page).toHaveScreenshot(`${route.slug}-${mode}.png`, { animations: "disabled", caret: "hide", fullPage: false })
    })
  }
}

for (const mode of ["light", "dark"] as const) {
  test(`sidebar keeps a single ${mode} domain signal when collapsed`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await openRepresentativePage(page, "/energy/consumption", "能耗查询", mode)

    const sidebar = page.locator('[data-sidebar="sidebar"]').first()
    await expect(sidebar.locator('[aria-current="page"]')).toHaveCount(1)
    await page.getByRole("button", { name: "Toggle Sidebar", exact: true }).first().click()
    await expect(page.locator('[data-slot="sidebar"][data-state="collapsed"]')).toBeVisible()
    await expect(page).toHaveScreenshot(`sidebar-collapsed-${mode}.png`, { animations: "disabled", caret: "hide", fullPage: false })
  })
}

test("admin surfaces avoid page-level horizontal overflow at desktop and mobile widths", async ({ page }) => {
  for (const viewport of [
    { width: 1280, height: 720 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport)
    await openRepresentativePage(page, "/carbon-mgmt/factors", "排放因子库", "dark")
    const dimensions = await page.evaluate(() => ({ clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }))
    expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth)
  }
})
