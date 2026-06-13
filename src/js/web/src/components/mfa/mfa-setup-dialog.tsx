import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"
import { BackupCodesDisplay } from "@/components/mfa/backup-codes-display"
import { TotpInput } from "@/components/mfa/totp-input"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { useConfirmMfaSetup, useInitiateMfaSetup } from "@/lib/api/hooks/auth"
import type { MfaSetup } from "@/lib/generated/api"

interface MfaSetupDialogProps {
  disabled?: boolean
}

export function MfaSetupDialog({ disabled }: MfaSetupDialogProps) {
  const [open, setOpen] = useState(false)
  const [setup, setSetup] = useState<MfaSetup | null>(null)
  const [codes, setCodes] = useState<string[] | null>(null)
  const [code, setCode] = useState("")
  const initiate = useInitiateMfaSetup()
  const confirm = useConfirmMfaSetup()

  const isLoading = initiate.isPending || confirm.isPending

  useEffect(() => {
    if (!open) {
      setSetup(null)
      setCodes(null)
      setCode("")
      return
    }
    if (setup || initiate.isPending) {
      return
    }
    initiate
      .mutateAsync()
      .then((data) => setSetup(data))
      .catch((error) => {
        toast.error("无法启动多因素认证设置", {
          description: error instanceof Error ? error.message : "请稍后重试",
        })
      })
  }, [open, initiate, setup])

  const handleConfirm = async () => {
    if (!code || code.length < 6) {
      toast.error("请输入认证器中的 6 位验证码")
      return
    }
    try {
      const result = await confirm.mutateAsync(code)
      setCodes(result.codes ?? [])
    } catch (error) {
      toast.error("验证码校验失败", {
        description: error instanceof Error ? error.message : "请检查验证码后重试",
      })
    }
  }

  const qrContent = useMemo(() => {
    if (initiate.isPending || !setup) {
      return (
        <div className="space-y-4">
          <Skeleton className="h-44 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      )
    }
    return (
      <div className="space-y-4">
        <div className="flex justify-center rounded-lg border border-border/60 bg-white p-4">
          <img src={setup.qrCode} alt="多因素认证二维码" className="h-48 w-48" />
        </div>
        <div className="rounded-lg border border-border/60 bg-muted/30 px-4 py-3 font-mono text-sm">{setup.secret}</div>
        <TotpInput value={code} onChange={setCode} disabled={isLoading} autoFocus />
      </div>
    )
  }, [setup, initiate.isPending, code, isLoading])

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button disabled={disabled}>启用多因素认证</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>启用多因素认证</DialogTitle>
          <DialogDescription>使用认证器扫描二维码，然后输入 6 位验证码。</DialogDescription>
        </DialogHeader>
        {codes ? <BackupCodesDisplay codes={codes} /> : qrContent}
        <DialogFooter>
          {codes ? (
            <Button onClick={() => setOpen(false)}>完成</Button>
          ) : (
            <Button onClick={handleConfirm} disabled={isLoading || code.length < 6}>
              校验并完成
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
