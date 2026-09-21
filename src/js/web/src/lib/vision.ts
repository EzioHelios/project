import { useQuery } from "@tanstack/react-query"
import { useAuthStore } from "@/lib/auth"

export type RecognitionConfig = {
  enabled: boolean
  rtsp_url: string
  playback_path: string
  area_id: number | null
  equipment_id: number | null
  equipment_type: string
  equipment_name?: string
  area_name?: string
  task_ref: string
  operation_type: string
  material_code: string
  material_name: string
  batch_no: string
  quantity: number
  unit: string
  weight_kg: number | null
  exclusive_equipment: boolean
  demo_source: boolean
  confidence_threshold: number
  movement_threshold: number
  history_seconds: number
  idle_seconds: number
  lost_seconds: number
  min_duration_seconds: number
  revision: number
}

export type VisionCamera = {
  id: number
  name: string
  area_name?: string
  config: Partial<RecognitionConfig>
  state: { status?: string; received_at?: string; detected_count?: number; working_count?: number; frames_processed?: number; message?: string }
}

export type VisionObservation = {
  id: number
  camera_id: number
  started_at: string
  ended_at: string
  duration_seconds: number
  confidence: number
  end_reason: string
  status: string
  equipment_name?: string
  material_name?: string
  batch_no?: string
  task_ref?: string
  operation_id?: number
  has_evidence: boolean
  demo_source: boolean
}

export type VisionDashboard = {
  cameras: VisionCamera[]
  observations: VisionObservation[]
  summary: { observations: number; linked: number; pending: number; duration_minutes: number }
  hourly: { hour_utc: number; minutes: number }[]
}

export const visionStateLabels: Record<string, string> = {
  running: "识别中",
  offline: "连接中断",
  awaiting_worker: "等待接入",
  stopped: "已停止",
  disabled: "已停用",
  error: "识别异常",
}
export const observationLabels: Record<string, string> = { linked: "已关联作业", pending: "待确认", unassigned: "待关联", incomplete: "片段中断", task_completed: "任务已处理" }
export const operationLabels: Record<string, string> = { inbound_putaway: "入库上架", outbound_picking: "出库拣选", internal_transfer: "内部转运", loading_unloading: "装卸" }

export async function visionRequest<T>(path: string, init?: RequestInit, teamId = useAuthStore.getState().currentTeam?.id): Promise<T> {
  const headers = new Headers(init?.headers)
  if (teamId) headers.set("X-Team-Id", teamId)
  if (init?.body) headers.set("Content-Type", "application/json")
  const response = await fetch(path, { ...init, credentials: "include", headers })
  const body = await response.json()
  if (!response.ok) throw new Error(body.detail || body.msg || "请求失败")
  return body.items ? body : (body.data ?? body)
}

export function useVisionDashboard(cameraId?: number) {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return useQuery({
    queryKey: ["vision", teamId, cameraId],
    queryFn: ({ signal }) => visionRequest<VisionDashboard>(`/api/vision/dashboard${cameraId ? `?camera_id=${cameraId}` : ""}`, { signal }, teamId),
    enabled: Boolean(teamId),
    refetchInterval: 2000,
  })
}
