import type {
  BigscreenLoadedScene,
  BigscreenSceneBuildingLayerConfig,
  BigscreenSceneConfig,
  BigscreenSceneCoordinateSystem,
  BigscreenSceneEnvironmentConfig,
  BigscreenSceneFeatureLayerConfig,
  BigscreenSceneImageryProviderConfig,
  BigscreenSceneInitialCamera,
  BigscreenSceneLngLat,
  BigscreenSceneModelAsset,
  BigscreenSceneModelLayerConfig,
  BigscreenScenePadding,
  BigscreenSceneSiteLayerConfig,
  BigscreenSceneTerrainProviderConfig,
  BigscreenSceneZoneLayerConfig,
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
  alpha: 0.42,
  brightness: 0.7,
  contrast: 0.92,
  saturation: 0.18,
  gamma: 0.96,
}

const DEFAULT_TERRAIN_PROVIDER: BigscreenSceneTerrainProviderConfig = {
  kind: "ellipsoid",
}

const DEFAULT_ENVIRONMENT: BigscreenSceneEnvironmentConfig = {
  backgroundColor: "#06151b",
  globeBaseColor: "#102a31",
  lighting: true,
  dynamicAtmosphereLighting: true,
  clockTime: "2026-04-18T23:20:00Z",
  fog: {
    enabled: true,
    density: 0.00018,
    minimumBrightness: 0.12,
    screenSpaceErrorFactor: 2.2,
  },
  ambientOcclusion: {
    enabled: true,
    intensity: 1.6,
    bias: 0.2,
    lengthCap: 0.22,
    directionCount: 6,
    stepCount: 20,
  },
}

type PartialSceneConfig = Partial<
  Omit<
    BigscreenSceneConfig,
    | "cameraHome"
    | "warehouseLayer"
    | "futureLayers"
    | "center"
    | "imageryProvider"
    | "terrainProvider"
    | "viewerOptions"
    | "environment"
    | "siteLayer"
    | "buildingLayer"
    | "zoneLayer"
    | "modelLayer"
  >
> & {
  extends?: string
  engine?: "maplibre"
  center?: BigscreenSceneLngLat
  imageryProvider?: Partial<BigscreenSceneImageryProviderConfig>
  terrainProvider?: Partial<Extract<BigscreenSceneTerrainProviderConfig, { kind: "cesium-terrain" }>> | { kind?: "ellipsoid" }
  cameraHome?: Partial<BigscreenSceneConfig["cameraHome"]>
  viewerOptions?: Partial<BigscreenSceneConfig["viewerOptions"]>
  environment?: Partial<Omit<BigscreenSceneEnvironmentConfig, "fog" | "ambientOcclusion">> & {
    fog?: Partial<BigscreenSceneEnvironmentConfig["fog"]>
    ambientOcclusion?: Partial<BigscreenSceneEnvironmentConfig["ambientOcclusion"]>
  }
  siteLayer?: Partial<BigscreenSceneSiteLayerConfig>
  buildingLayer?: Partial<BigscreenSceneBuildingLayerConfig>
  zoneLayer?: Partial<BigscreenSceneZoneLayerConfig>
  modelLayer?: Partial<Omit<BigscreenSceneModelLayerConfig, "assets">> & {
    assets?: Partial<BigscreenSceneModelAsset>[]
  }
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

export class BigscreenSceneResourceError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly resourceKind: "candidate-manifest" | "inherited-manifest" | "asset" = "asset",
  ) {
    super(message)
    this.name = "BigscreenSceneResourceError"
  }
}

