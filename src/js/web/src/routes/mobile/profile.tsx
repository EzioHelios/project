import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { MobileProfilePane, MobileRouteScaffold } from "@/components/mobile/mobile-energy-carbon-workbench"
import { readSearchParam, replaceMobileSearch } from "@/components/mobile/mobile-route-helpers"
import { MobileAppShell } from "@/components/mobile/mobile-shell"
import { useMobileEnergyCarbonData } from "@/hooks/mobile/use-mobile-energy-carbon"

type ProfilePanel = "overview" | "account" | "notifications" | "security" | "help"

export const Route = createFileRoute("/mobile/profile")({
  component: MobileProfileRoute,
})

function MobileProfileRoute() {
  const [panel, setPanel] = useState<ProfilePanel>(() => normalizePanel(readSearchParam("panel")))
  const data = useMobileEnergyCarbonData()
  const tenantName = data.currentTeam?.name ?? "当前租户"
  const updatePanel = (next: ProfilePanel) => {
    setPanel(next)
    replaceMobileSearch({ panel: next === "overview" ? null : next })
  }

  return (
    <MobileAppShell activeSection="profile" teams={data.teams} currentTeam={data.currentTeam} onTeamSelect={data.setCurrentTeam}>
      <MobileRouteScaffold data={data}>
        <MobileProfilePane summary={data.summary} tenantName={tenantName} user={data.currentUser} panel={panel} onPanelChange={updatePanel} />
      </MobileRouteScaffold>
    </MobileAppShell>
  )
}

function normalizePanel(value: string): ProfilePanel {
  if (value === "account" || value === "notifications" || value === "security" || value === "help") return value
  return "overview"
}
