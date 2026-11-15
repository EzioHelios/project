import { useState } from "react"
import { AdminPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { CarbonFormField } from "@/components/carbon/ghg-maintenance"
import { GhgAmountSummary, GhgRecordResults } from "@/components/carbon/ghg-record-results"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { type GhgActivity, type GhgCatalog, useGhgEmissionSources, useGhgInventoryActions } from "@/lib/api/hooks/ghg-inventory"

const generationSources = [
  { value: "energy_electricity", label: "能源用电台账", categories: ["2.1"] },
  { value: "energy_natural_gas", label: "天然气用量台账", categories: ["1.1"] },
  { value: "energy_diesel", label: "柴油用量台账", categories: ["1.1", "1.2"] },
]

export function GhgGenerateActivities({
  catalog,
  categoryCode,
  inventoryCode,
  onSelect,
}: {
  catalog?: GhgCatalog
  categoryCode: string
  inventoryCode?: string
  onSelect: (record: GhgActivity) => void
}) {
  const actions = useGhgInventoryActions()
  const [open, setOpen] = useState(false)
  const [periodId, setPeriodId] = useState("")
  const [facilityCode, setFacilityCode] = useState("")
  const [sourceCode, setSourceCode] = useState("")
  const [sourceType, setSourceType] = useState("")
  const options = generationSources.filter((source) => source.categories.includes(categoryCode))
  const period = catalog?.periods.find((item) => String(item.id) === periodId)
  const sources = useGhgEmissionSources({ inventoryCode: period?.code, categoryCode, status: "active" }, open && Boolean(period))
  const result = actions.generateActivities.data
  if (options.length === 0) return null

  return (
    <>
      <Button
        size="sm"
        variant="outline"
        onClick={() => {
          setPeriodId(String(catalog?.periods.find((item) => item.code === inventoryCode)?.id ?? catalog?.periods[0]?.id ?? ""))
          setFacilityCode(catalog?.areas.find((item) => item.level === 0)?.code ?? catalog?.areas[0]?.code ?? "")
          setSourceType(options[0].value)
          setSourceCode("")
          actions.generateActivities.reset()
          setOpen(true)
        }}
      >
        从现有台账生成
      </Button>
      <Sheet
        open={open}
        onOpenChange={(next) => {
          if (!actions.generateActivities.isPending) setOpen(next)
        }}
      >
        <SheetContent size="xwide" className="overflow-y-auto">
          <SheetHeader>
            <SheetTitle>从现有台账生成活动</SheetTitle>
          </SheetHeader>
          <div className="space-y-4 px-4 pb-4">
            <fieldset disabled={actions.generateActivities.isPending} className="grid gap-4 md:grid-cols-3">
              <CarbonFormField label="报告期">
                <Select
                  value={periodId}
                  onValueChange={(value) => {
                    setPeriodId(value)
                    setSourceCode("")
                    actions.generateActivities.reset()
                  }}
                >
                  <SelectTrigger aria-label="生成报告期">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {catalog?.periods.map((item) => (
                      <SelectItem key={item.id} value={String(item.id)}>
                        {item.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </CarbonFormField>
              <CarbonFormField label="工厂 / 区域">
                <Select
                  value={facilityCode}
                  onValueChange={(value) => {
                    setFacilityCode(value)
                    setSourceCode("")
                    actions.generateActivities.reset()
                  }}
                >
                  <SelectTrigger aria-label="生成工厂区域">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {catalog?.areas.map((item) => (
                      <SelectItem key={item.id} value={item.code}>
                        {item.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </CarbonFormField>
              <CarbonFormField label="来源台账">
                <Select
                  value={sourceType}
                  onValueChange={(value) => {
                    setSourceType(value)
                    setSourceCode("")
                    actions.generateActivities.reset()
                  }}
                >
                  <SelectTrigger aria-label="来源台账">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {options.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </CarbonFormField>
              <CarbonFormField label="排放源">
                <Select
                  value={sourceCode || "__auto"}
                  onValueChange={(value) => {
                    setSourceCode(value === "__auto" ? "" : value)
                    actions.generateActivities.reset()
                  }}
                >
                  <SelectTrigger aria-label="生成排放源">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__auto">自动匹配已配置排放源</SelectItem>
                    {(sources.data?.items ?? []).map((source) => (
                      <SelectItem key={source.sourceCode} value={source.sourceCode}>
                        {source.sourceName}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </CarbonFormField>
            </fieldset>
            {sources.isError && (
              <div role="alert" className="text-destructive text-sm">
                排放源加载失败
                <Button variant="link" onClick={() => void sources.refetch()}>
                  重新加载
                </Button>
              </div>
            )}
            <div className="flex justify-end">
              <Button
                disabled={!period || !facilityCode || !sourceType || actions.generateActivities.isPending}
                onClick={() => {
                  if (!period) return
                  actions.generateActivities.mutate({
                    inventoryCode: period.code,
                    reportingPeriodId: period.id,
                    facilityCode,
                    isoCategoryCode: categoryCode,
                    sourceTypes: [sourceType],
                    sourceCode: sourceCode || undefined,
                  })
                }}
              >
                {actions.generateActivities.isPending ? "正在生成" : result ? "重新生成" : "生成活动"}
              </Button>
            </div>
            {actions.generateActivities.isError && (
              <div role="alert" className="text-destructive text-sm">
                {actions.generateActivities.error.message}
              </div>
            )}
            {result && (
              <AdminPanel title="本次生成结果">
                <div className="space-y-4">
                  <MetricStrip>
                    <MetricTile label="新增" value={result.createdCount} unit="条" />
                    <MetricTile label="更新" value={result.updatedCount} unit="条" />
                    <MetricTile label="跳过" value={result.skippedCount} unit="条" />
                    <MetricTile label="失败" value={result.failedCount} unit="条" tone={result.failedCount ? "danger" : "default"} />
                  </MetricStrip>
                  <GhgAmountSummary summary={result.summary ?? []} />
                  {result.messages.length > 0 && (
                    <ul className="list-inside list-disc text-sm">
                      {[...new Set(result.messages)].map((message) => (
                        <li key={message}>{message}</li>
                      ))}
                    </ul>
                  )}
                  <GhgRecordResults
                    records={result.records ?? []}
                    catalog={catalog}
                    onSelect={(record) => {
                      setOpen(false)
                      onSelect(record)
                    }}
                  />
                </div>
              </AdminPanel>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </>
  )
}
