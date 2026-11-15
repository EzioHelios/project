import { describe, expect, it } from "vitest"
import { canAccessPath, type EffectiveAccess, filterNavigation } from "@/lib/permissions"

const access: EffectiveAccess = {
  isSuperuser: false,
  permissions: [
    ...["consumption", "intensity", "analysis", "benchmark", "flow", "balance", "budget"].map((name) => `energy.${name}.view`),
    "carbon.inventory.view",
    "product_footprint.view",
    "carbon.verification.view",
    "carbon.assets.view",
    "bigscreen.view",
  ],
}

describe("effective role navigation", () => {
  it("opens the twelve core functions", () => {
    for (const path of [
      ...["consumption", "intensity", "analysis", "benchmark", "flow", "balance", "budget"].map((name) => `/energy/${name}`),
      "/carbon/organization/records",
      "/carbon/product-footprint",
      "/carbon/supply-chain",
      "/carbon/verification",
      "/carbon/assets/overview",
    ])
      expect(canAccessPath(access, `${path}?year=2026`)).toBe(true)
  })
  it("opens standard bigscreens without opening video recognition", () => {
    expect(canAccessPath(access, "/bigscreen/overview")).toBe(true)
    expect(canAccessPath(access, "/bigscreen/vision")).toBe(false)
  })
  it("rejects excluded paths and unknown paths", () => {
    for (const path of [
      "/auth/users",
      "/admin/roles",
      "/teams",
      "/microgrid/overview",
      "/bigscreen/vision",
      "/mobile/energy",
      "/carbon/climate",
      "/tasks/schedules",
      "/new-unknown-module",
    ]) {
      expect(canAccessPath(access, path)).toBe(false)
    }
    expect(canAccessPath(null, "/home")).toBe(false)
  })
  it("does not leak empty groups or section headings", () => {
    expect(
      filterNavigation(
        [
          { title: "System", to: "/admin", items: [{ title: "Users", to: "/auth/users" }] },
          {
            title: "Carbon",
            to: "/carbon/climate",
            items: [
              { title: "Private", kind: "section" },
              { title: "Climate", to: "/carbon/climate" },
              { title: "Accounting", kind: "section" },
              { title: "Records", to: "/carbon/organization/records" },
            ],
          },
        ],
        access,
      ),
    ).toEqual([
      {
        title: "Carbon",
        to: "/carbon/organization/records",
        items: [
          { title: "Accounting", kind: "section" },
          { title: "Records", to: "/carbon/organization/records" },
        ],
      },
    ])
  })
})
