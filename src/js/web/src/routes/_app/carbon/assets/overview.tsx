import { createFileRoute } from "@tanstack/react-router"

import { AdminPageScaffold, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type AssetRow, AssetTable, formatNumber, RefreshButton, textOf } from "@/components/carbon/carbon-assets-common"
import { useCarbonAssetInstruments, useCarbonAssetOverview, useCarbonCompliance } from "@/lib/api/hooks/carbon-assets"

export const Route = createFileRoute("/_app/carbon/assets/overview")({ component: CarbonAssetsOverviewPage })

function CarbonAssetsOverviewPage() {
  const overview = useCarbonAssetOverview()
  const instruments = useCarbonAssetInstruments()
  const compliance = useCarbonCompliance()
  const data = overview.data
  const position = (data?.compliancePosition ?? {}) as AssetRow
  const instrumentName = new Map((instruments.data?.items ?? []).map((row) => [Number(row.id), textOf(row, "name")]))
  const refresh = () => void Promise.all([overview.refetch(), instruments.refetch(), compliance.cycles.refetch(), compliance.position.refetch(), compliance.settlements.refetch()])
  return (
    <AdminPageScaffold
      title="碳资产总览"
      topActions={<RefreshButton onClick={refresh} loading={overview.isFetching} />}
      metrics={
        <MetricStrip>
          <MetricTile label="资产估值" value={formatNumber(data?.portfolioValueCny)} unit="元" />
          <MetricTile label="履约义务" value={formatNumber(position.obligation_tco2e)} unit="tCO₂e" />
          <MetricTile label="可覆盖量" value={formatNumber(position.covered_tco2e)} unit="tCO₂e" tone="success" />
          <MetricTile label="履约缺口" value={formatNumber(position.gap_tco2e)} unit="tCO₂e" tone={Number(position.gap_tco2e ?? 0) > 0 ? "warning" : "success"} />
        </MetricStrip>
      }
    >
      <div className="grid gap-3 xl:grid-cols-2">
        <AssetTable
          title="资产余额"
          rows={(data?.balances ?? []) as AssetRow[]}
          columns={[
            { key: "name", label: "资产工具" },
            { key: "instrumentClass", label: "类别" },
            { key: "balance", label: "可用余额", align: "right", render: (row) => formatNumber(row.balance) },
            { key: "nativeUnit", label: "单位" },
          ]}
        />
        <AssetTable
          title="最新行情"
          rows={(data?.latestQuotes ?? []) as AssetRow[]}
          columns={[
            { key: "tradeDate", label: "交易日" },
            { key: "instrumentId", label: "工具", render: (row) => instrumentName.get(Number(row.instrumentId)) ?? "—" },
            { key: "closePrice", label: "收盘价", align: "right", render: (row) => formatNumber(row.closePrice) },
            { key: "sourceName", label: "来源" },
          ]}
        />
      </div>
      <div className="mt-3 grid gap-3 xl:grid-cols-2">
        <AssetTable
          title="履约周期"
          rows={(compliance.cycles.data?.items ?? []) as AssetRow[]}
          columns={[
            { key: "cycleCode", label: "周期编号" },
            { key: "cycleName", label: "周期" },
            { key: "requiredSurrenderTco2e", label: "应清缴量", align: "right", render: (row) => formatNumber(row.requiredSurrenderTco2e) },
            { key: "status", label: "状态", render: (row) => textOf(row, "status") },
          ]}
        />
        <AssetTable
          title="最近流水"
          rows={(data?.recentMovements ?? []) as AssetRow[]}
          columns={[
            { key: "occurredOn", label: "业务日期" },
            { key: "movementNo", label: "流水号" },
            { key: "movementType", label: "类型" },
            { key: "quantityDelta", label: "数量", align: "right", render: (row) => formatNumber(row.quantityDelta) },
          ]}
        />
      </div>
    </AdminPageScaffold>
  )
}
