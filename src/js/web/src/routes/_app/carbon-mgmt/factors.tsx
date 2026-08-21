/**
 * 官方排放因子库
 * APIs:
 * - /api/carbon/factor-library/overview
 * - /api/carbon/factor-library/category-tree
 * - /api/carbon/factor-library/records
 */
import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ChevronRight } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { AdminDataTable, AdminPageHeader, AdminPanel, AdminTableStateRow, AdminTableToolbar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { getConversionStatusLabel } from "@/lib/carbon-factor-labels"
import { cn } from "@/lib/utils"

type ImportBatch = {
  snapshot_id: string
  source_system: string
  checksum_verified: boolean
  xlsx_count: number
}

type FactorOverview = {
  batch: ImportBatch | null
  library_count: number
  category_count: number
  leaf_category_count: number
  raw_record_count: number
}

type CategoryNode = {
  id: number
  source_category_id: string
  parent_source_category_id?: string | null
  category_code?: string | null
  library_year?: string | null
  library_code?: string | null
  category_name: string
  category_path: string
  depth: number
  is_leaf: boolean
  children: CategoryNode[]
}

type CategoryGroup = {
  library_year?: string | null
  library_code?: string | null
  library_name: string
  institution?: string | null
  category_count?: number
  children: CategoryNode[]
}

type RawFactorRecord = {
  id: number
  snapshot_id: string
  library_year?: string | null
  library_code?: string | null
  library_name?: string | null
  category_path: string
  factor_name: string
  display_factor_name?: string | null
  factor_value_raw?: string | null
  factor_unit_raw?: string | null
  display_factor_unit_raw?: string | null
  region_raw?: string | null
  gas_raw?: string | null
  provider?: string | null
  projection_status: "candidate" | "raw_only" | string
  raw_payload?: unknown
}

type RawRecordsPage = {
  items: RawFactorRecord[]
  total: number
  limit: number
  offset: number
}

type ApiResponse<T> = { code: number; msg?: string; data: T }

export const Route = createFileRoute("/_app/carbon-mgmt/factors")({
  component: FactorsPage,
})

function formatNumber(value: number | undefined) {
  return Number(value ?? 0).toLocaleString("zh-CN")
}

function libraryKey(group: CategoryGroup) {
  return `${group.library_year ?? ""}::${group.library_code ?? ""}`
}

function splitLibraryKey(key: string) {
  const [libraryYear, libraryCode] = key.split("::")
  return { libraryYear, libraryCode }
}

function statusBadge(status?: string | null) {
  if (!status) return <Badge variant="outline">未标记</Badge>
  return <Badge variant={status === "candidate" ? "default" : "secondary"}>{getConversionStatusLabel(status)}</Badge>
}

function FactorsPage() {
  const [keyword, setKeyword] = useState("")
  const [projectionStatus, setProjectionStatus] = useState("all")
  const [selectedLibraryKey, setSelectedLibraryKey] = useState("")
  const [selectedCategory, setSelectedCategory] = useState<CategoryNode | null>(null)
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())
  const [offset, setOffset] = useState(0)
  const [selectedRecord, setSelectedRecord] = useState<RawFactorRecord | null>(null)

  const overviewQuery = useQuery<ApiResponse<FactorOverview>>({
    queryKey: ["carbon-mgmt", "factor-library", "overview"],
    queryFn: async () => (await fetch("/api/carbon/factor-library/overview")).json(),
  })

  const categoryTreeQuery = useQuery<ApiResponse<{ groups: CategoryGroup[] } | CategoryGroup[]>>({
    queryKey: ["carbon-mgmt", "factor-library", "category-tree"],
    queryFn: async () => (await fetch("/api/carbon/factor-library/category-tree")).json(),
  })

  const treeData = categoryTreeQuery.data?.data
  const groups = Array.isArray(treeData) ? treeData : (treeData?.groups ?? [])
  const selectedGroup = useMemo(() => groups.find((group) => libraryKey(group) === selectedLibraryKey) ?? groups[0], [groups, selectedLibraryKey])
  const selectedLibrary = selectedGroup ? splitLibraryKey(libraryKey(selectedGroup)) : { libraryYear: "", libraryCode: "" }

  useEffect(() => {
    if (!selectedLibraryKey && groups.length > 0) {
      setSelectedLibraryKey(libraryKey(groups[0]))
    }
  }, [groups, selectedLibraryKey])

  useEffect(() => {
    setSelectedCategory(null)
    setOffset(0)
    setExpandedIds(new Set((selectedGroup?.children ?? []).map((node) => node.source_category_id)))
  }, [selectedGroup])

  const recordsQuery = useQuery<ApiResponse<RawRecordsPage>>({
    queryKey: ["carbon-mgmt", "factor-library", "records", keyword, projectionStatus, selectedLibraryKey, selectedCategory?.category_path, offset],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (keyword.trim()) params.set("keyword", keyword.trim())
      if (projectionStatus !== "all") params.set("projection_status", projectionStatus)
      if (selectedLibrary.libraryYear) params.set("library_year", selectedLibrary.libraryYear)
      if (selectedLibrary.libraryCode) params.set("library_code", selectedLibrary.libraryCode)
      if (selectedCategory?.category_path) params.set("category_path_prefix", selectedCategory.category_path)
      params.set("limit", "50")
      params.set("offset", String(offset))
      return (await fetch(`/api/carbon/factor-library/records?${params.toString()}`)).json()
    },
    enabled: Boolean(selectedGroup),
  })

  const overview = overviewQuery.data?.data
  const batch = overview?.batch
  const recordsPage = recordsQuery.data?.data
  const records = recordsPage?.items ?? []
  const canGoPrev = offset > 0
  const canGoNext = (recordsPage?.total ?? 0) > offset + (recordsPage?.limit ?? 50)

  function resetFilters() {
    setKeyword("")
    setProjectionStatus("all")
    setSelectedCategory(null)
    setOffset(0)
  }

  function toggleNode(node: CategoryNode) {
    setExpandedIds((current) => {
      const next = new Set(current)
      if (next.has(node.source_category_id)) next.delete(node.source_category_id)
      else next.add(node.source_category_id)
      return next
    })
  }

  function selectCategory(node: CategoryNode) {
    setSelectedCategory(node)
    setOffset(0)
    if (node.children.length > 0) {
      setExpandedIds((current) => new Set(current).add(node.source_category_id))
    }
  }

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="排放因子库" />

      <PageSection>
        <MetricStrip className="xl:grid-cols-4">
          <MetricTile label="官方库" value={formatNumber(overview?.library_count)} meta={batch?.source_system ?? "未导入"} />
          <MetricTile label="分类节点" value={formatNumber(overview?.category_count)} meta={`${formatNumber(overview?.leaf_category_count)} 个叶子分类`} />
          <MetricTile label="原始记录" value={formatNumber(overview?.raw_record_count)} meta={`${formatNumber(batch?.xlsx_count)} 个审阅文件`} />
          <MetricTile label="校验状态" value={batch?.checksum_verified ? "通过" : "待校验"} meta={batch?.snapshot_id ?? "-"} />
        </MetricStrip>
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
        <AdminPanel
          title="分类树"
          className="xl:sticky xl:top-20 xl:self-start"
          actions={
            <Select
              value={selectedLibraryKey}
              onValueChange={(value) => {
                setSelectedLibraryKey(value)
                setOffset(0)
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择因子库" />
              </SelectTrigger>
              <SelectContent>
                {groups.map((group) => (
                  <SelectItem key={libraryKey(group)} value={libraryKey(group)}>
                    {group.library_year} {group.library_code} {group.library_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          }
          contentClassName="space-y-3"
        >
          {categoryTreeQuery.isLoading && <div className="text-muted-foreground text-sm">正在加载分类...</div>}
          {categoryTreeQuery.isError && <div className="text-destructive text-sm">分类加载失败。</div>}
          {!categoryTreeQuery.isLoading && !categoryTreeQuery.isError && (
            <div className="max-h-[640px] overflow-y-auto pr-1">
              <button
                type="button"
                onClick={() => {
                  setSelectedCategory(null)
                  setOffset(0)
                }}
                className={cn(
                  "mb-1 flex w-full items-center rounded-md px-2 py-2 text-left text-sm transition-colors hover:bg-accent",
                  !selectedCategory && "bg-primary/10 font-medium text-primary",
                )}
              >
                全部分类
              </button>
              {(selectedGroup?.children ?? []).map((node) => (
                <CategoryTreeNode
                  key={node.source_category_id}
                  node={node}
                  expandedIds={expandedIds}
                  selectedPath={selectedCategory?.category_path ?? null}
                  onToggle={toggleNode}
                  onSelect={selectCategory}
                />
              ))}
            </div>
          )}
        </AdminPanel>

        <AdminPanel
          title="官方原始因子"
          actions={
            <Button variant="outline" size="sm" onClick={resetFilters}>
              重置
            </Button>
          }
          className="min-w-0"
          contentClassName="space-y-4"
        >
          <div className="text-muted-foreground text-sm">
            {selectedCategory ? selectedCategory.category_path : "全部分类"} · 共 {formatNumber(recordsPage?.total)} 条
          </div>
          <AdminTableToolbar
            fields={[
              {
                key: "keyword",
                node: (
                  <Input
                    value={keyword}
                    onChange={(event) => {
                      setKeyword(event.target.value)
                      setOffset(0)
                    }}
                    placeholder="搜索：因子名称/分类/单位/发布方"
                  />
                ),
              },
              {
                key: "projectionStatus",
                node: (
                  <Select
                    value={projectionStatus}
                    onValueChange={(value) => {
                      setProjectionStatus(value)
                      setOffset(0)
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="转换状态" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">全部状态</SelectItem>
                      <SelectItem value="candidate">可转换</SelectItem>
                      <SelectItem value="raw_only">仅原始保留</SelectItem>
                    </SelectContent>
                  </Select>
                ),
              },
            ]}
            className="rounded-md border border-border/70 bg-muted/20"
          />
          {recordsQuery.isLoading && <div className="text-muted-foreground text-sm">正在加载...</div>}
          {recordsQuery.isError && <div className="text-destructive text-sm">数据加载失败，请稍后重试。</div>}
          {!recordsQuery.isLoading && !recordsQuery.isError && (
            <AdminDataTable className="rounded-none border-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>分类</TableHead>
                    <TableHead>因子名称</TableHead>
                    <TableHead className="text-right">原始值</TableHead>
                    <TableHead>单位</TableHead>
                    <TableHead>气体</TableHead>
                    <TableHead>地区</TableHead>
                    <TableHead>发布方</TableHead>
                    <TableHead>转换状态</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {records.length === 0 && <AdminTableStateRow colSpan={9}>暂无数据</AdminTableStateRow>}
                  {records.map((record) => (
                    <TableRow key={record.id}>
                      <TableCell className="max-w-[260px] truncate">{record.category_path}</TableCell>
                      <TableCell className="max-w-[360px] truncate font-medium">{record.display_factor_name ?? record.factor_name}</TableCell>
                      <TableCell className="text-right">{record.factor_value_raw ?? "-"}</TableCell>
                      <TableCell className="whitespace-nowrap">{record.display_factor_unit_raw ?? record.factor_unit_raw ?? "-"}</TableCell>
                      <TableCell>{record.gas_raw ?? "-"}</TableCell>
                      <TableCell>{record.region_raw ?? "-"}</TableCell>
                      <TableCell className="max-w-[160px] truncate">{record.provider ?? "-"}</TableCell>
                      <TableCell>{statusBadge(record.projection_status)}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="outline" size="sm" onClick={() => setSelectedRecord(record)}>
                          查看
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </AdminDataTable>
          )}
          <div className="flex items-center justify-between gap-3">
            <div className="text-muted-foreground text-sm">
              {recordsPage?.total ? `${formatNumber(offset + 1)} - ${formatNumber(Math.min(offset + (recordsPage?.limit ?? 50), recordsPage.total))}` : "0 - 0"}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={!canGoPrev} onClick={() => setOffset(Math.max(0, offset - 50))}>
                上一页
              </Button>
              <Button variant="outline" size="sm" disabled={!canGoNext} onClick={() => setOffset(offset + 50)}>
                下一页
              </Button>
            </div>
          </div>
        </AdminPanel>
      </PageSection>

      <RecordDetailSheet record={selectedRecord} onOpenChange={(open) => !open && setSelectedRecord(null)} />
    </PageContainer>
  )
}

function CategoryTreeNode({
  node,
  expandedIds,
  selectedPath,
  onToggle,
  onSelect,
}: {
  node: CategoryNode
  expandedIds: Set<string>
  selectedPath: string | null
  onToggle: (node: CategoryNode) => void
  onSelect: (node: CategoryNode) => void
}) {
  const hasChildren = node.children.length > 0
  const expanded = expandedIds.has(node.source_category_id)
  const selected = selectedPath === node.category_path

  return (
    <div>
      <div
        className={cn("flex items-center rounded-md text-sm transition-colors hover:bg-accent", selected && "bg-primary/10 font-medium text-primary")}
        style={{ paddingLeft: `${Math.min(node.depth, 5) * 14}px` }}
      >
        <button
          type="button"
          className="flex size-7 items-center justify-center text-muted-foreground"
          onClick={() => hasChildren && onToggle(node)}
          aria-label={expanded ? "收起分类" : "展开分类"}
        >
          {hasChildren && <ChevronRight className={cn("size-4 transition-transform", expanded && "rotate-90")} />}
        </button>
        <button type="button" className="min-w-0 flex-1 truncate py-2 text-left" title={node.category_path} onClick={() => onSelect(node)}>
          {node.category_code ? `${node.category_code} ` : ""}
          {node.category_name}
        </button>
        {node.is_leaf && <span className="mr-2 size-1.5 rounded-full bg-muted-foreground/40" />}
      </div>
      {hasChildren && expanded && (
        <div>
          {node.children.map((child) => (
            <CategoryTreeNode key={child.source_category_id} node={child} expandedIds={expandedIds} selectedPath={selectedPath} onToggle={onToggle} onSelect={onSelect} />
          ))}
        </div>
      )}
    </div>
  )
}

function RecordDetailSheet({ record, onOpenChange }: { record: RawFactorRecord | null; onOpenChange: (open: boolean) => void }) {
  return (
    <Sheet open={Boolean(record)} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>因子追溯</SheetTitle>
        </SheetHeader>
        {record && (
          <div className="space-y-4 px-4 pb-4">
            <div className="grid gap-3 rounded-md border border-border/70 p-4 text-sm">
              <DetailRow label="批次" value={record.snapshot_id ?? "-"} />
              <DetailRow label="库" value={`${record.library_year ?? "-"} ${record.library_code ?? ""} ${record.library_name ?? ""}`} />
              <DetailRow label="分类" value={record.category_path} />
              <DetailRow label="名称" value={record.display_factor_name ?? record.factor_name} />
              <DetailRow label="原始值" value={record.factor_value_raw ?? "-"} />
              <DetailRow label="单位" value={record.display_factor_unit_raw ?? record.factor_unit_raw ?? "-"} />
              <DetailRow label="地区" value={record.region_raw ?? "-"} />
              <DetailRow label="气体" value={record.gas_raw ?? "-"} />
              <DetailRow label="发布方" value={record.provider ?? "-"} />
            </div>
            <RawPayloadTable payload={record.raw_payload} />
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

function RawPayloadTable({ payload }: { payload: unknown }) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return null
  const entries = Object.entries(payload).sort(([a], [b]) => a.localeCompare(b))
  if (entries.length === 0) return null

  return (
    <AdminPanel title="原始字段" contentClassName="p-0">
      <AdminDataTable className="rounded-none border-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>字段</TableHead>
              <TableHead>值</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map(([key, value]) => (
              <TableRow key={key}>
                <TableCell className="text-muted-foreground">{key}</TableCell>
                <TableCell className="break-words font-medium">{formatPayloadValue(value)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </AdminDataTable>
    </AdminPanel>
  )
}

function formatPayloadValue(value: unknown): string {
  if (value === null || value === undefined) return "-"
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString("zh-CN") : String(value)
  if (typeof value === "boolean") return value ? "是" : "否"
  if (typeof value === "string") return value
  if (Array.isArray(value)) return value.map(formatPayloadValue).join("、")
  if (typeof value === "object")
    return Object.entries(value)
      .map(([key, nested]) => `${key}: ${formatPayloadValue(nested)}`)
      .join("；")
  return String(value)
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-2 sm:grid-cols-[90px_1fr]">
      <div className="text-muted-foreground">{label}</div>
      <div className="break-words font-medium">{value}</div>
    </div>
  )
}
