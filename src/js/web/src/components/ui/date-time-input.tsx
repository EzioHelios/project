import { Input } from "@/components/ui/input"

type DateTimeInputProps = {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  required?: boolean
  disabled?: boolean
}

export function DateTimeInput({ id, label, value, onChange, required, disabled }: DateTimeInputProps) {
  const [date = "", time = ""] = value.split("T")
  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_5.5rem] gap-2">
      <Input id={id} aria-label={`${label}日期`} type="date" value={date} disabled={disabled} onChange={(event) => onChange(`${event.target.value}T${time || "00:00"}`)} />
      <Input
        aria-label={`${label}时刻`}
        value={time}
        placeholder="HH:mm"
        inputMode="numeric"
        pattern="([01][0-9]|2[0-3]):[0-5][0-9]"
        maxLength={5}
        required={required}
        disabled={disabled}
        onChange={(event) => onChange(`${date}T${event.target.value}`)}
      />
    </div>
  )
}

export function isCompleteDateTime(value: string) {
  return /^\d{4}-\d{2}-\d{2}T([01]\d|2[0-3]):[0-5]\d$/.test(value) && Number.isFinite(new Date(value).getTime())
}
