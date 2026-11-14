/**
 * The records page — the share card for /world/records.
 *
 * Tokens-only, same contract the almanac and story cards keep: the product word, the
 * season-relative numeral set, no language beyond what the gate whitelists. Eight
 * marks, one stored world, one card.
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

export default function RecordsOpenGraphImage() {
  const label = (color: string, textAlign: "left" | "right") =>
    ({
      fontSize: 16,
      letterSpacing: "0.28em",
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
          <div style={label(GOLD, "right")}>RECORDS</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div
            style={{
              fontSize: 200,
              lineHeight: 0.9,
              fontWeight: 800,
              letterSpacing: "-0.06em",
              color: PAPER,
            }}
          >
            8
          </div>
          <div style={{ fontSize: 76, lineHeight: 1, fontWeight: 750, letterSpacing: "-0.03em", color: PAPER }}>
            RECORDS
          </div>
          <div style={{ height: 6, width: 330, background: `linear-gradient(90deg, ${ACCENT} 0%, ${GOLD} 65%, transparent 100%)` }} />
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
