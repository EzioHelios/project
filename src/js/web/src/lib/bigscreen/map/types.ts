export type BigscreenMapCoordinateSystem = "wgs84" | "gcj02"

export type BigscreenMapLngLat = [lng: number, lat: number]

export type BigscreenMapPadding = {
  top: number
  right: number
  bottom: number
  left: number
}

export type BigscreenMapCameraFallback = {
  center: BigscreenMapLngLat
  zoom: number
  bearing: number
  pitch: number
  maxZoom: number
  padding: BigscreenMapPadding
}

export type BigscreenMapSceneConfig = {
  engine: "maplibre"
  coordinateSystem: BigscreenMapCoordinateSystem
  center: BigscreenMapLngLat
  interactive: boolean
  styleUrl: string
  warehouseDataUrl: string
  attributionLabel?: string
  cameraFallback: BigscreenMapCameraFallback
  statusColors: Record<string, string>
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
  coordinates: BigscreenMapLngLat[][]
}

export type BigscreenMultiPolygonGeometry = {
  type: "MultiPolygon"
  coordinates: BigscreenMapLngLat[][][]
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

export type BigscreenMapFitBoundsResult = {
  kind: "bounds"
  bounds: [southWest: BigscreenMapLngLat, northEast: BigscreenMapLngLat]
  maxZoom: number
  bearing: number
  pitch: number
  padding: BigscreenMapPadding
}

export type BigscreenMapFallbackCameraResult = {
  kind: "fallback"
  center: BigscreenMapLngLat
  zoom: number
  bearing: number
  pitch: number
}

export type BigscreenMapInitialCamera = BigscreenMapFitBoundsResult | BigscreenMapFallbackCameraResult

export type BigscreenLoadedMapScene = {
  config: BigscreenMapSceneConfig
  warehouses: BigscreenWarehouseFeatureCollection
  manifestUrl: string
}

export type BigscreenMapEngineMountContext = {
  container: HTMLElement
  config: BigscreenMapSceneConfig
  warehouses: BigscreenWarehouseFeatureCollection
  onReady?: () => void
  onError?: (error: Error) => void
}

export interface BigscreenMapEngine {
  mount(context: BigscreenMapEngineMountContext): Promise<void> | void
  resize(): void
  destroy(): void
}
