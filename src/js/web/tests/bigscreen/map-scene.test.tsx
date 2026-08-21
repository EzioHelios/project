import { render, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { BigscreenSceneCanvas } from "@/components/bigscreen/scene-canvas"
import { getWarehouseStatusColor, loadBigscreenScene, loadBigscreenSceneCandidates, normalizeBigscreenSceneConfig, resolveInitialCamera } from "@/lib/bigscreen/map/scene"
import { resolveTenantBigscreenSceneManifestCandidates } from "@/lib/bigscreen/map/scene-resolver"
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
    expect(config.environment.lighting).toBe(true)
    expect(config.modelLayer.assets).toEqual([])
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

  it("resolves stable tenant scene namespaces before the platform fallback", () => {
    expect(resolveTenantBigscreenSceneManifestCandidates({ id: "019abcde-1234-7000-8000-000000000001", slug: "Taizhou-Park" }, "maps/fallback/scene.json")).toEqual([
      "/maps/tenants/taizhou-park/scene.json",
      "/maps/tenants/019abcde-1234-7000-8000-000000000001/scene.json",
      "/maps/fallback/scene.json",
    ])
    expect(resolveTenantBigscreenSceneManifestCandidates({ slug: "../../unsafe" }, "maps/fallback/scene.json")).toEqual(["/maps/fallback/scene.json"])
  })
})

describe("tenant scene manifests", () => {
  const originalFetch = global.fetch

  afterEach(() => {
    global.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it("inherits the platform template while keeping asset URLs relative to their owning manifest", async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(typeof input === "string" ? input : input.toString(), window.location.origin)
      if (url.pathname === "/maps/tenants/acme/scene.json") {
        return new Response(
          JSON.stringify({
            extends: "../../templates/industrial-v2.json",
            sceneId: "acme-campus",
            center: [120, 30],
            warehouseLayer: { dataUrl: "./warehouses.geojson" },
          }),
          { status: 200 },
        )
      }
      if (url.pathname === "/maps/templates/industrial-v2.json") {
        return new Response(
          JSON.stringify({
            sceneEngine: "cesium",
            modelLayer: {
              assets: [{ id: "tank", url: "./models/tank.glb", position: [120, 30, 0] }],
            },
          }),
          { status: 200 },
        )
      }
      if (url.pathname === "/maps/tenants/acme/warehouses.geojson") {
        return new Response(JSON.stringify(warehouses), { status: 200 })
      }
      return new Response("not found", { status: 404 })
    }) as typeof fetch

    const loaded = await loadBigscreenScene("/maps/tenants/acme/scene.json")

    expect(loaded.config.sceneId).toBe("acme-campus")
    expect(loaded.config.modelLayer.assets[0]?.url).toBe("http://localhost:3000/maps/templates/models/tank.glb")
    expect(loaded.config.warehouseLayer.dataUrl).toBe("http://localhost:3000/maps/tenants/acme/warehouses.geojson")
  })

  it("falls back only when a tenant manifest is absent", async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(typeof input === "string" ? input : input.toString(), window.location.origin)
      if (url.pathname === "/maps/tenants/missing/scene.json") {
        return new Response("not found", { status: 404 })
      }
      if (url.pathname === "/maps/fallback/scene.json") {
        return new Response(JSON.stringify(manifest), { status: 200 })
      }
      if (url.pathname === "/maps/fallback/warehouses.geojson") {
        return new Response(JSON.stringify(warehouses), { status: 200 })
      }
      return new Response("not found", { status: 404 })
    }) as typeof fetch

    const loaded = await loadBigscreenSceneCandidates(["/maps/tenants/missing/scene.json", "/maps/fallback/scene.json"])
    expect(loaded.manifestUrl).toBe("http://localhost:3000/maps/fallback/scene.json")
  })

  it("treats a Vite SPA HTML response as an absent tenant manifest", async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(typeof input === "string" ? input : input.toString(), window.location.origin)
      if (url.pathname === "/maps/tenants/default-tenant/scene.json") {
        return new Response("<!DOCTYPE html><html><body>Vite app shell</body></html>", {
          status: 200,
          headers: { "content-type": "text/html" },
        })
      }
      if (url.pathname === "/maps/fallback/scene.json") {
        return new Response(JSON.stringify(manifest), { status: 200 })
      }
      if (url.pathname === "/maps/fallback/warehouses.geojson") {
        return new Response(JSON.stringify(warehouses), { status: 200 })
      }
      return new Response("not found", { status: 404 })
    }) as typeof fetch

    const loaded = await loadBigscreenSceneCandidates(["/maps/tenants/default-tenant/scene.json", "/maps/fallback/scene.json"])

    expect(loaded.manifestUrl).toBe("http://localhost:3000/maps/fallback/scene.json")
  })

  it("does not hide malformed tenant JSON behind the platform fallback", async () => {
    const fallbackFetch = vi.fn()
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(typeof input === "string" ? input : input.toString(), window.location.origin)
      if (url.pathname === "/maps/tenants/broken/scene.json") {
        return new Response('{"sceneId":', { status: 200 })
      }
      if (url.pathname === "/maps/fallback/scene.json") {
        fallbackFetch()
        return new Response(JSON.stringify(manifest), { status: 200 })
      }
      return new Response("not found", { status: 404 })
    }) as typeof fetch

    await expect(loadBigscreenSceneCandidates(["/maps/tenants/broken/scene.json", "/maps/fallback/scene.json"])).rejects.toThrow("Invalid JSON")
    expect(fallbackFetch).not.toHaveBeenCalled()
  })

  it("does not hide a broken tenant scene behind the platform fallback", async () => {
    const fallbackFetch = vi.fn()
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(typeof input === "string" ? input : input.toString(), window.location.origin)
      if (url.pathname === "/maps/tenants/broken/scene.json") {
        return new Response(JSON.stringify(manifest), { status: 200 })
      }
      if (url.pathname === "/maps/tenants/broken/warehouses.geojson") {
        return new Response("not found", { status: 404 })
      }
      if (url.pathname === "/maps/fallback/scene.json") {
        fallbackFetch()
        return new Response(JSON.stringify(manifest), { status: 200 })
      }
      return new Response("not found", { status: 404 })
    }) as typeof fetch

    await expect(loadBigscreenSceneCandidates(["/maps/tenants/broken/scene.json", "/maps/fallback/scene.json"])).rejects.toThrow("warehouses.geojson")
    expect(fallbackFetch).not.toHaveBeenCalled()
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
