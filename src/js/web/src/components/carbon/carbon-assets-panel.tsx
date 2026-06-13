import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { AlertTriangle, BadgeDollarSign, CheckCircle2, Landmark, Plus, RefreshCw, ShieldCheck, TrendingUp } from "lucide-react"
import type * as React from "react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { type ApiEnvelope, fetchCarbonApi } from "@/components/carbon/analytics-panels"
import { CarbonStatusBadge } from "@/components/carbon/status-badge"
import { type PageResult, request, requestPage } from "@/components/platform/data-admin-pages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

type CompliancePosition = {
  period_id?: number | null
  period_name?: string | null
  period_code?: string | null
  market?: string | null
  status: string
  verified_emission: number
  allowance_available: number
  credit_available: number
  surrendered_amount: number
  available_assets: number
  net_position: number
  gap_amount: number
  gap_rate: number
  risk_level: string
  accounting_batch_id?: number | null
  boundary_id?: number | null
  inventory_status?: string | null
  inventory_locked?: boolean
  inventory_message?: string | null
  accounting_batch_status?: string | null
  accounting_inventory_status?: string | null
  inventory_locked_at?: string | null
}

type ForecastScenario = {
  id?: number | null
  period_id: number
  period_name?: string | null
  scenario_code: string
  scenario_name: string
  base_year?: number | null
  forecast_start?: string | null
  forecast_end?: string | null
  emission_growth_rate: number
  planned_reduction: number
  planned_allowance_purchase: number
  planned_credit_purchase: number
  planned_surrender: number
  allowance_price: number
  credit_price: number
  currency: string
  status: string
}

type ForecastResult = {
  forecast_emission: number
  forecast_available_assets: number
  forecast_surrendered: number
  forecast_net_position: number
  forecast_gap_amount: number
  forecast_gap_rate: number
  funding_need: number
  risk_level: string
}

type ForecastMonthlyPoint = {
  month: string
  projected_emission: number
  projected_assets: number
  projected_gap: number
  gap_rate: number
  risk_level: string
}

type ForecastPayload = {
  position: CompliancePosition
  scenario: ForecastScenario | null
  result: ForecastResult
  monthly_points: ForecastMonthlyPoint[]
}

type CarbonAssetsSummary = {
  period_count: number
  account_count: number
  allowance_available: number
  credit_available: number
  latest_position: CompliancePosition
}

type CompliancePeriod = {
  id: number
  period_code: string
  period_name: string
  market: string
  period_start: string
  period_end: string
  surrender_due_date?: string | null
  accounting_batch_id?: number | null
  boundary_id?: number | null
  status: string
  position?: CompliancePosition
}

type AssetAccount = {
  id: number
  account_code: string
  account_name: string
  asset_type: string
  market: string
  currency: string
  status: string
  registry_account_no?: string | null
  owner_name?: string | null
  available_amount?: number
}

type QuotaAllocation = {
  id: number
  period_id: number
  account_id: number
  allocation_no: string
  quota_type: string
  allocated_amount: number
  adjustment_amount: number
  used_amount: number
  frozen_amount: number
  available_amount?: number
  unit: string
  period_name?: string | null
  account_name?: string | null
}

type CreditHolding = {
  id: number
  account_id: number
  holding_no: string
  credit_type: string
  project_code?: string | null
  project_name?: string | null
  registry?: string | null
  vintage_year?: number | null
  quantity: number
  used_quantity: number
  frozen_quantity: number
  available_amount?: number
  market_price?: number | null
  currency: string
  status: string
}

type AssetTransaction = {
  id: number
  transaction_no: string
  account_id: number
  asset_type: string
  transaction_type: string
  amount: number
  unit_price: number
  currency: string
  trade_date?: string | null
  status: string
  total_amount?: number
  unit_total_price?: number
}

type SurrenderRecord = {
  id: number
  period_id: number
  account_id: number
  surrender_no: string
  asset_type: string
  amount: number
  status: string
  purpose: string
  surrendered_at?: string | null
}

type AlertItem = {
  period_id: number
  period_name: string
  risk_level: string
  gap_amount: number
  gap_rate: number
  message: string
  inventory_status?: string | null
  inventory_message?: string | null
}

type Recommendation = {
  priority: string
  action: string
}

type PeriodForm = {
  period_code: string
  period_name: string
  market: string
  period_start: string
  period_end: string
  surrender_due_date: string
  accounting_batch_id: string
  boundary_id: string
}

type AccountForm = {
  account_code: string
  account_name: string
  asset_type: string
  market: string
  registry_account_no: string
  owner_name: string
}

type AllowanceForm = {
  period_id: string
  account_id: string
  allocation_no: string
  quota_type: string
  allocated_amount: string
  adjustment_amount: string
  frozen_amount: string
}

type CreditForm = {
  account_id: string
  holding_no: string
  credit_type: string
  project_code: string
  project_name: string
  registry: string
  vintage_year: string
  quantity: string
  market_price: string
}

type TransactionForm = {
  account_id: string
  asset_type: string
  transaction_type: string
  amount: string
  unit_price: string
  fee_rate: string
  tax_rate: string
  counterparty: string
}

type SurrenderForm = {
  period_id: string
  account_id: string
  asset_type: string
  quota_allocation_id: string
  credit_holding_id: string
  amount: string
  purpose: string
}

type ForecastScenarioForm = {
  period_id: string
  scenario_code: string
  scenario_name: string
  base_year: string
  forecast_start: string
  forecast_end: string
  emission_growth_rate: string
  planned_reduction: string
  planned_allowance_purchase: string
  planned_credit_purchase: string
  planned_surrender: string
  allowance_price: string
  credit_price: string
  currency: string
  status: string
  confidence_level: string
  remark: string
}

const QUERY_KEY = ["carbon-assets"]

const defaultPeriodForm: PeriodForm = {
  period_code: "",
  period_name: "",
  market: "national",
  period_start: "",
  period_end: "",
  surrender_due_date: "",
  accounting_batch_id: "",
  boundary_id: "",
}

