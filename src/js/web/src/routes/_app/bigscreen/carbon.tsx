import { createFileRoute } from "@tanstack/react-router"

import { BigscreenCompareChart, BigscreenLineChart, BigscreenPieChart, BigscreenSankeyChart } from "@/components/bigscreen/charts"
import { BigscreenEmpty, BigscreenMetricCard, BigscreenPanel } from "@/components/bigscreen/panel"
import { useBigscreenCarbon } from "@/lib/bigscreen/hooks"

export const Route = createFileRoute("/_app/bigscreen/carbon")({
  component: BigscreenCarbonPage,
})

function BigscreenCarbonPage() {
  const carbonQuery = useBigscreenCarbon()
  const carbon = carbonQuery.data?.data

  return (
    <div className="bigscreen-grid-24">
      <BigscreenPanel title="碳排指标" eyebrow="Carbon" style={{ gridArea: "1 / 1 / 6 / 25" }}>
        <div className="grid h-full grid-cols-3 gap-3">
          {(carbon?.hero_metrics ?? []).map((metric, index) => (
            <BigscreenMetricCard key={metric.id} metric={metric} tone={index === 0 ? "emerald" : index === 1 ? "amber" : "cyan"} />
          ))}
        </div>
      </BigscreenPanel>

      <BigscreenPanel title="范围对比" eyebrow="Compare" style={{ gridArea: "6 / 1 / 16 / 9" }}>
        <BigscreenCompareChart items={carbon?.carbon_compare ?? []} height={265} />
      </BigscreenPanel>

      <BigscreenPanel title="贡献构成" eyebrow="Share" style={{ gridArea: "6 / 9 / 16 / 17" }}>
        <BigscreenPieChart items={carbon?.production_share ?? []} height={265} />
      </BigscreenPanel>

      <BigscreenPanel title="碳排预警" eyebrow="Alerts" style={{ gridArea: "6 / 17 / 16 / 25" }}>
        {carbon?.carbon_alerts?.length ? (
          <div className="bigscreen-scrollbar flex h-full flex-col gap-3 overflow-y-auto pr-1">
            {carbon.carbon_alerts.map((item) => (
              <div key={item.id} className="rounded-[16px] border border-white/8 bg-white/[0.03] p-4">
                <div className="text-sm font-semibold text-white">{item.title}</div>
                <div className="mt-2 text-xs leading-5 text-white/55">{item.detail}</div>
                <div className="mt-3 text-[11px] uppercase tracking-[0.18em] text-cyan-100/42">{item.occurred_at ?? "未记录时间"}</div>
              </div>
            ))}
          </div>
        ) : (
          <BigscreenEmpty label="暂无碳排预警" />
        )}
      </BigscreenPanel>

      <BigscreenPanel title={carbon?.carbon_flow.title ?? "范围级碳流"} eyebrow="Flow" style={{ gridArea: "16 / 1 / 25 / 15" }}>
        <BigscreenSankeyChart flow={carbon?.carbon_flow ?? { title: "范围级碳流", nodes: [], links: [] }} height={240} />
      </BigscreenPanel>

      <BigscreenPanel title="参考走势" eyebrow="Trend" style={{ gridArea: "16 / 15 / 25 / 25" }}>
        <BigscreenLineChart points={carbon?.carbon_price_trend ?? []} height={240} mode="single" />
      </BigscreenPanel>
    </div>
  )
}
