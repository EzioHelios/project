import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import { DataCard } from "@/components/carbon/data-view"
import { Card, CardContent } from "@/components/ui/card"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"

type ApiResponse<T> = {
  code: number
  msg: string
  data: T
}

type EnterpriseInfo = Record<string, unknown>

export const Route = createFileRoute("/_app/data/company")({
  component: CompanyPage,
})

function CompanyPage() {
  const { data, isLoading, isError } = useQuery<ApiResponse<EnterpriseInfo>>({
    queryKey: ["data", "company", "enterprise-info"],
    queryFn: async () => {
      // 复用碳大屏的企业信息接口 /api/page1/ckxxgk
      const res = await fetch("/api/page1/ckxxgk")
      return res.json()
    },
  })

  const info = data?.data ?? {}

  return (
    <PageContainer className="flex-1 space-y-6">
      <PageHeader eyebrow="数据管理" title="企业基本信息" description="展示仓库企业基础档案信息，数据来源于 EnterpriseInfo 表（与原系统保持一致）。" />

      <PageSection>
        {isLoading && (
          <Card>
            <CardContent className="py-10 text-sm text-muted-foreground">正在加载企业信息，请稍候…</CardContent>
          </Card>
        )}

        {isError && (
          <Card>
            <CardContent className="py-10 text-sm text-destructive">企业信息加载失败，请检查后端接口 /api/page1/ckxxgk 是否可用。</CardContent>
          </Card>
        )}

        {!isLoading && !isError && <DataCard title="企业信息详情" data={info} prefer="kv" rawTitle="原始返回值（ckxxgk）" />}
      </PageSection>
    </PageContainer>
  )
}
