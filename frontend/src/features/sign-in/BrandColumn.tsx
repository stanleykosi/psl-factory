// The brand column of the public pages (sign-in, set-up, recovery): wordmark, the three agents, one line.
export function BrandColumn() {
  return (
    <aside className="signin-brand psl-on-dark">
      <span className="signin-wordmark">PSL FACTORY</span>
      <div className="signin-agents" aria-hidden="true">
        {/* eslint-disable-next-line @next/next/no-img-element -- fixed mascot assets from public/agents */}
        <img src="/agents/tola-idle.png" alt="" height={220} />
        {/* eslint-disable-next-line @next/next/no-img-element -- fixed mascot assets from public/agents */}
        <img src="/agents/chidi-idle.png" alt="" height={210} />
        {/* eslint-disable-next-line @next/next/no-img-element -- fixed mascot assets from public/agents */}
        <img src="/agents/zainab-idle.png" alt="" height={215} />
      </div>
      <p className="signin-tagline">Work you can see moving, from first draft to verified.</p>
    </aside>
  );
}
