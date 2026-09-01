import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { MobileAlertsPane, MobileRouteScaffold } from "@/components/mobile/mobile-energy-carbon-workbench"
import { readSearchParam, replaceMobileSearch } from "@/components/mobile/mobile-route-helpers"
import { MobileAppShell } from "@/components/mobile/mobile-shell"
import { useMobileEnergyCarbonData } from "@/hooks/mobile/use-mobile-energy-carbon"

export const Route = createFileRoute("/mobile/alerts")({
  component: MobileAlertsRoute,
})

function MobileAlertsRoute() {
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(() => readSearchParam("alertId") || null)
  const data = useMobileEnergyCarbonData({ selectedAlertId })

  return (
    <MobileAppShell activeSection="alerts" teams={data.teams} currentTeam={data.currentTeam} onTeamSelect={data.setCurrentTeam}>
      <MobileRouteScaffold data={data}>
        <MobileAlertsPane
          summary={data.summary}
          trend={data.trend}
          alerts={data.alerts}
          detail={data.alertDetail}
          selectedAlertId={selectedAlertId}
          onSelectAlert={(alertId) => {
            setSelectedAlertId(alertId)
            replaceMobileSearch({ alertId })
          }}
          onCloseDetail={() => {
            setSelectedAlertId(null)
            replaceMobileSearch({ alertId: null })
          }}
          onAcknowledge={data.acknowledgeAlert}
          onTransfer={data.transferAlertToWorkOrder}
          loading={data.isBusinessLoading}
          actionPending={data.isActionPending}
        />
      </MobileRouteScaffold>
    </MobileAppShell>
  )
}
