import { createFileRoute, Link } from "@tanstack/react-router"
import { BigscreenBarChart, BigscreenSankeyChart } from "@/components/bigscreen/charts"
import { BigscreenDataState } from "@/components/bigscreen/data-state"
import { EventList, ScreenFacts, ScreenMetrics } from "@/components/bigscreen/operations"
import { BigscreenPanel } from "@/components/bigscreen/panel"
import { CommuteEnergy } from "@/components/bigscreen/warehouse-subjects"
import { useBigscreenCarbon, useBigscreenOverview } from "@/lib/bigscreen/hooks"
import type { BigscreenDistributionItem } from "@/lib/bigscreen/types"

export const Route = createFileRoute("/_app/bigscreen/carbon")({ component: CarbonPage })
function topItems(items: BigscreenDistributionItem[], count = 5) {
  const sorted = [...items].sort((a, b) => b.value - a.value)
  return sorted.length > count ? [...sorted.slice(0, count), { name: "其他", value: sorted.slice(count).reduce((sum, item) => sum + item.value, 0) }] : sorted
}
function CarbonPage() {
  const query = useBigscreenCarbon()
  const operations = useBigscreenOverview()
  const data = query.data?.data
  if (!data || !operations.data?.data)
    return (
      <BigscreenDataState
        failed={query.isError || operations.isError}
        retry={() => {
          void query.refetch()
          void operations.refetch()
        }}
      />
    )
  const context = operations.data.data
  const commute = context.presentation.carbon_focus === "commute"
  return (
    <div className="warehouse-screen" data-screen-ready={!query.isFetching && !operations.isFetching && !query.isError && !operations.isError}>
      <div className="warehouse-toolbar">
        <span>组织碳核算</span>
        <span className="warehouse-data-period">{data.period_facts[0]?.value}</span>
        <Link to="/carbon/organization/reports">盘查报告</Link>
        <Link to="/bigscreen/model">模型全屏</Link>
      </div>
      {(query.isError || operations.isError) && (
        <div role="alert" className="warehouse-query-error">
          数据更新失败{" "}
          <button
            type="button"
            onClick={() => {
              void query.refetch()
              void operations.refetch()
            }}
          >
            重试
          </button>
        </div>
      )}
      <div className="bigscreen-page warehouse-page warehouse-carbon-page">
        <aside className="warehouse-carbon-rail">
          <BigscreenPanel title="核算结果" frame="tall">
            <ScreenMetrics items={data.hero_metrics} />
          </BigscreenPanel>
          <BigscreenPanel title="核算活动构成" frame="tall">
            <BigscreenBarChart items={topItems(data.activity_distribution)} unit="条活动" height="100%" />
          </BigscreenPanel>
          <BigscreenPanel title="核算档案" frame="tall">
            <ScreenFacts items={data.period_facts} emptyLabel="暂无核算记录" />
          </BigscreenPanel>
        </aside>
        <div className="warehouse-center">
          <BigscreenPanel title="组织边界至区域设备碳流 · kgCO2e" frame="wide">
            <BigscreenSankeyChart flow={data.flow} height="100%" />
          </BigscreenPanel>
          <div className="warehouse-bottom">
            <BigscreenPanel title="主要排放源贡献" frame="wide">
              <BigscreenBarChart items={topItems(data.source_ranking)} unit="kgCO2e" height="100%" />
            </BigscreenPanel>
            <BigscreenPanel title="区域设备排放归集" frame="wide">
              <BigscreenBarChart items={topItems(data.area_ranking)} unit="kgCO2e" height="100%" />
            </BigscreenPanel>
          </div>
        </div>
        <aside className="warehouse-carbon-rail">
          <BigscreenPanel title="核算采用因子" frame="tall">
            <div className="warehouse-factor-list">
              <ScreenFacts items={data.factors} emptyLabel="暂无因子记录" />
            </div>
          </BigscreenPanel>
          <BigscreenPanel title={commute ? "通勤车辆能源构成" : "排放分类构成"} frame="tall">
            {commute ? <CommuteEnergy data={context} /> : <BigscreenBarChart items={data.scope_distribution} unit="kgCO2e" height="100%" />}
          </BigscreenPanel>
          <BigscreenPanel title={commute ? "历史碳排预警" : "排放源清单"} frame="tall">
            {commute ? (
              <EventList events={context.carbon_alarms} category="carbon" />
            ) : (
              <div className="warehouse-area-register">
                {data.source_ranking.map((item) => (
                  <div key={item.name}>
                    <span>{item.name}</span>
                    <strong>
                      {item.value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}
                      <small> kgCO2e</small>
                    </strong>
                  </div>
                ))}
              </div>
            )}
          </BigscreenPanel>
        </aside>
      </div>
    </div>
  )
}
