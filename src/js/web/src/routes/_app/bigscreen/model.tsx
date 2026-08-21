import { createFileRoute } from "@tanstack/react-router"

import { useAuthStore } from "@/lib/auth"

export const Route = createFileRoute("/_app/bigscreen/model")({
  component: BigscreenModelPage,
})

function BigscreenModelPage() {
  const currentTeam = useAuthStore((state) => state.currentTeam)
  return (
    <div className="bigscreen-model-page">
      <div className="bigscreen-model-status">
        <span>{currentTeam?.name ?? "当前园区"}</span>
        <strong>园区场景 · 实时状态</strong>
      </div>
      <section className="bigscreen-model-legend" aria-label="园区模型图例">
        <span data-tone="site">底盘道路绿化</span>
        <span data-tone="building">建筑体块</span>
        <span data-tone="solar">光伏屋顶</span>
        <span data-tone="zone">功能分区</span>
      </section>
    </div>
  )
}
