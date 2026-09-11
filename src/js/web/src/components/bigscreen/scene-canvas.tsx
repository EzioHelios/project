import "cesium/Build/Cesium/Widgets/widgets.css"

import { useEffect, useRef, useState } from "react"

import { createDefaultBigscreenSceneEngine } from "@/lib/bigscreen/map/engine"
import { loadBigscreenSceneCandidates } from "@/lib/bigscreen/map/scene"
import type { BigscreenLoadedScene, BigscreenSceneEngine, BigscreenSceneEngineKind } from "@/lib/bigscreen/map/types"

type BigscreenSceneLoadState = { status: "loading"; message: string } | { status: "ready"; message?: string } | { status: "error"; message: string }

export function BigscreenSceneCanvas({
  manifestUrl,
  manifestUrls,
  createEngine = createDefaultBigscreenSceneEngine,
  className,
  variant = "panel",
}: {
  manifestUrl?: string
  manifestUrls?: string[]
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
  const manifestCandidateKey = (manifestUrls?.length ? manifestUrls : [manifestUrl]).filter(Boolean).join("|")

  useEffect(() => {
    let cancelled = false
    let ownedEngine: BigscreenSceneEngine | null = null
    let ownedObserver: ResizeObserver | null = null

    async function mountScene() {
      const manifestCandidates = manifestCandidateKey.split("|").filter(Boolean)
      setLoadState({
        status: "loading",
        message: "正在加载园区场景",
      })

      try {
        const loadedScene = await loadBigscreenSceneCandidates(manifestCandidates)
        if (cancelled || !containerRef.current) {
          return
        }

        setScene(loadedScene)
        const engine = await createEngine(loadedScene.config.sceneEngine)
        if (cancelled || !containerRef.current) {
          engine.destroy()
          return
        }
        ownedEngine = engine
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

        if (!cancelled && typeof ResizeObserver !== "undefined") {
          const observer = new ResizeObserver(() => {
            engine.resize()
          })
          observer.observe(containerRef.current)
          ownedObserver = observer
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
      ownedObserver?.disconnect()
      if (observerRef.current === ownedObserver) observerRef.current = null
      ownedEngine?.destroy()
      if (engineRef.current === ownedEngine) engineRef.current = null
    }
  }, [createEngine, manifestCandidateKey])

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
