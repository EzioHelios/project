export function BigscreenDataState({ failed, retry }: { failed: boolean; retry: () => void }) {
  return (
    <div className="bigscreen-page">
      <div className="bigscreen-side-stack">
        <div className="bigscreen-info-card p-5 text-sm text-white/80" role={failed ? "alert" : "status"}>
          <p>{failed ? "数据加载失败" : "正在加载当前租户数据…"}</p>
          {failed ? (
            <button type="button" className="mt-3 text-cyan-100 underline" onClick={retry}>
              重新加载
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
