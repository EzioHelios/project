import type * as React from "react"
import { useEffect, useMemo, useRef, useState } from "react"

import type { BigscreenMediaItem } from "@/lib/bigscreen/types"
import { cn } from "@/lib/utils"

export function BigscreenCountUp({
  value,
  formatter = (next) => next.toLocaleString("zh-CN", { maximumFractionDigits: 2 }),
}: {
  value: number
  formatter?: (value: number) => string
}) {
  const [displayValue, setDisplayValue] = useState(value)
  const previousValueRef = useRef(value)

  useEffect(() => {
    const start = previousValueRef.current
    const end = value
    const duration = 650
    const startedAt = performance.now()
    let frameId = 0

    const frame = (now: number) => {
      const progress = Math.min((now - startedAt) / duration, 1)
      const eased = 1 - (1 - progress) * (1 - progress)
      setDisplayValue(start + (end - start) * eased)
      if (progress < 1) {
        frameId = requestAnimationFrame(frame)
      }
    }

    previousValueRef.current = value
    frameId = requestAnimationFrame(frame)

    return () => window.cancelAnimationFrame(frameId)
  }, [value])

  return <>{formatter(displayValue)}</>
}

export function useAutoIndex(length: number, intervalMs = 5000) {
  const [activeIndex, setActiveIndex] = useState(0)

  useEffect(() => {
    if (length <= 1) {
      setActiveIndex(0)
      return
    }

    const timer = window.setInterval(() => {
      setActiveIndex((current) => (current + 1) % length)
    }, intervalMs)

    return () => window.clearInterval(timer)
  }, [intervalMs, length])

  return { activeIndex, setActiveIndex }
}

export function BigscreenAutoCarousel({
  items,
  emptyLabel,
  captionClassName,
  renderContent,
}: {
  items: BigscreenMediaItem[]
  emptyLabel: string
  captionClassName?: string
  renderContent?: (item: BigscreenMediaItem) => React.ReactNode
}) {
  const { activeIndex, setActiveIndex } = useAutoIndex(items.length)
  const activeItem = items[activeIndex]

  if (!activeItem) {
    return <div className="flex h-full items-center justify-center rounded-[20px] border border-dashed border-white/10 bg-white/[0.03] text-sm text-white/42">{emptyLabel}</div>
  }

  return (
    <div className="bigscreen-carousel">
      <div className="bigscreen-carousel-frame">
        {renderContent ? (
          renderContent(activeItem)
        ) : activeItem.image_url ? (
          <img src={activeItem.image_url} alt={activeItem.title} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-white/40">暂无图片</div>
        )}
        <div className={cn("absolute inset-x-0 bottom-0 bg-[linear-gradient(180deg,transparent,rgba(4,11,21,0.94))] px-5 pb-5 pt-10", captionClassName)}>
          <div className="text-[18px] font-semibold text-white">{activeItem.title}</div>
          <div className="mt-2 text-sm leading-6 text-white/62">{activeItem.description || "内容待补充"}</div>
        </div>
        <div className="bigscreen-carousel-dots">
          {items.map((item, index) => (
            <button type="button" key={item.id} className="bigscreen-carousel-dot" data-active={index === activeIndex} onClick={() => setActiveIndex(index)} />
          ))}
        </div>
      </div>
    </div>
  )
}

export function BigscreenScrollBoard<T>({
  rows,
  headers,
  columns,
  rowHeight = 58,
  visibleRows = 5,
  emptyLabel,
  getRowKey,
  renderRow,
}: {
  rows: T[]
  headers: string[]
  columns: string
  rowHeight?: number
  visibleRows?: number
  emptyLabel: string
  getRowKey: (row: T, index: number) => string
  renderRow: (row: T, index: number) => React.ReactNode
}) {
  const duplicatedRows = useMemo(() => {
    if (rows.length <= visibleRows) {
      return rows
    }
    return [...rows, ...rows]
  }, [rows, visibleRows])
  const shouldAnimate = rows.length > visibleRows
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    if (!shouldAnimate) {
      setOffset(0)
      return
    }

    const timer = window.setInterval(() => {
      setOffset((current) => {
        const next = current + 1
        return next >= rows.length ? 0 : next
      })
    }, 2600)

    return () => window.clearInterval(timer)
  }, [rows.length, shouldAnimate])

  if (rows.length === 0) {
    return <div className="flex h-full items-center justify-center rounded-[20px] border border-dashed border-white/10 bg-white/[0.03] text-sm text-white/42">{emptyLabel}</div>
  }

  return (
    <div className="bigscreen-scroll-board h-full">
      <div className="bigscreen-scroll-board-header" style={{ gridTemplateColumns: columns }}>
        {headers.map((header) => (
          <div key={header}>{header}</div>
        ))}
      </div>
      <div className="bigscreen-scroll-board-body" style={{ height: `${rowHeight * visibleRows}px` }}>
        <div
          className="bigscreen-scroll-board-inner"
          style={{
            transform: `translateY(-${offset * rowHeight}px)`,
            transition: shouldAnimate ? "transform 520ms ease" : undefined,
          }}
        >
          {duplicatedRows.map((row, index) => (
            <div
              key={`${getRowKey(row, index % rows.length)}-${Math.floor(index / rows.length)}`}
              className="bigscreen-scroll-board-row"
              style={{ gridTemplateColumns: columns, minHeight: `${rowHeight}px` }}
            >
              {renderRow(row, index % rows.length)}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
