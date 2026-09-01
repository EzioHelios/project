import {
  AlertTriangle,
  Bell,
  Building2,
  CheckCircle2,
  ChevronRight,
  Clock3,
  FileText,
  IdCard,
  LockKeyhole,
  MessageSquare,
  QrCode,
  RefreshCw,
  Save,
  Send,
  Settings,
  ShieldCheck,
  TrendingUp,
  Upload,
  UserRound,
} from "lucide-react"
import { type ComponentType, type ReactNode, useMemo, useState } from "react"
import type {
  AlertDetail,
  AlertRow,
  AlertSummary,
  AlertTrend,
  EnergyRankingRow,
  EnergySummary,
  EnergyTrend,
  MobileEnergyCarbonData,
  MobileEnergyFilters,
  MobileWorkOrder,
  MonitorArea,
  MonitorDevice,
  MonitorDeviceDetail,
  MonitorDeviceTimeseries,
} from "@/hooks/mobile/use-mobile-energy-carbon"
import { useAuthStore } from "@/lib/auth"
import type { User } from "@/lib/generated/api"

type DeviceGroupKey = "meter" | "power" | "logistics"
type ProfilePanelKey = "overview" | "account" | "notifications" | "security" | "help"

const groupMeta: Record<DeviceGroupKey, { title: string; subtitle: string; image: string; match: RegExp }> = {
  meter: {
    title: "计量采集设备",
    subtitle: "电表、计量柜与主回路采集终端",
    image: "/mobile-assets/device-meter-cabinet.png",
    match: /电表|计量|主表|采集|PCC|网关|终端|仪表/,
  },
  power: {
    title: "能源动力设备",
    subtitle: "制冷、空压、光伏、储能与动力站房",
    image: "/mobile-assets/device-pv-storage.png",
    match: /制冷|冷机|空压|动力|储能|光伏|逆变|变压|天然气/,
  },
  logistics: {
    title: "作业柔性负荷",
    subtitle: "叉车、AGV、充电与厂内物流设备",
    image: "/mobile-assets/device-ev-charger.png",
    match: /充电|叉车|AGV|堆垛|输送|物流|装卸|机器人|作业/,
  },
}

const severityTone: Record<string, string> = {
  high: "bg-[#ffe9e3] text-[#b3432f]",
  critical: "bg-[#ffe9e3] text-[#b3432f]",
  medium: "bg-[#fff4e5] text-[#9a5a16]",
  warning: "bg-[#fff4e5] text-[#9a5a16]",
  low: "bg-[#e9f6ee] text-[#24825a]",
}

export function MobileEnergyPane({
  summary,
  trend,
  ranking,
  alertSummary,
  alertTrend,
  areas,
  tenantName,
  filters,
  onFiltersChange,
  loading,
}: {
  summary?: EnergySummary
  trend?: EnergyTrend
  ranking: EnergyRankingRow[]
  alertSummary?: AlertSummary
  alertTrend?: AlertTrend
  areas: MonitorArea[]
  tenantName: string
  filters: MobileEnergyFilters
  onFiltersChange: (filters: MobileEnergyFilters) => void
  loading: boolean
}) {
  const kwh = summary?.total_kwh ?? 0
  const carbon = kwh * 0.5703
  const intensity = kwh > 0 ? carbon / Math.max(summary?.meter_count ?? 1, 1) : 0
  const energyPoints = trend?.items.slice(-8).map((item) => ({ label: item.period.slice(-5), value: item.total_kwh })) ?? []
  const alertPoints = alertTrend?.series.slice(-6).map((item) => ({ label: item.period.slice(5), value: item.alerts_count })) ?? []

  return (
    <div className="space-y-3">
      <section className="flex items-start justify-between px-0.5">
        <div>
          <h2 className="text-[18px] font-semibold tracking-[0]">{tenantName}能碳移动工作台</h2>
          <p className="mt-1 text-[11px] text-[#8a95a6]">核心能耗、碳排、告警与目标执行情况</p>
        </div>
        <StatusPill
          text={summary?.calc_status === "ready" ? "数据正常" : summary?.calc_status === "empty" ? "暂无数据" : "部分数据"}
          tone={summary?.calc_status === "ready" ? "ok" : "warn"}
        />
      </section>

      <Card>
        <div className="grid grid-cols-2 gap-2">
          <SegmentedButton active={filters.period === "day"} text="日" onClick={() => onFiltersChange({ ...filters, period: "day" })} />
          <SegmentedButton active={filters.period !== "day"} text="月" onClick={() => onFiltersChange({ ...filters, period: "month" })} />
        </div>
        <div className="mt-2 grid grid-cols-[1fr_1fr] gap-2">
          <select
            className="h-9 rounded-[8px] border border-[#dce4e8] bg-white px-2 text-[11px]"
            value={filters.areaId ?? "all"}
            onChange={(event) => onFiltersChange({ ...filters, areaId: event.target.value })}
          >
            <option value="all">全部区域</option>
            {areas.map((area) => (
              <option key={area.id} value={String(area.id)}>
                {area.name}
              </option>
            ))}
          </select>
          <select
            className="h-9 rounded-[8px] border border-[#dce4e8] bg-white px-2 text-[11px]"
            value={filters.groupBy ?? "equipment"}
            onChange={(event) => onFiltersChange({ ...filters, groupBy: event.target.value === "area" ? "area" : "equipment" })}
          >
            <option value="equipment">按设备排行</option>
            <option value="area">按区域排行</option>
          </select>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-2.5">
        <Metric label="综合用电" value={formatNumber(kwh)} unit="kWh" note={`采样 ${summary?.sample_count ?? 0} 条`} />
        <Metric label="折算碳排" value={formatNumber(carbon)} unit="kgCO2e" note="按演示因子折算" />
        <Metric label="监测对象" value={formatNumber(summary?.meter_count ?? 0)} unit="项" note="区域与计量点统计" />
        <Metric label="异常波动" value={formatNumber(alertSummary?.unhandled ?? 0)} unit="项" note="告警中心同步" muted={(alertSummary?.unhandled ?? 0) === 0} />
      </div>

      <Card>
        <div className="flex items-center justify-between">
          <h3 className="text-[14px] font-semibold">用能趋势</h3>
          <span className="text-[11px] text-[#8a95a6]">{filters.granularity ?? "day"}</span>
        </div>
        <MiniAreaChart points={energyPoints} className="mt-2 h-[104px]" emptyText={loading ? "正在加载趋势" : "暂无趋势数据"} />
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <h3 className="text-[14px] font-semibold">能耗排行</h3>
          <TrendingUp className="h-4 w-4 text-[#238c60]" />
        </div>
        <div className="mt-3 space-y-2">
          {ranking.slice(0, 5).map((item, index) => (
            <BarRow key={item.id} rank={index + 1} title={item.name} value={item.total_kwh} max={ranking[0]?.total_kwh ?? 1} unit="kWh" />
          ))}
          {!loading && ranking.length === 0 ? <EmptyLine text="当前条件暂无排行数据" /> : null}
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <h3 className="text-[14px] font-semibold">目标与异常</h3>
          <StatusPill text="跟踪中" tone="ok" />
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <MiniStat label="单位对象碳排" value={`${formatNumber(intensity)} kg`} />
          <MiniStat label="高风险告警" value={`${alertSummary?.high_risk ?? 0} 项`} danger={(alertSummary?.high_risk ?? 0) > 0} />
        </div>
        <MiniAreaChart points={alertPoints} className="mt-2 h-[74px]" emptyText="暂无告警趋势" />
      </Card>
    </div>
  )
}

