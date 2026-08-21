import { Link, useRouterState } from "@tanstack/react-router"
import { Button } from "@/components/ui/button"

const navItems = [
  { label: "概览", to: "/admin", activePaths: ["/admin"], exact: true },
  { label: "用户管理", to: "/auth/users", activePaths: ["/auth/users", "/admin/users"] },
  { label: "角色管理", to: "/auth/roles", activePaths: ["/auth/roles"] },
  { label: "权限配置", to: "/admin/roles", activePaths: ["/admin/roles"] },
  { label: "审计日志", to: "/admin/audit", activePaths: ["/admin/audit"] },
] as const

export function PermissionCenterNav() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })

  return (
    <div className="flex flex-wrap gap-2">
      {navItems.map((item) => {
        const isActive = item.activePaths.some((path) => ("exact" in item && item.exact ? pathname === path : pathname === path || pathname.startsWith(path)))
        return (
          <Button key={item.to} asChild variant={isActive ? "default" : "outline"} size="sm">
            <Link to={item.to}>{item.label}</Link>
          </Button>
        )
      })}
    </div>
  )
}
