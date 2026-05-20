import "maplibre-gl/dist/maplibre-gl.css"

import { useEffect, useRef, useState } from "react"

import { createMaplibreBigscreenMapEngine } from "@/lib/bigscreen/map/engine"
import { loadBigscreenMapScene, resolveBigscreenPublicUrl } from "@/lib/bigscreen/map/scene"
import type { BigscreenLoadedMapScene, BigscreenMapEngine } from "@/lib/bigscreen/map/types"

type BigscreenMapLoadState = { status: "loading"; message: string } | { status: "ready"; message?: string } | { status: "error"; message: string }

export function BigscreenMapScene({
  manifestUrl = resolveBigscreenPublicUrl("maps/bigscreen/scene.json"),
  createEngine = createMaplibreBigscreenMapEngine,
  className,
  variant = "panel",
}: {
  manifestUrl?: string
  createEngine?: () => BigscreenMapEngine
  className?: string
  variant?: "panel" | "stage"
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const engineRef = useRef<BigscreenMapEngine | null>(null)
  const observerRef = useRef<ResizeObserver | null>(null)
  const [scene, setScene] = useState<BigscreenLoadedMapScene | null>(null)
  const [loadState, setLoadState] = useState<BigscreenMapLoadState>({
    status: "loading",
    message: "正在装载底图与仓库块体",
  })

  useEffect(() => {
    let cancelled = false

    async function mountScene() {
      setLoadState({
        status: "loading",
        message: "正在装载底图与仓库块体",
      })

      try {
        const loadedScene = await loadBigscreenMapScene(manifestUrl)
        if (cancelled || !containerRef.current) {
          return
        }

        setScene(loadedScene)
        const engine = createEngine()
        engineRef.current = engine
        engine.mount({
          container: containerRef.current,
          config: loadedScene.config,
          warehouses: loadedScene.warehouses,
          onReady: () => {
            if (!cancelled) {
              setLoadState({ status: "ready" })
            }
          },
          onError: (error) => {
            if (!cancelled) {
              setLoadState({
                status: "error",
                message: error.message || "地图渲染失败，已保留主视觉画布",
              })
            }
          },
        })

        if (typeof ResizeObserver !== "undefined") {
          const observer = new ResizeObserver(() => {
            engine.resize()
          })
          observer.observe(containerRef.current)
          observerRef.current = observer
        }
      } catch (error) {
        if (!cancelled) {
          setLoadState({
            status: "error",
            message: error instanceof Error ? error.message : "地图资源加载失败，已保留主视觉画布",
          })
        }
      }
    }

    mountScene()

    return () => {
      cancelled = true
      observerRef.current?.disconnect()
      observerRef.current = null
      engineRef.current?.destroy()
      engineRef.current = null
    }
  }, [createEngine, manifestUrl])

  return (
    <div className={`bigscreen-map-frame ${variant === "stage" ? "bigscreen-map-frame-stage" : ""} ${className ?? ""}`.trim()}>
      <div ref={containerRef} className="bigscreen-map-canvas" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} />
      <div className="bigscreen-map-shade" />
      {loadState.status !== "ready" ? (
        <div className="bigscreen-map-state">
          <div className="bigscreen-map-state-title">{loadState.status === "error" ? "Map Fallback" : "Map Loading"}</div>
          <div className="bigscreen-map-state-body">{loadState.message}</div>
        </div>
      ) : null}
      {scene?.config.attributionLabel ? <div className="bigscreen-map-attribution">{scene.config.attributionLabel}</div> : null}
    </div>
  )
}
