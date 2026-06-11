import { createFileRoute } from "@tanstack/react-router"

import { UnderConstructionModule } from "@/components/carbon/under-construction-module"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/benchmark")({
  component: EnergyBenchmarkPage,
})

function EnergyBenchmarkPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="能源管理" title="能效对标" description="对标历史基线、行业标杆和设备工序水平，用于形成评价结论和整改建议。" />
      <UnderConstructionModule
        guideTitle="能效对标"
        moduleType="分析展示型"
        plannedTabs={["历史基线", "行业标杆", "设备/工序对标", "对标结论", "整改建议"]}
        dataDependencies={["能源消费量和强度计算结果", "设备台账", "工序或区域边界", "行业标杆库"]}
        currentFoundation={["已有能源消费量趋势", "已有区域用能排行", "已有设备/电表底座"]}
        nextTodos={["补充行业标杆数据", "建立设备和工序对标维度", "生成对标结论和整改建议"]}
        status="建设中"
      />
    </PageContainer>
  )
}
