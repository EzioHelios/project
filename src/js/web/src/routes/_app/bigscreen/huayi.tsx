import { createFileRoute } from "@tanstack/react-router"

import { BigscreenBarChart, BigscreenLineChart } from "@/components/bigscreen/charts"
import { EnergyAssetOverviewPanel } from "@/components/bigscreen/custom/EnergyAssetOverviewPanel"
import { StorageOverviewPanel } from "@/components/bigscreen/custom/StorageOverviewPanel"
import { TerminalStatusTriplet } from "@/components/bigscreen/custom/TerminalStatusTriplet"
import { BigscreenMetricCard, BigscreenPanel } from "@/components/bigscreen/panel"
import { useHuayiBigscreenOverview } from "@/lib/bigscreen/hooks"
import type { BigscreenAlertItem, HuayiBigscreenKeyValue, HuayiBigscreenMetricGroup } from "@/lib/bigscreen/types"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_app/bigscreen/huayi")({
  component: HuayiBigscreenPage,
})

function normalizeTone(tone?: string): "cyan" | "amber" | "emerald" {
  if (tone === "amber" || tone === "emerald") return tone
  return "cyan"
}

function formatValue(value: number | string) {
  if (typeof value === "number") {
    return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })
  }
  return value
}

function MetricGrid({ items, columns }: { items: HuayiBigscreenKeyValue[]; columns: 2 | 3 }) {
  return (
    <div className="bigscreen-kpi-grid" data-columns={columns === 3 ? "3" : "2"}>
      {items.map((item) => (
        <BigscreenMetricCard
          key={item.label}
          metric={{
            label: item.label,
            value: typeof item.value === "number" ? item.value : 0,
            unit: item.unit,
            ratio: null,
          }}
          tone={normalizeTone(item.tone)}
          compact
        />
      ))}
    </div>
  )
}

