export function WidePanelFrame() {
  return (
    <div className="bigscreen-panel-svg-frame" aria-hidden="true">
      <svg className="bigscreen-panel-svg-frame-art" viewBox="0 0 1000 400" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="widePanelEdge" x1="0" y1="0" x2="1000" y2="400" gradientUnits="userSpaceOnUse">
            <stop stopColor="#3FCFFF" />
            <stop offset="0.55" stopColor="#2D7FFF" />
            <stop offset="1" stopColor="#18478E" />
          </linearGradient>
          <linearGradient id="widePanelTopGlow" x1="0" y1="0" x2="1000" y2="0" gradientUnits="userSpaceOnUse">
            <stop stopColor="#2F7EFF" stopOpacity="0.94" />
            <stop offset="0.55" stopColor="#49C8FF" stopOpacity="0.88" />
            <stop offset="1" stopColor="#2F7EFF" stopOpacity="0.94" />
          </linearGradient>
        </defs>

        <path d="M2 2H998V398H2V2Z" fill="none" stroke="url(#widePanelEdge)" strokeOpacity="0.42" strokeWidth="4" vectorEffect="non-scaling-stroke" />
        <path d="M0 0H1000V8H0V0Z" fill="url(#widePanelTopGlow)" />
        <path d="M0 0H74L52 42H0V0Z" fill="#58E0FF" fillOpacity="0.14" />
        <path d="M0 384H936L1000 320V400H0V384Z" fill="#5A99FF" fillOpacity="0.58" />
      </svg>
    </div>
  )
}
