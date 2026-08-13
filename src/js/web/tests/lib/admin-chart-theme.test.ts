import { describe, expect, it } from "vitest"

import { createSankeyChartOption, getAdminChartTheme } from "@/lib/admin-chart-theme"

describe("admin chart themes", () => {
  it.each([
    ["neutral", "light", "#3e6873", "#477763", "#071e2a"],
    ["energy", "light", "#007ea8", "#287962", "#071e2a"],
    ["carbon", "light", "#237b98", "#0a7d5e", "#071e2a"],
    ["neutral", "dark", "#77b8c4", "#75b89f", "#ecfafe"],
    ["energy", "dark", "#22d3ee", "#56c59d", "#ecfafe"],
    ["carbon", "dark", "#5cc6dd", "#34d399", "#ecfafe"],
  ] as const)("keeps the %s %s palette stable", (domain, mode, energy, carbon, text) => {
    const theme = getAdminChartTheme(domain, mode)
    expect({ domain: theme.domain, mode: theme.mode, energy: theme.palette.energy, carbon: theme.palette.carbon, text: theme.palette.text }).toEqual({
      domain,
      mode,
      energy,
      carbon,
      text,
    })
  })

  it("keeps operational statuses independent from the carbon domain", () => {
    const energy = getAdminChartTheme("energy", "light")
    const carbon = getAdminChartTheme("carbon", "light")

    expect(carbon.palette.success).toBe(energy.palette.success)
    expect(carbon.palette.warning).toBe(energy.palette.warning)
    expect(carbon.palette.danger).toBe(energy.palette.danger)
    expect(carbon.palette.success).not.toBe(carbon.palette.carbon)
  })

  it("keeps electrical and carbon signals visibly separated", () => {
    for (const mode of ["light", "dark"] as const) {
      const energy = getAdminChartTheme("energy", mode)
      const carbon = getAdminChartTheme("carbon", mode)

      expect(energy.palette.energy).not.toBe(carbon.palette.carbon)
      expect(energy.palette.electricity).not.toBe(carbon.palette.carbon)
      expect(carbon.palette.success).not.toBe(carbon.palette.carbon)
    }
  })

  it.each(["light", "dark"] as const)("reserves the blue-green-purple spectrum for flow diagrams in %s mode", (mode) => {
    const theme = getAdminChartTheme("energy", mode)

    expect(theme.flowColors).toHaveLength(7)
    expect(new Set(theme.flowColors).size).toBe(theme.flowColors.length)
    expect(theme.seriesColors).toContain(theme.palette.heat)
    expect(theme.seriesColors).toContain(theme.palette.cost)
    expect(theme.seriesColors).not.toEqual(theme.flowColors)
  })

  it("keeps warm business colors out of ordinary Sankey nodes while preserving danger semantics", () => {
    const theme = getAdminChartTheme("energy", "light")
    const option = createSankeyChartOption(
      theme,
      [
        { id: "source", name: "能源输入", category: "source" },
        { id: "use", name: "用能系统", category: "use_system" },
        { id: "conversion", name: "转换", category: "conversion" },
        { id: "loss", name: "损失", category: "loss" },
      ],
      [
        { source: "source", target: "use", value: 8 },
        { source: "source", target: "conversion", value: 4 },
        { source: "source", target: "loss", value: 1 },
      ],
    )
    const series = option?.series as Array<{ data?: Array<{ itemStyle?: { color?: string } }> }>
    const colors = series[0]?.data?.map((node) => node.itemStyle?.color)

    expect(colors).toEqual([theme.flowColors[0], theme.flowColors[1], theme.flowColors[2], theme.palette.danger])
    expect(colors).not.toContain(theme.palette.heat)
    expect(colors).not.toContain(theme.palette.cost)
  })
})
