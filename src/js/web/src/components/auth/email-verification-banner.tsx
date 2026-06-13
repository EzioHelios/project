import { useMutation } from "@tanstack/react-query"
import { AlertCircle, CheckCircle2, X } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/hooks/use-auth"
import { apiEmailVerificationRequestRequestVerification } from "@/lib/generated/api"

interface EmailVerificationBannerProps {
  dismissible?: boolean
  className?: string
}

export function EmailVerificationBanner({ dismissible = false, className }: EmailVerificationBannerProps) {
  const { user } = useAuth()
  const [isDismissed, setIsDismissed] = useState(false)
  const [lastSentAt, setLastSentAt] = useState<Date | null>(null)

  const { mutate: resendVerification, isPending } = useMutation({
    mutationFn: async () => {
      if (!user?.email) {
        throw new Error("当前账号未配置邮箱")
      }
      const response = await apiEmailVerificationRequestRequestVerification({
        body: { email: user.email },
      })
      if (response.error) {
        throw new Error((response.error as any).detail || "验证邮件发送失败")
      }
      return response.data
    },
    onSuccess: () => {
      setLastSentAt(new Date())
      toast.success("验证邮件已发送，请检查邮箱")
    },
    onError: (error: Error) => {
      toast.error(error.message || "验证邮件发送失败")
    },
  })

  const shouldHide = !user || user.isVerified || isDismissed
  if (shouldHide) {
    return null
  }

  const canResend = !lastSentAt || Date.now() - lastSentAt.getTime() > 60000 // 1 minute cooldown

  return (
    <Alert className={className} variant="warning">
      <AlertCircle className="h-4 w-4" />
      <AlertTitle className="flex items-center justify-between">
        <span>需要验证邮箱</span>
        {dismissible && (
          <Button variant="ghost" size="icon" className="h-4 w-4 p-0" onClick={() => setIsDismissed(true)}>
            <X className="h-3 w-3" />
          </Button>
        )}
      </AlertTitle>
      <AlertDescription className="mt-2">
        <p className="mb-2">
          请验证邮箱地址。验证链接已发送至 <strong>{user.email}</strong>。
        </p>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => resendVerification()} disabled={isPending || !canResend}>
            {isPending ? "发送中..." : "重新发送验证邮件"}
          </Button>
          {lastSentAt && !canResend && <span className="text-muted-foreground text-xs">请稍后再重新发送</span>}
        </div>
      </AlertDescription>
    </Alert>
  )
}

export function EmailVerificationSuccess() {
  return (
    <Alert variant="success">
      <CheckCircle2 className="h-4 w-4" />
      <AlertTitle>邮箱已验证</AlertTitle>
      <AlertDescription>当前账号邮箱已完成验证。</AlertDescription>
    </Alert>
  )
}
