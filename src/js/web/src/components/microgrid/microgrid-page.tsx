import { useNavigate, useRouterState } from "@tanstack/react-router"
import { AdminTabsList, StatusBadge } from "@/components/admin-ui"
import { Tabs, TabsTrigger } from "@/components/ui/tabs"
import type { MicrogridAsset } from "@/lib/api/hooks/microgrid"

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
