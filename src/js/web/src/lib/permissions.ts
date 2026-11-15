/** UI access follows the effective permissions returned by the authenticated API. */
export interface EffectiveAccess {
  permissions: string[]
  isSuperuser: boolean
}

export function hasPermission(access: EffectiveAccess | null, permission: string): boolean {
  return Boolean(access && (access.isSuperuser || access.permissions.includes(permission)))
}

const routePermissions: ReadonlyArray<readonly [string, string]> = [
  ["/auth/users", "auth.user.manage"],
  ["/auth/roles", "auth.role.manage"],
  ["/admin/users", "auth.user.manage"],
  ["/admin/roles", "auth.role.manage"],
  ["/admin/audit", "admin.audit.view"],
  ["/admin/teams", "admin.team.manage"],
  ["/admin", "auth.role.manage"],
  ["/teams", "admin.team.manage"],
  ["/tasks", "system.tasks.view"],
  ["/energy/consumption", "energy.consumption.view"],
  ["/energy/intensity", "energy.intensity.view"],
  ["/energy/analysis", "energy.analysis.view"],
  ["/energy/benchmark", "energy.benchmark.view"],
  ["/energy/flow", "energy.flow.view"],
  ["/energy/balance", "energy.balance.view"],
  ["/energy/budget", "energy.budget.view"],
  ["/data/energy-consumption", "energy.consumption.view"],
  ["/data/energy-types", "energy.consumption.view"],
  ["/data/energy-unit-conversions", "energy.consumption.view"],
  ["/data/energy-benchmark", "energy.benchmark.view"],
  ["/data/energy-budget", "energy.budget.view"],
  ["/carbon/organization", "carbon.inventory.view"],
  ["/carbon/product-footprint", "product_footprint.view"],
  ["/carbon/supply-chain", "carbon.inventory.view"],
  ["/carbon/verification", "carbon.verification.view"],
  ["/carbon/assets", "carbon.assets.view"],
  ["/carbon/climate", "carbon.climate.view"],
  ["/carbon/reduction", "carbon.reduction.view"],
  ["/carbon-mgmt/calculation-factors", "factor_library.view"],
  ["/carbon-mgmt/factors", "factor_library.view"],
  ["/carbon-mgmt/verification", "carbon.verification.view"],
  ["/carbon-mgmt", "carbon.inventory.view"],
  ["/data/company", "master_data.view"],
  ["/data/monitor-area", "master_data.view"],
  ["/data/terminals", "master_data.view"],
  ["/data/commute", "production.view"],
  ["/data/inbound", "production.view"],
  ["/data/outbound", "production.view"],
  ["/data/production-products", "production.view"],
  ["/data/production-output", "production.view"],
  ["/data/product-prices", "production.view"],
  ["/data/product-resource-bindings", "production.view"],
  ["/data/material-handling", "material_allocation.view"],
  ["/data/meter", "energy.consumption.view"],
  ["/data/point-monitoring", "iot.view"],
  ["/data/mqtt", "iot.view"],
  ["/data/api-key-mapping", "iot.view"],
  ["/data/video", "vision.view"],
  ["/data/alarm-rules", "monitor.view"],
  ["/data/energy-storage", "microgrid.view"],
  ["/bigscreen/vision", "vision.view"],
  ["/bigscreen", "bigscreen.view"],
  ["/microgrid", "microgrid.view"],
  ["/mobile", "monitor.view"],
  ["/energy-carbon/monitor", "monitor.view"],
  ["/energy-carbon/alerts", "monitor.view"],
]

export function canAccessPath(access: EffectiveAccess | null, rawPath: string): boolean {
  if (!access) return false
  const path = rawPath.split(/[?#]/, 1)[0].replace(/\/$/, "") || "/"
  if (access.isSuperuser || ["/home", "/profile", "/forbidden"].includes(path)) return true
  const match = routePermissions.find(([prefix]) => path === prefix || path.startsWith(`${prefix}/`))
  return Boolean(match && hasPermission(access, match[1]))
}

interface NavItem {
  title: string
  to: string
  items?: { title: string; to?: string; kind?: "link" | "section" }[]
}

export function filterNavigation<T extends NavItem>(items: T[], access: EffectiveAccess | null): T[] {
  return items.flatMap((item) => {
    if (!item.items) return canAccessPath(access, item.to) ? [item] : []
    const children: NonNullable<T["items"]> = []
    let section: NonNullable<T["items"]>[number] | undefined
    for (const child of item.items) {
      if (child.kind === "section") {
        section = child
        continue
      }
      if (!canAccessPath(access, child.to || item.to)) continue
      if (section) {
        children.push(section)
        section = undefined
      }
      children.push(child)
    }
    const first = children.find((child) => child.kind !== "section")
    if (!first) return []
    return [{ ...item, to: canAccessPath(access, item.to) ? item.to : first.to || item.to, items: children }]
  })
}
