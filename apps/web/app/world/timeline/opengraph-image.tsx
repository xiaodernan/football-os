/**
 * The Timeline share card — the season matchday by matchday.
 * Static typographic card: no API call, so the build never waits on a runtime.
 */

import { ImageResponse } from "next/og";

export const alt = "FOOTBALL OS";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const dynamic = "force-static";

const ACCENT = "#d8b56b";
const BG = "#10151a";
const PAPER = "#f0ede6";
const SUBTLE = "#97a0a8";
const LINE = "rgba(240, 237, 230, 0.09)";

// a hardening curve, not figures — the page owns the numbers
const BARS = [18, 14, 22, 18, 27, 31, 31, 34, 36, 40, 41, 41, 43, 46];

export default function TimelineOpenGraphImage() {
  const max = Math.max(...BARS);
  return new ImageResponse(
    (
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          background: BG,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "44px 56px 42px",
          overflow: "hidden",
        }}
      >
        <div style={{ position: "absolute", top: -130, right: -130, width: 430, height: 430, borderRadius: "50%", border: `1px solid ${LINE}`, display: "flex" }} />
        <div style={{ position: "absolute", bottom: -130, left: -130, width: 430, height: 430, borderRadius: "50%", border: `1px solid ${LINE}`, display: "flex" }} />

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 16, letterSpacing: "0.3em", textTransform: "uppercase", fontWeight: 700, color: SUBTLE, display: "flex" }}>FOOTBALL OS</div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", border: `1px solid ${ACCENT}66`, borderRadius: 8, padding: "5px 12px" }}>
            <span style={{ fontSize: 13, letterSpacing: "0.26em", color: ACCENT, fontWeight: 700, display: "flex" }}>1–14</span>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 12, height: 150 }}>
            {BARS.map((bar, index) => (
              <div
                key={index}
                style={{
                  flex: 1,
                  height: `${(bar / max) * 100}%`,
                  borderRadius: 4,
                  background: index === BARS.length - 1 ? ACCENT : "rgba(240, 237, 230, 0.16)",
                  display: "flex",
                }}
              />
            ))}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 120, letterSpacing: "-0.04em", fontWeight: 800, color: PAPER, lineHeight: 0.95 }}>23</div>
        </div>
      </div>
    ),
    { ...size },
  );
}
