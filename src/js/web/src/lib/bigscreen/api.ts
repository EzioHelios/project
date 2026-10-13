import { getApiBaseUrl } from "@/lib/api-base-url"
import type {
  BigscreenApiEnvelope,
  BigscreenCarbonResponse,
  BigscreenEventFilters,
  BigscreenEventSummary,
  BigscreenIntroResponse,
  BigscreenMetaResponse,
  BigscreenOperationsResponse,
  BigscreenPeriod,
  HuayiBigscreenOverviewResponse,
} from "@/lib/bigscreen/types"

type BigscreenRequestScope = { teamId?: string; signal?: AbortSignal }

export function getBigscreenEvents(filters: BigscreenEventFilters, scope?: BigscreenRequestScope) {
  const params = new URLSearchParams(
    Object.entries(filters)
      .filter(([, value]) => value !== "" && value != null)
      .map(([key, value]) => [key, String(value)]),
  )
  return requestBigscreen<BigscreenEventSummary>(`/api/bigscreen/events?${params}`, scope)
}

export async function getBigscreenPhoto(id: string, scope: BigscreenRequestScope) {
  const response = await fetch(`${getApiBaseUrl()}/api/bigscreen/photos/${encodeURIComponent(id)}`, {
    credentials: "include",
    signal: scope.signal,
    headers: scope.teamId ? { "X-Team-Id": scope.teamId } : undefined,
  })
  if (!response.ok) throw new Error("照片暂不可用")
  return response.blob()
}

async function requestBigscreen<T>(path: string, scope?: BigscreenRequestScope): Promise<BigscreenApiEnvelope<T>> {
  const apiUrl = getApiBaseUrl()
  const response = await fetch(`${apiUrl}${path}`, {
    credentials: "include",
    signal: scope?.signal,
    headers: scope?.teamId ? { "X-Team-Id": scope.teamId } : undefined,
  })
  const text = await response.text()
  const raw = text ? JSON.parse(text) : {}
  if (!response.ok || (raw.code && raw.code >= 400)) {
    throw new Error(raw.msg || raw.detail || `HTTP ${response.status}`)
  }
  return raw as BigscreenApiEnvelope<T>
}

export function getBigscreenMeta(variant: "default" | "huayi" = "default", scope?: BigscreenRequestScope) {
  return requestBigscreen<BigscreenMetaResponse>(variant === "huayi" ? "/api/bigscreen/huayi/meta" : "/api/bigscreen/meta", scope)
}

export function getBigscreenIntro(scope?: BigscreenRequestScope) {
  return requestBigscreen<BigscreenIntroResponse>("/api/bigscreen/intro", scope)
}

export function getBigscreenOverview(scope?: BigscreenRequestScope, period: BigscreenPeriod = {}) {
  return requestBigscreen<BigscreenOperationsResponse>(
    `/api/bigscreen/overview?${new URLSearchParams(Object.entries(period).filter(([, value]) => Boolean(value)) as [string, string][])}`,
    scope,
  )
}

export function getBigscreenPower(scope?: BigscreenRequestScope, period: BigscreenPeriod = {}) {
  return requestBigscreen<BigscreenOperationsResponse>(
    `/api/bigscreen/power?${new URLSearchParams(Object.entries(period).filter(([, value]) => Boolean(value)) as [string, string][])}`,
    scope,
  )
}

export function getBigscreenCarbon(scope?: BigscreenRequestScope) {
  return requestBigscreen<BigscreenCarbonResponse>("/api/bigscreen/carbon", scope)
}

export function getHuayiBigscreenOverview(scope?: BigscreenRequestScope) {
  return requestBigscreen<HuayiBigscreenOverviewResponse>("/api/bigscreen/huayi/overview", scope)
}
