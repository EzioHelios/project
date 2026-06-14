import { toast } from "sonner"
import { create } from "zustand"
import { persist } from "zustand/middleware"
import { getApiBaseUrl } from "@/lib/api-base-url"
import type { Team, User } from "@/lib/generated/api"
import { accountLogout, accountProfile } from "@/lib/generated/api"

export interface HumanVerificationSubmission {
  payload: string
  provider: string
}

interface LoginResult {
  mfaRequired: boolean
}

interface AuthState {
  user: User | null
  currentTeam: Team | null
  teams: Team[]
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string, verification?: HumanVerificationSubmission | null) => Promise<LoginResult>
  completeMfaLogin: () => Promise<void>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>
  setCurrentTeam: (team: Team) => void
  setTeams: (teams: Team[]) => void
}

export class HumanVerificationRequiredError extends Error {
  readonly code = "human_verification_required"
}

const apiUrl = getApiBaseUrl()

function isHumanVerificationRequired(payload: { detail?: string; title?: string } | null): boolean {
  return payload?.detail === "human_verification_required" || payload?.title === "human_verification_required"
}

async function postLogin(body: { username: string; password: string; humanVerification?: HumanVerificationSubmission }): Promise<Response> {
  const headers = new Headers({ "Content-Type": "application/json" })
  const csrfToken = window.__LITESTAR_CSRF__
  if (csrfToken) {
    headers.set("X-XSRF-TOKEN", csrfToken)
  }

  return fetch(`${apiUrl}/api/access/login`, {
    method: "POST",
    body: JSON.stringify(body),
    credentials: "include",
    headers,
  })
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      currentTeam: null,
      teams: [],
      isLoading: false,
      isAuthenticated: false,
      login: async (email: string, password: string, verification?: HumanVerificationSubmission | null) => {
        set({ isLoading: true })
        try {
          const response = await postLogin({
            username: email,
            password,
            humanVerification: verification ?? undefined,
          })

          const payload = (await response.json().catch(() => null)) as { detail?: string; title?: string; mfaRequired?: boolean } | null

          if (!response.ok) {
            if (isHumanVerificationRequired(payload)) {
              throw new HumanVerificationRequiredError("Human verification required")
            }
            throw new Error(payload?.detail || "Login failed")
          }

          if (payload?.mfaRequired) {
            set({ user: null, isAuthenticated: false })
            return { mfaRequired: true }
          }

          set({ isAuthenticated: true })
          try {
            const { data: user } = await accountProfile({ throwOnError: true })
            if (user) {
              set({ user })
            }
          } catch {
            // Session cookies are authoritative; profile fetch can reconcile later.
          }
          return { mfaRequired: false }
        } catch (error) {
          set({ user: null, currentTeam: null, teams: [], isAuthenticated: false })
          if (!(error instanceof HumanVerificationRequiredError)) {
            toast.error("An error occurred", {
              description: error instanceof Error ? error.message : "Unknown error",
            })
          }
          throw error
        } finally {
          set({ isLoading: false })
        }
      },
      completeMfaLogin: async () => {
        set({ isLoading: true })
        try {
          set({ isAuthenticated: true })
          try {
            const { data: user } = await accountProfile({ throwOnError: true })
            if (user) {
              set({ user })
            }
          } catch {
            // Session cookies are authoritative; profile fetch can reconcile later.
          }
        } catch (error) {
          set({ user: null, currentTeam: null, teams: [], isAuthenticated: false })
          toast.error("MFA verification failed", {
            description: error instanceof Error ? error.message : "Unable to complete login",
          })
        } finally {
          set({ isLoading: false })
        }
      },
      logout: async () => {
        set({ isLoading: true })
        try {
          await accountLogout()
          set({ user: null, currentTeam: null, teams: [], isAuthenticated: false })
        } finally {
          set({ isLoading: false })
        }
      },
      checkAuth: async () => {
        set({ isLoading: true })
        try {
          const { data: user } = await accountProfile({ throwOnError: true })
          if (!user) {
            throw new Error("Profile response did not include a user")
          }
          set({ user, isAuthenticated: true })
        } catch {
          set({ user: null, currentTeam: null, teams: [], isAuthenticated: false })
        } finally {
          set({ isLoading: false })
        }
      },
      setCurrentTeam: (team: Team) => set({ currentTeam: team }),
      setTeams: (teams: Team[]) =>
        set((state) => {
          const nextCurrent = state.currentTeam && teams.some((team) => team.id === state.currentTeam?.id) ? state.currentTeam : (teams[0] ?? null)
          return { teams, currentTeam: nextCurrent }
        }),
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({
        isAuthenticated: state.isAuthenticated,
        user: state.user,
        currentTeam: state.currentTeam,
      }),
    },
  ),
)

export async function ensureAuthStoreHydrated(): Promise<void> {
  if (useAuthStore.persist.hasHydrated()) {
    return
  }

  await useAuthStore.persist.rehydrate()
}
