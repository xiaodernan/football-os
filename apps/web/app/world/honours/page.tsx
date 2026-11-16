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
  const t = await getTranslations("worldHonours");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/honours",
  });
}

type Row = {
  tournament: string;
  kind: string;
  title: string;
  host: string;
  date: string;
  venue: string;
  champion: string;
  runner_up: string;
  score_regular: [number, number];
  score_extra_time: [number, number];
  score_penalties: [number, number];
  has_penalties: boolean;
  went_extra_time: boolean;
  on_field: [number, number];
  biggest_win: {
    match: string;
    score: [number, number];
    stage: string;
    matchday_date: string;
    venue: string | null;
  };
  goals_scored: number;
  venues: number;
  total_matches: number;
};
type HonoursPayload = WorldEnvelope & {
  entries: Row[];
  champion_lines: { champion: string; wins: number; years: string[]; kinds: string[] }[];
  totals: { entries: number; matches: number; goals_on_field: number };
  provenance: { data_origin: string; is_demo_data: boolean; license: string };
};

export default async function HonoursPage() {
  const t = await getTranslations("worldHonours");
  const tw = await getTranslations("world");
  const tr = await getTranslations("worldRealBook");

  const result = await readWorld<HonoursPayload>("/world/honours");
  if (!result.ok) return <WorldUnavailable message={result.message} />;

  const { entries, champion_lines, provenance } = result.data;

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
        <span className="records__panel-eyebrow">{t("eyebrow")}</span>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("thYear")}</th>
                <th scope="col">{t("thKind")}</th>
                <th scope="col">{t("thHost")}</th>
                <th scope="col">{t("thFinal")}</th>
                <th scope="col">{t("thChampion")}</th>
                <th scope="col">{t("thRunnerUp")}</th>
                <th scope="col">{t("thGoals")}</th>
                <th scope="col">{t("thMatches")}</th>
                <th scope="col">{t("thWidest")}</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={`${entry.tournament}-${entry.kind}`}>
                  <td>
                    <Link href={`/world/real-book?tournament=${entry.tournament}`} className="records__link">{entry.tournament.replace(/^(euro)/, "")}</Link>
                  </td>
                  <td>{entry.kind === "euro" ? t("kindEuro") : t("kindWorldCup")}</td>
                  <td className="muted">{entry.host}</td>
                  <td className="num">
                    {entry.score_extra_time[0]}–{entry.score_extra_time[1]}
                    {entry.went_extra_time ? <span className="chip">{tr("aetChip")}</span> : null}
                    {entry.has_penalties ? <span className="chip">{tr("penChip", { a: entry.score_penalties[0], b: entry.score_penalties[1] })}</span> : null}
                  </td>
                  <td><strong>{entry.champion}</strong></td>
                  <td className="muted">{entry.runner_up}</td>
                  <td className="num">{entry.goals_scored}</td>
                  <td className="num">{entry.total_matches}</td>
                  <td className="num muted">{entry.biggest_win.match.split(" ").slice(-3).join(" ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="records__fineprint muted">{t("snapshotNote")}</p>
      </section>

      <section className="records__panel">
        <span className="records__panel-eyebrow">{t("championLinesEyebrow")}</span>
        <h2>{t("championLinesTitle")}</h2>
        <p className="records__lede muted">{t("championLinesLede")}</p>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("thChampionTh")}</th>
                <th scope="col">{t("thWinsTh")}</th>
                <th scope="col">{t("thYearsTh")}</th>
              </tr>
            </thead>
            <tbody>
              {champion_lines.filter((line) => line.wins >= 2).map((line) => (
                <tr key={line.champion}>
                  <td><strong>{line.champion}</strong></td>
                  <td className="num">{line.wins}</td>
                  <td className="muted">{line.years.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <p className="records__ledger muted">
        {tr("attributionLine")}
      </p>

      <Provenance provenance={provenance} />
    </div>
  );
}
