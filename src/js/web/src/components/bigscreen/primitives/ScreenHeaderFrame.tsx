export function ScreenHeaderFrame() {
  return (
    <div className="bigscreen-screen-header-frame" aria-hidden="true">
      <svg className="bigscreen-screen-header-frame-art" viewBox="0 0 3840 194" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="headerShellFill" x1="0" y1="72" x2="3840" y2="72" gradientUnits="userSpaceOnUse">
            <stop stopColor="#10356D" stopOpacity="0.68" />
            <stop offset="0.28" stopColor="#0C2856" stopOpacity="0.62" />
            <stop offset="0.72" stopColor="#091E43" stopOpacity="0.58" />
            <stop offset="1" stopColor="#071732" stopOpacity="0.62" />
          </linearGradient>
          <linearGradient id="headerUtilityFill" x1="3048" y1="20" x2="3840" y2="120" gradientUnits="userSpaceOnUse">
            <stop stopColor="#0F2D60" stopOpacity="0.72" />
            <stop offset="1" stopColor="#081C3D" stopOpacity="0.64" />
          </linearGradient>
          <linearGradient id="headerEdgeLine" x1="0" y1="0" x2="3840" y2="0" gradientUnits="userSpaceOnUse">
            <stop stopColor="#53D2FF" stopOpacity="0.28" />
            <stop offset="0.36" stopColor="#409BFF" stopOpacity="0.22" />
            <stop offset="1" stopColor="#1A4B97" stopOpacity="0.18" />
          </linearGradient>
          <radialGradient id="headerBrandGlow" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(226 36) rotate(13) scale(264 126)">
            <stop stopColor="#44E5FF" stopOpacity="0.62" />
            <stop offset="0.48" stopColor="#44E5FF" stopOpacity="0.18" />
            <stop offset="1" stopColor="#41E7FF" stopOpacity="0" />
          </radialGradient>
        </defs>

        <path d="M0 18L28 0H3820L3840 18V194H0V18Z" fill="url(#headerShellFill)" />
        <path d="M3096 18H3820L3840 34V194H3012L3096 18Z" fill="url(#headerUtilityFill)" />
        <path d="M0 0H3840V3H0V0Z" fill="url(#headerEdgeLine)" />
        <path d="M0 18H1118L1210 0H1300L1186 144H1148L1224 122H0V18Z" fill="#5BE3FF" fillOpacity="0.1" />
        <path d="M1096 0H1300L1186 144H1148L1234 22L1096 0Z" fill="#49A9FF" fillOpacity="0.48" />
        <circle cx="226" cy="36" r="264" fill="url(#headerBrandGlow)" />
      </svg>
    </div>
  )
}
