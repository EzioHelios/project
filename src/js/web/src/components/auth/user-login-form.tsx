import "altcha"
import { zodResolver } from "@hookform/resolvers/zod"
import { useNavigate } from "@tanstack/react-router"
import { useEffect, useRef, useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { Icons } from "@/components/icons"
import { Button } from "@/components/ui/button"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { usePublicConfig } from "@/hooks/use-public-config"
import { HumanVerificationRequiredError, type HumanVerificationSubmission, useAuthStore } from "@/lib/auth"
import { resolveHumanVerificationSubmission } from "@/lib/human-verification"
import { DEFAULT_AUTH_REDIRECT } from "@/lib/redirect-utils"
import { type LoginFormData, loginFormSchema } from "@/lib/validation"

interface UserLoginFormProps extends React.HTMLAttributes<HTMLDivElement> {
  redirectUrl?: string | null
}

type AltchaWidgetElement = HTMLElement & {
  reset?: () => void
}

export function UserLoginForm({ className, redirectUrl, ...props }: UserLoginFormProps) {
  const navigate = useNavigate()
  const { config } = usePublicConfig()
  const { login, isLoading } = useAuthStore()
  const formRef = useRef<HTMLFormElement | null>(null)
  const widgetRef = useRef<AltchaWidgetElement | null>(null)
  const [verification, setVerification] = useState<HumanVerificationSubmission | null>(null)
  const [showCaptcha, setShowCaptcha] = useState(false)

  // Use redirect URL or default to /home
  const finalRedirect = redirectUrl || DEFAULT_AUTH_REDIRECT

  const form = useForm<LoginFormData>({
    resolver: zodResolver(loginFormSchema),
    defaultValues: {
      username: "",
      password: "",
    },
    mode: "onBlur",
    reValidateMode: "onBlur",
  })

  useEffect(() => {
    const widget = widgetRef.current
    if (!widget) {
      return
    }

    const handleStateChange = (event: Event) => {
      const detail = (event as CustomEvent<{ payload?: string; state?: string }>).detail
      if (detail?.state === "verified" && detail.payload) {
        setVerification({
          provider: config.captchaProvider ?? "altcha-sentinel",
          payload: detail.payload,
        })
      } else if (detail?.state !== "verified") {
        setVerification(null)
      }
    }

    widget.addEventListener("statechange", handleStateChange)
    return () => widget.removeEventListener("statechange", handleStateChange)
  }, [config.captchaProvider])

  const onSubmit = async (data: LoginFormData, event?: React.BaseSyntheticEvent) => {
    try {
      const formElement = (event?.target as HTMLFormElement | null) ?? formRef.current
      const resolvedVerification = resolveHumanVerificationSubmission(formElement, verification, config.captchaProvider ?? "altcha-sentinel")

      if (showCaptcha && !resolvedVerification) {
        toast.error("请先完成验证码校验")
        return
      }

      const result = await login(data.username, data.password, resolvedVerification)
      if (result.mfaRequired) {
        navigate({ to: "/mfa-challenge", search: { redirect: finalRedirect } })
        return
      }
      navigate({ to: finalRedirect })
    } catch (error) {
      setVerification(null)
      widgetRef.current?.reset?.()
      if (error instanceof HumanVerificationRequiredError) {
        setShowCaptcha(true)
        toast.error("请先完成验证码校验后再登录")
      }
    }
  }

  return (
    <div className={className} {...props}>
      <Form {...form}>
        <form ref={formRef} onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" autoComplete="on">
          <FormField
            control={form.control}
            name="username"
            render={({ field }) => (
              <FormItem>
                <FormLabel>邮箱</FormLabel>
                <FormControl>
                  <Input placeholder="name@example.com" autoCapitalize="none" autoComplete="username" autoCorrect="off" {...field} disabled={isLoading} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>密码</FormLabel>
                <FormControl>
                  <Input placeholder="请输入密码" type="password" autoCapitalize="none" autoCorrect="off" autoComplete="current-password" {...field} disabled={isLoading} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <Button type="submit" className="mt-2 w-full" disabled={isLoading}>
            {isLoading && <Icons.spinner className="mr-2 h-4 w-4" />}
            登录
          </Button>

          {showCaptcha && config.captchaEnabled && config.captchaChallengeUrl ? (
            <div className="rounded-xl border border-border/60 bg-background/80 p-4">
              <p className="mb-3 text-sm text-muted-foreground">连续登录失败后需要完成人机验证。</p>
              <altcha-widget ref={widgetRef} challenge={config.captchaChallengeUrl} hidefooter />
            </div>
          ) : null}
        </form>
      </Form>
    </div>
  )
}
