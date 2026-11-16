import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { Provenance, RefLink, WorldHead, WorldUnavailable } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { WorldEnvelope } from "@/lib/types";
import "@/styles/records.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldRealBook");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/real-book",
  });
}

type FactChallenge = {
  name: string;
  note: string;
  star?: string;
};
type FactVerse = {
  tournament: string;
  host: string;
  final_date: string;
  venues: number;
  total_matches: number;
  final_rounds: { round: string; matches: number }[];
  champion: FactChallenge;
  final: {
    home: string;
    away: string;
    score_regular: [number, number];
    score_extra_time: [number, number];
    score_penalties: [number, number];
    venue: string;
    attendance: string;
    matchday_date: string;
  };
  biggest_win: {
    match: string;
    score: [number, number];
    stage: string;
    matchday_date: string;
    venue: string;
  };
  runner_up: FactChallenge;
  golden_ball: FactChallenge;
  biggest_attendance: { match: string; attendance: string };
  openfootball_url: string;
};
type RealBookPayload = WorldEnvelope & {
  source: string;
  attribution: string;
  facts: FactVerse;
  provenance: { data_origin: string; is_demo_data: boolean; license: string };
};

export default async function RealBookPage() {
  const t = await getTranslations("worldRealBook");
  const tw = await getTranslations("world");

  const result = await readWorld<RealBookPayload>("/world/real-book");
  if (!result.ok) return <WorldUnavailable message={result.message} />;

  const { facts, attribution, provenance } = result.data;

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        provenance={provenance}
        title={t("title")}
      />

      <p className="records__book">{t("opening")}</p>

      <section className="records__panel">
        <span className="records__panel-eyebrow">{t("finalPanelEyebrow")}</span>
        <h2>{t("finalPanelTitle", { home: facts.final.home, away: facts.final.away })}</h2>
        <div className="records__fixture-row">
          <div className="records__team records__team--winner">
            <span className="records__team-name">{facts.final.home}</span>
          </div>
          <div className="records__score num">{facts.final.score_extra_time[0]}–{facts.final.score_extra_time[1]}</div>
          <div className="records__team records__team--runner">
            <span className="records__team-name">{facts.final.away}</span>
          </div>
        </div>
        <div className="records__fixture-note">
          <span className="chip num">{t("penaltiesChip", { a: facts.final.score_penalties[0], b: facts.final.score_penalties[1] })}</span>
          <span className="muted">{facts.final.venue} · {facts.final.attendance} · {facts.final.matchday_date}</span>
        </div>
      </section>

      <section className="records__panel">
        <span className="records__panel-eyebrow">{t("numbersEyebrow")}</span>
        <h2>{t("numbersTitle")}</h2>
        <div className="records__numbers">
          <div className="records__number">
            <span className="records__number-big num">{facts.total_matches}</span>
            <span className="records__number-sub muted">{t("matchesCaption")}</span>
          </div>
          <div className="records__number">
            <span className="records__number-big num">{facts.venues}</span>
            <span className="records__number-sub muted">{t("venuesCaption")}</span>
          </div>
          <div className="records__number">
            <span className="records__number-big">{facts.champion.name}</span>
            <span className="records__number-sub muted">{t("championCaption")}</span>
          </div>
          <div className="records__number">
            <span className="records__number-big num">3</span>
            <span className="records__number-sub muted">{t("finalGoalsCaption")}</span>
          </div>
        </div>
      </section>

      <section className="records__panel">
        <span className="records__panel-eyebrow">{t("awardsEyebrow")}</span>
        <h2>{t("awardsTitle")}</h2>
        <div className="records__tiles">
          <div className="records__tile">
            <span className="records__tile-eyebrow">{t("goldenBallTitle")}</span>
            <p className="records__tile-body"><strong>{facts.golden_ball.name}</strong></p>
            <p className="records__tile-sub muted">{facts.golden_ball.note}</p>
          </div>
          <div className="records__tile">
            <span className="records__tile-eyebrow">{t("topScorerTitle")}</span>
            <p className="records__tile-body"><strong>{facts.runner_up.name}</strong></p>
            <p className="records__tile-sub muted">{facts.runner_up.star}</p>
          </div>
          <div className="records__tile">
            <span className="records__tile-eyebrow">{t("biggestWinTitle")}</span>
            <p className="records__tile-body"><strong>{facts.biggest_win.match}</strong></p>
            <p className="records__tile-sub muted">{facts.biggest_win.stage} · {facts.biggest_win.venue} · {facts.biggest_win.matchday_date}</p>
          </div>
        </div>
      </section>

      <p className="records__ledger muted">
        {t("attributionLine")}
        <a href={facts.openfootball_url} rel="noopener" target="_blank" className="records__link">{t("sourceLabel")}</a>
      </p>

      <Provenance provenance={provenance} />
    </div>
  );
}
