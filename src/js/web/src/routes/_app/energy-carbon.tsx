import { createFileRoute, Link, Outlet, useLocation } from "@tanstack/react-router"
import { cn } from "@/lib/utils"

const TABS = [
  { path: "/energy-carbon", label: "经营总览" },
  { path: "/energy-carbon/energy", label: "综能监测" },
  { path: "/energy-carbon/monitor", label: "监测中心" },
  { path: "/energy-carbon/alerts", label: "告警中心" },
  { path: "/energy-carbon/flows", label: "能流分析" },
  { path: "/energy-carbon/carbon", label: "碳盘查与核算" },
  { path: "/energy-carbon/quality", label: "数据质量与追溯" },
  { path: "/energy-carbon/factors", label: "因子数据库" },
] as const

export const Route = createFileRoute("/_app/energy-carbon")({
  component: EnergyCarbonLayout,
})

function EnergyCarbonLayout() {
  const pathname = useLocation({ select: (location) => location.pathname })

  return (
    <div className="flex flex-1 flex-col space-y-4">
      <div className="overflow-x-auto border-b">
        <div className="flex min-w-max items-center gap-1 px-1">
          {TABS.map(({ path, label }) => {
            const active = pathname === path || (path === "/energy-carbon" && (pathname === "/energy-carbon" || pathname === "/energy-carbon/"))
            return (
              <Link
                key={path}
                to={path}
                className={cn(
                  "border-b-2 border-transparent px-4 py-3 text-sm font-medium transition-colors hover:text-primary",
                  active ? "border-primary text-primary" : "text-muted-foreground",
                )}
              >
                {label}
              </Link>
            )
          })}
        </div>
      </div>
      <Outlet />
    </div>
  )
}

export default EnergyCarbonLayout
