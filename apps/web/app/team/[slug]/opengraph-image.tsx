/**
 * The club's share card — the door every fan link settles on.
 *
 * A crest disc in the club's brand colour closed around its short_name, the
 * club name in paper-white beside it, the manager and formation in the
 * muted line, capacity dressed as a number — an ember-black field with the
 * club's own colour in the heart of it. Tokens-only vocabulary: no sentence
 * appears anywhere on the card.
 */

import { ImageResponse } from "next/og";

import { readWorld } from "@/lib/world";
import type { TeamDetail } from "@/lib/types";

export const alt = "FOOTBALL OS";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const dynamic = "force-dynamic";

const ACCENT = "#35f0a4";
const BG = "#10151a";
const PAPER = "#f0ede6";
const SUBTLE = "#97a0a8";
const GOLD = "#d8b56b";
const LINE = "rgba(240, 237, 230, 0.09)";

export default async function TeamOpenGraphImage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const result = await readWorld<TeamDetail>(`/world/teams/${encodeURIComponent(slug)}`).catch(() => null);
  const team = result?.ok ? result.data.team : null;

  if (!team) {
    return new ImageResponse(
      (
        <div style={{ position: "relative", width: "100%", height: "100%", background: BG, display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "52px 60px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 16, letterSpacing: "0.3em", textTransform: "uppercase", fontWeight: 700, color: SUBTLE, display: "flex" }}>FOOTBALL OS</div>
            <div style={{ fontSize: 16, letterSpacing: "0.3em", textTransform: "uppercase", fontWeight: 700, color: GOLD, display: "flex" }}>CLUB</div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            <div style={{ fontSize: 170, fontWeight: 800, lineHeight: 0.92, letterSpacing: "-0.05em", color: PAPER, display: "flex" }}>POSTER</div>
            <div style={{ height: 6, width: 320, background: `linear-gradient(90deg, ${ACCENT} 0%, ${GOLD} 60%, transparent 100%)`, display: "flex" }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 15, letterSpacing: "0.24em", color: SUBTLE, textTransform: "uppercase", fontWeight: 700, display: "flex" }}>SEASON</div>
            <div style={{ fontSize: 15, letterSpacing: "0.24em", color: GOLD, textTransform: "uppercase", fontWeight: 700, display: "flex" }}>CLUB</div>
          </div>
        </div>
      ),
      { ...size },
    );
  }

  const longestWord = (name: string) => Math.max(...name.split(" ").map((w) => w.length));
  const nameSize = (name: string) => {
    const w = longestWord(name);
    if (w > 11) return 88;
    if (w > 9) return 104;
    if (w > 7) return 118;
    if (w > 5) return 128;
    return 140;
  };

  const initials = team.short_name.toUpperCase().slice(0, 3);
  const faction = team.formation;

  return new ImageResponse(
    (
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          background: BG,
          display: "flex",
          alignItems: "center",
          padding: "44px 56px",
          overflow: "hidden",
        }}
      >
        <div style={{ position: "absolute", top: -120, right: -120, width: 380, height: 380, borderRadius: "50%", border: `1px solid ${LINE}`, display: "flex" }} />
        <div style={{ position: "absolute", bottom: -120, left: -120, width: 380, height: 380, borderRadius: "50%", border: `1px solid ${LINE}`, display: "flex" }} />

        <div style={{ display: "flex", alignItems: "center", gap: 42, minWidth: 0 }}>
          <div
            style={{
              width: 210,
              height: 210,
              borderRadius: "50%",
              background: `radial-gradient(circle at 40% 38%, ${team.brand_color} 0%, ${team.brand_color} 62%, ${shade(team.brand_color) } 100%)`,
              border: `2px solid ${team.brand_color}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <div style={{ fontSize: 68, fontWeight: 800, letterSpacing: "-0.02em", color: PAPER, display: "flex", textShadow: "0 2px 18px rgba(0,0,0,0.35)" }}>
              {initials}
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 0, maxWidth: 440 }}>
            <div style={{ fontSize: 13, letterSpacing: "0.26em", textTransform: "uppercase", color: SUBTLE, fontWeight: 700, display: "flex" }}>
              {(team.competition?.name ?? team.nation).toUpperCase()}
            </div>
            <div style={{ fontSize: nameSize(team.name), lineHeight: 0.95, fontWeight: 800, letterSpacing: "-0.04em", color: PAPER, display: "flex" }}>
              {team.name}
            </div>
            <div style={{ display: "flex", gap: 12, marginTop: 8, alignItems: "center" }}>
              <div
                style={{
                  padding: "5px 13px",
                  border: `1px solid ${GOLD}55`,
                  borderRadius: 8,
                  fontSize: 21,
                  fontWeight: 800,
                  letterSpacing: "0.05em",
                  color: GOLD,
                  display: "flex",
                }}
              >
                {faction}
              </div>
              <div style={{ display: "flex", gap: 10, alignItems: "center", padding: "5px 13px", border: `1px solid ${ACCENT}44`, borderRadius: 8 }}>
                <span style={{ fontSize: 16, color: SUBTLE, display: "flex", letterSpacing: "0.05em" }}>CAP</span>
                <span style={{ fontSize: 17, fontWeight: 700, color: PAPER, display: "flex", fontVariantNumeric: "tabular-nums" }}>{team.capacity.toLocaleString("en-GB")}</span>
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, minWidth: 120, marginLeft: "auto" }}>
          <div style={{ fontSize: 22, letterSpacing: "0.26em", color: SUBTLE, fontWeight: 700, display: "flex" }}>OVR</div>
          <div style={{ fontSize: 170, fontWeight: 800, lineHeight: 0.9, letterSpacing: "-0.05em", color: GOLD, display: "flex" }}>{team.overall}</div>
          <div style={{ fontSize: 13, letterSpacing: "0.22em", color: SUBTLE, display: "flex", marginTop: 6 }}>FOOTBALL OS</div>
        </div>
      </div>
    ),
    { ...size },
  );
}

/** A 30% darker shade of the same colour — the bottom of the crest sits in shadow without introducing a new hue. */
function shade(hex: string): string {
  const match = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex.trim());
  if (!match) return hex;
  const factor = 0.66;
  const [, r, g, b] = match;
  const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v * factor)));
  return `rgb(${clamp(parseInt(r, 16))}, ${clamp(parseInt(g, 16))}, ${clamp(parseInt(b, 16))})`;
}
