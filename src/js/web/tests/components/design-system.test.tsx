import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AdminPanel, MetricTile } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"

describe("admin component design variants", () => {
  it("exposes panel and metric variants to the global design layer", () => {
    render(
      <AdminPanel title="实时状态" emphasis="elevated" data-testid="panel">
        <MetricTile label="负荷" value="128" unit="kW" tone="domain" data-testid="metric" />
      </AdminPanel>,
    )

    expect(screen.getByTestId("panel")).toHaveAttribute("data-emphasis", "elevated")
    expect(screen.getByTestId("metric")).toHaveAttribute("data-tone", "domain")
  })

  it("keeps destructive actions on the destructive semantic token", () => {
    render(<Button variant="destructive">删除</Button>)
    expect(screen.getByRole("button", { name: "删除" })).toHaveClass("bg-destructive")
    expect(screen.getByRole("button", { name: "删除" })).not.toHaveClass("bg-primary")
  })
})
