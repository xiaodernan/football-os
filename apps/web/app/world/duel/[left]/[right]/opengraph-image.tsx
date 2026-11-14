/**
 * The duel's own share card — the picture a chat window shows before a stranger reads the page.
 *
 * 1200×630, generated at request time from the duel door itself. Three honest rules:
 * the card renders whether or not the API answers (a share image that 500s is worse than a plain one);
 * every figure on it is read from the API at request time, never typed into this file, so the card
 * cannot disagree with the page it previews; and nothing here guesses at a figure the world did not publish.
 *
 * The visual language follows the product's own duel page: the two corners tinted by their own accents,
 * the etched centre line, the mono ledger type at the bottom.
 */

import { ImageResponse } from "next/og";

import { apiBase } from "@/lib/api";
import type { DuelResult } from "@/lib/types";

export const alt = "FOOTBALL OS — the world's ledger, two footballers apart";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const dynamic = "force-dynamic";
export const revalidate = 0;

const ACCENT = "#35f0a4";
const INFO = "#5fa8ff";
const BG = "#10151a";
const PAPER = "#f0ede6";
const SUBTLE = "#97a0a8";
const GOLD = "#d8b56b";
const LINE = "rgba(240, 237, 230, 0.09)";

const PLACEHOLDER: string = "—";

