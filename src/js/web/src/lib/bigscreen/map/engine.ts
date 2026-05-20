import maplibregl from "maplibre-gl"

import { buildWarehouseStatusColorExpression, resolveInitialCamera } from "@/lib/bigscreen/map/scene"
import type { BigscreenMapEngine, BigscreenMapEngineMountContext } from "@/lib/bigscreen/map/types"

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

function addWarehouseLayers(map: maplibregl.Map, context: BigscreenMapEngineMountContext) {
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
      "fill-opacity": 0.18,
    },
  })

  map.addLayer({
    id: "warehouse-outline",
    type: "line",
    source: WAREHOUSE_SOURCE_ID,
    paint: {
      "line-color": "#d7f7ff",
      "line-opacity": 0.72,
      "line-width": 1.25,
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
      "fill-extrusion-opacity": 0.88,
      "fill-extrusion-vertical-gradient": true,
    },
  })
}

function applyCamera(map: maplibregl.Map, context: BigscreenMapEngineMountContext) {
  const initialCamera = resolveInitialCamera(context.config, context.warehouses)
  if (initialCamera.kind === "bounds") {
    map.fitBounds(initialCamera.bounds, {
      bearing: initialCamera.bearing,
      pitch: initialCamera.pitch,
      padding: initialCamera.padding,
      maxZoom: initialCamera.maxZoom,
      duration: 0,
    })
    return
  }

  map.jumpTo({
    center: initialCamera.center,
    zoom: initialCamera.zoom,
    bearing: initialCamera.bearing,
    pitch: initialCamera.pitch,
  })
}

export function createMaplibreBigscreenMapEngine(): BigscreenMapEngine {
  let map: maplibregl.Map | null = null

  return {
    mount(context) {
      if (map) {
        map.remove()
      }

      map = new maplibregl.Map({
        container: context.container,
        style: context.config.styleUrl,
        center: context.config.cameraFallback.center,
        zoom: context.config.cameraFallback.zoom,
        pitch: context.config.cameraFallback.pitch,
        bearing: context.config.cameraFallback.bearing,
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
