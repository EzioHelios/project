import { createFileRoute } from "@tanstack/react-router"
import { useMemo, useState } from "react"

import { BigscreenLineChart, BigscreenPieChart } from "@/components/bigscreen/charts"
import { BigscreenInfoCard, BigscreenMetricCard, BigscreenPanel } from "@/components/bigscreen/panel"
import { BigscreenSceneHost } from "@/components/bigscreen/scene"

export const Route = createFileRoute("/_app/bigscreen/zhijiang")({
  component: ZhijiangBigscreenPage,
})

type AuditStatus = "settled" | "verifying" | "baseline" | "rectifying"
type SiteType = "pump" | "fan"

type SiteTrendPoint = {
  period: string
  energy_kwh: number
  carbon_co2e: number
}

type SiteRecord = {
  id: string
  name: string
  shortName: string
  type: SiteType
  scene: string
  owner: string
  auditStatus: AuditStatus
  boundary: string
  baselineDays: number
  reportDays: number
  deviceCount: number
  meterCount: number
  dataCompleteness: number
  baselineKwh: number
  reportKwh: number
  savingKwh: number
  savingRate: number
  carbonReductionTons: number
  electricitySavingWan: number
  contractSettlementWan: number
  paybackYears: number
  unitBefore: string
  unitAfter: string
  issue: string
  x: number
  y: number
  trend: SiteTrendPoint[]
}

