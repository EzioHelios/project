import { createFileRoute } from "@tanstack/react-router"

import { ScopeRecordPage } from "@/components/carbon/scope-record-page"

type Scope3Transport = {
  id: number
  waybill_no: string
  origin: string
  destination: string
  vehicle_type: string
  distance_km: string | number
  load_ton: string | number
  status?: string
}

export const Route = createFileRoute("/_app/carbon-mgmt/scope3-transport")({
  component: Scope3TransportPage,
})

function Scope3TransportPage() {
  return (
    <ScopeRecordPage<Scope3Transport>
      title="[范围3] 外购运输"
      endpoint="/api/carbon/scope3-third-party-transport"
      queryKey={["carbon-mgmt", "scope3-transport", "list"]}
      searchPlaceholder="搜索：运单号/起点/终点/车辆类型…"
      columns={[
        { key: "waybill_no", label: "运单号" },
        { key: "origin", label: "起点" },
        { key: "destination", label: "终点" },
        { key: "vehicle_type", label: "车辆类型" },
        { key: "distance_km", label: "距离(km)", align: "right" },
        { key: "load_ton", label: "载重(吨)", align: "right" },
      ]}
      fields={[
        { name: "waybill_no", label: "运单号", required: true },
        { name: "origin", label: "起点", required: true },
        { name: "destination", label: "终点", required: true },
        { name: "vehicle_type", label: "车辆类型", required: true },
        { name: "distance_km", label: "距离(km)", type: "number", required: true },
        { name: "load_ton", label: "载重(吨)", type: "number", required: true },
        { name: "fuel_amount", label: "燃料用量", type: "number" },
        { name: "remark", label: "备注", type: "textarea" },
      ]}
    />
  )
}
