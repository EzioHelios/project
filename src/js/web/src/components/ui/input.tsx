import type * as React from "react"

import { ChineseDateInput } from "@/components/ui/chinese-date-input"
import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  if (type === "date") {
    return <ChineseDateInput className={className} {...props} />
  }

  return (
    <input
      type={type}
      data-slot="input"
      lang={type === "datetime-local" || type === "time" || type === "month" ? "zh-CN" : undefined}
      className={cn(
        "flex h-10 w-full min-w-0 rounded-md border border-border/80 bg-card/86 px-3 py-2 text-base shadow-sm outline-none transition-[color,box-shadow,transform] duration-200 selection:bg-primary selection:text-primary-foreground file:inline-flex file:h-8 file:border-0 file:bg-transparent file:font-medium file:text-foreground file:text-sm placeholder:text-muted-foreground disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-60 md:text-sm dark:bg-input/45",
        "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/35 focus-visible:shadow-[0_0_0_1px_hsl(var(--ring)/0.2)]",
        "aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40",
        className,
      )}
      {...props}
    />
  )
}

export { Input }
