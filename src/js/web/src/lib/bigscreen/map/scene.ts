import type {
  BigscreenLoadedMapScene,
  BigscreenMapInitialCamera,
  BigscreenMapLngLat,
  BigscreenMapPadding,
  BigscreenMapSceneConfig,
  BigscreenWarehouseFeature,
  BigscreenWarehouseFeatureCollection,
  BigscreenWarehouseFeatureProperties,
} from "@/lib/bigscreen/map/types"

const DEFAULT_PADDING: BigscreenMapPadding = {
  top: 88,
  right: 96,
  bottom: 112,
  left: 96,
}

const DEFAULT_STATUS_COLORS: Record<string, string> = {
  normal: "#38bdf8",
  active: "#22c55e",
  warning: "#f59e0b",
}

type PartialSceneConfig = Partial<Omit<BigscreenMapSceneConfig, "cameraFallback" | "statusColors" | "center">> & {
  center?: BigscreenMapLngLat
  cameraFallback?: Partial<BigscreenMapSceneConfig["cameraFallback"]>
  statusColors?: Record<string, string>
}

function isLngLat(value: unknown): value is BigscreenMapLngLat {
  return Array.isArray(value) && value.length === 2 && value.every((item) => typeof item === "number" && Number.isFinite(item))
}

function normalizePadding(value?: Partial<BigscreenMapPadding>): BigscreenMapPadding {
  return {
    top: value?.top ?? DEFAULT_PADDING.top,
    right: value?.right ?? DEFAULT_PADDING.right,
    bottom: value?.bottom ?? DEFAULT_PADDING.bottom,
    left: value?.left ?? DEFAULT_PADDING.left,
  }
}

function normalizeWarehouseFeatureProperties(properties: Partial<BigscreenWarehouseFeatureProperties> | undefined, index: number): BigscreenWarehouseFeatureProperties {
  return {
    id: properties?.id?.trim() || `warehouse-${index + 1}`,
    name: properties?.name?.trim() || `Warehouse ${index + 1}`,
    status: properties?.status?.trim() || "normal",
    height_m: typeof properties?.height_m === "number" && Number.isFinite(properties.height_m) ? properties.height_m : 24,
    accent: properties?.accent?.trim() || undefined,
  }
}

