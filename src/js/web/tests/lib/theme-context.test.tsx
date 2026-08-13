import { act, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ThemeProvider, resolveTheme, useTheme } from "@/lib/theme-context"

type ThemeListener = (event: MediaQueryListEvent) => void

let prefersDark = false
let listeners: ThemeListener[] = []
const storage = new Map<string, string>()

const localStorageMock = {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
  clear: () => storage.clear(),
  key: (index: number) => [...storage.keys()][index] ?? null,
  get length() {
    return storage.size
  },
}

function installMatchMedia() {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: prefersDark,
    media: query,
    onchange: null,
    addEventListener: (_type: string, listener: ThemeListener) => listeners.push(listener),
    removeEventListener: (_type: string, listener: ThemeListener) => {
      listeners = listeners.filter((candidate) => candidate !== listener)
    },
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
}

function ThemeProbe() {
  const { preference, resolvedTheme, setPreference } = useTheme()
  return (
    <div>
      <output data-testid="theme">{`${preference}:${resolvedTheme}`}</output>
      <button type="button" onClick={() => setPreference("system")}>
        system
      </button>
      <button type="button" onClick={() => setPreference("dark")}>
        dark
      </button>
    </div>
  )
}

describe("theme runtime", () => {
  beforeEach(() => {
    storage.clear()
    vi.stubGlobal("localStorage", localStorageMock)
    document.documentElement.className = ""
    prefersDark = false
    listeners = []
    installMatchMedia()
  })

  it("resolves explicit and system preferences", () => {
    expect(resolveTheme("system", true)).toBe("dark")
    expect(resolveTheme("system", false)).toBe("light")
    expect(resolveTheme("light", true)).toBe("light")
    expect(resolveTheme("dark", false)).toBe("dark")
  })

  it("migrates the legacy theme value and persists the new preference", () => {
    localStorageMock.setItem("theme", "dark")
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    )

    expect(screen.getByTestId("theme")).toHaveTextContent("dark:dark")
    expect(localStorageMock.getItem("app-theme-preference")).toBe("dark")
    expect(localStorageMock.getItem("theme")).toBeNull()
    expect(document.documentElement).toHaveClass("dark")
  })

  it("tracks system changes only while the system preference is active", async () => {
    const user = userEvent.setup()
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    )

    expect(screen.getByTestId("theme")).toHaveTextContent("system:light")
    act(() => listeners.forEach((listener) => listener({ matches: true } as MediaQueryListEvent)))
    expect(screen.getByTestId("theme")).toHaveTextContent("system:dark")

    await user.click(screen.getByRole("button", { name: "dark" }))
    act(() => listeners.forEach((listener) => listener({ matches: false } as MediaQueryListEvent)))
    expect(screen.getByTestId("theme")).toHaveTextContent("dark:dark")
    expect(localStorageMock.getItem("app-theme-preference")).toBe("dark")
  })
})
