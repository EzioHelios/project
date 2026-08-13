"use client"

import { Link, useNavigate, useRouterState } from "@tanstack/react-router"
import { ChevronRight, type LucideIcon } from "lucide-react"

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { SidebarGroup, SidebarGroupLabel, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarMenuSub, SidebarMenuSubButton, SidebarMenuSubItem } from "@/components/ui/sidebar"
import { type DesignDomain, resolveAdminDomain } from "@/lib/design-domain"

export function NavMain({
  items,
}: {
  items: {
    title: string
    to: string
    icon?: LucideIcon
    domain?: DesignDomain
    isActive?: boolean
    items?: {
      title: string
      to?: string
      kind?: "link" | "section"
    }[]
  }[]
}) {
  const navigate = useNavigate()
  const pathname = useRouterState({ select: (state) => state.location.pathname })

  return (
    <SidebarGroup className="quiet-sidebar-navigation">
      <SidebarGroupLabel className="sr-only">菜单</SidebarGroupLabel>
      <SidebarMenu>
        {items.map((item) => {
          if (!item.items || item.items.length === 0) {
            const isCurrent = pathname === item.to
            return (
              <SidebarMenuItem key={item.title} data-nav-domain={item.domain ?? resolveAdminDomain(item.to)}>
                <SidebarMenuButton asChild tooltip={item.title} isActive={isCurrent}>
                  <Link to={item.to} aria-current={isCurrent ? "page" : undefined}>
                    {item.icon && <item.icon className="shrink-0" />}
                    <span className="group-data-[collapsible=icon]:hidden">{item.title}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )
          }

          return (
            <Collapsible key={item.title} asChild defaultOpen={item.isActive} className="group/collapsible">
              <SidebarMenuItem data-nav-domain={item.domain ?? resolveAdminDomain(item.to)} data-has-active-child={Boolean(item.isActive)}>
                <CollapsibleTrigger asChild>
                  <SidebarMenuButton asChild tooltip={item.title} data-context-active={Boolean(item.isActive)}>
                    <button type="button" onClick={() => void navigate({ to: item.to })}>
                      {item.icon && <item.icon className="shrink-0" />}
                      <span className="group-data-[collapsible=icon]:hidden">{item.title}</span>
                      <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90 group-data-[collapsible=icon]:hidden" />
                    </button>
                  </SidebarMenuButton>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <SidebarMenuSub>
                    {item.items?.map((subItem) => (
                      <SidebarMenuSubItem key={subItem.title}>
                        {subItem.kind === "section" ? (
                          <div className="px-2 pt-3 pb-1 text-[0.6875rem] font-medium text-sidebar-foreground/45">{subItem.title}</div>
                        ) : (
                          <SidebarMenuSubButton asChild isActive={pathname === (subItem.to || item.to)}>
                            <Link to={subItem.to || item.to} aria-current={pathname === (subItem.to || item.to) ? "page" : undefined}>
                              <span>{subItem.title}</span>
                            </Link>
                          </SidebarMenuSubButton>
                        )}
                      </SidebarMenuSubItem>
                    ))}
                  </SidebarMenuSub>
                </CollapsibleContent>
              </SidebarMenuItem>
            </Collapsible>
          )
        })}
      </SidebarMenu>
    </SidebarGroup>
  )
}
