import { cva, type VariantProps } from "class-variance-authority"
import type * as React from "react"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground shadow-sm",
        secondary: "border-transparent bg-secondary text-secondary-foreground shadow-sm",
        outline: "text-foreground",
        destructive: "border-transparent bg-destructive text-destructive-foreground shadow-sm",
        success: "border-[hsl(var(--status-success))]/30 bg-[hsl(var(--status-success))]/10 text-[hsl(var(--status-success-foreground-admin))]",
        warning: "border-[hsl(var(--status-warning))]/35 bg-[hsl(var(--status-warning))]/12 text-[hsl(var(--status-warning-foreground-admin))]",
        info: "border-[hsl(var(--status-info))]/30 bg-[hsl(var(--status-info))]/10 text-[hsl(var(--status-info-foreground-admin))]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

type BadgeProps = React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof badgeVariants>

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div data-slot="badge" className={cn(badgeVariants({ variant, className }))} {...props} />
}

export { Badge, badgeVariants }