const siteRecords: SiteRecord[] = [
  {
    id: "taiping-pump-station",
    name: "太平街道二次供水泵房",
    shortName: "太平泵房",
    type: "pump",
    scene: "二次供水",
    owner: "县城投供水公司",
    auditStatus: "settled",
    boundary: "低压区/高压区双边界锁定",
    baselineDays: 90,
    reportDays: 62,
    deviceCount: 9,
    meterCount: 4,
    dataCompleteness: 98.6,
    baselineKwh: 64200,
    reportKwh: 45960,
    savingKwh: 18240,
    savingRate: 28.4,
    carbonReductionTons: 10.36,
    electricitySavingWan: 1.51,
    contractSettlementWan: 1.13,
    paybackYears: 1.8,
    unitBefore: "0.92 kWh/吨水",
    unitAfter: "0.66 kWh/吨水",
    issue: "当前无待整改问题，可直接进入月度结算。",
    x: 49,
    y: 48,
    trend: [
      { period: "1月", energy_kwh: 66800, carbon_co2e: 37.9 },
      { period: "2月", energy_kwh: 65200, carbon_co2e: 37.0 },
      { period: "3月", energy_kwh: 64100, carbon_co2e: 36.4 },
      { period: "4月", energy_kwh: 51100, carbon_co2e: 29.0 },
      { period: "5月", energy_kwh: 47200, carbon_co2e: 26.8 },
      { period: "6月", energy_kwh: 45960, carbon_co2e: 26.1 },
    ],
  },
  {
    id: "beimen-water-plant",
    name: "北门自来水厂送水泵组",
    shortName: "北门水厂",
    type: "pump",
    scene: "自来水厂",
    owner: "县水务集团",
    auditStatus: "verifying",
    boundary: "总送水泵组+清水池联动边界",
    baselineDays: 60,
    reportDays: 28,
    deviceCount: 6,
    meterCount: 3,
    dataCompleteness: 94.2,
    baselineKwh: 118300,
    reportKwh: 95140,
    savingKwh: 23160,
    savingRate: 19.6,
    carbonReductionTons: 13.15,
    electricitySavingWan: 1.92,
    contractSettlementWan: 0.84,
    paybackYears: 2.1,
    unitBefore: "0.54 kWh/吨水",
    unitAfter: "0.43 kWh/吨水",
    issue: "历史账期与运行日报仍需对账，当前只建议按 70% 作为暂估可结算量。",
    x: 59,
    y: 30,
    trend: [
      { period: "1月", energy_kwh: 119600, carbon_co2e: 67.9 },
      { period: "2月", energy_kwh: 117800, carbon_co2e: 66.9 },
      { period: "3月", energy_kwh: 118300, carbon_co2e: 67.2 },
      { period: "4月", energy_kwh: 106000, carbon_co2e: 60.2 },
      { period: "5月", energy_kwh: 98900, carbon_co2e: 56.2 },
      { period: "6月", energy_kwh: 95140, carbon_co2e: 54.0 },
    ],
  },
  {
    id: "renmin-hospital",
    name: "人民医院新风机房",
    shortName: "人民医院",
    type: "fan",
    scene: "医院新风",
    owner: "县人民医院",
    auditStatus: "verifying",
    boundary: "门急诊+病房楼新风主机边界",
    baselineDays: 45,
    reportDays: 30,
    deviceCount: 12,
    meterCount: 5,
    dataCompleteness: 96.1,
    baselineKwh: 52640,
    reportKwh: 39960,
    savingKwh: 12680,
    savingRate: 24.1,
    carbonReductionTons: 7.2,
    electricitySavingWan: 1.05,
    contractSettlementWan: 0.56,
    paybackYears: 2.4,
    unitBefore: "0.83 kWh/千m3风量",
    unitAfter: "0.63 kWh/千m3风量",
    issue: "手术部夜间负荷曲线需单独校正，避免混入非改造用能。",
    x: 39,
    y: 37,
    trend: [
      { period: "1月", energy_kwh: 51800, carbon_co2e: 29.4 },
      { period: "2月", energy_kwh: 52100, carbon_co2e: 29.6 },
      { period: "3月", energy_kwh: 52640, carbon_co2e: 29.9 },
      { period: "4月", energy_kwh: 44900, carbon_co2e: 25.5 },
      { period: "5月", energy_kwh: 41760, carbon_co2e: 23.7 },
      { period: "6月", energy_kwh: 39960, carbon_co2e: 22.7 },
    ],
  },
  {
    id: "metro-east",
    name: "东站地铁新风系统",
    shortName: "东站地铁",
    type: "fan",
    scene: "轨交新风",
    owner: "轨道公司运维中心",
    auditStatus: "baseline",
    boundary: "站厅/站台风机系统边界",
    baselineDays: 30,
    reportDays: 12,
    deviceCount: 8,
    meterCount: 2,
    dataCompleteness: 88.4,
    baselineKwh: 53600,
    reportKwh: 44060,
    savingKwh: 9540,
    savingRate: 17.8,
    carbonReductionTons: 5.42,
    electricitySavingWan: 0.79,
    contractSettlementWan: 0,
    paybackYears: 2.8,
    unitBefore: "1.24 kWh/千m3风量",
    unitAfter: "1.02 kWh/千m3风量",
    issue: "当前仍处报告期初段，暂不形成可结算节能量。",
    x: 70,
    y: 52,
    trend: [
      { period: "1月", energy_kwh: 53840, carbon_co2e: 30.6 },
      { period: "2月", energy_kwh: 54120, carbon_co2e: 30.7 },
      { period: "3月", energy_kwh: 53600, carbon_co2e: 30.4 },
      { period: "4月", energy_kwh: 49500, carbon_co2e: 28.1 },
      { period: "5月", energy_kwh: 46220, carbon_co2e: 26.2 },
      { period: "6月", energy_kwh: 44060, carbon_co2e: 25.0 },
    ],
  },
  {
    id: "guanghua-hotel",
    name: "光华酒店冷热源机房",
    shortName: "光华酒店",
    type: "pump",
    scene: "酒店综合机房",
    owner: "光华酒店管理公司",
    auditStatus: "rectifying",
    boundary: "冷热源泵组与客房公区边界",
    baselineDays: 60,
    reportDays: 41,
    deviceCount: 10,
    meterCount: 4,
    dataCompleteness: 91.8,
    baselineKwh: 63420,
    reportKwh: 48900,
    savingKwh: 14520,
    savingRate: 22.9,
    carbonReductionTons: 8.24,
    electricitySavingWan: 1.2,
    contractSettlementWan: 0.32,
    paybackYears: 2.2,
    unitBefore: "0.78 kWh/房晚",
    unitAfter: "0.60 kWh/房晚",
    issue: "暑期入住率波动影响较大，需补入住率修正项后再进入正式结算。",
    x: 28,
    y: 63,
    trend: [
      { period: "1月", energy_kwh: 61800, carbon_co2e: 35.1 },
      { period: "2月", energy_kwh: 62540, carbon_co2e: 35.5 },
      { period: "3月", energy_kwh: 63420, carbon_co2e: 36.0 },
      { period: "4月", energy_kwh: 54820, carbon_co2e: 31.1 },
      { period: "5月", energy_kwh: 51200, carbon_co2e: 29.0 },
      { period: "6月", energy_kwh: 48900, carbon_co2e: 27.7 },
    ],
  },
]

