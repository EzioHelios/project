export type BigscreenSceneEngineKind = "cesium" | "maplibre"

export type BigscreenSceneCoordinateSystem = "wgs84" | "gcj02"

export type BigscreenSceneLngLat = [lng: number, lat: number]

export type BigscreenScenePadding = {
  top: number
  right: number
  bottom: number
  left: number
}

export type BigscreenSceneCameraHome = {
  center: BigscreenSceneLngLat
  height: number
  heading: number
  pitch: number
  roll: number
  fitPadding: BigscreenScenePadding
}

export type BigscreenSceneViewerOptions = {
  sceneMode: "3d"
  shadows: boolean
  requestRenderMode: boolean
  maximumRenderTimeChange: number
  msaaSamples: number
  useBrowserRecommendedResolution: boolean
  resolutionScale: number
  fxaa: boolean
  orderIndependentTranslucency: boolean
  highDynamicRange: boolean
}

export type BigscreenSceneImageryProviderConfig = {
  kind: "url-template"
  url: string
  credit?: string
  minimumLevel?: number
  maximumLevel?: number
  subdomains?: string[]
  alpha: number
  brightness: number
  contrast: number
  saturation: number
  gamma: number
}

export type BigscreenSceneTerrainProviderConfig =
  | {
      kind: "ellipsoid"
    }
  | {
      kind: "cesium-terrain"
      url: string
      requestVertexNormals?: boolean
      requestWaterMask?: boolean
      credit?: string
    }

export type BigscreenFutureTilesetLayer = {
  id: string
  url: string
  show: boolean
}

export type BigscreenFutureSplatLayer = {
  id: string
  url: string
  show: boolean
}

export type BigscreenFuturePointCloudLayer = {
  id: string
  url: string
  show: boolean
}

export type BigscreenWarehouseLayerConfig = {
  dataUrl: string
  statusColors: Record<string, string>
  fillOpacity: number
  extrusionOpacity: number
  outlineColor: string
  outlineOpacity: number
  outlineWidth: number
}

export type BigscreenSceneFeatureLayerConfig = {
  dataUrl: string
  show: boolean
  outlineColor: string
  outlineOpacity: number
  outlineWidth: number
}

export type BigscreenSceneSiteLayerConfig = BigscreenSceneFeatureLayerConfig & {
  featureColorMode: "feature" | "palette"
  defaultColor: string
  typeColors: Record<string, string>
}

export type BigscreenSceneBuildingLayerConfig = BigscreenSceneFeatureLayerConfig & {
  defaultHeight: number
  defaultOpacity: number
  defaultWallColor: string
  defaultRoofColor: string
  featureColorMode: "feature" | "uniform"
  roofEdgeColor: string
  roofEdgeOpacity: number
  showLabels: boolean
  labelDistance: number
  solarPanelColor: string
  solarPanelStrokeColor: string
}

export type BigscreenSceneZoneLayerConfig = BigscreenSceneFeatureLayerConfig & {
  defaultOpacity: number
  defaultColor: string
  featureColorMode: "feature" | "uniform"
  defaultHeight: number
  surfaceHeight: number
  showLabels: boolean
}

export type BigscreenSceneEnvironmentConfig = {
  backgroundColor: string
  globeBaseColor: string
  lighting: boolean
  dynamicAtmosphereLighting: boolean
  clockTime?: string
  fog: {
    enabled: boolean
    density: number
    minimumBrightness: number
    screenSpaceErrorFactor: number
  }
  ambientOcclusion: {
    enabled: boolean
    intensity: number
    bias: number
    lengthCap: number
    directionCount: number
    stepCount: number
  }
}

export type BigscreenSceneModelAsset = {
  id: string
  name?: string
  url: string
  show: boolean
  position: [lng: number, lat: number, height: number]
  heading: number
  pitch: number
  roll: number
  scale: number
  minimumPixelSize: number
  maximumScale?: number
  castShadows: boolean
  receiveShadows: boolean
  semanticType?: string
  assetKey?: string
  source?: {
    name: string
    url?: string
    license: string
  }
}

