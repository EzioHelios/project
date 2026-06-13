import { AdminPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { SkeletonCard } from "@/components/ui/skeleton"
import { useAdminDashboardStats } from "@/lib/api/hooks/admin"

export function StatsCards() {
  const { data, isLoading, isError } = useAdminDashboardStats()

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: Static skeleton placeholders
          <SkeletonCard key={`stats-skeleton-${index}`} />
        ))}
      </div>
    )
  }

  if (isError || !data) {
    return (
      <AdminPanel title="权限中心统计">
        <div className="text-muted-foreground text-sm">统计数据加载失败，请稍后重试。</div>
      </AdminPanel>
    )
  }

  const items = [
    { label: "用户总数", value: data.totalUsers },
    { label: "启用用户", value: data.activeUsers },
    { label: "已验证用户", value: data.verifiedUsers },
    { label: "团队总数", value: data.totalTeams },
    { label: "今日新增用户", value: data.newUsersToday },
    { label: "本周新增用户", value: data.newUsersWeek },
    { label: "今日事件", value: data.eventsToday },
  ]

  return (
    <MetricStrip className="xl:grid-cols-4">
      {items.map((item) => (
        <MetricTile key={item.label} label={item.label} value={item.value.toLocaleString("zh-CN")} />
      ))}
    </MetricStrip>
  )
}