function titleCaseName(input: string): string {
  // The slugs are lowercase hyphenated by construction; anything else passes through untouched.
  if (!/^[a-z]+(-[a-z]+)*$/.test(input)) return input;
  return input
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

async function loadDuel(left: string, right: string): Promise<DuelResult | null> {
  const url = new URL("/api/v1/world/duel", apiBase());
  url.searchParams.set("left", left);
  url.searchParams.set("right", right);
  try {
    const res = await fetch(url, { cache: "no-store", headers: { accept: "application/json" } });
    if (!res.ok) return null;
    const body = (await res.json()) as DuelResult;
    // The door answers a flat envelope with top-level `left`, `right` and `verdict`.
    // If the contract ever moved, the card degrades to the slugs it was asked for — never to a lie.
    return body && typeof body === "object" && "verdict" in body ? body : null;
  } catch {
    return null;
  }
}

function figure(value: number | null | undefined): string {
  if (value === null || value === undefined) return PLACEHOLDER;
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
}

const SHORT_LABELS: [key: string, label: string][] = [
  ["goals", "GLS"],
  ["assists", "AST"],
  ["involvement_per_90", "INV-90"],
  ["rating", "RAT"],
  ["minutes", "MIN"],
  ["overall", "OVR"],
  ["discipline", "CARDS"],
];

export default async function DuelOpenGraphImage({ params }: { params: Promise<{ left: string; right: string }> }) {
  const { left, right } = await params;
  const result = await loadDuel(left, right);

  const a = result?.left ?? null;
  const b = result?.right ?? null;
  const verdict = result?.verdict ?? null;
  const categories = result?.categories ?? [];

  const nameLeft = a?.player?.name ?? titleCaseName(left);
  const nameRight = b?.player?.name ?? titleCaseName(right);
  const overallLeft = a?.player?.overall ?? null;
  const overallRight = b?.player?.overall ?? null;

  const winnerName = verdict ? (verdict.winner === "left" ? nameLeft : verdict.winner === "right" ? nameRight : null) : null;
  const verdictLine = verdict
    ? verdict.winner === "draw"
      ? `LEVEL AT THE LEDGER — ${verdict.counted} DECLARED, ${verdict.levelled} LEVEL`
      : `${winnerName} TAKES THE DUEL`
    : null;

  const margin = {
    display: "flex",
    flexDirection: "column",
    width: "100%",
    height: "100%",
    padding: "40px 56px 46px",
    background: BG,
    fontFamily: "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif",
    position: "relative",
    overflow: "hidden",
  } as const;

  const mkGlow = (side: "left" | "right") =>
    ({
      position: "absolute",
      top: "14%",
      [side]: "-6%",
      width: "560px",
      height: "430px",
      background: side === "left" ? `radial-gradient(ellipse at center, ${ACCENT}16 0%, transparent 68%)` : `radial-gradient(ellipse at center, ${INFO}17 0%, transparent 68%)`,
      pointerEvents: "none",
    }) as const;

  const labelStyle = {
    fontSize: 15,
    letterSpacing: "0.28em",
    color: SUBTLE,
    textTransform: "uppercase",
    fontWeight: 600,
    display: "flex",
  } as const;

  const overallLeftColor = verdict?.winner === "left" ? ACCENT : PAPER;
  const overallRightColor = verdict?.winner === "right" ? INFO : PAPER;

  const cells = SHORT_LABELS.map(([key, label]) => {
    const row = categories.find((category) => category.key === key);
    const isLevel = row?.winner === "level" || row?.winner === "unavailable";
    const leftValue = row ? figure(row.left) : PLACEHOLDER;
    const rightValue = row ? figure(row.right) : PLACEHOLDER;
    return { label, isLevel, leftValue, rightValue, row };
  });

  return new ImageResponse(
    (
      <div style={margin}>
        <div style={mkGlow("left")} />
        <div style={mkGlow("right")} />
        <div
          style={{
            position: "absolute",
            inset: 0,
            margin: "0 auto",
            left: "50%",
            width: "1px",
            background: LINE,
          }}
        />
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", zIndex: 1 }}>
          <div style={labelStyle}>FOOTBALL OS</div>
          <div style={{ ...labelStyle, color: GOLD }}>THE WORLD'S LEDGER</div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 46, gap: 24, zIndex: 1 }}>
          <div style={{ display: "flex", flexDirection: "column", flex: 1, alignItems: "flex-start", textAlign: "left" }}>
            <div style={{ ...labelStyle, marginBottom: 10 }}>LEFT CORNER</div>
            <div style={{ fontSize: nameLeft.length > 12 ? 42 : 50, lineHeight: 1.05, fontWeight: 800, letterSpacing: "-0.03em", color: PAPER, maxWidth: 420 }}>
              {nameLeft}
            </div>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 18, marginTop: 14 }}>
              <div style={{ fontSize: 116, lineHeight: 0.9, fontWeight: 800, letterSpacing: "-0.04em", fontVariantNumeric: "tabular-nums", color: overallLeftColor }}>
                {figure(overallLeft)}
              </div>
              <div style={{ ...labelStyle, paddingBottom: 10 }}>OVR</div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1 }}>
            <div style={{ fontSize: 92, fontWeight: 800, letterSpacing: "-0.02em", color: GOLD, fontStyle: "italic", opacity: 0.92 }}>v</div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", flex: 1, alignItems: "flex-end", textAlign: "right" }}>
            <div style={{ ...labelStyle, marginBottom: 10 }}>RIGHT CORNER</div>
            <div style={{ fontSize: nameRight.length > 12 ? 42 : 50, lineHeight: 1.05, fontWeight: 800, letterSpacing: "-0.03em", color: PAPER, maxWidth: 420 }}>
              {nameRight}
            </div>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 18, marginTop: 14 }}>
              <div style={{ ...labelStyle, paddingBottom: 10 }}>OVR</div>
              <div style={{ fontSize: 116, lineHeight: 0.9, fontWeight: 800, letterSpacing: "-0.04em", fontVariantNumeric: "tabular-nums", color: overallRightColor }}>
                {figure(overallRight)}
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", gap: 6, marginTop: 30, zIndex: 1 }}>
          {cells.map(({ label, isLevel, leftValue, rightValue, row }) => (
            <div
              key={label}
              style={{
                flex: 1,
                border: `1px solid ${isLevel ? "rgba(240,237,230,0.08)" : "rgba(240,237,230,0.14)"}`,
                borderRadius: 10,
                padding: "10px 6px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 5,
                background: isLevel ? "transparent" : "rgba(240,237,230,0.025)",
              }}
            >
              <div style={{ fontSize: 10, letterSpacing: "0.18em", color: SUBTLE, fontWeight: 700 }}>{label}</div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <div
                  style={{
                    fontSize: 19,
                    fontVariantNumeric: "tabular-nums",
                    fontWeight: 700,
                    color: row?.winner === "left" ? ACCENT : isLevel ? SUBTLE : PAPER,
                  }}
                >
                  {leftValue}
                </div>
                <div style={{ width: 3, height: 3, borderRadius: 3, background: "rgba(240,237,230,0.35)" }} />
                <div
                  style={{
                    fontSize: 19,
                    fontVariantNumeric: "tabular-nums",
                    fontWeight: 700,
                    color: row?.winner === "right" ? INFO : isLevel ? SUBTLE : PAPER,
                  }}
                >
                  {rightValue}
                </div>
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 22, zIndex: 1 }}>
          <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: "0.02em", color: PAPER }}>{verdictLine ?? "TWO PLAYERS. ONE LEDGER."}</div>
          <div style={{ ...labelStyle, color: "#6d7680" }}>SYNTHETIC DEMO WORLD</div>
        </div>
      </div>
    ),
    { ...size },
  );
}
