import { useMutation } from "@tanstack/react-query"
import { toast } from "sonner"
import { Icons } from "@/components/icons"
import { Button } from "@/components/ui/button"
import { apiAuthOauthGithubGithubAuthorize } from "@/lib/generated/api"

/** Key used to store the post-auth redirect destination in sessionStorage */
export const GITHUB_AUTH_REDIRECT_KEY = "github_auth_redirect"

interface GitHubSignInButtonProps {
  variant?: "signin" | "signup" | "link"
  onSuccess?: () => void
  onError?: (error: string) => void
  redirectUrl?: string
  /** The destination to redirect to after successful OAuth authentication */
  authRedirect?: string
  className?: string
}

export function GitHubSignInButton({ variant = "signin", onSuccess, onError, redirectUrl, authRedirect, className }: GitHubSignInButtonProps) {
  const { mutate: initiateOAuth, isPending } = useMutation({
    mutationFn: async () => {
      const targetUrl = redirectUrl ?? `${window.location.origin}/auth/github/callback`
      const response = await apiAuthOauthGithubGithubAuthorize({
        query: {
          redirect_url: targetUrl,
        },
      })

      if (response.error) {
        throw new Error("无法启动 GitHub 授权")
      }

      return response.data
    },
    onSuccess: (data) => {
      if (data?.authorizationUrl) {
        // Store the post-auth redirect destination before leaving for OAuth
        if (authRedirect) {
          sessionStorage.setItem(GITHUB_AUTH_REDIRECT_KEY, authRedirect)
        } else {
          sessionStorage.removeItem(GITHUB_AUTH_REDIRECT_KEY)
        }
        // Redirect to GitHub OAuth
        window.location.href = data.authorizationUrl
      } else {
        toast.error("无法获取 GitHub 授权地址")
        onError?.("无法获取 GitHub 授权地址")
      }
      onSuccess?.()
    },
    onError: (error: Error) => {
      const message = error.message || "GitHub 登录失败"
      toast.error(message)
      onError?.(message)
    },
  })

  const handleClick = () => {
    initiateOAuth()
  }

  const getButtonText = () => {
    switch (variant) {
      case "signup":
        return "使用 GitHub 注册"
      case "link":
        return "关联 GitHub 账号"
      default:
        return "使用 GitHub 登录"
    }
  }

  return (
    <Button type="button" variant="outline" onClick={handleClick} disabled={isPending} className={className}>
      {isPending ? <Icons.spinner className="mr-2 h-4 w-4 animate-spin" /> : <Icons.gitHub className="mr-2 h-4 w-4" />}
      {getButtonText()}
    </Button>
  )
}
