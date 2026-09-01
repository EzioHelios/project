import { createFileRoute } from "@tanstack/react-router"
import { Plus } from "lucide-react"
import { useMemo, useState } from "react"

import { AdminFilterBar, AdminPageScaffold, ChartPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type AssetRow, AssetTable, formatNumber, marketQuoteMetricLabel, RefreshButton, textOf } from "@/components/carbon/carbon-assets-common"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { createMarketKlineChartOption, createMarketPriceVolumeChartOption, useAdminChartTheme } from "@/lib/admin-chart-theme"
import { useCarbonAssetInstruments, useCarbonMarketQuotes, useCreateMarketQuote } from "@/lib/api/hooks/carbon-assets"
import type { MarketQuoteRequest } from "@/lib/generated/api"

export const Route = createFileRoute("/_app/carbon/assets/market")({ component: CarbonAssetMarketPage })

function CarbonAssetMarketPage() {
  const theme = useAdminChartTheme("carbon")
  const [instrumentId, setInstrumentId] = useState<number>()
  const [chartMode, setChartMode] = useState<"price-volume" | "kline">("kline")
  const [open, setOpen] = useState(false)
  const instruments = useCarbonAssetInstruments()
  const instrumentRows = (instruments.data?.items ?? []) as AssetRow[]
  const defaultInstrument = instrumentRows.find((row) => textOf(row, "instrumentClass") === "CEA") ?? instrumentRows[0]
  const firstInstrumentId = defaultInstrument?.id ? Number(defaultInstrument.id) : undefined
  const selectedInstrumentId = instrumentId ?? firstInstrumentId
  const quotes = useCarbonMarketQuotes(selectedInstrumentId)
  const createQuote = useCreateMarketQuote()
  const rows = useMemo(() => (quotes.data?.items ?? []) as AssetRow[], [quotes.data?.items])
  const selectedInstrument = instrumentRows.find((row) => Number(row.id) === selectedInstrumentId)
  const orderedRows = useMemo(() => [...rows].reverse(), [rows])
  const hasOhlc = rows.length > 0 && rows.every((row) => row.openPrice != null && row.highPrice != null && row.lowPrice != null)
  const priceLabel =
    textOf(selectedInstrument ?? {}, "instrumentClass") === "CEA" ? "综合价格收盘价" : textOf(selectedInstrument ?? {}, "instrumentClass") === "CCER" ? "成交均价" : "月度均价"
  const instrumentName = new Map((instruments.data?.items ?? []).map((row) => [Number(row.id), textOf(row, "name")]))
  const option = useMemo(() => {
    if (chartMode === "kline" && hasOhlc) {
      return createMarketKlineChartOption(
        theme,
        orderedRows.map((row) => ({
          trade_date: textOf(row, "tradeDate"),
          open: Number(row.openPrice),
          close: Number(row.closePrice),
          low: Number(row.lowPrice),
          high: Number(row.highPrice),
          volume: row.volume == null ? null : Number(row.volume),
        })),
        {
          priceUnit: `元/${textOf(selectedInstrument ?? {}, "nativeUnit", "单位")}`,
          volumeUnit: textOf(selectedInstrument ?? {}, "nativeUnit", "单位"),
        },
      )
    }
    return createMarketPriceVolumeChartOption(
      theme,
      orderedRows.map((row) => ({
        period: textOf(row, "tradeDate"),
        price: Number(row.closePrice ?? 0),
        volume: row.volume == null ? null : Number(row.volume),
      })),
      { priceUnit: "元", volumeUnit: textOf(selectedInstrument ?? {}, "nativeUnit"), priceLabel },
    )
  }, [chartMode, hasOhlc, orderedRows, priceLabel, selectedInstrument, theme])
  const latest = rows[0]
  return (
    <AdminPageScaffold
      title="碳市场行情"
      topActions={
        <QuoteDialog
          open={open}
          onOpenChange={setOpen}
          instruments={(instruments.data?.items ?? []) as AssetRow[]}
          pending={createQuote.isPending}
          onSubmit={(body) => createQuote.mutate(body, { onSuccess: () => setOpen(false) })}
        />
      }
      filters={
        <AdminFilterBar
          fields={[
            {
              key: "instrument",
              node: (
                <Select value={selectedInstrumentId ? String(selectedInstrumentId) : undefined} onValueChange={(value) => setInstrumentId(Number(value))}>
                  <SelectTrigger aria-label="资产工具">
                    <SelectValue placeholder="选择资产工具" />
                  </SelectTrigger>
                  <SelectContent>
                    {(instruments.data?.items ?? []).map((row) => (
                      <SelectItem key={String(row.id)} value={String(row.id)}>
                        {textOf(row, "name")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ),
            },
          ]}
          actions={<RefreshButton onClick={() => void quotes.refetch()} loading={quotes.isFetching} />}
        />
      }
      metrics={
        <MetricStrip>
          <MetricTile label="行情记录" value={quotes.data?.total ?? 0} unit="条" />
          <MetricTile label="最新价格" value={formatNumber(latest?.closePrice)} unit="元" />
          <MetricTile label="最新成交量" value={formatNumber(latest?.volume)} />
          <MetricTile label="行情日期" value={textOf(latest ?? {}, "tradeDate")} />
        </MetricStrip>
      }
    >
      <ChartPanel
        title={chartMode === "kline" && hasOhlc ? "月K线与成交量" : "月度量价走势"}
        unit={`元/${textOf(selectedInstrument ?? {}, "nativeUnit", "单位")}`}
        source={textOf(latest ?? {}, "sourceName", "市场行情台账")}
        option={rows.length ? option : undefined}
        height={320}
        actions={
          hasOhlc ? (
            <Select value={chartMode} onValueChange={(value) => setChartMode(value as "price-volume" | "kline")}>
              <SelectTrigger aria-label="图表模式" className="h-8 w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="price-volume">量价视图</SelectItem>
                <SelectItem value="kline">K线视图</SelectItem>
              </SelectContent>
            </Select>
          ) : undefined
        }
      />
      <div className="mt-3">
        <AssetTable
          title="行情台账"
          rows={rows}
          columns={[
            { key: "tradeDate", label: "月份" },
            { key: "instrumentId", label: "工具", render: (row) => instrumentName.get(Number(row.instrumentId)) ?? "—" },
            { key: "closePrice", label: "价格", align: "right", render: (row) => formatNumber(row.closePrice) },
            ...(hasOhlc
              ? [
                  { key: "openPrice", label: "开盘", align: "right" as const, render: (row: AssetRow) => formatNumber(row.openPrice) },
                  { key: "highPrice", label: "最高", align: "right" as const, render: (row: AssetRow) => formatNumber(row.highPrice) },
                  { key: "lowPrice", label: "最低", align: "right" as const, render: (row: AssetRow) => formatNumber(row.lowPrice) },
                ]
              : []),
            { key: "volume", label: "成交量", align: "right", render: (row) => formatNumber(row.volume) },
            { key: "sourceVersion", label: "价格口径", render: (row) => marketQuoteMetricLabel(row.sourceVersion) },
            { key: "sourceName", label: "来源" },
            { key: "sourceKind", label: "数据类型" },
          ]}
        />
      </div>
    </AdminPageScaffold>
  )
}

function QuoteDialog({
  open,
  onOpenChange,
  instruments,
  pending,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (value: boolean) => void
  instruments: AssetRow[]
  pending: boolean
  onSubmit: (body: MarketQuoteRequest) => void
}) {
  const [instrumentId, setInstrumentId] = useState("")
  const [tradeDate, setTradeDate] = useState(new Date().toISOString().slice(0, 10))
  const [closePrice, setClosePrice] = useState("")
  const [sourceName, setSourceName] = useState("")
  const instrument = instruments.find((row) => String(row.id) === instrumentId)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus />
          登记行情
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>登记市场行情</DialogTitle>
          <DialogDescription className="sr-only">登记已观测或正式导入的市场价格。</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <div className="grid gap-2">
            <Label>资产工具</Label>
            <Select value={instrumentId} onValueChange={setInstrumentId}>
              <SelectTrigger>
                <SelectValue placeholder="选择工具" />
              </SelectTrigger>
              <SelectContent>
                {instruments.map((row) => (
                  <SelectItem key={String(row.id)} value={String(row.id)}>
                    {textOf(row, "name")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label>交易日</Label>
              <Input type="date" value={tradeDate} onChange={(event) => setTradeDate(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>价格</Label>
              <Input type="number" min="0" step="0.01" value={closePrice} onChange={(event) => setClosePrice(event.target.value)} />
            </div>
          </div>
          <div className="grid gap-2">
            <Label>数据来源</Label>
            <Input value={sourceName} onChange={(event) => setSourceName(event.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button
            disabled={!instrumentId || !closePrice || !sourceName || pending}
            onClick={() =>
              onSubmit({
                instrumentId: Number(instrumentId),
                tradeDate,
                closePrice: Number(closePrice),
                currency: "CNY",
                quoteUnit: textOf(instrument ?? {}, "nativeUnit"),
                sourceKind: "observed",
                sourceName,
                sourceVersion: "manual-observed-v1",
              })
            }
          >
            确认登记
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
