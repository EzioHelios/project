import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ChevronDown } from "lucide-react"
import { useEffect } from "react"
import { useAuthStore } from "@/lib/auth"
import { listTeams } from "@/lib/generated/api"

export function BigscreenTenantSwitcher() {
  const { currentTeam, setCurrentTeam, setTeams, isAuthenticated } = useAuthStore()
  const queryClient = useQueryClient()
  const {
    data: teams,
    isPending,
    isError,
  } = useQuery({
    queryKey: ["teams"],
    queryFn: async () => {
      const response = await listTeams({ throwOnError: true })
      return response.data.items ?? []
    },
    enabled: isAuthenticated,
  })

  useEffect(() => {
    if (teams) setTeams(teams)
  }, [teams, setTeams])

  const selectedId = teams?.some((team) => team.id === currentTeam?.id) ? currentTeam?.id : ""

  return (
    <div className="bigscreen-screen-header-utility-item bigscreen-tenant-switcher">
      <select
        aria-label="切换租户"
        title={isError ? "租户列表加载失败" : (currentTeam?.name ?? "选择租户")}
        value={selectedId ?? ""}
        disabled={isPending || isError || !teams?.length}
        onChange={(event) => {
          const team = teams?.find((item) => item.id === event.target.value)
          if (!team || team.id === currentTeam?.id) return
          setCurrentTeam(team)
          void queryClient.invalidateQueries()
        }}
      >
        {!selectedId && <option value="">{isPending ? "加载租户…" : isError ? "租户加载失败" : "选择租户"}</option>}
        {teams?.map((team) => (
          <option key={team.id} value={team.id}>
            {team.name}
          </option>
        ))}
      </select>
      <ChevronDown aria-hidden="true" size={16} />
    </div>
  )
}
