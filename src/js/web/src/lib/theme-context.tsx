import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

export type ThemePreference = "system" | "light" | "dark"
export type ResolvedTheme = "light" | "dark"

type ThemeContextType = {
  theme: ResolvedTheme
  resolvedTheme: ResolvedTheme
  preference: ThemePreference
  setPreference: (preference: ThemePreference) => void
  toggleTheme: () => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)
const THEME_STORAGE_KEY = "app-theme-preference"
const LEGACY_THEME_STORAGE_KEY = "theme"
const THEME_QUERY = "(prefers-color-scheme: dark)"

function isThemePreference(value: string | null): value is ThemePreference {
  return value === "system" || value === "light" || value === "dark"
}

function getInitialPreference(): ThemePreference {
  if (typeof window === "undefined") return "system"
  const savedPreference = localStorage.getItem(THEME_STORAGE_KEY)
  if (isThemePreference(savedPreference)) return savedPreference
  const legacyTheme = localStorage.getItem(LEGACY_THEME_STORAGE_KEY)
  return legacyTheme === "light" || legacyTheme === "dark" ? legacyTheme : "system"
}

export function resolveTheme(preference: ThemePreference, prefersDark: boolean): ResolvedTheme {
  return preference === "system" ? (prefersDark ? "dark" : "light") : preference
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [preference, setPreference] = useState<ThemePreference>(getInitialPreference)
  const [prefersDark, setPrefersDark] = useState(() => (typeof window === "undefined" ? false : window.matchMedia(THEME_QUERY).matches))
  const resolvedTheme = resolveTheme(preference, prefersDark)

  useEffect(() => {
    const mediaQuery = window.matchMedia(THEME_QUERY)
    const handleChange = (event: MediaQueryListEvent) => setPrefersDark(event.matches)
    setPrefersDark(mediaQuery.matches)
    mediaQuery.addEventListener("change", handleChange)
    return () => mediaQuery.removeEventListener("change", handleChange)
  }, [])

  useEffect(() => {
    const root = window.document.documentElement
    root.classList.remove("light", "dark")
    root.classList.add(resolvedTheme)
    root.dataset.theme = resolvedTheme
    root.dataset.themePreference = preference
    root.style.colorScheme = resolvedTheme
    localStorage.setItem(THEME_STORAGE_KEY, preference)
    localStorage.removeItem(LEGACY_THEME_STORAGE_KEY)
  }, [preference, resolvedTheme])

  const toggleTheme = useCallback(() => {
    setPreference(resolvedTheme === "light" ? "dark" : "light")
  }, [resolvedTheme])

  const value = useMemo(() => ({ theme: resolvedTheme, resolvedTheme, preference, setPreference, toggleTheme }), [preference, resolvedTheme, toggleTheme])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider")
  }
  return context
}
