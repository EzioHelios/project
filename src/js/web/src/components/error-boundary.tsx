import type { ErrorComponentProps } from "@tanstack/react-router"
import { useRouter } from "@tanstack/react-router"
import { AlertCircle, Home, RefreshCw } from "lucide-react"
import { useEffect } from "react"
import { AdminPanel } from "@/components/admin-ui"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

const moduleLoadErrorPatterns = ["Importing a module script failed", "Failed to fetch dynamically imported module", "error loading dynamically imported module"]

export function ErrorBoundary({ error, reset }: ErrorComponentProps) {
  const router = useRouter()

  const errorMessage = error instanceof Error ? error.message : "An unexpected error occurred"
  const isModuleLoadError = moduleLoadErrorPatterns.some((pattern) => errorMessage.includes(pattern))

  useEffect(() => {
    if (!isModuleLoadError) return

    const retryKey = `module-load-retry:${window.location.pathname}`
    if (window.sessionStorage.getItem(retryKey) === "1") return

    window.sessionStorage.setItem(retryKey, "1")
    window.location.reload()
  }, [isModuleLoadError])

  return (
    <div className="flex min-h-screen w-full items-center justify-center px-4 py-12">
      <AdminPanel className="w-full max-w-md" contentClassName="space-y-4" title="页面加载失败">
        <div className="text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
            <AlertCircle className="h-6 w-6 text-destructive" />
          </div>
        </div>
        <Alert variant="destructive">
          <AlertDescription>{errorMessage}</AlertDescription>
        </Alert>
        <div className="flex flex-col gap-2">
          <Button onClick={reset} variant="default" className="w-full">
            <RefreshCw className="mr-2 h-4 w-4" />
            重试
          </Button>
          <Button onClick={() => router.navigate({ to: "/" })} variant="outline" className="w-full">
            <Home className="mr-2 h-4 w-4" />
            返回首页
          </Button>
        </div>
      </AdminPanel>
    </div>
  )
}
