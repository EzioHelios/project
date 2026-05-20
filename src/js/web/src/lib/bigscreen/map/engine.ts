import type { BigscreenSceneEngine, BigscreenSceneEngineKind } from "@/lib/bigscreen/map/types"

export async function createDefaultBigscreenSceneEngine(sceneEngine: BigscreenSceneEngineKind): Promise<BigscreenSceneEngine> {
  if (sceneEngine === "maplibre") {
    const { createMaplibreBigscreenSceneEngine } = await import("@/lib/bigscreen/map/maplibre-engine")
    return createMaplibreBigscreenSceneEngine()
  }

  const { createCesiumBigscreenSceneEngine } = await import("@/lib/bigscreen/map/cesium-engine")
  return createCesiumBigscreenSceneEngine()
}

export async function createCesiumBigscreenSceneEngine() {
  const module = await import("@/lib/bigscreen/map/cesium-engine")
  return module.createCesiumBigscreenSceneEngine()
}

export async function createMaplibreBigscreenSceneEngine() {
  const module = await import("@/lib/bigscreen/map/maplibre-engine")
  return module.createMaplibreBigscreenSceneEngine()
}

export const createMaplibreBigscreenMapEngine = createMaplibreBigscreenSceneEngine
