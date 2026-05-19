import { createFileRoute } from "@tanstack/react-router"

import { BigscreenEmpty, BigscreenPanel } from "@/components/bigscreen/panel"
import { useBigscreenIntro } from "@/lib/bigscreen/hooks"

export const Route = createFileRoute("/_app/bigscreen/intro")({
  component: BigscreenIntroPage,
})

function BigscreenIntroPage() {
  const introQuery = useBigscreenIntro()
  const intro = introQuery.data?.data

  return (
    <div className="bigscreen-grid-24">
      <BigscreenPanel title="企业介绍" eyebrow="Intro" className="min-h-0" bodyClassName="h-[calc(100%-72px)] min-h-0" style={{ gridArea: "1 / 1 / 13 / 9" }}>
        {intro?.company_gallery?.length ? (
          <div className="grid h-full grid-cols-2 gap-3">
            {intro.company_gallery.map((item) => (
              <div key={item.id} className="overflow-hidden rounded-[18px] border border-white/8 bg-white/[0.03]">
                {item.image_url ? (
                  <img src={item.image_url} alt={item.title} className="h-[180px] w-full object-cover" />
                ) : (
                  <div className="flex h-[180px] items-center justify-center bg-white/[0.04] text-sm text-white/40">暂无图片</div>
                )}
                <div className="p-3">
                  <div className="text-sm font-medium text-white">{item.title}</div>
                  <div className="mt-1 text-xs leading-5 text-white/55">{item.description || "现场内容待补充"}</div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <BigscreenEmpty label="企业图集待补充" />
        )}
      </BigscreenPanel>

      <BigscreenPanel title="品牌叙事" eyebrow="Narrative" className="min-h-0" bodyClassName="h-[calc(100%-72px)] min-h-0" style={{ gridArea: "1 / 9 / 25 / 17" }}>
        <div className="flex h-full flex-col gap-4">
          <div className="rounded-[20px] border border-cyan-300/10 bg-cyan-300/6 p-5">
            <div className="bigscreen-title text-[28px] text-cyan-50">{intro?.hero_title ?? "企业介绍"}</div>
            <div className="mt-4 text-[15px] leading-7 text-white/72">{intro?.hero_description ?? "当前还没有介绍内容，首版大屏保留结构与内容承载位。"}</div>
          </div>
          <div className="grid flex-1 gap-3">
            {(intro?.project_spotlights?.length
              ? intro.project_spotlights
              : Array.from({ length: 3 }).map((_, index) => ({ id: String(index), title: "项目卡片", description: "待补充", image_url: null }))
            ).map((item) => (
              <div key={item.id} className="flex items-center gap-4 rounded-[18px] border border-white/8 bg-white/[0.03] p-4">
                {item.image_url ? (
                  <img src={item.image_url} alt={item.title} className="h-24 w-32 rounded-[14px] object-cover" />
                ) : (
                  <div className="flex h-24 w-32 items-center justify-center rounded-[14px] bg-white/[0.04] text-xs text-white/35">暂无图片</div>
                )}
                <div className="min-w-0">
                  <div className="text-[15px] font-semibold text-white">{item.title}</div>
                  <div className="mt-2 text-sm leading-6 text-white/58">{item.description || "首版保留运营项目展示位，后续可切换为客户定制内容。"}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </BigscreenPanel>

      <BigscreenPanel title="宣传视频" eyebrow="Media" className="min-h-0" bodyClassName="h-[calc(100%-72px)] min-h-0" style={{ gridArea: "1 / 17 / 11 / 25" }}>
        {intro?.promo_video_url ? (
          <video className="h-full w-full rounded-[18px] object-cover" src={intro.promo_video_url} autoPlay muted loop controls />
        ) : (
          <BigscreenEmpty label="当前未配置宣传视频，后续可直接替换为客户素材。" />
        )}
      </BigscreenPanel>

      <BigscreenPanel title="企业信息摘要" eyebrow="Facts" className="min-h-0" bodyClassName="h-[calc(100%-72px)] min-h-0" style={{ gridArea: "11 / 17 / 19 / 25" }}>
        {intro?.company_facts?.length ? (
          <div className="grid gap-2">
            {intro.company_facts.map((item) => (
              <div key={item.label} className="flex items-center justify-between gap-3 rounded-[14px] border border-white/8 bg-white/[0.03] px-4 py-3">
                <span className="text-sm text-white/58">{item.label}</span>
                <span className="text-sm font-medium text-amber-200">{item.value}</span>
              </div>
            ))}
          </div>
        ) : (
          <BigscreenEmpty label="企业摘要待补充" />
        )}
      </BigscreenPanel>

      <BigscreenPanel title="成功案例" eyebrow="Cases" className="min-h-0" bodyClassName="h-[calc(100%-72px)] min-h-0" style={{ gridArea: "19 / 17 / 25 / 25" }}>
        {intro?.success_cases?.length ? (
          <div className="grid h-full grid-cols-2 gap-3">
            {intro.success_cases.map((item) => (
              <div key={item.id} className="rounded-[16px] border border-white/8 bg-white/[0.03] p-3">
                <div className="text-sm font-semibold text-white">{item.title}</div>
                <div className="mt-2 text-xs leading-5 text-white/55">{item.description || "案例描述待补充"}</div>
              </div>
            ))}
          </div>
        ) : (
          <BigscreenEmpty label="成功案例待补充" />
        )}
      </BigscreenPanel>
    </div>
  )
}
