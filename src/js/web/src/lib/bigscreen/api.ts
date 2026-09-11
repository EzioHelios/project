import { getApiBaseUrl } from "@/lib/api-base-url"
import type {
  BigscreenApiEnvelope,
  BigscreenCarbonResponse,
  BigscreenIntroResponse,
  BigscreenMetaResponse,
  BigscreenOverviewResponse,
  BigscreenPowerResponse,
  HuayiBigscreenOverviewResponse,
} from "@/lib/bigscreen/types"

type BigscreenRequestScope = { teamId?: string; signal?: AbortSignal }

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

export function getBigscreenOverview(scope?: BigscreenRequestScope) {
  return requestBigscreen<BigscreenOverviewResponse>("/api/bigscreen/overview", scope)
}

export function getBigscreenPower(scope?: BigscreenRequestScope) {
  return requestBigscreen<BigscreenPowerResponse>("/api/bigscreen/power", scope)
}

export function getBigscreenCarbon(scope?: BigscreenRequestScope) {
  return requestBigscreen<BigscreenCarbonResponse>("/api/bigscreen/carbon", scope)
}

export function getHuayiBigscreenOverview(scope?: BigscreenRequestScope) {
  return requestBigscreen<HuayiBigscreenOverviewResponse>("/api/bigscreen/huayi/overview", scope)
}
