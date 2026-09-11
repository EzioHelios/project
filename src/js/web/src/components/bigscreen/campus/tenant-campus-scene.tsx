import { useEffect, useRef, useState } from "react"
import { BigscreenSceneCanvas } from "@/components/bigscreen/scene-canvas"
import { useAuthStore } from "@/lib/auth"
import { fetchSceneAsset, fetchSceneManifest, SceneNotConfiguredError } from "@/lib/bigscreen/campus/api"
import type { CampusManifest, CampusRuntime, CampusViewState } from "@/lib/bigscreen/campus/types"
import "./campus.css"

export function TenantCampusScene({ showControls }: { showControls: boolean }) {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return <CampusScene key={teamId ?? "no-team"} teamId={teamId} showControls={showControls} />
}

function CampusScene({ teamId, showControls }: { teamId?: string; showControls: boolean }) {
  const container = useRef<HTMLDivElement>(null)
  const runtime = useRef<CampusRuntime | null>(null)
  const [manifest, setManifest] = useState<CampusManifest | null>(null)
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading")
  const [message, setMessage] = useState(teamId ? "正在加载园区模型" : "请选择租户")
  const [view, setView] = useState<CampusViewState>({ mode: "orbit", entry: null, night: false })
  const [reference, setReference] = useState<string | null>(null)
  const [showReference, setShowReference] = useState(false)

  useEffect(() => {
    if (!teamId) return
    const controller = new AbortController()
    let imageUrl: string | null = null
    let disposed = false
    async function mount() {
      try {
        const loaded = await fetchSceneManifest(teamId as string, controller.signal)
        if (disposed) return
        if (loaded.engine === "cesium") {
          setManifest(loaded)
          setStatus("ready")
          return
        }
        const createCampusRuntime =
          loaded.engine === "cesium-campus"
            ? (await import("@/lib/bigscreen/campus/cesium-runtime")).createCesiumCampusRuntime
            : (await import("@/lib/bigscreen/campus/runtime")).createCampusRuntime
        if (disposed || !container.current) return
        setManifest(loaded)
        runtime.current = createCampusRuntime(
          container.current,
          loaded,
          controller.signal,
          (state) => {
            if (!disposed) setView(state)
          },
          () => {
            if (!disposed) setStatus("ready")
          },
          (error) => {
            if (!disposed) {
              setMessage(error.message)
              setStatus("error")
            }
          },
        )
        if (loaded.reference) {
          try {
            const response = await fetchSceneAsset(loaded.reference, loaded.teamId, controller.signal)
            const blob = await response.blob()
            if (disposed) return
            imageUrl = URL.createObjectURL(blob)
            setReference(imageUrl)
          } catch {
            /* The reference image is optional; model failures are reported separately. */
          }
        }
      } catch (error) {
        if (!disposed) {
          setStatus(error instanceof SceneNotConfiguredError ? "empty" : "error")
          setMessage(error instanceof Error ? error.message : "园区模型加载失败")
        }
      }
    }
    void mount()
    return () => {
      disposed = true
      controller.abort()
      runtime.current?.dispose()
      runtime.current = null
      if (imageUrl) URL.revokeObjectURL(imageUrl)
    }
  }, [teamId])

  useEffect(() => {
    if (!showControls) runtime.current?.home()
  }, [showControls])

  const ready = status === "ready"
  if (manifest?.engine === "cesium") return <BigscreenSceneCanvas key={`${teamId}:${manifest.revision}`} variant="stage" manifestUrl={manifest.legacyManifest} />
  return (
    <div
      className={`campus-shell ${view.night ? "campus-night" : ""}`}
      data-team-id={teamId}
      data-scene-status={status}
      data-scene-id={manifest?.sceneId}
      data-scene-engine={manifest?.engine}
    >
      {/* biome-ignore lint/a11y/noNoninteractiveTabindex: This WebGL application surface handles camera keyboard input. */}
      <div ref={container} className="campus-canvas" role="application" aria-label="园区三维漫游" tabIndex={0} style={{ pointerEvents: "auto" }} />
      {status !== "ready" && <output className="campus-message">{message}</output>}
      {showControls && ready && manifest && (
        <>
          <div className="campus-place">
            <strong>{manifest.title}</strong>
            <span>{manifest.address}</span>
          </div>
          <div className="campus-tools" role="toolbar" aria-label="模型视图控制">
            <button type="button" onClick={() => runtime.current?.home()}>
              总览
            </button>
            <button type="button" onClick={() => runtime.current?.home(true)}>
              俯视
            </button>
            <button type="button" aria-pressed={view.night} onClick={() => runtime.current?.toggleNight()}>
              {view.night ? "日景" : "夜景"}
            </button>
            {reference && (
              <button
                type="button"
                aria-pressed={showReference}
                onClick={() => {
                  setShowReference(!showReference)
                  if (!showReference) runtime.current?.home(true)
                }}
              >
                卫星对照
              </button>
            )}
          </div>
          {showReference && reference && (
            <div className="campus-reference">
              <div>
                <strong>同位置卫星影像</strong>
                <button type="button" aria-label="关闭卫星对照" onClick={() => setShowReference(false)}>
                  ×
                </button>
              </div>
              <img src={reference} alt={`${manifest.title}卫星影像，北向上`} />
              <small>{manifest.attribution}</small>
            </div>
          )}
          <div className="campus-navigation">
            <nav aria-label="漫游入口">
              <button type="button" aria-pressed={view.mode === "orbit"} onClick={() => runtime.current?.home()}>
                全景环绕
              </button>
              {manifest.world.entries.map((entry) => (
                <button type="button" key={entry.id} aria-pressed={view.entry === entry.id} onClick={() => runtime.current?.enter(entry.id)}>
                  {entry.label}
                </button>
              ))}
            </nav>
            <p>
              {view.mode === "orbit"
                ? manifest.engine === "cesium-campus"
                  ? "拖动移动 · 滚轮缩放 · 中键倾斜"
                  : "拖动旋转 · 滚轮缩放 · 右键平移"
                : "W A S D 行走 · 拖动 / Q E 转向 · Shift 加速 · Esc 返回"}
            </p>
          </div>
          {view.mode === "walk" && (
            <div className="campus-walk-pad" role="toolbar" aria-label="步行控制">
              {(
                [
                  { id: "forward", label: "向前走", icon: "↑" },
                  { id: "left", label: "向左走", icon: "←" },
                  { id: "back", label: "向后走", icon: "↓" },
                  { id: "right", label: "向右走", icon: "→" },
                ] as const
              ).map((motion) => (
                <button type="button" key={motion.id} aria-label={motion.label} onClick={() => runtime.current?.move(motion.id)}>
                  {motion.icon}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
