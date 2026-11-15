/**
 * The world article's share card — the desk they never asked for, printed on the world's own ink.
 *
 * One headline, one claim-class chip, one category in the gold rim — the article is the copy,
 * the card is the envelope. If the door cannot answer, the card degrades to a matches-only
 * unfurled instead of to a broken image.
 *
 * 1200×630, force-dynamic, sibling to the player/team posters.
 */

import { ImageResponse } from "next/og";

import { readWorld } from "@/lib/world";
import type { NewsDetail } from "@/lib/types";

export const alt = "FOOTBALL OS";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const dynamic = "force-dynamic";

const ACCENT = "#35f0a4";
const GOLD = "#d8b56b";
const BG = "#10151a";
const PAPER = "#f0ede6";
const SUBTLE = "#97a0a8";
const LINE = "rgba(240, 237, 230, 0.09)";

export default async function NewsArticleOpenGraphImage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const result = await readWorld<NewsDetail>(`/world/news/${encodeURIComponent(slug)}`).catch(() => null);
  const article = result?.ok ? result.data.article : null;

  const claimClass = article?.claim_class?.toUpperCase() ?? "DESK";
  const category = article?.category?.replace(/_/g, " ").toUpperCase() ?? "NEWS";
  const title = article?.title ?? "POSTER";

  const titleSize = title.length > 110 ? 56 : title.length > 84 ? 66 : title.length > 56 ? 78 : 96;
  const shown = title.length > 140 ? title.slice(0, 140).trim() + "…" : title;

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
          <div style={{ display: "flex", gap: 10, alignItems: "center", border: `1px solid ${GOLD}66`, borderRadius: 8, padding: "5px 12px" }}>
            <span style={{ fontSize: 13, letterSpacing: "0.26em", textTransform: "uppercase", color: GOLD, fontWeight: 700, display: "flex" }}>{category}</span>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ fontSize: 15, letterSpacing: "0.3em", textTransform: "uppercase", fontWeight: 700, color: ACCENT, display: "flex" }}>{claimClass}</div>
            <div style={{ width: 48, height: 1, background: `${ACCENT}55`, display: "flex" }} />
            <div style={{ fontSize: 13, letterSpacing: "0.24em", textTransform: "uppercase", fontWeight: 700, color: SUBTLE, display: "flex" }}>DESK</div>
          </div>
          <div
            style={{
              fontSize: titleSize,
              lineHeight: 1.04,
              fontWeight: 800,
              letterSpacing: "-0.035em",
              color: PAPER,
              display: "flex",
              maxWidth: 1080,
            }}
          >
            {shown}
          </div>
          <div style={{ height: 6, width: 300, background: `linear-gradient(90deg, ${ACCENT} 0%, ${GOLD} 60%, transparent 100%)` }} />
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 15, letterSpacing: "0.24em", color: SUBTLE, textTransform: "uppercase", fontWeight: 700, display: "flex" }}>SEASON 2026/27</div>
          <div style={{ fontSize: 15, letterSpacing: "0.26em", color: GOLD, textTransform: "uppercase", fontWeight: 700, display: "flex" }}>WORLD</div>
        </div>
      </div>
    ),
    { ...size },
  );
}
