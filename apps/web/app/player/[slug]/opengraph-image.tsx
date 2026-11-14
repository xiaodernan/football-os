/**
 * The player's share card — the page their club link previews.
 *
 * 1200×630, the almanac/story families language: one big OVR, the name in
 * ember-white, one position chip in the gold rim, and a footer row that names
 * the product and the world's tournament. If the door cannot answer, the card
 * degrades to a tokens-only poster rather than to a broken image.
 */

import { ImageResponse } from "next/og";

import { readWorld } from "@/lib/world";
import type { PlayerDetail } from "@/lib/types";

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

export default async function PlayerOpenGraphImage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const result = await readWorld<PlayerDetail>(`/world/players/${encodeURIComponent(slug)}`).catch(() => null);
  const player = result?.ok ? result.data.player : null;

  if (!player) {
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
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 16, letterSpacing: "0.3em", textTransform: "uppercase", fontWeight: 700, color: SUBTLE, display: "flex" }}>FOOTBALL OS</div>
            <div style={{ fontSize: 16, letterSpacing: "0.3em", textTransform: "uppercase", fontWeight: 700, color: GOLD, display: "flex" }}>ST</div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            <div style={{ fontSize: 170, fontWeight: 800, lineHeight: 0.92, letterSpacing: "-0.05em", color: PAPER }}>POSTER</div>
            <div style={{ height: 6, width: 320, background: `linear-gradient(90deg, ${ACCENT} 0%, ${GOLD} 60%, transparent 100%)` }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 15, letterSpacing: "0.24em", color: SUBTLE, textTransform: "uppercase", fontWeight: 700, display: "flex" }}>SEASON</div>
            <div style={{ fontSize: 15, letterSpacing: "0.24em", color: GOLD, textTransform: "uppercase", fontWeight: 700, display: "flex" }}>PLAYER</div>
          </div>
        </div>
      ),
      { ...size },
    );
  }

  const nameSize = player.name.length > 16 ? 94 : player.name.length > 12 ? 112 : 132;

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
          padding: "44px 56px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            right: -110,
            top: -110,
            width: 420,
            height: 420,
            borderRadius: "50%",
            border: `1px solid ${LINE}`,
            display: "flex",
          }}
        />
        <div style={{ position: "absolute", left: -150, bottom: -170, width: 400, height: 400, borderRadius: "50%", border: `1px solid ${LINE}`, display: "flex" }} />

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 16, letterSpacing: "0.3em", textTransform: "uppercase", fontWeight: 700, color: SUBTLE, display: "flex" }}>FOOTBALL OS</div>
          <div style={{ fontSize: 16, letterSpacing: "0.3em", textTransform: "uppercase", fontWeight: 700, color: GOLD, display: "flex" }}>{player.position}</div>
        </div>

        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 36 }}>
          <div style={{ display: "flex", flexDirection: "column", minWidth: 0, maxWidth: 760 }}>
            <div style={{ fontSize: 18, letterSpacing: "0.26em", textTransform: "uppercase", color: SUBTLE, fontWeight: 700, display: "flex" }}>
              {(player.club?.name ?? player.nation).toUpperCase()}
            </div>
            <div style={{ fontSize: nameSize, lineHeight: 0.94, fontWeight: 800, letterSpacing: "-0.04em", color: PAPER, display: "flex", maxWidth: 720 }}>
              {player.name}
            </div>
            <div style={{ display: "flex", gap: 14, marginTop: 18, alignItems: "center" }}>
              <div
                style={{
                  padding: "6px 14px",
                  border: `1px solid ${ACCENT}66`,
                  borderRadius: 8,
                  color: ACCENT,
                  fontSize: 20,
                  fontWeight: 800,
                  letterSpacing: "0.06em",
                  display: "flex",
                }}
              >
                {player.overall} OVR
              </div>
              <div style={{ padding: "6px 14px", border: `1px solid ${GOLD}66`, borderRadius: 8, color: GOLD, fontSize: 14, fontWeight: 800, letterSpacing: "0.08em", display: "flex" }}>
                POT {player.potential}
              </div>
              <div style={{ color: SUBTLE, fontSize: 20, letterSpacing: "0.1em", display: "flex" }}>{player.age} · {player.nation}</div>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
            <div style={{ fontSize: 26, letterSpacing: "0.2em", color: SUBTLE, fontWeight: 700, display: "flex" }}>OVR</div>
            <div style={{ fontSize: 210, fontWeight: 800, lineHeight: 0.85, letterSpacing: "-0.06em", color: GOLD, display: "flex" }}>
              {player.overall}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ height: 6, width: 300, background: `linear-gradient(90deg, ${ACCENT} 0%, ${GOLD} 65%, transparent 100%)`, display: "flex" }} />
          <div style={{ fontSize: 14, letterSpacing: "0.28em", color: SUBTLE, textTransform: "uppercase", fontWeight: 700, display: "flex" }}>
            FOOTBALL OS
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}
