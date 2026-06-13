import { Hammer, ListChecks } from "lucide-react"

import { AdminPanel } from "@/components/admin-ui"
import { Badge } from "@/components/ui/badge"

export type UnderConstructionModuleProps = {
  guideTitle: string
  moduleType: "业务办理型" | "分析展示型" | "数据台账型" | "运营处置型"
  plannedTabs: string[]
  dataDependencies: string[]
  currentFoundation: string[]
  nextTodos: string[]
  status: "建设中" | "设计中" | "等待数据" | "待开发"
}

export function UnderConstructionModule({ guideTitle, moduleType, plannedTabs, dataDependencies, currentFoundation, nextTodos, status }: UnderConstructionModuleProps) {
  return (
    <AdminPanel
      title={
        <span className="flex items-center gap-2">
          <Hammer className="h-4 w-4 text-muted-foreground" />
          {guideTitle}
        </span>
      }
      actions={
        <>
          <Badge variant="secondary">{status}</Badge>
          <Badge variant="outline">{moduleType}</Badge>
        </>
      }
      contentClassName="grid gap-4 lg:grid-cols-2"
    >
      <ConstructionList title="页面范围" items={plannedTabs} />
      <ConstructionList title="依赖数据" items={dataDependencies} />
      <ConstructionList title="当前基础" items={currentFoundation} />
      <ConstructionList title="后续动作" items={nextTodos} tone="todo" />
    </AdminPanel>
  )
}

function ConstructionList({ title, items, tone = "default" }: { title: string; items: string[]; tone?: "default" | "todo" }) {
  return (
    <div className="rounded-lg border border-border/60 bg-card/60 p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-medium">
        <ListChecks className={tone === "todo" ? "h-4 w-4 text-primary" : "h-4 w-4 text-muted-foreground"} />
        {title}
      </div>
      <ul className="space-y-2 text-sm text-muted-foreground">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-muted-foreground/60" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
