import { createFileRoute } from "@tanstack/react-router"

import { BigscreenAutoCarousel } from "@/components/bigscreen/motion"
import { BigscreenInfoCard, BigscreenPanel } from "@/components/bigscreen/panel"
import { type BigscreenSceneAnchor, BigscreenSceneHost } from "@/components/bigscreen/scene"
import { useBigscreenIntro } from "@/lib/bigscreen/hooks"
import type { BigscreenMediaItem } from "@/lib/bigscreen/types"

export const Route = createFileRoute("/_app/bigscreen/intro")({
  component: BigscreenIntroPage,
})

function buildFallbackMedia(title: string, description: string, count: number) {
  return Array.from({ length: count }).map<BigscreenMediaItem>((_, index) => ({
    id: `${title}-${index}`,
    title,
    description,
    image_url: null,
  }))
}

function BigscreenIntroPage() {
  const introQuery = useBigscreenIntro()
  const intro = introQuery.data?.data

  const facts = intro?.company_facts ?? []
  const sceneAnchors: BigscreenSceneAnchor[] = [
    {
      id: "company",
      label: "Company",
      value: intro?.hero_title ?? "企业介绍",
      position: "ct",
    },
    {
      id: "staff",
      label: facts[4]?.label ?? "员工规模",
      value: facts[4]?.value ?? "0",
      position: "lt",
    },
    {
      id: "storage",
      label: facts[5]?.label ?? "仓储面积",
      value: facts[5]?.value ?? "未配置",
      position: "lb",
    },
    {
      id: "park",
      label: facts[6]?.label ?? "园区面积",
      value: facts[6]?.value ?? "未配置",
      position: "rt",
    },
    {
      id: "industry",
      label: facts[2]?.label ?? "行业方向",
      value: facts[2]?.value ?? "未配置",
      position: "rb",
    },
  ]

  const companyGallery = intro?.company_gallery?.length ? intro.company_gallery : buildFallbackMedia("企业图集", "等待客户正式素材", 3)
  const projectSpots = intro?.project_spotlights?.length ? intro.project_spotlights : buildFallbackMedia("运营项目", "当前保留轮播展示位", 3)
  const successCases = intro?.success_cases?.length ? intro.success_cases : buildFallbackMedia("成功案例", "当前保留案例轮播位", 3)

  return (
    <div className="bigscreen-page">
      <div className="bigscreen-side-stack">
        <BigscreenPanel title="企业图集" eyebrow="Company Gallery">
          <BigscreenAutoCarousel items={companyGallery} emptyLabel="企业图集待补充" />
        </BigscreenPanel>

        <BigscreenPanel title="企业信息摘要" eyebrow="Company Facts">
          <div className="bigscreen-stack">
            {facts.slice(0, 6).map((item, index) => (
              <BigscreenInfoCard key={item.label} label={item.label} value={item.value} accent={index % 3 === 0 ? "cyan" : index % 3 === 1 ? "emerald" : "amber"} />
            ))}
          </div>
        </BigscreenPanel>
      </div>

      <div className="bigscreen-main-stack">
        <BigscreenSceneHost
          eyebrow="Brand Core"
          title={intro?.hero_title ?? "企业介绍主视觉区"}
          description={intro?.hero_description ?? "当前还没有正式品牌叙事内容，主视觉区先保留给视频、园区形象或 3D 企业场景。"}
          status="Brand Visual Safe Zone"
          anchors={sceneAnchors}
          overlay={
            <div className="flex h-full items-center justify-center">
              <div className="h-[56%] w-[58%] overflow-hidden rounded-[26px] border border-white/10 bg-[#020c15] shadow-[0_28px_64px_rgba(0,0,0,0.28)]">
                {intro?.promo_video_url ? (
                  <video className="h-full w-full object-cover" src={intro.promo_video_url} autoPlay muted loop controls />
                ) : (
                  <div className="flex h-full flex-col items-center justify-center bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.16),transparent_34%),linear-gradient(180deg,#061321,#020811)] px-10 text-center">
                    <div className="bigscreen-title text-[42px] text-cyan-50">Brand Main Visual</div>
                    <div className="mt-4 max-w-[520px] text-sm leading-7 text-white/58">
                      当前主视觉区预留给品牌视频、3D 园区形象或中央企业主对象。正式素材到位后，外围 HUD 结构无需变更。
                    </div>
                  </div>
                )}
              </div>
            </div>
          }
        />

        <div className="bigscreen-bottom-grid" data-columns="2">
          <BigscreenPanel title="品牌叙事" eyebrow="Narrative">
            <div className="bigscreen-stack">
              <BigscreenInfoCard
                label="品牌定位"
                value={intro?.hero_title ?? "企业品牌展示"}
                detail={intro?.hero_description ?? "当前品牌叙事内容待补充，先保留展示位与大屏节奏。"}
                accent="cyan"
              />
              <div className="bigscreen-split" data-columns="2">
                {facts.slice(6, 8).map((item, index) => (
                  <BigscreenInfoCard key={item.label} label={item.label} value={item.value} accent={index === 0 ? "amber" : "emerald"} />
                ))}
              </div>
            </div>
          </BigscreenPanel>

          <BigscreenPanel title="运营视角" eyebrow="Program Focus">
            <div className="bigscreen-stack">
              {projectSpots.slice(0, 3).map((item, index) => (
                <BigscreenInfoCard
                  key={item.id}
                  label={`Focus ${index + 1}`}
                  value={item.title}
                  detail={item.description ?? "当前保留运营项目说明位。"}
                  accent={index === 0 ? "cyan" : index === 1 ? "emerald" : "amber"}
                />
              ))}
            </div>
          </BigscreenPanel>
        </div>
      </div>

      <div className="bigscreen-side-stack">
        <BigscreenPanel title="运营项目轮播" eyebrow="Project Showcase">
          <BigscreenAutoCarousel items={projectSpots} emptyLabel="暂无运营项目素材" />
        </BigscreenPanel>

        <BigscreenPanel title="成功案例轮播" eyebrow="Success Cases">
          <BigscreenAutoCarousel items={successCases} emptyLabel="暂无成功案例素材" />
        </BigscreenPanel>
      </div>
    </div>
  )
}
