import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/lib/generated/api", () => ({
  accountLogout: vi.fn(),
  accountProfile: vi.fn(),
}))

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
  },
}))

describe("auth login", () => {
  const originalFetch = global.fetch
  const storage = new Map<string, string>()

  beforeEach(() => {
    vi.clearAllMocks()
    storage.clear()
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => {
        storage.set(key, value)
      },
      removeItem: (key: string) => {
        storage.delete(key)
      },
      clear: () => {
        storage.clear()
      },
    })
    global.fetch = vi.fn(async () => {
      return new Response(JSON.stringify({ title: "human_verification_required", detail: "Bad Request" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      })
    }) as typeof fetch
  })

  afterEach(() => {
    global.fetch = originalFetch
    vi.unstubAllGlobals()
  })

  it("treats a problem-details title of human_verification_required as a captcha challenge", async () => {
    const { HumanVerificationRequiredError, useAuthStore } = await import("@/lib/auth")
    await expect(useAuthStore.getState().login("admin@example.com", "wrongpass")).rejects.toBeInstanceOf(
      HumanVerificationRequiredError,
    )
  })

  it("can restore authenticated state from the server session after a hard refresh", async () => {
    const { accountProfile } = await import("@/lib/generated/api")
    const { useAuthStore } = await import("@/lib/auth")

    vi.mocked(accountProfile).mockResolvedValue({
      data: {
        id: "user-1",
        email: "root@example.com",
        name: "Root",
      },
    } as Awaited<ReturnType<typeof accountProfile>>)

    useAuthStore.setState({
      user: null,
      currentTeam: null,
      teams: [],
      isAuthenticated: false,
      isLoading: false,
    })

    await useAuthStore.getState().checkAuth()

    expect(useAuthStore.getState().isAuthenticated).toBe(true)
    expect(useAuthStore.getState().user?.email).toBe("root@example.com")
  })
})
