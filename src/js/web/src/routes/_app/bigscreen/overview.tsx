import { createFileRoute } from "@tanstack/react-router"

import { BigscreenBarChart, BigscreenLineChart, BigscreenSankeyChart } from "@/components/bigscreen/charts"
import { BigscreenEmpty, BigscreenMetricCard, BigscreenPanel } from "@/components/bigscreen/panel"
import { useBigscreenOverview } from "@/lib/bigscreen/hooks"

export const Route = createFileRoute("/_app/bigscreen/overview")({
  component: BigscreenOverviewPage,
})

function BigscreenOverviewPage() {
  const overviewQuery = useBigscreenOverview()
  const overview = overviewQuery.data?.data

  return (
    <div className="bigscreen-grid-24">
      <BigscreenPanel title="能源概览" eyebrow="Overview" style={{ gridArea: "1 / 1 / 7 / 13" }}>
        <div className="grid h-full grid-cols-3 gap-3">
          {(overview?.energy_kpis ?? []).map((metric, index) => (
            <BigscreenMetricCard key={metric.id} metric={metric} tone={index === 1 ? "amber" : "cyan"} />
          ))}
        </div>
      </BigscreenPanel>

      <BigscreenPanel title="碳排概览" eyebrow="Overview" style={{ gridArea: "1 / 13 / 7 / 21" }}>
        <div className="grid h-full grid-cols-3 gap-3">
          {(overview?.carbon_kpis ?? []).map((metric, index) => (
            <BigscreenMetricCard key={metric.id} metric={metric} tone={index === 0 ? "emerald" : "amber"} />
          ))}
        </div>
      </BigscreenPanel>

      <BigscreenPanel title="当前筛选视图" eyebrow="Filters" style={{ gridArea: "1 / 21 / 7 / 25" }}>
        <div className="flex h-full flex-col gap-3">
          <div>
            <div className="mb-2 text-[11px] uppercase tracking-[0.22em] text-white/48">账期</div>
            <div className="flex flex-wrap gap-2">
              {(overview?.filters?.months ?? []).slice(-4).map((item) => (
                <span key={item.value} className="rounded-full border border-white/8 bg-white/[0.04] px-3 py-1 text-xs text-white/65">
                  {item.label}
                </span>
              ))}
            </div>
          </div>
          <div>
            <div className="mb-2 text-[11px] uppercase tracking-[0.22em] text-white/48">区域</div>
            <div className="flex flex-wrap gap-2">
              {(overview?.filters?.areas ?? []).slice(0, 4).map((item) => (
                <span key={item.value} className="rounded-full border border-cyan-300/14 bg-cyan-300/8 px-3 py-1 text-xs text-cyan-100/70">
                  {item.label}
                </span>
              ))}
            </div>
          </div>
          {overview?.filters?.months?.length ? null : <BigscreenEmpty label="暂无筛选范围" />}
        </div>
      </BigscreenPanel>

      <BigscreenPanel title={overview?.energy_flow.title ?? "能源流向"} eyebrow="Flow" style={{ gridArea: "7 / 1 / 25 / 14" }}>
        <BigscreenSankeyChart flow={overview?.energy_flow ?? { title: "能源流向", nodes: [], links: [] }} height={540} />
      </BigscreenPanel>

      <BigscreenPanel title="账期趋势" eyebrow="Trend" style={{ gridArea: "7 / 14 / 19 / 25" }}>
        <BigscreenLineChart points={overview?.production_trend ?? []} height={330} />
      </BigscreenPanel>

      <BigscreenPanel title="账期能耗速览" eyebrow="Ranking" style={{ gridArea: "19 / 14 / 25 / 25" }}>
        <BigscreenBarChart
          items={(overview?.production_trend ?? []).slice(-6).map((point) => ({
            name: point.period,
            value: point.energy_kwh,
          }))}
          unit="kWh"
          height={180}
        />
      </BigscreenPanel>
    </div>
  )
}
