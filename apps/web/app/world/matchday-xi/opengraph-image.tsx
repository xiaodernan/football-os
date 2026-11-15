/**
 * The XI share card — the door a fan link settles on.
 *
 * Eleven shirt numbers in formation on the ember-black field, paper-white numerals and names
 * in place of prose: the card names no one but shows everything. Tokens-only vocabulary — the
 * duel, almanac and story families raised the bar, and this opens the formation too.
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
const LINE = "rgba(240, 237, 230, 0.09)";

const ROWS: { slots: number[] }[] = [
  { slots: [7, 9, 11] },
  { slots: [6, 8, 10] },
  { slots: [2, 4, 5, 3] },
  { slots: [1] },
];

export default function MatchdayXiOpenGraphImage() {
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
          padding: "40px 56px 44px",
          overflow: "hidden",
        }}
      >
        <div style={{ position: "absolute", top: -120, right: -120, width: 420, height: 420, borderRadius: "50%", border: `1px solid ${LINE}`, display: "flex" }} />
        <div style={{ position: "absolute", bottom: -120, left: -120, width: 420, height: 420, borderRadius: "50%", border: `1px solid ${LINE}`, display: "flex" }} />

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 16, letterSpacing: "0.3em", textTransform: "uppercase", fontWeight: 700, color: SUBTLE, display: "flex" }}>FOOTBALL OS</div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", border: `1px solid ${GOLD}66`, borderRadius: 8, padding: "5px 12px" }}>
            <span style={{ fontSize: 13, letterSpacing: "0.26em", textTransform: "uppercase", color: GOLD, fontWeight: 700, display: "flex" }}>4-3-3</span>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 18 }}>
          {ROWS.map((row, rowIndex) => (
            <div key={rowIndex} style={{ display: "flex", gap: 22 }}>
              {row.slots.map((n) => (
                <div
                  key={n}
                  style={{
                    width: 108,
                    height: 128,
                    borderRadius: "50%",
                    border: `2px solid ${n === 1 || n === 10 ? GOLD : LINE}`,
                    background: rowIndex === 0 ? "#151c22" : rowIndex === 3 ? "#151c22" : BG,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 2,
                  }}
                >
                  <div style={{ fontSize: 56, fontWeight: 800, lineHeight: 0.9, letterSpacing: "-0.04em", color: n === 1 || n === 10 ? GOLD : PAPER, display: "flex" }}>{n}</div>
                </div>
              ))}
            </div>
          ))}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 15, letterSpacing: "0.24em", color: SUBTLE, textTransform: "uppercase", fontWeight: 700, display: "flex" }}>SEASON</div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <span style={{ width: 8, height: 8, borderRadius: 4, background: ACCENT, display: "flex" }} />
            <div style={{ fontSize: 15, letterSpacing: "0.28em", color: GOLD, textTransform: "uppercase", fontWeight: 700, display: "flex" }}>XI</div>
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}
