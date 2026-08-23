import { createFileRoute } from "@tanstack/react-router"
import { ExternalLink, RefreshCw } from "lucide-react"
import { useState } from "react"

import { AdminFilterBar, AdminPageScaffold, AdminPanel, MetricStrip, MetricTile, StatusBadge } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useReductionMethodologies } from "@/lib/api/hooks/decarbonization"
import type { ReductionMethodologyResponse } from "@/lib/generated/api"

export const Route = createFileRoute("/_app/carbon/reduction/methodologies")({ component: ReductionMethodologiesPage })

function ReductionMethodologiesPage() {
  const [keyword, setKeyword] = useState("")
  const [sector, setSector] = useState("all")
  const [capability, setCapability] = useState("all")
  const [selected, setSelected] = useState<ReductionMethodologyResponse | null>(null)
  const methods = useReductionMethodologies({
    keyword: keyword || undefined,
    sector: sector === "all" ? undefined : sector,
    executable: capability === "all" ? undefined : capability === "executable",
  })
  const items = methods.data?.items ?? []
  const sectors = [...new Set(items.map((item) => item.sector))]

  return (
    <AdminPageScaffold
      title="方法学与CCER"
      filters={
        <AdminFilterBar
          fields={[
            { key: "search", node: <Input aria-label="搜索方法学" placeholder="编号或方法学名称" value={keyword} onChange={(event) => setKeyword(event.target.value)} /> },
            {
              key: "sector",
              node: (
                <Select value={sector} onValueChange={setSector}>
                  <SelectTrigger aria-label="行业领域">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部行业</SelectItem>
                    {sectors.map((value) => (
                      <SelectItem key={value} value={value}>
                        {value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ),
            },
            {
              key: "capability",
              node: (
                <Select value={capability} onValueChange={setCapability}>
                  <SelectTrigger aria-label="计算能力">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部能力</SelectItem>
                    <SelectItem value="executable">可执行计算</SelectItem>
                    <SelectItem value="reference">目录参考</SelectItem>
                  </SelectContent>
                </Select>
              ),
            },
          ]}
          actions={
            <Button variant="outline" size="sm" onClick={() => void methods.refetch()}>
              <RefreshCw className="h-4 w-4" />
              刷新
            </Button>
          }
        />
      }
      metrics={
        <MetricStrip>
          <MetricTile label="现行CCER方法学" value={items.filter((item) => item.methodKind === "ccer").length} unit="项" tone="domain" />
          <MetricTile label="可执行适配器" value={items.filter((item) => item.executable).length} unit="项" />
          <MetricTile label="覆盖领域" value={new Set(items.map((item) => item.sector)).size} unit="类" />
          <MetricTile label="版本有效" value={items.filter((item) => item.status === "published").length} unit="项" tone="success" />
        </MetricStrip>
      }
    >
      <AdminPanel contentClassName="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>编号</TableHead>
              <TableHead>方法学名称</TableHead>
              <TableHead>领域</TableHead>
              <TableHead>版本</TableHead>
              <TableHead>发布日期</TableHead>
              <TableHead>计算能力</TableHead>
              <TableHead>状态</TableHead>
              <TableHead className="w-20" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="font-medium tabular-nums">{item.code}</TableCell>
                <TableCell>{item.name}</TableCell>
                <TableCell>{item.sector}</TableCell>
                <TableCell>{item.version}</TableCell>
                <TableCell className="tabular-nums">{item.publishedOn ?? "-"}</TableCell>
                <TableCell>{item.executable ? <StatusBadge status="approved" label="可执行" /> : <StatusBadge status="inactive" label="目录参考" />}</TableCell>
                <TableCell>
                  <StatusBadge status={item.status === "published" ? "approved" : "archived"} label={item.status === "published" ? "现行" : "历史"} />
                </TableCell>
                <TableCell>
                  <Button variant="ghost" size="sm" onClick={() => setSelected(item)}>
                    查看
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </AdminPanel>

      <Sheet open={Boolean(selected)} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
          <SheetHeader>
            <SheetTitle>
              {selected?.code} {selected?.name}
            </SheetTitle>
            <SheetDescription>
              {selected?.sector} · {selected?.version}
            </SheetDescription>
          </SheetHeader>
          {selected && (
            <div className="grid gap-5 px-4 pb-6">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-muted-foreground text-xs">生效日期</div>
                  <div className="mt-1">{selected.effectiveFrom ?? "-"}</div>
                </div>
                <div>
                  <div className="text-muted-foreground text-xs">方法类型</div>
                  <div className="mt-1">{selected.methodKind === "ccer" ? "国家CCER方法学" : "企业内部方法"}</div>
                </div>
              </div>
              <MethodSection title="适用性条件" items={selected.applicabilitySchema.map((item) => String(item.label ?? item.code ?? "适用条件"))} />
              <MethodSection
                title="输入参数"
                items={selected.parameterSchema.map((item) => `${String(item.name ?? item.label ?? item.code ?? "参数")} · ${String(item.unit ?? "-")}`)}
              />
              <MethodSection title="监测要求" items={selected.monitoringSchema} />
              <MethodSection title="证据清单" items={selected.evidenceSchema} />
              <Button asChild variant="outline">
                <a href={selected.sourceUrl} target="_blank" rel="noreferrer">
                  <ExternalLink className="h-4 w-4" />
                  查看正式来源
                </a>
              </Button>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </AdminPageScaffold>
  )
}

function MethodSection({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="mb-2 font-medium text-sm">{title}</h3>
      <div className="divide-y rounded-md border">
        {items.length ? (
          items.map((item) => (
            <div className="px-3 py-2 text-sm" key={item}>
              {item}
            </div>
          ))
        ) : (
          <div className="px-3 py-3 text-muted-foreground text-sm">无专项要求</div>
        )}
      </div>
    </div>
  )
}