const defaultAccountForm: AccountForm = {
  account_code: "",
  account_name: "",
  asset_type: "quota",
  market: "national",
  registry_account_no: "",
  owner_name: "",
}

const defaultAllowanceForm: AllowanceForm = {
  period_id: "",
  account_id: "",
  allocation_no: "",
  quota_type: "CEA",
  allocated_amount: "",
  adjustment_amount: "0",
  frozen_amount: "0",
}

const defaultCreditForm: CreditForm = {
  account_id: "",
  holding_no: "",
  credit_type: "ccer",
  project_code: "",
  project_name: "",
  registry: "",
  vintage_year: "",
  quantity: "",
  market_price: "",
}

const defaultTransactionForm: TransactionForm = {
  account_id: "",
  asset_type: "quota",
  transaction_type: "buy",
  amount: "",
  unit_price: "",
  fee_rate: "0",
  tax_rate: "0",
  counterparty: "",
}

const defaultSurrenderForm: SurrenderForm = {
  period_id: "",
  account_id: "",
  asset_type: "quota",
  quota_allocation_id: "",
  credit_holding_id: "",
  amount: "",
  purpose: "compliance",
}

const defaultForecastScenarioForm: ForecastScenarioForm = {
  period_id: "",
  scenario_code: "",
  scenario_name: "",
  base_year: "",
  forecast_start: "",
  forecast_end: "",
  emission_growth_rate: "0",
  planned_reduction: "0",
  planned_allowance_purchase: "0",
  planned_credit_purchase: "0",
  planned_surrender: "0",
  allowance_price: "0",
  credit_price: "0",
  currency: "CNY",
  status: "active",
  confidence_level: "medium",
  remark: "",
}

const assetTypeLabels: Record<string, string> = {
  quota: "配额",
  ccer: "CCER",
  green_certificate: "绿证",
  carbon_credit: "碳信用",
}

const riskLabels: Record<string, string> = {
  empty: "无周期",
  locked: "已锁定",
  low: "低",
  medium: "中",
  missing_batch: "缺清单",
  missing_inventory_total: "缺总量",
  yellow: "黄色",
  orange: "橙色",
  red: "红色",
  unlocked_inventory: "未锁定",
}

