import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Provenance, RefLink, WorldHead, WorldUnavailable } from "@/components/world";
import { pageMetadata, absolute } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { WorldEnvelope } from "@/lib/types";
import "@/styles/timeline.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldTimeline");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/timeline",
    images: [{ url: absolute("/world/timeline/opengraph-image"), width: 1200, height: 630, alt: "FOOTBALL OS" }],
  });
}

type RoundLeader = {
  id: string;
  slug: string;
  name: string;
  path: string;
  points: number;
  goal_difference?: number;
  played?: number;
};
type TimelineRound = {
  matchday: number;
  label: string;
  fixtures: number;
  goals: number;
  leader: RoundLeader;
  runner_up: { id: string; slug: string; name: string; path: string; points: number } | null;
  gap: number;
};
type TimelineChartPoint = {
  matchday: number;
  leader_points: number;
  champion_points: number;
  runner_up_points: number;
  gap: number;
};
type TimelinePayload = WorldEnvelope & {
  available: boolean;
  season: { label: string; kind: string };
  competition: string;
  competition_slug: string;
  matchdays: number;
  rounds: TimelineRound[];
  chart: TimelineChartPoint[];
  champion: RoundLeader & { won: number; drawn: number; lost: number };
  beats: {
    opening: {
      available: boolean;
      matchday: number;
      label: string;
      fixtures: number;
      goals: number;
      leader: RoundLeader;
      eventual_champion_led: boolean;
    };
    avalanche: { available: boolean; matchday: number; label: string; goals: number; fixtures: number };
    takeover: { available: boolean; matchday?: number; label?: string; lead_matchdays?: number };
    settled: { available: boolean; matchday?: number; label?: string; points?: number; gap?: number; decided_on_tiebreak: boolean };
  };
};

const GOLD = "#d8b56b";
const SUBTLE = "#97a0a8";
const LINE_SOFT = "rgba(240, 237, 230, 0.10)";
const PAPER_INK = "#f0ede6";

function RaceChart({ points, championLabel, runnerupLabel, pointsUnit }: { points: TimelineChartPoint[]; championLabel: string; runnerupLabel: string; pointsUnit: string }) {
  const width = 640;
  const height = 216;
  const padX = 30;
  const padTop = 14;
  const padBottom = 26;
  const maxPoints = Math.max(...points.flatMap((p) => [p.champion_points, p.runner_up_points]), 1) + 2;
  const x = (matchday: number) => padX + ((matchday - 1) / Math.max(points.length - 1, 1)) * (width - padX * 2);
  const y = (value: number) => padTop + (1 - value / maxPoints) * (height - padTop - padBottom);
  const line = (key: "champion_points" | "runner_up_points") =>
    points.map((p) => `${x(p.matchday).toFixed(1)},${y(p[key]).toFixed(1)}`).join(" ");
  const gridValues = [Math.round(maxPoints / 2), maxPoints - 2];

  return (
    <figure style={{ margin: 0 }} aria-label={`${championLabel} ${pointsUnit}`}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" width="100%" height="216" style={{ maxWidth: "100%" }}>
        {gridValues.map((value) => (
          <g key={value}>
            <line x1={padX} x2={width - padX} y1={y(value)} y2={y(value)} stroke={LINE_SOFT} strokeWidth="1" strokeDasharray="2 4" />
            <text x={2} y={y(value) + 3} fontSize="8" fill={SUBTLE}>{value}</text>
          </g>
        ))}
        <text x={2} y={height - 4} fontSize="8" fill={SUBTLE}>{pointsUnit}</text>
        <polyline
          points={line("runner_up_points")}
          fill="none"
          stroke={SUBTLE}
          strokeWidth="1.6"
          strokeLinejoin="round"
          strokeLinecap="round"
          strokeDasharray="5 4"
        />
        <polyline
          points={line("champion_points")}
          fill="none"
          stroke={GOLD}
          strokeWidth="3"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {points.length > 0 && (
          <>
            <circle cx={x(points[points.length - 1].matchday)} cy={y(points[points.length - 1].champion_points)} r="4" fill={GOLD} />
            <circle cx={x(points[points.length - 1].matchday)} cy={y(points[points.length - 1].runner_up_points)} r="3.4" fill="none" stroke={SUBTLE} strokeWidth="1.4" />
          </>
        )}
        {points.filter((_, i) => i === 0 || i === points.length - 1).map((p) => (
          <text key={p.matchday} x={x(p.matchday)} y={height - 6} fontSize="9" fill={SUBTLE} textAnchor={p.matchday === 1 ? "start" : "end"}>
            {`M${p.matchday}`}
          </text>
        ))}
      </svg>
      <figcaption style={{ display: "flex", gap: "1rem", marginTop: "0.3rem", flexWrap: "wrap" }}>
        <span className="timeline__legend">
          <i className="timeline__swatch timeline__swatch--champ" />
          <span>{championLabel}</span>
        </span>
        <span className="timeline__legend">
          <i className="timeline__swatch timeline__swatch--runner" />
          <span>{runnerupLabel}</span>
        </span>
      </figcaption>
    </figure>
  );
}

