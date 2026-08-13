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
      <div className="product-brand-mark" aria-hidden="true">
        {brandMarkUrl ? <img src={brandMarkUrl} alt="" className="size-full object-contain" /> : <span>{shortName}</span>}
      </div>
      <div className="product-brand-copy group-data-[collapsible=icon]:hidden">
        <div className="product-brand-name">{displayName}</div>
      </div>
    </div>
  )
}
