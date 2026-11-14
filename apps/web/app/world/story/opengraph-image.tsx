/**
 * The season's story — the share card for /world/story.
 *
 * Tokens-only poster, same contract the almanac and duel cards keep: one product token, one
 * roman numeral chord, no language beyond what the gate whitelists. The card says the page
 * exists — three chapters, one stored world — and nothing else.
 */

import { ImageResponse } from "next/og";

export const alt = "FOOTBALL OS";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const dynamic = "force-static";

const ACCENT = "#35f0a4";
const BG = "#10151a";
const PAPER = "#f0ede6";
const SUBTLE = "#97a0a8";
const GOLD = "#d8b56b";

export default function StoryOpenGraphImage() {
  const label = (color: string, textAlign: "left" | "right") =>
    ({
      fontSize: 16,
      letterSpacing: "0.3em",
      textTransform: "uppercase" as const,
      fontWeight: 700,
      color,
      textAlign,
      display: "flex",
    }) as const;

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
          padding: "52px 60px",
          overflow: "hidden",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={label(SUBTLE, "left")}>FOOTBALL OS</div>
          <div style={label(GOLD, "right")}>STORY</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 22 }}>
            {["I", "II", "III"].map((n) => (
              <div
                key={n}
                style={{
                  fontSize: 120,
                  lineHeight: 0.9,
                  fontWeight: 800,
                  letterSpacing: "-0.06em",
                  color: "transparent",
                  WebkitTextStroke: `2px ${GOLD}88`,
                }}
              >
                {n}
              </div>
            ))}
          </div>
          <div style={{ fontSize: 132, lineHeight: 0.92, fontWeight: 800, letterSpacing: "-0.05em", color: PAPER }}>
            STORY
          </div>
          <div style={{ height: 6, width: 360, background: `linear-gradient(90deg, ${ACCENT} 0%, ${GOLD} 60%, transparent 100%)` }} />
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 15, letterSpacing: "0.24em", textTransform: "uppercase", fontWeight: 700, color: SUBTLE }}>
            2026/27
          </div>
          <div style={{ fontSize: 15, letterSpacing: "0.24em", textTransform: "uppercase", fontWeight: 700, color: GOLD }}>
            SEASON
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}
