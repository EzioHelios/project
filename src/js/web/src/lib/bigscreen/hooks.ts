import { useQuery } from "@tanstack/react-query"
import { useAuthStore } from "@/lib/auth"

import {
  getBigscreenCarbon,
  getBigscreenEvents,
  getBigscreenIntro,
  getBigscreenMeta,
  getBigscreenOverview,
  getBigscreenPower,
  getHuayiBigscreenOverview,
} from "@/lib/bigscreen/api"
import { getBigscreenEnvironment } from "@/lib/bigscreen/environment"
import type { BigscreenEventFilters, BigscreenPeriod } from "@/lib/bigscreen/types"

export function useBigscreenEvents(filters: BigscreenEventFilters) {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return useQuery({
    queryKey: ["bigscreen", "events", teamId, filters],
    queryFn: ({ signal }) => getBigscreenEvents(filters, { teamId, signal }),
    enabled: Boolean(teamId),
  })
}

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

export function useBigscreenOverview(period: BigscreenPeriod = {}) {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return useQuery({
    queryKey: ["bigscreen", "overview", teamId, period],
    queryFn: ({ signal }) => getBigscreenOverview({ teamId, signal }, period),
    placeholderData: (previous, previousQuery) => (previousQuery?.queryKey[2] === teamId ? previous : undefined),
    refetchInterval: 60000,
    enabled: Boolean(teamId),
  })
}

export function useBigscreenPower(period: BigscreenPeriod = {}) {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return useQuery({
    queryKey: ["bigscreen", "power", teamId, period],
    queryFn: ({ signal }) => getBigscreenPower({ teamId, signal }, period),
    placeholderData: (previous, previousQuery) => (previousQuery?.queryKey[2] === teamId ? previous : undefined),
    refetchInterval: 60000,
    enabled: Boolean(teamId),
  })
}

export function useBigscreenCarbon(enabled = true) {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return useQuery({
    queryKey: ["bigscreen", "carbon", teamId],
    queryFn: ({ signal }) => getBigscreenCarbon({ teamId, signal }),
    enabled: Boolean(teamId) && enabled,
    refetchInterval: 60000,
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
