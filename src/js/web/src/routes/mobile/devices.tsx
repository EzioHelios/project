import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { MobileDevicesPane, MobileRouteScaffold } from "@/components/mobile/mobile-energy-carbon-workbench"
import { readNumberSearchParam, replaceMobileSearch } from "@/components/mobile/mobile-route-helpers"
import { MobileAppShell } from "@/components/mobile/mobile-shell"
import { useMobileEnergyCarbonData } from "@/hooks/mobile/use-mobile-energy-carbon"

export const Route = createFileRoute("/mobile/devices")({
  component: MobileDevicesRoute,
})

function MobileDevicesRoute() {
  const [selectedDeviceId, setSelectedDeviceId] = useState<number | null>(() => readNumberSearchParam("deviceId"))
  const data = useMobileEnergyCarbonData({ selectedDeviceId })
  const tenantName = data.currentTeam?.name ?? "当前租户"

  return (
    <MobileAppShell activeSection="devices" teams={data.teams} currentTeam={data.currentTeam} onTeamSelect={data.setCurrentTeam}>
      <MobileRouteScaffold data={data}>
        <MobileDevicesPane
          devices={data.devices}
          areas={data.areas}
          detail={data.deviceDetail}
          timeseries={data.deviceTimeseries}
          videos={data.deviceVideos}
          selectedDeviceId={selectedDeviceId}
          onSelectDevice={(deviceId) => {
            setSelectedDeviceId(deviceId)
            replaceMobileSearch({ deviceId })
          }}
          onCloseDetail={() => {
            setSelectedDeviceId(null)
            replaceMobileSearch({ deviceId: null })
          }}
          tenantName={tenantName}
          loading={data.isBusinessLoading}
        />
      </MobileRouteScaffold>
    </MobileAppShell>
  )
}