export function CarbonAssetsPanel() {
  const qc = useQueryClient()
  const [periodOpen, setPeriodOpen] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const [allowanceOpen, setAllowanceOpen] = useState(false)
  const [creditOpen, setCreditOpen] = useState(false)
  const [transactionOpen, setTransactionOpen] = useState(false)
  const [surrenderOpen, setSurrenderOpen] = useState(false)
  const [forecastOpen, setForecastOpen] = useState(false)
  const [selectedPeriodId, setSelectedPeriodId] = useState<number | null>(null)
  const [selectedScenarioId, setSelectedScenarioId] = useState<number | null>(null)
  const [periodForm, setPeriodForm] = useState<PeriodForm>(defaultPeriodForm)
  const [accountForm, setAccountForm] = useState<AccountForm>(defaultAccountForm)
  const [allowanceForm, setAllowanceForm] = useState<AllowanceForm>(defaultAllowanceForm)
  const [creditForm, setCreditForm] = useState<CreditForm>(defaultCreditForm)
  const [transactionForm, setTransactionForm] = useState<TransactionForm>(defaultTransactionForm)
  const [surrenderForm, setSurrenderForm] = useState<SurrenderForm>(defaultSurrenderForm)
  const [forecastForm, setForecastForm] = useState<ForecastScenarioForm>(defaultForecastScenarioForm)
  const [simulation, setSimulation] = useState<AssetTransaction | null>(null)

  const summaryQuery = useQuery<ApiEnvelope<CarbonAssetsSummary>>({
    queryKey: [...QUERY_KEY, "summary"],
    queryFn: () => fetchCarbonApi<CarbonAssetsSummary>("/api/carbon/assets/summary"),
  })
  const periodsQuery = useQuery<PageResult<CompliancePeriod>>({
    queryKey: [...QUERY_KEY, "periods"],
    queryFn: () => requestPage<CompliancePeriod>("/api/carbon/assets/compliance-periods", { limit: 100 }),
  })
  const accountsQuery = useQuery<PageResult<AssetAccount>>({
    queryKey: [...QUERY_KEY, "accounts"],
    queryFn: () => requestPage<AssetAccount>("/api/carbon/assets/accounts", { limit: 100 }),
  })

  const periods = periodsQuery.data?.items ?? []
  const accounts = accountsQuery.data?.items ?? []
  const activePeriodId = selectedPeriodId ?? periods[0]?.id ?? null
  const quotaAccounts = accounts.filter((item) => item.asset_type === "quota")
  const creditAccounts = accounts.filter((item) => item.asset_type !== "quota")

  const allowancesQuery = useQuery<PageResult<QuotaAllocation>>({
    queryKey: [...QUERY_KEY, "allowances", activePeriodId],
    queryFn: () => requestPage<QuotaAllocation>("/api/carbon/assets/allowances", { period_id: activePeriodId, limit: 100 }),
    enabled: Boolean(activePeriodId),
  })
  const creditsQuery = useQuery<PageResult<CreditHolding>>({
    queryKey: [...QUERY_KEY, "credits"],
    queryFn: () => requestPage<CreditHolding>("/api/carbon/assets/credits", { limit: 100 }),
  })
  const transactionsQuery = useQuery<PageResult<AssetTransaction>>({
    queryKey: [...QUERY_KEY, "transactions"],
    queryFn: () => requestPage<AssetTransaction>("/api/carbon/assets/transactions", { limit: 100 }),
  })
  const surrendersQuery = useQuery<PageResult<SurrenderRecord>>({
    queryKey: [...QUERY_KEY, "surrenders", activePeriodId],
    queryFn: () => requestPage<SurrenderRecord>("/api/carbon/assets/surrenders", { period_id: activePeriodId, limit: 100 }),
    enabled: Boolean(activePeriodId),
  })
  const positionQuery = useQuery<ApiEnvelope<CompliancePosition>>({
    queryKey: [...QUERY_KEY, "position", activePeriodId],
    queryFn: () => fetchCarbonApi<CompliancePosition>(`/api/carbon/assets/compliance-position${activePeriodId ? `?period_id=${activePeriodId}` : ""}`),
  })
  const alertsQuery = useQuery<ApiEnvelope<{ items: AlertItem[] }>>({
    queryKey: [...QUERY_KEY, "alerts"],
    queryFn: () => fetchCarbonApi<{ items: AlertItem[] }>("/api/carbon/assets/alerts"),
  })
  const recommendationsQuery = useQuery<ApiEnvelope<{ items: Recommendation[] }>>({
    queryKey: [...QUERY_KEY, "recommendations", activePeriodId],
    queryFn: () => fetchCarbonApi<{ items: Recommendation[] }>(`/api/carbon/assets/recommendations${activePeriodId ? `?period_id=${activePeriodId}` : ""}`),
  })
  const forecastScenariosQuery = useQuery<PageResult<ForecastScenario>>({
    queryKey: [...QUERY_KEY, "forecast-scenarios", activePeriodId],
    queryFn: () => requestPage<ForecastScenario>("/api/carbon/assets/forecast-scenarios", { period_id: activePeriodId, limit: 100 }),
    enabled: Boolean(activePeriodId),
  })
  const forecastQuery = useQuery<ApiEnvelope<ForecastPayload>>({
    queryKey: [...QUERY_KEY, "forecast", activePeriodId, selectedScenarioId],
    queryFn: () => fetchCarbonApi<ForecastPayload>(`/api/carbon/assets/forecast${forecastQueryString({ period_id: activePeriodId, scenario_id: selectedScenarioId })}`),
  })

  const summary = summaryQuery.data?.data
  const position = positionQuery.data?.data ?? summary?.latest_position
  const allowances = allowancesQuery.data?.items ?? []
  const credits = creditsQuery.data?.items ?? []
  const transactions = transactionsQuery.data?.items ?? []
  const surrenders = surrendersQuery.data?.items ?? []
  const alerts = alertsQuery.data?.data.items ?? []
  const recommendations = recommendationsQuery.data?.data.items ?? []
  const forecastScenarios = forecastScenariosQuery.data?.items ?? []
  const forecast = forecastQuery.data?.data
  const forecastResult = forecast?.result
  const monthlyPoints = forecast?.monthly_points ?? []

  const activePeriodOptions = useMemo(() => periods.map((item) => ({ label: `${item.period_name} (${item.period_code})`, value: String(item.id) })), [periods])

  const createPeriod = useMutation({
    mutationFn: () =>
      request<CompliancePeriod>("/api/carbon/assets/compliance-periods", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(periodPayload(periodForm)),
      }),
    onSuccess: async () => {
      toast.success("履约周期已创建")
      setPeriodOpen(false)
      setPeriodForm(defaultPeriodForm)
      await invalidateAssets(qc)
    },
    onError: toastError("创建履约周期失败"),
  })

  const createAccount = useMutation({
    mutationFn: () =>
      request<AssetAccount>("/api/carbon/assets/accounts", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(cleanPayload(accountForm)),
      }),
    onSuccess: async () => {
      toast.success("资产账户已创建")
      setAccountOpen(false)
      setAccountForm(defaultAccountForm)
      await invalidateAssets(qc)
    },
    onError: toastError("创建资产账户失败"),
  })

  const createAllowance = useMutation({
    mutationFn: () =>
      request<QuotaAllocation>("/api/carbon/assets/allowances", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(numberPayload(allowanceForm, ["period_id", "account_id", "allocated_amount", "adjustment_amount", "frozen_amount"])),
      }),
    onSuccess: async () => {
      toast.success("配额记录已创建")
      setAllowanceOpen(false)
      setAllowanceForm(defaultAllowanceForm)
      await invalidateAssets(qc)
    },
    onError: toastError("创建配额记录失败"),
  })

  const createCredit = useMutation({
    mutationFn: () =>
      request<CreditHolding>("/api/carbon/assets/credits", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(numberPayload(creditForm, ["account_id", "vintage_year", "quantity", "market_price"])),
      }),
    onSuccess: async () => {
      toast.success("持仓已创建")
      setCreditOpen(false)
      setCreditForm(defaultCreditForm)
      await invalidateAssets(qc)
    },
    onError: toastError("创建持仓失败"),
  })

  const simulateTransaction = useMutation({
    mutationFn: () =>
      request<AssetTransaction>("/api/carbon/assets/transactions/simulate", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(numberPayload(transactionForm, ["account_id", "amount", "unit_price", "fee_rate", "tax_rate"])),
      }),
    onSuccess: async (res) => {
      toast.success("交易模拟已生成")
      setSimulation(res.data)
      setTransactionOpen(false)
      await invalidateAssets(qc)
    },
    onError: toastError("交易模拟失败"),
  })

  const createSurrender = useMutation({
    mutationFn: () =>
      request<SurrenderRecord>("/api/carbon/assets/surrenders", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(numberPayload(surrenderForm, ["period_id", "account_id", "quota_allocation_id", "credit_holding_id", "amount"])),
      }),
    onSuccess: async () => {
      toast.success("清缴记录已创建")
      setSurrenderOpen(false)
      setSurrenderForm(defaultSurrenderForm)
      await invalidateAssets(qc)
    },
    onError: toastError("创建清缴记录失败"),
  })

  const createForecastScenario = useMutation({
    mutationFn: () =>
      request<ForecastScenario>("/api/carbon/assets/forecast-scenarios", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          ...numberPayload(forecastForm, [
            "period_id",
            "base_year",
            "emission_growth_rate",
            "planned_reduction",
            "planned_allowance_purchase",
            "planned_credit_purchase",
            "planned_surrender",
            "allowance_price",
            "credit_price",
          ]),
          period_id: Number(forecastForm.period_id || activePeriodId),
        }),
      }),
    onSuccess: async (res) => {
      toast.success("预测情景已创建")
      setForecastOpen(false)
      setForecastForm(defaultForecastScenarioForm)
      if (res.data?.id) setSelectedScenarioId(res.data.id)
      await invalidateAssets(qc)
    },
    onError: toastError("创建预测情景失败"),
  })

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={<Landmark className="size-4" />} label="履约周期" value={summary?.period_count ?? 0} />
        <MetricCard icon={<BadgeDollarSign className="size-4" />} label="资产账户" value={summary?.account_count ?? 0} />
        <MetricCard icon={<ShieldCheck className="size-4" />} label="配额可用" value={summary?.allowance_available ?? 0} unit="tCO2e" />
        <MetricCard icon={<CheckCircle2 className="size-4" />} label="信用可用" value={summary?.credit_available ?? 0} unit="tCO2e" />
      </div>

      <Card>
        <CardContent className="grid gap-4 pt-6 md:grid-cols-3 xl:grid-cols-6">
          <PositionMetric label="核定排放" value={position?.verified_emission} unit="tCO2e" />
          <PositionMetric label="可用资产" value={position?.available_assets} unit="tCO2e" />
          <PositionMetric label="已清缴" value={position?.surrendered_amount} unit="tCO2e" />
          <PositionMetric label="缺口" value={position?.gap_amount} unit="tCO2e" />
          <div className="rounded-md border p-3">
            <div className="text-xs text-muted-foreground">风险等级</div>
            <div className="mt-2">
              <RiskBadge value={position?.risk_level ?? "empty"} />
            </div>
          </div>
          <div className="rounded-md border p-3">
            <div className="text-xs text-muted-foreground">清单口径</div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <RiskBadge value={position?.inventory_status ?? "empty"} />
              {position?.accounting_batch_id ? <Badge variant="outline">批次 {position.accounting_batch_id}</Badge> : null}
            </div>
            <div className="mt-2 text-xs text-muted-foreground">{position?.inventory_message ?? "-"}</div>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center gap-3">
        <Select value={activePeriodId ? String(activePeriodId) : ""} onValueChange={(value) => setSelectedPeriodId(Number(value))}>
          <SelectTrigger className="w-[280px]">
            <SelectValue placeholder="选择履约周期" />
          </SelectTrigger>
          <SelectContent>
            {activePeriodOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" onClick={() => invalidateAssets(qc)}>
          <RefreshCw className="mr-2 size-4" />
          刷新
        </Button>
      </div>

      <Tabs defaultValue="allowances" className="space-y-4">
        <TabsList>
          <TabsTrigger value="allowances">配额台账</TabsTrigger>
          <TabsTrigger value="credits">CCER/绿证</TabsTrigger>
          <TabsTrigger value="periods">履约周期</TabsTrigger>
          <TabsTrigger value="transactions">交易模拟</TabsTrigger>
          <TabsTrigger value="forecast">滚动预测</TabsTrigger>
          <TabsTrigger value="risk">风险预警</TabsTrigger>
        </TabsList>

        <TabsContent value="allowances">
          <SectionCard
            title="配额台账"
            action={
              <Dialog open={allowanceOpen} onOpenChange={setAllowanceOpen}>
                <DialogTrigger asChild>
                  <Button size="sm">
                    <Plus className="mr-2 size-4" />
                    新增配额
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>新增配额</DialogTitle>
                  </DialogHeader>
                  <AllowanceFormView form={allowanceForm} setForm={setAllowanceForm} periods={periods} accounts={quotaAccounts} />
                  <DialogFooter>
                    <Button onClick={() => createAllowance.mutate()} disabled={createAllowance.isPending}>
                      保存
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            }
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>编号</TableHead>
                  <TableHead>周期</TableHead>
                  <TableHead>账户</TableHead>
                  <TableHead className="text-right">分配量</TableHead>
                  <TableHead className="text-right">调整量</TableHead>
                  <TableHead className="text-right">已用</TableHead>
                  <TableHead className="text-right">冻结</TableHead>
                  <TableHead className="text-right">可用</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {allowances.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.allocation_no}</TableCell>
                    <TableCell>{item.period_name ?? item.period_id}</TableCell>
                    <TableCell>{item.account_name ?? item.account_id}</TableCell>
                    <TableCell className="text-right">{formatNumber(item.allocated_amount)}</TableCell>
                    <TableCell className="text-right">{formatNumber(item.adjustment_amount)}</TableCell>
                    <TableCell className="text-right">{formatNumber(item.used_amount)}</TableCell>
                    <TableCell className="text-right">{formatNumber(item.frozen_amount)}</TableCell>
                    <TableCell className="text-right">{formatNumber(item.available_amount)}</TableCell>
                  </TableRow>
                ))}
                {allowances.length === 0 && <EmptyRow columns={8} />}
              </TableBody>
            </Table>
          </SectionCard>
        </TabsContent>

        <TabsContent value="credits">
          <SectionCard
            title="CCER/绿证"
            action={
              <Dialog open={creditOpen} onOpenChange={setCreditOpen}>
                <DialogTrigger asChild>
                  <Button size="sm">
                    <Plus className="mr-2 size-4" />
                    新增持仓
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>新增持仓</DialogTitle>
                  </DialogHeader>
                  <CreditFormView form={creditForm} setForm={setCreditForm} accounts={creditAccounts} />
                  <DialogFooter>
                    <Button onClick={() => createCredit.mutate()} disabled={createCredit.isPending}>
                      保存
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            }
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>编号</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead>项目</TableHead>
                  <TableHead>签发年份</TableHead>
                  <TableHead className="text-right">数量</TableHead>
                  <TableHead className="text-right">已用</TableHead>
                  <TableHead className="text-right">可用</TableHead>
                  <TableHead>状态</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {credits.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.holding_no}</TableCell>
                    <TableCell>{assetTypeLabels[item.credit_type] ?? item.credit_type}</TableCell>
                    <TableCell>{item.project_name ?? item.project_code ?? "-"}</TableCell>
                    <TableCell>{item.vintage_year ?? "-"}</TableCell>
                    <TableCell className="text-right">{formatNumber(item.quantity)}</TableCell>
                    <TableCell className="text-right">{formatNumber(item.used_quantity)}</TableCell>
                    <TableCell className="text-right">{formatNumber(item.available_amount)}</TableCell>
                    <TableCell>
                      <CarbonStatusBadge status={item.status} />
                    </TableCell>
                  </TableRow>
                ))}
                {credits.length === 0 && <EmptyRow columns={8} />}
              </TableBody>
            </Table>
          </SectionCard>
        </TabsContent>

        <TabsContent value="periods">
          <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
            <SectionCard
              title="履约周期"
              action={
                <Dialog open={periodOpen} onOpenChange={setPeriodOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm">
                      <Plus className="mr-2 size-4" />
                      新增周期
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>新增周期</DialogTitle>
                    </DialogHeader>
                    <PeriodFormView form={periodForm} setForm={setPeriodForm} />
                    <DialogFooter>
                      <Button onClick={() => createPeriod.mutate()} disabled={createPeriod.isPending}>
                        保存
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              }
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>编号</TableHead>
                    <TableHead>名称</TableHead>
                    <TableHead>市场</TableHead>
                    <TableHead>期间</TableHead>
                    <TableHead>状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {periods.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.period_code}</TableCell>
                      <TableCell>{item.period_name}</TableCell>
                      <TableCell>{item.market}</TableCell>
                      <TableCell>
                        {item.period_start} 至 {item.period_end}
                      </TableCell>
                      <TableCell>
                        <CarbonStatusBadge status={item.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                  {periods.length === 0 && <EmptyRow columns={5} />}
                </TableBody>
              </Table>
            </SectionCard>

            <SectionCard
              title="资产账户"
              action={
                <Dialog open={accountOpen} onOpenChange={setAccountOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm">
                      <Plus className="mr-2 size-4" />
                      新增账户
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>新增账户</DialogTitle>
                    </DialogHeader>
                    <AccountFormView form={accountForm} setForm={setAccountForm} />
                    <DialogFooter>
                      <Button onClick={() => createAccount.mutate()} disabled={createAccount.isPending}>
                        保存
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              }
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>编号</TableHead>
                    <TableHead>名称</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead className="text-right">可用量</TableHead>
                    <TableHead>状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {accounts.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.account_code}</TableCell>
                      <TableCell>{item.account_name}</TableCell>
                      <TableCell>{assetTypeLabels[item.asset_type] ?? item.asset_type}</TableCell>
                      <TableCell className="text-right">{formatNumber(item.available_amount)}</TableCell>
                      <TableCell>
                        <CarbonStatusBadge status={item.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                  {accounts.length === 0 && <EmptyRow columns={5} />}
                </TableBody>
              </Table>
            </SectionCard>
          </div>
        </TabsContent>

        <TabsContent value="transactions">
          <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
            <SectionCard
              title="交易模拟"
              action={
                <Dialog open={transactionOpen} onOpenChange={setTransactionOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm">
                      <Plus className="mr-2 size-4" />
                      新增模拟
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>新增模拟</DialogTitle>
                    </DialogHeader>
                    <TransactionFormView form={transactionForm} setForm={setTransactionForm} accounts={accounts} />
                    <DialogFooter>
                      <Button onClick={() => simulateTransaction.mutate()} disabled={simulateTransaction.isPending}>
                        生成
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              }
            >
              <div className="grid gap-3 sm:grid-cols-2">
                <PositionMetric label="成交金额" value={simulation?.total_amount} unit={simulation?.currency ?? "CNY"} />
                <PositionMetric label="含费单价" value={simulation?.unit_total_price} unit={simulation?.currency ?? "CNY"} />
              </div>
            </SectionCard>

            <SectionCard
              title="模拟记录"
              action={
                <Dialog open={surrenderOpen} onOpenChange={setSurrenderOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm" variant="outline">
                      <Plus className="mr-2 size-4" />
                      新增清缴
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>新增清缴</DialogTitle>
                    </DialogHeader>
                    <SurrenderFormView form={surrenderForm} setForm={setSurrenderForm} periods={periods} accounts={accounts} allowances={allowances} credits={credits} />
                    <DialogFooter>
                      <Button onClick={() => createSurrender.mutate()} disabled={createSurrender.isPending}>
                        保存
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              }
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>编号</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>动作</TableHead>
                    <TableHead className="text-right">数量</TableHead>
                    <TableHead className="text-right">单价</TableHead>
                    <TableHead>状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {transactions.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.transaction_no}</TableCell>
                      <TableCell>{assetTypeLabels[item.asset_type] ?? item.asset_type}</TableCell>
                      <TableCell>{item.transaction_type}</TableCell>
                      <TableCell className="text-right">{formatNumber(item.amount)}</TableCell>
                      <TableCell className="text-right">{formatNumber(item.unit_price)}</TableCell>
                      <TableCell>
                        <CarbonStatusBadge status={item.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                  {transactions.length === 0 && <EmptyRow columns={6} />}
                </TableBody>
              </Table>
            </SectionCard>
          </div>
        </TabsContent>

        <TabsContent value="forecast">
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
              <PositionMetric label="预测排放" value={forecastResult?.forecast_emission} unit="tCO2e" />
              <PositionMetric label="预测资产" value={forecastResult?.forecast_available_assets} unit="tCO2e" />
              <PositionMetric label="预测缺口" value={forecastResult?.forecast_gap_amount} unit="tCO2e" />
              <PositionMetric label="资金需求" value={forecastResult?.funding_need} unit={forecast?.scenario?.currency ?? "CNY"} />
              <div className="rounded-md border p-3">
                <div className="text-xs text-muted-foreground">预测风险</div>
                <div className="mt-2">
                  <RiskBadge value={forecastResult?.risk_level ?? "empty"} />
                </div>
              </div>
            </div>

            <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
              <SectionCard
                title="预测情景"
                action={
                  <Dialog open={forecastOpen} onOpenChange={setForecastOpen}>
                    <DialogTrigger asChild>
                      <Button size="sm">
                        <TrendingUp className="mr-2 size-4" />
                        新增情景
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>新增预测情景</DialogTitle>
                      </DialogHeader>
                      <ForecastScenarioFormView form={forecastForm} setForm={setForecastForm} periods={periods} activePeriodId={activePeriodId} />
                      <DialogFooter>
                        <Button onClick={() => createForecastScenario.mutate()} disabled={createForecastScenario.isPending || !activePeriodId}>
                          保存
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                }
              >
                <div className="mb-3">
                  <Select
                    value={selectedScenarioId ? String(selectedScenarioId) : "baseline"}
                    onValueChange={(value) => setSelectedScenarioId(value === "baseline" ? null : Number(value))}
                  >
                    <SelectTrigger className="w-[260px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="baseline">基线预测</SelectItem>
                      {forecastScenarios.map((item) => (
                        <SelectItem key={item.id ?? item.scenario_code} value={String(item.id)}>
                          {item.scenario_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>编号</TableHead>
                      <TableHead>名称</TableHead>
                      <TableHead className="text-right">增长率</TableHead>
                      <TableHead className="text-right">计划减排</TableHead>
                      <TableHead>状态</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {forecastScenarios.map((item) => (
                      <TableRow key={item.id ?? item.scenario_code}>
                        <TableCell>{item.scenario_code}</TableCell>
                        <TableCell>{item.scenario_name}</TableCell>
                        <TableCell className="text-right">{formatPercent(item.emission_growth_rate)}</TableCell>
                        <TableCell className="text-right">{formatNumber(item.planned_reduction)}</TableCell>
                        <TableCell>
                          <CarbonStatusBadge status={item.status} />
                        </TableCell>
                      </TableRow>
                    ))}
                    {forecastScenarios.length === 0 && <EmptyRow columns={5} />}
                  </TableBody>
                </Table>
              </SectionCard>

              <SectionCard title="月度滚动预测">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>月份</TableHead>
                      <TableHead className="text-right">预计排放</TableHead>
                      <TableHead className="text-right">预计资产</TableHead>
                      <TableHead className="text-right">预计缺口</TableHead>
                      <TableHead className="text-right">缺口率</TableHead>
                      <TableHead>风险</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {monthlyPoints.map((item) => (
                      <TableRow key={item.month}>
                        <TableCell>{item.month}</TableCell>
                        <TableCell className="text-right">{formatNumber(item.projected_emission)}</TableCell>
                        <TableCell className="text-right">{formatNumber(item.projected_assets)}</TableCell>
                        <TableCell className="text-right">{formatNumber(item.projected_gap)}</TableCell>
                        <TableCell className="text-right">{formatPercent(item.gap_rate)}</TableCell>
                        <TableCell>
                          <RiskBadge value={item.risk_level} />
                        </TableCell>
                      </TableRow>
                    ))}
                    {monthlyPoints.length === 0 && <EmptyRow columns={6} />}
                  </TableBody>
                </Table>
              </SectionCard>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="risk">
          <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
            <SectionCard title="风险预警">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>周期</TableHead>
                    <TableHead>风险</TableHead>
                    <TableHead className="text-right">缺口</TableHead>
                    <TableHead className="text-right">缺口率</TableHead>
                    <TableHead>状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {alerts.map((item) => (
                    <TableRow key={item.period_id}>
                      <TableCell>{item.period_name}</TableCell>
                      <TableCell>
                        <RiskBadge value={item.risk_level} />
                      </TableCell>
                      <TableCell className="text-right">{formatNumber(item.gap_amount)}</TableCell>
                      <TableCell className="text-right">{formatPercent(item.gap_rate)}</TableCell>
                      <TableCell>{item.message}</TableCell>
                    </TableRow>
                  ))}
                  {alerts.length === 0 && <EmptyRow columns={5} />}
                </TableBody>
              </Table>
            </SectionCard>

            <SectionCard title="履约建议">
              <div className="space-y-3">
                {recommendations.map((item, index) => (
                  <div key={`${item.priority}-${index}`} className="flex gap-3 rounded-md border p-3">
                    <AlertTriangle className="mt-0.5 size-4 text-amber-600" />
                    <div className="space-y-1">
                      <Badge variant="outline">{item.priority}</Badge>
                      <div className="text-sm">{item.action}</div>
                    </div>
                  </div>
                ))}
                {recommendations.length === 0 && <div className="rounded-md border p-4 text-sm text-muted-foreground">暂无建议</div>}
              </div>
            </SectionCard>

            <SectionCard title="清缴记录">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>编号</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead className="text-right">数量</TableHead>
                    <TableHead>用途</TableHead>
                    <TableHead>状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {surrenders.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.surrender_no}</TableCell>
                      <TableCell>{assetTypeLabels[item.asset_type] ?? item.asset_type}</TableCell>
                      <TableCell className="text-right">{formatNumber(item.amount)}</TableCell>
                      <TableCell>{item.purpose}</TableCell>
                      <TableCell>
                        <CarbonStatusBadge status={item.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                  {surrenders.length === 0 && <EmptyRow columns={5} />}
                </TableBody>
              </Table>
            </SectionCard>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

function MetricCard({ icon, label, value, unit }: { icon: React.ReactNode; label: string; value: number; unit?: string }) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between pt-6">
        <div>
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className="mt-1 text-2xl font-semibold">
            {formatNumber(value)}
            {unit ? <span className="ml-1 text-sm font-normal text-muted-foreground">{unit}</span> : null}
          </div>
        </div>
        <div className="rounded-md border bg-muted/30 p-2">{icon}</div>
      </CardContent>
    </Card>
  )
}

function PositionMetric({ label, value, unit }: { label: string; value?: number | null; unit?: string }) {
  return (
    <div className="rounded-md border p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold">
        {formatNumber(value)}
        {unit ? <span className="ml-1 text-sm font-normal text-muted-foreground">{unit}</span> : null}
      </div>
    </div>
  )
}

function SectionCard({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle>{title}</CardTitle>
        {action}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

function RiskBadge({ value }: { value: string }) {
  const variant =
    value === "red" || value === "orange" || value === "unlocked_inventory" || value === "missing_inventory_total" || value === "missing_batch" ? "destructive" : "outline"
  return <Badge variant={variant}>{riskLabels[value] ?? value}</Badge>
}

function EmptyRow({ columns }: { columns: number }) {
  return (
    <TableRow>
      <TableCell colSpan={columns} className="py-8 text-center text-muted-foreground">
        暂无数据
      </TableCell>
    </TableRow>
  )
}

function PeriodFormView({ form, setForm }: { form: PeriodForm; setForm: (value: PeriodForm) => void }) {
  return (
    <div className="grid gap-4 py-2">
      <FormInput label="周期编号" value={form.period_code} onChange={(period_code) => setForm({ ...form, period_code })} />
      <FormInput label="周期名称" value={form.period_name} onChange={(period_name) => setForm({ ...form, period_name })} />
      <FormInput label="开始日期" type="date" value={form.period_start} onChange={(period_start) => setForm({ ...form, period_start })} />
      <FormInput label="结束日期" type="date" value={form.period_end} onChange={(period_end) => setForm({ ...form, period_end })} />
      <FormInput label="清缴截止" type="date" value={form.surrender_due_date} onChange={(surrender_due_date) => setForm({ ...form, surrender_due_date })} />
      <FormInput label="核算批次 ID" value={form.accounting_batch_id} onChange={(accounting_batch_id) => setForm({ ...form, accounting_batch_id })} />
      <FormInput label="边界 ID" value={form.boundary_id} onChange={(boundary_id) => setForm({ ...form, boundary_id })} />
    </div>
  )
}

function AccountFormView({ form, setForm }: { form: AccountForm; setForm: (value: AccountForm) => void }) {
  return (
    <div className="grid gap-4 py-2">
      <FormInput label="账户编号" value={form.account_code} onChange={(account_code) => setForm({ ...form, account_code })} />
      <FormInput label="账户名称" value={form.account_name} onChange={(account_name) => setForm({ ...form, account_name })} />
      <Label>
        <span className="mb-2 block">资产类型</span>
        <Select value={form.asset_type} onValueChange={(asset_type) => setForm({ ...form, asset_type })}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(assetTypeLabels).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Label>
      <FormInput label="登记账号" value={form.registry_account_no} onChange={(registry_account_no) => setForm({ ...form, registry_account_no })} />
      <FormInput label="持有人" value={form.owner_name} onChange={(owner_name) => setForm({ ...form, owner_name })} />
    </div>
  )
}

function AllowanceFormView({
  form,
  setForm,
  periods,
  accounts,
}: {
  form: AllowanceForm
  setForm: (value: AllowanceForm) => void
  periods: CompliancePeriod[]
  accounts: AssetAccount[]
}) {
  return (
    <div className="grid gap-4 py-2">
      <SelectField label="履约周期" value={form.period_id} onChange={(period_id) => setForm({ ...form, period_id })} items={periods} getLabel={(item) => item.period_name} />
      <SelectField label="配额账户" value={form.account_id} onChange={(account_id) => setForm({ ...form, account_id })} items={accounts} getLabel={(item) => item.account_name} />
      <FormInput label="配额编号" value={form.allocation_no} onChange={(allocation_no) => setForm({ ...form, allocation_no })} />
      <FormInput label="分配量" value={form.allocated_amount} onChange={(allocated_amount) => setForm({ ...form, allocated_amount })} />
      <FormInput label="调整量" value={form.adjustment_amount} onChange={(adjustment_amount) => setForm({ ...form, adjustment_amount })} />
      <FormInput label="冻结量" value={form.frozen_amount} onChange={(frozen_amount) => setForm({ ...form, frozen_amount })} />
    </div>
  )
}

function CreditFormView({ form, setForm, accounts }: { form: CreditForm; setForm: (value: CreditForm) => void; accounts: AssetAccount[] }) {
  return (
    <div className="grid gap-4 py-2">
      <SelectField label="资产账户" value={form.account_id} onChange={(account_id) => setForm({ ...form, account_id })} items={accounts} getLabel={(item) => item.account_name} />
      <FormInput label="持仓编号" value={form.holding_no} onChange={(holding_no) => setForm({ ...form, holding_no })} />
      <Label>
        <span className="mb-2 block">持仓类型</span>
        <Select value={form.credit_type} onValueChange={(credit_type) => setForm({ ...form, credit_type })}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {["ccer", "green_certificate", "carbon_credit"].map((value) => (
              <SelectItem key={value} value={value}>
                {assetTypeLabels[value]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Label>
      <FormInput label="项目编号" value={form.project_code} onChange={(project_code) => setForm({ ...form, project_code })} />
      <FormInput label="项目名称" value={form.project_name} onChange={(project_name) => setForm({ ...form, project_name })} />
      <FormInput label="签发年份" value={form.vintage_year} onChange={(vintage_year) => setForm({ ...form, vintage_year })} />
      <FormInput label="数量" value={form.quantity} onChange={(quantity) => setForm({ ...form, quantity })} />
      <FormInput label="市场价格" value={form.market_price} onChange={(market_price) => setForm({ ...form, market_price })} />
    </div>
  )
}

function TransactionFormView({ form, setForm, accounts }: { form: TransactionForm; setForm: (value: TransactionForm) => void; accounts: AssetAccount[] }) {
  return (
    <div className="grid gap-4 py-2">
      <SelectField label="资产账户" value={form.account_id} onChange={(account_id) => setForm({ ...form, account_id })} items={accounts} getLabel={(item) => item.account_name} />
      <FormInput label="数量" value={form.amount} onChange={(amount) => setForm({ ...form, amount })} />
      <FormInput label="单价" value={form.unit_price} onChange={(unit_price) => setForm({ ...form, unit_price })} />
      <FormInput label="手续费率" value={form.fee_rate} onChange={(fee_rate) => setForm({ ...form, fee_rate })} />
      <FormInput label="税率" value={form.tax_rate} onChange={(tax_rate) => setForm({ ...form, tax_rate })} />
      <FormInput label="对手方" value={form.counterparty} onChange={(counterparty) => setForm({ ...form, counterparty })} />
    </div>
  )
}

function SurrenderFormView({
  form,
  setForm,
  periods,
  accounts,
  allowances,
  credits,
}: {
  form: SurrenderForm
  setForm: (value: SurrenderForm) => void
  periods: CompliancePeriod[]
  accounts: AssetAccount[]
  allowances: QuotaAllocation[]
  credits: CreditHolding[]
}) {
  return (
    <div className="grid gap-4 py-2">
      <SelectField label="履约周期" value={form.period_id} onChange={(period_id) => setForm({ ...form, period_id })} items={periods} getLabel={(item) => item.period_name} />
      <SelectField label="资产账户" value={form.account_id} onChange={(account_id) => setForm({ ...form, account_id })} items={accounts} getLabel={(item) => item.account_name} />
      <Label>
        <span className="mb-2 block">清缴来源</span>
        <Select value={form.asset_type} onValueChange={(asset_type) => setForm({ ...form, asset_type, quota_allocation_id: "", credit_holding_id: "" })}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="quota">配额</SelectItem>
            <SelectItem value="ccer">CCER/绿证</SelectItem>
          </SelectContent>
        </Select>
      </Label>
      {form.asset_type === "quota" ? (
        <SelectField
          label="配额记录"
          value={form.quota_allocation_id}
          onChange={(quota_allocation_id) => setForm({ ...form, quota_allocation_id })}
          items={allowances}
          getLabel={(item) => item.allocation_no}
        />
      ) : (
        <SelectField
          label="信用/绿证持仓"
          value={form.credit_holding_id}
          onChange={(credit_holding_id) => setForm({ ...form, credit_holding_id })}
          items={credits}
          getLabel={(item) => item.holding_no}
        />
      )}
      <FormInput label="数量" value={form.amount} onChange={(amount) => setForm({ ...form, amount })} />
    </div>
  )
}

function ForecastScenarioFormView({
  form,
  setForm,
  periods,
  activePeriodId,
}: {
  form: ForecastScenarioForm
  setForm: (value: ForecastScenarioForm) => void
  periods: CompliancePeriod[]
  activePeriodId: number | null
}) {
  const selectedPeriod = form.period_id || (activePeriodId ? String(activePeriodId) : "")
  return (
    <div className="grid gap-4 py-2">
      <SelectField label="履约周期" value={selectedPeriod} onChange={(period_id) => setForm({ ...form, period_id })} items={periods} getLabel={(item) => item.period_name} />
      <FormInput label="情景编号" value={form.scenario_code} onChange={(scenario_code) => setForm({ ...form, scenario_code })} />
      <FormInput label="情景名称" value={form.scenario_name} onChange={(scenario_name) => setForm({ ...form, scenario_name })} />
      <FormInput label="基准年" value={form.base_year} onChange={(base_year) => setForm({ ...form, base_year })} />
      <div className="grid gap-3 sm:grid-cols-2">
        <FormInput label="预测开始" type="date" value={form.forecast_start} onChange={(forecast_start) => setForm({ ...form, forecast_start })} />
        <FormInput label="预测结束" type="date" value={form.forecast_end} onChange={(forecast_end) => setForm({ ...form, forecast_end })} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <FormInput label="排放增长率" value={form.emission_growth_rate} onChange={(emission_growth_rate) => setForm({ ...form, emission_growth_rate })} />
        <FormInput label="计划减排" value={form.planned_reduction} onChange={(planned_reduction) => setForm({ ...form, planned_reduction })} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <FormInput label="计划配额购买" value={form.planned_allowance_purchase} onChange={(planned_allowance_purchase) => setForm({ ...form, planned_allowance_purchase })} />
        <FormInput label="计划信用购买" value={form.planned_credit_purchase} onChange={(planned_credit_purchase) => setForm({ ...form, planned_credit_purchase })} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <FormInput label="计划清缴" value={form.planned_surrender} onChange={(planned_surrender) => setForm({ ...form, planned_surrender })} />
        <FormInput label="币种" value={form.currency} onChange={(currency) => setForm({ ...form, currency })} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <FormInput label="配额价格" value={form.allowance_price} onChange={(allowance_price) => setForm({ ...form, allowance_price })} />
        <FormInput label="信用价格" value={form.credit_price} onChange={(credit_price) => setForm({ ...form, credit_price })} />
      </div>
    </div>
  )
}

function FormInput({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <Label>
      <span className="mb-2 block">{label}</span>
      <Input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </Label>
  )
}

function SelectField<T extends { id: number }>({
  label,
  value,
  onChange,
  items,
  getLabel,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  items: T[]
  getLabel: (item: T) => string
}) {
  return (
    <Label>
      <span className="mb-2 block">{label}</span>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {items.map((item) => (
            <SelectItem key={item.id} value={String(item.id)}>
              {getLabel(item)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Label>
  )
}

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits })
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return `${(Number(value) * 100).toFixed(2)}%`
}

function cleanPayload<T extends Record<string, string>>(form: T) {
  return Object.fromEntries(Object.entries(form).filter(([, value]) => value !== "")) as Record<string, string>
}

function numberPayload<T extends Record<string, string>>(form: T, numericKeys: string[]) {
  const payload: Record<string, string | number> = {}
  for (const [key, value] of Object.entries(form)) {
    if (value === "") continue
    payload[key] = numericKeys.includes(key) ? Number(value) : value
  }
  return payload
}

function periodPayload(form: PeriodForm) {
  return numberPayload(form, ["accounting_batch_id", "boundary_id"])
}

function forecastQueryString(params: { period_id: number | null; scenario_id: number | null }) {
  const query = new URLSearchParams()
  if (params.period_id) query.set("period_id", String(params.period_id))
  if (params.scenario_id) query.set("scenario_id", String(params.scenario_id))
  const text = query.toString()
  return text ? `?${text}` : ""
}

async function invalidateAssets(qc: ReturnType<typeof useQueryClient>) {
  await qc.invalidateQueries({ queryKey: QUERY_KEY })
}

function toastError(message: string) {
  return (error: Error) => toast.error(error.message || message)
}
