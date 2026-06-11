import {
  Cartesian2,
  Cartesian3,
  Math as CesiumMath,
  CesiumTerrainProvider,
  Color,
  Credit,
  EllipsoidTerrainProvider,
  Entity,
  GeoJsonDataSource,
  GridMaterialProperty,
  HeadingPitchRange,
  JulianDate,
  LabelStyle,
  Matrix4,
  PolylineGlowMaterialProperty,
  UrlTemplateImageryProvider,
  VerticalOrigin,
  Viewer,
} from "cesium"

import { getWarehouseStatusColor, resolveInitialCamera } from "@/lib/bigscreen/map/scene"
import type { BigscreenSceneEngine, BigscreenSceneEngineMountContext, BigscreenSceneFeatureLayerConfig, BigscreenSceneLngLat } from "@/lib/bigscreen/map/types"

type SceneFeatureProperties = {
  id?: string
  name?: string
  type?: string
  color?: string
  opacity?: number
  outlineColor?: string
  height_m?: number
  displayHeight_m?: number
  roof?: string
  roofColor?: string
  wallColor?: string
}

type ScenePolygonFeature = {
  type: "Feature"
  properties?: SceneFeatureProperties
  geometry?: {
    type: "Polygon"
    coordinates: BigscreenSceneLngLat[][]
  }
}

type SceneFeatureCollection = {
  type: "FeatureCollection"
  features: ScenePolygonFeature[]
}

function readProperty(entity: Entity, key: string, now: JulianDate) {
  return entity.properties?.[key]?.getValue(now) as unknown
}

function readStringProperty(entity: Entity, key: string, now: JulianDate) {
  const value = readProperty(entity, key, now)
  return typeof value === "string" ? value : undefined
}

function readNumberProperty(entity: Entity, key: string, now: JulianDate) {
  const value = readProperty(entity, key, now)
  return typeof value === "number" && Number.isFinite(value) ? value : undefined
}

