import { createFileRoute } from "@tanstack/react-router"

import { BigscreenBarChart, BigscreenLineChart, BigscreenPieChart, BigscreenSankeyChart } from "@/components/bigscreen/charts"
import { BigscreenScrollBoard } from "@/components/bigscreen/motion"
import { BigscreenInfoCard, BigscreenMetricCard, BigscreenPanel } from "@/components/bigscreen/panel"
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
        <BigscreenPanel title="运行指标" eyebrow="Terminal Status">
          <div className="bigscreen-kpi-grid" data-columns="1">
            {(power?.hero_metrics ?? []).map((metric, index) => (
              <BigscreenMetricCard key={metric.id} metric={metric} tone={index === 0 ? "emerald" : index === 1 ? "cyan" : "amber"} compact />
            ))}
          </div>
        </BigscreenPanel>

        <BigscreenPanel title="用电预警滚动榜" eyebrow="Alert Feed">
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
          description="中部为配电路径、园区用电热区或 GIS 电力主对象预留。外围组件仅做运行解读，不再抢占主视觉。"
          status="Energy Flow Canvas Reserved"
          anchors={sceneAnchors}
          showCore={false}
          className="bigscreen-scene-ghost"
          overlay={
            <div className="flex h-full items-end justify-between">
              <div className="max-w-[280px] rounded-[18px] border border-white/10 bg-[#02101ca6] px-4 py-3 backdrop-blur-xl">
                <div className="text-[11px] uppercase tracking-[0.22em] text-cyan-100/52">运行判断</div>
                <div className="mt-2 text-sm leading-6 text-white/62">主视觉区改为纯留白，用于承接全屏电力底图和配电路径，不再用中心大卡片截断背景。</div>
              </div>
              <div className="flex flex-wrap justify-end gap-2">
                {power?.energy_structure?.slice(0, 3).map((item) => (
                  <span key={item.name} className="bigscreen-status-chip">
                    {item.name}
                  </span>
                ))}
              </div>
            </div>
          }
        />

        <div className="bigscreen-bottom-grid" data-columns="3">
          <BigscreenPanel title="区域电量流图" eyebrow="Flow Path">
            <BigscreenSankeyChart flow={power?.energy_flow ?? { title: "区域用电流图", nodes: [], links: [] }} height={168} />
          </BigscreenPanel>

          <BigscreenPanel title="账期电量趋势" eyebrow="Time Series">
            <BigscreenLineChart points={power?.energy_timeseries ?? []} height={168} mode="single" />
          </BigscreenPanel>

          <BigscreenPanel title="重点回路观察" eyebrow="Hot Feed">
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
        <BigscreenPanel title="用电结构" eyebrow="Load Structure">
          <BigscreenPieChart items={power?.energy_structure ?? []} height={238} />
          <div className="mt-4 grid gap-2">
            {power?.energy_structure?.slice(0, 3).map((item, index) => (
              <BigscreenInfoCard
                key={item.name}
                label={`Structure ${index + 1}`}
                value={item.name}
                accent={index === 0 ? "cyan" : index === 1 ? "emerald" : "amber"}
                detail={`${item.value.toLocaleString("zh-CN", { maximumFractionDigits: 0 })} kWh`}
              />
            ))}
          </div>
        </BigscreenPanel>

        <BigscreenPanel title="用电排行" eyebrow="Meter Ranking">
          <BigscreenBarChart items={power?.energy_ranking ?? []} unit="kWh" height={220} />
        </BigscreenPanel>
      </div>
    </div>
  )
}