export function MobileDevicesPane({
  devices,
  areas,
  detail,
  timeseries,
  videos,
  selectedDeviceId,
  onSelectDevice,
  onCloseDetail,
  tenantName,
  loading,
}: {
  devices: MonitorDevice[]
  areas: MonitorArea[]
  detail?: MonitorDeviceDetail
  timeseries?: MonitorDeviceTimeseries
  videos: Record<string, unknown>[]
  selectedDeviceId?: number | null
  onSelectDevice: (deviceId: number) => void
  onCloseDetail: () => void
  tenantName: string
  loading: boolean
}) {
  const [areaFilter, setAreaFilter] = useState("all")
  const [statusFilter, setStatusFilter] = useState("all")
  const groups = useMemo(() => buildDeviceGroups(devices), [devices])
  const filteredDevices = devices.filter((item) => {
    const matchArea = areaFilter === "all" || String(item.sector_id ?? "") === areaFilter
    const matchStatus = statusFilter === "all" || (statusFilter === "abnormal" ? hasDeviceIssue(item) : isDeviceOnline(item))
    return matchArea && matchStatus
  })
  const selected = selectedDeviceId ? devices.find((item) => item.id === selectedDeviceId) : null

  if (selectedDeviceId && selected) {
    return <DeviceDetailPanel device={selected} detail={detail} timeseries={timeseries} videos={videos} onClose={onCloseDetail} loading={loading} />
  }

  return (
    <div className="space-y-3">
      <Card className="p-3.5">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-semibold">设备台账分类</h2>
          <button className="inline-flex items-center gap-1 rounded-full border border-[#dfe7e3] px-2.5 py-1 text-[11px] font-semibold text-[#315246]" type="button">
            <QrCode className="h-3.5 w-3.5" />
            扫码
          </button>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2">
          {groups.map((group) => (
            <div key={group.key} className="min-h-[118px] rounded-[8px] border border-[#edf0f2] bg-[#f8fafb] p-2 text-left">
              <img className="mx-auto h-12 w-full object-contain" src={group.image} alt="" />
              <p className="mt-1.5 text-[10.5px] font-semibold leading-snug text-[#17212f]">{group.title}</p>
              <p className="mt-1 text-[10px] text-[#7e8b9b]">
                {group.online}/{group.total} 在线
              </p>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <h3 className="text-[14px] font-semibold">区域状态</h3>
          <span className="text-[11px] text-[#8a95a6]">{tenantName}</span>
        </div>
        <div className="mt-3 space-y-2">
          {areas.slice(0, 4).map((area) => (
            <IssueRow key={area.id} title={area.name} value={`${area.equipment_online}/${area.equipment_total} 在线`} tone={area.alert_unhandled > 0 ? "warn" : "info"} />
          ))}
          {!loading && areas.length === 0 ? <EmptyLine text="当前租户暂无区域数据" /> : null}
        </div>
      </Card>

      <Card>
        <h3 className="text-[14px] font-semibold">设备列表</h3>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <select className="h-9 rounded-[8px] border border-[#dce4e8] bg-white px-2 text-[11px]" value={areaFilter} onChange={(event) => setAreaFilter(event.target.value)}>
            <option value="all">全部区域</option>
            {areas.map((area) => (
              <option key={area.id} value={String(area.id)}>
                {area.name}
              </option>
            ))}
          </select>
          <select className="h-9 rounded-[8px] border border-[#dce4e8] bg-white px-2 text-[11px]" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">全部状态</option>
            <option value="online">在线正常</option>
            <option value="abnormal">异常跟踪</option>
          </select>
        </div>
        <div className="mt-2 divide-y divide-[#eef1f3]">
          {filteredDevices.slice(0, 20).map((item) => (
            <button key={item.id} className="grid w-full grid-cols-[1fr_auto] items-center gap-3 py-3 text-left" type="button" onClick={() => onSelectDevice(item.id)}>
              <div>
                <p className="text-[12.5px] font-semibold">{item.name}</p>
                <p className="mt-1 text-[11px] text-[#8a95a6]">
                  {item.code ?? item.location ?? item.sector_name ?? "设备台账"} · {item.protocol ?? "实时监控"}
                </p>
              </div>
              <StateBadge status={item.status} alerts={item.alert_unhandled ?? 0} />
            </button>
          ))}
          {!loading && filteredDevices.length === 0 ? <EmptyLine text="当前条件暂无设备" /> : null}
        </div>
      </Card>
    </div>
  )
}

export function MobileAlertsPane({
  summary,
  trend,
  alerts,
  detail,
  selectedAlertId,
  onSelectAlert,
  onCloseDetail,
  onAcknowledge,
  onTransfer,
  loading,
  actionPending,
}: {
  summary?: AlertSummary
  trend?: AlertTrend
  alerts: AlertRow[]
  detail?: AlertDetail
  selectedAlertId?: string | null
  onSelectAlert: (alertId: string) => void
  onCloseDetail: () => void
  onAcknowledge: (alertId: string, note?: string) => Promise<void>
  onTransfer: (alertId: string, note?: string) => Promise<string | null>
  loading: boolean
  actionPending: boolean
}) {
  const [severityFilter, setSeverityFilter] = useState("all")
  const [statusFilter, setStatusFilter] = useState("all")
  if (selectedAlertId) {
    return (
      <AlertDetailPanel
        alert={detail ?? alerts.find((item) => item.id === selectedAlertId)}
        onClose={onCloseDetail}
        onAcknowledge={onAcknowledge}
        onTransfer={onTransfer}
        actionPending={actionPending}
      />
    )
  }
  const points = trend?.series.slice(-6).map((item) => ({ label: item.period.slice(5), value: item.alerts_count })) ?? []
  const filteredAlerts = alerts.filter((alert) => {
    const matchSeverity = severityFilter === "all" || alert.severity === severityFilter
    const matchStatus = statusFilter === "all" || alert.status === statusFilter
    return matchSeverity && matchStatus
  })
  return (
    <div className="space-y-3">
      <Card>
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-semibold">告警中心</h2>
          <StatusPill text={`未处理 ${summary?.unhandled ?? 0}`} tone={(summary?.unhandled ?? 0) > 0 ? "warn" : "ok"} />
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2">
          <MiniStat label="全部告警" value={`${summary?.total ?? alerts.length}`} />
          <MiniStat label="今日新增" value={`${summary?.today_added ?? 0}`} />
          <MiniStat label="高风险" value={`${summary?.high_risk ?? 0}`} danger={(summary?.high_risk ?? 0) > 0} />
        </div>
        <MiniAreaChart points={points} className="mt-2 h-[86px]" emptyText="暂无趋势数据" />
      </Card>

      <Card>
        <h3 className="text-[14px] font-semibold">告警消息</h3>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <select
            className="h-9 rounded-[8px] border border-[#dce4e8] bg-white px-2 text-[11px]"
            value={severityFilter}
            onChange={(event) => setSeverityFilter(event.target.value)}
          >
            <option value="all">全部等级</option>
            <option value="high">高风险</option>
            <option value="medium">中风险</option>
            <option value="low">低风险</option>
          </select>
          <select className="h-9 rounded-[8px] border border-[#dce4e8] bg-white px-2 text-[11px]" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">全部状态</option>
            <option value="待处理">待处理</option>
            <option value="已确认">已确认</option>
            <option value="处理中">处理中</option>
            <option value="已转工单">已转工单</option>
            <option value="已处理">已处理</option>
          </select>
        </div>
        <div className="mt-2 divide-y divide-[#eef1f3]">
          {filteredAlerts.slice(0, 20).map((alert) => (
            <button key={alert.id} className="w-full py-3 text-left first:pt-1 last:pb-0" type="button" onClick={() => onSelectAlert(alert.id)}>
              <div className="flex items-center justify-between gap-3">
                <p className="min-w-0 truncate text-[12.5px] font-semibold">{alert.title}</p>
                <span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold ${severityTone[alert.severity] ?? "bg-[#eef6f1] text-[#24744f]"}`}>
                  {formatSeverity(alert.severity)}
                </span>
              </div>
              <p className="mt-1 text-[11px] leading-5 text-[#8a95a6]">
                {alert.area_name ?? "监控区域"} · {alert.object_name ?? alert.alert_type} · {alert.status}
              </p>
            </button>
          ))}
          {!loading && filteredAlerts.length === 0 ? <EmptyLine text="当前条件暂无告警记录" /> : null}
        </div>
      </Card>
    </div>
  )
}

export function MobileWorkOrdersPane({
  workOrders,
  detail,
  selectedWorkOrderId,
  onSelectWorkOrder,
  onCloseDetail,
  onAccept,
  onSubmit,
  loading,
  actionPending,
}: {
  workOrders: MobileWorkOrder[]
  detail?: MobileWorkOrder
  selectedWorkOrderId?: string | null
  onSelectWorkOrder: (workOrderId: string) => void
  onCloseDetail: () => void
  onAccept: (workOrderId: string) => Promise<void>
  onSubmit: (workOrderId: string, result: string, attachments: string[]) => Promise<void>
  loading: boolean
  actionPending: boolean
}) {
  const [statusFilter, setStatusFilter] = useState("all")
  const [typeFilter, setTypeFilter] = useState("all")
  if (selectedWorkOrderId) {
    return (
      <WorkOrderDetailPanel
        workOrder={detail ?? workOrders.find((item) => item.id === selectedWorkOrderId)}
        onClose={onCloseDetail}
        onAccept={onAccept}
        onSubmit={onSubmit}
        actionPending={actionPending}
      />
    )
  }
  const pending = workOrders.filter((item) => item.status !== "已完成").length
  const taskTypes = Array.from(new Set(workOrders.map((item) => item.task_type))).filter(Boolean)
  const filteredWorkOrders = workOrders.filter((item) => {
    const matchStatus = statusFilter === "all" || item.status === statusFilter
    const matchType = typeFilter === "all" || item.task_type === typeFilter
    return matchStatus && matchType
  })
  return (
    <div className="space-y-3">
      <Card>
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-semibold">工单任务</h2>
          <StatusPill text={`待处理 ${pending}`} tone={pending > 0 ? "warn" : "ok"} />
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2">
          <MiniStat label="全部" value={`${workOrders.length}`} />
          <MiniStat label="处理中" value={`${workOrders.filter((item) => item.status === "处理中").length}`} />
          <MiniStat label="已完成" value={`${workOrders.filter((item) => item.status === "已完成").length}`} />
        </div>
      </Card>

      <Card>
        <h3 className="text-[14px] font-semibold">任务列表</h3>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <select className="h-9 rounded-[8px] border border-[#dce4e8] bg-white px-2 text-[11px]" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">全部状态</option>
            <option value="待接单">待接单</option>
            <option value="处理中">处理中</option>
            <option value="待分派">待分派</option>
            <option value="已完成">已完成</option>
          </select>
          <select className="h-9 rounded-[8px] border border-[#dce4e8] bg-white px-2 text-[11px]" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
            <option value="all">全部类型</option>
            {taskTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
        <div className="mt-2 divide-y divide-[#eef1f3]">
          {filteredWorkOrders.slice(0, 20).map((item) => (
            <button
              key={item.id}
              className="grid w-full grid-cols-[1fr_auto] items-center gap-3 py-3 text-left first:pt-1"
              type="button"
              onClick={() => onSelectWorkOrder(item.id)}
            >
              <div>
                <div className="flex items-center gap-2">
                  <p className="min-w-0 truncate text-[12.5px] font-semibold">{item.title}</p>
                  <span className="shrink-0 rounded-full bg-[#eef6f1] px-2 py-0.5 text-[10px] font-semibold text-[#24744f]">{item.task_type}</span>
                </div>
                <p className="mt-1 text-[11px] text-[#8a95a6]">
                  {item.area_name ?? "区域"} · {item.object_name ?? "对象"} · {item.assignee}
                </p>
              </div>
              <StatusPill text={item.status} tone={item.status === "已完成" ? "ok" : "warn"} />
            </button>
          ))}
          {!loading && filteredWorkOrders.length === 0 ? <EmptyLine text="当前条件暂无工单任务" /> : null}
        </div>
      </Card>
    </div>
  )
}

export function MobileProfilePane({
  summary,
  tenantName,
  user,
  panel,
  onPanelChange,
}: {
  summary?: AlertSummary
  tenantName: string
  user: User | null
  panel: ProfilePanelKey
  onPanelChange: (panel: ProfilePanelKey) => void
}) {
  const logout = useAuthStore((state) => state.logout)
  const displayName = user?.name || user?.username || "运营管理员"
  const email = user?.email ?? "未绑定邮箱"
  const roleLabel = user?.isSuperuser ? "系统管理员" : "业务用户"
  const securityLabel = user?.isTwoFactorEnabled ? "双因素认证已启用" : user?.hasPassword ? "密码登录已启用" : "登录凭据已配置"

  if (panel !== "overview") {
    return <ProfileDetailPanel panel={panel} displayName={displayName} email={email} securityLabel={securityLabel} onClose={() => onPanelChange("overview")} onLogout={logout} />
  }

  return (
    <div className="space-y-3">
      <Card className="grid grid-cols-[52px_1fr] items-center gap-3">
        <div className="grid h-12 w-12 place-items-center rounded-[8px] bg-[#eef7f2] text-[#24744f]">
          <UserRound className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <h2 className="truncate text-[15px] font-semibold">{displayName}</h2>
          <p className="mt-1 truncate text-[11px] text-[#8a95a6]">{tenantName}综合能碳管理平台</p>
        </div>
      </Card>
      <Card>
        <ProfileRow icon={IdCard} title="账户资料" text={`${email} · ${securityLabel}`} onClick={() => onPanelChange("account")} actionText="编辑" />
        <ProfileRow icon={Building2} title="当前租户" text={`${tenantName} · ${roleLabel}`} />
        <ProfileRow icon={Bell} title="消息通知" text={`告警、设备提醒 · 未处理 ${summary?.unhandled ?? 0} 项`} onClick={() => onPanelChange("notifications")} actionText="设置" />
        <ProfileRow icon={ShieldCheck} title="权限范围" text="按租户、角色和菜单权限控制访问范围" onClick={() => onPanelChange("security")} actionText="查看" />
        <ProfileRow icon={FileText} title="操作手册" text="查看平台操作手册与功能说明" onClick={() => onPanelChange("help")} actionText="查看" />
      </Card>
    </div>
  )
}

export function MobilePageState({ title, text, tone = "neutral" }: { title: string; text: string; tone?: "neutral" | "danger" }) {
  return (
    <Card className="mt-4">
      <div className="flex gap-3">
        <AlertTriangle className={`mt-0.5 h-5 w-5 shrink-0 ${tone === "danger" ? "text-[#b3432f]" : "text-[#667085]"}`} />
        <div>
          <h2 className="text-[15px] font-semibold">{title}</h2>
          <p className="mt-1 text-[12px] leading-5 text-[#7d8998]">{text}</p>
        </div>
      </div>
    </Card>
  )
}

export function MobileRouteScaffold({ data, children }: { data: MobileEnergyCarbonData; children: ReactNode }) {
  if (data.isTeamsLoading) return <MobilePageState title="正在加载租户" text="正在读取当前账号可访问的租户列表。" />
  if (!data.currentTeam) return <MobilePageState title="暂无可用租户" text="当前账号未配置可访问租户，请联系系统管理员完成授权。" tone="danger" />
  if (data.isError) return <MobilePageState title="数据加载失败" text={data.errorMessage || "业务接口返回异常，请确认登录态、租户权限和服务状态。"} tone="danger" />
  return <>{children}</>
}

function DeviceDetailPanel({
  device,
  detail,
  timeseries,
  videos,
  onClose,
  loading,
}: {
  device: MonitorDevice
  detail?: MonitorDeviceDetail
  timeseries?: MonitorDeviceTimeseries
  videos: Record<string, unknown>[]
  onClose: () => void
  loading: boolean
}) {
  const samples = detail?.meter_samples ?? []
  const points = timeseries?.series.slice(-8).map((item) => ({ label: item.period.slice(-5), value: item.energy_kwh })) ?? []
  return (
    <div className="space-y-3">
      <DetailHeader title={device.name} meta={device.sector_name ?? device.location ?? "设备详情"} onClose={onClose} />
      <Card>
        <div className="grid grid-cols-3 gap-2">
          <MiniStat label="状态" value={isDeviceOnline(device) ? "在线" : "跟踪"} danger={!isDeviceOnline(device)} />
          <MiniStat label="告警" value={`${device.alert_unhandled ?? 0} 项`} danger={(device.alert_unhandled ?? 0) > 0} />
          <MiniStat label="视频" value={`${videos.length} 路`} />
        </div>
        <MiniAreaChart points={points} className="mt-3 h-[90px]" emptyText={loading ? "正在加载曲线" : "暂无实时曲线"} />
      </Card>
      <Card>
        <h3 className="text-[14px] font-semibold">基础信息</h3>
        <KeyValue label="设备编码" value={device.code} />
        <KeyValue label="所属区域" value={device.sector_name} />
        <KeyValue label="通讯协议" value={device.protocol} />
        <KeyValue label="安装位置" value={device.location} />
      </Card>
      <Card>
        <h3 className="text-[14px] font-semibold">最近采样</h3>
        <div className="mt-2 divide-y divide-[#eef1f3]">
          {samples.slice(0, 5).map((item, index) => (
            <div key={`${item.id ?? index}`} className="flex items-center justify-between py-2 text-[11px]">
              <span className="text-[#667085]">{item.point_code ?? "计量点"}</span>
              <span className="font-semibold">{formatNumber(Number(item.normalized_value ?? 0))}</span>
            </div>
          ))}
          {!loading && samples.length === 0 ? <EmptyLine text="暂无采样记录" /> : null}
        </div>
      </Card>
    </div>
  )
}

function AlertDetailPanel({
  alert,
  onClose,
  onAcknowledge,
  onTransfer,
  actionPending,
}: {
  alert?: AlertDetail | AlertRow
  onClose: () => void
  onAcknowledge: (alertId: string, note?: string) => Promise<void>
  onTransfer: (alertId: string, note?: string) => Promise<string | null>
  actionPending: boolean
}) {
  const [message, setMessage] = useState<string | null>(null)
  const history = "history" in (alert ?? {}) ? (alert as AlertDetail).history : []
  if (!alert) return <MobilePageState title="告警不存在" text="未找到对应告警记录。" tone="danger" />
  return (
    <div className="space-y-3">
      <DetailHeader title={alert.title} meta={`${alert.area_name ?? "监控区域"} · ${alert.object_name ?? alert.alert_type}`} onClose={onClose} />
      {message ? <ResultBanner text={message} /> : null}
      <Card>
        <div className="grid grid-cols-3 gap-2">
          <MiniStat label="等级" value={formatSeverity(alert.severity)} danger={alert.severity === "high"} />
          <MiniStat label="状态" value={alert.status} />
          <MiniStat label="来源" value={alert.source === "video" ? "视频" : "设备"} />
        </div>
        <p className="mt-3 rounded-[8px] bg-[#f8faf9] p-3 text-[12px] leading-5 text-[#435064]">{alert.description ?? alert.title}</p>
      </Card>
      <Card>
        <h3 className="text-[14px] font-semibold">处理记录</h3>
        <div className="mt-3 space-y-2">
          {(history.length ? history : fallbackHistory(alert)).map((item) => (
            <ProcessStep key={`${item.label}-${item.value}`} label={item.label} time={formatHistoryValue(item.label, item.value)} />
          ))}
        </div>
      </Card>
      <div className="grid grid-cols-2 gap-2">
        <ActionButton
          icon={CheckCircle2}
          text="确认"
          disabled={actionPending}
          onClick={async () => {
            await onAcknowledge(alert.id, "已确认告警")
            setMessage("告警已确认")
          }}
        />
        <ActionButton
          icon={Send}
          text="转工单"
          disabled={actionPending}
          onClick={async () => {
            await onTransfer(alert.id, "已转入工单处理")
            setMessage("告警已转入工单")
          }}
        />
      </div>
    </div>
  )
}

function WorkOrderDetailPanel({
  workOrder,
  onClose,
  onAccept,
  onSubmit,
  actionPending,
}: {
  workOrder?: MobileWorkOrder
  onClose: () => void
  onAccept: (workOrderId: string) => Promise<void>
  onSubmit: (workOrderId: string, result: string, attachments: string[]) => Promise<void>
  actionPending: boolean
}) {
  const [result, setResult] = useState("现场已核查设备与计量数据，异常处置完成。")
  const [attachment, setAttachment] = useState("现场照片.jpg")
  const [message, setMessage] = useState<string | null>(null)
  if (!workOrder) return <MobilePageState title="工单不存在" text="未找到对应工单任务。" tone="danger" />
  return (
    <div className="space-y-3">
      <DetailHeader title={workOrder.title} meta={`${workOrder.task_type} · ${workOrder.status}`} onClose={onClose} />
      {message ? <ResultBanner text={message} /> : null}
      <Card>
        <div className="grid grid-cols-3 gap-2">
          <MiniStat label="优先级" value={workOrder.priority} danger={workOrder.priority === "高"} />
          <MiniStat label="状态" value={workOrder.status} />
          <MiniStat label="责任" value={workOrder.assignee} />
        </div>
        <KeyValue label="区域" value={workOrder.area_name} />
        <KeyValue label="对象" value={workOrder.object_name} />
      </Card>
      <Card>
        <h3 className="text-[14px] font-semibold">处理结果</h3>
        <label className="mt-3 block text-[11px] font-semibold text-[#667085]" htmlFor="mobile-work-order-result">
          结果说明
        </label>
        <textarea
          id="mobile-work-order-result"
          className="mt-1 min-h-[92px] w-full rounded-[8px] border border-[#dce4e8] bg-white p-3 text-[12px] leading-5 outline-none focus:border-[#2f7d59]"
          value={result}
          onChange={(event) => setResult(event.target.value)}
        />
        <label className="mt-3 block text-[11px] font-semibold text-[#667085]" htmlFor="mobile-work-order-attachment">
          附件名称
        </label>
        <input
          id="mobile-work-order-attachment"
          className="mt-1 h-10 w-full rounded-[8px] border border-[#dce4e8] bg-white px-3 text-[12px] outline-none focus:border-[#2f7d59]"
          value={attachment}
          onChange={(event) => setAttachment(event.target.value)}
        />
      </Card>
      <div className="grid grid-cols-2 gap-2">
        <ActionButton
          icon={Clock3}
          text="接单"
          disabled={actionPending}
          onClick={async () => {
            await onAccept(workOrder.id)
            setMessage("工单已接单")
          }}
        />
        <ActionButton
          icon={Upload}
          text="提交"
          disabled={actionPending}
          onClick={async () => {
            await onSubmit(workOrder.id, result, attachment ? [attachment] : [])
            setMessage("处理结果已提交")
          }}
        />
      </div>
    </div>
  )
}

function ProfileDetailPanel({
  panel,
  displayName,
  email,
  securityLabel,
  onClose,
  onLogout,
}: {
  panel: ProfilePanelKey
  displayName: string
  email: string
  securityLabel: string
  onClose: () => void
  onLogout: () => Promise<void>
}) {
  const titleMap: Record<ProfilePanelKey, string> = {
    overview: "我的",
    account: "账户资料",
    notifications: "消息偏好",
    security: "权限与安全",
    help: "操作手册",
  }
  return (
    <div className="space-y-3">
      <DetailHeader title={titleMap[panel]} meta={displayName} onClose={onClose} />
      <Card>
        {panel === "account" ? (
          <>
            <KeyValue label="姓名" value={displayName} />
            <KeyValue label="邮箱" value={email} />
            <ActionButton icon={Save} text="保存资料" onClick={() => undefined} />
          </>
        ) : null}
        {panel === "notifications" ? (
          <>
            <ToggleRow icon={Bell} title="告警提醒" text="高风险和待处理告警及时提醒" enabled />
            <ToggleRow icon={MessageSquare} title="工单提醒" text="接单、转派和审核状态提醒" enabled />
            <ToggleRow icon={RefreshCw} title="日报提醒" text="每日能碳数据摘要" enabled={false} />
          </>
        ) : null}
        {panel === "security" ? (
          <>
            <KeyValue label="登录状态" value={securityLabel} />
            <KeyValue label="权限范围" value="按当前租户和角色授权" />
            <ActionButton icon={LockKeyhole} text="修改密码" onClick={() => undefined} />
          </>
        ) : null}
        {panel === "help" ? (
          <>
            <ProfileLink icon={FileText} title="平台操作手册" text="能碳、设备、告警、工单移动操作说明" href="/help/woheng-showcase/index.html" />
            <ProfileLink icon={Settings} title="演示材料" text="沃衡汽车综合能碳管理平台建设能力介绍" href="/help/woheng-showcase/index.html" />
          </>
        ) : null}
      </Card>
      <button
        className="flex h-10 w-full items-center justify-center rounded-full border border-[#e2e7eb] bg-white text-[12px] font-semibold text-[#b3432f]"
        type="button"
        onClick={() => void onLogout()}
      >
        退出登录
      </button>
    </div>
  )
}

function DetailHeader({ title, meta, onClose }: { title: string; meta: string; onClose: () => void }) {
  return (
    <section className="flex items-center justify-between gap-3 px-0.5">
      <div className="min-w-0">
        <h2 className="truncate text-[17px] font-semibold tracking-[0]">{title}</h2>
        <p className="mt-1 truncate text-[11px] text-[#8a95a6]">{meta}</p>
      </div>
      <button className="shrink-0 rounded-full border border-[#dfe7e3] px-3 py-1.5 text-[11px] font-semibold text-[#315246]" type="button" onClick={onClose}>
        返回列表
      </button>
    </section>
  )
}

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-[8px] border border-[#e2e7eb] bg-white/95 p-4 shadow-[0_12px_28px_rgba(24,35,52,0.045)] ${className}`}>{children}</section>
}

function Metric({ label, value, unit, note, muted = false }: { label: string; value: string; unit: string; note: string; muted?: boolean }) {
  return (
    <Card className="min-h-[90px] p-3.5">
      <p className="text-[12.5px] font-semibold">{label}</p>
      <div className="mt-2 flex items-end gap-1">
        <strong className={`text-[24px] font-semibold leading-none ${muted ? "text-[#334155]" : "text-[#1d9a66]"}`}>{value}</strong>
        <span className="pb-0.5 text-[10px] font-medium">{unit}</span>
      </div>
      <p className="mt-1 text-[10.5px] text-[#8a95a6]">{note}</p>
    </Card>
  )
}

function MiniStat({ label, value, danger = false }: { label: string; value: string; danger?: boolean }) {
  return (
    <div className="rounded-[8px] bg-[#f6f8f9] px-2 py-2">
      <p className="text-[10px] text-[#8792a1]">{label}</p>
      <p className={`mt-1 truncate text-[13px] font-semibold ${danger ? "text-[#b3432f]" : "text-[#182334]"}`}>{value}</p>
    </div>
  )
}

function SegmentedButton({ text, active, onClick }: { text: string; active: boolean; onClick: () => void }) {
  return (
    <button
      className={`h-9 rounded-[8px] text-[12px] font-semibold ${active ? "bg-[#2f7d59] text-white" : "border border-[#dce4e8] bg-white text-[#465264]"}`}
      type="button"
      onClick={onClick}
    >
      {text}
    </button>
  )
}

function ActionButton({
  icon: Icon,
  text,
  disabled = false,
  onClick,
}: {
  icon: ComponentType<{ className?: string }>
  text: string
  disabled?: boolean
  onClick: () => void | Promise<void>
}) {
  return (
    <button
      className="flex h-10 items-center justify-center gap-1.5 rounded-full bg-[#2f7d59] text-[12px] font-semibold text-white shadow-[0_7px_16px_rgba(47,125,89,0.16)] disabled:opacity-60"
      type="button"
      disabled={disabled}
      onClick={() => void onClick()}
    >
      <Icon className="h-4 w-4" />
      {text}
    </button>
  )
}

function StatusPill({ text, tone }: { text: string; tone: "ok" | "warn" }) {
  return <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${tone === "ok" ? "bg-[#e1f2e8] text-[#24744f]" : "bg-[#fff4e5] text-[#9a5a16]"}`}>{text}</span>
}

function IssueRow({ title, value, tone }: { title: string; value: string; tone: "warn" | "info" }) {
  const toneClass = tone === "warn" ? "bg-[#fff4e5] text-[#9a5a16]" : "bg-[#edf4fb] text-[#346899]"
  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-3 rounded-[8px] bg-[#f8faf9] px-3 py-2.5">
      <p className="truncate text-[12px] font-medium">{title}</p>
      <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${toneClass}`}>{value}</span>
    </div>
  )
}

function ProcessStep({ label, time }: { label: string; time: string }) {
  return (
    <div className="grid grid-cols-[18px_1fr_auto] items-center gap-2">
      <CheckCircle2 className="h-4 w-4 text-[#24744f]" />
      <span className="text-[12px] font-medium text-[#344154]">{label}</span>
      <span className="max-w-[126px] truncate text-[11px] text-[#8a95a6]">{time}</span>
    </div>
  )
}

function ProfileRow({
  icon: Icon,
  title,
  text,
  onClick,
  actionText,
}: {
  icon: ComponentType<{ className?: string }>
  title: string
  text: string
  onClick?: () => void
  actionText?: string
}) {
  const content = (
    <>
      <Icon className="h-4 w-4 text-[#667085]" />
      <div className="min-w-0">
        <p className="text-[12.5px] font-semibold">{title}</p>
        <p className="mt-0.5 truncate text-[11px] text-[#8a95a6]">{text}</p>
      </div>
      {onClick ? (
        <span className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-[#24744f]">
          {actionText ?? "进入"}
          <ChevronRight className="h-4 w-4 text-[#9aa4b2]" />
        </span>
      ) : (
        <ChevronRight className="h-4 w-4 text-transparent" aria-hidden="true" />
      )}
    </>
  )
  const className = "grid w-full grid-cols-[20px_1fr_auto] items-center gap-3 border-b border-[#eef1f3] py-3 text-left first:pt-0 last:border-b-0 last:pb-0"
  return onClick ? (
    <button className={className} type="button" onClick={onClick}>
      {content}
    </button>
  ) : (
    <div className={className}>{content}</div>
  )
}

function ProfileLink({ icon: Icon, title, text, href }: { icon: ComponentType<{ className?: string }>; title: string; text: string; href: string }) {
  return (
    <a className="grid grid-cols-[20px_1fr_auto] items-center gap-3 border-b border-[#eef1f3] py-3 first:pt-0 last:border-b-0 last:pb-0" href={href}>
      <Icon className="h-4 w-4 text-[#667085]" />
      <div className="min-w-0">
        <p className="text-[12.5px] font-semibold">{title}</p>
        <p className="mt-0.5 truncate text-[11px] text-[#8a95a6]">{text}</p>
      </div>
      <ChevronRight className="h-4 w-4 text-[#9aa4b2]" />
    </a>
  )
}

function ToggleRow({ icon: Icon, title, text, enabled }: { icon: ComponentType<{ className?: string }>; title: string; text: string; enabled: boolean }) {
  return (
    <div className="grid grid-cols-[20px_1fr_auto] items-center gap-3 border-b border-[#eef1f3] py-3 first:pt-0 last:border-b-0 last:pb-0">
      <Icon className="h-4 w-4 text-[#667085]" />
      <div className="min-w-0">
        <p className="text-[12.5px] font-semibold">{title}</p>
        <p className="mt-0.5 truncate text-[11px] text-[#8a95a6]">{text}</p>
      </div>
      <span className={`h-5 w-9 rounded-full p-0.5 ${enabled ? "bg-[#2f7d59]" : "bg-[#d8dee5]"}`}>
        <i className={`block h-4 w-4 rounded-full bg-white transition ${enabled ? "translate-x-4" : ""}`} />
      </span>
    </div>
  )
}

function KeyValue({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="mt-3 flex items-center justify-between gap-3 text-[12px]">
      <span className="shrink-0 text-[#7d8998]">{label}</span>
      <span className="min-w-0 truncate font-semibold text-[#253246]">{value ?? "-"}</span>
    </div>
  )
}

function StateBadge({ status, alerts }: { status?: number | null; alerts: number }) {
  const abnormal = !(status == null || status === 0) || alerts > 0
  return (
    <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${abnormal ? "bg-[#fff4e5] text-[#9a5a16]" : "bg-[#e8f4ed] text-[#24744f]"}`}>
      {abnormal ? "跟踪" : "正常"}
    </span>
  )
}

function BarRow({ rank, title, value, max, unit }: { rank: number; title: string; value: number; max: number; unit: string }) {
  const width = `${Math.max(8, Math.min(100, (value / Math.max(max, 1)) * 100))}%`
  return (
    <div>
      <div className="flex items-center justify-between gap-3 text-[11px]">
        <span className="min-w-0 truncate font-semibold">
          {rank}. {title}
        </span>
        <span className="shrink-0 text-[#667085]">
          {formatNumber(value)} {unit}
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[#eef1f3]">
        <div className="h-full rounded-full bg-[#2f7d59]" style={{ width }} />
      </div>
    </div>
  )
}

function ResultBanner({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2 rounded-[8px] border border-[#cde6d8] bg-[#edf8f2] px-3 py-2 text-[12px] font-semibold text-[#24744f]">
      <CheckCircle2 className="h-4 w-4" />
      {text}
    </div>
  )
}

function EmptyLine({ text }: { text: string }) {
  return <p className="py-5 text-center text-[12px] text-[#8a95a6]">{text}</p>
}

function MiniAreaChart({ points, className, emptyText }: { points: { label: string; value: number }[]; className?: string; emptyText: string }) {
  const normalized = points.length > 1 ? points : []
  const coords = normalized.length > 1 ? buildPolyline(normalized.map((item) => item.value)) : null

  return (
    <div className={className}>
      {coords ? (
        <svg className="h-full w-full overflow-visible" viewBox="0 0 320 100" role="img" aria-label="趋势图">
          <path d={`${coords.area} L 308 82 L 12 82 Z`} fill="#2f7d59" opacity="0.1" />
          <path d={coords.line} fill="none" stroke="#2f7d59" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.4" />
          <line x1="12" x2="308" y1="82" y2="82" stroke="#dfe5ea" />
          {normalized.slice(0, 8).map((point, index) => (
            <text
              key={`${point.label}-${index}`}
              x={12 + index * (296 / Math.max(normalized.length - 1, 1))}
              y="98"
              fill="#8792a1"
              fontSize="10"
              textAnchor={index === 0 ? "start" : index === normalized.length - 1 ? "end" : "middle"}
            >
              {point.label}
            </text>
          ))}
        </svg>
      ) : (
        <div className="flex h-full items-center justify-center text-[11px] text-[#8a95a6]">{emptyText}</div>
      )}
    </div>
  )
}

function buildPolyline(values: number[]) {
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = Math.max(max - min, 1)
  const points = values.map((value, index) => {
    const x = 12 + (index / Math.max(values.length - 1, 1)) * 296
    const y = 8 + (1 - (value - min) / span) * 62
    return [x, y] as const
  })
  return {
    line: points.map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`).join(" "),
    area: points.map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`).join(" "),
  }
}

function buildDeviceGroups(devices: MonitorDevice[]) {
  const groups = (Object.keys(groupMeta) as DeviceGroupKey[]).map((key) => {
    const meta = groupMeta[key]
    const items = devices.filter((item) => meta.match.test(`${item.name}${item.code ?? ""}${item.sector_name ?? ""}${item.location ?? ""}`))
    return {
      key,
      ...meta,
      items,
      total: items.length,
      online: items.filter(isDeviceOnline).length,
      abnormal: items.filter(hasDeviceIssue).length,
    }
  })
  const assigned = new Set(groups.flatMap((group) => group.items.map((item) => item.id)))
  const rest = devices.filter((item) => !assigned.has(item.id))
  groups[1].items.push(...rest)
  groups[1].total = groups[1].items.length
  groups[1].online = groups[1].items.filter(isDeviceOnline).length
  groups[1].abnormal = groups[1].items.filter(hasDeviceIssue).length
  return groups
}

function isDeviceOnline(item: MonitorDevice) {
  return item.status == null || item.status === 0
}

function hasDeviceIssue(item: MonitorDevice) {
  return !isDeviceOnline(item) || Number(item.alert_unhandled ?? 0) > 0
}

function fallbackHistory(alert?: AlertDetail | AlertRow) {
  if (!alert) return []
  return [
    { label: "发生", value: alert.occurred_at },
    { label: "当前状态", value: alert.status },
    { label: "风险等级", value: alert.severity },
  ]
}

function formatHistoryValue(label: string, value: string | null | undefined) {
  if (!value) return "-"
  if (label === "风险等级") return formatSeverity(value)
  return value.replace("T", " ").slice(0, 16)
}

function formatSeverity(value?: string | null) {
  if (value === "high" || value === "critical") return "高"
  if (value === "medium" || value === "warning") return "中"
  if (value === "low") return "低"
  return value || "-"
}

function formatNumber(value: number) {
  if (!Number.isFinite(value)) return "0"
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: value > 100 ? 0 : 1 }).format(value)
}
