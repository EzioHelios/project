import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowRight, FileText, KeyRound, ShieldCheck, Users } from "lucide-react"
import { PermissionCenterNav } from "@/components/admin/permission-center-nav"
import { AdminPageHeader } from "@/components/admin-ui"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {shortcuts.map((item) => (
            <Card key={item.to} hover className="border-border/60 bg-card/80">
              <CardHeader className="space-y-2">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <item.icon className="h-5 w-5" />
                </div>
                <CardTitle className="text-base">{item.title}</CardTitle>
                <CardDescription>{item.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <Link to={item.to} className="inline-flex items-center text-sm font-medium text-primary hover:text-primary/80">
                  进入页面 <ArrowRight className="ml-1 h-4 w-4" />
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      </PageSection>
    </PageContainer>
  )
}