function normalizeWarehouseFeature(feature: BigscreenWarehouseFeature, index: number): BigscreenWarehouseFeature {
  return {
    ...feature,
    properties: normalizeWarehouseFeatureProperties(feature.properties, index),
  }
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to load ${url}: HTTP ${response.status}`)
  }
  return (await response.json()) as T
}

export function resolveBigscreenPublicUrl(path: string) {
  const baseUrl = import.meta.env.BASE_URL || "/"
  return `${baseUrl}${path.replace(/^\//u, "")}`
}

export function normalizeBigscreenMapSceneConfig(input: PartialSceneConfig): BigscreenMapSceneConfig {
  const center = isLngLat(input.center) ? input.center : ([119.890793, 32.421059] satisfies BigscreenMapLngLat)

  return {
    engine: input.engine === "maplibre" ? "maplibre" : "maplibre",
    coordinateSystem: input.coordinateSystem === "gcj02" ? "gcj02" : "wgs84",
    center,
    interactive: input.interactive ?? false,
    styleUrl: input.styleUrl?.trim() || "./style.json",
    warehouseDataUrl: input.warehouseDataUrl?.trim() || "./warehouses.geojson",
    attributionLabel: input.attributionLabel?.trim() || undefined,
    cameraFallback: {
      center: isLngLat(input.cameraFallback?.center) ? input.cameraFallback.center : center,
      zoom: input.cameraFallback?.zoom ?? 16.3,
      bearing: input.cameraFallback?.bearing ?? -18,
      pitch: input.cameraFallback?.pitch ?? 52,
      maxZoom: input.cameraFallback?.maxZoom ?? 17.1,
      padding: normalizePadding(input.cameraFallback?.padding),
    },
    statusColors: {
      ...DEFAULT_STATUS_COLORS,
      ...input.statusColors,
    },
  }
}

export function normalizeWarehouseFeatureCollection(input: Partial<BigscreenWarehouseFeatureCollection> | undefined): BigscreenWarehouseFeatureCollection {
  const features = Array.isArray(input?.features) ? input.features : []
  return {
    type: "FeatureCollection",
    features: features.map((feature, index) => normalizeWarehouseFeature(feature as BigscreenWarehouseFeature, index)),
  }
}

export function resolveSceneAssetUrl(url: string, manifestUrl: string) {
  return new URL(url, new URL(manifestUrl, window.location.origin)).toString()
}

export async function loadBigscreenMapScene(manifestUrl: string): Promise<BigscreenLoadedMapScene> {
  const rawConfig = await fetchJson<PartialSceneConfig>(manifestUrl)
  const config = normalizeBigscreenMapSceneConfig(rawConfig)
  const styleUrl = resolveSceneAssetUrl(config.styleUrl, manifestUrl)
  const warehouseDataUrl = resolveSceneAssetUrl(config.warehouseDataUrl, manifestUrl)
  const warehouses = normalizeWarehouseFeatureCollection(await fetchJson<BigscreenWarehouseFeatureCollection>(warehouseDataUrl))

  return {
    manifestUrl,
    config: {
      ...config,
      styleUrl,
      warehouseDataUrl,
    },
    warehouses,
  }
}

export function getWarehouseStatusColor(config: BigscreenMapSceneConfig, status: string) {
  return config.statusColors[status] ?? config.statusColors.normal ?? DEFAULT_STATUS_COLORS.normal
}

export function buildWarehouseStatusColorExpression(config: BigscreenMapSceneConfig) {
  const entries = Object.entries(config.statusColors).flat()
  return ["match", ["coalesce", ["get", "status"], "normal"], ...entries, config.statusColors.normal ?? DEFAULT_STATUS_COLORS.normal]
}

export function resolveWarehouseBounds(warehouses: BigscreenWarehouseFeatureCollection): [BigscreenMapLngLat, BigscreenMapLngLat] | null {
  let minLng = Number.POSITIVE_INFINITY
  let minLat = Number.POSITIVE_INFINITY
  let maxLng = Number.NEGATIVE_INFINITY
  let maxLat = Number.NEGATIVE_INFINITY

  for (const feature of warehouses.features) {
    const coordinateGroups = feature.geometry.type === "Polygon" ? [feature.geometry.coordinates] : feature.geometry.coordinates
    for (const polygon of coordinateGroups) {
      for (const ring of polygon) {
        for (const [lng, lat] of ring) {
          minLng = Math.min(minLng, lng)
          minLat = Math.min(minLat, lat)
          maxLng = Math.max(maxLng, lng)
          maxLat = Math.max(maxLat, lat)
        }
      }
    }
  }

  if (!Number.isFinite(minLng) || !Number.isFinite(minLat) || !Number.isFinite(maxLng) || !Number.isFinite(maxLat)) {
    return null
  }

  return [
    [minLng, minLat],
    [maxLng, maxLat],
  ]
}

export function resolveInitialCamera(config: BigscreenMapSceneConfig, warehouses: BigscreenWarehouseFeatureCollection): BigscreenMapInitialCamera {
  const bounds = resolveWarehouseBounds(warehouses)
  if (bounds) {
    return {
      kind: "bounds",
      bounds,
      maxZoom: config.cameraFallback.maxZoom,
      bearing: config.cameraFallback.bearing,
      pitch: config.cameraFallback.pitch,
      padding: config.cameraFallback.padding,
    }
  }

  return {
    kind: "fallback",
    center: config.cameraFallback.center,
    zoom: config.cameraFallback.zoom,
    bearing: config.cameraFallback.bearing,
    pitch: config.cameraFallback.pitch,
  }
}
