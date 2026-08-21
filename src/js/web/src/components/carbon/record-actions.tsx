import type { QueryKey } from "@tanstack/react-query"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import type { CarbonStatus } from "@/components/carbon/status-badge"
import { Button } from "@/components/ui/button"

type Action = "submit" | "approve" | "reject" | "delete"

interface CarbonRecordActionsProps {
  id: number
  status?: CarbonStatus
  basePath: string
  invalidateKey: QueryKey
}

async function callAction(basePath: string, id: number, action: Action) {
  if (action === "delete") {
    const res = await fetch(`${basePath}/${id}`, { method: "DELETE" })
    let json: any = null
    try {
      json = await res.json()
    } catch {
      // 后端可能返回的是纯文本错误（例如 Traceback），避免 JSON 解析异常把原始错误吞掉
    }
    if (!res.ok || (json?.code && json.code !== 200 && json.code !== 0)) {
      throw new Error(json?.msg || `删除失败 (HTTP ${res.status})`)
    }
    return
  }
  const res = await fetch(`${basePath}/${id}/${action}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: action === "reject" ? JSON.stringify({ reason: "不符合审核要求" }) : undefined,
  })
  let json: any = null
  try {
    json = await res.json()
  } catch {
    // 后端异常时可能返回纯文本 Traceback，这里避免 JSON 解析错误导致误报
  }
  if (!res.ok || (json?.code && json.code !== 200 && json.code !== 0)) {
    throw new Error(json?.msg || `操作失败 (HTTP ${res.status})`)
  }
}

export function CarbonRecordActions({ id, status, basePath, invalidateKey }: CarbonRecordActionsProps) {
  const qc = useQueryClient()
  const mut = useMutation({
    mutationFn: async (action: Action) => callAction(basePath, id, action),
    onSuccess: async () => {
      toast.success("操作成功")
      await qc.invalidateQueries({ queryKey: invalidateKey })
    },
    onError: (e) => toast.error("操作失败", { description: e instanceof Error ? e.message : "请稍后重试" }),
  })

  const st = status ?? "draft"

  return (
    <div className="flex flex-wrap justify-end gap-2">
      <Button variant="outline" size="sm" onClick={() => mut.mutate("submit")} disabled={st !== "draft" || mut.isPending}>
        送审
      </Button>
      <Button variant="outline" size="sm" onClick={() => mut.mutate("approve")} disabled={st !== "pending" || mut.isPending}>
        通过
      </Button>
      <Button variant="outline" size="sm" onClick={() => mut.mutate("reject")} disabled={st !== "pending" || mut.isPending}>
        驳回
      </Button>
      <Button variant="destructive" size="sm" onClick={() => mut.mutate("delete")} disabled={st === "approved" || mut.isPending}>
        删除
      </Button>
    </div>
  )
}
