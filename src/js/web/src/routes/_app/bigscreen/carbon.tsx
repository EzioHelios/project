import { createFileRoute } from "@tanstack/react-router"

import { BigscreenCompareChart, BigscreenLineChart, BigscreenPieChart, BigscreenSankeyChart } from "@/components/bigscreen/charts"
import { BigscreenScrollBoard } from "@/components/bigscreen/motion"
import { BigscreenInfoCard, BigscreenMetricCard, BigscreenPanel } from "@/components/bigscreen/panel"
import { type BigscreenSceneAnchor, BigscreenSceneHost } from "@/components/bigscreen/scene"
import { useBigscreenCarbon } from "@/lib/bigscreen/hooks"

export const Route = createFileRoute("/_app/bigscreen/carbon")({
  component: BigscreenCarbonPage,
})

function BigscreenCarbonPage() {
  const carbonQuery = useBigscreenCarbon()
  const carbon = carbonQuery.data?.data

  const sceneAnchors: BigscreenSceneAnchor[] = [
    {
      id: "scope1",
      label: "Scope 1",
      value: `${carbon?.carbon_compare?.[0]?.current?.toLocaleString("zh-CN", { maximumFractionDigits: 0 }) ?? "0"} kgCO2e`,
      position: "lt",
    },
    {
      id: "scope2",
      label: "Scope 2",
      value: `${carbon?.carbon_compare?.[1]?.current?.toLocaleString("zh-CN", { maximumFractionDigits: 0 }) ?? "0"} kgCO2e`,
      position: "ct",
    },
    {
      id: "scope3",
      label: "Scope 3",
      value: `${carbon?.carbon_compare?.[2]?.current?.toLocaleString("zh-CN", { maximumFractionDigits: 0 }) ?? "0"} kgCO2e`,
      position: "rt",
    },
    {
      id: "alerts",
      label: "Carbon Alerts",
      value: `${carbon?.carbon_alerts?.length ?? 0} 条`,
      position: "lb",
    },
    {
      id: "factors",
      label: "Factor Years",
      value: `${carbon?.hero_metrics?.[2]?.value ?? 0} 个`,
      position: "rb",
    },
  ]

  const alertRows =
    carbon?.carbon_alerts?.map((item) => ({
      title: item.title,
      detail: item.detail ?? "无补充说明",
      time: item.occurred_at ? item.occurred_at.slice(5, 16).replace("T", " ") : "未记录",
    })) ?? []

  return (
    <div className="bigscreen-page">
      <div className="bigscreen-side-stack">
        <BigscreenPanel title="碳排指标" eyebrow="Carbon Pulse">
          <div className="bigscreen-kpi-grid" data-columns="1">
            {(carbon?.hero_metrics ?? []).map((metric, index) => (
              <BigscreenMetricCard key={metric.id} metric={metric} tone={index === 0 ? "emerald" : index === 1 ? "amber" : "cyan"} compact />
            ))}
          </div>
        </BigscreenPanel>

        <BigscreenPanel title="范围对比" eyebrow="Scope Compare">
          <BigscreenCompareChart items={carbon?.carbon_compare ?? []} height={244} />
        </BigscreenPanel>
      </div>

      <div className="bigscreen-main-stack">
        <BigscreenSceneHost
          eyebrow="Carbon Scene"
          title="能碳协同主视觉区"
          description="能碳协同总览"
          anchors={sceneAnchors}
          showCore={false}
          showSafezone={false}
          className="bigscreen-scene-ghost"
        />

        <div className="bigscreen-bottom-grid" data-columns="3">
          <BigscreenPanel title={carbon?.carbon_flow.title ?? "范围级碳流"} eyebrow="Carbon Flow">
            <BigscreenSankeyChart flow={carbon?.carbon_flow ?? { title: "范围级碳流", nodes: [], links: [] }} height={168} />
          </BigscreenPanel>

          <BigscreenPanel title="碳价 / 因子走势" eyebrow="Reference Trend">
            <BigscreenLineChart points={carbon?.carbon_price_trend ?? []} height={168} mode="single" />
          </BigscreenPanel>

          <BigscreenPanel title="协同说明" eyebrow="Reading Notes">
            <div className="bigscreen-stack">
              {(carbon?.commentary?.length ? carbon.commentary : ["暂无协同说明"]).slice(0, 4).map((item, index) => (
                <BigscreenInfoCard key={item} label={`Insight ${index + 1}`} value={item} accent={index % 2 === 0 ? "cyan" : "amber"} />
              ))}
            </div>
          </BigscreenPanel>
        </div>
      </div>

      <div className="bigscreen-side-stack">
        <BigscreenPanel title="贡献构成" eyebrow="Contribution Share">
          <BigscreenPieChart items={carbon?.production_share ?? []} height={238} />
          <div className="mt-4 grid gap-2">
            {carbon?.production_share?.slice(0, 3).map((item, index) => (
              <BigscreenInfoCard
                key={item.name}
                label={`Share ${index + 1}`}
                value={item.name}
                accent={index === 0 ? "emerald" : index === 1 ? "cyan" : "amber"}
                detail={`${item.value.toLocaleString("zh-CN", { maximumFractionDigits: 0 })} kgCO2e`}
              />
            ))}
          </div>
        </BigscreenPanel>

        <BigscreenPanel title="碳排预警滚动榜" eyebrow="Alert Feed">
          <BigscreenScrollBoard
            rows={alertRows}
            headers={["事件", "补充说明", "时间"]}
            columns="1.2fr 1.8fr 1fr"
            visibleRows={5}
            emptyLabel="暂无碳排预警"
            getRowKey={(row) => `${row.title}-${row.time}`}
            renderRow={(row) => (
              <>
                <div className="text-sm font-medium text-white">{row.title}</div>
                <div className="text-xs text-white/58">{row.detail}</div>
                <div className="text-xs text-cyan-100/60">{row.time}</div>
              </>
            )}
          />
        </BigscreenPanel>
      </div>
    </div>
  )
}
