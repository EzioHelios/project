import { useMemo } from "react"
import { toast } from "sonner"
import { AdminEmptyState, AdminPanel } from "@/components/admin-ui"
import { Icons } from "@/components/icons"
import { OAuthLinkButton } from "@/components/profile/oauth-link-button"
import { Button } from "@/components/ui/button"
import { SkeletonCard } from "@/components/ui/skeleton"
import { useOAuthConfig } from "@/hooks/use-oauth-config"
import { useOAuthAccounts, useStartOAuthLink, useUnlinkOAuthAccount } from "@/lib/api/hooks/auth"

export function ConnectedAccounts() {
  const { data, isLoading, isError } = useOAuthAccounts()
  const { data: oauthConfig } = useOAuthConfig()
  const startLink = useStartOAuthLink()
  const unlink = useUnlinkOAuthAccount()

  const accounts = data?.items ?? []
  const linkedProviders = useMemo(() => new Set(accounts.map((account) => account.provider)), [accounts])

  if (isLoading) {
    return <SkeletonCard />
  }

  if (isError) {
    return (
      <AdminPanel title="关联账号">
        <AdminEmptyState title="关联账号加载失败" className="min-h-28" />
      </AdminPanel>
    )
  }

  const handleLink = async (provider: "google" | "github") => {
    try {
      const redirectUrl = `${window.location.origin}/profile`
      const result = await startLink.mutateAsync({ provider, redirectUrl })
      if (result?.authorizationUrl) {
        window.location.href = result.authorizationUrl
        return
      }
      toast.error("无法启动第三方账号授权")
    } catch (error) {
      toast.error("无法启动第三方账号授权", {
        description: error instanceof Error ? error.message : "请稍后重试",
      })
    }
  }

  const handleUnlink = async (provider: string) => {
    try {
      await unlink.mutateAsync(provider)
      toast.success(`已解除 ${provider} 关联`)
    } catch (error) {
      toast.error("解除关联失败", {
        description: error instanceof Error ? error.message : "请稍后重试",
      })
    }
  }

  return (
    <AdminPanel title="关联账号" contentClassName="space-y-4">
      {accounts.length === 0 ? (
        <AdminEmptyState title="暂无关联账号" className="min-h-28" />
      ) : (
        <div className="space-y-3">
          {accounts.map((account) => {
            const Icon = account.provider === "google" ? Icons.google : Icons.gitHub
            return (
              <div key={account.provider} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/60 bg-muted/30 px-4 py-3">
                <div className="flex items-center gap-3">
                  <Icon className="h-4 w-4" />
                  <div>
                    <p className="font-medium capitalize">{account.provider}</p>
                    <p className="text-muted-foreground text-sm">{account.email}</p>
                  </div>
                </div>
                <Button variant="outline" size="sm" onClick={() => handleUnlink(account.provider)}>
                  解除关联
                </Button>
              </div>
            )
          })}
        </div>
      )}
      <div className="flex flex-wrap gap-2 border-border/70 border-t pt-4">
        {oauthConfig?.googleEnabled && !linkedProviders.has("google") && <OAuthLinkButton provider="google" onClick={() => handleLink("google")} disabled={startLink.isPending} />}
        {oauthConfig?.githubEnabled && !linkedProviders.has("github") && <OAuthLinkButton provider="github" onClick={() => handleLink("github")} disabled={startLink.isPending} />}
      </div>
    </AdminPanel>
  )
}
