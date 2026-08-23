import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  type AccountRequest,
  type ComplianceCycleRequest,
  type CostScenarioRequest,
  carbonAssetsCreateAccount,
  carbonAssetsCreateCostScenario,
  carbonAssetsCreateCycle,
  carbonAssetsCreateLot,
  carbonAssetsCreateQuote,
  carbonAssetsCreateSettlement,
  carbonAssetsGetCompliancePosition,
  carbonAssetsGetOverview,
  carbonAssetsListAccounts,
  carbonAssetsListCostRuns,
  carbonAssetsListCostScenarios,
  carbonAssetsListCycles,
  carbonAssetsListEnvironmentalUsages,
  carbonAssetsListInstruments,
  carbonAssetsListLots,
  carbonAssetsListMovements,
  carbonAssetsListQuotes,
  carbonAssetsListRules,
  carbonAssetsListSettlements,
  carbonAssetsPostMovement,
  carbonAssetsPostSettlement,
  carbonAssetsRecordEnvironmentalUsage,
  carbonAssetsRunCostScenario,
  type EnvironmentalUsageRequest,
  type LotRequest,
  type MarketQuoteRequest,
  type MovementRequest,
  type SettlementRequest,
} from "@/lib/generated/api"

const rootKey = ["carbon-assets"] as const

export function useCarbonAssetOverview() {
  return useQuery({ queryKey: [...rootKey, "overview"], queryFn: async () => (await carbonAssetsGetOverview({ throwOnError: true })).data })
}

export function useCarbonAssetInstruments(instrumentClass?: string) {
  return useQuery({
    queryKey: [...rootKey, "instruments", instrumentClass],
    queryFn: async () => (await carbonAssetsListInstruments({ query: { instrument_class: instrumentClass, limit: 100 }, throwOnError: true })).data,
  })
}

export function useCarbonAssetAccounts(instrumentId?: number) {
  return useQuery({
    queryKey: [...rootKey, "accounts", instrumentId],
    queryFn: async () => (await carbonAssetsListAccounts({ query: { instrument_id: instrumentId, limit: 100 }, throwOnError: true })).data,
  })
}

export function useCarbonAssetLots(filters: { instrumentId?: number; accountId?: number } = {}) {
  return useQuery({
    queryKey: [...rootKey, "lots", filters],
    queryFn: async () => (await carbonAssetsListLots({ query: { instrument_id: filters.instrumentId, account_id: filters.accountId, limit: 100 }, throwOnError: true })).data,
  })
}

export function useCarbonAssetMovements(filters: { instrumentId?: number; accountId?: number; lotId?: number } = {}) {
  return useQuery({
    queryKey: [...rootKey, "movements", filters],
    queryFn: async () =>
      (await carbonAssetsListMovements({ query: { instrument_id: filters.instrumentId, account_id: filters.accountId, lot_id: filters.lotId, limit: 100 }, throwOnError: true }))
        .data,
  })
}

export function useCarbonCompliance(cycleId?: number) {
  const cycles = useQuery({ queryKey: [...rootKey, "cycles"], queryFn: async () => (await carbonAssetsListCycles({ query: { limit: 100 }, throwOnError: true })).data })
  const rules = useQuery({ queryKey: [...rootKey, "rules"], queryFn: async () => (await carbonAssetsListRules({ query: { limit: 100 }, throwOnError: true })).data })
  const position = useQuery({
    queryKey: [...rootKey, "position", cycleId],
    queryFn: async () => (await carbonAssetsGetCompliancePosition({ query: { cycle_id: cycleId }, throwOnError: true })).data,
  })
  const settlements = useQuery({
    queryKey: [...rootKey, "settlements"],
    queryFn: async () => (await carbonAssetsListSettlements({ query: { limit: 100 }, throwOnError: true })).data,
  })
  return { cycles, rules, position, settlements }
}

export function useCarbonMarketQuotes(instrumentId?: number) {
  return useQuery({
    queryKey: [...rootKey, "quotes", instrumentId],
    queryFn: async () => (await carbonAssetsListQuotes({ query: { instrument_id: instrumentId, limit: 200 }, throwOnError: true })).data,
  })
}

export function useCarbonCostScenarios() {
  const scenarios = useQuery({
    queryKey: [...rootKey, "cost-scenarios"],
    queryFn: async () => (await carbonAssetsListCostScenarios({ query: { limit: 100 }, throwOnError: true })).data,
  })
  const runs = useQuery({ queryKey: [...rootKey, "cost-runs"], queryFn: async () => (await carbonAssetsListCostRuns({ query: { limit: 100 }, throwOnError: true })).data })
  return { scenarios, runs }
}

export function useEnvironmentalAssetUsages() {
  return useQuery({
    queryKey: [...rootKey, "environmental-usages"],
    queryFn: async () => (await carbonAssetsListEnvironmentalUsages({ query: { limit: 100 }, throwOnError: true })).data,
  })
}

function mutation<T>(handler: (value: T) => Promise<unknown>, success: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: handler,
    onSuccess: async () => {
      toast.success(success)
      await queryClient.invalidateQueries({ queryKey: rootKey })
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "操作失败"),
  })
}

export function usePostCarbonMovement() {
  return mutation<MovementRequest>(async (body) => carbonAssetsPostMovement({ body, throwOnError: true }), "资产流水已登记")
}

export function useCreateCarbonAccount() {
  return mutation<AccountRequest>(async (body) => carbonAssetsCreateAccount({ body, throwOnError: true }), "资产账户已创建")
}

export function useCreateCarbonLot() {
  return mutation<LotRequest>(async (body) => carbonAssetsCreateLot({ body, throwOnError: true }), "资产批次已登记")
}

export function useCreateComplianceCycle() {
  return mutation<ComplianceCycleRequest>(async (body) => carbonAssetsCreateCycle({ body, throwOnError: true }), "履约周期已创建")
}

export function useCreateSettlement() {
  return mutation<SettlementRequest>(async (body) => carbonAssetsCreateSettlement({ body, throwOnError: true }), "履约结算草稿已创建")
}

export function usePostSettlement() {
  return mutation<number>(async (settlementId) => carbonAssetsPostSettlement({ path: { settlement_id: settlementId }, throwOnError: true }), "履约结算已入账")
}

export function useCreateMarketQuote() {
  return mutation<MarketQuoteRequest>(async (body) => carbonAssetsCreateQuote({ body, throwOnError: true }), "行情数据已登记")
}

export function useCreateCostScenario() {
  return mutation<CostScenarioRequest>(async (body) => carbonAssetsCreateCostScenario({ body, throwOnError: true }), "成本情景已保存")
}

export function useRunCostScenario() {
  return mutation<number>(async (scenarioId) => carbonAssetsRunCostScenario({ path: { scenario_id: scenarioId }, throwOnError: true }), "成本测算已完成")
}

export function useRecordEnvironmentalUsage() {
  return mutation<EnvironmentalUsageRequest>(async (body) => carbonAssetsRecordEnvironmentalUsage({ body, throwOnError: true }), "环境权益用途已登记")
}
