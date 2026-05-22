export function ScreenHeaderNavFrame() {
  return (
    <div className="bigscreen-screen-header-nav-frame" aria-hidden="true">
      <svg className="bigscreen-screen-header-nav-frame-art" viewBox="0 0 1920 32" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="headerNavBarFill" x1="0" y1="16" x2="1920" y2="16" gradientUnits="userSpaceOnUse">
            <stop stopColor="#5EE9FF" stopOpacity="0.16" />
            <stop offset="0.14" stopColor="#3C9FFF" stopOpacity="0.34" />
            <stop offset="0.5" stopColor="#1D4EA8" stopOpacity="0.56" />
            <stop offset="0.86" stopColor="#3C9FFF" stopOpacity="0.34" />
            <stop offset="1" stopColor="#5EE9FF" stopOpacity="0.16" />
          </linearGradient>
          <linearGradient id="headerNavBarGlow" x1="0" y1="0" x2="1920" y2="0" gradientUnits="userSpaceOnUse">
            <stop stopColor="#67EDFF" stopOpacity="0.42" />
            <stop offset="0.18" stopColor="#52C2FF" stopOpacity="0.82" />
            <stop offset="0.5" stopColor="#3B86FF" stopOpacity="0.96" />
            <stop offset="0.82" stopColor="#52C2FF" stopOpacity="0.82" />
            <stop offset="1" stopColor="#67EDFF" stopOpacity="0.42" />
          </linearGradient>
        </defs>

        <rect x="0" y="6" width="1920" height="20" fill="url(#headerNavBarFill)" />
        <rect x="0" y="0" width="1920" height="2" fill="url(#headerNavBarGlow)" />
        <rect x="0" y="30" width="1920" height="2" fill="url(#headerNavBarGlow)" fillOpacity="0.78" />
      </svg>
    </div>
  )
}