function LoadGroup({ group }: { group: HuayiBigscreenMetricGroup }) {
  return (
    <div className="bigscreen-list-card flex flex-col gap-3 px-4 py-4">
      <div className="text-sm font-semibold text-white">{group.title}</div>
      <div className="grid grid-cols-2 gap-3">
        {group.metrics.map((metric) => (
          <div key={metric.label} className="rounded-[14px] border border-cyan-300/10 bg-slate-950/35 px-3 py-3">
            <div className="text-[11px] uppercase tracking-[0.22em] text-white/45">{metric.label}</div>
            <div
              className={cn(
                "mt-2 font-['Rajdhani'] text-[28px] font-semibold",
                metric.tone === "amber" ? "text-amber-200" : metric.tone === "emerald" ? "text-emerald-200" : "text-cyan-100",
              )}
            >
              {formatValue(metric.value)}
              {metric.unit ? <span className="ml-1 text-xs text-white/55">{metric.unit}</span> : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function KeyValueList({ items, highlightFirst = false }: { items: HuayiBigscreenKeyValue[]; highlightFirst?: boolean }) {
  return (
    <div className="grid gap-2">
      {items.map((item, index) => (
        <div
          key={`${item.label}-${index}`}
          className={cn(
            "flex items-center justify-between gap-3 rounded-[14px] border px-4 py-3",
            highlightFirst && index === 0 ? "border-emerald-300/20 bg-emerald-500/10" : "border-cyan-300/10 bg-slate-950/30",
          )}
        >
          <div className="text-sm text-cyan-50/85">{item.label}</div>
          <div
            className={cn(
              "font-['Rajdhani'] text-[30px] font-semibold leading-none",
              item.tone === "amber" ? "text-amber-200" : item.tone === "emerald" ? "text-emerald-200" : "text-cyan-100",
            )}
          >
            {formatValue(item.value)}
            {item.unit ? <span className="ml-1 text-xs text-white/55">{item.unit}</span> : null}
          </div>
        </div>
      ))}
    </div>
  )
}

function ResourceCard({ group }: { group: HuayiBigscreenMetricGroup }) {
  return (
    <div className="bigscreen-list-card flex h-full flex-col gap-3 px-4 py-4">
      <div className="text-center text-sm font-semibold text-cyan-100">{group.title}</div>
      <div className="grid flex-1 grid-cols-2 gap-3">
        {group.metrics.map((metric) => (
          <div key={metric.label} className="rounded-[14px] border border-cyan-300/10 bg-slate-950/35 px-3 py-3 text-center">
            <div className="text-[11px] uppercase tracking-[0.22em] text-white/45">{metric.label}</div>
            <div
              className={cn(
                "mt-2 font-['Rajdhani'] text-[24px] font-semibold",
                metric.tone === "amber" ? "text-amber-200" : metric.tone === "emerald" ? "text-emerald-200" : "text-cyan-100",
              )}
            >
              {formatValue(metric.value)}
              {metric.unit ? <span className="ml-1 text-xs text-white/55">{metric.unit}</span> : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function AlertRows({ alerts }: { alerts: BigscreenAlertItem[] }) {
  return (
    <div className="grid gap-2">
      {alerts.map((alert) => (
        <div key={alert.id} className="flex items-center gap-4 rounded-[14px] border border-amber-300/14 bg-slate-950/30 px-4 py-3">
          <div className="font-['Rajdhani'] text-lg font-semibold text-amber-200">{alert.occurred_at ?? "--:--"}</div>
          <div className="text-sm text-white">{alert.title}</div>
        </div>
      ))}
    </div>
  )
}

function HuayiBigscreenPage() {
  const overviewQuery = useHuayiBigscreenOverview()
  const overview = overviewQuery.data?.data

  return (
    <div className="bigscreen-page">
      <div className="grid h-full min-h-0 grid-rows-[0.95fr_0.5fr_1.4fr_0.55fr] gap-[var(--panel-gap)]">
        <BigscreenPanel title="光伏发电" frame="tall">
          <EnergyAssetOverviewPanel kind="generation" metrics={overview?.photovoltaic_metrics ?? []} />
        </BigscreenPanel>

        <BigscreenPanel title="充电桩" frame="tall">
          <MetricGrid items={overview?.charger_metrics ?? []} columns={3} />
        </BigscreenPanel>

        <BigscreenPanel title="全区负荷" frame="tall">
          <div className="grid h-full grid-rows-[auto_1fr] gap-4">
            <div className="grid gap-3">
              {(overview?.load_groups ?? []).map((group) => (
                <LoadGroup key={group.id} group={group} />
              ))}
            </div>
            <BigscreenBarChart items={overview?.area_distribution ?? []} unit="度" height={150} />
          </div>
        </BigscreenPanel>

        <BigscreenPanel title="储能系统" frame="tall">
          <StorageOverviewPanel metric={overview?.storage_status} />
        </BigscreenPanel>
      </div>

      <div className="grid h-full min-h-0 grid-rows-[1.05fr_0.8fr_0.5fr_0.55fr] gap-[var(--panel-gap)]">
        <BigscreenPanel title="碳排放统计" frame="wide">
          <div className="grid h-full grid-rows-[auto_180px] gap-4">
            <KeyValueList items={overview?.carbon_stats ?? []} />
            <BigscreenLineChart points={overview?.carbon_trend ?? []} height={180} mode="single" />
          </div>
        </BigscreenPanel>

        <BigscreenPanel title="环保数据" frame="wide">
          <div className="grid h-full grid-cols-2 gap-4">
            {(overview?.resource_cards ?? []).map((group) => (
              <ResourceCard key={group.id} group={group} />
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
            ]}
            family="power"
            summary={{
              label: overview?.device_status?.[2]?.label ?? "离线",
              value: overview?.device_status?.[2]?.value ?? 0,
              unit: overview?.device_status?.[2]?.unit,
              detail: "园区终端运行状态",
            }}
          />
        </BigscreenPanel>

        <BigscreenPanel title="最近告警" frame="wide">
          <AlertRows alerts={overview?.alerts ?? []} />
        </BigscreenPanel>
      </div>

      <div className="grid h-full min-h-0 grid-rows-[0.65fr_1.35fr] gap-[var(--panel-gap)]">
        <BigscreenPanel title="碳普惠" frame="tall">
          <KeyValueList items={overview?.benefit_items ?? []} />
        </BigscreenPanel>

        <BigscreenPanel title="零碳生活" frame="tall">
          <div className="grid gap-4">
            {(overview?.lifestyle_sections ?? []).map((section) => (
              <div key={section.id} className="grid gap-3">
                <div className="bigscreen-chip w-fit" data-tone="highlight">
                  {section.title}
                </div>
                <KeyValueList items={section.items} highlightFirst={section.id === "green-traffic"} />
              </div>
            ))}
          </div>
        </BigscreenPanel>
      </div>
    </div>
  )
}
