import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import { AdminEmptyState, AdminPageHeader, AdminPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { PageContainer, PageSection } from "@/components/ui/page-layout"

type ApiResponse<T> = {
  code: number
  msg: string
  data: T
}

type EnterpriseInfo = {
  name?: string | null
  unify_code?: string | null
  belong_unit?: string | null
  industry?: string | null
  location?: string | null
  park_area?: string | number | null
  store_area?: string | number | null
  green_area?: string | number | null
  people_count?: string | number | null
}

export const Route = createFileRoute("/_app/data/company")({
  component: CompanyPage,
})

function CompanyPage() {
  const { data, isLoading, isError } = useQuery<ApiResponse<EnterpriseInfo>>({
    queryKey: ["data", "company", "enterprise-info"],
    queryFn: async () => {
      const res = await fetch("/api/master-data/enterprise-profile")
      return res.json()
    },
  })

  const info = data?.data ?? {}

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="企业基本信息" />

      <PageSection>
        {isLoading && (
          <AdminPanel title="组织档案">
            <div className="grid gap-3">
              <MetricStrip>
                {Array.from({ length: 4 }).map((_, index) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: skeleton tiles are static placeholders.
                  <div key={index} className="h-24 rounded-md bg-muted/70" />
                ))}
              </MetricStrip>
              <div className="grid gap-3 sm:grid-cols-2">
                {Array.from({ length: 5 }).map((_, index) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: skeleton rows are static placeholders.
                  <div key={index} className="h-16 rounded-md bg-muted/60" />
                ))}
              </div>
            </div>
          </AdminPanel>
        )}

        {isError && (
          <AdminPanel title="组织档案">
            <AdminEmptyState title="企业信息加载失败" className="min-h-40 text-destructive" />
          </AdminPanel>
        )}

        {!isLoading && !isError && <EnterpriseInfoCard info={info} />}
      </PageSection>
    </PageContainer>
  )
}

function EnterpriseInfoCard({ info }: { info: EnterpriseInfo }) {
  const keyFacts = [
    { label: "企业名称", value: info.name },
    { label: "统一社会信用代码", value: info.unify_code },
    { label: "所属单位", value: info.belong_unit },
    { label: "所属行业", value: info.industry },
  ]

  const fields = [
    { label: "企业地址", value: info.location, wide: true },
    { label: "园区面积", value: formatArea(info.park_area) },
    { label: "仓储面积", value: formatArea(info.store_area) },
    { label: "绿化面积", value: formatArea(info.green_area) },
    { label: "人员数量", value: formatCount(info.people_count) },
  ]

  return (
    <AdminPanel title="组织档案" contentClassName="space-y-4">
      <MetricStrip>
        {keyFacts.map((fact) => (
          <MetricTile key={fact.label} label={fact.label} value={fact.value || "-"} className="min-w-0" />
        ))}
      </MetricStrip>
      <div>
        <div className="mb-2 font-semibold text-muted-foreground text-xs leading-5">基础资料</div>
        <div className="grid gap-3 sm:grid-cols-2">
          {fields.map((field) => (
            <InfoField key={field.label} label={field.label} value={field.value} wide={field.wide} />
          ))}
        </div>
      </div>
    </AdminPanel>
  )
}

function InfoField({ label, value, wide = false }: { label: string; value: string | number | null | undefined; wide?: boolean }) {
  return (
    <div className={wide ? "sm:col-span-2" : undefined}>
      <div className="rounded-md border border-border/70 bg-background/70 px-3 py-2.5">
        <div className="text-[0.72rem] font-medium text-muted-foreground">{label}</div>
        <div className="mt-1 min-h-5 break-words font-medium text-sm">{value || "-"}</div>
      </div>
    </div>
  )
}

function formatArea(value: string | number | null | undefined) {
  return formatValueWithUnit(value, "m2")
}

function formatCount(value: string | number | null | undefined) {
  return formatValueWithUnit(value, "人")
}

function formatValueWithUnit(value: string | number | null | undefined, unit: string) {
  if (value === null || value === undefined || value === "") {
    return "-"
  }
  return `${value} ${unit}`
}
