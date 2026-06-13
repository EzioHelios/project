import { useState } from "react"
import { toast } from "sonner"
import { AdminEmptyState, AdminPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { BackupCodesDisplay } from "@/components/mfa/backup-codes-display"
import { MfaDisableDialog } from "@/components/mfa/mfa-disable-dialog"
import { MfaSetupDialog } from "@/components/mfa/mfa-setup-dialog"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { SkeletonCard } from "@/components/ui/skeleton"
import { useMfaStatus, useRegenerateBackupCodes } from "@/lib/api/hooks/auth"

export function MfaSection() {
  const { data, isLoading, isError } = useMfaStatus()
  const regenerate = useRegenerateBackupCodes()
  const [regenOpen, setRegenOpen] = useState(false)
  const [regenPassword, setRegenPassword] = useState("")
  const [regenCodes, setRegenCodes] = useState<string[] | null>(null)

  if (isLoading) {
    return <SkeletonCard />
  }

  if (isError || !data) {
    return (
      <AdminPanel title="多因素认证">
        <AdminEmptyState title="多因素认证状态加载失败" className="min-h-28" />
      </AdminPanel>
    )
  }

  const handleRegenerate = async () => {
    if (!regenPassword) {
      toast.error("请输入密码后再重新生成备用码")
      return
    }
    try {
      const result = await regenerate.mutateAsync(regenPassword)
      setRegenCodes(result.codes ?? [])
    } catch (error) {
      toast.error("备用码重新生成失败", {
        description: error instanceof Error ? error.message : "请稍后重试",
      })
    }
  }

  return (
    <AdminPanel title="多因素认证" contentClassName="space-y-4">
      <MetricStrip className="xl:grid-cols-2">
        <MetricTile label="认证状态" value={data.enabled ? "已启用" : "未启用"} tone={data.enabled ? "success" : "warning"} />
        <MetricTile label="备用码剩余" value={data.backupCodesRemaining ?? "-"} />
      </MetricStrip>
      <div className="border-border/70 border-t pt-4">
        {data.enabled ? (
          <div className="flex flex-wrap gap-2">
            <MfaDisableDialog />
            <Button variant="outline" onClick={() => setRegenOpen(true)}>
              重新生成备用码
            </Button>
          </div>
        ) : (
          <MfaSetupDialog />
        )}
      </div>
      <Dialog open={regenOpen} onOpenChange={setRegenOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>重新生成备用码</DialogTitle>
            <DialogDescription>输入当前密码后生成新的备用码，旧备用码将失效。</DialogDescription>
          </DialogHeader>
          {regenCodes ? (
            <BackupCodesDisplay codes={regenCodes} />
          ) : (
            <Input type="password" placeholder="当前密码" value={regenPassword} onChange={(event) => setRegenPassword(event.target.value)} />
          )}
          <DialogFooter>
            {regenCodes ? (
              <Button onClick={() => setRegenOpen(false)}>完成</Button>
            ) : (
              <Button onClick={handleRegenerate} disabled={regenerate.isPending}>
                重新生成
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AdminPanel>
  )
}
