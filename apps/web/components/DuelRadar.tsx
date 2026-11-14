/**
 * Two attribute profiles on one set of axes.
 *
 * The single-player radar lives in `AttributeRadar` and is left alone: it draws one polygon and owns its own
 * scale. A duel needs the opposite decision — both players measured against the **same** ring, or the picture
 * lies about who is ahead — so the axes are the union of the two profiles (the six the pair argues about most)
 * and every vertex is `value / 99` on a shared grid.
 *
 * Pure SVG, no client JS: this renders inside a server component like every other figure on the page.
 */

export type RadarAxis = { key: string; label: string; left: number; right: number };

export function DuelRadar({ axes, size = 300 }: { axes: RadarAxis[]; size?: number }) {
  if (axes.length < 3) return null;
  const centre = size / 2;
  const radius = centre - 46;
  const angle = (index: number) => (Math.PI * 2 * index) / axes.length - Math.PI / 2;
  const point = (index: number, ratio: number) => {
    const a = angle(index);
    return [centre + Math.cos(a) * radius * ratio, centre + Math.sin(a) * radius * ratio] as const;
  };
  const ratio = (value: number) => Math.max(0.04, Math.min(1, value / 99));
  const polygon = (side: "left" | "right") =>
    axes.map((axis, index) => point(index, ratio(axis[side])).join(",")).join(" ");

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="duel-radar" style={{ width: "100%", maxWidth: size, height: "auto" }}>
      {[0.25, 0.5, 0.75, 1].map((ring) => (
        <polygon key={ring} fill="none" stroke="#1d293d" points={axes.map((_, index) => point(index, ring).join(",")).join(" ")} />
      ))}
      {axes.map((axis, index) => {
        const [x, y] = point(index, 1);
        return <line key={`spoke-${axis.key}`} x1={centre} y1={centre} x2={x} y2={y} stroke="#17212f" />;
      })}
      <polygon className="duel-radar__shape duel-radar__shape--left" points={polygon("left")} />
      <polygon className="duel-radar__shape duel-radar__shape--right" points={polygon("right")} />
      {axes.map((axis, index) => {
        const [x, y] = point(index, 1.17);
        return (
          <text
            key={`label-${axis.key}`}
            x={x}
            y={y}
            fill="#a9b7cc"
            fontSize={9.5}
            fontFamily="inherit"
            textAnchor={x > centre + 4 ? "start" : x < centre - 4 ? "end" : "middle"}
            dominantBaseline="middle"
          >
            {axis.label}
          </text>
        );
      })}
    </svg>
  );
}
