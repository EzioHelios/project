import { Link } from "@tanstack/react-router"
import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-react"
import { useState } from "react"
import { BigscreenBarChart, BigscreenLineChart, BigscreenSankeyChart } from "@/components/bigscreen/charts"
import { TerminalStatusTriplet } from "@/components/bigscreen/custom/TerminalStatusTriplet"
import { BigscreenDataState } from "@/components/bigscreen/data-state"
import { BigscreenPanel } from "@/components/bigscreen/panel"
import { WarehouseProfile } from "@/components/bigscreen/warehouse-profile"
import { DeviceBoard, DeviceReadings, EnergyCalendar, WarehouseLedger } from "@/components/bigscreen/warehouse-subjects"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { useAuthStore } from "@/lib/auth"
import { useBigscreenCarbon, useBigscreenEvents, useBigscreenOverview } from "@/lib/bigscreen/hooks"
import type { BigscreenEventCategory, BigscreenEventFilters, BigscreenEventSummary, BigscreenInfoItem, BigscreenMetric, BigscreenPeriod } from "@/lib/bigscreen/types"

export function ScreenFacts({ items, emptyLabel = "尚未录入仓库档案" }: { items: BigscreenInfoItem[]; emptyLabel?: string }) {
  return items.length ? (
    <dl className="warehouse-facts">
      {items.map((item) => (
        <div key={`${item.label}:${item.value}`}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  ) : (
    <div className="warehouse-empty">{emptyLabel}</div>
  )
}

export function ScreenMetrics({ items }: { items: BigscreenMetric[] }) {
  return (
    <div className="warehouse-metrics">
      {items.map((item) => (
        <div key={item.id}>
          <span>{item.label}</span>
          <strong>
            {item.value == null ? "—" : item.value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}
            <small>{item.unit}</small>
          </strong>
          {item.emphasis && <small>{item.emphasis}</small>}
        </div>
      ))}
    </div>
  )
}

export function EventList({ events, category }: { events: BigscreenEventSummary; category?: BigscreenEventCategory }) {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return <EventListContent key={teamId} events={events} category={category} />
}

function EventListContent({ events, category }: { events: BigscreenEventSummary; category?: BigscreenEventCategory }) {
  const [detail, setDetail] = useState<BigscreenEventSummary["recent"][number] | null>(null)
  const [history, setHistory] = useState(false)
  return (
    <div className="warehouse-event-content">
      <div className="warehouse-data-period">{events.start ? `${events.start.slice(0, 10)} 至 ${events.end?.slice(0, 10)}` : "暂无事件记录"}</div>
      {category && (
        <button type="button" className="warehouse-history-link" onClick={() => setHistory(true)}>
          全部记录 · {events.total.toLocaleString("zh-CN")} 条
        </button>
      )}
      <div className="warehouse-events">
        {events.recent.map((event) => (
          <button type="button" key={event.id} onClick={() => setDetail(event)}>
            <span className="warehouse-event-type">{event.type}</span>
            <span className="warehouse-event-title">{event.title}</span>
            <time>{event.time?.slice(0, 16).replace("T", " ")}</time>
            <span data-pending={event.status === "未处理"}>{event.status}</span>
          </button>
        ))}
      </div>
      {category && history && (
        <Dialog open onOpenChange={setHistory}>
          <DialogContent aria-describedby={undefined} className="warehouse-event-dialog warehouse-history-dialog">
            <DialogTitle>历史预警查询</DialogTitle>
            <EventHistory category={category} regions={events.region_distribution.map((item) => item.name)} />
          </DialogContent>
        </Dialog>
      )}
      {detail && (
        <Dialog open={Boolean(detail)} onOpenChange={(open) => !open && setDetail(null)}>
          <DialogContent aria-describedby={undefined} className="warehouse-event-dialog">
            <DialogTitle>预警详情</DialogTitle>
            <ScreenFacts
              items={[
                { label: "类型", value: detail.type },
                { label: "区域", value: detail.area },
                { label: "设备", value: detail.device },
                ...(detail.level ? [{ label: "等级", value: detail.level }] : []),
                { label: "事件", value: detail.title },
                { label: "发生时间", value: detail.time?.replace("T", " ") ?? "未记录" },
                { label: "处理状态", value: detail.status },
                ...(detail.handle_note ? [{ label: "处理记录", value: detail.handle_note }] : []),
              ]}
            />
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

function EventHistory({ category, regions }: { category: BigscreenEventCategory; regions: string[] }) {
  const [filters, setFilters] = useState<BigscreenEventFilters>({ category, page: 1 })
  const query = useBigscreenEvents(filters)
  const data = query.data?.data
  const change = (value: Partial<BigscreenEventFilters>) => setFilters({ ...filters, ...value, page: 1 })
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  return (
    <div data-history-ready={!query.isFetching && !query.isError}>
      <div className="warehouse-history-filters">
        <label>
          开始日期
          <input aria-label="预警开始日期" type="date" value={filters.start ?? ""} onChange={(event) => change({ start: event.target.value })} />
        </label>
        <label>
          结束日期
          <input aria-label="预警结束日期" type="date" value={filters.end ?? ""} onChange={(event) => change({ end: event.target.value })} />
        </label>
        <label>
          处理状态
          <select aria-label="预警处理状态" value={filters.status ?? ""} onChange={(event) => change({ status: event.target.value })}>
            <option value="">全部状态</option>
            <option value="pending">未处理</option>
            <option value="handled">已处理</option>
            <option value="unknown">未记录</option>
          </select>
        </label>
        <label>
          {category === "video" ? "功能区" : "区域"}
          <select aria-label="预警区域" value={filters.area ?? ""} onChange={(event) => change({ area: event.target.value })}>
            <option value="">全部区域</option>
            {regions.map((region) => (
              <option key={region}>{region}</option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => setFilters({ category, page: 1 })}>
          重置
        </button>
      </div>
      {query.isError ? (
        <div role="alert">
          预警查询失败，请检查日期范围。
          <button type="button" onClick={() => void query.refetch()}>
            重试
          </button>
        </div>
      ) : query.isFetching ? (
        <output className="warehouse-empty">正在查询</output>
      ) : (
        data && (
          <>
            <EventDistribution events={data} video={category === "video"} height={160} />
            {data.recent.length ? <EventList events={data} /> : <div className="warehouse-empty">当前筛选条件下暂无预警记录</div>}
            <div className="warehouse-history-pagination">
              <span>
                共 {data.total.toLocaleString("zh-CN")} 条 · 第 {data.page} / {pages} 页
              </span>
              <button type="button" title="上一页" aria-label="上一页" disabled={data.page <= 1} onClick={() => setFilters({ ...filters, page: data.page - 1 })}>
                <ChevronLeft size={18} />
              </button>
              <button type="button" title="下一页" aria-label="下一页" disabled={data.page >= pages} onClick={() => setFilters({ ...filters, page: data.page + 1 })}>
                <ChevronRight size={18} />
              </button>
            </div>
          </>
        )
      )}
    </div>
  )
}

export function EventDistribution({
  events,
  video = false,
  height = 172,
  initialDimension = "type",
}: {
  events: BigscreenEventSummary
  video?: boolean
  height?: number
  initialDimension?: "type" | "region" | "status"
}) {
  const [dimension, setDimension] = useState<"type" | "region" | "status">(initialDimension)
  const items = dimension === "region" ? events.region_distribution : dimension === "status" ? events.status_distribution : events.distribution
  const ranked = [...items].sort((left, right) => right.value - left.value)
  const visible = ranked.length > 6 ? [...ranked.slice(0, 5), { name: "其他", value: ranked.slice(5).reduce((sum, item) => sum + item.value, 0) }] : ranked
  return (
    <>
      <fieldset className="warehouse-chart-controls" aria-label={video ? "安全预警统计维度" : "预警统计维度"}>
        {(
          [
            ["type", "类型"],
            ["region", video ? "功能区" : "区域"],
            ["status", "处理状态"],
          ] as const
        ).map(([key, label]) => (
          <button key={key} type="button" aria-pressed={dimension === key} onClick={() => setDimension(key)}>
            {label}
          </button>
        ))}
        <span>{events.total.toLocaleString("zh-CN")} 条</span>
      </fieldset>
      <BigscreenBarChart items={visible} unit="条" height={height} />
    </>
  )
}

export function WarehouseOperations({ mode }: { mode: "overview" | "power" | "monitor" }) {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return <OperationsContent key={`${teamId}-${mode}`} mode={mode} />
}

function OperationsContent({ mode }: { mode: "overview" | "power" | "monitor" }) {
  const [period, setPeriod] = useState<BigscreenPeriod>({})
  const [zone, setZone] = useState("")
  const [search, setSearch] = useState("")
  const [meterId, setMeterId] = useState<string | null>(null)
  const query = useBigscreenOverview(period)
  const carbon = useBigscreenCarbon(mode === "overview")
  const data = query.data?.data
  if (!data) return <BigscreenDataState failed={query.isError} retry={() => void query.refetch()} />
  const meters = data.devices.filter((item) => item.category === 0)
  const recentMeters = meters.filter((item) => item.last_reading && Date.now() - Date.parse(item.last_reading) >= 0 && Date.now() - Date.parse(item.last_reading) < 86400000)
  const selectedMeter = data.devices.find((item) => item.id === meterId)
  const selectedEnergy = data.equipment_ranking.find((item) => item.id === meterId)
  const periodLabel = `${data.period_start} 至 ${data.period_end}`
  const trend = data.trend.map((point) => ({
    ...point,
    period: point.period.slice(0, period.grain === "hour" ? 16 : period.grain === "month" ? 7 : 10).replace("T", " "),
    energy_kwh: point.value,
    carbon_co2e: null,
  }))
  const deviceGroups = [...new Set(data.devices.map((item) => item.area_id))]
    .map((id) => ({
      id,
      name: data.devices.find((item) => item.area_id === id)?.area ?? "未关联区域",
      value: data.devices.filter((item) => item.area_id === id).length,
    }))
    .sort((a, b) => b.value - a.value)
  const shownDevices = data.devices.filter((item) => (!zone || (item.area_id ?? "unallocated") === zone) && item.name.includes(search))
  const hasBusiness = data.presentation.overview_focus === "business"
  const safetyFocus = data.presentation.monitor_focus === "safety"
  const monitoring = mode === "monitor"
  const refresh = () => {
    void query.refetch()
    if (mode === "overview") void carbon.refetch()
  }
  return (
    <div className="warehouse-screen" data-screen-ready={!query.isFetching && !query.isError && (mode !== "overview" || (!carbon.isFetching && !carbon.isError))}>
      <div className="warehouse-toolbar">
        {!monitoring && (
          <>
            <label>
              开始
              <input aria-label="开始日期" type="date" value={period.start ?? data.period_start} onChange={(event) => setPeriod({ ...period, start: event.target.value })} />
            </label>
            <label>
              结束
              <input aria-label="结束日期" type="date" value={period.end ?? data.period_end} onChange={(event) => setPeriod({ ...period, end: event.target.value })} />
            </label>
            <select aria-label="趋势粒度" value={period.grain ?? "day"} onChange={(event) => setPeriod({ ...period, grain: event.target.value })}>
              <option value="hour">按小时</option>
              <option value="day">按日</option>
              <option value="month">按月</option>
            </select>
            <select aria-label="统计区域" value={period.area ?? ""} onChange={(event) => setPeriod({ ...period, area: event.target.value })}>
              <option value="">全部区域</option>
              {data.areas.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
            <span className="warehouse-data-period">电量更新 {data.observed_at ? new Date(data.observed_at).toLocaleString("zh-CN", { hour12: false }) : "暂无"}</span>
          </>
        )}
        {monitoring && (
          <>
            <input aria-label="搜索设备" placeholder="搜索设备" value={search} onChange={(event) => setSearch(event.target.value)} />
            <select aria-label="设备所属区域" value={zone} onChange={(event) => setZone(event.target.value)}>
              <option value="">全部区域</option>
              {deviceGroups.map((item) => (
                <option key={item.id ?? "unallocated"} value={item.id ?? "unallocated"}>
                  {item.name}
                </option>
              ))}
            </select>
            <span className="warehouse-data-period">{shownDevices.length} 台设备</span>
          </>
        )}
        <button type="button" title="刷新数据" aria-label="刷新数据" onClick={refresh}>
          <RefreshCw size={17} />
        </button>
        <Link to="/bigscreen/model">模型全屏</Link>
        {monitoring && <Link to="/bigscreen/vision">视频与作业观测</Link>}
      </div>
      {(query.isError || (mode === "overview" && carbon.isError)) && (
        <div role="alert" className="warehouse-query-error">
          数据更新失败{" "}
          <button type="button" onClick={refresh}>
            重试
          </button>
        </div>
      )}
      <div className={`bigscreen-page warehouse-page warehouse-page-${mode}`}>
        <aside className="warehouse-rail">
          <BigscreenPanel title={mode === "overview" ? "仓库概况" : monitoring ? "设备采集概况" : "期间用电概览"} frame="tall">
            {mode === "overview" ? (
              <WarehouseProfile
                facts={[
                  ...data.company_facts,
                  { label: "登记设备", value: `${data.devices.length} 台` },
                  { label: "挂载区域", value: `${deviceGroups.filter((group) => group.id != null).length} 个` },
                ]}
              />
            ) : monitoring ? (
              <ScreenMetrics
                items={[
                  { id: "all", label: "登记设备", value: data.devices.length, unit: "台" },
                  { id: "meter", label: "计量电表", value: meters.length, unit: "台" },
                  { id: "sample", label: "近24h采样电表", value: recentMeters.length, unit: "台" },
                ]}
              />
            ) : (
              <>
                <ScreenMetrics items={data.energy_kpis} />
                <div className="warehouse-data-period">{periodLabel}</div>
              </>
            )}
          </BigscreenPanel>
          <BigscreenPanel title={monitoring ? "区域设备分布" : "区域用电排行 Top 7"} frame="tall">
            <BigscreenBarChart
              items={monitoring ? deviceGroups.slice(0, 7) : data.area_ranking.slice(0, 7)}
              unit={monitoring ? "台" : "kWh"}
              height="100%"
              onSelect={(item) => {
                if (monitoring) setZone(item.id ?? "unallocated")
                else if (item.id) setPeriod({ ...period, area: item.id })
              }}
            />
          </BigscreenPanel>
          <BigscreenPanel title={monitoring ? (safetyFocus ? "历史安全预警" : "设备类型构成") : mode === "power" ? "电表用电排行 Top 6" : "期间用电概览"} frame="tall">
            {monitoring ? (
              safetyFocus ? (
                <EventDistribution events={data.safety} video height={195} />
              ) : (
                <BigscreenBarChart
                  items={[
                    { name: "计量电表", value: meters.length },
                    { name: "发电设备", value: data.devices.filter((x) => x.category === 1).length },
                    { name: "其他设备档案", value: data.devices.filter((x) => x.category !== 0 && x.category !== 1).length },
                  ]}
                  unit="台"
                  height="100%"
                />
              )
            ) : mode === "power" ? (
              <BigscreenBarChart items={data.equipment_ranking.slice(0, 6)} unit="kWh" height="100%" onSelect={(item) => item.id && setMeterId(item.id)} />
            ) : (
              <>
                <ScreenMetrics items={data.energy_kpis} />
                <div className="warehouse-data-period">{periodLabel}</div>
              </>
            )}
          </BigscreenPanel>
        </aside>
        <div className={`warehouse-center ${mode === "power" ? "warehouse-energy-center" : ""}`}>
          {mode === "power" ? (
            <>
              <EnergyCalendar items={data.energy_calendar} />
              <BigscreenPanel title="电量归集流图 · kWh" frame="wide">
                <BigscreenSankeyChart flow={data.energy_flow} height="100%" />
              </BigscreenPanel>
            </>
          ) : monitoring ? (
            <BigscreenPanel title="区域设备监测" frame="wide">
              <DeviceBoard devices={shownDevices} onSelect={setMeterId} />
            </BigscreenPanel>
          ) : (
            <div className="warehouse-scene-window">
              <EnergyCalendar items={data.energy_calendar} />
            </div>
          )}
          <div className="warehouse-bottom">
            <BigscreenPanel title={monitoring ? (safetyFocus ? "安全预警功能区分布" : "电表采样覆盖") : "用电变化趋势"} frame="wide">
              {monitoring ? (
                safetyFocus ? (
                  <BigscreenBarChart items={data.safety.region_distribution.slice(0, 6)} unit="条" height="100%" />
                ) : (
                  <BigscreenBarChart
                    items={[
                      { name: "已采样", value: meters.filter((item) => item.last_reading).length },
                      { name: "未采样", value: meters.filter((item) => !item.last_reading).length },
                    ]}
                    unit="台"
                    height="100%"
                  />
                )
              ) : (
                <BigscreenLineChart points={trend} height="100%" mode="single" />
              )}
            </BigscreenPanel>
            <BigscreenPanel title={mode === "overview" ? "组织碳核算" : monitoring ? "设备台账状态" : "采集概况"} frame="wide">
              {mode === "overview" ? (
                carbon.isError ? (
                  <div role="alert">核算数据获取失败</div>
                ) : carbon.data?.data ? (
                  <>
                    <ScreenMetrics items={carbon.data.data.hero_metrics} />
                    <div className="warehouse-data-period">{carbon.data.data.period_facts[0]?.value}</div>
                    <Link className="warehouse-history-link" to="/bigscreen/carbon">
                      查看碳排管理
                    </Link>
                  </>
                ) : (
                  <output>加载核算数据</output>
                )
              ) : monitoring ? (
                <BigscreenBarChart
                  items={[
                    { name: "正常", value: data.devices.filter((x) => x.status === 0).length },
                    { name: "故障", value: data.devices.filter((x) => x.status === 1).length },
                    { name: "未登记", value: data.devices.filter((x) => x.status == null).length },
                  ]}
                  unit="台"
                  height={200}
                />
              ) : (
                <TerminalStatusTriplet
                  variant="dense"
                  items={[
                    { id: "total", label: "计量电表", value: meters.length, kind: "total" },
                    { id: "sample", label: "近24h采样", value: recentMeters.length, kind: "online" },
                    { id: "fault", label: "台账故障", value: meters.filter((x) => x.status === 1).length, kind: "fault" },
                  ]}
                />
              )}
            </BigscreenPanel>
          </div>
        </div>
        <aside className="warehouse-rail">
          <BigscreenPanel title={mode === "overview" ? "监测终端概况" : "最新计量读数"} frame="tall">
            {mode === "overview" ? (
              <TerminalStatusTriplet
                variant="dense"
                items={[
                  { id: "total", label: "计量电表", value: meters.length, kind: "total" },
                  { id: "sample", label: "近24h采样", value: recentMeters.length, kind: "online" },
                  { id: "fault", label: "台账故障", value: meters.filter((x) => x.status === 1).length, kind: "fault" },
                ]}
              />
            ) : (
              <DeviceReadings devices={meters} onSelect={setMeterId} />
            )}
          </BigscreenPanel>
          <BigscreenPanel title={mode === "overview" && hasBusiness ? "历史出入库金额" : monitoring && safetyFocus ? "最近安全事件" : "区域设备挂载"} frame="tall">
            {mode === "overview" && hasBusiness ? (
              <WarehouseLedger data={data} />
            ) : monitoring && safetyFocus ? (
              <EventList events={data.safety} category="video" />
            ) : (
              <div className="warehouse-area-register">
                {deviceGroups.map((group) => (
                  <div key={group.id ?? "unallocated"}>
                    <span>{group.name}</span>
                    <strong>{group.value} 台</strong>
                  </div>
                ))}
              </div>
            )}
          </BigscreenPanel>
          <BigscreenPanel title={mode === "overview" ? (hasBusiness ? "历史预警记录" : "重点设备采样") : "计量设备清单"} frame="tall">
            {mode === "overview" ? (
              hasBusiness ? (
                <EventList events={data.alarms} category="all" />
              ) : (
                <DeviceReadings devices={meters} onSelect={setMeterId} />
              )
            ) : (
              <div className="warehouse-area-register">
                {meters.map((item) => (
                  <button type="button" key={item.id} onClick={() => setMeterId(item.id)}>
                    <span>{item.name}</span>
                    <strong>
                      {item.register_value == null ? "未采样" : `${item.register_value.toLocaleString("zh-CN", { maximumFractionDigits: 3 })} ${item.register_unit ?? ""}`}
                    </strong>
                  </button>
                ))}
              </div>
            )}
          </BigscreenPanel>
        </aside>
      </div>
      {selectedMeter && (
        <Dialog open={Boolean(selectedMeter)} onOpenChange={(open) => !open && setMeterId(null)}>
          <DialogContent aria-describedby={undefined} className="warehouse-event-dialog">
            <DialogTitle>{selectedMeter.category === 0 ? "电表详情" : "设备详情"}</DialogTitle>
            <ScreenFacts
              items={[
                { label: "设备名称", value: selectedMeter.name },
                { label: "所属区域", value: selectedMeter.area ?? "未关联区域" },
                { label: "统计期间", value: periodLabel },
                { label: "期间电量", value: selectedEnergy ? `${selectedEnergy.value.toLocaleString("zh-CN", { maximumFractionDigits: 3 })} kWh` : "本筛选范围无数据" },
                {
                  label: "最新累计示值",
                  value:
                    selectedMeter.register_value == null
                      ? "未采样"
                      : `${selectedMeter.register_value.toLocaleString("zh-CN", { maximumFractionDigits: 3 })} ${selectedMeter.register_unit ?? ""}`,
                },
                { label: "采样时间", value: selectedMeter.last_reading?.replace("T", " ") ?? "未采样" },
                { label: "台账状态", value: selectedMeter.status === 0 ? "正常" : selectedMeter.status === 1 ? "故障" : "未登记" },
              ]}
            />
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
