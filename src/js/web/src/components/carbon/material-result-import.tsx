import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { useAuthStore } from "@/lib/auth"
import { type HandlingRow, handlingRequest, handlingStates } from "@/lib/material-handling"

export function MaterialResultImport({ studyId, stages }: { studyId: number | null; stages: { id: number; stage_name: string }[] }) {
  const team = useAuthStore((s) => s.currentTeam?.id)
  const cache = useQueryClient()
  const [open, setOpen] = useState(false)
  const [resultId, setResultId] = useState("")
  const [stageId, setStageId] = useState("")
  const results = useQuery({
    queryKey: ["handling-pcf-results", team, studyId],
    queryFn: () => handlingRequest<{ items: HandlingRow[] }>(`/api/material-allocation/results?study_id=${studyId}&limit=200`),
    enabled: open && Boolean(studyId),
  })
  const selected = results.data?.items.find((r) => r.id === Number(resultId))
  const mutation = useMutation({
    mutationFn: (unlink: boolean) =>
      unlink
        ? handlingRequest(`/api/carbon/product-footprint/material-references/${selected?.product_footprint_item_id}`, "DELETE")
        : handlingRequest(`/api/carbon/product-footprint/studies/${studyId}/material-results`, "POST", { result_id: Number(resultId), stage_id: Number(stageId) }),
    onSuccess: () => {
      toast.success("引用已更新")
      setOpen(false)
      void cache.invalidateQueries()
    },
    onError: (e: Error) => toast.error(e.message),
  })
  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v)
        setResultId("")
        setStageId("")
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" disabled={!studyId}>
          引用物资作业
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>物资作业引用</DialogTitle>
        </DialogHeader>
        <Label htmlFor="handling-result">分配结果</Label>
        <select id="handling-result" className="h-9 rounded-md border bg-background px-3" value={resultId} onChange={(e) => setResultId(e.target.value)}>
          <option value="">请选择</option>
          {results.data?.items.map((r) => (
            <option value={r.id} key={r.id}>
              {r.material_name} / {r.batch_no} / {r.equipment_name} / {r.allocated_energy_kwh} kWh / {handlingStates[r.data_status]}
            </option>
          ))}
        </select>
        {results.isLoading && <p>加载中</p>}
        {results.isError && <p role="alert">{results.error.message}</p>}
        {results.isSuccess && !results.data.items.length && <p>当前研究物资暂无分配结果</p>}
        <Label htmlFor="handling-stage">生命周期阶段</Label>
        <select id="handling-stage" className="h-9 rounded-md border bg-background px-3" value={stageId} onChange={(e) => setStageId(e.target.value)}>
          <option value="">请选择</option>
          {stages.map((s) => (
            <option value={s.id} key={s.id}>
              {s.stage_name}
            </option>
          ))}
        </select>
        <div className="flex justify-end gap-2">
          {selected?.product_footprint_item_id && (
            <Button variant="outline" disabled={mutation.isPending} onClick={() => mutation.mutate(true)}>
              取消引用
            </Button>
          )}
          <Button disabled={!selected || selected.data_status !== "ready" || !stageId || mutation.isPending} onClick={() => mutation.mutate(false)}>
            {selected?.product_footprint_item_id ? "同步引用" : "引用"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
