import {
  Cartesian2,
  Cartesian3,
  Cesium3DTileset,
  Math as CesiumMath,
  CesiumTerrainProvider,
  Color,
  ColorMaterialProperty,
  ConstantProperty,
  Credit,
  DistanceDisplayCondition,
  EllipsoidTerrainProvider,
  type Entity,
  GeoJsonDataSource,
  GridMaterialProperty,
  HeadingPitchRange,
  HeadingPitchRoll,
  JulianDate,
  LabelStyle,
  Matrix4,
  NearFarScalar,
  type PolygonGraphics,
  ShadowMode,
  Transforms,
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

function applyPolygonStyle(
  polygon: PolygonGraphics,
  options: {
    height: number
    extrudedHeight: number
    outline: boolean
    outlineColor: Color
    materialColor: Color
  },
) {
  polygon.height = new ConstantProperty(options.height)
  polygon.extrudedHeight = new ConstantProperty(options.extrudedHeight)
  polygon.perPositionHeight = new ConstantProperty(false)
  polygon.outline = new ConstantProperty(options.outline)
  polygon.outlineColor = new ConstantProperty(options.outlineColor)
  polygon.material = new ColorMaterialProperty(options.materialColor)
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
  viewer.camera.lookAt(targetPosition, new HeadingPitchRange(CesiumMath.toRadians(target.heading), CesiumMath.toRadians(target.pitch), target.height))
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

function applyEnvironment(viewer: Viewer, context: BigscreenSceneEngineMountContext) {
  const environment = context.config.environment
  viewer.scene.backgroundColor = Color.fromCssColorString(environment.backgroundColor)
  viewer.scene.globe.baseColor = Color.fromCssColorString(environment.globeBaseColor)
  viewer.scene.globe.enableLighting = environment.lighting
  viewer.scene.globe.dynamicAtmosphereLighting = environment.dynamicAtmosphereLighting
  viewer.scene.globe.dynamicAtmosphereLightingFromSun = environment.dynamicAtmosphereLighting

  if (environment.clockTime) {
    try {
      viewer.clock.currentTime = JulianDate.fromIso8601(environment.clockTime)
      viewer.clock.shouldAnimate = false
    } catch {
      // Invalid tenant clock configuration must not prevent the scene from loading.
    }
  }

  viewer.scene.fog.enabled = environment.fog.enabled
  viewer.scene.fog.density = environment.fog.density
  viewer.scene.fog.minimumBrightness = environment.fog.minimumBrightness
  viewer.scene.fog.screenSpaceErrorFactor = environment.fog.screenSpaceErrorFactor

  const ambientOcclusion = viewer.scene.postProcessStages.ambientOcclusion
  ambientOcclusion.enabled = environment.ambientOcclusion.enabled
  Object.assign(ambientOcclusion.uniforms, {
    intensity: environment.ambientOcclusion.intensity,
    bias: environment.ambientOcclusion.bias,
    lengthCap: environment.ambientOcclusion.lengthCap,
    directionCount: environment.ambientOcclusion.directionCount,
    stepCount: environment.ambientOcclusion.stepCount,
  })
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
    const height = readNumberProperty(entity, "height_m", now) ?? 0
    const type = readStringProperty(entity, "type", now)
    const color = layer.featureColorMode === "feature" ? readStringProperty(entity, "color", now) : (layer.typeColors[type ?? ""] ?? layer.defaultColor)
    const opacity = layer.featureColorMode === "feature" ? (readNumberProperty(entity, "opacity", now) ?? 0.82) : type === "reserved" ? 0.72 : 0.98

    if (!entity.polygon) return
    applyPolygonStyle(entity.polygon, {
      height,
      extrudedHeight: height + 0.04,
      outline: type !== "road",
      outlineColor: cssColor(layer.outlineColor, layer.outlineColor, type === "concrete" ? layer.outlineOpacity * 0.42 : layer.outlineOpacity),
      materialColor: cssColor(color, type === "road" ? "#334247" : "#65777a", opacity),
    })
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

function ringToDegreesArrayHeights(ring: BigscreenSceneLngLat[], height: number) {
  return ring.flatMap(([lng, lat]) => [lng, lat, height])
}

function getFeatureShortCode(feature: ScenePolygonFeature) {
  const name = feature.properties?.name?.trim()
  if (!name) {
    return feature.properties?.id?.trim() ?? ""
  }

  const [code] = name.split(/\s+/)
  return code || name
}

function addPerimeterLine(viewer: Viewer, ring: BigscreenSceneLngLat[], height: number, color: string, opacity: number, width = 1.2) {
  viewer.entities.add({
    polyline: {
      positions: Cartesian3.fromDegreesArrayHeights(ringToDegreesArrayHeights(ring, height)),
      width,
      material: Color.fromCssColorString(color).withAlpha(opacity),
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
  const lineCount = Math.max(3, Math.min(10, Math.floor(widthMeters / 34)))
  const stepLng = (bounds.maxLng - bounds.minLng) / lineCount
  const material = Color.fromCssColorString("#719094").withAlpha(0.24)

  for (let index = 1; index < lineCount; index += 1) {
    const lng = bounds.minLng + stepLng * index
    for (const lat of [bounds.minLat, bounds.maxLat]) {
      viewer.entities.add({
        polyline: {
          positions: [Cartesian3.fromDegrees(lng, lat, 0.25), Cartesian3.fromDegrees(lng, lat, height - 0.4)],
          width: 0.8,
          material,
        },
      })
    }
  }
}

function addRoofCap(viewer: Viewer, context: BigscreenSceneEngineMountContext, feature: ScenePolygonFeature) {
  const bounds = getFeatureBounds(feature)
  const ring = feature.geometry?.coordinates?.[0] ?? []
  const buildingLayer = context.config.buildingLayer
  if (!bounds || ring.length < 3 || !buildingLayer) {
    return
  }

  const height = feature.properties?.height_m ?? buildingLayer.defaultHeight
  const roofDeckColor = buildingLayer.featureColorMode === "feature" ? (feature.properties?.roofColor ?? buildingLayer.defaultRoofColor) : buildingLayer.defaultRoofColor
  viewer.entities.add({
    name: `${feature.properties?.name ?? "建筑"} 屋顶盖板`,
    polygon: {
      hierarchy: Cartesian3.fromDegreesArray(ring.flat()),
      height: height + 0.08,
      material: cssColor(roofDeckColor, buildingLayer.defaultRoofColor, 0.98),
      outline: false,
    },
  })

  addPerimeterLine(viewer, ring, height + 0.2, buildingLayer.roofEdgeColor, buildingLayer.roofEdgeOpacity, feature.properties?.type?.startsWith("warehouse") ? 1.4 : 1.1)
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
    maxDistance?: number
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
      font: `600 ${options.fontSize}px Geist, "PingFang SC", sans-serif`,
      fillColor: cssColor(options.color, "#f8fdff", 0.96),
      outlineColor: Color.BLACK.withAlpha(0.88),
      outlineWidth: 4,
      style: LabelStyle.FILL_AND_OUTLINE,
      verticalOrigin: VerticalOrigin.BOTTOM,
      pixelOffset: new Cartesian2(0, options.offsetY ?? -8),
      disableDepthTestDistance: Math.min(options.maxDistance ?? 900, 700),
      distanceDisplayCondition: new DistanceDisplayCondition(0, options.maxDistance ?? 900),
      scaleByDistance: new NearFarScalar(180, 1, options.maxDistance ?? 900, 0.72),
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
  const insetMeters = 6.5
  const usableWidth = Math.max(8, widthMeters - insetMeters * 2)
  const usableDepth = Math.max(8, depthMeters - insetMeters * 2)
  const west = bounds.minLng + insetMeters / metersPerLng
  const south = bounds.minLat + insetMeters / metersPerLat
  const east = west + usableWidth / metersPerLng
  const north = south + usableDepth / metersPerLat
  const height = (feature.properties?.height_m ?? buildingLayer.defaultHeight) + 0.28

  viewer.entities.add({
    name: `${feature.properties?.name ?? "建筑"} 光伏阵列`,
    polygon: {
      hierarchy: Cartesian3.fromDegreesArray([west, south, east, south, east, north, west, north]),
      height,
      material: cssColor(buildingLayer.solarPanelColor, buildingLayer.solarPanelColor, 0.96),
      outline: false,
    },
  })
  viewer.entities.add({
    name: `${feature.properties?.name ?? "建筑"} 光伏阵列分格`,
    polygon: {
      hierarchy: Cartesian3.fromDegreesArray([west, south, east, south, east, north, west, north]),
      height: height + 0.025,
      material: new GridMaterialProperty({
        color: cssColor(buildingLayer.solarPanelStrokeColor, buildingLayer.solarPanelStrokeColor, 0.42),
        cellAlpha: 0.04,
        lineCount: new Cartesian2(columns, rows),
        lineThickness: new Cartesian2(0.055, 0.055),
      }),
      outline: false,
    },
  })
}

async function addBuildingLayer(viewer: Viewer, context: BigscreenSceneEngineMountContext) {
  const layer = context.config.buildingLayer
  if (!layer) {
    return null
  }

  const dataSource = await addGeoJsonFeatureLayer(viewer, layer, (entity, now) => {
    const color = layer.featureColorMode === "feature" ? (readStringProperty(entity, "wallColor", now) ?? readStringProperty(entity, "color", now)) : layer.defaultWallColor
    const opacity = layer.featureColorMode === "feature" ? (readNumberProperty(entity, "opacity", now) ?? layer.defaultOpacity) : layer.defaultOpacity
    const height = readNumberProperty(entity, "height_m", now) ?? layer.defaultHeight

    if (!entity.polygon) return
    applyPolygonStyle(entity.polygon, {
      height: 0,
      extrudedHeight: height,
      outline: true,
      outlineColor: cssColor(layer.outlineColor, layer.outlineColor, layer.outlineOpacity),
      materialColor: cssColor(color, layer.defaultWallColor, opacity),
    })
  })

  const featureCollection = await fetchJson<SceneFeatureCollection>(layer.dataUrl)
  for (const feature of featureCollection.features) {
    addRoofCap(viewer, context, feature)
    addSolarPanels(viewer, context, feature)
    if (!layer.showLabels || !shouldShowBuildingLabel(feature)) {
      continue
    }
    const height = feature.properties?.height_m ?? layer.defaultHeight
    addFeatureLabel(viewer, feature, height + 5.5, {
      fontSize: feature.properties?.type?.startsWith("warehouse") ? 20 : 18,
      color: "#f8fdff",
      offsetY: -12,
      maxDistance: layer.labelDistance,
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
    const color = layer.featureColorMode === "feature" ? readStringProperty(entity, "color", now) : layer.defaultColor
    const opacity = layer.featureColorMode === "feature" ? (readNumberProperty(entity, "opacity", now) ?? layer.defaultOpacity) : layer.defaultOpacity
    const height = readNumberProperty(entity, "displayHeight_m", now) ?? layer.surfaceHeight
    const thickness = readNumberProperty(entity, "height_m", now) ?? layer.defaultHeight

    if (!entity.polygon) return
    applyPolygonStyle(entity.polygon, {
      height,
      extrudedHeight: height + thickness,
      outline: true,
      outlineColor: cssColor(layer.outlineColor, layer.outlineColor, layer.outlineOpacity),
      materialColor: cssColor(color, layer.defaultColor, opacity),
    })
  })

  const featureCollection = await fetchJson<SceneFeatureCollection>(layer.dataUrl)
  if (!layer.showLabels) {
    return dataSource
  }
  for (const feature of featureCollection.features) {
    const height = feature.properties?.displayHeight_m ?? layer.surfaceHeight
    const thickness = feature.properties?.height_m ?? layer.defaultHeight
    addFeatureLabel(viewer, feature, height + thickness + 1.2, {
      text: getFeatureShortCode(feature),
      fontSize: 13,
      color: "#ffffff",
      offsetY: -4,
      maxDistance: 720,
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

    applyPolygonStyle(entity.polygon, {
      height: 0,
      extrudedHeight: Number.isFinite(height) ? height : 24,
      outline: true,
      outlineColor,
      materialColor: baseColor.withAlpha(context.config.warehouseLayer.extrusionOpacity),
    })
  }

  await viewer.dataSources.add(dataSource)
  return dataSource
}

function resolveModelShadowMode(castShadows: boolean, receiveShadows: boolean) {
  if (castShadows && receiveShadows) return ShadowMode.ENABLED
  if (castShadows) return ShadowMode.CAST_ONLY
  if (receiveShadows) return ShadowMode.RECEIVE_ONLY
  return ShadowMode.DISABLED
}

function addModelLayer(viewer: Viewer, context: BigscreenSceneEngineMountContext) {
  const layer = context.config.modelLayer
  if (!layer.show) {
    return
  }

  for (const asset of layer.assets) {
    if (!asset.show) {
      continue
    }
    const position = Cartesian3.fromDegrees(asset.position[0], asset.position[1], asset.position[2])
    const orientation = Transforms.headingPitchRollQuaternion(
      position,
      new HeadingPitchRoll(CesiumMath.toRadians(asset.heading), CesiumMath.toRadians(asset.pitch), CesiumMath.toRadians(asset.roll)),
    )
    viewer.entities.add({
      id: `scene-model:${asset.id}`,
      name: asset.name ?? asset.id,
      position,
      orientation,
      properties: {
        assetKey: asset.assetKey,
        semanticType: asset.semanticType,
      },
      model: {
        uri: asset.url,
        show: true,
        scale: asset.scale,
        minimumPixelSize: asset.minimumPixelSize,
        maximumScale: asset.maximumScale,
        shadows: resolveModelShadowMode(asset.castShadows, asset.receiveShadows),
        runAnimations: false,
        incrementallyLoadTextures: true,
      },
    })
  }
}

async function addTilesetLayers(viewer: Viewer, context: BigscreenSceneEngineMountContext) {
  const tilesets: Cesium3DTileset[] = []
  for (const layer of context.config.futureLayers.tileset) {
    if (!layer.show) {
      continue
    }
    const tileset = await Cesium3DTileset.fromUrl(layer.url, {
      enableCollision: false,
      preloadWhenHidden: false,
      maximumScreenSpaceError: 12,
    })
    tileset.show = true
    viewer.scene.primitives.add(tileset)
    tilesets.push(tileset)
  }
  return tilesets
}

export function createCesiumBigscreenSceneEngine(): BigscreenSceneEngine {
  let viewer: Viewer | null = null
  let sceneDataSources: GeoJsonDataSource[] = []
  let sceneTilesets: Cesium3DTileset[] = []
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
      applyEnvironment(viewer, context)

      const imageryProvider = createImageryProvider(context)
      if (imageryProvider) {
        const imageryLayer = viewer.imageryLayers.addImageryProvider(imageryProvider)
        imageryLayer.alpha = context.config.imageryProvider.alpha
        imageryLayer.brightness = context.config.imageryProvider.brightness
        imageryLayer.contrast = context.config.imageryProvider.contrast
        imageryLayer.saturation = context.config.imageryProvider.saturation
        imageryLayer.gamma = context.config.imageryProvider.gamma
      }
      viewer.terrainProvider = await createTerrainProvider(context)
      viewer.scene.globe.depthTestAgainstTerrain = false
      applyInteractionPolicy(viewer, context.config.interactive)
      const siteDataSource = await addSiteLayer(viewer, context)
      const buildingDataSource = await addBuildingLayer(viewer, context)
      const zoneDataSource = await addZoneLayer(viewer, context)
      const warehouseDataSource = context.config.siteLayer || context.config.buildingLayer || context.config.zoneLayer ? null : await addWarehouseLayer(viewer, context)
      sceneDataSources = [siteDataSource, buildingDataSource, zoneDataSource, warehouseDataSource].filter((dataSource): dataSource is GeoJsonDataSource => Boolean(dataSource))
      addModelLayer(viewer, context)
      sceneTilesets = await addTilesetLayers(viewer, context)
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
        for (const tileset of sceneTilesets) {
          viewer.scene.primitives.remove(tileset)
        }
        viewer.entities.removeAll()
      }
      sceneDataSources = []
      sceneTilesets = []
      mountContext = null
      viewer?.destroy()
      viewer = null
    },
  }
}
