import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Provenance, WorldHead, WorldUnavailable, formatDay } from "@/components/world";
import { FinalsCoachRead } from "@/components/FinalsCoachRead";
import { pageMetadata, absolute } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { WorldEnvelope } from "@/lib/types";
import "@/styles/finals.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldFinals");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/finals",
    images: [{ url: absolute("/world/finals/opengraph-image"), width: 1200, height: 630, alt: "FOOTBALL OS" }],
  });
}

type SideBrief = { id: string; slug: string; name: string; path: string } | null;
type FinalRow = {
  competition: { id: string; name: string; slug: string | null; path: string | null };
  fixture: { id: string; slug: string; path: string; kickoff: string | null; venue: string | null; city: string | null; season: string };
  home: SideBrief;
  away: SideBrief;
  home_goals: number;
  away_goals: number;
  winner: "home" | "away" | "drawn";
  winning_team: SideBrief;
  mvp: { id: string; slug: string; name: string; path: string; overall: number; position: string; rating: number; goals: number; assists: number } | null;
};
type CupWinRow = { team: SideBrief; cups: number; names: string[] };
type FinalsPayload = WorldEnvelope & {
  available: boolean;
  season: { label: string; kind: string };
  finals?: FinalRow[];
  stats?: { finals: number; goals: number };
  loudest?: { competition: { name: string; slug: string | null; path: string | null }; goals: number; home_goals: number; away_goals: number; venue: string | null };
  cup_wins?: CupWinRow[];
};

export default async function FinalsPage() {
  const t = await getTranslations("worldFinals");
  const tw = await getTranslations("world");

  const result = await readWorld<FinalsPayload>("/world/finals");
  if (!result.ok) return <WorldUnavailable message={result.message} />;
  if (!result.data.available) return <WorldUnavailable message={t("unavailable")} />;

  const { finals = [], stats, loudest, cup_wins = [] } = result.data;

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        provenance={result.data}
        title={t("title")}
      />

      <div className="finals__stats">
        <div className="finals__tile">
          <span className="finals__tile-eyebrow">{t("statFinalsLabel")}</span>
          <p className="finals__big">{stats?.finals ?? 0}</p>
        </div>
        <div className="finals__tile">
          <span className="finals__tile-eyebrow">{t("statGoalsLabel")}</span>
          <p className="finals__big">{stats?.goals ?? 0}</p>
        </div>
        <div className="finals__tile">
          <span className="finals__tile-eyebrow">{t("statLoudestLabel")}</span>
          <p className="finals__big">{loudest?.goals ?? 0}</p>
          <p className="finals__sub">{loudest?.competition.name}</p>
        </div>
      </div>

      <section>
        <span className="timeline__beat-key" style={{ color: "var(--gold, #d8b56b)" }}>{t("winnersLabel")}</span>
        <p className="muted" style={{ fontSize: "0.82rem", margin: "0.15rem 0 0.35rem" }}>{t("holdersLede")}</p>
        <div className="finals__holders">
          {cup_wins.map((row) => (
            <Link key={row.team?.id} href={row.team?.path ?? "#"} className="finals__cup-chip" title={row.names.join(" · ")}>
              <b>{row.cups}</b>
              {row.team?.name}
            </Link>
          ))}
        </div>
      </section>

      <div className="finals__grid">
        {finals.map((final) => (
          <article key={final.fixture.id} className="finals__card">
            <div className="finals__card-kicker">
              <span className="finals__card-competition">
                <Link href={final.competition.path ?? "#"}>{final.competition.name}</Link>
              </span>
              <span>{formatDay(final.fixture.kickoff)}</span>
            </div>
            <Link className="finals__score-link" href={final.fixture.path} aria-label={final.fixture.slug}>
              <div className="finals__score">
                <span className="finals__score-team">{final.home?.name}</span>
                <span className="finals__score-num">{final.home_goals} – {final.away_goals}</span>
                <span className="finals__score-team">{final.away?.name}</span>
              </div>
            </Link>
            <p className="finals__winner-line">
              {final.winner === "drawn"
                ? t("drawnLabel")
                : t("winnerLabel", { name: final.winning_team?.name ?? final.winning_team?.slug ?? "" })}
              {" · "}{final.fixture.venue ?? ""}
            </p>
            <p className="finals__mvp">
              <span>
                <span className="finals__tile-eyebrow" style={{ display: "block" }}>{t("mvpLabel")}</span>
                {final.mvp ? <Link className="finals__mvp-name" href={final.mvp.path}>{final.mvp.name}</Link> : t("unavailable")}
              </span>
              {final.mvp && (
                <span className="finals__mvp-meta">{final.mvp.position} · {final.mvp.rating.toFixed(2)}</span>
              )}
            </p>
          </article>
        ))}
      </div>

      <FinalsCoachRead />

      <Provenance provenance={result.data} />
    </div>
  );
}
