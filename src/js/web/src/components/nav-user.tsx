"use client"

import { useNavigate } from "@tanstack/react-router"
import { Building2, Check, ChevronsUpDown, LogOut, Plus, ShieldCheck, User } from "lucide-react"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem, useSidebar } from "@/components/ui/sidebar"
import { useAuthStore } from "@/lib/auth"
import type { Team } from "@/lib/generated/api"

interface NavUserProps {
  teams: Team[]
  currentTeam: Team | null
  onTeamSelect: (team: Team) => void
}

function getInitials(value: string) {
  return value
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
}

function MenuActionRow({ title }: { title: string }) {
  return (
    <span className="grid min-w-0 flex-1 gap-0.5 text-left">
      <span className="truncate text-sm font-medium">{title}</span>
    </span>
  )
}

export function NavUser({ teams, currentTeam, onTeamSelect }: NavUserProps) {
  const navigate = useNavigate()
  const { logout, user } = useAuthStore()
  const { isMobile } = useSidebar()

  const onLogout = async () => {
    await logout()
    navigate({ to: "/" })
  }

  if (!user) {
    return null
  }

  const displayName = user.name || user.username || "账号"
  const initials = getInitials(displayName)
  const activeTeam = currentTeam ?? teams[0] ?? null
  const activeTeamInitials = activeTeam ? getInitials(activeTeam.name) : "租"

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg" className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground">
              <Avatar className="h-8 w-8 shrink-0 rounded-lg">
                <AvatarImage src={user.avatarUrl ?? undefined} alt={displayName} />
                <AvatarFallback className="rounded-lg">{initials}</AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
                <span className="truncate font-medium">{displayName}</span>
                <span className="truncate text-xs">{user.email}</span>
              </div>
              <ChevronsUpDown className="ml-auto size-4 group-data-[collapsible=icon]:hidden" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-80 rounded-lg" side={isMobile ? "bottom" : "right"} align="end" sideOffset={4}>
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-3 px-2 py-2 text-left text-sm">
                <Avatar className="h-9 w-9 rounded-lg">
                  <AvatarImage src={user.avatarUrl ?? undefined} alt={displayName} />
                  <AvatarFallback className="rounded-lg">{initials}</AvatarFallback>
                </Avatar>
                <div className="grid min-w-0 flex-1 text-left text-sm leading-tight">
                  <span className="text-[0.65rem] font-semibold uppercase tracking-wide text-muted-foreground">账号</span>
                  <span className="truncate font-medium">{displayName}</span>
                  <span className="truncate text-xs">{user.email}</span>
                </div>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-3 px-2 py-2 text-left text-sm">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-xs font-semibold text-primary">{activeTeamInitials}</div>
                <div className="grid min-w-0 flex-1 leading-tight">
                  <span className="text-[0.65rem] font-semibold uppercase tracking-wide text-muted-foreground">租户</span>
                  <div className="truncate text-sm font-medium">{activeTeam?.name ?? "未选择租户"}</div>
                  {activeTeam?.slug && <div className="truncate text-xs font-normal text-muted-foreground">{activeTeam.slug}</div>}
                </div>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger className="gap-2 py-2">
                <Building2 className="size-4 text-muted-foreground" />
                切换租户
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent className="w-64">
                {teams.length > 0 ? (
                  teams.map((team) => {
                    const isActive = team.id === activeTeam?.id

                    return (
                      <DropdownMenuItem key={team.id} className="gap-2" onClick={() => onTeamSelect(team)}>
                        <span className="flex size-5 items-center justify-center">{isActive && <Check className="size-4 text-primary" />}</span>
                        <span className="min-w-0 flex-1 truncate">{team.name}</span>
                      </DropdownMenuItem>
                    )
                  })
                ) : (
                  <DropdownMenuItem disabled>暂无可切换租户</DropdownMenuItem>
                )}
              </DropdownMenuSubContent>
            </DropdownMenuSub>
            <DropdownMenuSeparator />
            {activeTeam && (
              <DropdownMenuItem className="h-auto cursor-pointer items-start gap-3 px-2 py-2" onClick={() => navigate({ to: "/teams/$teamId", params: { teamId: activeTeam.id } })}>
                <Building2 className="mt-0.5 size-4" />
                <MenuActionRow title="租户资料" />
              </DropdownMenuItem>
            )}
            <DropdownMenuItem className="h-auto cursor-pointer items-start gap-3 px-2 py-2" onClick={() => navigate({ to: "/profile" })}>
              <User className="mt-0.5 size-4" />
              <MenuActionRow title="个人资料" />
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="cursor-pointer" onClick={() => navigate({ to: "/teams/new" })}>
              <Plus />
              新建租户
            </DropdownMenuItem>
            <DropdownMenuItem className="cursor-default focus:bg-transparent">
              <ShieldCheck />
              MFA
              <Badge variant={user.isTwoFactorEnabled ? "default" : "secondary"} className="ml-auto">
                {user.isTwoFactorEnabled ? "已启用" : "未启用"}
              </Badge>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="cursor-pointer" onClick={onLogout}>
              <LogOut />
              退出登录
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
