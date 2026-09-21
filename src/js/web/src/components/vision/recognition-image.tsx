import { useEffect, useState } from "react"
import { useAuthStore } from "@/lib/auth"

export function RecognitionImage({ path, live = false, className = "" }: { path?: string; live?: boolean; className?: string }) {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  const [url, setUrl] = useState("")
  const [error, setError] = useState("")
  useEffect(() => {
    setUrl("")
    setError("")
    if (!path || !teamId) return
    const abort = new AbortController()
    let current = ""
    let timer: ReturnType<typeof setTimeout> | undefined
    const load = async () => {
      try {
        const response = await fetch(path, { signal: abort.signal, credentials: "include", headers: { "X-Team-Id": teamId } })
        if (!response.ok) throw new Error(response.status === 404 ? "等待识别画面" : "画面读取失败")
        const next = URL.createObjectURL(await response.blob())
        if (abort.signal.aborted) {
          URL.revokeObjectURL(next)
          return
        }
        const previous = current
        current = next
        setUrl(next)
        setError("")
        if (previous) URL.revokeObjectURL(previous)
      } catch (failure) {
        if (!abort.signal.aborted) setError(failure instanceof Error ? failure.message : "画面读取失败")
      } finally {
        if (live && !abort.signal.aborted) timer = setTimeout(load, 1000)
      }
    }
    void load()
    return () => {
      abort.abort()
      if (timer) clearTimeout(timer)
      if (current) URL.revokeObjectURL(current)
    }
  }, [path, live, teamId])
  return (
    <div className={`relative flex min-h-0 items-center justify-center overflow-hidden bg-black/70 ${className}`}>
      {url ? <img src={url} alt="摄像头识别画面" className="h-full w-full object-contain" /> : <span className="text-sm text-slate-400">{error || "等待识别画面"}</span>}
      {url && error ? <output className="absolute bottom-2 bg-black/80 px-3 py-1 text-amber-200">{error}</output> : null}
    </div>
  )
}
