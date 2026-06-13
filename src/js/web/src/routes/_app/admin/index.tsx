import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowRight, FileText, KeyRound, ShieldCheck, Users } from "lucide-react"
import { PermissionCenterNav } from "@/components/admin/permission-center-nav"
import { AdminPageHeader, AdminPanel } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { PageContainer, PageSection } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/admin/")({
  component: AdminDashboardPage,
})

const shortcuts = [
  { title: "用户管理", to: "/auth/users", description: "查看和管理系统用户", icon: Users },
  { title: "角色管理", to: "/auth/roles", description: "创建、编辑和维护角色", icon: KeyRound },
  { title: "权限配置", to: "/admin/roles", description: "按角色配置权限码", icon: ShieldCheck },
  { title: "审计日志", to: "/admin/audit", description: "查看权限与安全相关操作", icon: FileText },
] as const

function AdminDashboardPage() {
  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="权限中心概览" />
      <PermissionCenterNav />
      <PageSection>
        <AdminPanel title="权限中心入口" contentClassName="p-0">
          {shortcuts.map((item) => (
            <div key={item.to} className="flex flex-col gap-3 border-border/70 border-b px-4 py-3 last:border-b-0 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border/70 bg-muted/40 text-muted-foreground">
                  <item.icon className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <div className="font-medium text-sm">{item.title}</div>
                  <div className="text-muted-foreground text-xs">{item.description}</div>
                </div>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link to={item.to}>
                  进入
                  <ArrowRight className="ml-1 h-4 w-4" />
                </Link>
              </Button>
            </div>
          ))}
        </AdminPanel>
      </PageSection>
    </PageContainer>
  )
}
