import { createFileRoute } from "@tanstack/react-router"

import { UnderConstructionModule } from "@/components/carbon/under-construction-module"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/carbon/product-footprint")({
  component: ProductFootprintPage,
})

function ProductFootprintPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="碳排放管理" title="产品碳足迹核算" description="围绕产品、BOM、工序、生命周期边界和报告生成建设产品碳足迹核算能力。" />
      <UnderConstructionModule
        guideTitle="产品碳足迹核算"
        moduleType="业务办理型"
        plannedTabs={["产品清单", "BOM/工序", "生命周期边界", "活动数据", "核算结果", "报告生成"]}
        dataDependencies={["产品档案", "BOM 和工序", "能源与物料台账", "排放因子库", "运输和废弃物记录"]}
        currentFoundation={["已有排放因子库", "已有入库/出库台账", "已有外购运输活动数据"]}
        nextTodos={["建立产品和工序模型", "补充生命周期边界配置", "实现产品级核算结果和报告模板"]}
        status="建设中"
      />
    </PageContainer>
  )
}
