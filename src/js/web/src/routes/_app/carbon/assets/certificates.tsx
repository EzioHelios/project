import { createFileRoute } from "@tanstack/react-router"
import { Plus } from "lucide-react"
import { useState } from "react"

import { AdminPageScaffold, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type AssetRow, AssetTable, formatNumber, numberOf, RefreshButton, textOf } from "@/components/carbon/carbon-assets-common"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useCarbonAssetInstruments, useCarbonAssetLots, useEnvironmentalAssetUsages, useRecordEnvironmentalUsage } from "@/lib/api/hooks/carbon-assets"
import type { EnvironmentalUsageRequest } from "@/lib/generated/api"

export const Route = createFileRoute("/_app/carbon/assets/certificates")({ component: EnvironmentalCertificatesPage })

function EnvironmentalCertificatesPage() {
  const instruments = useCarbonAssetInstruments("GREEN_CERTIFICATE")
  const instrumentId = Number(instruments.data?.items[0]?.id ?? 0) || undefined
  const lots = useCarbonAssetLots({ instrumentId })
  const usages = useEnvironmentalAssetUsages()
  const recordUsage = useRecordEnvironmentalUsage()
  const [open, setOpen] = useState(false)
  const lotRows = (lots.data?.items ?? []) as AssetRow[]
  const usageRows = (usages.data?.items ?? []) as AssetRow[]
  const issued = lotRows.reduce((sum, row) => sum + numberOf(row, "issuedQuantity"), 0)
  const used = usageRows.reduce((sum, row) => sum + numberOf(row, "quantity"), 0)
  return (
    <AdminPageScaffold
      title="绿证与环境权益"
      topActions={
        <UsageDialog
          open={open}
          onOpenChange={setOpen}
          lots={lotRows}
          pending={recordUsage.isPending}
          onSubmit={(body) => recordUsage.mutate(body, { onSuccess: () => setOpen(false) })}
        />
      }
      metrics={
        <MetricStrip>
          <MetricTile label="绿证批次" value={lots.data?.total ?? 0} unit="批" />
          <MetricTile label="取得数量" value={formatNumber(issued, 0)} unit="张" />
          <MetricTile label="已使用" value={formatNumber(used, 0)} unit="张" />
          <MetricTile label="剩余数量" value={formatNumber(issued - used, 0)} unit="张" />
        </MetricStrip>
      }
    >
      <div className="grid gap-3 xl:grid-cols-2">
        <AssetTable
          title="绿证批次"
          rows={lotRows}
          actions={<RefreshButton onClick={() => void Promise.all([lots.refetch(), usages.refetch()])} loading={lots.isFetching || usages.isFetching} />}
          columns={[
            { key: "lotNo", label: "批次号" },
            { key: "registrySerialNo", label: "登记序列" },
            { key: "vintageYear", label: "年份" },
            { key: "issuedQuantity", label: "数量", align: "right", render: (row) => formatNumber(row.issuedQuantity, 0) },
            { key: "status", label: "状态" },
          ]}
        />
        <AssetTable
          title="权益使用记录"
          rows={usageRows}
          columns={[
            { key: "usageNo", label: "使用编号" },
            { key: "purpose", label: "用途" },
            { key: "targetType", label: "归属对象" },
            { key: "reportingPeriod", label: "报告期" },
            { key: "quantity", label: "数量", align: "right", render: (row) => formatNumber(row.quantity, 0) },
          ]}
        />
      </div>
    </AdminPageScaffold>
  )
}

function UsageDialog({
  open,
  onOpenChange,
  lots,
  pending,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (value: boolean) => void
  lots: AssetRow[]
  pending: boolean
  onSubmit: (body: EnvironmentalUsageRequest) => void
}) {
  const [lotId, setLotId] = useState("")
  const [quantity, setQuantity] = useState("")
  const [purpose, setPurpose] = useState("renewable_electricity_claim")
  const [reportingPeriod, setReportingPeriod] = useState(String(new Date().getFullYear()))
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus />
          登记使用
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>登记环境权益使用</DialogTitle>
          <DialogDescription className="sr-only">登记绿证在可再生电力声明或能源属性核销中的用途。</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <div className="grid gap-2">
            <Label>绿证批次</Label>
            <Select value={lotId} onValueChange={setLotId}>
              <SelectTrigger>
                <SelectValue placeholder="选择批次" />
              </SelectTrigger>
              <SelectContent>
                {lots.map((row) => (
                  <SelectItem key={String(row.id)} value={String(row.id)}>
                    {textOf(row, "lotNo")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label>使用数量</Label>
              <Input type="number" min="1" step="1" value={quantity} onChange={(event) => setQuantity(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>报告期</Label>
              <Input value={reportingPeriod} onChange={(event) => setReportingPeriod(event.target.value)} />
            </div>
          </div>
          <div className="grid gap-2">
            <Label>用途</Label>
            <Select value={purpose} onValueChange={setPurpose}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="renewable_electricity_claim">可再生电力声明</SelectItem>
                <SelectItem value="energy_attribute_retirement">能源属性核销</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button
            disabled={!lotId || !quantity || pending}
            onClick={() => onSubmit({ lotId: Number(lotId), quantity: Number(quantity), purpose, targetType: "organization", reportingPeriod })}
          >
            确认登记
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
