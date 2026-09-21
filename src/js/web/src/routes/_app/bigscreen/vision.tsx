import { useMutation, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Check, Settings, X } from "lucide-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"
import { BigscreenBarChart } from "@/components/bigscreen/charts"
import { BigscreenDataState } from "@/components/bigscreen/data-state"
import { BigscreenPanel } from "@/components/bigscreen/panel"
import { LiveVideo } from "@/components/vision/live-video"
import { RecognitionImage } from "@/components/vision/recognition-image"
import { useAuthStore } from "@/lib/auth"
import { observationLabels, operationLabels, useVisionDashboard, visionRequest, visionStateLabels } from "@/lib/vision"
import "@/components/vision/vision.css"

export const Route = createFileRoute("/_app/bigscreen/vision")({ component: VisionPage })

function VisionPage() {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return <VisionContent key={teamId} />
}

function VisionContent() {
  const canManage = useAuthStore((state) => Boolean(state.user?.isSuperuser))
  const [selectedCamera, setSelectedCamera] = useState<number>()
  const [evidence, setEvidence] = useState<number | null>(null)
  const [confirmation, setConfirmation] = useState<number | null>(null)
  const [status, setStatus] = useState("")
  const query = useVisionDashboard(selectedCamera)
  const cache = useQueryClient()
  const confirm = useMutation({
    mutationFn: (id: number) => visionRequest(`/api/vision/observations/${id}/attach`, { method: "POST" }),
    onSuccess: () => {
      setConfirmation(null)
      toast.success("已归入作业草稿，请在物资作业台账核对确认")
      void cache.invalidateQueries({ queryKey: ["vision"] })
    },
    onError: (error: Error) => toast.error(error.message),
  })
  const data = query.data
  useEffect(() => {
    if (selectedCamera === undefined && data?.cameras.length) setSelectedCamera((data.cameras.find((item) => item.config.playback_path) ?? data.cameras[0]).id)
  }, [data, selectedCamera])
  if (!data) return <BigscreenDataState failed={query.isError} retry={() => void query.refetch()} />
  const camera = data.cameras.find((item) => item.id === selectedCamera) ?? data.cameras.find((item) => item.config.playback_path) ?? data.cameras[0]
  const observations = data.observations.filter((item) => item.camera_id === camera?.id)
  const summary = selectedCamera
    ? data.summary
    : {
        observations: observations.length,
        linked: observations.filter((item) => item.status === "linked").length,
        pending: observations.filter((item) => item.status === "pending").length,
        duration_minutes: observations.reduce((sum, item) => sum + item.duration_seconds, 0) / 60,
      }
  const config = camera?.config
  const confirmationRow = observations.find((row) => row.id === confirmation)
  return (
    <div className="vision-screen">
      <section className="vision-screen-monitor">
        <div className="vision-toolbar">
          <select aria-label="监控摄像头" value={camera?.id ?? ""} onChange={(event) => setSelectedCamera(Number(event.target.value))}>
            {data.cameras.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <span>事件识别：{visionStateLabels[camera?.state.status ?? ""] ?? "未启用"}</span>
          {config?.demo_source ? <span className="vision-source-label">演示视频</span> : null}
          {canManage ? (
            <Link to="/data/video" title="摄像头配置" aria-label="摄像头配置">
              <Settings size={20} />
            </Link>
          ) : null}
        </div>
        {camera ? <LiveVideo cameraId={camera.id} streamPath={camera.config.playback_path} /> : <div>暂无摄像头</div>}
        <div className="vision-monitor-footer">
          <span>{camera?.area_name ?? "未配置区域"}</span>
          <span>
            画面目标 {camera?.state.status === "running" ? (camera.state.detected_count ?? 0) : "--"} · 移动中{" "}
            {camera?.state.status === "running" ? (camera.state.working_count ?? 0) : "--"}
          </span>
          <span>{camera?.state.received_at ? `识别更新 ${new Date(camera.state.received_at).toLocaleTimeString("zh-CN")}` : "暂无识别更新"}</span>
        </div>
        {query.isError ? (
          <div role="alert">
            数据更新失败{" "}
            <button type="button" onClick={() => void query.refetch()}>
              重试
            </button>
          </div>
        ) : null}
      </section>
      <aside className="vision-side">
        <BigscreenPanel title="作业观测 · 最近24小时" frame="wide">
          <div className="vision-metrics">
            {[
              ["识别片段", summary.observations, "段"],
              ["观测时长", summary.duration_minutes.toFixed(1), "分钟"],
              ["待确认", summary.pending, "段"],
              ["已关联作业", summary.linked, "项"],
            ].map(([label, value, unit]) => (
              <div key={label}>
                <span>{label}</span>
                <strong>
                  {value}
                  <small>{unit}</small>
                </strong>
              </div>
            ))}
          </div>
        </BigscreenPanel>
        <BigscreenPanel title="分时作业时长" frame="wide">
          <BigscreenBarChart
            height={180}
            unit="分钟"
            items={data.hourly.filter((item) => item.minutes > 0).map((item) => ({ name: `${String((item.hour_utc + 8) % 24).padStart(2, "0")}:00`, value: item.minutes }))}
          />
        </BigscreenPanel>
        <BigscreenPanel title="当前任务关联" frame="wide">
          <dl className="vision-binding">
            {[
              ["设备", config?.equipment_name],
              ["物资", config?.material_name || config?.material_code],
              ["批次", config?.batch_no],
              ["作业", operationLabels[config?.operation_type ?? ""]],
              ["任务", config?.task_ref],
            ].map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value || "未关联"}</dd>
              </div>
            ))}
          </dl>
        </BigscreenPanel>
      </aside>
      <BigscreenPanel title="作业片段与物资关联 · 最近100条" frame="wide" className="vision-observations">
        <select aria-label="作业片段状态" className="vision-status-filter" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">全部状态</option>
          {Object.entries(observationLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <div className="vision-table-wrap">
          <table>
            <thead>
              <tr>
                <th>发生时间</th>
                <th>设备</th>
                <th>物资 / 批次</th>
                <th>时长</th>
                <th>置信度</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {observations
                .filter((row) => !status || row.status === status)
                .map((row) => (
                  <tr key={row.id}>
                    <td>{new Date(row.started_at).toLocaleString("zh-CN", { hour12: false })}</td>
                    <td>{row.equipment_name ?? "待关联"}</td>
                    <td>
                      {row.material_name ?? "待关联"}
                      <small>{row.batch_no}</small>
                    </td>
                    <td>{row.duration_seconds.toFixed(1)} 秒</td>
                    <td>{(row.confidence * 100).toFixed(1)}%</td>
                    <td>{observationLabels[row.status]}</td>
                    <td>
                      <div className="flex gap-3">
                        {row.has_evidence ? (
                          <button type="button" onClick={() => setEvidence(row.id)}>
                            查看画面
                          </button>
                        ) : null}
                        {row.status === "pending" && canManage ? (
                          <button type="button" onClick={() => setConfirmation(row.id)}>
                            归入作业
                          </button>
                        ) : row.operation_id ? (
                          <a href="/data/material-handling">查看作业</a>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
          {!observations.some((row) => !status || row.status === status) ? <div className="p-6 text-center text-white/60">暂无符合条件的作业片段</div> : null}
        </div>
      </BigscreenPanel>
      {evidence !== null ? (
        <div className="vision-modal" role="dialog" aria-label="作业画面证据">
          <button type="button" aria-label="关闭画面" onClick={() => setEvidence(null)}>
            <X />
          </button>
          <RecognitionImage path={`/api/vision/observations/${evidence}/evidence`} className="h-full w-full" />
        </div>
      ) : null}
      {confirmation !== null ? (
        <div className="vision-confirm" role="dialog" aria-label="归入物资作业">
          <p>将所选观测归入以下任务的作业草稿？</p>
          <dl className="vision-binding">
            <div>
              <dt>任务</dt>
              <dd>{confirmationRow?.task_ref}</dd>
            </div>
            <div>
              <dt>设备</dt>
              <dd>{confirmationRow?.equipment_name}</dd>
            </div>
            <div>
              <dt>物资</dt>
              <dd>{confirmationRow?.material_name}</dd>
            </div>
            <div>
              <dt>批次</dt>
              <dd>{confirmationRow?.batch_no}</dd>
            </div>
          </dl>
          <div>
            <button type="button" onClick={() => setConfirmation(null)}>
              取消
            </button>
            <button type="button" disabled={confirm.isPending} onClick={() => confirm.mutate(confirmation)}>
              <Check size={16} />
              {confirm.isPending ? "提交中" : "确认归入"}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
