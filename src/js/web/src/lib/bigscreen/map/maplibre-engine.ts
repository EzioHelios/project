import "maplibre-gl/dist/maplibre-gl.css"

import maplibregl from "maplibre-gl"

import { buildWarehouseStatusColorExpression, resolveInitialCamera } from "@/lib/bigscreen/map/scene"
import type { BigscreenSceneEngine, BigscreenSceneEngineMountContext } from "@/lib/bigscreen/map/types"

const WAREHOUSE_SOURCE_ID = "bigscreen-warehouses"

function applyInteractionPolicy(map: maplibregl.Map, interactive: boolean) {
  if (interactive) {
    return
  }

  map.dragPan.disable()
  map.scrollZoom.disable()
  map.boxZoom.disable()
  map.dragRotate.disable()
  map.keyboard.disable()
  map.doubleClickZoom.disable()
  map.touchZoomRotate.disable()
}

function addWarehouseLayers(map: maplibregl.Map, context: BigscreenSceneEngineMountContext) {
  if (map.getSource(WAREHOUSE_SOURCE_ID)) {
    return
  }

  const statusColorExpression = buildWarehouseStatusColorExpression(context.config) as unknown as maplibregl.DataDrivenPropertyValueSpecification<string>

  map.addSource(WAREHOUSE_SOURCE_ID, {
    type: "geojson",
    data: context.warehouses,
  })

  map.addLayer({
    id: "warehouse-footprint",
    type: "fill",
    source: WAREHOUSE_SOURCE_ID,
    paint: {
      "fill-color": statusColorExpression,
      "fill-opacity": context.config.warehouseLayer.fillOpacity,
    },
  })

  map.addLayer({
    id: "warehouse-outline",
    type: "line",
    source: WAREHOUSE_SOURCE_ID,
    paint: {
      "line-color": context.config.warehouseLayer.outlineColor,
      "line-opacity": context.config.warehouseLayer.outlineOpacity,
      "line-width": context.config.warehouseLayer.outlineWidth,
    },
  })

  map.addLayer({
    id: "warehouse-extrusion",
    type: "fill-extrusion",
    source: WAREHOUSE_SOURCE_ID,
    paint: {
      "fill-extrusion-color": statusColorExpression,
      "fill-extrusion-base": 0,
      "fill-extrusion-height": ["coalesce", ["get", "height_m"], 24],
      "fill-extrusion-opacity": context.config.warehouseLayer.extrusionOpacity,
      "fill-extrusion-vertical-gradient": true,
    },
  })
}

function applyCamera(map: maplibregl.Map, context: BigscreenSceneEngineMountContext) {
  const initialCamera = resolveInitialCamera(context.config, context.warehouses)
  if (initialCamera.kind === "bounds") {
    map.fitBounds(initialCamera.bounds, {
      bearing: context.config.maplibre?.cameraFallback.bearing ?? context.config.cameraHome.heading,
      pitch: context.config.maplibre?.cameraFallback.pitch ?? Math.abs(context.config.cameraHome.pitch),
      padding: initialCamera.padding,
      maxZoom: context.config.maplibre?.cameraFallback.maxZoom ?? 17.1,
      duration: 0,
    })
    return
  }

  const fallbackCamera = context.config.maplibre?.cameraFallback
  map.jumpTo({
    center: fallbackCamera?.center ?? initialCamera.center,
    zoom: fallbackCamera?.zoom ?? 16.45,
    bearing: fallbackCamera?.bearing ?? initialCamera.heading,
    pitch: fallbackCamera?.pitch ?? Math.abs(initialCamera.pitch),
  })
}

export function createMaplibreBigscreenSceneEngine(): BigscreenSceneEngine {
  let map: maplibregl.Map | null = null

  return {
    mount(context) {
      if (map) {
        map.remove()
      }

      map = new maplibregl.Map({
        container: context.container,
        style: context.config.maplibre?.styleUrl ?? "",
        center: context.config.maplibre?.cameraFallback.center ?? context.config.center,
        zoom: context.config.maplibre?.cameraFallback.zoom ?? 16.45,
        pitch: context.config.maplibre?.cameraFallback.pitch ?? 54,
        bearing: context.config.maplibre?.cameraFallback.bearing ?? -18,
        attributionControl: false,
      })

      applyInteractionPolicy(map, context.config.interactive)

      map.once("load", () => {
        if (!map) {
          return
        }
        addWarehouseLayers(map, context)
        applyCamera(map, context)
        context.onReady?.()
      })

      map.on("error", (event) => {
        const message = event.error instanceof Error ? event.error.message : typeof event.error === "string" ? event.error : "Map rendering failed"
        context.onError?.(new Error(message))
      })
    },
    resize() {
      map?.resize()
    },
    destroy() {
      map?.remove()
      map = null
    },
  }
}

export const createMaplibreBigscreenMapEngine = createMaplibreBigscreenSceneEngine
