import type { Metadata } from "next";

import { Provenance, WorldHead, WorldUnavailable, formatDay } from "@/components/world";
import { NoiseCoachRead } from "@/components/NoiseCoachRead";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { absolute, pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { WorldEnvelope } from "@/lib/types";
import "@/styles/noise.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldNoise");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/noise",
    images: [{ url: absolute("/world/noise/opengraph-image"), width: 1200, height: 630, alt: "FOOTBALL OS" }],
  });
}

type SideBrief = { id: string; slug: string; name: string; path: string } | null;
type UpsetRow = {
  slug: string;
  path: string;
  kickoff_at: string | null;
  home: SideBrief;
  away: SideBrief;
  home_goals: number;
  away_goals: number;
  called: "home" | "away" | "draw";
  actual: "home" | "away" | "draw";
  rating_gap: number;
};
type NoisePayload = WorldEnvelope & {
  available: boolean;
  season: { label: string; kind: string };
  competition?: string;
  competition_slug?: string;
  judged?: number;
  correct?: number;
  wrong?: number;
  accuracy_pct?: number;
  chance_pct?: number;
  draw_window?: number;
  draw_calls?: number;
  draw_hits?: number;
  draw_hit_pct?: number;
  best_streak?: number;
  upsets?: UpsetRow[];
};

export default async function NoisePage() {
  const t = await getTranslations("worldNoise");
  const tw = await getTranslations("world");

  const result = await readWorld<NoisePayload>("/world/noise");
  if (!result.ok) return <WorldUnavailable message={result.message} />;
  if (!result.data.available) return <WorldUnavailable message={t("unavailable")} />;

  const { judged, correct, wrong, accuracy_pct, chance_pct, draw_calls, draw_hits, draw_hit_pct, best_streak, upsets = [] } = result.data;

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        provenance={result.data}
        title={t("title")}
      />

      <div className="noise__stats">
        <div className="noise__tile">
          <span className="noise__tile-eyebrow">{t("statAccuracyLabel")}</span>
          <p className="noise__big">{accuracy_pct?.toFixed(1) ?? "0.0"}<span className="noise__pct">%</span></p>
          <p className="noise__sub">{t("accuracyCaption", { correct: correct ?? 0, judged: judged ?? 0 })}</p>
        </div>
        <div className="noise__tile">
          <span className="noise__tile-eyebrow">{t("statDrawLabel")}</span>
          <p className="noise__big">{draw_hit_pct?.toFixed(1) ?? "0.0"}<span className="noise__pct">%</span></p>
          <p className="noise__sub">{t("drawCaption", { hits: draw_hits ?? 0, calls: draw_calls ?? 0 })}</p>
        </div>
        <div className="noise__tile">
          <span className="noise__tile-eyebrow">{t("statStreakLabel")}</span>
          <p className="noise__big">{best_streak ?? 0}</p>
          <p className="noise__sub">{t("streakCaption")}</p>
        </div>
      </div>

      <p className="noise__verdict">
        {t("verdictBody", { chance: chance_pct?.toFixed(2) ?? "33.33" })}
      </p>

      <section>
        <h2 className="noise__title">{t("upsetBoardTitle")}</h2>
        <p className="muted" style={{ fontSize: "0.82rem", margin: "0.15rem 0 0.5rem" }}>{t("upsetBoardLede")}</p>
        <div className="noise__board">
          {upsets.map((row) => (
            <Link key={row.slug} href={row.path} className="noise__row">
              <span className="noise__row-date">{formatDay(row.kickoff_at)}</span>
              <span className="noise__row-fixture">
                <strong>{row.home?.name}</strong>
                <span className="noise__row-goals">{row.home_goals} – {row.away_goals}</span>
                <strong>{row.away?.name}</strong>
              </span>
              <span className="noise__row-call">
                {t("upsetCallLabel")}: <em>{row.called}</em>
              </span>
              <span className="noise__row-result">{t("upsetActualLabel")}: <em>{row.actual}</em></span>
              <span className="noise__row-gap">{row.rating_gap.toFixed(1)}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="noise__method">
        <span className="noise__tile-eyebrow">{t("methodEyebrow")}</span>
        <p>{t("methodBody")}</p>
      </section>

      <NoiseCoachRead />

      <Provenance provenance={result.data} />
    </div>
  );
}
