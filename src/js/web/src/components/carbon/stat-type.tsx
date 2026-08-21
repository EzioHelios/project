import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export type StatType = "day" | "month" | "year"

export function StatTypeSelect({ value, onChange, className }: { value: StatType; onChange: (value: StatType) => void; className?: string }) {
  return (
    <div className={className}>
      <Select value={value} onValueChange={(v) => onChange(v as StatType)}>
        <SelectTrigger className="h-9 w-[120px]">
          <SelectValue placeholder="选择粒度" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="day">日</SelectItem>
          <SelectItem value="month">月</SelectItem>
          <SelectItem value="year">年</SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}
