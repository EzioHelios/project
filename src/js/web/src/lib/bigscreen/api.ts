import type {
  BigscreenApiEnvelope,
  BigscreenCarbonResponse,
  BigscreenIntroResponse,
  BigscreenMetaResponse,
  BigscreenOverviewResponse,
  BigscreenPowerResponse,
  HuayiBigscreenOverviewResponse,
} from "@/lib/bigscreen/types"
import { getApiBaseUrl } from "@/lib/api-base-url"

async function requestBigscreen<T>(path: string): Promise<BigscreenApiEnvelope<T>> {
  const apiUrl = getApiBaseUrl()
  const response = await fetch(`${apiUrl}${path}`, {
    credentials: "include",
  })
  const text = await response.text()
  const raw = text ? JSON.parse(text) : {}
  if (!response.ok || (raw.code && raw.code >= 400)) {
    throw new Error(raw.msg || raw.detail || `HTTP ${response.status}`)
  }
  return raw as BigscreenApiEnvelope<T>
}

export function getBigscreenMeta(variant: "default" | "huayi" = "default") {
  return requestBigscreen<BigscreenMetaResponse>(variant === "huayi" ? "/api/bigscreen/huayi/meta" : "/api/bigscreen/meta")
}

export function getBigscreenIntro() {
  return requestBigscreen<BigscreenIntroResponse>("/api/bigscreen/intro")
}

export function getBigscreenOverview() {
  return requestBigscreen<BigscreenOverviewResponse>("/api/bigscreen/overview")
}

export function getBigscreenPower() {
  return requestBigscreen<BigscreenPowerResponse>("/api/bigscreen/power")
}

export function getBigscreenCarbon() {
  return requestBigscreen<BigscreenCarbonResponse>("/api/bigscreen/carbon")
}

export function getHuayiBigscreenOverview() {
  return requestBigscreen<HuayiBigscreenOverviewResponse>("/api/bigscreen/huayi/overview")
}
