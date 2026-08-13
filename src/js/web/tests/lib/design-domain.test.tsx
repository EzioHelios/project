import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AdminDomainScope, resolveAdminDomain } from "@/lib/design-domain"

describe("resolveAdminDomain", () => {
  it.each([
    ["/energy/consumption", "energy"],
    ["/energy/intensity", "energy"],
    ["/microgrid/overview", "energy"],
    ["/energy-carbon/monitor", "energy"],
    ["/data/point-monitoring", "energy"],
    ["/carbon/accounting", "carbon"],
    ["/carbon-mgmt/scope2-bill", "carbon"],
    ["/energy-carbon/factors", "carbon"],
    ["/energy-carbon/carbon", "carbon"],
    ["/energy-carbon/quality", "carbon"],
    ["/energy/budget", "carbon"],
    ["/home", "neutral"],
    ["/data/equipment", "neutral"],
    ["/admin/users", "neutral"],
    ["/teams", "neutral"],
  ] as const)("maps %s to %s", (pathname, domain) => {
    expect(resolveAdminDomain(pathname)).toBe(domain)
  })

  it("gives the carbon budget exception priority over the energy prefix", () => {
    expect(resolveAdminDomain("/energy/budget/detail")).toBe("carbon")
  })
})

describe("AdminDomainScope", () => {
  it("supports nested domain overrides without changing its parent", () => {
    render(
      <AdminDomainScope domain="neutral" data-testid="neutral">
        <AdminDomainScope domain="energy" data-testid="energy">
          <AdminDomainScope domain="carbon" data-testid="carbon" />
        </AdminDomainScope>
      </AdminDomainScope>,
    )

    expect(screen.getByTestId("neutral")).toHaveAttribute("data-design-domain", "neutral")
    expect(screen.getByTestId("energy")).toHaveAttribute("data-design-domain", "energy")
    expect(screen.getByTestId("carbon")).toHaveAttribute("data-design-domain", "carbon")
    expect(screen.getByTestId("carbon").parentElement).toBe(screen.getByTestId("energy"))
  })
})
