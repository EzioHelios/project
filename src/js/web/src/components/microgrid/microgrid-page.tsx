import { useNavigate, useRouterState } from "@tanstack/react-router"
import { AdminTabsList, StatusBadge } from "@/components/admin-ui"
import { Tabs, TabsTrigger } from "@/components/ui/tabs"
import type { MicrogridAsset, MicrogridTopology } from "@/lib/api/hooks/microgrid"
import { cn } from "@/lib/utils"

const settingsTabs = [
  { value: "/microgrid/settings/assets", label: "设备与场景" },
  { value: "/microgrid/settings/flexibility", label: "柔性契约" },
] as const

type MicrogridSettingsRoute = (typeof settingsTabs)[number]["value"]

export function MicrogridSettingsTabs() {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const navigate = useNavigate()
  const active = settingsTabs.some((item) => item.value === pathname) ? (pathname as MicrogridSettingsRoute) : "/microgrid/settings/assets"
  return (
    <Tabs value={active} onValueChange={(value) => void navigate({ to: value as MicrogridSettingsRoute })}>
      <AdminTabsList>
        {settingsTabs.map((item) => (
          <TabsTrigger key={item.value} value={item.value}>
            {item.label}
          </TabsTrigger>
        ))}
      </AdminTabsList>
    </Tabs>
  )
}

export function ShadowModeBadge() {
  return <StatusBadge status="in_progress" label="影子运行" />
}

export function RunStatusBadge({ status }: { status?: string | null }) {
  if (status === "optimal" || status === "feasible" || status === "completed") return <StatusBadge status="approved" label={status === "optimal" ? "最优解" : "已完成"} />
  if (status === "running" || status === "queued") return <StatusBadge status="in_progress" label="计算中" />
  if (status === "failed" || status === "infeasible") return <StatusBadge status="rejected" label={status === "infeasible" ? "不可行" : "失败"} />
  return <StatusBadge status="pending" label="未运行" />
}

export function formatNumber(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return value.toLocaleString("zh-CN", { maximumFractionDigits: digits })
}

const assetTypeLabel: Record<MicrogridAsset["assetType"], string> = {
  grid: "电网",
  pv: "光伏",
  storage: "储能",
  charger: "充电桩",
  lighting: "照明",
  load: "负荷",
  generator: "备用机组",
}

export function getAssetTypeLabel(type: MicrogridAsset["assetType"]) {
  return assetTypeLabel[type]
}

export function MicrogridSingleLine({ topology }: { topology: MicrogridTopology }) {
  const nodeMap = new Map(topology.nodes.map((node) => [node.id, node]))
  const assetMap = new Map((topology.assets ?? []).map((asset) => [asset.code, asset]))
  return (
    <div className="min-h-[390px] overflow-x-auto bg-muted/15 p-3">
      <svg aria-label="微电网单线拓扑" className="min-w-[620px]" role="img" viewBox="0 0 560 360">
        <defs>
          <marker id="flow-arrow" markerHeight="6" markerWidth="6" orient="auto" refX="5" refY="3">
            <path className="fill-primary" d="M0,0 L0,6 L6,3 z" />
          </marker>
        </defs>
        {topology.edges.map((edge) => {
          const source = nodeMap.get(edge.source)
          const target = nodeMap.get(edge.target)
          if (!source || !target) return null
          return (
            <line
              className="stroke-border"
              key={`${edge.source}-${edge.target}`}
              markerEnd="url(#flow-arrow)"
              strokeWidth="2"
              x1={source.x}
              x2={target.x}
              y1={source.y}
              y2={target.y}
            />
          )
        })}
        {topology.nodes.map((node) => {
          const asset = node.assetCode ? assetMap.get(node.assetCode) : undefined
          return (
            <g key={node.id} transform={`translate(${node.x - 54} ${node.y - 25})`}>
              <rect className={cn("fill-background stroke-border", asset?.online && "stroke-primary")} height="50" rx="6" strokeWidth="1.5" width="108" />
              <circle className={asset?.online ? "fill-[hsl(var(--status-success))]" : "fill-muted-foreground"} cx="13" cy="14" r="4" />
              <text className="fill-foreground text-[11px] font-medium" x="22" y="18">
                {node.label}
              </text>
              <text className="fill-muted-foreground text-[10px] tabular-nums" x="12" y="37">
                {asset ? `${formatNumber(asset.activePowerKw)} kW` : "交流母线"}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