function cssColor(value: string | undefined, fallback: string, alpha = 1) {
  return Color.fromCssColorString(value?.trim() || fallback).withAlpha(alpha)
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to load ${url}: HTTP ${response.status}`)
  }
  return (await response.json()) as T
}

function applyInteractionPolicy(viewer: Viewer, interactive: boolean) {
  const controller = viewer.scene.screenSpaceCameraController
  controller.enableTranslate = interactive
  controller.enableZoom = interactive
  controller.enableRotate = interactive
  controller.enableTilt = interactive
  controller.enableLook = interactive
}

function createImageryProvider(context: BigscreenSceneEngineMountContext) {
  const config = context.config.imageryProvider
  if (config.url.trim().toLowerCase() === "none") {
    return null
  }

  return new UrlTemplateImageryProvider({
    url: config.url,
    credit: config.credit ? new Credit(config.credit) : undefined,
    minimumLevel: config.minimumLevel,
    maximumLevel: config.maximumLevel,
    subdomains: config.subdomains,
  })
}

async function createTerrainProvider(context: BigscreenSceneEngineMountContext) {
  const config = context.config.terrainProvider
  if (config.kind === "cesium-terrain") {
    return CesiumTerrainProvider.fromUrl(config.url, {
      requestVertexNormals: config.requestVertexNormals,
      requestWaterMask: config.requestWaterMask,
      credit: config.credit ? new Credit(config.credit) : undefined,
    })
  }

  return new EllipsoidTerrainProvider()
}

function resolveCameraTarget(context: BigscreenSceneEngineMountContext) {
  const initialCamera = resolveInitialCamera(context.config, context.warehouses)
  if (initialCamera.kind === "fallback") {
    return initialCamera
  }

  const [southWest, northEast] = initialCamera.bounds
  const center: BigscreenSceneLngLat = [(southWest[0] + northEast[0]) / 2, (southWest[1] + northEast[1]) / 2]
  const centerLatRadians = CesiumMath.toRadians(center[1])
  const widthMeters = Math.abs(northEast[0] - southWest[0]) * 111_320 * Math.cos(centerLatRadians)
  const heightMeters = Math.abs(northEast[1] - southWest[1]) * 111_320
  const diagonalMeters = Math.hypot(widthMeters, heightMeters)
  const paddingFactor = 1 + (initialCamera.padding.left + initialCamera.padding.right + initialCamera.padding.top + initialCamera.padding.bottom) / 1600
  const height = Math.max(context.config.cameraHome.height, diagonalMeters * 2.4 * paddingFactor + 240)

  return {
    kind: "fallback" as const,
    center,
    height,
    heading: context.config.cameraHome.heading,
    pitch: context.config.cameraHome.pitch,
    roll: context.config.cameraHome.roll,
  }
}

function applyCamera(viewer: Viewer, context: BigscreenSceneEngineMountContext) {
  const target = resolveCameraTarget(context)
  const targetPosition = Cartesian3.fromDegrees(target.center[0], target.center[1], 0)
  viewer.camera.lookAt(
    targetPosition,
    new HeadingPitchRange(CesiumMath.toRadians(target.heading), CesiumMath.toRadians(target.pitch), target.height),
  )
  viewer.camera.lookAtTransform(Matrix4.IDENTITY)
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function resolveVisualScale(container: HTMLElement) {
  const rect = container.getBoundingClientRect()
  const widthScale = container.clientWidth > 0 ? rect.width / container.clientWidth : 1
  const heightScale = container.clientHeight > 0 ? rect.height / container.clientHeight : 1
  const visualScale = Math.max(widthScale, heightScale)
  return Number.isFinite(visualScale) && visualScale > 0 ? visualScale : 1
}

function applyRenderQuality(viewer: Viewer, context: BigscreenSceneEngineMountContext) {
  const options = context.config.viewerOptions
  const visualScale = resolveVisualScale(context.container)
  const configuredScale = Number.isFinite(options.resolutionScale) ? options.resolutionScale : 1

  viewer.useBrowserRecommendedResolution = options.useBrowserRecommendedResolution
  viewer.resolutionScale = clamp(configuredScale * Math.max(1, visualScale), 1, 2)
  viewer.scene.msaaSamples = options.msaaSamples
  viewer.scene.postProcessStages.fxaa.enabled = options.fxaa

  if (viewer.scene.highDynamicRangeSupported) {
    viewer.scene.highDynamicRange = options.highDynamicRange
  }
}

async function addGeoJsonFeatureLayer(viewer: Viewer, layer: BigscreenSceneFeatureLayerConfig, applyEntityStyle: (entity: Entity, now: JulianDate) => void) {
  if (!layer.show) {
    return null
  }

  const dataSource = await GeoJsonDataSource.load(layer.dataUrl, {
    clampToGround: false,
  })
  const now = JulianDate.now()

  for (const entity of dataSource.entities.values) {
    if (!entity.polygon) {
      continue
    }
    applyEntityStyle(entity, now)
  }

  await viewer.dataSources.add(dataSource)
  return dataSource
}

async function addSiteLayer(viewer: Viewer, context: BigscreenSceneEngineMountContext) {
  const layer = context.config.siteLayer
  if (!layer) {
    return null
  }

  return addGeoJsonFeatureLayer(viewer, layer, (entity, now) => {
    const color = readStringProperty(entity, "color", now)
    const opacity = readNumberProperty(entity, "opacity", now) ?? 0.82
    const height = readNumberProperty(entity, "height_m", now) ?? 0
    const outlineColor = readStringProperty(entity, "outlineColor", now) ?? layer.outlineColor
    const type = readStringProperty(entity, "type", now)

    entity.polygon.height = height
    entity.polygon.extrudedHeight = height + 0.04
    entity.polygon.perPositionHeight = false
    entity.polygon.outline = true
    entity.polygon.outlineColor = cssColor(outlineColor, layer.outlineColor, layer.outlineOpacity)
    if (type === "concrete") {
      entity.polygon.material = new GridMaterialProperty({
        color: cssColor(color, "#d7e6e8", Math.min(0.72, opacity)),
        cellAlpha: 0.1,
        lineCount: new Cartesian2(26, 18),
        lineThickness: new Cartesian2(0.55, 0.55),
      })
      return
    }
    entity.polygon.material = cssColor(color, "#d7e6e8", opacity)
  })
}

function getFeatureBounds(feature: ScenePolygonFeature) {
  const ring = feature.geometry?.coordinates?.[0] ?? []
  if (!ring.length) {
    return null
  }

  let minLng = Number.POSITIVE_INFINITY
  let maxLng = Number.NEGATIVE_INFINITY
  let minLat = Number.POSITIVE_INFINITY
  let maxLat = Number.NEGATIVE_INFINITY

  for (const [lng, lat] of ring) {
    minLng = Math.min(minLng, lng)
    maxLng = Math.max(maxLng, lng)
    minLat = Math.min(minLat, lat)
    maxLat = Math.max(maxLat, lat)
  }

  return { minLng, maxLng, minLat, maxLat }
}

function getFeatureCenter(feature: ScenePolygonFeature): BigscreenSceneLngLat | null {
  const bounds = getFeatureBounds(feature)
  if (!bounds) {
    return null
  }

  return [(bounds.minLng + bounds.maxLng) / 2, (bounds.minLat + bounds.maxLat) / 2]
}

function boundsToDegreesArray(bounds: NonNullable<ReturnType<typeof getFeatureBounds>>) {
  return [bounds.minLng, bounds.minLat, bounds.maxLng, bounds.minLat, bounds.maxLng, bounds.maxLat, bounds.minLng, bounds.maxLat]
}

function boundsToDegreesArrayHeights(bounds: NonNullable<ReturnType<typeof getFeatureBounds>>, height: number) {
  return [
    bounds.minLng,
    bounds.minLat,
    height,
    bounds.maxLng,
    bounds.minLat,
    height,
    bounds.maxLng,
    bounds.maxLat,
    height,
    bounds.minLng,
    bounds.maxLat,
    height,
    bounds.minLng,
    bounds.minLat,
    height,
  ]
}

function getFeatureShortCode(feature: ScenePolygonFeature) {
  const name = feature.properties?.name?.trim()
  if (!name) {
    return feature.properties?.id?.trim() ?? ""
  }

  const [code] = name.split(/\s+/)
  return code || name
}

function addPerimeterLine(viewer: Viewer, bounds: NonNullable<ReturnType<typeof getFeatureBounds>>, height: number, color = "#9be8ff", width = 2) {
  viewer.entities.add({
    polyline: {
      positions: Cartesian3.fromDegreesArrayHeights(boundsToDegreesArrayHeights(bounds, height)),
      width,
      material: new PolylineGlowMaterialProperty({
        color: Color.fromCssColorString(color).withAlpha(0.78),
        glowPower: 0.16,
      }),
    },
  })
}

function addBuildingFacadeLines(viewer: Viewer, feature: ScenePolygonFeature, height: number) {
  const bounds = getFeatureBounds(feature)
  if (!bounds || !feature.properties?.type?.startsWith("warehouse")) {
    return
  }

  const centerLat = (bounds.minLat + bounds.maxLat) / 2
  const metersPerLng = 111_320 * Math.cos(CesiumMath.toRadians(centerLat))
  const widthMeters = (bounds.maxLng - bounds.minLng) * metersPerLng
  const lineCount = Math.max(4, Math.min(18, Math.floor(widthMeters / 24)))
  const stepLng = (bounds.maxLng - bounds.minLng) / lineCount
  const material = Color.fromCssColorString("#c9f4ff").withAlpha(0.5)

  for (let index = 1; index < lineCount; index += 1) {
    const lng = bounds.minLng + stepLng * index
    for (const lat of [bounds.minLat, bounds.maxLat]) {
      viewer.entities.add({
        polyline: {
          positions: [Cartesian3.fromDegrees(lng, lat, 0.25), Cartesian3.fromDegrees(lng, lat, height - 0.4)],
          width: 1.15,
          material,
        },
      })
    }
  }
}

function addRoofCap(viewer: Viewer, context: BigscreenSceneEngineMountContext, feature: ScenePolygonFeature) {
  const bounds = getFeatureBounds(feature)
  const buildingLayer = context.config.buildingLayer
  if (!bounds || !buildingLayer) {
    return
  }

  const height = feature.properties?.height_m ?? buildingLayer.defaultHeight
  const roofDeckColor = feature.properties?.roof === "solar" ? "#e9f4f8" : (feature.properties?.roofColor ?? "#eef8fb")
  viewer.entities.add({
    name: `${feature.properties?.name ?? "建筑"} 屋顶盖板`,
    polygon: {
      hierarchy: Cartesian3.fromDegreesArray(boundsToDegreesArray(bounds)),
      height: height + 0.08,
      material: cssColor(roofDeckColor, "#eef8fb", 0.98),
      outline: true,
      outlineColor: cssColor(feature.properties?.outlineColor, buildingLayer.outlineColor, 0.9),
    },
  })

  addPerimeterLine(viewer, bounds, 0.22, "#7adff5", 1.5)
  addPerimeterLine(viewer, bounds, height + 0.2, "#d7fbff", feature.properties?.type?.startsWith("warehouse") ? 2.4 : 1.7)
  addBuildingFacadeLines(viewer, feature, height)
}

function addFeatureLabel(
  viewer: Viewer,
  feature: ScenePolygonFeature,
  height: number,
  options: {
    fontSize: number
    text?: string
    color?: string
    offsetY?: number
  },
) {
  const center = getFeatureCenter(feature)
  const labelText = options.text ?? feature.properties?.name
  if (!center || !labelText) {
    return
  }

  viewer.entities.add({
    name: `${labelText} 标注`,
    position: Cartesian3.fromDegrees(center[0], center[1], height),
    label: {
      text: labelText,
      font: `700 ${options.fontSize}px sans-serif`,
      fillColor: cssColor(options.color, "#f8fdff", 0.96),
      outlineColor: Color.BLACK.withAlpha(0.88),
      outlineWidth: 4,
      style: LabelStyle.FILL_AND_OUTLINE,
      verticalOrigin: VerticalOrigin.BOTTOM,
      pixelOffset: new Cartesian2(0, options.offsetY ?? -8),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
      showBackground: true,
      backgroundColor: Color.fromCssColorString("#02111c").withAlpha(0.68),
      backgroundPadding: new Cartesian2(7, 4),
    },
  })
}

function shouldShowBuildingLabel(feature: ScenePolygonFeature) {
  const type = feature.properties?.type
  return type !== "reserved" && type !== "gatehouse"
}

function addSolarPanels(viewer: Viewer, context: BigscreenSceneEngineMountContext, feature: ScenePolygonFeature) {
  const buildingLayer = context.config.buildingLayer
  if (!buildingLayer || feature.properties?.roof !== "solar") {
    return
  }

  const bounds = getFeatureBounds(feature)
  if (!bounds) {
    return
  }

  const centerLat = (bounds.minLat + bounds.maxLat) / 2
  const metersPerLng = 111_320 * Math.cos(CesiumMath.toRadians(centerLat))
  const metersPerLat = 111_320
  const widthMeters = (bounds.maxLng - bounds.minLng) * metersPerLng
  const depthMeters = (bounds.maxLat - bounds.minLat) * metersPerLat
  const columns = Math.max(4, Math.min(36, Math.floor(widthMeters / 8)))
  const rows = Math.max(3, Math.min(18, Math.floor(depthMeters / 6)))
  const gapMeters = 1.25
  const insetMeters = 6.5
  const usableWidth = Math.max(8, widthMeters - insetMeters * 2)
  const usableDepth = Math.max(8, depthMeters - insetMeters * 2)
  const panelWidthMeters = Math.max(4, (usableWidth - gapMeters * (columns - 1)) / columns)
  const panelDepthMeters = Math.max(3, (usableDepth - gapMeters * (rows - 1)) / rows)
  const panelWidthLng = panelWidthMeters / metersPerLng
  const panelDepthLat = panelDepthMeters / metersPerLat
  const gapLng = gapMeters / metersPerLng
  const gapLat = gapMeters / metersPerLat
  const startLng = bounds.minLng + insetMeters / metersPerLng
  const startLat = bounds.minLat + insetMeters / metersPerLat
  const height = (feature.properties?.height_m ?? buildingLayer.defaultHeight) + 0.28

  for (let row = 0; row < rows; row += 1) {
    for (let column = 0; column < columns; column += 1) {
      const west = startLng + column * (panelWidthLng + gapLng)
      const south = startLat + row * (panelDepthLat + gapLat)
      const east = west + panelWidthLng
      const north = south + panelDepthLat
      viewer.entities.add({
        name: `${feature.properties?.name ?? "建筑"} 光伏板`,
        polygon: {
          hierarchy: Cartesian3.fromDegreesArray([west, south, east, south, east, north, west, north]),
          height,
          material: cssColor(feature.properties?.roofColor, buildingLayer.solarPanelColor, 0.96),
          outline: true,
          outlineColor: cssColor(buildingLayer.solarPanelStrokeColor, buildingLayer.solarPanelStrokeColor, 0.52),
        },
      })
    }
  }
}

async function addBuildingLayer(viewer: Viewer, context: BigscreenSceneEngineMountContext) {
  const layer = context.config.buildingLayer
  if (!layer) {
    return null
  }

  const dataSource = await addGeoJsonFeatureLayer(viewer, layer, (entity, now) => {
    const color = readStringProperty(entity, "wallColor", now) ?? readStringProperty(entity, "color", now)
    const opacity = readNumberProperty(entity, "opacity", now) ?? layer.defaultOpacity
    const height = readNumberProperty(entity, "height_m", now) ?? layer.defaultHeight
    const outlineColor = readStringProperty(entity, "outlineColor", now) ?? layer.outlineColor

    entity.polygon.height = 0
    entity.polygon.extrudedHeight = height
    entity.polygon.perPositionHeight = false
    entity.polygon.outline = true
    entity.polygon.outlineColor = cssColor(outlineColor, layer.outlineColor, layer.outlineOpacity)
    entity.polygon.material = cssColor(color, "#d8eef2", opacity)
  })

  const featureCollection = await fetchJson<SceneFeatureCollection>(layer.dataUrl)
  for (const feature of featureCollection.features) {
    addRoofCap(viewer, context, feature)
    addSolarPanels(viewer, context, feature)
    if (!shouldShowBuildingLabel(feature)) {
      continue
    }
    const height = feature.properties?.height_m ?? layer.defaultHeight
    addFeatureLabel(viewer, feature, height + 5.5, {
      fontSize: feature.properties?.type?.startsWith("warehouse") ? 20 : 18,
      color: "#f8fdff",
      offsetY: -12,
    })
  }

  return dataSource
}

async function addZoneLayer(viewer: Viewer, context: BigscreenSceneEngineMountContext) {
  const layer = context.config.zoneLayer
  if (!layer) {
    return null
  }

  const dataSource = await addGeoJsonFeatureLayer(viewer, layer, (entity, now) => {
    const color = readStringProperty(entity, "color", now)
    const opacity = readNumberProperty(entity, "opacity", now) ?? layer.defaultOpacity
    const height = readNumberProperty(entity, "displayHeight_m", now) ?? layer.surfaceHeight
    const thickness = readNumberProperty(entity, "height_m", now) ?? layer.defaultHeight
    const outlineColor = readStringProperty(entity, "outlineColor", now) ?? layer.outlineColor

    entity.polygon.height = height
    entity.polygon.extrudedHeight = height + thickness
    entity.polygon.perPositionHeight = false
    entity.polygon.outline = true
    entity.polygon.outlineColor = cssColor(outlineColor, layer.outlineColor, layer.outlineOpacity)
    entity.polygon.material = cssColor(color, "#38bdf8", opacity)
  })

  const featureCollection = await fetchJson<SceneFeatureCollection>(layer.dataUrl)
  for (const feature of featureCollection.features) {
    const height = feature.properties?.displayHeight_m ?? layer.surfaceHeight
    const thickness = feature.properties?.height_m ?? layer.defaultHeight
    addFeatureLabel(viewer, feature, height + thickness + 1.2, {
      text: getFeatureShortCode(feature),
      fontSize: 13,
      color: "#ffffff",
      offsetY: -4,
    })
  }

  return dataSource
}

async function addWarehouseLayer(viewer: Viewer, context: BigscreenSceneEngineMountContext) {
  const dataSource = await GeoJsonDataSource.load(context.config.warehouseLayer.dataUrl, {
    clampToGround: false,
  })

  const outlineColor = Color.fromCssColorString(context.config.warehouseLayer.outlineColor).withAlpha(context.config.warehouseLayer.outlineOpacity)
  const now = JulianDate.now()

  for (const entity of dataSource.entities.values) {
    if (!entity.polygon) {
      continue
    }

    const status = entity.properties?.status?.getValue(now) as string | undefined
    const height = Number(entity.properties?.height_m?.getValue(now) ?? 24)
    const baseColor = Color.fromCssColorString(getWarehouseStatusColor(context.config, status ?? "normal"))

    entity.polygon.height = 0
    entity.polygon.extrudedHeight = Number.isFinite(height) ? height : 24
    entity.polygon.perPositionHeight = false
    entity.polygon.outline = true
    entity.polygon.outlineColor = outlineColor
    entity.polygon.material = baseColor.withAlpha(context.config.warehouseLayer.extrusionOpacity)
  }

  await viewer.dataSources.add(dataSource)
  return dataSource
}

export function createCesiumBigscreenSceneEngine(): BigscreenSceneEngine {
  let viewer: Viewer | null = null
  let sceneDataSources: GeoJsonDataSource[] = []
  let mountContext: BigscreenSceneEngineMountContext | null = null

  return {
    async mount(context) {
      if (viewer) {
        viewer.destroy()
      }
      mountContext = context

      viewer = new Viewer(context.container, {
        animation: false,
        timeline: false,
        sceneModePicker: false,
        baseLayerPicker: false,
        baseLayer: false,
        geocoder: false,
        homeButton: false,
        navigationHelpButton: false,
        fullscreenButton: false,
        vrButton: false,
        infoBox: false,
        selectionIndicator: false,
        projectionPicker: false,
        creditContainer: document.createElement("div"),
        useBrowserRecommendedResolution: context.config.viewerOptions.useBrowserRecommendedResolution,
        orderIndependentTranslucency: context.config.viewerOptions.orderIndependentTranslucency,
        shadows: context.config.viewerOptions.shadows,
        requestRenderMode: context.config.viewerOptions.requestRenderMode,
        maximumRenderTimeChange: context.config.viewerOptions.maximumRenderTimeChange,
        msaaSamples: context.config.viewerOptions.msaaSamples,
      })
      applyRenderQuality(viewer, context)

      const imageryProvider = createImageryProvider(context)
      if (imageryProvider) {
        const imageryLayer = viewer.imageryLayers.addImageryProvider(imageryProvider)
        imageryLayer.alpha = 0.62
        imageryLayer.brightness = 0.72
        imageryLayer.contrast = 0.82
        imageryLayer.saturation = 0.28
      }
      viewer.terrainProvider = await createTerrainProvider(context)
      viewer.scene.globe.baseColor = Color.fromCssColorString("#cfe0e3")
      viewer.scene.globe.depthTestAgainstTerrain = false
      applyInteractionPolicy(viewer, context.config.interactive)
      const siteDataSource = await addSiteLayer(viewer, context)
      const buildingDataSource = await addBuildingLayer(viewer, context)
      const zoneDataSource = await addZoneLayer(viewer, context)
      const warehouseDataSource = context.config.siteLayer || context.config.buildingLayer || context.config.zoneLayer ? null : await addWarehouseLayer(viewer, context)
      sceneDataSources = [siteDataSource, buildingDataSource, zoneDataSource, warehouseDataSource].filter((dataSource): dataSource is GeoJsonDataSource => Boolean(dataSource))
      applyCamera(viewer, context)
      viewer.scene.requestRender()
      context.onReady?.()
    },
    resize() {
      if (!viewer) {
        return
      }
      ;(viewer as unknown as { resize?: () => void; forceResize?: () => void }).resize?.()
      ;(viewer as unknown as { resize?: () => void; forceResize?: () => void }).forceResize?.()
      if (mountContext) {
        applyRenderQuality(viewer, mountContext)
      }
      viewer.scene.requestRender()
    },
    destroy() {
      if (viewer) {
        for (const dataSource of sceneDataSources) {
          viewer.dataSources.remove(dataSource, true)
        }
        viewer.entities.removeAll()
      }
      sceneDataSources = []
      mountContext = null
      viewer?.destroy()
      viewer = null
    },
  }
}
