import type * as React from "react"

import { TabsList } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"

export function AdminTabsList({ className, ...props }: React.ComponentProps<typeof TabsList>) {
  return <TabsList className={cn("admin-tabs-list grid h-auto w-full grid-cols-[repeat(auto-fit,minmax(120px,1fr))] items-center justify-stretch", className)} {...props} />
}
