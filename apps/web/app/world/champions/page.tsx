import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { ChampionsCoachRead } from "@/components/ChampionsCoachRead";
import { pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { WorldEnvelope } from "@/lib/types";
import "@/styles/records.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldChampions");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/champions",
  });
}

type CupFinal = {
  home: string;
  away: string;
  score_regular: [number, number];
  score_extra_time: [number, number];
  score_penalties: [number, number];
  venue: string;
  attendance: string | null;
  matchday_date: string;
};
type CupBiggestWin = {
  match: string;
  score: [number, number];
  stage: string;
  matchday_date: string;
  venue: string;
};
type CupFinalRow = {
  date: string | null;
  team1: string | null;
  team2: string | null;
  on_field: [number, number] | null;
  et: [number, number] | null;
  penalties: [number, number] | null;
  ht: [number, number] | null;
};
type CupEntry = {
  tournament: string;
  title: string;
  host: string;
  venues: number;
  total_matches: number;
  goals_scored: number;
  goals_per_match: number;
  has_penalties: boolean;
  champion: { name: string; note: string };
  runner_up: { name: string; star: string };
  golden_ball: { name: string; note: string };
  final: CupFinal;
  final_row: CupFinalRow | null;
  biggest_win: CupBiggestWin;
  top_scorers: { name: string; goals: number; penalties: number }[];
  top_scorers_note: string;
};
type MergedScorer = { name: string; goals_2014: number; goals_2018: number; goals_2022: number; total: number };
type ChampionsPayload = WorldEnvelope & {
  source: string;
  attribution: string;
  entries: CupEntry[];
  merged_scorers: MergedScorer[];
  joint_top_scorers_note: string;
  provenance: { data_origin: string; is_demo_data: boolean; license: string };
};

export default async function ChampionsPage() {
  const t = await getTranslations("worldChampions");
  const tw = await getTranslations("world");

  const result = await readWorld<ChampionsPayload>("/world/champions");
  if (!result.ok) return <WorldUnavailable message={result.message} />;

  const { entries, merged_scorers, attribution, provenance, source, joint_top_scorers_note } = result.data;

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

      <section className="records__panel" aria-labelledby="numbers">
        <span className="records__panel-eyebrow">{t("numbersEyebrow")}</span>
        <h2 id="numbers">{t("numbersTitle")}</h2>
        <nav className="champions__cups" aria-label={t("title")}>
          {entries.map((entry) => (
            <Link key={entry.tournament} href={`/world/real-book?tournament=${entry.tournament}`} className="records__panel champions__cup">
              <span className="records__panel-eyebrow">{t("finalKicker")} · {entry.tournament} · {entry.host}</span>
              <span className="records__panel-eyebrow">{t("championCaption")}</span>
              <h2>{entry.champion.name}</h2>
              <div className="records__fixture-row champions__score">
                <div className="records__team records__team--winner">
                  <span className="records__team-name">{entry.final.home}</span>
                </div>
                <div className="records__score num">{entry.final.score_extra_time[0]}–{entry.final.score_extra_time[1]}</div>
                <div className="records__team records__team--runner">
                  <span className="records__team-name">{entry.final.away}</span>
                </div>
              </div>
              <div className="records__fixture-note">
                {entry.final_row?.et != null ? <span className="chip num">{t("aetChip")}</span> : null}
                {entry.final.score_penalties[0] !== 0 || entry.final.score_penalties[1] !== 0 ? (
                  <span className="chip num">{t("penChip", { a: entry.final.score_penalties[0], b: entry.final.score_penalties[1] })}</span>
                ) : null}
                <span className="muted">{entry.final.venue}{entry.final.attendance ? ` · ${entry.final.attendance}` : ""} · {entry.final.matchday_date}</span>
              </div>
              <p className="records__tile-sub muted">{t("goldenBallCaption")}: <strong>{entry.golden_ball.name}</strong> — {entry.golden_ball.note}</p>
              <p className="records__tile-sub muted"><span className="mono">{entry.goals_scored}</span> {t("goalsOnFieldCaption")} · <span className="mono">{entry.goals_per_match}</span> {t("goalsPerMatchCaption")}</p>
              <p className="records__tile-sub muted"><span className="mono">{entry.venues}</span> {t("venuesCaption")} · <span className="mono">{entry.total_matches}</span> {t("matchesCaption")}</p>
              <p style={{ margin: 0 }}><span className="chip">{t("openBookLink")}</span></p>
            </Link>
          ))}
        </nav>
      </section>

      <section className="records__panel">
        <span className="records__panel-eyebrow">{t("widestEyebrow")}</span>
        <h2>{t("widestTitle")}</h2>
        <div className="stack" style={{ gap: "0.6rem" }}>
          {entries.map((entry) => (
            <div className="records__fixture-note" key={`margin-${entry.tournament}`}>
              <span className="chip num">{entry.tournament}</span>
              <strong>{entry.biggest_win.match}</strong>
              <span className="muted"> — {entry.biggest_win.stage} · {entry.biggest_win.venue} · {entry.biggest_win.matchday_date}</span>
            </div>
          ))}
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
                <th scope="col">{t("thPlayer")}</th>
                <th scope="col">{t("th2014")}</th>
                <th scope="col">{t("th2018")}</th>
                <th scope="col">{t("th2022")}</th>
                <th scope="col">{t("thTotal")}</th>
              </tr>
            </thead>
            <tbody>
              {merged_scorers.map((scorer) => (
                <tr key={scorer.name}>
                  <td>{scorer.name}</td>
                  <td className="num muted">{scorer.goals_2014}</td>
                  <td className="num muted">{scorer.goals_2018}</td>
                  <td className="num muted">{scorer.goals_2022}</td>
                  <td className="num">{scorer.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="records__fineprint muted">{t("mergedNote")}</p>
        <p className="records__fineprint muted">{joint_top_scorers_note}</p>
      </section>

      <p className="records__ledger muted">
        {t("attributionLine")}
        <a href="https://github.com/openfootball/worldcup.json" rel="noopener" target="_blank" className="records__link">{t("sourceLabel")}</a>
      </p>
      <p className="records__fineprint muted">{t("snapshotNote")}</p>

      <ChampionsCoachRead />

      <Provenance provenance={provenance} />
    </div>
  );
}
