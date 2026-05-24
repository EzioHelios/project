import { useEffect, useMemo, useState } from "react"

import { BigscreenCountUp } from "@/components/bigscreen/motion"
import { BigscreenEmpty } from "@/components/bigscreen/panel"
import type { HuayiBigscreenListSection } from "@/lib/bigscreen/types"
import { cn } from "@/lib/utils"

function normalizeTone(tone?: string) {
  if (tone === "amber" || tone === "emerald") {
    return tone
  }
  return "cyan"
}

export function LifestyleSectionPanel({
  section,
  highlight = false,
  className,
  variant = "default",
  maxVisibleItems,
  autoRotate = false,
}: {
  section: HuayiBigscreenListSection | null | undefined
  highlight?: boolean
  className?: string
  variant?: "default" | "dense" | "rotating"
  maxVisibleItems?: number
  autoRotate?: boolean
}) {
  const items = section?.items ?? []
  const chunkSize = Math.max(1, maxVisibleItems ?? (items.length || 1))
  const pages = useMemo(() => {
    const result: HuayiBigscreenListSection["items"][] = []
    for (let index = 0; index < items.length; index += chunkSize) {
      result.push(items.slice(index, index + chunkSize))
    }
    return result
  }, [chunkSize, items])
  const [pageIndex, setPageIndex] = useState(0)

  useEffect(() => {
    if (!autoRotate || pages.length <= 1) {
      return
    }
    const timer = window.setInterval(() => {
      setPageIndex((current) => (current + 1) % pages.length)
    }, 4800)
    return () => window.clearInterval(timer)
  }, [autoRotate, pages.length])

  const visibleItems = pages[pageIndex % Math.max(pages.length, 1)] ?? []

  if (!section) {
    return <BigscreenEmpty label="暂无零碳生活数据" />
  }

  return (
    <div className={cn("bigscreen-lifestyle-section", className)} data-highlight={highlight} data-variant={variant}>
      <div className="bigscreen-lifestyle-section-title">{section.title}</div>
      <div className="bigscreen-lifestyle-section-list">
        {visibleItems.map((item, index) => (
          <article key={`${item.label}-${index}`} className="bigscreen-lifestyle-section-row" data-tone={normalizeTone(item.tone)} data-emphasis={highlight && index === 0}>
            <div className="bigscreen-lifestyle-section-label">{item.label}</div>
            <div className="bigscreen-lifestyle-section-main">
              <span className="bigscreen-lifestyle-section-value">{typeof item.value === "number" ? <BigscreenCountUp value={item.value} /> : item.value}</span>
              {item.unit ? <span className="bigscreen-lifestyle-section-unit">{item.unit}</span> : null}
            </div>
          </article>
        ))}
      </div>
      {autoRotate && pages.length > 1 ? (
        <div className="bigscreen-lifestyle-section-pagination" aria-hidden="true">
          {pages.map((page, index) => (
            <span key={`${section.id}-${page.map((item) => item.label).join("-")}`} className="bigscreen-lifestyle-section-dot" data-active={index === pageIndex} />
          ))}
        </div>
      ) : null}
    </div>
  )
}
