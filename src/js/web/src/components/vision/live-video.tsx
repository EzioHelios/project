import Hls from "hls.js"
import { RefreshCw } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useAuthStore } from "@/lib/auth"

export function LiveVideo({ cameraId, streamPath }: { cameraId: number; streamPath?: string }) {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  const video = useRef<HTMLVideoElement>(null)
  const [attempt, setAttempt] = useState(0)
  const [status, setStatus] = useState("正在连接视频")
  // biome-ignore lint/correctness/useExhaustiveDependencies: retry explicitly recreates the HLS connection.
  useEffect(() => {
    const element = video.current
    if (!element || !teamId || !streamPath) {
      setStatus("未配置播放通道")
      return
    }
    if (!Hls.isSupported()) {
      setStatus("当前浏览器不支持此视频格式")
      return
    }
    setStatus("正在连接视频")
    const hls = new Hls({
      lowLatencyMode: false,
      xhrSetup: (xhr) => {
        xhr.withCredentials = true
        xhr.setRequestHeader("X-Team-Id", teamId)
      },
    })
    let disposed = false
    let lastTime = -1
    let lastProgress = Date.now()
    hls.on(Hls.Events.ERROR, (_, data) => {
      if (data.fatal) setStatus("视频连接中断")
    })
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      void element.play().catch(() => {
        if (!disposed) setStatus("请点击播放")
      })
    })
    hls.loadSource(`/api/vision/cameras/${cameraId}/stream/index.m3u8`)
    hls.attachMedia(element)
    const timer = window.setInterval(() => {
      if (element.currentTime > lastTime && element.readyState >= 2 && !element.paused) {
        lastProgress = Date.now()
        lastTime = element.currentTime
        setStatus("")
      } else if (Date.now() - lastProgress > 12000) {
        setStatus(element.paused ? "播放已暂停" : "视频连接中断")
      }
    }, 1000)
    return () => {
      disposed = true
      clearInterval(timer)
      hls.destroy()
      element.removeAttribute("src")
      element.load()
    }
  }, [cameraId, teamId, streamPath, attempt])
  return (
    <div className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-black">
      <video ref={video} aria-label="摄像头实时视频" autoPlay muted playsInline controls className="h-full w-full object-contain" />
      <output className="absolute left-3 top-3 flex items-center gap-2 bg-black/80 px-3 py-1 text-sm text-white" aria-live="polite">
        {status || "视频播放中"}
        {status && streamPath ? (
          <button type="button" title="重新连接视频" aria-label="重新连接视频" onClick={() => setAttempt((value) => value + 1)}>
            <RefreshCw size={16} />
          </button>
        ) : null}
      </output>
    </div>
  )
}
