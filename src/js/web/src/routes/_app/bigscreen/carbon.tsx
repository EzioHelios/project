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
          description="中部预留给碳流主对象、范围热点或 3D 园区碳热点图层。当前通过范围锚点和说明摘要建立空间主叙事。"
          status="Carbon Flow Canvas Reserved"
          anchors={sceneAnchors}
          showCore={false}
          className="bigscreen-scene-ghost"
          overlay={
            <div className="flex h-full flex-col justify-between">
              <div className="ml-auto max-w-[280px] rounded-[18px] border border-white/10 bg-[#02101ca6] px-4 py-3 backdrop-blur-xl">
                <div className="text-[11px] uppercase tracking-[0.22em] text-cyan-100/52">Commentary</div>
                <div className="mt-2 grid gap-2 text-sm leading-6 text-white/62">
                  {(carbon?.commentary?.length ? carbon.commentary : ["当前暂无补充说明，大屏先保持结构完整。"]).slice(0, 3).map((item) => (
                    <div key={item} className="rounded-[14px] border border-white/8 bg-white/[0.03] px-3 py-2">
                      {item}
                    </div>
                  ))}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {(carbon?.production_share ?? []).slice(0, 3).map((item) => (
                  <span key={item.name} className="bigscreen-status-chip">
                    {item.name}
                  </span>
                ))}
              </div>
            </div>
          }
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
              {(carbon?.commentary?.length ? carbon.commentary : ["当前暂无协同说明，首版保持可读占位。"]).slice(0, 4).map((item, index) => (
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
