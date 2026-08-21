import { createFileRoute } from "@tanstack/react-router"
import { useMemo } from "react"

import { BigscreenBarChart, BigscreenLoadCompositeChart, BigscreenPieChart } from "@/components/bigscreen/charts"
import { CarbonStatsBoard } from "@/components/bigscreen/custom/CarbonStatsBoard"
import { ChargerSummaryPanel } from "@/components/bigscreen/custom/ChargerSummaryPanel"
import { EnergyAssetOverviewPanel } from "@/components/bigscreen/custom/EnergyAssetOverviewPanel"
import { LifestyleSectionPanel } from "@/components/bigscreen/custom/LifestyleSectionPanel"
import { LoadSummaryPanel } from "@/components/bigscreen/custom/LoadSummaryPanel"
import { ResourceConversionPanel } from "@/components/bigscreen/custom/ResourceConversionPanel"
import { StorageOverviewPanel } from "@/components/bigscreen/custom/StorageOverviewPanel"
import { TerminalStatusTriplet } from "@/components/bigscreen/custom/TerminalStatusTriplet"
import { BigscreenHorizontalPager, BigscreenVerticalTicker } from "@/components/bigscreen/motion"
import { BigscreenPanel } from "@/components/bigscreen/panel"
import { useHuayiBigscreenOverview } from "@/lib/bigscreen/hooks"
import type { BigscreenAlertItem } from "@/lib/bigscreen/types"

export const Route = createFileRoute("/_app/bigscreen/huayi")({
  component: HuayiBigscreenPage,
})

function AlertRows({ alerts }: { alerts: BigscreenAlertItem[] }) {
  const topAlerts = useMemo(() => alerts.slice(0, 10), [alerts])

  return (
    <BigscreenVerticalTicker
      items={topAlerts}
      className="bigscreen-huayi-alert-list"
      visibleItems={4}
      itemHeight={42}
      intervalMs={2600}
      emptyLabel="当前没有告警记录"
      getItemKey={(alert) => alert.id}
      renderItem={(alert) => (
        <div key={alert.id} className="bigscreen-huayi-alert-row">
          <div className="bigscreen-huayi-alert-time">{alert.occurred_at ?? "--:--"}</div>
          <div className="bigscreen-huayi-alert-title">{alert.title}</div>
        </div>
      )}
    />
  )
}

