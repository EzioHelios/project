import type * as React from "react"

import { cn } from "@/lib/utils"

export type DesignDomain = "neutral" | "energy" | "carbon"

const carbonPaths = ["/carbon", "/carbon-mgmt", "/energy/budget", "/energy-carbon/carbon", "/energy-carbon/factors", "/energy-carbon/quality"]
const energyPaths = [
  "/energy",
  "/microgrid",
  "/energy-carbon/monitor",
  "/energy-carbon/alerts",
  "/data/alarm-rules",
  "/data/alarm-events",
  "/data/video-alarm-events",
  "/data/point-monitoring",
]

function pathMatches(pathname: string, prefix: string) {
  return pathname === prefix || pathname.startsWith(`${prefix}/`) || (prefix.endsWith("/") && pathname.startsWith(prefix))
}

export function resolveAdminDomain(pathname: string): DesignDomain {
  if (carbonPaths.some((path) => pathMatches(pathname, path))) return "carbon"
  if (energyPaths.some((path) => pathMatches(pathname, path))) return "energy"
  return "neutral"
}

type AdminDomainScopeProps = React.HTMLAttributes<HTMLDivElement> & {
  domain: DesignDomain
}

export function AdminDomainScope({ domain, className, ...props }: AdminDomainScopeProps) {
  return <div data-design-domain={domain} className={cn("admin-domain-scope", className)} {...props} />
}
