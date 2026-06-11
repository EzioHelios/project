import "cesium/Build/Cesium/Widgets/widgets.css"

import { useEffect, useRef, useState } from "react"

import { createDefaultBigscreenSceneEngine } from "@/lib/bigscreen/map/engine"
import { loadBigscreenScene, resolveBigscreenPublicUrl } from "@/lib/bigscreen/map/scene"
import type { BigscreenLoadedScene, BigscreenSceneEngine, BigscreenSceneEngineKind } from "@/lib/bigscreen/map/types"

type BigscreenSceneLoadState = { status: "loading"; message: string } | { status: "ready"; message?: string } | { status: "error"; message: string }

export function BigscreenSceneCanvas({
  manifestUrl = resolveBigscreenPublicUrl("maps/taizhou-warehouse/scene.json"),
  createEngine = createDefaultBigscreenSceneEngine,
  className,
  variant = "panel",
}: {
  manifestUrl?: string
  createEngine?: (sceneEngine: BigscreenSceneEngineKind) => Promise<BigscreenSceneEngine> | BigscreenSceneEngine
  className?: string
  variant?: "panel" | "stage"
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const engineRef = useRef<BigscreenSceneEngine | null>(null)
  const observerRef = useRef<ResizeObserver | null>(null)
  const [scene, setScene] = useState<BigscreenLoadedScene | null>(null)
  const [loadState, setLoadState] = useState<BigscreenSceneLoadState>({
    status: "loading",
    message: "正在加载园区场景",
  })

  useEffect(() => {
    let cancelled = false

    async function mountScene() {
      setLoadState({
        status: "loading",
        message: "正在加载园区场景",
      })

      try {
        const loadedScene = await loadBigscreenScene(manifestUrl)
        if (cancelled || !containerRef.current) {
          return
        }

        setScene(loadedScene)
        const engine = await createEngine(loadedScene.config.sceneEngine)
        engineRef.current = engine
        await engine.mount({
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
                message: error.message || "场景渲染失败，请检查资源配置",
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
            message: error instanceof Error ? error.message : "场景资源加载失败，请检查资源配置",
          })
        }
      }
    }

    void mountScene()

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
          <div className="bigscreen-map-state-title">{loadState.status === "error" ? "场景加载异常" : "场景载入中"}</div>
          <div className="bigscreen-map-state-body">{loadState.message}</div>
        </div>
      ) : null}
      {scene?.config.attributionLabel ? <div className="bigscreen-map-attribution">{scene.config.attributionLabel}</div> : null}
    </div>
  )
}
