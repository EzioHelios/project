import { useQuery } from "@tanstack/react-query"
import { getApiBaseUrl } from "@/lib/api-base-url"

export interface PublicAppConfig {
  displayName: string
  shortName: string
  description: string
  brandMarkUrl: string | null
  faviconUrl: string | null
  authMode: "cookie-session"
  captchaProvider: string | null
  captchaEnabled: boolean
  captchaChallengeUrl: string | null
  captchaSiteKey: string | null
}

const demoLogoFullUrlEnv = import.meta.env.VITE_DEMO_LOGO_FULL_URL
const demoLogoFullUrl = typeof demoLogoFullUrlEnv === "string" && demoLogoFullUrlEnv.trim().length > 0 ? demoLogoFullUrlEnv.trim() : null
const demoLogoFullUrlConfigured = typeof demoLogoFullUrlEnv === "string"
const demoBrandName = import.meta.env.VITE_DEMO_BRAND_NAME
const demoBrandShortName = import.meta.env.VITE_DEMO_BRAND_SHORT_NAME

export const defaultPublicConfig: PublicAppConfig = {
  displayName: demoBrandName ?? "碳数据收集与管理系统",
  shortName: demoBrandShortName ?? "CD",
  description: "支持 Scope 1/2/3 碳排放数据的采集、审核与统计分析。",
  brandMarkUrl: demoLogoFullUrlConfigured ? demoLogoFullUrl : null,
  faviconUrl: null,
  authMode: "cookie-session",
  captchaProvider: null,
  captchaEnabled: false,
  captchaChallengeUrl: null,
  captchaSiteKey: null,
}

const demoBrandOverride: Partial<PublicAppConfig> = {
  ...(typeof demoBrandName === "string" ? { displayName: demoBrandName } : {}),
  ...(typeof demoBrandShortName === "string" ? { shortName: demoBrandShortName } : {}),
  ...(demoLogoFullUrlConfigured ? { brandMarkUrl: demoLogoFullUrl } : {}),
}

async function fetchPublicConfig(): Promise<PublicAppConfig> {
  const apiUrl = getApiBaseUrl()
  const response = await fetch(`${apiUrl}/api/config/public`)

  if (!response.ok) {
    return defaultPublicConfig
  }

  return { ...defaultPublicConfig, ...(await response.json()), ...demoBrandOverride }
}

export function usePublicConfig() {
  const query = useQuery({
    queryKey: ["public-config"],
    queryFn: fetchPublicConfig,
    staleTime: 1000 * 60 * 5,
    retry: false,
  })

  return {
    ...query,
    config: query.data ?? defaultPublicConfig,
  }
}
