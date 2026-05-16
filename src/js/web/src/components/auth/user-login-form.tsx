import { zodResolver } from "@hookform/resolvers/zod"
import { useNavigate } from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { Icons } from "@/components/icons"
import { Button } from "@/components/ui/button"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { useAuthStore } from "@/lib/auth"
import { DEFAULT_AUTH_REDIRECT } from "@/lib/redirect-utils"
import { type LoginFormData, loginFormSchema } from "@/lib/validation"

interface UserLoginFormProps extends React.HTMLAttributes<HTMLDivElement> {
  redirectUrl?: string | null
}

export function UserLoginForm({ className, redirectUrl, ...props }: UserLoginFormProps) {
  const navigate = useNavigate()
  const { login, isLoading } = useAuthStore()

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

  const onSubmit = async (data: LoginFormData) => {
    try {
      const result = await login(data.username, data.password)
      if (result.mfaRequired) {
        navigate({ to: "/mfa-challenge", search: { redirect: finalRedirect } })
        return
      }
      navigate({ to: finalRedirect })
    } catch (_error) {
      // Error is handled by useAuthStore
    }
  }

  return (
    <div className={className} {...props}>
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" autoComplete="on">
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
        </form>
      </Form>
    </div>
  )
}
