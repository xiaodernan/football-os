import { ImageResponse } from "next/og";

import enMessages from "../../../messages/en.json";

export const alt = "FOOTBALL OS";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const dynamic = "force-static";

const kicker = enMessages.worldRealBook.eyebrow.toUpperCase();
const ground = "1986 — 2024";

const BG = "#10151a";
const PAPER = "#f0ede6";
const GOLD = "#d8b56b";
const SUBTLE = "#97a0a8";
const LINE = "rgba(240, 237, 230, 0.09)";

export default function RealBookOpenGraphImage() {
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
          <div style={{ display: "flex", gap: 10, alignItems: "center", border: `1px solid ${GOLD}66`, borderRadius: 8, padding: "5px 12px" }}>
            <span style={{ fontSize: 13, color: GOLD, fontWeight: 700, letterSpacing: "0.24em", display: "flex" }}>{kicker}</span>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ display: "flex", alignItems: "baseline", fontSize: 170, fontWeight: 800, color: PAPER, lineHeight: 0.95, letterSpacing: "-0.03em" }}>
            12
          </div>
          <div style={{ height: 3, background: GOLD, width: "34%" }} />
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <div style={{ fontSize: 16, color: SUBTLE, letterSpacing: "0.08em", display: "flex" }}>{ground}</div>
          <div style={{ fontSize: 12, color: SUBTLE, letterSpacing: "0.3em", display: "flex" }}>{kicker}</div>
        </div>
      </div>
    ),
    { ...size },
  );
}
