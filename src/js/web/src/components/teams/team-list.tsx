import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { Check, ChevronRight, Plus, Search, Shield, Users } from "lucide-react"
import { useEffect, useState } from "react"
import { AdminEmptyState, AdminPanel, AdminTableToolbar, StatusBadge } from "@/components/admin-ui"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useAuthStore } from "@/lib/auth"
import { listTeams, type Team } from "@/lib/generated/api"

function getTeamInitials(name: string): string {
  return name
    .split(/\s+/)
    .map((word) => word[0])
    .join("")
    .toUpperCase()
    .slice(0, 2)
}

export function TeamList() {
  const { user, currentTeam, setCurrentTeam, setTeams } = useAuthStore()
  const [search, setSearch] = useState("")

  const {
    data: teamsData = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["teams"],
    queryFn: async () => {
      const response = await listTeams()
      return response.data?.items ?? []
    },
  })

  useEffect(() => {
    if (!isLoading && !isError) {
      setTeams(teamsData)
    }
  }, [isError, isLoading, setTeams, teamsData])

  const filteredTeams = teamsData.filter((team) => team.name.toLowerCase().includes(search.toLowerCase()) || team.description?.toLowerCase().includes(search.toLowerCase()))

  if (isLoading) {
    return (
      <AdminPanel title="团队列表">
        <AdminEmptyState title="正在加载团队" />
      </AdminPanel>
    )
  }

  if (isError) {
    return (
      <AdminPanel title="团队列表">
        <AdminEmptyState title="团队数据加载失败" description="请稍后重试。" />
      </AdminPanel>
    )
  }

  if (teamsData.length === 0) {
    return (
      <AdminPanel title="团队列表">
        <AdminEmptyState
          title="暂无团队"
          actions={
            <Button asChild size="sm">
              <Link to="/teams/new">
                <Plus className="mr-2 h-4 w-4" />
                新建团队
              </Link>
            </Button>
          }
        />
      </AdminPanel>
    )
  }

  return (
    <AdminPanel
      title="团队列表"
      actions={
        <Button asChild size="sm">
          <Link to="/teams/new">
            <Plus className="mr-2 h-4 w-4" />
            新建团队
          </Link>
        </Button>
      }
      contentClassName="space-y-3"
    >
      {teamsData.length > 3 && (
        <AdminTableToolbar
          search={
            <div className="relative">
              <Search className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input placeholder="搜索团队" value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" />
            </div>
          }
          className="rounded-md border border-border/70 bg-muted/20"
        />
      )}

      <div className="overflow-hidden rounded-md border border-border/70 bg-background">
        {filteredTeams.map((team: Team) => {
          const isActive = currentTeam?.id === team.id
          const tags = team.tags ?? []
          const memberCount = team.members?.length ?? 0
          const userMembership = team.members?.find((m) => m.userId === user?.id)
          const isOwner = userMembership?.isOwner
          const isAdmin = userMembership?.role === "ADMIN"

          return (
            <div key={team.id} className="flex flex-col gap-3 border-border/70 border-b px-4 py-3 last:border-b-0 md:flex-row md:items-center md:justify-between">
              <div className="flex min-w-0 items-start gap-3">
                <button type="button" onClick={() => setCurrentTeam(team)} className="relative" title={isActive ? "当前团队" : "切换到该团队"}>
                  <Avatar className="h-10 w-10 rounded-md border border-border/70 bg-muted text-muted-foreground">
                    <AvatarFallback className="rounded-md bg-muted font-semibold text-xs">{getTeamInitials(team.name)}</AvatarFallback>
                  </Avatar>
                  {isActive && (
                    <span className="absolute -right-1 -bottom-1 flex h-5 w-5 items-center justify-center rounded-sm border border-background bg-primary text-primary-foreground">
                      <Check className="h-3 w-3" />
                    </span>
                  )}
                </button>
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link to="/teams/$teamId" params={{ teamId: team.id }} className="truncate font-medium text-foreground hover:underline">
                      {team.name}
                    </Link>
                    {isActive && <StatusBadge status="in_progress" label="当前团队" />}
                    {(isOwner || isAdmin) && (
                      <Badge variant="outline" className="h-5 rounded-sm px-1.5 text-[10px] font-medium">
                        {isOwner ? (
                          "所有者"
                        ) : (
                          <>
                            <Shield className="mr-0.5 h-2.5 w-2.5" />
                            Admin
                          </>
                        )}
                      </Badge>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-muted-foreground text-xs">
                    <span className="inline-flex items-center gap-1">
                      <Users className="h-3 w-3" />
                      {memberCount} 名成员
                    </span>
                    {team.description && <span className="line-clamp-1">{team.description}</span>}
                  </div>
                  {tags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {tags.slice(0, 3).map((tag) => (
                        <Badge key={tag.id} variant="secondary" className="rounded-sm px-2 py-0 text-[10px]">
                          {tag.name}
                        </Badge>
                      ))}
                      {tags.length > 3 && (
                        <Badge variant="outline" className="rounded-sm px-2 py-0 text-[10px]">
                          +{tags.length - 3}
                        </Badge>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <Button variant="outline" size="sm" asChild>
                <Link to="/teams/$teamId" params={{ teamId: team.id }}>
                  查看
                  <ChevronRight className="ml-1 h-4 w-4" />
                </Link>
              </Button>
            </div>
          )
        })}
      </div>

      {filteredTeams.length === 0 && search && <AdminEmptyState title={`没有匹配“${search}”的团队`} className="min-h-28" />}

      {filteredTeams.length > 0 && (
        <p className="text-center text-muted-foreground text-xs">
          共 {teamsData.length} 个团队，当前显示 {filteredTeams.length} 个
        </p>
      )}
    </AdminPanel>
  )
}
