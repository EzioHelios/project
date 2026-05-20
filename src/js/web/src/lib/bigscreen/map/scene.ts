import type {
  BigscreenLoadedScene,
  BigscreenSceneConfig,
  BigscreenSceneCoordinateSystem,
  BigscreenSceneImageryProviderConfig,
  BigscreenSceneInitialCamera,
  BigscreenSceneLngLat,
  BigscreenScenePadding,
  BigscreenSceneTerrainProviderConfig,
  BigscreenWarehouseFeature,
  BigscreenWarehouseFeatureCollection,
  BigscreenWarehouseFeatureProperties,
  BigscreenWarehouseLayerConfig,
} from "@/lib/bigscreen/map/types"

const DEFAULT_CENTER = [119.890793, 32.421059] satisfies BigscreenSceneLngLat

const DEFAULT_PADDING: BigscreenScenePadding = {
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

const DEFAULT_IMAGERY_PROVIDER: BigscreenSceneImageryProviderConfig = {
  kind: "url-template",
  url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  credit: "© OpenStreetMap contributors",
  maximumLevel: 19,
}

const DEFAULT_TERRAIN_PROVIDER: BigscreenSceneTerrainProviderConfig = {
  kind: "ellipsoid",
}

type PartialSceneConfig = Partial<Omit<BigscreenSceneConfig, "cameraHome" | "warehouseLayer" | "futureLayers" | "center" | "imageryProvider" | "terrainProvider" | "viewerOptions">> & {
  engine?: "maplibre"
  center?: BigscreenSceneLngLat
  imageryProvider?: Partial<BigscreenSceneImageryProviderConfig>
  terrainProvider?: Partial<Extract<BigscreenSceneTerrainProviderConfig, { kind: "cesium-terrain" }>> | { kind?: "ellipsoid" }
  cameraHome?: Partial<BigscreenSceneConfig["cameraHome"]>
  viewerOptions?: Partial<BigscreenSceneConfig["viewerOptions"]>
  warehouseLayer?: Partial<BigscreenWarehouseLayerConfig>
  futureLayers?: Partial<BigscreenSceneConfig["futureLayers"]>
  styleUrl?: string
  warehouseDataUrl?: string
  statusColors?: Record<string, string>
  cameraFallback?: {
    center?: BigscreenSceneLngLat
    zoom?: number
    bearing?: number
    pitch?: number
    maxZoom?: number
    padding?: Partial<BigscreenScenePadding>
  }
}

function isLngLat(value: unknown): value is BigscreenSceneLngLat {
  return Array.isArray(value) && value.length === 2 && value.every((item) => typeof item === "number" && Number.isFinite(item))
}

function normalizePadding(value?: Partial<BigscreenScenePadding>): BigscreenScenePadding {
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

function normalizeImageryProvider(input?: Partial<BigscreenSceneImageryProviderConfig>): BigscreenSceneImageryProviderConfig {
  return {
    kind: "url-template",
    url: input?.url?.trim() || DEFAULT_IMAGERY_PROVIDER.url,
    credit: input?.credit?.trim() || DEFAULT_IMAGERY_PROVIDER.credit,
    minimumLevel: input?.minimumLevel,
    maximumLevel: input?.maximumLevel ?? DEFAULT_IMAGERY_PROVIDER.maximumLevel,
    subdomains: input?.subdomains?.length ? input.subdomains : undefined,
  }
}

function normalizeTerrainProvider(input?: PartialSceneConfig["terrainProvider"]): BigscreenSceneTerrainProviderConfig {
  if (input?.kind === "cesium-terrain") {
    return {
      kind: "cesium-terrain",
      url: input.url?.trim() || "",
      requestVertexNormals: input.requestVertexNormals ?? true,
      requestWaterMask: input.requestWaterMask ?? false,
      credit: input.credit?.trim() || undefined,
    }
  }

  return DEFAULT_TERRAIN_PROVIDER
}

function normalizeWarehouseLayer(input: PartialSceneConfig, center: BigscreenSceneLngLat): BigscreenWarehouseLayerConfig {
  const statusColors = {
    ...DEFAULT_STATUS_COLORS,
    ...input.statusColors,
    ...input.warehouseLayer?.statusColors,
  }

  return {
    dataUrl: input.warehouseLayer?.dataUrl?.trim() || input.warehouseDataUrl?.trim() || "./warehouses.geojson",
    statusColors,
    fillOpacity: input.warehouseLayer?.fillOpacity ?? 0.18,
    extrusionOpacity: input.warehouseLayer?.extrusionOpacity ?? 0.88,
    outlineColor: input.warehouseLayer?.outlineColor?.trim() || "#d7f7ff",
    outlineOpacity: input.warehouseLayer?.outlineOpacity ?? 0.72,
    outlineWidth: input.warehouseLayer?.outlineWidth ?? 1.25,
  }
}

export function resolveBigscreenPublicUrl(path: string) {
  const baseUrl = import.meta.env.BASE_URL || "/"
  return `${baseUrl}${path.replace(/^\//u, "")}`
}

export function normalizeBigscreenSceneConfig(input: PartialSceneConfig): BigscreenSceneConfig {
  const center = isLngLat(input.center) ? input.center : DEFAULT_CENTER
  const sceneEngine = input.sceneEngine ?? (input.engine === "maplibre" ? "maplibre" : "cesium")
  const fitPadding = normalizePadding(input.cameraHome?.fitPadding ?? input.cameraFallback?.padding)

  return {
    sceneEngine,
    coordinateSystem: (input.coordinateSystem === "gcj02" ? "gcj02" : "wgs84") satisfies BigscreenSceneCoordinateSystem,
    center,
    interactive: input.interactive ?? true,
    attributionLabel: input.attributionLabel?.trim() || DEFAULT_IMAGERY_PROVIDER.credit,
    imageryProvider: normalizeImageryProvider(input.imageryProvider),
    terrainProvider: normalizeTerrainProvider(input.terrainProvider),
    cameraHome: {
      center: isLngLat(input.cameraHome?.center) ? input.cameraHome.center : isLngLat(input.cameraFallback?.center) ? input.cameraFallback.center : center,
      height: input.cameraHome?.height ?? 1450,
      heading: input.cameraHome?.heading ?? input.cameraFallback?.bearing ?? -18,
      pitch: input.cameraHome?.pitch ?? input.cameraFallback?.pitch ?? -42,
      roll: input.cameraHome?.roll ?? 0,
      fitPadding,
    },
    viewerOptions: {
      sceneMode: "3d",
      shadows: input.viewerOptions?.shadows ?? false,
      requestRenderMode: input.viewerOptions?.requestRenderMode ?? false,
      maximumRenderTimeChange: input.viewerOptions?.maximumRenderTimeChange ?? 0,
      msaaSamples: input.viewerOptions?.msaaSamples ?? 4,
    },
    warehouseLayer: normalizeWarehouseLayer(input, center),
    futureLayers: {
      tileset: input.futureLayers?.tileset ?? [],
      splat: input.futureLayers?.splat ?? [],
      pointCloud: input.futureLayers?.pointCloud ?? [],
    },
    maplibre: {
      styleUrl: input.styleUrl?.trim() || "./style.json",
      cameraFallback: {
        center: isLngLat(input.cameraFallback?.center) ? input.cameraFallback.center : center,
        zoom: input.cameraFallback?.zoom ?? 16.45,
        bearing: input.cameraFallback?.bearing ?? -18,
        pitch: input.cameraFallback?.pitch ?? 54,
        maxZoom: input.cameraFallback?.maxZoom ?? 17.1,
        padding: fitPadding,
      },
    },
  }
}

export function normalizeBigscreenMapSceneConfig(input: PartialSceneConfig) {
  return normalizeBigscreenSceneConfig(input)
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

export function resolveWarehouseDataUrl(config: BigscreenSceneConfig) {
  return config.warehouseLayer.dataUrl
}

export async function loadBigscreenScene(manifestUrl: string): Promise<BigscreenLoadedScene> {
  const rawConfig = await fetchJson<PartialSceneConfig>(manifestUrl)
  const config = normalizeBigscreenSceneConfig(rawConfig)
  const imageryProvider =
    config.imageryProvider.kind === "url-template"
      ? {
          ...config.imageryProvider,
          url: resolveSceneAssetUrl(config.imageryProvider.url, manifestUrl),
        }
      : config.imageryProvider
  const terrainProvider =
    config.terrainProvider.kind === "cesium-terrain"
      ? {
          ...config.terrainProvider,
          url: resolveSceneAssetUrl(config.terrainProvider.url, manifestUrl),
        }
      : config.terrainProvider
  const warehouseDataUrl = resolveSceneAssetUrl(resolveWarehouseDataUrl(config), manifestUrl)
  const maplibre =
    config.maplibre
      ? {
          ...config.maplibre,
          styleUrl: resolveSceneAssetUrl(config.maplibre.styleUrl, manifestUrl),
        }
      : undefined
  const warehouses = normalizeWarehouseFeatureCollection(await fetchJson<BigscreenWarehouseFeatureCollection>(warehouseDataUrl))

  return {
    manifestUrl,
    config: {
      ...config,
      imageryProvider,
      terrainProvider,
      warehouseLayer: {
        ...config.warehouseLayer,
        dataUrl: warehouseDataUrl,
      },
      maplibre,
    },
    warehouses,
  }
}

export async function loadBigscreenMapScene(manifestUrl: string) {
  return loadBigscreenScene(manifestUrl)
}

export function getWarehouseStatusColor(config: BigscreenSceneConfig, status: string) {
  return config.warehouseLayer.statusColors[status] ?? config.warehouseLayer.statusColors.normal ?? DEFAULT_STATUS_COLORS.normal
}

export function buildWarehouseStatusColorExpression(config: BigscreenSceneConfig) {
  const entries = Object.entries(config.warehouseLayer.statusColors).flat()
  return ["match", ["coalesce", ["get", "status"], "normal"], ...entries, config.warehouseLayer.statusColors.normal ?? DEFAULT_STATUS_COLORS.normal]
}

export function resolveWarehouseBounds(warehouses: BigscreenWarehouseFeatureCollection): [BigscreenSceneLngLat, BigscreenSceneLngLat] | null {
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

export function resolveInitialCamera(config: BigscreenSceneConfig, warehouses: BigscreenWarehouseFeatureCollection): BigscreenSceneInitialCamera {
  const bounds = resolveWarehouseBounds(warehouses)
  if (bounds) {
    return {
      kind: "bounds",
      bounds,
      padding: config.cameraHome.fitPadding,
    }
  }

  return {
    kind: "fallback",
    center: config.cameraHome.center,
    height: config.cameraHome.height,
    heading: config.cameraHome.heading,
    pitch: config.cameraHome.pitch,
    roll: config.cameraHome.roll,
  }
}
