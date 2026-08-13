import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { MfaDisableDialog } from "@/components/mfa/mfa-disable-dialog"

// Mock the auth store
const mockUser = vi.fn()
vi.mock("@/lib/auth", () => ({
  useAuthStore: () => ({
    user: mockUser(),
  }),
}))

// Mock the auth hooks
const mockDisableMfa = vi.fn()
const mockInitiateOAuth = vi.fn()
vi.mock("@/lib/api/hooks/auth", () => ({
  useDisableMfa: () => ({
    mutateAsync: mockDisableMfa,
    isPending: false,
  }),
  useInitiateDisableMfaOAuth: () => ({
    mutateAsync: mockInitiateOAuth,
    isPending: false,
  }),
}))

// Mock sonner toast
vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe("MfaDisableDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockDisableMfa.mockResolvedValue({})
    mockInitiateOAuth.mockResolvedValue({ authorizationUrl: "https://oauth.example.com/auth" })
  })

  describe("when user has a password", () => {
    beforeEach(() => {
      mockUser.mockReturnValue({
        id: "user-1",
        email: "test@example.com",
        hasPassword: true,
        oauthAccounts: [],
      })
    })

    it("renders password input when dialog is opened", async () => {
      const user = userEvent.setup()
      render(<MfaDisableDialog />, { wrapper: createWrapper() })

      // Click trigger button to open dialog
      await user.click(screen.getByRole("button", { name: "停用多因素认证" }))

      // Should show password input
      expect(screen.getByPlaceholderText("当前密码")).toBeInTheDocument()
      // Should NOT show OAuth button
      expect(screen.queryByRole("button", { name: /使用.+校验/ })).not.toBeInTheDocument()
    })

    it("calls disableMfa with password when submitted", async () => {
      const user = userEvent.setup()
      render(<MfaDisableDialog />, { wrapper: createWrapper() })

      await user.click(screen.getByRole("button", { name: "停用多因素认证" }))
      await user.type(screen.getByPlaceholderText("当前密码"), "testpassword123")
      await user.click(screen.getByRole("button", { name: "停用", exact: true }))

      expect(mockDisableMfa).toHaveBeenCalledWith("testpassword123")
    })
  })

  describe("when user does not have a password (OAuth-only)", () => {
    beforeEach(() => {
      mockUser.mockReturnValue({
        id: "user-1",
        email: "test@example.com",
        hasPassword: false,
        oauthAccounts: [
          { id: "oauth-1", oauthName: "github", accountId: "gh-123", accountEmail: "test@github.com" },
        ],
      })
    })

    it("renders OAuth verification button instead of password input", async () => {
      const user = userEvent.setup()
      render(<MfaDisableDialog />, { wrapper: createWrapper() })

      await user.click(screen.getByRole("button", { name: "停用多因素认证" }))

      // Should NOT show password input
      expect(screen.queryByPlaceholderText("当前密码")).not.toBeInTheDocument()
      // Should show OAuth button with provider name
      expect(screen.getByRole("button", { name: "使用 Github 校验" })).toBeInTheDocument()
    })

    it("shows explanatory message about OAuth verification", async () => {
      const user = userEvent.setup()
      render(<MfaDisableDialog />, { wrapper: createWrapper() })

      await user.click(screen.getByRole("button", { name: "停用多因素认证" }))

      expect(screen.getByText("使用已关联账号完成校验后停用多因素认证。")).toBeInTheDocument()
    })

    it("initiates OAuth flow when verify button is clicked", async () => {
      const user = userEvent.setup()

      // Mock window.location.href assignment
      const hrefSpy = vi.fn()
      const originalLocation = window.location
      Object.defineProperty(window, "location", {
        value: {
          ...originalLocation,
          set href(url: string) {
            hrefSpy(url)
          },
          get href() {
            return ""
          },
        },
        writable: true,
      })

      render(<MfaDisableDialog />, { wrapper: createWrapper() })

      await user.click(screen.getByRole("button", { name: "停用多因素认证" }))
      await user.click(screen.getByRole("button", { name: "使用 Github 校验" }))

      expect(mockInitiateOAuth).toHaveBeenCalledWith("github")
      expect(hrefSpy).toHaveBeenCalledWith("https://oauth.example.com/auth")

      // Restore
      Object.defineProperty(window, "location", {
        value: originalLocation,
        writable: true,
      })
    })
  })

  describe("when user has multiple OAuth providers", () => {
    beforeEach(() => {
      mockUser.mockReturnValue({
        id: "user-1",
        email: "test@example.com",
        hasPassword: false,
        oauthAccounts: [
          { id: "oauth-1", oauthName: "github", accountId: "gh-123", accountEmail: "test@github.com" },
          { id: "oauth-2", oauthName: "google", accountId: "g-456", accountEmail: "test@gmail.com" },
        ],
      })
    })

    it("shows the first OAuth provider as the default verification option", async () => {
      const user = userEvent.setup()
      render(<MfaDisableDialog />, { wrapper: createWrapper() })

      await user.click(screen.getByRole("button", { name: "停用多因素认证" }))

      // Should show first provider (github)
      expect(screen.getByRole("button", { name: "使用 Github 校验" })).toBeInTheDocument()
    })
  })
})
