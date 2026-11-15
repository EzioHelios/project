import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"

export function BigscreenDemoNotice({ userId }: { userId: string }) {
  const storageKey = `bigscreen-demo-notice:v1:${userId}`
  const [open, setOpen] = useState(() => sessionStorage.getItem(storageKey) !== "acknowledged")

  function onOpenChange(value: boolean) {
    setOpen(value)
    if (!value) sessionStorage.setItem(storageKey, "acknowledged")
  }

  return (
    <>
      <button type="button" className="bigscreen-demo-notice-trigger" onClick={() => setOpen(true)}>
        定制演示
      </button>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>定制大屏演示</DialogTitle>
            <DialogDescription className="pt-2 leading-relaxed">
              当前大屏使用虚拟基地和演示数据，展示定制效果。正式项目的页面布局、三维场景和展示指标按双方确认的方案实施。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => onOpenChange(false)}>了解，进入大屏</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
