export const MICROGRID_SITE_TIME_ZONE = "Asia/Shanghai"

type SiteTimeFormat = "date-time" | "time"

function formatSiteTimestamp(value: string | null | undefined, format: SiteTimeFormat) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value

  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: MICROGRID_SITE_TIME_ZONE,
    month: format === "date-time" ? "2-digit" : undefined,
    day: format === "date-time" ? "2-digit" : undefined,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  })
    .formatToParts(date)
    .reduce<Record<string, string>>((result, part) => {
      result[part.type] = part.value
      return result
    }, {})

  const time = `${parts.hour}:${parts.minute}`
  return format === "date-time" ? `${parts.month}-${parts.day} ${time}` : time
}

export function formatMicrogridDateTime(value: string | null | undefined) {
  return formatSiteTimestamp(value, "date-time")
}

export function formatMicrogridTime(value: string | null | undefined) {
  return formatSiteTimestamp(value, "time")
}