function HuayiBigscreenPage() {
  const overviewQuery = useHuayiBigscreenOverview()
  const overview = overviewQuery.data?.data
  const loadStructure = useMemo(
    () =>
      (overview?.load_groups ?? [])
        .map((group) => ({
          name: group.title,
          value: typeof group.metrics[1]?.value === "number" ? group.metrics[1].value : Number(group.metrics[1]?.value ?? 0),
        }))
        .filter((item) => Number.isFinite(item.value) && item.value > 0),
    [overview?.load_groups],
  )
  const areaRanking = useMemo(() => [...(overview?.area_distribution ?? [])].sort((left, right) => right.value - left.value), [overview?.area_distribution])
  const lifestylePages = overview?.lifestyle_sections ?? []

  return (
    <div className="bigscreen-page bigscreen-huayi-page">
      <div className="grid h-full min-h-0 grid-rows-[1.18fr_0.82fr_0.86fr_0.54fr] gap-[var(--bigscreen-huayi-panel-gap,var(--panel-gap))]">
        <BigscreenPanel title="光伏发电" frame="tall">
          <EnergyAssetOverviewPanel kind="generation" metrics={overview?.photovoltaic_metrics ?? []} variant="dense" />
        </BigscreenPanel>

        <BigscreenPanel title="充电桩" frame="tall">
          <ChargerSummaryPanel metrics={overview?.charger_metrics ?? []} variant="dense" />
        </BigscreenPanel>

        <BigscreenPanel title="储能系统" frame="tall">
          <StorageOverviewPanel metric={overview?.storage_status} variant="dense" />
        </BigscreenPanel>

        <BigscreenPanel title="最近告警" frame="tall">
          <AlertRows alerts={overview?.alerts ?? []} />
        </BigscreenPanel>
      </div>

      <div className="grid h-full min-h-0 grid-rows-[1.28fr_0.98fr_0.78fr] gap-[var(--bigscreen-huayi-panel-gap,var(--panel-gap))]">
        <BigscreenPanel title="全区负荷" frame="wide">
          <div className="grid h-full grid-cols-[minmax(0,0.94fr)_minmax(0,1.06fr)] gap-[var(--bigscreen-huayi-panel-gap,var(--panel-gap))]">
            <LoadSummaryPanel groups={overview?.load_groups ?? []} variant="dense" />
            <div className="grid h-full grid-rows-[1.08fr_0.92fr] gap-[var(--bigscreen-huayi-panel-gap,var(--panel-gap))]">
              <BigscreenLoadCompositeChart points={overview?.carbon_trend ?? []} height={118} />
              <div className="grid h-full grid-cols-2 gap-[var(--bigscreen-huayi-panel-gap,var(--panel-gap))]">
                <BigscreenPieChart items={loadStructure} height={118} />
                <BigscreenBarChart items={areaRanking} unit="度" height={118} />
              </div>
            </div>
          </div>
        </BigscreenPanel>

        <BigscreenPanel title="环保数据" frame="wide">
          <div className="grid h-full grid-cols-2 gap-[var(--bigscreen-huayi-panel-gap,var(--panel-gap))]">
            {(overview?.resource_cards ?? []).map((group) => (
              <ResourceConversionPanel key={group.id} group={group} variant="dense" />
            ))}
          </div>
        </BigscreenPanel>

        <BigscreenPanel title="设备状态" frame="wide">
          <TerminalStatusTriplet
            className="h-full"
            items={[
              {
                id: "huayi-device-total",
                label: overview?.device_status?.[0]?.label ?? "总设备",
                value: typeof overview?.device_status?.[0]?.value === "number" ? overview.device_status[0].value : 0,
                unit: overview?.device_status?.[0]?.unit,
                kind: "total",
              },
              {
                id: "huayi-device-online",
                label: overview?.device_status?.[1]?.label ?? "在线",
                value: typeof overview?.device_status?.[1]?.value === "number" ? overview.device_status[1].value : 0,
                unit: overview?.device_status?.[1]?.unit,
                kind: "online",
              },
              {
                id: "huayi-device-alert",
                label: overview?.device_status?.[3]?.label ?? "告警",
                value: typeof overview?.device_status?.[3]?.value === "number" ? overview.device_status[3].value : 0,
                unit: overview?.device_status?.[3]?.unit,
                kind: "fault",
              },
              {
                id: "huayi-device-offline",
                label: overview?.device_status?.[2]?.label ?? "离线",
                value: typeof overview?.device_status?.[2]?.value === "number" ? overview.device_status[2].value : 0,
                unit: overview?.device_status?.[2]?.unit,
                kind: "offline",
              },
            ]}
            family="power"
            variant="dense"
          />
        </BigscreenPanel>
      </div>

      <div className="grid h-full min-h-0 grid-rows-[0.72fr_0.44fr_0.84fr] gap-[var(--bigscreen-huayi-panel-gap,var(--panel-gap))]">
        <BigscreenPanel title="碳排放统计" frame="tall">
          <CarbonStatsBoard metrics={overview?.carbon_stats ?? []} variant="dense" highlightMode="rotate" />
        </BigscreenPanel>

        <BigscreenPanel title="碳普惠" frame="tall">
          <CarbonStatsBoard metrics={overview?.benefit_items ?? []} variant="minimal" highlightMode="rotate" />
        </BigscreenPanel>

        <BigscreenPanel title="零碳生活" frame="tall">
          <BigscreenHorizontalPager
            items={lifestylePages}
            emptyLabel="暂无零碳生活数据"
            intervalMs={5200}
            getItemKey={(section) => section.id}
            renderPage={(section) => <LifestyleSectionPanel section={section} highlight={section.id === "green-traffic"} variant="rotating" className="h-full" />}
          />
        </BigscreenPanel>
      </div>
    </div>
  )
}
