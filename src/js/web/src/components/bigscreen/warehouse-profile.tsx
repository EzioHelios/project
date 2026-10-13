import { ChevronLeft, ChevronRight, Expand, RefreshCw } from "lucide-react"
import { useEffect, useState } from "react"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { useAuthStore } from "@/lib/auth"
import { getBigscreenPhoto } from "@/lib/bigscreen/api"
import { useBigscreenIntro } from "@/lib/bigscreen/hooks"
import type { BigscreenInfoItem, BigscreenMediaItem } from "@/lib/bigscreen/types"

export function SitePhoto({ item }: { item: BigscreenMediaItem }) {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  const [attempt, setAttempt] = useState(0)
  return <PhotoContent key={`${teamId}:${item.id}:${attempt}`} item={item} retry={() => setAttempt((value) => value + 1)} />
}

function PhotoContent({ item, retry }: { item: BigscreenMediaItem; retry: () => void }) {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    let resource: string | undefined
    setUrl(null)
    setFailed(false)
    if (teamId)
      void getBigscreenPhoto(item.id, { teamId, signal: controller.signal })
        .then((blob) => {
          if (!controller.signal.aborted) {
            resource = URL.createObjectURL(blob)
            setUrl(resource)
          }
        })
        .catch(() => {
          if (!controller.signal.aborted) setFailed(true)
        })
    return () => {
      controller.abort()
      if (resource) URL.revokeObjectURL(resource)
    }
  }, [item.id, teamId])
  return (
    <figure className="warehouse-site-photo">
      {failed ? (
        <div role="alert">
          照片加载失败
          <button type="button" title="重试照片" aria-label="重试照片" onClick={retry}>
            <RefreshCw size={18} />
          </button>
        </div>
      ) : url ? (
        <img src={url} alt={item.title} onError={() => setFailed(true)} />
      ) : (
        <output>加载照片</output>
      )}
      <figcaption>{item.title}</figcaption>
    </figure>
  )
}

export function WarehouseGallery({ items }: { items: BigscreenMediaItem[] }) {
  const [region, setRegion] = useState("")
  const [index, setIndex] = useState(0)
  const photos = items.filter((item) => !region || item.title === region)
  const current = photos[index] ?? photos[0]
  if (!current) return null
  return (
    <section className="warehouse-site-gallery" aria-label="仓库现场实景">
      <div className="warehouse-photo-controls">
        <label>
          区域{" "}
          <select
            aria-label="实景区域"
            value={region}
            onChange={(event) => {
              setRegion(event.target.value)
              setIndex(0)
            }}
          >
            <option value="">全部区域</option>
            {[...new Set(items.map((item) => item.title))].map((title) => (
              <option key={title}>{title}</option>
            ))}
          </select>
        </label>
        <span>
          {index + 1} / {photos.length}
        </span>
        <button type="button" title="上一张" aria-label="上一张" disabled={index === 0} onClick={() => setIndex(index - 1)}>
          <ChevronLeft size={20} />
        </button>
        <button type="button" title="下一张" aria-label="下一张" disabled={index >= photos.length - 1} onClick={() => setIndex(index + 1)}>
          <ChevronRight size={20} />
        </button>
      </div>
      <SitePhoto key={current.id} item={current} />
    </section>
  )
}

export function WarehouseProfile({ facts }: { facts: BigscreenInfoItem[] }) {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return <ProfileContent key={teamId} facts={facts} />
}

function ProfileContent({ facts }: { facts: BigscreenInfoItem[] }) {
  const name = useAuthStore((state) => state.currentTeam?.name)
  const query = useBigscreenIntro()
  const photos = query.data?.data.company_gallery ?? []
  const [open, setOpen] = useState(false)
  const fields = [{ label: "仓库", value: name ?? "" }, ...facts]
  const details = (
    <dl className="warehouse-facts">
      {fields.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  )
  return (
    <div className="warehouse-profile-summary" data-has-photos={photos.length > 0}>
      <dl className="warehouse-facts">
        {fields.slice(0, photos.length ? 2 : 5).map((item) => (
          <div key={item.label}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
      {query.isError ? (
        <div role="alert">
          实景查询失败{" "}
          <button type="button" onClick={() => void query.refetch()}>
            重试
          </button>
        </div>
      ) : (
        photos[0] && (
          <div className="warehouse-photo-preview">
            <SitePhoto key={photos[0].id} item={photos[0]} />
          </div>
        )
      )}
      <button type="button" className="warehouse-profile-open" onClick={() => setOpen(true)}>
        <Expand size={15} />
        仓库概况{photos.length > 0 && <span> · {photos.length} 张实景</span>}
      </button>
      {open && (
        <Dialog open onOpenChange={setOpen}>
          <DialogContent aria-describedby={undefined} className={`warehouse-event-dialog warehouse-profile-dialog ${photos.length ? "has-photos" : ""}`}>
            <DialogTitle>{name} · 仓库概况</DialogTitle>
            {details}
            {photos.length > 0 && <WarehouseGallery items={photos} />}
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
