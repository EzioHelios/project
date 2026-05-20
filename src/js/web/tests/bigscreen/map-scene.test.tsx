import { render, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { BigscreenSceneCanvas } from "@/components/bigscreen/scene-canvas"
import { getWarehouseStatusColor, normalizeBigscreenSceneConfig, resolveInitialCamera } from "@/lib/bigscreen/map/scene"
import type { BigscreenSceneEngine, BigscreenWarehouseFeatureCollection } from "@/lib/bigscreen/map/types"

const manifest = {
  sceneEngine: "cesium",
  center: [119.890793, 32.421059],
  warehouseLayer: {
    dataUrl: "./warehouses.geojson",
    statusColors: {
      normal: "#38bdf8",
      active: "#22c55e",
      warning: "#f59e0b",
    },
  },
}

const warehouses: BigscreenWarehouseFeatureCollection = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: {
        id: "w1",
        name: "Warehouse 1",
        status: "active",
        height_m: 28,
      },
      geometry: {
        type: "Polygon",
        coordinates: [[[119.89, 32.421], [119.891, 32.421], [119.891, 32.42], [119.89, 32.42], [119.89, 32.421]]],
      },
    },
  ],
}

class ResizeObserverMock {
  public observe = vi.fn()
  public disconnect = vi.fn()
}

describe("bigscreen map scene helpers", () => {
  it("applies default scene config values", () => {
    const config = normalizeBigscreenSceneConfig({
      warehouseLayer: {
        dataUrl: "./warehouses.geojson",
      },
    })

    expect(config.sceneEngine).toBe("cesium")
    expect(config.coordinateSystem).toBe("wgs84")
    expect(config.interactive).toBe(true)
    expect(config.cameraHome.center).toEqual([119.890793, 32.421059])
    expect(config.warehouseLayer.statusColors.normal).toBe("#38bdf8")
    expect(config.futureLayers.tileset).toEqual([])
  })

  it("maps warehouse status to configured colors", () => {
    const config = normalizeBigscreenSceneConfig({
      warehouseLayer: {
        dataUrl: "./warehouses.geojson",
        statusColors: {
          normal: "#111111",
          active: "#222222",
        },
      },
    })

    expect(getWarehouseStatusColor(config, "active")).toBe("#222222")
    expect(getWarehouseStatusColor(config, "unknown")).toBe("#111111")
  })

  it("prefers fitBounds when warehouse geometry exists", () => {
    const config = normalizeBigscreenSceneConfig({
      center: [119.890793, 32.421059],
      warehouseLayer: {
        dataUrl: "./warehouses.geojson",
      },
    })

    const initialCamera = resolveInitialCamera(config, warehouses)

    expect(initialCamera.kind).toBe("bounds")
    if (initialCamera.kind === "bounds") {
      expect(initialCamera.bounds[0][0]).toBeLessThan(initialCamera.bounds[1][0])
      expect(initialCamera.bounds[0][1]).toBeLessThan(initialCamera.bounds[1][1])
    }
  })

  it("falls back to configured camera when no geometry exists", () => {
    const config = normalizeBigscreenSceneConfig({
      center: [119.890793, 32.421059],
      warehouseLayer: {
        dataUrl: "./warehouses.geojson",
      },
    })

    const initialCamera = resolveInitialCamera(config, {
      type: "FeatureCollection",
      features: [],
    })

    expect(initialCamera.kind).toBe("fallback")
    if (initialCamera.kind === "fallback") {
      expect(initialCamera.center).toEqual(config.cameraHome.center)
      expect(initialCamera.height).toBe(config.cameraHome.height)
    }
  })
})

describe("BigscreenSceneCanvas", () => {
  const originalFetch = global.fetch
  const originalResizeObserver = global.ResizeObserver

  beforeEach(() => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString()
      if (url.endsWith("/scene.json")) {
        return new Response(JSON.stringify(manifest), { status: 200 })
      }
      if (url.endsWith("/warehouses.geojson")) {
        return new Response(JSON.stringify(warehouses), { status: 200 })
      }
      return new Response("not found", { status: 404 })
    }) as typeof fetch
    global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver
  })

  afterEach(() => {
    global.fetch = originalFetch
    global.ResizeObserver = originalResizeObserver
    vi.restoreAllMocks()
  })

  it("destroys the map engine on unmount", async () => {
    const mount = vi.fn()
    const resize = vi.fn()
    const destroy = vi.fn()

    const createEngine = (): BigscreenSceneEngine => ({
      mount,
      resize,
      destroy,
    })

    const { unmount } = render(<BigscreenSceneCanvas manifestUrl="/maps/bigscreen/scene.json" createEngine={createEngine} />)

    await waitFor(() => {
      expect(mount).toHaveBeenCalledTimes(1)
    })

    unmount()

    expect(destroy).toHaveBeenCalledTimes(1)
  })
})
