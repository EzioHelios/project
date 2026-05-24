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

  const companyGallery = intro?.company_gallery?.length ? intro.company_gallery : buildFallbackMedia("企业图集", "企业形象展示", 3)
  const projectSpots = intro?.project_spotlights?.length ? intro.project_spotlights : buildFallbackMedia("运营项目", "运营项目概览", 3)
  const successCases = intro?.success_cases?.length ? intro.success_cases : buildFallbackMedia("成功案例", "项目成果展示", 3)

  return (
    <div className="bigscreen-page">
      <div className="bigscreen-side-stack">
        <BigscreenPanel title="企业图集" frame="tall">
          <BigscreenAutoCarousel items={companyGallery} emptyLabel="暂无企业图集" />
        </BigscreenPanel>

        <BigscreenPanel title="企业信息摘要" frame="tall">
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
          description={intro?.hero_description ?? "企业形象总览"}
          anchors={sceneAnchors}
          showCore={false}
          showSafezone={false}
          className="bigscreen-scene-ghost"
        />

        <div className="bigscreen-bottom-grid" data-columns="2">
          <BigscreenPanel title="品牌叙事" frame="wide">
            <div className="bigscreen-stack">
              <BigscreenInfoCard label="品牌定位" value={intro?.hero_title ?? "企业品牌展示"} detail={intro?.hero_description ?? "企业品牌展示"} accent="cyan" />
              <div className="bigscreen-split" data-columns="2">
                {facts.slice(6, 8).map((item, index) => (
                  <BigscreenInfoCard key={item.label} label={item.label} value={item.value} accent={index === 0 ? "amber" : "emerald"} />
                ))}
              </div>
            </div>
          </BigscreenPanel>

          <BigscreenPanel title="运营视角" frame="wide">
            <div className="bigscreen-stack">
              {projectSpots.slice(0, 3).map((item, index) => (
                <BigscreenInfoCard
                  key={item.id}
                  label={`Focus ${index + 1}`}
                  value={item.title}
                  detail={item.description ?? "运营项目概览"}
                  accent={index === 0 ? "cyan" : index === 1 ? "emerald" : "amber"}
                />
              ))}
            </div>
          </BigscreenPanel>
        </div>
      </div>

      <div className="bigscreen-side-stack">
        <BigscreenPanel title="运营项目轮播" frame="tall">
          <BigscreenAutoCarousel items={projectSpots} emptyLabel="暂无运营项目" />
        </BigscreenPanel>

        <BigscreenPanel title="成功案例轮播" frame="tall">
          <BigscreenAutoCarousel items={successCases} emptyLabel="暂无成功案例" />
        </BigscreenPanel>
      </div>
    </div>
  )
}