export default async function TimelinePage() {
  const t = await getTranslations("worldTimeline");
  const tw = await getTranslations("world");

  const result = await readWorld<TimelinePayload>("/world/timeline");
  if (!result.ok) return <WorldUnavailable message={result.message} />;
  if (!result.data.available) return <WorldUnavailable message={t("unavailable")} />;

  const { rounds, chart, champion, beats } = result.data;
  const opening = beats.opening;
  const avalanche = beats.avalanche;
  const takeover = beats.takeover;
  const settled = beats.settled;
  const settledBody = settled.available
    ? t("settledEarlyBody", { label: settled.label as string })
    : settled.decided_on_tiebreak
      ? t("settledWhistleBody")
      : t("settledHeldBody");

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        provenance={result.data}
        title={t("title")}
      />

      <div className="timeline__stats">
        <article className="timeline__tile">
          <span className="timeline__tile-eyebrow">{t("statChampionLabel")}</span>
          <p className="timeline__big" style={{ fontSize: "1.55rem", letterSpacing: "-0.02em", lineHeight: 1.12, minHeight: "2.6em" }}>
            <Link href={champion.path}>{champion.name}</Link>
          </p>
          <p className="timeline__sub">{result.data.competition}</p>
        </article>
        <div className="timeline__tile">
          <span className="timeline__tile-eyebrow">{t("statPointsLabel")}</span>
          <p className="timeline__big">{champion.points}</p>
          <p className="timeline__sub">{t("pointsPar", { won: champion.won, drawn: champion.drawn, lost: champion.lost })}</p>
        </div>
        <div className="timeline__tile">
          <span className="timeline__tile-eyebrow">{t("statGdLabel")}</span>
          <p className="timeline__big">{champion.goal_difference! >= 0 ? `+${champion.goal_difference}` : `${champion.goal_difference}`}</p>
          <p className="timeline__sub">{t("statPlayedLabel", { played: champion.played ?? 0 })}</p>
        </div>
      </div>

      <section className="timeline__race">
        <div className="timeline__race-head">
          <h2 className="timeline__race-title">{t("chartTitle")}</h2>
          <span className="timeline__tile-eyebrow" style={{ color: "var(--text-3)" }}>{result.data.competition}</span>
        </div>
        <p className="timeline__sub" style={{ margin: "0.2rem 0 0.55rem" }}>{t("chartLede")}</p>
        <RaceChart points={chart} championLabel={t("chartChampionLegend")} runnerupLabel={t("chartRunnerupLegend")} pointsUnit={t("chartPointsUnit")} />
      </section>

      <div className="timeline__beats">
        <article className="timeline__beat">
          <span className="timeline__beat-key">{t("beatsOpeningEyebrow")}</span>
          <h3>{t("beatsOpeningTitle")}</h3>
          <p>{t("openingBody", { label: opening.label, goals: opening.goals, fixtures: opening.fixtures, leader: opening.leader.name })}</p>
          <span className={`timeline__chip${opening.eventual_champion_led ? "" : " timeline__chip--hollow"}`}>
            {opening.eventual_champion_led ? t("openingChampionsLedChip") : t("openingChasedChip")}
          </span>
        </article>

        <article className="timeline__beat">
          <span className="timeline__beat-key">{t("beatsAvalancheEyebrow")}</span>
          <h3>{t("beatsAvalancheTitle")}</h3>
          <p>{t("avalancheBody", { label: avalanche.label, goals: avalanche.goals, fixtures: avalanche.fixtures })}</p>
        </article>

        <article className="timeline__beat">
          <span className="timeline__beat-key">{t("beatsTakeoverEyebrow")}</span>
          <h3>{t("beatsTakeoverTitle")}</h3>
          <p>
            {takeover.available
              ? t("takeoverBody", { label: takeover.label as string, count: takeover.lead_matchdays as number })
              : t("settledHeldBody")}
          </p>
          {takeover.available ? <span className="timeline__chip">{t("takeoverCountUnit", { count: takeover.lead_matchdays as number })}</span> : null}
        </article>

        <article className="timeline__beat">
          <span className="timeline__beat-key">{t("beatsSettlementEyebrow")}</span>
          <h3>{t("beatsSettlementTitle")}</h3>
          <p>{settledBody}</p>
          {settled.available ? <span className="timeline__chip">{t("settledEarlyChip", { label: settled.label as string })}</span> : null}
        </article>
      </div>

      <section>
        <h2 className="timeline__race-title" style={{ marginBottom: "0.2rem" }}>{t("archiveTitle")}</h2>
        <p className="timeline__sub" style={{ marginTop: 0 }}>{t("archiveLede")}</p>
        <div className="timeline__archive" style={{ marginTop: "0.6rem" }}>
          <table className="timeline__table">
            <thead>
              <tr>
                <th scope="col">{t("archiveMW")}</th>
                <th scope="col">{t("archiveFixtures")}</th>
                <th scope="col">{t("archiveGoals")}</th>
                <th scope="col">{t("archiveLeader")}</th>
                <th scope="col">{t("archivePoints")}</th>
                <th scope="col">{t("archiveGap")}</th>
              </tr>
            </thead>
            <tbody>
              {rounds.map((round) => (
                <tr key={round.matchday} data-champion={round.leader.id === champion.id ? "true" : undefined}>
                  <td>{round.matchday}</td>
                  <td>{round.fixtures}</td>
                  <td>{round.goals}</td>
                  <td>
                    <Link href={round.leader.path}>{round.leader.name}</Link>
                  </td>
                  <td>{round.leader.points}</td>
                  <td>{round.gap === 0 ? "—" : `+${round.gap}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <Provenance provenance={result.data} />
    </div>
  );
}