export type BigscreenSceneModelLayerConfig = {
  show: boolean
  assets: BigscreenSceneModelAsset[]
}

export type BigscreenSceneLegacyMaplibreConfig = {
  styleUrl: string
  cameraFallback: {
    center: BigscreenSceneLngLat
    zoom: number
    bearing: number
    pitch: number
    maxZoom: number
    padding: BigscreenScenePadding
  }
}

export type BigscreenSceneConfig = {
  sceneId: string
  revision: string
  sceneEngine: BigscreenSceneEngineKind
  coordinateSystem: BigscreenSceneCoordinateSystem
  center: BigscreenSceneLngLat
  interactive: boolean
  attributionLabel?: string
  imageryProvider: BigscreenSceneImageryProviderConfig
  terrainProvider: BigscreenSceneTerrainProviderConfig
  cameraHome: BigscreenSceneCameraHome
  viewerOptions: BigscreenSceneViewerOptions
  environment: BigscreenSceneEnvironmentConfig
  siteLayer?: BigscreenSceneSiteLayerConfig
  buildingLayer?: BigscreenSceneBuildingLayerConfig
  zoneLayer?: BigscreenSceneZoneLayerConfig
  modelLayer: BigscreenSceneModelLayerConfig
  warehouseLayer: BigscreenWarehouseLayerConfig
  futureLayers: {
    tileset: BigscreenFutureTilesetLayer[]
    splat: BigscreenFutureSplatLayer[]
    pointCloud: BigscreenFuturePointCloudLayer[]
  }
  maplibre?: BigscreenSceneLegacyMaplibreConfig
}

export type BigscreenWarehouseFeatureProperties = {
  id: string
  name: string
  status: "normal" | "active" | "warning" | string
  height_m: number
  accent?: string
}

export type BigscreenPolygonGeometry = {
  type: "Polygon"
  coordinates: BigscreenSceneLngLat[][]
}

export type BigscreenMultiPolygonGeometry = {
  type: "MultiPolygon"
  coordinates: BigscreenSceneLngLat[][][]
}

export type BigscreenWarehouseFeature = {
  type: "Feature"
  properties: BigscreenWarehouseFeatureProperties
  geometry: BigscreenPolygonGeometry | BigscreenMultiPolygonGeometry
}

export type BigscreenWarehouseFeatureCollection = {
  type: "FeatureCollection"
  features: BigscreenWarehouseFeature[]
}

export type BigscreenSceneInitialCamera =
  | {
      kind: "bounds"
      bounds: [southWest: BigscreenSceneLngLat, northEast: BigscreenSceneLngLat]
      padding: BigscreenScenePadding
    }
  | {
      kind: "fallback"
      center: BigscreenSceneLngLat
      height: number
      heading: number
      pitch: number
      roll: number
    }

export type BigscreenLoadedScene = {
  config: BigscreenSceneConfig
  warehouses: BigscreenWarehouseFeatureCollection
  manifestUrl: string
}

export type BigscreenSceneEngineMountContext = {
  container: HTMLElement
  config: BigscreenSceneConfig
  warehouses: BigscreenWarehouseFeatureCollection
  onReady?: () => void
  onError?: (error: Error) => void
}

export interface BigscreenSceneEngine {
  mount(context: BigscreenSceneEngineMountContext): Promise<void> | void
  resize(): void
  destroy(): void
}

export type BigscreenMapCoordinateSystem = BigscreenSceneCoordinateSystem
export type BigscreenMapLngLat = BigscreenSceneLngLat
export type BigscreenMapPadding = BigscreenScenePadding
export type BigscreenMapSceneConfig = BigscreenSceneConfig
export type BigscreenMapInitialCamera = BigscreenSceneInitialCamera
export type BigscreenLoadedMapScene = BigscreenLoadedScene
export type BigscreenMapEngineMountContext = BigscreenSceneEngineMountContext
export type BigscreenMapEngine = BigscreenSceneEngine
