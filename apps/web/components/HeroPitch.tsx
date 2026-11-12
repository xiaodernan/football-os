/**
 * The home hero's signature: a tactical board that scans.
 *
 * No copy, no data, no client JavaScript — it is one `<svg>` and four CSS animations, so it costs the
 * page a paint and nothing else. Two decisions are deliberate:
 *
 * * **It carries no text.** Every string on this product comes from the message catalogues (§81), and a
 *   decorative drawing that printed "SCAN" would be a twentieth place to translate a picture. What it
 *   shows instead is the thing the product does — a player looking over a shoulder, the space that opens
 *   when they do, and the pass that space makes available.
 * * **It is a server component.** The animation is CSS, so the browser starts it on first paint; a
 *   client component would have hydrated first and animated second.
 *
 * `aria-hidden` is explicit: the drawing is the hero's atmosphere, and a screen reader that stopped to
 * describe eleven circles would be reading the wallpaper instead of the sentence beside it.
 */
export function HeroPitch() {
  return (
    <div className="hero-art" aria-hidden="true">
      <svg className="hero-pitch" viewBox="0 0 520 360" role="presentation" focusable="false">
        <defs>
          <linearGradient id="hp-sweep" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.32" />
            <stop offset="70%" stopColor="var(--accent)" stopOpacity="0.04" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="hp-pass" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.9" />
            <stop offset="100%" stopColor="var(--info)" stopOpacity="0.25" />
          </linearGradient>
          <radialGradient id="hp-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.5" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* the field */}
        <g className="hero-pitch__field">
          <rect x="14" y="14" width="492" height="332" rx="16" className="hero-pitch__line" />
          <line x1="260" y1="14" x2="260" y2="346" className="hero-pitch__line" />
          <circle cx="260" cy="180" r="52" className="hero-pitch__line" />
          <circle cx="260" cy="180" r="3" className="hero-pitch__dot" />
          <rect x="14" y="98" width="58" height="164" className="hero-pitch__line" />
          <rect x="14" y="140" width="22" height="80" className="hero-pitch__line" />
          <rect x="448" y="98" width="58" height="164" className="hero-pitch__line" />
          <rect x="484" y="140" width="22" height="80" className="hero-pitch__line" />
        </g>

        {/* the pass network: what the scan makes visible */}
        <g className="hero-pitch__net">
          <path d="M150 236 L246 168 L338 214" className="hero-pitch__pass" />
          <path d="M246 168 L372 120" className="hero-pitch__pass hero-pitch__pass--slow" />
          <path d="M150 236 L338 214" className="hero-pitch__pass hero-pitch__pass--slow" />
        </g>

        {/* the player being scanned, and the space they can see */}
        <g className="hero-pitch__subject">
          <circle cx="150" cy="236" r="46" fill="url(#hp-glow)" />
          <g className="hero-pitch__sweep">
            <path d="M150 236 L262 236 A112 112 0 0 0 229 157 Z" fill="url(#hp-sweep)" />
          </g>
          <circle cx="150" cy="236" r="14" className="hero-pitch__ring" />
          <circle cx="150" cy="236" r="14" className="hero-pitch__ring hero-pitch__ring--late" />
          <circle cx="150" cy="236" r="7" className="hero-pitch__node" />
        </g>

        {/* teammates: the options the scan finds */}
        <g className="hero-pitch__team">
          <circle cx="246" cy="168" r="6" className="hero-pitch__node hero-pitch__node--info" />
          <circle cx="338" cy="214" r="6" className="hero-pitch__node hero-pitch__node--info" />
          <circle cx="372" cy="120" r="6" className="hero-pitch__node hero-pitch__node--info" />
        </g>

        {/* opponents: the reason the scan matters */}
        <g className="hero-pitch__rivals">
          <circle cx="212" cy="212" r="5" className="hero-pitch__rival" />
          <circle cx="292" cy="138" r="5" className="hero-pitch__rival" />
          <circle cx="318" cy="252" r="5" className="hero-pitch__rival" />
        </g>
      </svg>
    </div>
  );
}
