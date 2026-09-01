import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { MobileEnergyPane, MobileRouteScaffold } from "@/components/mobile/mobile-energy-carbon-workbench"
import { readSearchParam, replaceMobileSearch } from "@/components/mobile/mobile-route-helpers"
import { MobileAppShell } from "@/components/mobile/mobile-shell"
import { type MobileEnergyFilters, useMobileEnergyCarbonData } from "@/hooks/mobile/use-mobile-energy-carbon"

export const Route = createFileRoute("/mobile/energy")({
  component: MobileEnergyRoute,
})

function MobileEnergyRoute() {
  const [filters, setFilters] = useState<MobileEnergyFilters>(() => ({
    period: readSearchParam("period", "month") === "day" ? "day" : "month",
    granularity: readSearchParam("granularity", "day") === "month" ? "month" : "day",
    groupBy: readSearchParam("groupBy", "equipment") === "area" ? "area" : "equipment",
    areaId: readSearchParam("areaId", "all") || "all",
  }))
  const data = useMobileEnergyCarbonData({ energy: filters })
  const tenantName = data.currentTeam?.name ?? "当前租户"
  const updateFilters = (next: MobileEnergyFilters) => {
    setFilters(next)
    replaceMobileSearch({
      period: next.period,
      granularity: next.granularity,
      groupBy: next.groupBy,
      areaId: next.areaId === "all" ? null : next.areaId,
    })
  }

  return (
    <MobileAppShell activeSection="energy" teams={data.teams} currentTeam={data.currentTeam} onTeamSelect={data.setCurrentTeam}>
      <MobileRouteScaffold data={data}>
        <MobileEnergyPane
          summary={data.energySummary}
          trend={data.energyTrend}
          ranking={data.energyRanking}
          alertSummary={data.summary}
          alertTrend={data.trend}
          areas={data.areas}
          tenantName={tenantName}
          filters={filters}
          onFiltersChange={updateFilters}
          loading={data.isBusinessLoading}
        />
      </MobileRouteScaffold>
    </MobileAppShell>
  )
}
