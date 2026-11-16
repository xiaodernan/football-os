import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
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
    attendance: string | null;
    matchday_date: string;
  };
  biggest_win: {
    match: string;
    score: [number, number];
    stage: string;
    matchday_date: string;
    venue: string;
  };
  goals_scored: number;
  has_penalties: boolean;
  joint_top_scorers_note: string;
  runner_up: FactChallenge;
  golden_ball: FactChallenge;
  biggest_attendance: { match: string; attendance: string };
  openfootball_url: string;
};
type FixtureRow = {
  date: string;
  round: string;
  group: string | null;
  team1: string;
  team2: string;
  ht: [number, number] | null;
  ft: [number, number];
  et: [number, number] | null;
  penalties: [number, number] | null;
  on_field: [number, number];
  ground: string;
};
type RealBookScorer = { name: string; goals: number; penalties: number };
type RealBookPayload = WorldEnvelope & {
  tournament: string;
  source: string;
  attribution: string;
  facts: FactVerse;
  results: FixtureRow[];
  scorers: RealBookScorer[];
  provenance: { data_origin: string; is_demo_data: boolean; license: string };
};

type FixtureDay = { date: string; round: string; rows: FixtureRow[] };

function groupByDay(rows: FixtureRow[]): FixtureDay[] {
  const days: FixtureDay[] = [];
  for (const row of rows) {
    const last = days[days.length - 1];
    if (last && last.date === row.date) {
      last.rows.push(row);
    } else {
      days.push({ date: row.date, round: row.round, rows: [row] });
    }
  }
  return days;
}

type RealBookScreen = { tournament?: string };

export default async function RealBookPage({ searchParams }: { searchParams: Promise<RealBookScreen> }) {
  const t = await getTranslations("worldRealBook");
  const tw = await getTranslations("world");
  const { tournament = "2022" } = await searchParams;

  const result = await readWorld<RealBookPayload>("/world/real-book", { tournament });
  if (!result.ok) return <WorldUnavailable message={result.message} />;

  const { facts, provenance, results, scorers } = result.data;
  const days = groupByDay(results);
  const is2018 = tournament === "2018";
  const is2014 = tournament === "2014";

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={t("eyebrow")}
        lede={is2014 ? t("lede2014") : is2018 ? t("lede2018") : t("lede")}
        provenance={provenance}
        title={t("title")}
      />

      <nav className="realbook__switch" aria-label={t("eyebrow")}>
        <Link href="?tournament=2022" className={`realbook__chip${!is2018 && !is2014 ? " realbook__chip--active" : ""}`} aria-current={!is2018 && !is2014 ? "page" : undefined}>{t("chip2022")}</Link>
        <Link href="?tournament=2018" className={`realbook__chip${is2018 ? " realbook__chip--active" : ""}`} aria-current={is2018 ? "page" : undefined}>{t("chip2018")}</Link>
        <Link href="?tournament=2014" className={`realbook__chip${is2014 ? " realbook__chip--active" : ""}`} aria-current={is2014 ? "page" : undefined}>{t("chip2014")}</Link>
      </nav>

      <p className="records__book">{is2014 ? t("opening2014") : is2018 ? t("opening2018") : t("opening")}</p>

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
          {facts.has_penalties ? (
            <span className="chip num">{t("penaltiesChip", { a: facts.final.score_penalties[0], b: facts.final.score_penalties[1] })}</span>
          ) : null}
          <span className="muted">{facts.final.venue}{facts.final.attendance ? ` · ${facts.final.attendance}` : ""} · {facts.final.matchday_date}</span>
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
            <span className="records__number-big num">{facts.goals_scored}</span>
            <span className="records__number-sub muted">{t("onFieldGoalsCaption")}</span>
          </div>
          <div className="records__number">
            <span className="records__number-big">{facts.champion.name}</span>
            <span className="records__number-sub muted">{t("championCaption")}</span>
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

      <section className="records__panel">
        <span className="records__panel-eyebrow">{t("scorersEyebrow")}</span>
        <h2>{t("scorersTitle")}</h2>
        <p className="records__lede muted">{t("scorersLede")}</p>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">{t("thPlayer")}</th>
                <th scope="col">{t("thGoals")}</th>
                <th scope="col">{t("thPenalties")}</th>
              </tr>
            </thead>
            <tbody>
              {scorers.map((scorer, index) => (
                <tr key={scorer.name}>
                  <td className="num muted">{index + 1}</td>
                  <td>{scorer.name}</td>
                  <td className="num">{scorer.goals}</td>
                  <td className="num muted">{scorer.penalties}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="records__fineprint muted">{t("spellingNote")}</p>
      </section>

      <section className="records__panel">
        <span className="records__panel-eyebrow">{t("ledgerEyebrow")}</span>
        <h2>{t("ledgerTitle")}</h2>
        <p className="records__lede muted">{t("ledgerLede")}</p>
        {days.map((day) => (
          <div key={day.date} className="realbook__day">
            <div className="realbook__dayhead">
              <span className="mono realbook__daydate">{day.date}</span>
              <span className="chip">{day.round}</span>
              <span className="num muted realbook__daycount">{t("matchesOnDay", { count: day.rows.length })}</span>
            </div>
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{t("thFixture")}</th>
                    <th scope="col">{t("thScore")}</th>
                    <th scope="col">{t("thVenue")}</th>
                  </tr>
                </thead>
                <tbody>
                  {day.rows.map((row) => (
                    <tr key={`${row.team1}-${row.team2}`}>
                      <td>
                        {row.team1} v {row.team2}
                        {row.group ? <span className="muted realbook__group">{row.group}</span> : null}
                      </td>
                      <td className="num">
                        <span className="realbook__score num">{row.on_field[0]}–{row.on_field[1]}</span>
                        {row.et ? <span className="chip">{t("aetChip")}</span> : null}
                        {row.penalties ? <span className="chip">{t("penChip", { a: row.penalties[0], b: row.penalties[1] })}</span> : null}
                      </td>
                      <td className="muted">{row.ground}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </section>

      <p className="records__ledger muted">
        {t("attributionLine")}
        <a href={facts.openfootball_url} rel="noopener" target="_blank" className="records__link">{t("sourceLabel")}</a>
      </p>
      <p className="records__fineprint muted">{t("snapshotNote")}</p>

      <Provenance provenance={provenance} />
    </div>
  );
}
