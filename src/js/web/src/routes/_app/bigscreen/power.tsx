import { createFileRoute } from "@tanstack/react-router"

import { BigscreenBarChart, BigscreenLineChart, BigscreenPieChart, BigscreenSankeyChart } from "@/components/bigscreen/charts"
import { BigscreenEmpty, BigscreenMetricCard, BigscreenPanel } from "@/components/bigscreen/panel"
import { useBigscreenPower } from "@/lib/bigscreen/hooks"

export const Route = createFileRoute("/_app/bigscreen/power")({
  component: BigscreenPowerPage,
})

function BigscreenPowerPage() {
  const powerQuery = useBigscreenPower()
  const power = powerQuery.data?.data

  return (
    <div className="bigscreen-grid-24">
      <BigscreenPanel title="运行指标" eyebrow="Power" style={{ gridArea: "1 / 1 / 6 / 25" }}>
        <div className="grid h-full grid-cols-3 gap-3">
          {(power?.hero_metrics ?? []).map((metric, index) => (
            <BigscreenMetricCard key={metric.id} metric={metric} tone={index === 0 ? "emerald" : index === 1 ? "cyan" : "amber"} />
          ))}
        </div>
      </BigscreenPanel>

      <BigscreenPanel title="用电预警" eyebrow="Alerts" style={{ gridArea: "6 / 1 / 17 / 8" }}>
        {power?.alerts?.length ? (
          <div className="bigscreen-scrollbar flex h-full flex-col gap-3 overflow-y-auto pr-1">
            {power.alerts.map((item) => (
              <div key={item.id} className="rounded-[16px] border border-white/8 bg-white/[0.03] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold text-white">{item.title}</div>
                  <span className="rounded-full border border-amber-300/18 bg-amber-300/10 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-amber-100/80">
                    {item.severity}
                  </span>
                </div>
                <div className="mt-2 text-xs leading-5 text-white/55">{item.detail}</div>
                <div className="mt-3 text-[11px] uppercase tracking-[0.18em] text-cyan-100/42">{item.occurred_at ?? "未记录时间"}</div>
              </div>
            ))}
          </div>
        ) : (
          <BigscreenEmpty label="当前没有预警记录" />
        )}
      </BigscreenPanel>

      <BigscreenPanel title="用电结构" eyebrow="Structure" style={{ gridArea: "6 / 8 / 17 / 16" }}>
        <BigscreenPieChart items={power?.energy_structure ?? []} height={300} />
      </BigscreenPanel>

      <BigscreenPanel title="用电排行" eyebrow="Ranking" style={{ gridArea: "6 / 16 / 17 / 25" }}>
        <BigscreenBarChart items={power?.energy_ranking ?? []} unit="kWh" height={300} />
      </BigscreenPanel>

      <BigscreenPanel title="电量流图" eyebrow="Flow" style={{ gridArea: "17 / 1 / 25 / 14" }}>
        <BigscreenSankeyChart flow={power?.energy_flow ?? { title: "区域用电流图", nodes: [], links: [] }} height={220} />
      </BigscreenPanel>

      <BigscreenPanel title="账期趋势" eyebrow="Timeseries" style={{ gridArea: "17 / 14 / 25 / 25" }}>
        <BigscreenLineChart points={power?.energy_timeseries ?? []} height={220} mode="single" />
      </BigscreenPanel>
    </div>
  )
}
