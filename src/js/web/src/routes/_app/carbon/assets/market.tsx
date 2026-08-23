import { createFileRoute } from "@tanstack/react-router"
import { Plus } from "lucide-react"
import { useMemo, useState } from "react"

import { AdminFilterBar, AdminPageScaffold, ChartPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type AssetRow, AssetTable, formatNumber, RefreshButton, textOf } from "@/components/carbon/carbon-assets-common"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { createTrendChartOption, useAdminChartTheme } from "@/lib/admin-chart-theme"
import { useCarbonAssetInstruments, useCarbonMarketQuotes, useCreateMarketQuote } from "@/lib/api/hooks/carbon-assets"
import type { MarketQuoteRequest } from "@/lib/generated/api"

export const Route = createFileRoute("/_app/carbon/assets/market")({ component: CarbonAssetMarketPage })

function CarbonAssetMarketPage() {
  const theme = useAdminChartTheme("carbon")
  const [instrumentId, setInstrumentId] = useState<number>()
  const [open, setOpen] = useState(false)
  const instruments = useCarbonAssetInstruments()
  const quotes = useCarbonMarketQuotes(instrumentId)
  const createQuote = useCreateMarketQuote()
  const rows = (quotes.data?.items ?? []) as AssetRow[]
  const instrumentName = new Map((instruments.data?.items ?? []).map((row) => [Number(row.id), textOf(row, "name")]))
  const option = useMemo(
    () =>
      createTrendChartOption(
        theme,
        [...rows].reverse().map((row) => ({ period: textOf(row, "tradeDate"), close: Number(row.closePrice ?? 0) })),
        [{ key: "close", label: "收盘价", colorKey: "scope2" }],
        { periodKey: "period", includeZeroSeries: true },
      ),
    [rows, theme],
  )
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
                <Select value={instrumentId ? String(instrumentId) : "all"} onValueChange={(value) => setInstrumentId(value === "all" ? undefined : Number(value))}>
                  <SelectTrigger aria-label="资产工具">
                    <SelectValue placeholder="全部资产工具" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部资产工具</SelectItem>
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
          <MetricTile label="最新收盘" value={formatNumber(latest?.closePrice)} unit="元" />
          <MetricTile label="最新成交量" value={formatNumber(latest?.volume)} />
          <MetricTile label="行情日期" value={textOf(latest ?? {}, "tradeDate")} />
        </MetricStrip>
      }
    >
      <ChartPanel title="价格走势" option={rows.length ? option : undefined} height={300} />
      <div className="mt-3">
        <AssetTable
          title="行情台账"
          rows={rows}
          columns={[
            { key: "tradeDate", label: "交易日" },
            { key: "instrumentId", label: "工具", render: (row) => instrumentName.get(Number(row.instrumentId)) ?? "—" },
            { key: "closePrice", label: "收盘价", align: "right", render: (row) => formatNumber(row.closePrice) },
            { key: "volume", label: "成交量", align: "right", render: (row) => formatNumber(row.volume) },
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
              <Label>收盘价</Label>
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
                sourceVersion: "1",
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
