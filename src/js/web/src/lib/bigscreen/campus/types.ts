export type PixelPoint = [number, number]
export type CampusEntry = { id: string; label: string; pixel: PixelPoint; yaw: number }
export type ThreeCampusManifest = {
  sceneId: string
  revision: string
  teamId: string
  engine: "three"
  title: string
  address: string
  attribution?: string
  assets: string[]
  reference?: string
  world: {
    origin: PixelPoint
    originPixel: PixelPoint
    metresPerPixel: number
    buildings: { id: string; polygon: PixelPoint[]; height: number }[]
    water: PixelPoint[][]
    walkBounds: [number, number, number, number]
    orbitPosition: [number, number, number]
    orbitTarget: [number, number, number]
    entries: CampusEntry[]
    lights: PixelPoint[]
  }
}
export type LegacyCampusManifest = {
  sceneId: string
  revision: string
  teamId: string
  engine: "cesium"
  title: string
  address: string
  assets: string[]
  legacyManifest: string
}
export type CampusGeoregistration = {
  version: 1
  crs: "EPSG:4326"
  origin: PixelPoint
  scale: [number, number, number]
  ellipsoidHeight: number
  heightStatus: "estimated" | "surveyed"
  upAxis: "Y"
  forwardAxis: "X"
  terrain: "ellipsoid"
  imagery: { url: string; credit: string; maximumLevel: number }
}
export type CesiumCampusManifest = Omit<ThreeCampusManifest, "engine"> & {
  engine: "cesium-campus"
  georegistration: CampusGeoregistration
}
export type ModelCampusManifest = ThreeCampusManifest | CesiumCampusManifest
export type CampusManifest = ModelCampusManifest | LegacyCampusManifest
export type CampusViewState = { mode: "orbit" | "walk"; entry: string | null; night: boolean }
export type CampusRuntime = {
  home(top?: boolean): void
  enter(id: string): void
  toggleNight(): void
  move(direction: "forward" | "back" | "left" | "right"): void
  dispose(): void
}
