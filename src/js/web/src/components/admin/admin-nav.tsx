import { Link, useRouterState } from "@tanstack/react-router"
import { Button } from "@/components/ui/button"

const navItems = [
  { label: "概览", to: "/admin" },
  { label: "角色", to: "/admin/roles" },
  { label: "用户", to: "/admin/users" },
  { label: "团队", to: "/admin/teams" },
  { label: "审计日志", to: "/admin/audit" },
] as const

export function AdminNav() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })

  return (
    <div className="flex flex-wrap gap-2">
      {navItems.map((item) => {
        const isActive = pathname === item.to || (item.to !== "/admin" && pathname.startsWith(item.to))
        return (
          <Button key={item.to} asChild variant={isActive ? "default" : "outline"} size="sm">
            <Link to={item.to}>{item.label}</Link>
          </Button>
        )
      })}
    </div>
  )
}