async function fetchJson<T>(url: string, resourceKind: BigscreenSceneResourceError["resourceKind"] = "asset"): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new BigscreenSceneResourceError(`Failed to load ${url}: HTTP ${response.status}`, response.status, resourceKind)
  }

  const body = await response.text()
  const contentType = response.headers.get("content-type")?.toLowerCase() ?? ""
  const isHtmlFallback = contentType.includes("text/html") || /^\s*(?:<!doctype\s+html|<html[\s>])/iu.test(body)
  if (isHtmlFallback) {
    // Vite and some SPA hosts return index.html with HTTP 200 for a missing
    // public asset. Treat that response as an absent top-level candidate so
    // tenant lookup can continue, but never hide a broken inherited manifest
    // or a missing scene asset behind the platform fallback.
    const status = resourceKind === "candidate-manifest" ? 404 : response.status
    throw new BigscreenSceneResourceError(`Expected JSON from ${url}, received the SPA HTML fallback`, status, resourceKind)
  }

  try {
    return JSON.parse(body) as T
  } catch (error) {
    throw new BigscreenSceneResourceError(`Invalid JSON in ${url}: ${error instanceof Error ? error.message : "unknown parse error"}`, response.status, resourceKind)
  }
}

function normalizeImageryProvider(input?: Partial<BigscreenSceneImageryProviderConfig>): BigscreenSceneImageryProviderConfig {
  return {
    kind: "url-template",
    url: input?.url?.trim() || DEFAULT_IMAGERY_PROVIDER.url,
    credit: input?.credit?.trim() || DEFAULT_IMAGERY_PROVIDER.credit,
    minimumLevel: input?.minimumLevel,
    maximumLevel: input?.maximumLevel ?? DEFAULT_IMAGERY_PROVIDER.maximumLevel,
    subdomains: input?.subdomains?.length ? input.subdomains : undefined,
    alpha: input?.alpha ?? DEFAULT_IMAGERY_PROVIDER.alpha,
    brightness: input?.brightness ?? DEFAULT_IMAGERY_PROVIDER.brightness,
    contrast: input?.contrast ?? DEFAULT_IMAGERY_PROVIDER.contrast,
    saturation: input?.saturation ?? DEFAULT_IMAGERY_PROVIDER.saturation,
    gamma: input?.gamma ?? DEFAULT_IMAGERY_PROVIDER.gamma,
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

function normalizeWarehouseLayer(input: PartialSceneConfig, _center: BigscreenSceneLngLat): BigscreenWarehouseLayerConfig {
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

function normalizeFeatureLayer(input: Partial<BigscreenSceneFeatureLayerConfig> | undefined, dataUrl: string, outlineColor: string): BigscreenSceneFeatureLayerConfig | undefined {
  if (!input?.dataUrl?.trim() && !input?.show) {
    return undefined
  }

  return {
    dataUrl: input?.dataUrl?.trim() || dataUrl,
    show: input?.show ?? true,
    outlineColor: input?.outlineColor?.trim() || outlineColor,
    outlineOpacity: input?.outlineOpacity ?? 0.72,
    outlineWidth: input?.outlineWidth ?? 1,
  }
}

function normalizeBuildingLayer(input: Partial<BigscreenSceneBuildingLayerConfig> | undefined): BigscreenSceneBuildingLayerConfig | undefined {
  const baseLayer = normalizeFeatureLayer(input, "./buildings.geojson", "#dcfbff")
  if (!baseLayer) {
    return undefined
  }

  return {
    ...baseLayer,
    defaultHeight: input?.defaultHeight ?? 8,
    defaultOpacity: input?.defaultOpacity ?? 0.96,
    defaultWallColor: input?.defaultWallColor?.trim() || "#a9b9bb",
    defaultRoofColor: input?.defaultRoofColor?.trim() || "#c8d3d4",
    featureColorMode: input?.featureColorMode === "feature" ? "feature" : "uniform",
    roofEdgeColor: input?.roofEdgeColor?.trim() || "#8bc4ca",
    roofEdgeOpacity: input?.roofEdgeOpacity ?? 0.44,
    showLabels: input?.showLabels ?? true,
    labelDistance: input?.labelDistance ?? 1200,
    solarPanelColor: input?.solarPanelColor?.trim() || "#123f58",
    solarPanelStrokeColor: input?.solarPanelStrokeColor?.trim() || "#4da8ba",
  }
}

function normalizeSiteLayer(input: Partial<BigscreenSceneSiteLayerConfig> | undefined): BigscreenSceneSiteLayerConfig | undefined {
  const baseLayer = normalizeFeatureLayer(input, "./site.geojson", "#58777b")
  if (!baseLayer) {
    return undefined
  }
  return {
    ...baseLayer,
    featureColorMode: input?.featureColorMode === "feature" ? "feature" : "palette",
    defaultColor: input?.defaultColor?.trim() || "#526568",
    typeColors: {
      concrete: "#526568",
      road: "#29393d",
      green: "#294d3d",
      reserved: "#3d554d",
      corridor: "#203a40",
      ...input?.typeColors,
    },
  }
}

function normalizeZoneLayer(input: Partial<BigscreenSceneZoneLayerConfig> | undefined): BigscreenSceneZoneLayerConfig | undefined {
  const baseLayer = normalizeFeatureLayer(input, "./zones.geojson", "#f8fdff")
  if (!baseLayer) {
    return undefined
  }

  return {
    ...baseLayer,
    defaultOpacity: input?.defaultOpacity ?? 0.26,
    defaultColor: input?.defaultColor?.trim() || "#2eb8a6",
    featureColorMode: input?.featureColorMode === "feature" ? "feature" : "uniform",
    defaultHeight: input?.defaultHeight ?? 0.55,
    surfaceHeight: input?.surfaceHeight ?? 14.2,
    showLabels: input?.showLabels ?? false,
  }
}

function normalizeEnvironment(input?: PartialSceneConfig["environment"]): BigscreenSceneEnvironmentConfig {
  return {
    backgroundColor: input?.backgroundColor?.trim() || DEFAULT_ENVIRONMENT.backgroundColor,
    globeBaseColor: input?.globeBaseColor?.trim() || DEFAULT_ENVIRONMENT.globeBaseColor,
    lighting: input?.lighting ?? DEFAULT_ENVIRONMENT.lighting,
    dynamicAtmosphereLighting: input?.dynamicAtmosphereLighting ?? DEFAULT_ENVIRONMENT.dynamicAtmosphereLighting,
    clockTime: input?.clockTime?.trim() || DEFAULT_ENVIRONMENT.clockTime,
    fog: {
      enabled: input?.fog?.enabled ?? DEFAULT_ENVIRONMENT.fog.enabled,
      density: input?.fog?.density ?? DEFAULT_ENVIRONMENT.fog.density,
      minimumBrightness: input?.fog?.minimumBrightness ?? DEFAULT_ENVIRONMENT.fog.minimumBrightness,
      screenSpaceErrorFactor: input?.fog?.screenSpaceErrorFactor ?? DEFAULT_ENVIRONMENT.fog.screenSpaceErrorFactor,
    },
    ambientOcclusion: {
      enabled: input?.ambientOcclusion?.enabled ?? DEFAULT_ENVIRONMENT.ambientOcclusion.enabled,
      intensity: input?.ambientOcclusion?.intensity ?? DEFAULT_ENVIRONMENT.ambientOcclusion.intensity,
      bias: input?.ambientOcclusion?.bias ?? DEFAULT_ENVIRONMENT.ambientOcclusion.bias,
      lengthCap: input?.ambientOcclusion?.lengthCap ?? DEFAULT_ENVIRONMENT.ambientOcclusion.lengthCap,
      directionCount: input?.ambientOcclusion?.directionCount ?? DEFAULT_ENVIRONMENT.ambientOcclusion.directionCount,
      stepCount: input?.ambientOcclusion?.stepCount ?? DEFAULT_ENVIRONMENT.ambientOcclusion.stepCount,
    },
  }
}

function normalizeModelLayer(input?: PartialSceneConfig["modelLayer"]): BigscreenSceneModelLayerConfig {
  const assets = (input?.assets ?? []).flatMap((asset, index): BigscreenSceneModelAsset[] => {
    const position = asset.position
    if (!Array.isArray(position) || position.length !== 3 || !position.every((value) => typeof value === "number" && Number.isFinite(value)) || !asset.url?.trim()) {
      return []
    }
    return [
      {
        id: asset.id?.trim() || `model-${index + 1}`,
        name: asset.name?.trim() || undefined,
        url: asset.url.trim(),
        show: asset.show ?? true,
        position: position as [number, number, number],
        heading: asset.heading ?? 0,
        pitch: asset.pitch ?? 0,
        roll: asset.roll ?? 0,
        scale: asset.scale ?? 1,
        minimumPixelSize: asset.minimumPixelSize ?? 0,
        maximumScale: asset.maximumScale,
        castShadows: asset.castShadows ?? true,
        receiveShadows: asset.receiveShadows ?? true,
        semanticType: asset.semanticType?.trim() || undefined,
        assetKey: asset.assetKey?.trim() || undefined,
        source:
          asset.source?.name?.trim() && asset.source.license?.trim()
            ? {
                name: asset.source.name.trim(),
                url: asset.source.url?.trim() || undefined,
                license: asset.source.license.trim(),
              }
            : undefined,
      },
    ]
  })

  return {
    show: input?.show ?? true,
    assets,
  }
}

export function resolveBigscreenPublicUrl(path: string) {
  if (/^https?:\/\//iu.test(path)) {
    return path
  }
  const baseUrl = import.meta.env.BASE_URL || "/"
  return `${baseUrl}${path.replace(/^\//u, "")}`
}

export function normalizeBigscreenSceneConfig(input: PartialSceneConfig): BigscreenSceneConfig {
  const center = isLngLat(input.center) ? input.center : DEFAULT_CENTER
  const sceneEngine = input.sceneEngine ?? (input.engine === "maplibre" ? "maplibre" : "cesium")
  const legacyCamera = input.maplibre?.cameraFallback ?? input.cameraFallback
  const fitPadding = normalizePadding(input.cameraHome?.fitPadding ?? legacyCamera?.padding)

  return {
    sceneId: input.sceneId?.trim() || "industrial-campus",
    revision: input.revision?.trim() || "1",
    sceneEngine,
    coordinateSystem: (input.coordinateSystem === "gcj02" ? "gcj02" : "wgs84") satisfies BigscreenSceneCoordinateSystem,
    center,
    interactive: input.interactive ?? true,
    attributionLabel: input.attributionLabel?.trim() || DEFAULT_IMAGERY_PROVIDER.credit,
    imageryProvider: normalizeImageryProvider(input.imageryProvider),
    terrainProvider: normalizeTerrainProvider(input.terrainProvider),
    cameraHome: {
      center: isLngLat(input.cameraHome?.center) ? input.cameraHome.center : isLngLat(legacyCamera?.center) ? legacyCamera.center : center,
      height: input.cameraHome?.height ?? 1450,
      heading: input.cameraHome?.heading ?? legacyCamera?.bearing ?? -18,
      pitch: input.cameraHome?.pitch ?? legacyCamera?.pitch ?? -42,
      roll: input.cameraHome?.roll ?? 0,
      fitPadding,
    },
    viewerOptions: {
      sceneMode: "3d",
      shadows: input.viewerOptions?.shadows ?? false,
      requestRenderMode: input.viewerOptions?.requestRenderMode ?? false,
      maximumRenderTimeChange: input.viewerOptions?.maximumRenderTimeChange ?? 0,
      msaaSamples: input.viewerOptions?.msaaSamples ?? 4,
      useBrowserRecommendedResolution: input.viewerOptions?.useBrowserRecommendedResolution ?? false,
      resolutionScale: input.viewerOptions?.resolutionScale ?? 1,
      fxaa: input.viewerOptions?.fxaa ?? true,
      orderIndependentTranslucency: input.viewerOptions?.orderIndependentTranslucency ?? true,
      highDynamicRange: input.viewerOptions?.highDynamicRange ?? true,
    },
    environment: normalizeEnvironment(input.environment),
    siteLayer: normalizeSiteLayer(input.siteLayer),
    buildingLayer: normalizeBuildingLayer(input.buildingLayer),
    zoneLayer: normalizeZoneLayer(input.zoneLayer),
    modelLayer: normalizeModelLayer(input.modelLayer),
    warehouseLayer: normalizeWarehouseLayer(input, center),
    futureLayers: {
      tileset: input.futureLayers?.tileset ?? [],
      splat: input.futureLayers?.splat ?? [],
      pointCloud: input.futureLayers?.pointCloud ?? [],
    },
    maplibre: {
      styleUrl: input.maplibre?.styleUrl?.trim() || input.styleUrl?.trim() || "./style.json",
      cameraFallback: {
        center: isLngLat(legacyCamera?.center) ? legacyCamera.center : center,
        zoom: legacyCamera?.zoom ?? 16.45,
        bearing: legacyCamera?.bearing ?? -18,
        pitch: legacyCamera?.pitch ?? 54,
        maxZoom: legacyCamera?.maxZoom ?? 17.1,
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
  const resolved = new URL(url, new URL(manifestUrl, window.location.origin))
  if (!/^https?:$/u.test(resolved.protocol)) {
    throw new Error(`Unsupported scene asset protocol: ${resolved.protocol}`)
  }
  return resolved.toString()
}

function shouldResolveSceneAssetUrl(url: string) {
  return url.trim().toLowerCase() !== "none"
}

export function resolveWarehouseDataUrl(config: BigscreenSceneConfig) {
  return config.warehouseLayer.dataUrl
}

function mergeSceneConfig(base: PartialSceneConfig, override: PartialSceneConfig): PartialSceneConfig {
  return {
    ...base,
    ...override,
    imageryProvider: { ...base.imageryProvider, ...override.imageryProvider },
    terrainProvider: { ...base.terrainProvider, ...override.terrainProvider } as PartialSceneConfig["terrainProvider"],
    cameraHome: {
      ...base.cameraHome,
      ...override.cameraHome,
      fitPadding: override.cameraHome?.fitPadding ?? base.cameraHome?.fitPadding,
    },
    viewerOptions: { ...base.viewerOptions, ...override.viewerOptions },
    environment: {
      ...base.environment,
      ...override.environment,
      fog: { ...base.environment?.fog, ...override.environment?.fog },
      ambientOcclusion: { ...base.environment?.ambientOcclusion, ...override.environment?.ambientOcclusion },
    },
    siteLayer: override.siteLayer === undefined ? base.siteLayer : { ...base.siteLayer, ...override.siteLayer },
    buildingLayer: override.buildingLayer === undefined ? base.buildingLayer : { ...base.buildingLayer, ...override.buildingLayer },
    zoneLayer: override.zoneLayer === undefined ? base.zoneLayer : { ...base.zoneLayer, ...override.zoneLayer },
    modelLayer: {
      ...base.modelLayer,
      ...override.modelLayer,
      assets: override.modelLayer?.assets ?? base.modelLayer?.assets,
    },
    warehouseLayer: { ...base.warehouseLayer, ...override.warehouseLayer },
    futureLayers: {
      tileset: override.futureLayers?.tileset ?? base.futureLayers?.tileset,
      splat: override.futureLayers?.splat ?? base.futureLayers?.splat,
      pointCloud: override.futureLayers?.pointCloud ?? base.futureLayers?.pointCloud,
    },
    maplibre: override.maplibre === undefined ? base.maplibre : { ...base.maplibre, ...override.maplibre },
    cameraFallback: {
      ...base.cameraFallback,
      ...override.cameraFallback,
      padding: override.cameraFallback?.padding ?? base.cameraFallback?.padding,
    },
    statusColors: { ...base.statusColors, ...override.statusColors },
    extends: undefined,
  }
}

function resolvePartialSceneAssetUrls(input: PartialSceneConfig, manifestUrl: string): PartialSceneConfig {
  const resolveUrl = (url: string | undefined) => (url && shouldResolveSceneAssetUrl(url) ? resolveSceneAssetUrl(url, manifestUrl) : url)
  return {
    ...input,
    imageryProvider: input.imageryProvider
      ? {
          ...input.imageryProvider,
          url: resolveUrl(input.imageryProvider.url),
        }
      : undefined,
    terrainProvider:
      input.terrainProvider?.kind === "cesium-terrain"
        ? {
            ...input.terrainProvider,
            url: resolveUrl(input.terrainProvider.url) ?? "",
          }
        : input.terrainProvider,
    siteLayer: input.siteLayer ? { ...input.siteLayer, dataUrl: resolveUrl(input.siteLayer.dataUrl) } : undefined,
    buildingLayer: input.buildingLayer ? { ...input.buildingLayer, dataUrl: resolveUrl(input.buildingLayer.dataUrl) } : undefined,
    zoneLayer: input.zoneLayer ? { ...input.zoneLayer, dataUrl: resolveUrl(input.zoneLayer.dataUrl) } : undefined,
    warehouseLayer: input.warehouseLayer ? { ...input.warehouseLayer, dataUrl: resolveUrl(input.warehouseLayer.dataUrl) } : undefined,
    warehouseDataUrl: resolveUrl(input.warehouseDataUrl),
    styleUrl: resolveUrl(input.styleUrl),
    maplibre: input.maplibre ? { ...input.maplibre, styleUrl: resolveUrl(input.maplibre.styleUrl) ?? input.maplibre.styleUrl } : undefined,
    modelLayer: input.modelLayer
      ? {
          ...input.modelLayer,
          assets: input.modelLayer.assets?.map((asset) => ({ ...asset, url: resolveUrl(asset.url) ?? asset.url })),
        }
      : undefined,
    futureLayers: input.futureLayers
      ? {
          tileset: input.futureLayers.tileset?.map((layer) => ({ ...layer, url: resolveUrl(layer.url) ?? layer.url })),
          splat: input.futureLayers.splat?.map((layer) => ({ ...layer, url: resolveUrl(layer.url) ?? layer.url })),
          pointCloud: input.futureLayers.pointCloud?.map((layer) => ({ ...layer, url: resolveUrl(layer.url) ?? layer.url })),
        }
      : undefined,
  }
}

async function loadSceneConfigChain(manifestUrl: string, ancestors: string[] = []): Promise<PartialSceneConfig> {
  const resolvedManifestUrl = resolveSceneAssetUrl(manifestUrl, window.location.href)
  if (ancestors.includes(resolvedManifestUrl)) {
    throw new Error(`Scene manifest inheritance cycle: ${[...ancestors, resolvedManifestUrl].join(" -> ")}`)
  }
  if (ancestors.length >= 8) {
    throw new Error("Scene manifest inheritance exceeds 8 levels")
  }

  const rawConfig = await fetchJson<PartialSceneConfig>(resolvedManifestUrl, ancestors.length === 0 ? "candidate-manifest" : "inherited-manifest")
  const currentConfig = resolvePartialSceneAssetUrls(rawConfig, resolvedManifestUrl)
  if (!rawConfig.extends?.trim()) {
    return currentConfig
  }

  const baseUrl = resolveSceneAssetUrl(rawConfig.extends, resolvedManifestUrl)
  const baseConfig = await loadSceneConfigChain(baseUrl, [...ancestors, resolvedManifestUrl])
  return mergeSceneConfig(baseConfig, currentConfig)
}

export async function loadBigscreenScene(manifestUrl: string): Promise<BigscreenLoadedScene> {
  const rawConfig = await loadSceneConfigChain(manifestUrl)
  const config = normalizeBigscreenSceneConfig(rawConfig)
  const warehouses = normalizeWarehouseFeatureCollection(await fetchJson<BigscreenWarehouseFeatureCollection>(resolveWarehouseDataUrl(config)))

  return {
    manifestUrl: resolveSceneAssetUrl(manifestUrl, window.location.href),
    config,
    warehouses,
  }
}

export async function loadBigscreenSceneCandidates(manifestUrls: string[]): Promise<BigscreenLoadedScene> {
  if (manifestUrls.length === 0) {
    throw new Error("At least one scene manifest candidate is required")
  }

  for (const [index, manifestUrl] of manifestUrls.entries()) {
    try {
      return await loadBigscreenScene(manifestUrl)
    } catch (error) {
      const canFallback = error instanceof BigscreenSceneResourceError && error.status === 404 && error.resourceKind === "candidate-manifest" && index < manifestUrls.length - 1
      if (!canFallback) {
        throw error
      }
    }
  }

  throw new Error("No scene manifest could be loaded")
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
