import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { MobileRouteScaffold, MobileWorkOrdersPane } from "@/components/mobile/mobile-energy-carbon-workbench"
import { readSearchParam, replaceMobileSearch } from "@/components/mobile/mobile-route-helpers"
import { MobileAppShell } from "@/components/mobile/mobile-shell"
import { useMobileEnergyCarbonData } from "@/hooks/mobile/use-mobile-energy-carbon"

export const Route = createFileRoute("/mobile/work-orders")({
  component: MobileWorkOrdersRoute,
})

function MobileWorkOrdersRoute() {
  const [selectedWorkOrderId, setSelectedWorkOrderId] = useState<string | null>(() => readSearchParam("workOrderId") || null)
  const data = useMobileEnergyCarbonData({ selectedWorkOrderId })

  return (
    <MobileAppShell activeSection="work-orders" teams={data.teams} currentTeam={data.currentTeam} onTeamSelect={data.setCurrentTeam}>
      <MobileRouteScaffold data={data}>
        <MobileWorkOrdersPane
          workOrders={data.workOrders}
          detail={data.workOrderDetail}
          selectedWorkOrderId={selectedWorkOrderId}
          onSelectWorkOrder={(workOrderId) => {
            setSelectedWorkOrderId(workOrderId)
            replaceMobileSearch({ workOrderId })
          }}
          onCloseDetail={() => {
            setSelectedWorkOrderId(null)
            replaceMobileSearch({ workOrderId: null })
          }}
          onAccept={data.acceptWorkOrder}
          onSubmit={data.submitWorkOrder}
          loading={data.isBusinessLoading}
          actionPending={data.isActionPending}
        />
      </MobileRouteScaffold>
    </MobileAppShell>
  )
}
