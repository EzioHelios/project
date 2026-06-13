import { useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { useDisableMfa, useInitiateDisableMfaOAuth } from "@/lib/api/hooks/auth"
import { useAuthStore } from "@/lib/auth"

interface MfaDisableDialogProps {
  disabled?: boolean
}

export function MfaDisableDialog({ disabled }: MfaDisableDialogProps) {
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState("")
  const { user } = useAuthStore()
  const disableMfa = useDisableMfa()
  const initiateOAuth = useInitiateDisableMfaOAuth()

  const hasPassword = user?.hasPassword ?? true
  const oauthProvider = user?.oauthAccounts?.[0]?.oauthName

  const handlePasswordDisable = async () => {
    if (!password) {
      toast.error("请输入密码后再停用多因素认证")
      return
    }
    try {
      await disableMfa.mutateAsync(password)
      setOpen(false)
      setPassword("")
    } catch (error) {
      toast.error("多因素认证停用失败", {
        description: error instanceof Error ? error.message : "请检查密码后重试",
      })
    }
  }

  const handleOAuthDisable = async () => {
    if (!oauthProvider) {
      toast.error("未找到可用于校验的关联账号")
      return
    }
    try {
      const result = await initiateOAuth.mutateAsync(oauthProvider)
      if (result.authorizationUrl) {
        window.location.href = result.authorizationUrl
      }
    } catch (error) {
      toast.error("无法启动第三方账号校验", {
        description: error instanceof Error ? error.message : "请稍后重试",
      })
    }
  }

  const formatProviderName = (provider: string) => {
    return provider.charAt(0).toUpperCase() + provider.slice(1)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" disabled={disabled}>
          停用多因素认证
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>停用多因素认证</DialogTitle>
          <DialogDescription className="sr-only">{hasPassword ? "输入当前密码以停用多因素认证。" : "使用已关联账号完成校验后停用多因素认证。"}</DialogDescription>
        </DialogHeader>

        {hasPassword ? (
          <>
            <Input type="password" placeholder="当前密码" value={password} onChange={(event) => setPassword(event.target.value)} />
            <DialogFooter>
              <Button onClick={handlePasswordDisable} disabled={disableMfa.isPending}>
                停用
              </Button>
            </DialogFooter>
          </>
        ) : (
          <DialogFooter>
            <Button onClick={handleOAuthDisable} disabled={initiateOAuth.isPending}>
              使用 {oauthProvider ? formatProviderName(oauthProvider) : "第三方账号"} 校验
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  )
}
