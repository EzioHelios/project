import { ACCESS_TOKEN_KEY } from "@/lib/auth"
import type {
  BigscreenApiEnvelope,
  BigscreenCarbonResponse,
  BigscreenIntroResponse,
  BigscreenMetaResponse,
  BigscreenOverviewResponse,
  BigscreenPowerResponse,
} from "@/lib/bigscreen/types"

async function requestBigscreen<T>(path: string): Promise<BigscreenApiEnvelope<T>> {
  const apiUrl = import.meta.env.VITE_API_URL ?? ""
  const token = typeof window === "undefined" ? null : window.localStorage.getItem(ACCESS_TOKEN_KEY)
  const response = await fetch(`${apiUrl}${path}`, {
    credentials: "include",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  const text = await response.text()
  const raw = text ? JSON.parse(text) : {}
  if (!response.ok || (raw.code && raw.code >= 400)) {
    throw new Error(raw.msg || raw.detail || `HTTP ${response.status}`)
  }
  return raw as BigscreenApiEnvelope<T>
}

export function getBigscreenMeta() {
  return requestBigscreen<BigscreenMetaResponse>("/api/bigscreen/meta")
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
