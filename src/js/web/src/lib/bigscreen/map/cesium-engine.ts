import {
  Cartesian3,
  Math as CesiumMath,
  CesiumTerrainProvider,
  Color,
  Credit,
  EllipsoidTerrainProvider,
  GeoJsonDataSource,
  JulianDate,
  UrlTemplateImageryProvider,
  Viewer,
} from "cesium"

import { getWarehouseStatusColor, resolveInitialCamera } from "@/lib/bigscreen/map/scene"
import type { BigscreenSceneEngine, BigscreenSceneEngineMountContext, BigscreenSceneLngLat } from "@/lib/bigscreen/map/types"

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
  viewer.camera.setView({
    destination: Cartesian3.fromDegrees(target.center[0], target.center[1], target.height),
    orientation: {
      heading: CesiumMath.toRadians(target.heading),
      pitch: CesiumMath.toRadians(target.pitch),
      roll: CesiumMath.toRadians(target.roll),
    },
  })
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
  let warehouseDataSource: GeoJsonDataSource | null = null

  return {
    async mount(context) {
      if (viewer) {
        viewer.destroy()
      }

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
        shadows: context.config.viewerOptions.shadows,
        requestRenderMode: context.config.viewerOptions.requestRenderMode,
        maximumRenderTimeChange: context.config.viewerOptions.maximumRenderTimeChange,
        msaaSamples: context.config.viewerOptions.msaaSamples,
      })

      viewer.imageryLayers.addImageryProvider(createImageryProvider(context))
      viewer.terrainProvider = await createTerrainProvider(context)
      viewer.scene.globe.depthTestAgainstTerrain = false
      applyInteractionPolicy(viewer, context.config.interactive)
      warehouseDataSource = await addWarehouseLayer(viewer, context)
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
      viewer.scene.requestRender()
    },
    destroy() {
      if (viewer && warehouseDataSource) {
        viewer.dataSources.remove(warehouseDataSource, true)
      }
      warehouseDataSource = null
      viewer?.destroy()
      viewer = null
    },
  }
}
