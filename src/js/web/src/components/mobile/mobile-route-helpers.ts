export function readSearchParam(name: string, fallback = "") {
  if (typeof window === "undefined") return fallback
  return new URLSearchParams(window.location.search).get(name) ?? fallback
}

export function readNumberSearchParam(name: string) {
  const value = readSearchParam(name)
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

export function replaceMobileSearch(updates: Record<string, string | number | null | undefined>) {
  if (typeof window === "undefined") return
  const params = new URLSearchParams(window.location.search)
  for (const [key, value] of Object.entries(updates)) {
    if (value == null || value === "") {
      params.delete(key)
    } else {
      params.set(key, String(value))
    }
  }
  const query = params.toString()
  window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}`)
}
