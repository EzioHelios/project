import { AdminEmptyState, AdminPanel } from "@/components/admin-ui"
import { SkeletonTable } from "@/components/ui/skeleton"
import { useAdminRecentActivity } from "@/lib/api/hooks/admin"

export function RecentActivity() {
  const { data, isLoading, isError } = useAdminRecentActivity()

  if (isLoading) {
    return <SkeletonTable rows={4} />
  }

  if (isError || !data) {
    return (
      <AdminPanel title="最近活动">
        <div className="text-muted-foreground text-sm">最近活动加载失败，请稍后重试。</div>
      </AdminPanel>
    )
  }

  return (
    <AdminPanel title="最近活动" contentClassName="space-y-3">
      {data.activities.length === 0 && <AdminEmptyState title="暂无最近活动" className="min-h-28" />}
      {data.activities.map((activity) => (
        <div key={activity.id} className="flex flex-col gap-1 rounded-lg border border-border/60 bg-muted/30 px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-medium">{activity.action}</p>
            <span className="text-xs text-muted-foreground">{new Date(activity.createdAt).toLocaleString()}</span>
          </div>
          <div className="text-muted-foreground text-sm">
            {activity.actorEmail ?? "系统"} {activity.targetLabel ? `· ${activity.targetLabel}` : ""}
          </div>
        </div>
      ))}
    </AdminPanel>
  )
}
