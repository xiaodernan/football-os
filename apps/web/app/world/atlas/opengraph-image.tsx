/**
 * The Atlas share card — the constellation, digits-free.
 */

import { ImageResponse } from "next/og";

export const alt = "FOOTBALL OS";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const dynamic = "force-static";

import enMessages from "../../../messages/en.json";

const kicker = enMessages.worldAtlas.eyebrow.toUpperCase();
const tag = enMessages.worldAtlas.ogTag;

const BG = "#0b1118";
const PAPER = "#f0ede6";
const GOLD = "#d8b56b";
const SUBTLE = "#97a0a8";
const LINE = "rgba(240, 237, 230, 0.09)";

const STAR_POINTS = [
  [60, 140], [190, 250], [330, 210], [460, 320], [600, 180], [720, 260], [850, 120], [1010, 220], [1150, 90],
];
const CONSTELLATION = STAR_POINTS.map((p) => p.join(",")).join(" ");

export default function AtlasOpenGraphImage() {
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

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 16, letterSpacing: "0.3em", textTransform: "uppercase", fontWeight: 700, color: SUBTLE, display: "flex" }}>FOOTBALL OS</div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", border: `1px solid ${GOLD}66`, borderRadius: 8, padding: "5px 12px" }}>
            <span style={{ fontSize: 13, color: GOLD, fontWeight: 700, letterSpacing: "0.24em", display: "flex" }}>{kicker}</span>
          </div>
        </div>

        <svg width="100%" height="260" viewBox="0 0 1200 380">
          <polyline points={CONSTELLATION} fill="none" stroke={GOLD} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" opacity="0.85" />
          {STAR_POINTS.map(([x, y], index) => (
            <circle key={index} cx={x} cy={y} r={index === 4 ? 9 : 5} fill={PAPER} opacity={index === 4 ? 1 : 0.85} />
          ))}
        </svg>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <div style={{ fontSize: 16, color: SUBTLE, letterSpacing: "0.08em", display: "flex" }}>{tag}</div>
          <div style={{ fontSize: 12, color: SUBTLE, letterSpacing: "0.3em", display: "flex" }}>FOOTBALL</div>
        </div>
      </div>
    ),
    { ...size },
  );
}
