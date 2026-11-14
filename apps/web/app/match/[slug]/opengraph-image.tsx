/**
 * The match-centre's share card — the page every argument and every plugging argument settles on.
 *
 * Two clubs, one ember-black field, one score. The card advertises the fixture, not a verdict:
 * the scorer lines belong to the feed, not to the poster. Tokens-only vocabulary — the idiom
 * the duel, almanac and player cards already speak.
 */

import { ImageResponse } from "next/og";

import { readWorld } from "@/lib/world";
import type { MatchDetail } from "@/lib/types";

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

export default async function MatchOpenGraphImage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const result = await readWorld<MatchDetail>(`/world/matches/${encodeURIComponent(slug)}`).catch(() => null);
  const match = result?.ok ? result.data.match : null;

  if (!match) {
    return new ImageResponse(
      (
        <div style={{ position: "relative", width: "100%", height: "100%", background: BG, display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "52px 60px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 16, letterSpacing: "0.3em", textTransform: "uppercase", fontWeight: 700, color: SUBTLE, display: "flex" }}>FOOTBALL OS</div>
            <div style={{ fontSize: 16, letterSpacing: "0.3em", textTransform: "uppercase", fontWeight: 700, color: GOLD, display: "flex" }}>SEASON</div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ fontSize: 140, fontWeight: 800, lineHeight: 0.9, letterSpacing: "-0.05em", color: PAPER }}>POSTER</div>
            <div style={{ height: 6, width: 320, background: `linear-gradient(90deg, ${ACCENT} 0%, ${GOLD} 60%, transparent 100%)` }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 15, letterSpacing: "0.24em", color: SUBTLE, textTransform: "uppercase", fontWeight: 700, display: "flex" }}>SEASON</div>
            <div style={{ fontSize: 15, letterSpacing: "0.24em", color: GOLD, textTransform: "uppercase", fontWeight: 700, display: "flex" }}>MATCH</div>
          </div>
        </div>
      ),
      { ...size },
    );
  }

  const played = match.home_goals !== null && match.away_goals !== null;
  const kickoff = match.kickoff_at ? new Date(match.kickoff_at) : null;
  const dateChip = kickoff ? `${kickoff.getUTCDate()}/${kickoff.getUTCMonth() + 1}/${kickoff.getUTCFullYear()}` : null;
  const longestWord = (name: string) => Math.max(...name.split(" ").map((w) => w.length));
  const nameSize = (name: string) => {
    const w = longestWord(name);
    if (w > 11) return 62;
    if (w > 9) return 72;
    if (w > 7) return 84;
    if (w > 6) return 98;
    if (w > 5) return 118;
    return 140;
  };

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
        <div style={{ position: "absolute", left: -140, top: -140, width: 380, height: 380, borderRadius: "50%", border: `1px solid ${LINE}`, display: "flex" }} />
        <div style={{ position: "absolute", right: -140, bottom: -140, width: 380, height: 380, borderRadius: "50%", border: `1px solid ${LINE}`, display: "flex" }} />

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 15, letterSpacing: "0.28em", textTransform: "uppercase", fontWeight: 700, color: SUBTLE, display: "flex", maxWidth: 620 }}>
            {(match.competition?.name ?? "WORLD").toUpperCase()}
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", border: `1px solid ${GOLD}55`, borderRadius: 8, padding: "5px 12px" }}>
            <span style={{ width: 8, height: 8, borderRadius: 4, background: GOLD, display: "flex" }} />
            <span style={{ fontSize: 13, letterSpacing: "0.26em", textTransform: "uppercase", color: GOLD, fontWeight: 700, display: "flex" }}>
              {match.round_label.replace(/^Matchday\s+/i, "MD ")}
            </span>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 28 }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", textAlign: "right", width: 360 }}>
            <div style={{ fontSize: nameSize(match.home?.name ?? ""), fontWeight: 800, lineHeight: 0.98, letterSpacing: "-0.04em", color: PAPER, display: "flex" }}>
              {match.home?.name ?? "—"}
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: 190, gap: 4 }}>
            {played ? (
              <>
                <div style={{ fontSize: 150, fontWeight: 800, lineHeight: 0.85, letterSpacing: "-0.04em", color: GOLD, display: "flex", fontVariantNumeric: "tabular-nums" }}>
                  {match.home_goals}–{match.away_goals}
                </div>
                <div style={{ fontSize: 15, letterSpacing: "0.3em", textTransform: "uppercase", color: SUBTLE, fontWeight: 700, display: "flex", marginTop: 10 }}>
                  FT
                </div>
              </>
            ) : (
              <>
                <div style={{ fontSize: 120, fontWeight: 800, lineHeight: 0.9, color: "transparent", WebkitTextStroke: `2px ${GOLD}99`, display: "flex" }}>VS</div>
                <div style={{ fontSize: 13, letterSpacing: "0.3em", textTransform: "uppercase", color: SUBTLE, fontWeight: 700, display: "flex", marginTop: 8 }}>
                  {dateChip ?? "WORLD"}
                </div>
              </>
            )}
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", width: 360 }}>
            <div style={{ fontSize: nameSize(match.away?.name ?? ""), fontWeight: 800, lineHeight: 0.98, letterSpacing: "-0.04em", color: PAPER, display: "flex" }}>
              {match.away?.name ?? "—"}
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
