import { createFileRoute } from "@tanstack/react-router"
import { Plus } from "lucide-react"
import { useState } from "react"

import { AdminFilterBar, AdminPageScaffold, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type AssetRow, AssetTable, formatNumber, RefreshButton, textOf } from "@/components/carbon/carbon-assets-common"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  useCarbonAssetAccounts,
  useCarbonAssetInstruments,
  useCarbonAssetLots,
  useCarbonAssetMovements,
  useCreateCarbonAccount,
  useCreateCarbonLot,
  usePostCarbonMovement,
} from "@/lib/api/hooks/carbon-assets"
import type { AccountRequest, LotRequest, MovementRequest } from "@/lib/generated/api"

export const Route = createFileRoute("/_app/carbon/assets/ledger")({ component: CarbonAssetLedgerPage })

function CarbonAssetLedgerPage() {
  const [instrumentId, setInstrumentId] = useState<number>()
  const [accountId, setAccountId] = useState<number>()
  const [lotId, setLotId] = useState<number>()
  const [dialogOpen, setDialogOpen] = useState(false)
  const instruments = useCarbonAssetInstruments()
  const accounts = useCarbonAssetAccounts(instrumentId)
  const lots = useCarbonAssetLots({ instrumentId, accountId })
  const movements = useCarbonAssetMovements({ instrumentId, accountId, lotId })
  const postMovement = usePostCarbonMovement()
  const createAccount = useCreateCarbonAccount()
  const createLot = useCreateCarbonLot()
  const rows = (movements.data?.items ?? []) as AssetRow[]
  const refresh = () => void Promise.all([instruments.refetch(), accounts.refetch(), lots.refetch(), movements.refetch()])
  return (
    <AdminPageScaffold
      title="资产台账"
      topActions={
        <div className="flex items-center gap-2">
          <AccountDialog
            instruments={(instruments.data?.items ?? []) as AssetRow[]}
            pending={createAccount.isPending}
            onSubmit={(body, close) => createAccount.mutate(body, { onSuccess: close })}
          />
          <LotDialog accounts={(accounts.data?.items ?? []) as AssetRow[]} pending={createLot.isPending} onSubmit={(body, close) => createLot.mutate(body, { onSuccess: close })} />
          <MovementDialog
            open={dialogOpen}
            onOpenChange={setDialogOpen}
            lots={(lots.data?.items ?? []) as AssetRow[]}
            pending={postMovement.isPending}
            onSubmit={(body) => postMovement.mutate(body, { onSuccess: () => setDialogOpen(false) })}
          />
        </div>
      }
      filters={
        <AdminFilterBar
          fields={[
            {
              key: "instrument",
              node: (
                <Select
                  value={instrumentId ? String(instrumentId) : "all"}
                  onValueChange={(value) => {
                    setInstrumentId(value === "all" ? undefined : Number(value))
                    setAccountId(undefined)
                    setLotId(undefined)
                  }}
                >
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
            {
              key: "account",
              node: (
                <Select
                  value={accountId ? String(accountId) : "all"}
                  onValueChange={(value) => {
                    setAccountId(value === "all" ? undefined : Number(value))
                    setLotId(undefined)
                  }}
                >
                  <SelectTrigger aria-label="资产账户">
                    <SelectValue placeholder="全部账户" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部账户</SelectItem>
                    {(accounts.data?.items ?? []).map((row) => (
                      <SelectItem key={String(row.id)} value={String(row.id)}>
                        {textOf(row, "accountName")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ),
            },
            {
              key: "lot",
              node: (
                <Select value={lotId ? String(lotId) : "all"} onValueChange={(value) => setLotId(value === "all" ? undefined : Number(value))}>
                  <SelectTrigger aria-label="资产批次">
                    <SelectValue placeholder="全部批次" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部批次</SelectItem>
                    {(lots.data?.items ?? []).map((row) => (
                      <SelectItem key={String(row.id)} value={String(row.id)}>
                        {textOf(row, "lotNo")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ),
            },
          ]}
          actions={<RefreshButton onClick={refresh} loading={movements.isFetching} />}
        />
      }
      metrics={
        <MetricStrip>
          <MetricTile label="资产工具" value={instruments.data?.total ?? 0} unit="项" />
          <MetricTile label="资产账户" value={accounts.data?.total ?? 0} unit="个" />
          <MetricTile label="资产批次" value={lots.data?.total ?? 0} unit="批" />
          <MetricTile label="台账流水" value={movements.data?.total ?? 0} unit="笔" />
        </MetricStrip>
      }
    >
      <div className="grid gap-3 xl:grid-cols-[0.9fr_1.5fr]">
        <AssetTable
          title="资产批次"
          rows={(lots.data?.items ?? []) as AssetRow[]}
          columns={[
            { key: "lotNo", label: "批次号" },
            { key: "projectName", label: "项目/来源" },
            { key: "vintageYear", label: "年份" },
            { key: "issuedQuantity", label: "签发/取得量", align: "right", render: (row) => formatNumber(row.issuedQuantity) },
          ]}
        />
        <AssetTable
          title="不可变流水"
          rows={rows}
          columns={[
            { key: "occurredOn", label: "业务日期" },
            { key: "movementNo", label: "流水号" },
            { key: "movementType", label: "业务类型" },
            { key: "quantityDelta", label: "数量变化", align: "right", render: (row) => formatNumber(row.quantityDelta) },
            { key: "sourceName", label: "来源" },
          ]}
        />
      </div>
    </AdminPageScaffold>
  )
}

function AccountDialog({ instruments, pending, onSubmit }: { instruments: AssetRow[]; pending: boolean; onSubmit: (body: AccountRequest, close: () => void) => void }) {
  const [open, setOpen] = useState(false)
  const [instrumentId, setInstrumentId] = useState("")
  const [accountCode, setAccountCode] = useState("")
  const [accountName, setAccountName] = useState("")
  const [registryAccountNo, setRegistryAccountNo] = useState("")
  const [sourceName, setSourceName] = useState("")
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          新建账户
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建资产账户</DialogTitle>
          <DialogDescription className="sr-only">建立资产工具对应的登记或托管账户。</DialogDescription>
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
              <Label>账户编号</Label>
              <Input value={accountCode} onChange={(event) => setAccountCode(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>账户名称</Label>
              <Input value={accountName} onChange={(event) => setAccountName(event.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label>登记账户号</Label>
              <Input value={registryAccountNo} onChange={(event) => setRegistryAccountNo(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>数据来源</Label>
              <Input value={sourceName} onChange={(event) => setSourceName(event.target.value)} />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button
            disabled={!instrumentId || !accountCode || !accountName || !sourceName || pending}
            onClick={() =>
              onSubmit(
                {
                  instrumentId: Number(instrumentId),
                  accountCode,
                  accountName,
                  registryAccountNo: registryAccountNo || undefined,
                  sourceName,
                },
                () => setOpen(false),
              )
            }
          >
            保存账户
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function LotDialog({ accounts, pending, onSubmit }: { accounts: AssetRow[]; pending: boolean; onSubmit: (body: LotRequest, close: () => void) => void }) {
  const [open, setOpen] = useState(false)
  const [accountId, setAccountId] = useState("")
  const [lotNo, setLotNo] = useState("")
  const [quantity, setQuantity] = useState("")
  const [vintageYear, setVintageYear] = useState(String(new Date().getFullYear()))
  const [projectName, setProjectName] = useState("")
  const [sourceName, setSourceName] = useState("")
  const [evidenceRef, setEvidenceRef] = useState("")
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          登记批次
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>登记资产批次</DialogTitle>
          <DialogDescription className="sr-only">登记配额分配、减排量签发、绿证核发或采购取得批次。</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <div className="grid gap-2">
            <Label>资产账户</Label>
            <Select value={accountId} onValueChange={setAccountId}>
              <SelectTrigger>
                <SelectValue placeholder="选择账户" />
              </SelectTrigger>
              <SelectContent>
                {accounts.map((row) => (
                  <SelectItem key={String(row.id)} value={String(row.id)}>
                    {textOf(row, "accountName")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label>批次号</Label>
              <Input value={lotNo} onChange={(event) => setLotNo(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>取得数量</Label>
              <Input type="number" min="0" step="0.001" value={quantity} onChange={(event) => setQuantity(event.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label>年份</Label>
              <Input type="number" value={vintageYear} onChange={(event) => setVintageYear(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>项目/来源名称</Label>
              <Input value={projectName} onChange={(event) => setProjectName(event.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label>数据来源</Label>
              <Input value={sourceName} onChange={(event) => setSourceName(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>凭证引用</Label>
              <Input value={evidenceRef} onChange={(event) => setEvidenceRef(event.target.value)} />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button
            disabled={!accountId || !lotNo || !quantity || !sourceName || pending}
            onClick={() =>
              onSubmit(
                {
                  accountId: Number(accountId),
                  lotNo,
                  issuedQuantity: Number(quantity),
                  vintageYear: Number(vintageYear) || undefined,
                  projectName: projectName || undefined,
                  sourceName,
                  evidenceRef: evidenceRef || undefined,
                },
                () => setOpen(false),
              )
            }
          >
            保存批次
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function MovementDialog({
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
  onSubmit: (body: MovementRequest) => void
}) {
  const [selectedLot, setSelectedLot] = useState("")
  const [movementType, setMovementType] = useState("purchase")
  const [quantity, setQuantity] = useState("")
  const [occurredOn, setOccurredOn] = useState(new Date().toISOString().slice(0, 10))
  const outgoing = ["sale", "transfer_out", "freeze", "surrender", "offset", "consume", "expire"].includes(movementType)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus />
          登记流水
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>登记资产流水</DialogTitle>
          <DialogDescription className="sr-only">登记批次级碳资产数量变化。</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <div className="grid gap-2">
            <Label>资产批次</Label>
            <Select value={selectedLot} onValueChange={setSelectedLot}>
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
          <div className="grid gap-2">
            <Label>业务类型</Label>
            <Select value={movementType} onValueChange={setMovementType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {["purchase", "sale", "transfer_in", "transfer_out", "freeze", "unfreeze"].map((value) => (
                  <SelectItem key={value} value={value}>
                    {value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label>数量</Label>
              <Input type="number" min="0" step="0.001" value={quantity} onChange={(event) => setQuantity(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>业务日期</Label>
              <Input type="date" value={occurredOn} onChange={(event) => setOccurredOn(event.target.value)} />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button
            disabled={!selectedLot || !quantity || pending}
            onClick={() => onSubmit({ lotId: Number(selectedLot), movementType, quantityDelta: (outgoing ? -1 : 1) * Number(quantity), occurredOn, feeAmount: 0, currency: "CNY" })}
          >
            确认登记
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