const auditStatusMeta: Record<AuditStatus, { label: string; tone: "cyan" | "emerald" | "amber" | "slate" }> = {
  settled: { label: "已结算", tone: "emerald" },
  verifying: { label: "审核中", tone: "cyan" },
  baseline: { label: "基线期", tone: "amber" },
  rectifying: { label: "待整改", tone: "slate" },
}

function formatNumber(value: number, maximumFractionDigits = 0) {
  return value.toLocaleString("zh-CN", { maximumFractionDigits })
}

function AuditStatusTag({ status }: { status: AuditStatus }) {
  const meta = auditStatusMeta[status]
  return (
    <span className="bigscreen-zhijiang-status-tag" data-tone={meta.tone}>
      {meta.label}
    </span>
  )
}

function CountyPilotMap({ sites, selectedSiteId, onSelect }: { sites: SiteRecord[]; selectedSiteId: string; onSelect: (siteId: string) => void }) {
  return (
    <div className="bigscreen-zhijiang-map-shell">
      <svg className="bigscreen-zhijiang-map-base" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id="zhijiang-map-fill" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="rgba(18, 86, 112, 0.86)" />
            <stop offset="100%" stopColor="rgba(7, 35, 58, 0.92)" />
          </linearGradient>
        </defs>
        <path
          d="M16 20 L31 12 L48 14 L63 8 L77 16 L86 27 L83 41 L89 55 L79 72 L64 84 L47 88 L30 82 L17 70 L11 55 L14 37 Z"
          fill="url(#zhijiang-map-fill)"
          stroke="rgba(111, 230, 255, 0.65)"
          strokeWidth="0.7"
        />
        <path d="M27 24 L43 18 L56 24 L52 37 L35 41 L25 33 Z" fill="rgba(74, 222, 128, 0.06)" stroke="rgba(125, 255, 190, 0.16)" strokeWidth="0.38" />
        <path d="M51 47 L67 42 L79 50 L73 66 L56 66 L46 57 Z" fill="rgba(56, 189, 248, 0.08)" stroke="rgba(87, 209, 255, 0.16)" strokeWidth="0.38" />
        <path d="M24 56 L36 49 L47 58 L40 73 L25 70 L19 62 Z" fill="rgba(251, 191, 36, 0.07)" stroke="rgba(255, 215, 108, 0.16)" strokeWidth="0.38" />
      </svg>

      <div className="bigscreen-zhijiang-map-grid" aria-hidden="true" />

      {sites.map((site) => (
        <button
          key={site.id}
          type="button"
          className="bigscreen-zhijiang-map-point"
          data-status={site.auditStatus}
          data-selected={site.id === selectedSiteId}
          style={{ left: `${site.x}%`, top: `${site.y}%` }}
          onClick={() => onSelect(site.id)}
        >
          <span className="bigscreen-zhijiang-map-pulse" />
          <span className="bigscreen-zhijiang-map-core" />
          <span className="bigscreen-zhijiang-map-label">
            <span>{site.shortName}</span>
            <strong>{site.savingRate.toFixed(1)}%</strong>
          </span>
        </button>
      ))}

      <div className="bigscreen-zhijiang-map-legend">
        <span data-tone="settled">已结算</span>
        <span data-tone="verifying">审核中</span>
        <span data-tone="baseline">基线期</span>
        <span data-tone="rectifying">待整改</span>
      </div>
    </div>
  )
}

