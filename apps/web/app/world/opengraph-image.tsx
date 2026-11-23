/**
 * The world's own card — the door every world link previews.
 *
 * The collage is not an image the world built; next/og draws it at request time. The shape is the
 * almanac family's shape — one titan product word, a row of stat tokens from the duel's own grammar,
 * and a footer row pinned to the season. No prose; no token outside the stat-row set.
 */

import { ImageResponse } from "next/og";

export const alt = "FOOTBALL OS";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const dynamic = "force-static";

const ACCENT = "#35f0a4";
const GOLD = "#d8b56b";
const BG = "#10151a";
const PAPER = "#f0ede6";
const SUBTLE = "#97a0a8";
const LINE = "rgba(240, 237, 230, 0.09)";

export default function WorldOpenGraphImage() {
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
        <div style={{ position: "absolute", right: -110, top: -110, width: 420, height: 420, borderRadius: "50%", border: `1px solid ${LINE}`, display: "flex" }} />
        <div style={{ position: "absolute", left: -120, bottom: -140, width: 400, height: 400, borderRadius: "50%", border: `1px solid ${LINE}`, display: "flex" }} />

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 16, letterSpacing: "0.3em", textTransform: "uppercase", fontWeight: 700, color: SUBTLE, display: "flex" }}>FOOTBALL OS</div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", border: `1px solid ${ACCENT}66`, borderRadius: 8, padding: "5px 12px" }}>
            <span style={{ fontSize: 13, letterSpacing: "0.26em", textTransform: "uppercase", color: ACCENT, fontWeight: 700, display: "flex" }}>WORLD</span>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div
            style={{
              fontSize: 190,
              lineHeight: 0.9,
              fontWeight: 800,
              letterSpacing: "-0.055em",
              color: PAPER,
              display: "flex",
            }}
          >
            WORLD
          </div>
          <div style={{ height: 6, width: 300, background: `linear-gradient(90deg, ${ACCENT} 0%, ${GOLD} 60%, transparent 100%)` }} />
          <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
            {["GLS", "AST", "INV", "OVR", "RAT", "CARDS"].map((t) => (
              <div
                key={t}
                style={{
                  minWidth: 64,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: "7px 12px",
                  border: `1px solid ${LINE}`,
                  borderRadius: 8,
                  color: SUBTLE,
                  fontSize: 15,
                  letterSpacing: "0.18em",
                  fontWeight: 800,
                }}
              >
                {t}
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 15, letterSpacing: "0.24em", color: SUBTLE, textTransform: "uppercase", fontWeight: 700, display: "flex" }}>SEASON 2026/27</div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ fontSize: 15, letterSpacing: "0.26em", color: GOLD, textTransform: "uppercase", fontWeight: 700, display: "flex" }}>XI</div>
            <span style={{ display: "flex", width: 10, height: 10, background: GOLD, transform: "rotate(45deg)" }} />
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}
