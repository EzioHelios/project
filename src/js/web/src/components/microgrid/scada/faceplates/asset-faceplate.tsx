import { Activity, Clock3, Database, Radio, Thermometer } from "lucide-react"
import { ChartPanel } from "@/components/admin-ui"
import { getAssetTypeLabel } from "@/components/microgrid/microgrid-page"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { createTrendChartOption, useAdminChartTheme } from "@/lib/admin-chart-theme"
import { useMicrogridAssetSeries } from "@/lib/api/hooks/microgrid"
import { formatMicrogridDateTime, formatMicrogridTime } from "@/lib/microgrid-time"
import type { ScadaSelection } from "../types"

const sourceLabels: Record<string, string> = {
  simulated: "系统状态",
  measured: "现场采集",
  projected: "状态计算",
  unknown: "未识别",
}

const toneClasses = {
  alarm: "bg-[hsl(var(--status-danger))]",
  normal: "bg-[hsl(var(--status-success))]",
  offline: "bg-muted-foreground",
  simulated: "bg-[hsl(var(--status-info))]",
  warning: "bg-[hsl(var(--status-warning))]",
}

function Fact({ label, value, icon: Icon }: { label: string; value: string; icon: typeof Activity }) {
  return (
    <div className="border-border/70 border-b py-3 last:border-b-0">
      <div className="flex items-center gap-2 text-muted-foreground text-xs">
        <Icon className="size-3.5" />
        {label}
      </div>
      <div className="mt-1.5 font-medium text-sm tabular-nums">{value}</div>
    </div>
  )
}

export function AssetFaceplate({ selection, onOpenChange }: { selection: ScadaSelection | null; onOpenChange: (open: boolean) => void }) {
  const chartTheme = useAdminChartTheme("energy")
  const asset = selection?.asset
  const series = useMicrogridAssetSeries(asset?.id ?? null)
  const chartPoints = (series.data ?? []).map((point) => ({ period: formatMicrogridTime(point.observedAt), value: point.value }))
  const option = createTrendChartOption(chartTheme, chartPoints, [{ key: "value", label: "有功功率", colorKey: "energy" }], { includeZeroSeries: true })
  return (
    <Sheet onOpenChange={onOpenChange} open={selection !== null}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader className="border-b pr-12">
          <div className="flex items-center gap-2">
            <span className={`inline-flex size-2 rounded-full ${toneClasses[selection?.tone ?? "simulated"]}`} />
            <SheetTitle>{selection?.label ?? "设备详情"}</SheetTitle>
          </div>
          <SheetDescription>{asset ? `${getAssetTypeLabel(asset.assetType)} · ${asset.code}` : "一次系统结构节点"}</SheetDescription>
        </SheetHeader>
        <div className="px-4">
          <div className="grid grid-cols-2 gap-x-5">
            <Fact icon={Activity} label="运行状态" value={selection?.statusLabel ?? "-"} />
            <Fact icon={Radio} label="通信状态" value={asset ? (asset.online ? "在线" : "离线") : "状态正常"} />
            <Fact icon={Activity} label="有功功率" value={asset?.activePowerKw === null || asset?.activePowerKw === undefined ? "-" : `${asset.activePowerKw.toFixed(1)} kW`} />
            <Fact icon={Database} label="数据来源" value={sourceLabels[asset?.stateSourceKind ?? "simulated"] ?? asset?.stateSourceKind ?? "系统状态"} />
            {asset?.socPct !== null && asset?.socPct !== undefined && <Fact icon={Activity} label="储能SOC" value={`${asset.socPct.toFixed(1)} %`} />}
            {asset?.temperatureC !== null && asset?.temperatureC !== undefined && <Fact icon={Thermometer} label="设备温度" value={`${asset.temperatureC.toFixed(1)} ℃`} />}
            <Fact icon={Clock3} label="数据时间" value={formatMicrogridDateTime(asset?.observedAt)} />
            <Fact icon={Database} label="运行边界" value={asset?.controllable ? "功率目标" : "状态监视"} />
          </div>
          {asset && (
            <div className="mt-4 pb-5">
              <ChartPanel
                emptyLabel={series.isLoading ? "正在读取遥测趋势" : "暂无遥测趋势"}
                height={220}
                option={option}
                source={sourceLabels[asset.stateSourceKind] ?? asset.stateSourceKind}
                title="最近24小时功率"
                unit="kW"
                updatedAt={formatMicrogridDateTime(series.data?.[Math.max((series.data?.length ?? 1) - 1, 0)]?.observedAt ?? asset.observedAt)}
              />
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
