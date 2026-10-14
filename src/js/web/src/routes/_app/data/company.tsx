import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Pencil, Save } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { AdminEmptyState, AdminPageHeader, AdminPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { CarbonFormField } from "@/components/carbon/ghg-maintenance"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Textarea } from "@/components/ui/textarea"

type ApiResponse<T> = {
  code: number
  msg: string
  data: T
}

type EnterpriseInfo = {
  id?: number
  name?: string | null
  unify_code?: string | null
  belong_unit?: string | null
  industry?: string | null
  location?: string | null
  park_area?: string | number | null
  store_area?: string | number | null
  green_area?: string | number | null
  people_count?: string | number | null
  other_info?: Record<string, unknown> | null
}

const textFields = [
  ["name", "企业名称", 100],
  ["unify_code", "统一社会信用代码", 30],
  ["belong_unit", "所属单位", 100],
  ["industry", "所属行业", 30],
  ["location", "运营地址", 50],
  ["registered_address", "注册地址", 500],
  ["legal_representative", "法定代表人", 100],
  ["contact_name", "联系人", 100],
  ["contact_details", "联系方式", 300],
] as const
const numberFields = [
  ["people_count", "人员数量"],
  ["park_area", "园区面积（m²）"],
  ["store_area", "仓储面积（m²）"],
  ["green_area", "绿化面积（m²）"],
] as const
const proseFields = [
  ["organization_description", "组织概况"],
  ["process_description", "主要业务及作业过程"],
] as const

export const Route = createFileRoute("/_app/data/company")({
  component: CompanyPage,
})

function CompanyPage() {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<Record<string, string>>({})
  const { data, isLoading, isError } = useQuery<ApiResponse<EnterpriseInfo>>({
    queryKey: ["data", "company", "enterprise-info"],
    queryFn: async () => {
      const res = await fetch("/api/master-data/enterprise-profile")
      if (!res.ok) throw new Error("企业信息加载失败")
      return res.json()
    },
  })

  const info = data?.data ?? {}
  const save = useMutation({
    mutationFn: async () => {
      const body: Record<string, string | number | null> = { ...form }
      for (const [key] of numberFields) body[key] = form[key] ? Number(form[key]) : null
      const response = await fetch(`/api/master-data/enterprise-profile/${info.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || "保存失败")
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["data", "company"] })
      setEditing(false)
      toast.success("企业资料已保存")
    },
    onError: (error) => toast.error(error.message),
  })
  const edit = () => {
    const values: Record<string, unknown> = { ...info, ...info.other_info }
    setForm(Object.fromEntries([...textFields, ...numberFields, ...proseFields].map(([key]) => [key, String(values[key] ?? "")])))
    setEditing(true)
  }

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader
        title="企业基本信息"
        actions={
          <Button onClick={edit} disabled={!info.id}>
            <Pencil />
            编辑资料
          </Button>
        }
      />

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
      <Sheet open={editing} onOpenChange={setEditing}>
        <SheetContent className="overflow-y-auto sm:max-w-2xl">
          <SheetHeader>
            <SheetTitle>编辑企业资料</SheetTitle>
          </SheetHeader>
          <form
            className="grid gap-4 p-4"
            onSubmit={(event) => {
              event.preventDefault()
              save.mutate()
            }}
          >
            {textFields.map(([key, label, maxLength]) => (
              <CarbonFormField key={key} label={label}>
                <Input
                  aria-label={label}
                  value={form[key] ?? ""}
                  maxLength={maxLength}
                  required={key === "name"}
                  onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))}
                />
              </CarbonFormField>
            ))}
            {numberFields.map(([key, label]) => (
              <CarbonFormField key={key} label={label}>
                <Input
                  aria-label={label}
                  type="number"
                  min={0}
                  step={key === "people_count" ? 1 : "any"}
                  value={form[key] ?? ""}
                  onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))}
                />
              </CarbonFormField>
            ))}
            {proseFields.map(([key, label]) => (
              <CarbonFormField key={key} label={label}>
                <Textarea
                  aria-label={label}
                  rows={5}
                  maxLength={10000}
                  value={form[key] ?? ""}
                  onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))}
                />
              </CarbonFormField>
            ))}
            <Button type="submit" disabled={save.isPending || !form.name?.trim()}>
              <Save />
              {save.isPending ? "保存中" : "保存"}
            </Button>
          </form>
        </SheetContent>
      </Sheet>
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
    ...textFields.slice(5).map(([key, label]) => ({ label, value: String(info.other_info?.[key] ?? ""), wide: true })),
    ...proseFields.map(([key, label]) => ({ label, value: String(info.other_info?.[key] ?? ""), wide: true })),
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
