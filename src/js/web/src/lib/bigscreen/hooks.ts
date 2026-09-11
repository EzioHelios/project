import { useQuery } from "@tanstack/react-query"
import { useAuthStore } from "@/lib/auth"

import { getBigscreenCarbon, getBigscreenIntro, getBigscreenMeta, getBigscreenOverview, getBigscreenPower, getHuayiBigscreenOverview } from "@/lib/bigscreen/api"
import { getBigscreenEnvironment } from "@/lib/bigscreen/environment"

export function useBigscreenMeta(variant: "default" | "huayi" = "default") {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return useQuery({
    queryKey: ["bigscreen", "meta", variant, teamId],
    queryFn: ({ signal }) => getBigscreenMeta(variant, { teamId, signal }),
    enabled: Boolean(teamId),
    staleTime: 1000 * 60 * 5,
  })
}

export function useBigscreenIntro() {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return useQuery({
    queryKey: ["bigscreen", "intro", teamId],
    queryFn: ({ signal }) => getBigscreenIntro({ teamId, signal }),
    enabled: Boolean(teamId),
  })
}

export function useBigscreenOverview() {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return useQuery({
    queryKey: ["bigscreen", "overview", teamId],
    queryFn: ({ signal }) => getBigscreenOverview({ teamId, signal }),
    enabled: Boolean(teamId),
  })
}

export function useBigscreenPower() {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return useQuery({
    queryKey: ["bigscreen", "power", teamId],
    queryFn: ({ signal }) => getBigscreenPower({ teamId, signal }),
    enabled: Boolean(teamId),
  })
}

export function useBigscreenCarbon() {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return useQuery({
    queryKey: ["bigscreen", "carbon", teamId],
    queryFn: ({ signal }) => getBigscreenCarbon({ teamId, signal }),
    enabled: Boolean(teamId),
  })
}

export function useHuayiBigscreenOverview() {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return useQuery({
    queryKey: ["bigscreen", "huayi", "overview", teamId],
    queryFn: ({ signal }) => getHuayiBigscreenOverview({ teamId, signal }),
    enabled: Boolean(teamId),
    staleTime: 1000 * 60 * 5,
  })
}

export function useBigscreenEnvironment(weatherEnabled: boolean) {
  return useQuery({
    queryKey: ["bigscreen", "environment", weatherEnabled],
    queryFn: () => getBigscreenEnvironment({ weatherEnabled }),
    staleTime: 1000 * 60 * 15,
    retry: 1,
  })
}
