import { createFileRoute } from "@tanstack/react-router"

import { BigscreenBarChart, BigscreenLineChart, BigscreenSankeyChart } from "@/components/bigscreen/charts"
import { BigscreenScrollBoard } from "@/components/bigscreen/motion"
import { BigscreenInfoCard, BigscreenMetricCard, BigscreenPanel } from "@/components/bigscreen/panel"
import { type BigscreenSceneAnchor, BigscreenSceneHost } from "@/components/bigscreen/scene"
import { useBigscreenOverview } from "@/lib/bigscreen/hooks"

export const Route = createFileRoute("/_app/bigscreen/overview")({
  component: BigscreenOverviewPage,
})

function BigscreenOverviewPage() {
  const overviewQuery = useBigscreenOverview()
  const overview = overviewQuery.data?.data

  const sceneAnchors: BigscreenSceneAnchor[] = [
    {
      id: "month",
      label: "Latest Window",
      value: overview?.filters?.months?.slice(-1)[0]?.label ?? "未标注账期",
      position: "ct",
    },
    {
      id: "energy",
      label: "Energy Focus",
      value: `${overview?.energy_kpis?.[0]?.value?.toLocaleString("zh-CN", { maximumFractionDigits: 0 }) ?? "0"} ${overview?.energy_kpis?.[0]?.unit ?? ""}`.trim(),
      position: "lt",
    },
    {
      id: "carbon",
      label: "Carbon Focus",
      value: `${overview?.carbon_kpis?.[0]?.value?.toLocaleString("zh-CN", { maximumFractionDigits: 0 }) ?? "0"} ${overview?.carbon_kpis?.[0]?.unit ?? ""}`.trim(),
      position: "rt",
    },
    {
      id: "areas",
      label: "Online Areas",
      value: `${overview?.carbon_kpis?.[2]?.value ?? 0} 个`,
      position: "lb",
    },
    {
      id: "meters",
      label: "Active Meters",
      value: `${overview?.energy_kpis?.[2]?.value ?? 0} 台`,
      position: "rb",
    },
  ]

  const flowRanking = overview?.energy_flow?.nodes?.filter((node) => node.category === "area").map((node) => ({ name: node.name, value: node.value ?? 0 })) ?? []

  const trendRows =
    overview?.production_trend
      ?.slice(-8)
      .reverse()
      .map((point) => ({
        period: point.period,
        energy: point.energy_kwh.toLocaleString("zh-CN", { maximumFractionDigits: 0 }),
        carbon: point.carbon_co2e.toLocaleString("zh-CN", { maximumFractionDigits: 0 }),
      })) ?? []

  return (
    <div className="bigscreen-page">
      <div className="bigscreen-side-stack">
        <BigscreenPanel title="能耗主指标" eyebrow="Energy Cluster">
          <div className="bigscreen-kpi-grid" data-columns="1">
            {(overview?.energy_kpis ?? []).map((metric, index) => (
              <BigscreenMetricCard key={metric.id} metric={metric} tone={index === 1 ? "amber" : "cyan"} compact />
            ))}
          </div>
        </BigscreenPanel>

        <BigscreenPanel title="碳排主指标" eyebrow="Carbon Cluster">
          <div className="bigscreen-kpi-grid" data-columns="1">
            {(overview?.carbon_kpis ?? []).map((metric, index) => (
              <BigscreenMetricCard key={metric.id} metric={metric} tone={index === 0 ? "emerald" : "amber"} compact />
            ))}
          </div>
        </BigscreenPanel>
      </div>

      <div className="bigscreen-main-stack">
        <BigscreenSceneHost
          eyebrow="Overview Scene"
          title="园区经营总览主视觉区"
          description="中部保留给 GIS、Cesium 或 Three.js 主对象。当前用主视觉安全区占位，并把关键状态锚点挂在四周。"
          status="Main Visual Safe Zone Reserved"
          anchors={sceneAnchors}
          showCore={false}
          showSafezone
          className="bigscreen-scene-ghost"
          overlay={
            <div className="flex h-full flex-col justify-between">
              <div className="flex items-start justify-between gap-5">
                <div className="max-w-[300px] rounded-[22px] border border-cyan-300/14 bg-[#03121ba6] px-5 py-4 shadow-[0_18px_36px_rgba(0,0,0,0.2)] backdrop-blur-xl">
                  <div className="text-[11px] uppercase tracking-[0.28em] text-cyan-100/54">Overview Scene</div>
                  <div className="bigscreen-title mt-3 text-[24px] text-white">寺巷街道仓储园区块体演示</div>
                  <div className="mt-3 text-[13px] leading-6 text-white/56">主体底图现在退到整张大屏下层，中心只保留仓储演示留白和关键锚点。</div>
                  <div className="mt-4 inline-flex rounded-full border border-cyan-300/18 bg-cyan-300/10 px-4 py-2 text-[11px] uppercase tracking-[0.22em] text-cyan-100/74">
                    MapLibre / WGS84 / Fill Extrusion
                  </div>
                </div>
                <div className="flex max-w-[420px] flex-wrap justify-end gap-2">
                  <span className="bigscreen-status-chip">Center 32.421059, 119.890793</span>
                  {(overview?.filters?.months ?? []).slice(-4).map((item) => (
                    <span key={item.value} className="bigscreen-status-chip">
                      {item.label}
                    </span>
                  ))}
                </div>
              </div>
              <div className="ml-auto max-w-[260px] rounded-[18px] border border-white/10 bg-[#02101ca6] px-4 py-3 backdrop-blur-xl">
                <div className="text-[11px] uppercase tracking-[0.22em] text-cyan-100/52">Screen Intent</div>
                <div className="mt-2 text-sm leading-6 text-white/62">中间不再放实体主卡，底图持续贯穿全屏。后续换底图源或引擎时，只改背景层和适配层。</div>
              </div>
            </div>
          }
        />

        <div className="bigscreen-bottom-grid" data-columns="3">
          <BigscreenPanel title={overview?.energy_flow.title ?? "购电流向"} eyebrow="Flow Map">
            <BigscreenSankeyChart flow={overview?.energy_flow ?? { title: "购电流向", nodes: [], links: [] }} height={168} />
          </BigscreenPanel>

          <BigscreenPanel title="月度经营趋势" eyebrow="Trend Pulse">
            <BigscreenLineChart points={overview?.production_trend ?? []} height={168} />
          </BigscreenPanel>

          <BigscreenPanel title="账期观察窗" eyebrow="Trend Feed">
            <BigscreenScrollBoard
              rows={trendRows}
              headers={["账期", "能耗", "碳排"]}
              columns="1.1fr 1fr 1fr"
              visibleRows={4}
              emptyLabel="暂无账期趋势"
              getRowKey={(row) => row.period}
              renderRow={(row) => (
                <>
                  <div className="font-medium text-white">{row.period}</div>
                  <div className="text-cyan-100/72">{row.energy}</div>
                  <div className="text-amber-100/72">{row.carbon}</div>
                </>
              )}
            />
          </BigscreenPanel>
        </div>
      </div>

      <div className="bigscreen-side-stack">
        <BigscreenPanel title="当前视图摘要" eyebrow="View Scope">
          <div className="bigscreen-stack">
            <BigscreenInfoCard
              label="默认账期范围"
              value={(overview?.filters?.months ?? []).slice(-1)[0]?.label ?? "未配置"}
              detail="顶部与中央锚点同步使用账期摘要，避免大屏上再放重型筛选器。"
            />
            <div className="bigscreen-stack">
              <div className="text-[11px] uppercase tracking-[0.22em] text-cyan-100/52">关注区域</div>
              <div className="flex flex-wrap gap-2">
                {(overview?.filters?.areas ?? []).slice(0, 6).map((item, index) => (
                  <span
                    key={item.value}
                    className={
                      index < 3
                        ? "rounded-full border border-cyan-300/18 bg-cyan-300/8 px-3 py-2 text-xs text-cyan-100/76"
                        : "rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-white/66"
                    }
                  >
                    {item.label}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </BigscreenPanel>

        <BigscreenPanel title="区域能耗速览" eyebrow="Area Ranking">
          <BigscreenBarChart items={flowRanking.slice(0, 6)} unit="kWh" height={232} />
          <div className="mt-4 grid gap-2">
            {flowRanking.slice(0, 3).map((item, index) => (
              <div key={item.name} className="bigscreen-list-card flex items-center justify-between gap-3 px-4 py-3">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.22em] text-white/46">Top {index + 1}</div>
                  <div className="mt-1 text-sm font-semibold text-white">{item.name}</div>
                </div>
                <div className="bigscreen-kpi-value text-[28px] text-cyan-100">{item.value.toLocaleString("zh-CN", { maximumFractionDigits: 0 })}</div>
              </div>
            ))}
          </div>
        </BigscreenPanel>
      </div>
    </div>
  )
}
