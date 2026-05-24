const ENVIRONMENT_CACHE_KEY = "bigscreen.environment.cache.v1"
const CITY_CACHE_MAX_AGE_MS = 1000 * 60 * 60 * 24
const WEATHER_CACHE_MAX_AGE_MS = 1000 * 60 * 30

type BigscreenEnvironmentCache = {
  city: string | null
  weather: string | null
  latitude: number | null
  longitude: number | null
  cityResolvedAt: number | null
  weatherResolvedAt: number | null
}

export type BigscreenEnvironment = {
  city: string
  weather: string
}

type ReverseGeocodeResponse = {
  address?: {
    city?: string
    town?: string
    county?: string
    municipality?: string
    city_district?: string
    state_district?: string
    state?: string
  }
}

type OpenMeteoResponse = {
  current?: {
    temperature_2m?: number
    weather_code?: number
  }
}

function createEmptyCache(): BigscreenEnvironmentCache {
  return {
    city: null,
    weather: null,
    latitude: null,
    longitude: null,
    cityResolvedAt: null,
    weatherResolvedAt: null,
  }
}

function readEnvironmentCache(): BigscreenEnvironmentCache {
  if (typeof window === "undefined") {
    return createEmptyCache()
  }

  try {
    const raw = window.localStorage.getItem(ENVIRONMENT_CACHE_KEY)
    if (!raw) {
      return createEmptyCache()
    }

    const parsed = JSON.parse(raw) as Partial<BigscreenEnvironmentCache>
    return {
      ...createEmptyCache(),
      ...parsed,
    }
  } catch {
    return createEmptyCache()
  }
}

function writeEnvironmentCache(cache: BigscreenEnvironmentCache) {
  if (typeof window === "undefined") {
    return
  }

  try {
    window.localStorage.setItem(ENVIRONMENT_CACHE_KEY, JSON.stringify(cache))
  } catch {
    // Ignore storage write failures and continue with live data in memory.
  }
}

function isFresh(timestamp: number | null, maxAgeMs: number) {
  return typeof timestamp === "number" && Date.now() - timestamp < maxAgeMs
}

function coordinatesChanged(cache: BigscreenEnvironmentCache, latitude: number, longitude: number) {
  if (cache.latitude === null || cache.longitude === null) {
    return true
  }

  return Math.abs(cache.latitude - latitude) > 0.01 || Math.abs(cache.longitude - longitude) > 0.01
}

function getCurrentPosition() {
  return new Promise<GeolocationPosition>((resolve, reject) => {
    if (typeof window === "undefined" || !("geolocation" in navigator)) {
      reject(new Error("geolocation unavailable"))
      return
    }

    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: false,
      timeout: 8000,
      maximumAge: 1000 * 60 * 10,
    })
  })
}

function normalizeCityLabel(value: string | null | undefined) {
  if (!value) {
    return null
  }

  return value.replace(/\s+/g, "").trim() || null
}

function resolveWeatherLabel(weatherCode?: number) {
  const labelMap: Record<number, string> = {
    0: "晴",
    1: "少云",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "冻雾",
    51: "毛毛雨",
    53: "小雨",
    55: "中雨",
    56: "冻雨",
    57: "冻雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "冰粒",
    80: "阵雨",
    81: "强阵雨",
    82: "暴雨",
    85: "阵雪",
    86: "强阵雪",
    95: "雷雨",
    96: "雷雨冰雹",
    99: "强雷雨冰雹",
  }

  return weatherCode === undefined ? "天气未知" : (labelMap[weatherCode] ?? "天气未知")
}

async function reverseGeocodeCity(latitude: number, longitude: number) {
  const url = new URL("https://nominatim.openstreetmap.org/reverse")
  url.searchParams.set("lat", latitude.toString())
  url.searchParams.set("lon", longitude.toString())
  url.searchParams.set("format", "jsonv2")
  url.searchParams.set("zoom", "10")
  url.searchParams.set("addressdetails", "1")
  url.searchParams.set("accept-language", "zh-CN")

  const response = await fetch(url.toString(), {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  })
  if (!response.ok) {
    throw new Error(`reverse geocode failed: ${response.status}`)
  }

  const payload = (await response.json()) as ReverseGeocodeResponse
  const address = payload.address
  return normalizeCityLabel(address?.city ?? address?.municipality ?? address?.county ?? address?.city_district ?? address?.state_district ?? address?.town ?? address?.state)
}

async function fetchWeatherSummary(latitude: number, longitude: number) {
  const url = new URL("https://api.open-meteo.com/v1/forecast")
  url.searchParams.set("latitude", latitude.toString())
  url.searchParams.set("longitude", longitude.toString())
  url.searchParams.set("current", "temperature_2m,weather_code")
  url.searchParams.set("timezone", "auto")

  const response = await fetch(url.toString(), {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  })
  if (!response.ok) {
    throw new Error(`weather fetch failed: ${response.status}`)
  }

  const payload = (await response.json()) as OpenMeteoResponse
  const temperature = payload.current?.temperature_2m
  const label = resolveWeatherLabel(payload.current?.weather_code)
  return typeof temperature === "number" ? `${label} ${Math.round(temperature)}°C` : label
}

export async function getBigscreenEnvironment(options: { weatherEnabled: boolean }): Promise<BigscreenEnvironment> {
  const cache = readEnvironmentCache()
  const workingCache = { ...cache }
  let liveCoordinates: { latitude: number; longitude: number } | null = null

  try {
    const position = await getCurrentPosition()
    liveCoordinates = {
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
    }
    workingCache.latitude = liveCoordinates.latitude
    workingCache.longitude = liveCoordinates.longitude
  } catch {
    if (cache.latitude !== null && cache.longitude !== null) {
      liveCoordinates = {
        latitude: cache.latitude,
        longitude: cache.longitude,
      }
    }
  }

  const shouldRefreshLocation =
    liveCoordinates !== null && (!isFresh(cache.cityResolvedAt, CITY_CACHE_MAX_AGE_MS) || coordinatesChanged(cache, liveCoordinates.latitude, liveCoordinates.longitude))
  const shouldRefreshWeather =
    options.weatherEnabled &&
    liveCoordinates !== null &&
    (!isFresh(cache.weatherResolvedAt, WEATHER_CACHE_MAX_AGE_MS) || coordinatesChanged(cache, liveCoordinates.latitude, liveCoordinates.longitude))

  if (shouldRefreshLocation && liveCoordinates) {
    try {
      const city = await reverseGeocodeCity(liveCoordinates.latitude, liveCoordinates.longitude)
      if (city) {
        workingCache.city = city
        workingCache.cityResolvedAt = Date.now()
      }
    } catch {
      // Keep cache fallback below.
    }
  }

  if (shouldRefreshWeather && liveCoordinates) {
    try {
      workingCache.weather = await fetchWeatherSummary(liveCoordinates.latitude, liveCoordinates.longitude)
      workingCache.weatherResolvedAt = Date.now()
    } catch {
      // Keep cache fallback below.
    }
  }

  writeEnvironmentCache(workingCache)

  return {
    city: workingCache.city ?? cache.city ?? "--",
    weather: options.weatherEnabled ? (workingCache.weather ?? cache.weather ?? "--") : "--",
  }
}
