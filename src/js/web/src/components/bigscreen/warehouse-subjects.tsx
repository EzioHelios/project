import { BigscreenBarChart, BigscreenLedgerChart } from "@/components/bigscreen/charts"
import consumptionIllustration from "@/components/bigscreen/custom/assets/yongdiantu.a4bf1067.png"
import type { BigscreenOperationsResponse } from "@/lib/bigscreen/types"

export function DeviceReadings({ devices, onSelect }: { devices: BigscreenOperationsResponse["devices"]; onSelect: (id: string) => void }) {
  return (
    <div className="warehouse-sample-list">
      {devices
        .filter((item) => item.last_reading)
        .sort((a, b) => (b.last_reading ?? "").localeCompare(a.last_reading ?? ""))
        .map((item) => (
          <button type="button" key={item.id} onClick={() => onSelect(item.id)}>
            <span>{item.name}</span>
            <strong>
              {item.register_value?.toLocaleString("zh-CN", { maximumFractionDigits: 2 }) ?? "—"}
              <small> {item.register_unit}</small>
            </strong>
            <time>{item.last_reading?.replace("T", " ")}</time>
          </button>
        ))}
    </div>
  )
}

export function DeviceBoard({ devices, onSelect }: { devices: BigscreenOperationsResponse["devices"]; onSelect: (id: string) => void }) {
  const groups = new Map<string, typeof devices>()
  for (const item of [...devices].sort((a, b) => (b.last_reading ?? "").localeCompare(a.last_reading ?? ""))) {
    const key = item.area_id ?? "unallocated"
    groups.set(key, [...(groups.get(key) ?? []), item])
  }
  return (
    <div className="warehouse-device-board">
      {[...groups].map(([id, items]) => (
        <section key={id}>
          <h3>
            {items[0].area ?? "未关联区域"}
            <small>{items.length} 台</small>
          </h3>
          {items.map((item) => (
            <button type="button" key={item.id} onClick={() => onSelect(item.id)}>
              <span>
                {item.name}
                <small>{item.category === 0 ? "电表" : item.category === 1 ? "发电设备" : "设备档案"}</small>
              </span>
              <strong>
                {item.register_value?.toLocaleString("zh-CN", { maximumFractionDigits: 2 }) ?? "—"}
                <small> {item.register_unit}</small>
              </strong>
              <time>{item.last_reading?.replace("T", " ") ?? "暂无采样"}</time>
              <em>{item.status === 0 ? "台账正常" : item.status === 1 ? "台账故障" : "状态未登记"}</em>
            </button>
          ))}
        </section>
      ))}
    </div>
  )
}

export function EnergyCalendar({ items }: { items: BigscreenOperationsResponse["energy_calendar"] }) {
  return (
    <section className="warehouse-energy-calendar" aria-label="电表日月年已记录电量">
      <div className="warehouse-calendar-caption">
        <img src={consumptionIllustration} alt="" />
        <span>电表电量合计</span>
        <small>截至 {items[0]?.end}</small>
      </div>
      {items.map((item) => (
        <div key={item.id} className="warehouse-calendar-value">
          <span>{item.label}</span>
          <strong>
            {item.value?.toLocaleString("zh-CN", { maximumFractionDigits: 2 }) ?? "—"}
            <small>kWh</small>
          </strong>
          <small>
            {item.recorded_days} / {item.calendar_days} 天有记录
          </small>
        </div>
      ))}
    </section>
  )
}

export function WarehouseLedger({ data }: { data: BigscreenOperationsResponse }) {
  return (
    <div className="warehouse-ledger-subject">
      <div className="warehouse-ledger-totals">
        {data.business
          .filter((item) => item.unit === "万元")
          .map((item) => (
            <div key={item.label}>
              <span>历史{item.label}</span>
              <strong>
                {item.value?.toLocaleString("zh-CN", { maximumFractionDigits: 2 }) ?? "—"}
                <small>万元</small>
              </strong>
            </div>
          ))}
      </div>
      <BigscreenLedgerChart points={data.ledger.trend} height={125} />
      <div className="warehouse-ledger-coverage">
        {data.ledger.coverage.map((item) => (
          <div key={item.kind}>
            <span>
              {item.kind === "inbound" ? "入库" : "出库"} {item.records.toLocaleString("zh-CN")} 条
            </span>
            <span>
              缺日期 {item.undated_records} · 缺金额 {item.missing_amount}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function CommuteEnergy({ data }: { data: BigscreenOperationsResponse }) {
  const total = data.commute_power.reduce((sum, item) => sum + item.value, 0)
  return (
    <div>
      <div className="warehouse-commute-total">
        通勤档案 <strong>{total}</strong> 条
      </div>
      <BigscreenBarChart items={data.commute_power} unit="条档案" height={130} />
      <div className="warehouse-commute-legend">
        {data.commute_power.map((item) => (
          <span key={item.name}>
            {item.name}
            <strong>{item.value}</strong>
          </span>
        ))}
      </div>
    </div>
  )
}
