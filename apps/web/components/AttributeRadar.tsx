/** Six-axis attribute radar. Pure SVG so it renders in server components with no client JS. */

import { useTranslations } from "next-intl";

export function AttributeRadar({
  values,
  size = 220,
  label,
}: {
  values: { key: string; label: string; value: number }[];
  size?: number;
  label?: string;
}) {
  const t = useTranslations("common");
  if (values.length < 3) return null;
  const centre = size / 2;
  const radius = centre - 34;
  const angle = (index: number) => (Math.PI * 2 * index) / values.length - Math.PI / 2;
  const point = (index: number, ratio: number) => {
    const a = angle(index);
    return [centre + Math.cos(a) * radius * ratio, centre + Math.sin(a) * radius * ratio] as const;
  };
  const polygon = values.map((item, index) => point(index, Math.max(0.04, Math.min(1, item.value / 99))).join(",")).join(" ");
  const rings = [0.25, 0.5, 0.75, 1];

  return (
    <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label ?? t("attributeProfile")} style={{ width: "100%", maxWidth: size, height: "auto" }}>
      {rings.map((ratio) => (
        <polygon
          key={ratio}
          fill="none"
          stroke="#1d293d"
          points={values.map((_, index) => point(index, ratio).join(",")).join(" ")}
        />
      ))}
      {values.map((item, index) => {
        const [x, y] = point(index, 1);
        return <line key={item.key} x1={centre} y1={centre} x2={x} y2={y} stroke="#17212f" />;
      })}
      <polygon fill="rgba(53, 240, 164, 0.16)" stroke="#35f0a4" strokeWidth={1.5} points={polygon} />
      {values.map((item, index) => {
        const [x, y] = point(index, 1.16);
        return (
          <text
            key={item.key}
            x={x}
            y={y}
            fill="#a9b7cc"
            fontSize={9}
            fontFamily="inherit"
            textAnchor={x > centre + 4 ? "start" : x < centre - 4 ? "end" : "middle"}
            dominantBaseline="middle"
          >
            {item.label}
          </text>
        );
      })}
      {values.map((item, index) => {
        const [x, y] = point(index, Math.max(0.04, Math.min(1, item.value / 99)));
        return <circle key={`dot-${item.key}`} cx={x} cy={y} r={2.6} fill="#35f0a4" />;
      })}
    </svg>
  );
}
