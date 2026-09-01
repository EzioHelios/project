import { cn } from "@/lib/utils"

type ProductBrandProps = {
  displayName: string
  shortName: string
  brandMarkUrl?: string | null
  className?: string
}

export function ProductBrand({ displayName, shortName, brandMarkUrl, className }: ProductBrandProps) {
  return (
    <div className={cn("product-brand", className)}>
      <div className={cn("product-brand-mark", brandMarkUrl && "product-brand-mark--image")} aria-hidden="true">
        {brandMarkUrl ? <img src={brandMarkUrl} alt="" className="size-full object-contain" /> : <span>{shortName}</span>}
      </div>
      <div className={cn("product-brand-copy group-data-[collapsible=icon]:hidden", brandMarkUrl && "sr-only")}>
        <div className="product-brand-name">{displayName}</div>
      </div>
    </div>
  )
}
