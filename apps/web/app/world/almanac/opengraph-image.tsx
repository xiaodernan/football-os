/**
 * The almanac's share card — the season, summed into one ember-gold picture.
 *
 * The share card keeps the gate's honest contract: nothing on it that the catalogues
 * don't already carry, no language model prompted to write it, just the stat codes
 * the duel page proves out. The card advertises the existence of the ledger — the page
 * renders the reason to open it.
 *
 * 1200×630, static, language-free tokens.
 */

import { ImageResponse } from "next/og";

export const alt = "FOOTBALL OS";
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

export default function AlmanacOpenGraphImage() {
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
          <div style={label(GOLD, "right")}>ALMANAC</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ fontSize: 186, lineHeight: 0.92, fontWeight: 800, letterSpacing: "-0.05em", color: PAPER }}>
            ALMANAC
          </div>
          <div style={{ height: 6, width: 320, background: `linear-gradient(90deg, ${ACCENT} 0%, ${GOLD} 60%, transparent 100%)` }} />
          <div style={{ fontSize: 34, letterSpacing: "0.44em", textTransform: "uppercase", fontWeight: 800, color: SUBTLE, marginTop: 12 }}>
            SEASON
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {["GLS", "AST", "INV", "RAT", "OVR", "CARDS"].map((t) => (
              <div
                key={t}
                style={{
                  padding: "9px 14px",
                  border: `1px solid ${t === "CARDS" ? "#ffc46b55" : `${t === "AST" ? INFO : ACCENT}55`}`,
                  borderRadius: 10,
                  color:
                    t === "CARDS" ? "#ffc46b" :
                    t === "AST" ? INFO :
                    t === "OVR" ? GOLD :
                    t === "RAT" ? "#bfe3ff" :
                    t === "INV" ? "#96ffd0" :
                    ACCENT,
                  fontSize: 28,
                  fontWeight: 800,
                  letterSpacing: "0.06em",
                }}
              >
                {t}
              </div>
            ))}
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}
