import { useQuery } from "@tanstack/react-query"

import { getBigscreenCarbon, getBigscreenIntro, getBigscreenMeta, getBigscreenOverview, getBigscreenPower } from "@/lib/bigscreen/api"

export function useBigscreenMeta() {
  return useQuery({
    queryKey: ["bigscreen", "meta"],
    queryFn: getBigscreenMeta,
    staleTime: 1000 * 60 * 5,
  })
}

export function useBigscreenIntro() {
  return useQuery({
    queryKey: ["bigscreen", "intro"],
    queryFn: getBigscreenIntro,
  })
}

export function useBigscreenOverview() {
  return useQuery({
    queryKey: ["bigscreen", "overview"],
    queryFn: getBigscreenOverview,
  })
}

export function useBigscreenPower() {
  return useQuery({
    queryKey: ["bigscreen", "power"],
    queryFn: getBigscreenPower,
  })
}

export function useBigscreenCarbon() {
  return useQuery({
    queryKey: ["bigscreen", "carbon"],
    queryFn: getBigscreenCarbon,
  })
}
