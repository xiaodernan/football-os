/**
 * The picker's share card — what a link to /world/duel previews as before anyone reads it.
 *
 * The picker page is the product's public antenna; the picture it carries says what the page is
 * about in one glance: two corners, one ledger. No figures — the card advertises the question,
 * not an answer.
 */

import { ImageResponse } from "next/og";

export const alt = "FOOTBALL OS — pick two players, the ledger decides";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const dynamic = "force-static";

const ACCENT = "#35f0a4";
const INFO = "#5fa8ff";
const BG = "#10151a";
const PAPER = "#f0ede6";
const SUBTLE = "#97a0a8";
const GOLD = "#d8b56b";
const LINE = "rgba(240, 237, 230, 0.09)";

export default function DuelPickerOpenGraphImage() {
  const corner = (side: "left" | "right") => ({
    position: "absolute" as const,
    top: "12%",
    [side]: "-8%",
    width: "640px",
    height: "480px",
    background:
      side === "left"
        ? `radial-gradient(ellipse at center, ${ACCENT}18 0%, transparent 68%)`
        : `radial-gradient(ellipse at center, ${INFO}18 0%, transparent 68%)`,
  });

  const label = {
    fontSize: 17,
    letterSpacing: "0.28em",
    color: SUBTLE,
    textTransform: "uppercase" as const,
    fontWeight: 700,
    display: "flex",
  };

  const nameStyle = {
    fontSize: 118,
    lineHeight: 0.95,
    fontWeight: 800,
    letterSpacing: "-0.045em",
    color: PAPER,
  };

  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          width: "100%",
          height: "100%",
          padding: "42px 60px 48px",
          background: BG,
          fontFamily: "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div style={corner("left")} />
        <div style={corner("right")} />
        <div style={{ position: "absolute", inset: 0, left: "50%", width: "1px", background: LINE }} />

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", zIndex: 1 }}>
          <div style={label}>FOOTBALL OS</div>
          <div style={{ ...label, color: GOLD }}>THE WORLD'S LEDGER</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", flex: 1, zIndex: 1 }}>
          <div style={{ ...label, marginBottom: 26 }}>PICK ANY TWO FROM THE WORLD</div>
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 46 }}>
            <div style={nameStyle}>ONE</div>
            <div style={{ ...nameStyle, fontStyle: "italic", color: GOLD, fontWeight: 700 }}>v</div>
            <div style={nameStyle}>TWO</div>
          </div>
          <div style={{ ...label, marginTop: 30, color: PAPER, opacity: 0.85 }}>GOALS · ASSISTS · INVOLVEMENT · RATING · MINUTES · OVERALL · DISCIPLINE</div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", zIndex: 1 }}>
          <div style={{ fontSize: 19, fontWeight: 700, color: PAPER }}>Seven columns. One verdict.</div>
          <div style={{ ...label, color: "#6d7680" }}>SYNTHETIC DEMO WORLD</div>
        </div>
      </div>
    ),
    { ...size },
  );
}
