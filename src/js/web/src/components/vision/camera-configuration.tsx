import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { useAuthStore } from "@/lib/auth"
import { type HandlingOptions, handlingRequest } from "@/lib/material-handling"
import { operationLabels, type RecognitionConfig, visionRequest } from "@/lib/vision"

type Option = { id: number; name: string; code: string; sector_id?: number }
const editableKeys = [
  "enabled",
  "rtsp_url",
  "playback_path",
  "area_id",
  "equipment_id",
  "equipment_type",
  "task_ref",
  "operation_type",
  "material_code",
  "material_name",
  "batch_no",
  "quantity",
  "unit",
  "weight_kg",
  "exclusive_equipment",
  "demo_source",
  "confidence_threshold",
  "movement_threshold",
  "history_seconds",
  "idle_seconds",
  "lost_seconds",
  "min_duration_seconds",
  "revision",
]
const selectClass = "h-9 w-full rounded-md border bg-background px-3 text-sm"

export function CameraConfiguration({ cameraId, onClose }: { cameraId: number | null; onClose: () => void }) {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  const cache = useQueryClient()
  const [form, setForm] = useState<RecognitionConfig | null>(null)
  const query = useQuery({
    queryKey: ["vision-config", teamId, cameraId],
    queryFn: () => visionRequest<RecognitionConfig>(`/api/vision/cameras/${cameraId}/config`),
    enabled: cameraId !== null,
  })
  const devices = useQuery({
    queryKey: ["vision-devices", teamId],
    queryFn: () => visionRequest<{ items: Option[] }>("/api/master-data/devices?limit=500"),
    enabled: cameraId !== null,
  })
  const areas = useQuery({ queryKey: ["vision-areas", teamId], queryFn: () => visionRequest<{ items: Option[] }>("/api/master-data/areas?limit=500"), enabled: cameraId !== null })
  const materials = useQuery({
    queryKey: ["handling-options", teamId],
    queryFn: () => handlingRequest<HandlingOptions>("/api/material-allocation/options"),
    enabled: cameraId !== null,
  })
  useEffect(() => {
    setForm(query.data ?? null)
  }, [query.data])
  const save = useMutation({
    mutationFn: () =>
      visionRequest(`/api/vision/cameras/${cameraId}/config`, {
        method: "PUT",
        body: JSON.stringify(Object.fromEntries(Object.entries(form ?? {}).filter(([key]) => editableKeys.includes(key)))),
      }),
    onSuccess: () => {
      toast.success("识别配置已保存")
      void cache.invalidateQueries({ queryKey: ["vision"] })
      void cache.invalidateQueries({ queryKey: ["vision-config"] })
      onClose()
    },
    onError: (error: Error) => toast.error(error.message),
  })
  const change = <K extends keyof RecognitionConfig>(key: K, value: RecognitionConfig[K]) => setForm((current) => (current ? { ...current, [key]: value } : current))
  const field = (key: keyof RecognitionConfig, label: string, type = "text", step?: string) => (
    <div className="space-y-2" key={key}>
      <Label htmlFor={`vision-${key}`}>{label}</Label>
      <Input
        id={`vision-${key}`}
        type={type}
        step={step}
        value={String(form?.[key] ?? "")}
        onChange={(event) => change(key, type === "number" ? (event.target.value === "" ? null : Number(event.target.value)) : event.target.value)}
      />
    </div>
  )
  return (
    <Sheet
      open={cameraId !== null}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>摄像头识别配置</SheetTitle>
        </SheetHeader>
        {query.isError ? (
          <div role="alert" className="p-4">
            {query.error.message}
            <Button variant="outline" onClick={() => void query.refetch()}>
              重试
            </Button>
          </div>
        ) : null}
        {form ? (
          <form
            className="space-y-6 p-4"
            onSubmit={(event) => {
              event.preventDefault()
              save.mutate()
            }}
          >
            <fieldset className="space-y-4">
              <legend className="mb-3 font-semibold">视频接入</legend>
              {field("rtsp_url", "RTSP 视频源")}
              {field("playback_path", "流媒体播放通道")}
            </fieldset>
            <fieldset className="space-y-4">
              <legend className="mb-3 font-semibold">视频识别</legend>
              <div className="flex gap-6">
                {(
                  [
                    ["enabled", "启用识别"],
                    ["demo_source", "演示视频"],
                  ] as const
                ).map(([key, label]) => (
                  <label className="flex items-center gap-2 text-sm" key={key}>
                    <input type="checkbox" checked={form[key]} onChange={(event) => change(key, event.target.checked)} />
                    {label}
                  </label>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-4">
                {field("confidence_threshold", "检测置信度", "number", "0.05")}
                {field("movement_threshold", "位移阈值（640像素画面）", "number", "1")}
                {field("history_seconds", "观察窗口（秒）", "number", "0.1")}
                {field("idle_seconds", "静止结束时长（秒）", "number", "0.1")}
                {field("lost_seconds", "目标丢失时长（秒）", "number", "0.1")}
                {field("min_duration_seconds", "最短片段（秒）", "number", "0.1")}
              </div>
            </fieldset>
            <fieldset className="space-y-4 border-t pt-4">
              <legend className="font-semibold">设备与区域</legend>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="vision-area">作业区域</Label>
                  <select
                    id="vision-area"
                    className={selectClass}
                    value={form.area_id ?? ""}
                    onChange={(event) => setForm({ ...form, area_id: event.target.value ? Number(event.target.value) : null, equipment_id: null })}
                  >
                    <option value="">请选择</option>
                    {areas.data?.items.map((item) => (
                      <option value={item.id} key={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="vision-device">关联设备</Label>
                  <select
                    id="vision-device"
                    className={selectClass}
                    value={form.equipment_id ?? ""}
                    onChange={(event) => change("equipment_id", event.target.value ? Number(event.target.value) : null)}
                  >
                    <option value="">请选择</option>
                    {devices.data?.items
                      .filter((item) => !form.area_id || item.sector_id === form.area_id)
                      .map((item) => (
                        <option value={item.id} key={item.id}>
                          {item.name}
                        </option>
                      ))}
                  </select>
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.exclusive_equipment} onChange={(event) => change("exclusive_equipment", event.target.checked)} />
                该监控范围仅关联所选设备
              </label>
              {devices.isError || areas.isError ? (
                <p role="alert" className="text-destructive">
                  设备或区域加载失败，请重新打开配置。
                </p>
              ) : null}
            </fieldset>
            <fieldset className="space-y-4 border-t pt-4">
              <legend className="font-semibold">当前物资任务</legend>
              <div className="grid grid-cols-2 gap-4">
                {field("task_ref", "任务编号")}
                <div className="space-y-2">
                  <Label htmlFor="vision-operation">作业类型</Label>
                  <select id="vision-operation" className={selectClass} value={form.operation_type} onChange={(event) => change("operation_type", event.target.value)}>
                    {Object.entries(operationLabels).map(([value, label]) => (
                      <option value={value} key={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="vision-material">物资</Label>
                  <select
                    id="vision-material"
                    className={selectClass}
                    value={form.material_code ?? ""}
                    onChange={(event) => {
                      const material = materials.data?.materials.find((m) => m.code === event.target.value)
                      setForm({ ...form, material_code: material?.code ?? "", material_name: material?.name ?? "", unit: material?.default_unit ?? "" })
                    }}
                  >
                    <option value="">请选择</option>
                    {materials.data?.materials.map((m) => (
                      <option key={m.id} value={m.code}>
                        {m.name} ({m.default_unit})
                      </option>
                    ))}
                  </select>
                </div>
                {field("batch_no", "物资批次")}
                {field("quantity", "任务数量", "number", "0.001")}
                <div className="space-y-2">
                  <Label htmlFor="vision-unit">计量单位</Label>
                  <Input id="vision-unit" readOnly value={form.unit ?? ""} />
                </div>
                {field("weight_kg", "任务重量（kg）", "number", "0.001")}
              </div>
            </fieldset>
            <div className="flex justify-end gap-2 border-t pt-4">
              <Button variant="outline" type="button" onClick={onClose}>
                取消
              </Button>
              <Button type="submit" disabled={save.isPending}>
                {save.isPending ? "保存中…" : "保存配置"}
              </Button>
            </div>
          </form>
        ) : !query.isError ? (
          <div className="p-4 text-muted-foreground">正在加载配置…</div>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
