export function TallPanelFrame() {
  return (
    <div className="bigscreen-panel-svg-frame" aria-hidden="true">
      <svg className="bigscreen-panel-svg-frame-art" viewBox="0 0 496 656" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="tallPanelEdge" x1="0" y1="0" x2="496" y2="656" gradientUnits="userSpaceOnUse">
            <stop stopColor="#48D6FF" />
            <stop offset="0.52" stopColor="#2C82FF" />
            <stop offset="1" stopColor="#174489" />
          </linearGradient>
          <linearGradient id="tallPanelTopGlow" x1="0" y1="0" x2="496" y2="0" gradientUnits="userSpaceOnUse">
            <stop stopColor="#2F7EFF" stopOpacity="0.94" />
            <stop offset="0.55" stopColor="#49C8FF" stopOpacity="0.88" />
            <stop offset="1" stopColor="#2F7EFF" stopOpacity="0.94" />
          </linearGradient>
        </defs>

        <path d="M28 0H496V596L438 656H0V28L28 0Z" fill="none" stroke="url(#tallPanelEdge)" strokeOpacity="0.46" strokeWidth="4" vectorEffect="non-scaling-stroke" />
        <path d="M0 8L28 0H496V8H0Z" fill="url(#tallPanelTopGlow)" />
        <path d="M0 0H74L52 42H0V0Z" fill="#62E8FF" fillOpacity="0.16" />
        <path d="M0 28L28 0H0V28Z" fill="#5294FF" fillOpacity="0.72" />
        <path d="M438 656L496 596V656H438Z" fill="#5A99FF" fillOpacity="0.72" />
      </svg>
    </div>
  )
}
