export function ScreenHeaderNavTabFrame({ active }: { active: boolean }) {
  return (
    <div className="bigscreen-screen-header-tab-frame" aria-hidden="true" data-active={active}>
      <svg className="bigscreen-screen-header-tab-frame-art" viewBox="0 0 176 40" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id={active ? "navTabFillActive" : "navTabFillIdle"} x1="0" y1="20" x2="176" y2="20" gradientUnits="userSpaceOnUse">
            {active ? (
              <>
                <stop stopColor="#1A5FD0" stopOpacity="0.9" />
                <stop offset="0.52" stopColor="#103A84" stopOpacity="0.82" />
                <stop offset="1" stopColor="#0A224C" stopOpacity="0.9" />
              </>
            ) : (
              <>
                <stop stopColor="#102A5E" stopOpacity="0.5" />
                <stop offset="0.52" stopColor="#0A1B3D" stopOpacity="0.34" />
                <stop offset="1" stopColor="#08142B" stopOpacity="0.5" />
              </>
            )}
          </linearGradient>
          <linearGradient id={active ? "navTabEdgeActive" : "navTabEdgeIdle"} x1="0" y1="0" x2="176" y2="0" gradientUnits="userSpaceOnUse">
            {active ? (
              <>
                <stop stopColor="#6BE7FF" stopOpacity="0.98" />
                <stop offset="0.42" stopColor="#49A1FF" stopOpacity="0.92" />
                <stop offset="1" stopColor="#2B63C7" stopOpacity="0.88" />
              </>
            ) : (
              <>
                <stop stopColor="#62DFFF" stopOpacity="0.44" />
                <stop offset="0.42" stopColor="#3C92FF" stopOpacity="0.34" />
                <stop offset="1" stopColor="#2355A9" stopOpacity="0.28" />
              </>
            )}
          </linearGradient>
        </defs>

        <path d="M16 0H176L160 40H0L16 0Z" fill={`url(#${active ? "navTabFillActive" : "navTabFillIdle"})`} />
        <path d="M16 0H176L160 40H0L16 0Z" fill="none" stroke={`url(#${active ? "navTabEdgeActive" : "navTabEdgeIdle"})`} strokeWidth="2" vectorEffect="non-scaling-stroke" />
        <path d="M0 38H160V40H0V38Z" fill={`url(#${active ? "navTabEdgeActive" : "navTabEdgeIdle"})`} fillOpacity={active ? "0.92" : "0.56"} />
        {active ? <path d="M0 0H54L38 40H0L16 0Z" fill="#69E4FF" fillOpacity="0.16" /> : null}
      </svg>
    </div>
  )
}
