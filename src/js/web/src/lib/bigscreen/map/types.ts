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
}

export type BigscreenSceneImageryProviderConfig = {
  kind: "url-template"
  url: string
  credit?: string
  minimumLevel?: number
  maximumLevel?: number
  subdomains?: string[]
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
  sceneEngine: BigscreenSceneEngineKind
  coordinateSystem: BigscreenSceneCoordinateSystem
  center: BigscreenSceneLngLat
  interactive: boolean
  attributionLabel?: string
  imageryProvider: BigscreenSceneImageryProviderConfig
  terrainProvider: BigscreenSceneTerrainProviderConfig
  cameraHome: BigscreenSceneCameraHome
  viewerOptions: BigscreenSceneViewerOptions
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
