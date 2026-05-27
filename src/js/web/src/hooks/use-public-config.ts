import { useQuery } from "@tanstack/react-query"
import { getApiBaseUrl } from "@/lib/api-base-url"

export interface PublicAppConfig {
  displayName: string
  shortName: string
  description: string
  authMode: "cookie-session"
  captchaProvider: string | null
  captchaEnabled: boolean
  captchaChallengeUrl: string | null
  captchaSiteKey: string | null
}

export const defaultPublicConfig: PublicAppConfig = {
  displayName: "碳数据收集与管理系统",
  shortName: "CD",
  description: "支持 Scope 1/2/3 碳排放数据的采集、审核与统计分析。",
  authMode: "cookie-session",
  captchaProvider: null,
  captchaEnabled: false,
  captchaChallengeUrl: null,
  captchaSiteKey: null,
}

async function fetchPublicConfig(): Promise<PublicAppConfig> {
  const apiUrl = getApiBaseUrl()
  const response = await fetch(`${apiUrl}/api/config/public`)

  if (!response.ok) {
    return defaultPublicConfig
  }

  return { ...defaultPublicConfig, ...(await response.json()) }
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
