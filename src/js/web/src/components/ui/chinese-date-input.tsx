import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react"
import * as React from "react"

import { cn } from "@/lib/utils"

type ChineseDateInputProps = Omit<React.ComponentProps<"input">, "type">

const weekDays = ["一", "二", "三", "四", "五", "六", "日"]

function asInputValue(value: ChineseDateInputProps["value"] | ChineseDateInputProps["defaultValue"]) {
  if (Array.isArray(value)) return value[0] ?? ""
  if (value === null || value === undefined) return ""
  return String(value)
}

function parseIsoDate(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return null

  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const date = new Date(year, month - 1, day)

  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null
  return date
}

function toIsoDate(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function todayIsoDate() {
  return toIsoDate(new Date())
}

function formatChineseDate(value: string) {
  const date = parseIsoDate(value)
  if (!date) return value

  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}年${month}月${day}日`
}

function monthLabel(date: Date) {
  return `${date.getFullYear()}年${date.getMonth() + 1}月`
}

function buildMonthCells(cursor: Date) {
  const firstDay = new Date(cursor.getFullYear(), cursor.getMonth(), 1)
  const mondayOffset = (firstDay.getDay() + 6) % 7
  const start = new Date(firstDay)
  start.setDate(firstDay.getDate() - mondayOffset)

  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(start)
    date.setDate(start.getDate() + index)
    return date
  })
}

function isOutsideRange(isoValue: string, min?: string | number, max?: string | number) {
  const minValue = min === undefined ? "" : String(min)
  const maxValue = max === undefined ? "" : String(max)

  if (minValue && isoValue < minValue) return true
  if (maxValue && isoValue > maxValue) return true
  return false
}

function makeChangeEvent(name: string | undefined, value: string) {
  return {
    target: { name, value },
    currentTarget: { name, value },
  } as React.ChangeEvent<HTMLInputElement>
}

function ChineseDateInput({ className, value, defaultValue, onChange, disabled, readOnly, name, id, placeholder = "选择日期", min, max, ...props }: ChineseDateInputProps) {
  const inputId = React.useId()
  const resolvedId = id ?? inputId
  const wrapperRef = React.useRef<HTMLDivElement>(null)
  const [open, setOpen] = React.useState(false)
  const [internalValue, setInternalValue] = React.useState(() => asInputValue(defaultValue))
  const currentValue = value !== undefined ? asInputValue(value) : internalValue
  const selectedDate = parseIsoDate(currentValue)
  const [cursor, setCursor] = React.useState(() => selectedDate ?? new Date())

  React.useEffect(() => {
    if (selectedDate) setCursor(new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1))
  }, [selectedDate])

  React.useEffect(() => {
    if (!open) return

    const handlePointerDown = (event: PointerEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) setOpen(false)
    }

    document.addEventListener("pointerdown", handlePointerDown)
    return () => document.removeEventListener("pointerdown", handlePointerDown)
  }, [open])

  const emitChange = (nextValue: string) => {
    if (disabled || readOnly) return
    if (value === undefined) setInternalValue(nextValue)
    onChange?.(makeChangeEvent(name, nextValue))
  }

  const selectDate = (date: Date) => {
    const nextValue = toIsoDate(date)
    if (isOutsideRange(nextValue, min, max)) return
    emitChange(nextValue)
    setOpen(false)
  }

  const clearDate = () => {
    emitChange("")
    setOpen(false)
  }

  const openPicker = () => {
    if (disabled || readOnly) return
    setCursor(selectedDate ?? new Date())
    setOpen(true)
  }

  const visibleValue = currentValue ? formatChineseDate(currentValue) : ""
  const cells = buildMonthCells(cursor)
  const currentMonth = cursor.getMonth()
  const today = todayIsoDate()

  return (
    <div ref={wrapperRef} className="relative w-full">
      {name ? <input type="hidden" name={name} value={currentValue} /> : null}
      <div className="relative">
        <input
          {...props}
          id={resolvedId}
          type="text"
          data-slot="input"
          lang="zh-CN"
          role="combobox"
          value={visibleValue}
          placeholder={placeholder}
          readOnly
          disabled={disabled}
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-readonly={readOnly}
          className={cn(
            "flex h-10 w-full min-w-0 cursor-pointer rounded-lg border border-border/80 bg-card/80 py-2 pr-10 pl-3 text-base shadow-sm outline-none transition-[color,box-shadow,transform] selection:bg-primary selection:text-primary-foreground placeholder:text-muted-foreground disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-60 md:text-sm dark:bg-input/40",
            "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:shadow-lg focus-visible:shadow-ring/10",
            "aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40",
            className,
          )}
          onClick={openPicker}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault()
              openPicker()
            }
            if (event.key === "Escape") setOpen(false)
            if (event.key === "Backspace" || event.key === "Delete") clearDate()
          }}
        />
        <button
          type="button"
          aria-label="打开日期选择器"
          className="absolute top-1/2 right-2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
          disabled={disabled || readOnly}
          onClick={openPicker}
        >
          <CalendarDays className="h-4 w-4" />
        </button>
      </div>

      {open ? (
        <div className="absolute top-11 left-0 z-50 w-[296px] rounded-lg border border-border bg-popover p-3 text-popover-foreground shadow-lg">
          <div className="mb-3 flex items-center justify-between">
            <button
              type="button"
              aria-label="上个月"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
              onClick={() => setCursor((date) => new Date(date.getFullYear(), date.getMonth() - 1, 1))}
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <div className="font-medium text-sm">{monthLabel(cursor)}</div>
            <button
              type="button"
              aria-label="下个月"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
              onClick={() => setCursor((date) => new Date(date.getFullYear(), date.getMonth() + 1, 1))}
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="mb-1 grid grid-cols-7 gap-1 text-center text-muted-foreground text-xs">
            {weekDays.map((day) => (
              <div key={day} className="py-1">
                {day}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {cells.map((date) => {
              const isoValue = toIsoDate(date)
              const muted = date.getMonth() !== currentMonth
              const selected = isoValue === currentValue
              const isToday = isoValue === today
              const blocked = isOutsideRange(isoValue, min, max)

              return (
                <button
                  key={isoValue}
                  type="button"
                  disabled={blocked}
                  className={cn(
                    "h-8 rounded-md text-center text-sm tabular-nums transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-30",
                    muted && "text-muted-foreground/55",
                    isToday && "border border-border font-medium",
                    selected && "bg-primary text-primary-foreground hover:bg-primary",
                  )}
                  onClick={() => selectDate(date)}
                >
                  {date.getDate()}
                </button>
              )
            })}
          </div>

          <div className="mt-3 flex items-center justify-between border-t pt-3">
            <button type="button" className="rounded-md px-2 py-1 text-muted-foreground text-xs hover:bg-muted hover:text-foreground" onClick={clearDate}>
              清空
            </button>
            <button type="button" className="rounded-md px-2 py-1 font-medium text-primary text-xs hover:bg-muted" onClick={() => selectDate(new Date())}>
              今天
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}

export { ChineseDateInput }