function ZhijiangBigscreenPage() {
  const [selectedSiteId, setSelectedSiteId] = useState(siteRecords[0]?.id ?? "")
  const selectedSite = useMemo(() => siteRecords.find((site) => site.id === selectedSiteId) ?? siteRecords[0], [selectedSiteId])

  const portfolio = useMemo(() => {
    const totalBaseline = siteRecords.reduce((sum, site) => sum + site.baselineKwh, 0)
    const totalReport = siteRecords.reduce((sum, site) => sum + site.reportKwh, 0)
    const totalSaving = siteRecords.reduce((sum, site) => sum + site.savingKwh, 0)
    const totalCarbon = siteRecords.reduce((sum, site) => sum + site.carbonReductionTons, 0)
    const totalElectricitySavingWan = siteRecords.reduce((sum, site) => sum + site.electricitySavingWan, 0)
    const totalSettlementWan = siteRecords.reduce((sum, site) => sum + site.contractSettlementWan, 0)
    const weightedDataCompleteness =
      siteRecords.reduce((sum, site) => sum + site.dataCompleteness * site.meterCount, 0) / siteRecords.reduce((sum, site) => sum + site.meterCount, 0)
    const weightedPayback = siteRecords.reduce((sum, site) => sum + site.paybackYears * site.deviceCount, 0) / siteRecords.reduce((sum, site) => sum + site.deviceCount, 0)

    return {
      totalBaseline,
      totalReport,
      totalSaving,
      totalCarbon,
      totalElectricitySavingWan,
      totalSettlementWan,
      weightedDataCompleteness,
      weightedPayback,
      savingRate: totalBaseline > 0 ? (totalSaving / totalBaseline) * 100 : 0,
    }
  }, [])

  const topMetrics = [
    { label: "报告期电耗", value: portfolio.totalReport, unit: "kWh", ratio: -portfolio.savingRate },
    { label: "节电量", value: portfolio.totalSaving, unit: "kWh", ratio: portfolio.savingRate },
    { label: "减碳量", value: Number(portfolio.totalCarbon.toFixed(1)), unit: "tCO2e", ratio: portfolio.savingRate },
  ]

  const financeCards = [
    {
      label: "折合电费节省",
      value: `${portfolio.totalElectricitySavingWan.toFixed(2)} 万元`,
      detail: "按当前点位实测电价口径折算",
      accent: "cyan" as const,
    },
    {
      label: "当前可结算收益",
      value: `${portfolio.totalSettlementWan.toFixed(2)} 万元`,
      detail: "仅统计已结算+可暂估结算部分",
      accent: "emerald" as const,
    },
    {
      label: "已确认可结算点位",
      value: `${siteRecords.filter((site) => site.auditStatus === "settled").length} 个`,
      detail: "已锁定边界且达到月度结算条件",
      accent: "amber" as const,
    },
  ]

  const auditCards = [
    {
      label: "数据完整率",
      value: `${portfolio.weightedDataCompleteness.toFixed(1)}%`,
      detail: "按计量点加权后的综合数据质量",
      accent: "cyan" as const,
    },
    {
      label: "已进入结算点位",
      value: `${siteRecords.filter((site) => site.auditStatus === "settled").length} 个`,
      detail: "边界已锁定，报告期达到要求",
      accent: "emerald" as const,
    },
    {
      label: "待整改点位",
      value: `${siteRecords.filter((site) => site.auditStatus === "rectifying").length} 个`,
      detail: "存在修正项或边界混入问题",
      accent: "amber" as const,
    },
  ]

  const sceneAnchors = [
    { id: "site-count", label: "试点点位", value: `${siteRecords.length} 个`, position: "lt" as const },
    { id: "saving-rate", label: "综合节电率", value: `${portfolio.savingRate.toFixed(1)}%`, position: "rt" as const },
    { id: "settlement", label: "可结算收益", value: `${portfolio.totalSettlementWan.toFixed(2)} 万元`, position: "lb" as const },
    { id: "quality", label: "数据完整率", value: `${portfolio.weightedDataCompleteness.toFixed(1)}%`, position: "rb" as const },
    { id: "carbon", label: "累计减碳", value: `${portfolio.totalCarbon.toFixed(1)} tCO2e`, position: "ct" as const },
  ]

  const totalTrend = useMemo(() => {
    const periods = siteRecords[0]?.trend.map((point) => point.period) ?? []
    return periods.map((period, index) => {
      const energyKwh = siteRecords.reduce((sum, site) => sum + (site.trend[index]?.energy_kwh ?? 0), 0)
      return {
        period,
        energy_kwh: energyKwh,
        carbon_co2e: Number(siteRecords.reduce((sum, site) => sum + (site.trend[index]?.carbon_co2e ?? 0), 0).toFixed(1)),
        value: energyKwh,
      }
    })
  }, [])

  const sceneDistribution = useMemo(() => {
    const map = new Map<string, number>()
    for (const site of siteRecords) {
      map.set(site.scene, (map.get(site.scene) ?? 0) + site.savingKwh)
    }
    return Array.from(map.entries()).map(([name, value]) => ({ name, value }))
  }, [])

  const efficiencyRows = useMemo(() => {
    const parseUnitValue = (text: string) => Number.parseFloat(text.split(" ")[0] ?? "0")
    const maxSavingRate = Math.max(...siteRecords.map((site) => site.savingRate), 1)
    const maxEfficiencyGain = Math.max(
      ...siteRecords.map((site) => ((parseUnitValue(site.unitBefore) - parseUnitValue(site.unitAfter)) / parseUnitValue(site.unitBefore)) * 100),
      1,
    )

    return siteRecords.map((site) => {
      const before = parseUnitValue(site.unitBefore)
      const after = parseUnitValue(site.unitAfter)
      const efficiencyGain = before > 0 ? ((before - after) / before) * 100 : 0
      return {
        id: site.id,
        name: site.shortName,
        savingRate: site.savingRate,
        efficiencyGain,
        savingRateWidth: `${(site.savingRate / maxSavingRate) * 100}%`,
        efficiencyWidth: `${(efficiencyGain / maxEfficiencyGain) * 100}%`,
      }
    })
  }, [])

  const auditRows = useMemo(() => [...siteRecords].sort((left, right) => right.dataCompleteness - left.dataCompleteness), [])

  return (
    <div className="bigscreen-page bigscreen-zhijiang-page">
      <div className="bigscreen-zhijiang-column bigscreen-zhijiang-column-left">
        <BigscreenPanel title="县域能碳总账" frame="tall">
          <div className="bigscreen-kpi-grid" data-columns="1">
            {topMetrics.map((metric, index) => (
              <BigscreenMetricCard key={metric.label} metric={metric} tone={index === 3 ? "emerald" : index === 2 ? "amber" : "cyan"} compact />
            ))}
          </div>
        </BigscreenPanel>

        <BigscreenPanel title="合同收益测算" frame="tall">
          <div className="bigscreen-zhijiang-stack">
            {financeCards.map((card) => (
              <BigscreenInfoCard key={card.label} label={card.label} value={card.value} detail={card.detail} accent={card.accent} />
            ))}
          </div>
        </BigscreenPanel>

        <BigscreenPanel title="审计与 M&V 状态" frame="tall">
          <div className="bigscreen-zhijiang-stack">
            {auditCards.map((card) => (
              <BigscreenInfoCard key={card.label} label={card.label} value={card.value} detail={card.detail} accent={card.accent} />
            ))}
          </div>
        </BigscreenPanel>
      </div>

      <div className="bigscreen-zhijiang-column bigscreen-zhijiang-column-center">
        <BigscreenSceneHost
          eyebrow="Energy-carbon cockpit"
          title="公共设施节能降碳管理平台"
          description="地图只表达已纳入试点的真实点位。所有总量、收益和减碳结果，均围绕已确认边界、已采集计量和已形成报告期的数据口径。"
          anchors={sceneAnchors}
          showSafezone={false}
          showCore={false}
          background={<CountyPilotMap sites={siteRecords} selectedSiteId={selectedSite.id} onSelect={setSelectedSiteId} />}
          className="bigscreen-zhijiang-scene"
        />

        <div className="bigscreen-bottom-grid" data-columns="2">
          <BigscreenPanel title="月度节电与减碳趋势" frame="wide">
            <BigscreenLineChart points={totalTrend} height={188} />
          </BigscreenPanel>

          <BigscreenPanel title="场景节电结构" frame="wide">
            <div className="grid h-full grid-cols-[0.95fr_1.05fr] gap-4">
              <BigscreenPieChart items={sceneDistribution} height={188} />
              <div className="bigscreen-zhijiang-stack">
                {sceneDistribution
                  .slice()
                  .sort((left, right) => right.value - left.value)
                  .map((item) => (
                    <div key={item.name} className="bigscreen-zhijiang-list-row">
                      <span>{item.name}</span>
                      <strong>{formatNumber(item.value)} kWh</strong>
                    </div>
                  ))}
              </div>
            </div>
          </BigscreenPanel>
        </div>
      </div>

      <div className="bigscreen-zhijiang-column bigscreen-zhijiang-column-right">
        <BigscreenPanel title="选中点位节能审计卡" frame="tall">
          <div className="bigscreen-zhijiang-stack">
            <div className="bigscreen-zhijiang-site-head">
              <div>
                <div className="bigscreen-zhijiang-site-name">{selectedSite.name}</div>
                <div className="bigscreen-zhijiang-site-meta">
                  <span>{selectedSite.scene}</span>
                  <span>{selectedSite.owner}</span>
                  <AuditStatusTag status={selectedSite.auditStatus} />
                </div>
              </div>
              <div className="bigscreen-zhijiang-site-rate">{selectedSite.savingRate.toFixed(1)}%</div>
            </div>

            <div className="bigscreen-zhijiang-audit-kpis" data-columns="2">
              <div className="bigscreen-zhijiang-audit-kpi">
                <span>基线期电耗</span>
                <strong>{formatNumber(selectedSite.baselineKwh)} kWh</strong>
              </div>
              <div className="bigscreen-zhijiang-audit-kpi">
                <span>报告期电耗</span>
                <strong>{formatNumber(selectedSite.reportKwh)} kWh</strong>
              </div>
              <div className="bigscreen-zhijiang-audit-kpi">
                <span>节电量</span>
                <strong>{formatNumber(selectedSite.savingKwh)} kWh</strong>
              </div>
              <div className="bigscreen-zhijiang-audit-kpi">
                <span>可结算收益</span>
                <strong>{selectedSite.contractSettlementWan.toFixed(2)} 万元</strong>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="bigscreen-zhijiang-mini-stat">
                <span>基线 / 报告期</span>
                <strong>
                  {selectedSite.baselineDays} / {selectedSite.reportDays} 天
                </strong>
              </div>
              <div className="bigscreen-zhijiang-mini-stat">
                <span>数据完整率</span>
                <strong>{selectedSite.dataCompleteness.toFixed(1)}%</strong>
              </div>
              <div className="bigscreen-zhijiang-mini-stat">
                <span>单位能耗前</span>
                <strong>{selectedSite.unitBefore}</strong>
              </div>
              <div className="bigscreen-zhijiang-mini-stat">
                <span>单位能耗后</span>
                <strong>{selectedSite.unitAfter}</strong>
              </div>
            </div>

            <div className="bigscreen-zhijiang-note-card">
              <div className="bigscreen-zhijiang-note-label">核算边界</div>
              <div className="bigscreen-zhijiang-note-value">{selectedSite.boundary}</div>
            </div>
            <div className="bigscreen-zhijiang-note-card" data-tone="warning">
              <div className="bigscreen-zhijiang-note-label">当前审计结论</div>
              <div className="bigscreen-zhijiang-note-value">{selectedSite.issue}</div>
            </div>
          </div>
        </BigscreenPanel>

        <BigscreenPanel title="能耗下降与能效提升" frame="tall">
          <div className="bigscreen-zhijiang-composite-chart">
            {efficiencyRows.map((row) => (
              <div key={row.id} className="bigscreen-zhijiang-composite-row">
                <div className="bigscreen-zhijiang-composite-head">
                  <span className="bigscreen-zhijiang-composite-name">{row.name}</span>
                  <div className="bigscreen-zhijiang-composite-values">
                    <span>节电 {row.savingRate.toFixed(1)}%</span>
                    <span>能效改善 {row.efficiencyGain.toFixed(1)}%</span>
                  </div>
                </div>
                <div className="bigscreen-zhijiang-composite-bars">
                  <div className="bigscreen-zhijiang-composite-bar-track">
                    <div className="bigscreen-zhijiang-composite-bar-fill" style={{ width: row.savingRateWidth }} />
                  </div>
                  <div className="bigscreen-zhijiang-composite-bar-track" data-tone="emerald">
                    <div className="bigscreen-zhijiang-composite-bar-fill" data-tone="emerald" style={{ width: row.efficiencyWidth }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </BigscreenPanel>

        <BigscreenPanel title="点位审核清单" frame="tall">
          <div className="bigscreen-zhijiang-audit-table">
            {auditRows.map((site) => (
              <button key={site.id} type="button" className="bigscreen-zhijiang-audit-row" data-active={site.id === selectedSite.id} onClick={() => setSelectedSiteId(site.id)}>
                <div className="bigscreen-zhijiang-audit-row-main">
                  <div className="bigscreen-zhijiang-audit-row-name">{site.shortName}</div>
                  <AuditStatusTag status={site.auditStatus} />
                </div>
                <div className="bigscreen-zhijiang-audit-row-meta">
                  <span>完整率 {site.dataCompleteness.toFixed(1)}%</span>
                </div>
              </button>
            ))}
          </div>
        </BigscreenPanel>
      </div>
    </div>
  )
}
