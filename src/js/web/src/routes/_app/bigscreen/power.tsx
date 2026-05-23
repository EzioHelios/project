import { createFileRoute } from "@tanstack/react-router"

import { BigscreenBarChart, BigscreenLineChart, BigscreenSankeyChart } from "@/components/bigscreen/charts"
import { EnergyAssetOverviewPanel } from "@/components/bigscreen/custom/EnergyAssetOverviewPanel"
import { TerminalStatusTriplet } from "@/components/bigscreen/custom/TerminalStatusTriplet"
import { BigscreenScrollBoard } from "@/components/bigscreen/motion"
import { BigscreenPanel } from "@/components/bigscreen/panel"
import { type BigscreenSceneAnchor, BigscreenSceneHost } from "@/components/bigscreen/scene"
import { useBigscreenPower } from "@/lib/bigscreen/hooks"

export const Route = createFileRoute("/_app/bigscreen/power")({
  component: BigscreenPowerPage,
})

function BigscreenPowerPage() {
  const powerQuery = useBigscreenPower()
  const power = powerQuery.data?.data

  const sceneAnchors: BigscreenSceneAnchor[] = [
    {
      id: "online",
      label: "Online Terminals",
      value: `${power?.hero_metrics?.[0]?.value ?? 0} 台`,
      position: "lt",
    },
    {
      id: "total",
      label: "Total Terminals",
      value: `${power?.hero_metrics?.[1]?.value ?? 0} 台`,
      position: "lb",
    },
    {
      id: "latest",
      label: "Latest Load",
      value: `${power?.hero_metrics?.[2]?.value?.toLocaleString("zh-CN", { maximumFractionDigits: 0 }) ?? "0"} ${power?.hero_metrics?.[2]?.unit ?? ""}`.trim(),
      position: "rt",
    },
    {
      id: "top-area",
      label: "Top Area",
      value: power?.energy_structure?.[0]?.name ?? "未分区",
      position: "rb",
    },
    {
      id: "top-meter",
      label: "Top Meter",
      value: power?.energy_ranking?.[0]?.name ?? "未命名电表",
      position: "ct",
    },
  ]

  const alertRows =
    power?.alerts?.map((item) => ({
      level: item.severity.toUpperCase(),
      title: item.title,
      time: item.occurred_at ? item.occurred_at.slice(5, 16).replace("T", " ") : "未记录",
    })) ?? []

  return (
    <div className="bigscreen-page">
      <div className="bigscreen-side-stack">
        <BigscreenPanel title="运行指标" frame="tall">
          <TerminalStatusTriplet
            items={[
              {
                id: "power-total",
                label: power?.hero_metrics?.[1]?.label ?? "终端总量",
                value: power?.hero_metrics?.[1]?.value ?? 0,
                unit: power?.hero_metrics?.[1]?.unit,
                kind: "total",
              },
              {
                id: "power-online",
                label: power?.hero_metrics?.[0]?.label ?? "在线终端",
                value: power?.hero_metrics?.[0]?.value ?? 0,
                unit: power?.hero_metrics?.[0]?.unit,
                kind: "online",
              },
            ]}
            family="power"
            summary={{
              label: power?.hero_metrics?.[2]?.label ?? "最新账期总电量",
              value: power?.hero_metrics?.[2]?.value ?? 0,
              unit: power?.hero_metrics?.[2]?.unit,
              detail: "电表总览摘要",
            }}
          />
        </BigscreenPanel>

        <BigscreenPanel title="用电预警滚动榜" frame="tall">
          <BigscreenScrollBoard
            rows={alertRows}
            headers={["级别", "事件", "时间"]}
            columns="0.8fr 2fr 1.1fr"
            visibleRows={5}
            emptyLabel="当前没有预警记录"
            getRowKey={(row) => `${row.title}-${row.time}`}
            renderRow={(row) => (
              <>
                <div className="text-[11px] uppercase tracking-[0.18em] text-amber-100/80">{row.level}</div>
                <div className="text-sm text-white/82">{row.title}</div>
                <div className="text-xs text-cyan-100/60">{row.time}</div>
              </>
            )}
          />
        </BigscreenPanel>
      </div>

      <div className="bigscreen-main-stack">
        <BigscreenSceneHost
          eyebrow="Power Scene"
          title="配电主视觉留白区"
          description="配电运行总览"
          anchors={sceneAnchors}
          showCore={false}
          showSafezone={false}
          className="bigscreen-scene-ghost"
        />

        <div className="bigscreen-bottom-grid" data-columns="3">
          <BigscreenPanel title="区域电量流图" frame="wide">
            <BigscreenSankeyChart flow={power?.energy_flow ?? { title: "区域用电流图", nodes: [], links: [] }} height={168} />
          </BigscreenPanel>

          <BigscreenPanel title="账期电量趋势" frame="wide">
            <BigscreenLineChart points={power?.energy_timeseries ?? []} height={168} mode="single" />
          </BigscreenPanel>

          <BigscreenPanel title="重点回路观察" frame="wide">
            <div className="bigscreen-stack">
              {power?.energy_ranking?.slice(0, 4).map((item, index) => (
                <div key={item.name} className="bigscreen-list-card flex items-center justify-between gap-3 px-4 py-3">
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.22em] text-white/44">Circuit {index + 1}</div>
                    <div className="mt-1 text-sm font-semibold text-white">{item.name}</div>
                  </div>
                  <div className="bigscreen-kpi-value text-[26px] text-amber-100">{item.value.toLocaleString("zh-CN", { maximumFractionDigits: 0 })}</div>
                </div>
              )) ?? <div className="text-sm text-white/42">暂无重点回路数据</div>}
            </div>
          </BigscreenPanel>
        </div>
      </div>

      <div className="bigscreen-side-stack">
        <BigscreenPanel title="用电结构" frame="tall">
          <EnergyAssetOverviewPanel
            kind="consumption"
            metrics={(power?.energy_structure ?? []).slice(0, 5).map((item, index) => ({
              label: index === 0 ? "重点区域用电" : item.name,
              value: item.value,
              unit: "kWh",
              tone: index === 1 ? "emerald" : index === 2 ? "amber" : "cyan",
            }))}
          />
        </BigscreenPanel>

        <BigscreenPanel title="用电排行" frame="tall">
          <BigscreenBarChart items={power?.energy_ranking ?? []} unit="kWh" height={220} />
        </BigscreenPanel>
      </div>
    </div>
  )
}
