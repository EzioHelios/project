import { useMemo } from "react"
import { toast } from "sonner"
import { AdminPanel } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"

interface BackupCodesDisplayProps {
  codes: string[]
  title?: string
  description?: string
}

export function BackupCodesDisplay({ codes, title = "Backup codes", description }: BackupCodesDisplayProps) {
  const formatted = useMemo(() => codes.filter(Boolean), [codes])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(formatted.join("\n"))
      toast.success("备用码已复制")
    } catch {
      toast.error("备用码复制失败")
    }
  }

  return (
    <AdminPanel
      title={title}
      description={description}
      actions={
        <Button variant="outline" size="sm" onClick={handleCopy}>
          复制
        </Button>
      }
    >
      <div className="grid gap-2 sm:grid-cols-2">
        {formatted.map((code) => (
          <div key={code} className="rounded-md border border-border/60 bg-muted/40 px-3 py-2 font-mono text-sm text-foreground">
            {code}
          </div>
        ))}
      </div>
    </AdminPanel>
  )
}
