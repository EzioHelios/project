import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import { AdminPageHeader } from "@/components/admin-ui"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
      const res = await fetch("/api/page1/ckxxgk")
      return res.json()
    },
  })

  const info = data?.data ?? {}

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="企业基本信息" />

      <PageSection>
        {isLoading && (
          <Card>
            <CardContent className="grid gap-3 py-8">
              <div className="h-5 w-40 rounded bg-muted" />
              <div className="grid gap-3 sm:grid-cols-2">
                {Array.from({ length: 8 }).map((_, index) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: skeleton rows are static placeholders.
                  <div key={index} className="h-11 rounded-md bg-muted/70" />
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {isError && (
          <Card>
            <CardContent className="py-10 text-sm text-destructive">企业信息加载失败，请稍后重试。</CardContent>
          </Card>
        )}

        {!isLoading && !isError && <EnterpriseInfoCard info={info} />}
      </PageSection>
    </PageContainer>
  )
}

function EnterpriseInfoCard({ info }: { info: EnterpriseInfo }) {
  const fields = [
    { label: "企业名称", value: info.name },
    { label: "统一社会信用代码", value: info.unify_code },
    { label: "所属单位", value: info.belong_unit },
    { label: "所属行业", value: info.industry },
    { label: "企业地址", value: info.location, wide: true },
    { label: "园区面积", value: formatArea(info.park_area) },
    { label: "仓储面积", value: formatArea(info.store_area) },
    { label: "绿化面积", value: formatArea(info.green_area) },
    { label: "人员数量", value: formatCount(info.people_count) },
  ]

  return (
    <Card>
      <CardHeader className="border-border/70 border-b">
        <CardTitle>组织档案</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 sm:grid-cols-2">
          {fields.map((field) => (
            <InfoField key={field.label} label={field.label} value={field.value} wide={field.wide} />
          ))}
        </div>
      </CardContent>
    </Card>
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
