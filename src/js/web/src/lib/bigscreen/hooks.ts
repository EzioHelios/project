import { useQuery } from "@tanstack/react-query"

import { getBigscreenCarbon, getBigscreenIntro, getBigscreenMeta, getBigscreenOverview, getBigscreenPower, getHuayiBigscreenOverview } from "@/lib/bigscreen/api"
import { getBigscreenEnvironment } from "@/lib/bigscreen/environment"

export function useBigscreenMeta(variant: "default" | "huayi" = "default") {
  return useQuery({
    queryKey: ["bigscreen", "meta", variant],
    queryFn: () => getBigscreenMeta(variant),
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

export function useHuayiBigscreenOverview() {
  return useQuery({
    queryKey: ["bigscreen", "huayi", "overview"],
    queryFn: getHuayiBigscreenOverview,
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
