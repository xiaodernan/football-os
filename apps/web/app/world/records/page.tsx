import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { getTranslations } from "next-intl/server";

import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { RecordsCoachRead } from "@/components/RecordsCoachRead";
import { pageMetadata, absolute } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type {
  RecordCardsFixture,
  RecordCastle,
  RecordDefenceClub,
  RecordGoalFest,
  SeasonRecord,
  RecordMatch,
  RecordOffenceClub,
  RecordPlayer,
  RecordsResult,
  RecordTeam,
} from "@/lib/types";

import "@/styles/records.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldRecords");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/records",
    images: [{ url: absolute("/world/records/opengraph-image"), width: 1200, height: 630, alt: "FOOTBALL OS" }],
  });
}

export default async function RecordsPage() {
  const t = await getTranslations("worldRecords");
  const result = await readWorld<RecordsResult>("/world/records");

  if (!result.ok) {
    return (
      <div className="container page stack">
        <WorldHead eyebrow={t("eyebrow")} title={t("title")} />
        <p className="records__unavailable">{t("unavailable")}</p>
      </div>
    );
  }

  const [biggestHaul, goalFest, offence, defence, castle, cards, wall, pinnacle] = result.data.records;

  return (
    <div className="container page stack">
      <WorldHead
        eyebrow={t("eyebrow")}
        title={t("title")}
        lede={t("lede")}
        provenance={result.data}
        back={{ href: "/world", label: t("backWorld") }}
      />
      <p className="chip mono records__chip-row">{t("seasonLabel")}</p>

      <div className="records__grid">
        <RecordTile
          eyebrow={t("recordBiggestHaul")}
          hint={t("recordBiggestHaulHint")}
          caption={t("captionGoals")}
          figure={biggestHaul.available ? biggestHaul.goals : undefined}
        >
          {biggestHaul.available && biggestHaul.player ? (
            <>
              <PlayerLine player={biggestHaul.player} />
              {biggestHaul.match && <MatchLine match={biggestHaul.match} />}
            </>
          ) : null}
        </RecordTile>

        <RecordTile
          eyebrow={t("recordGoalFest")}
          hint={t("recordGoalFestHint")}
          caption={t("captionGoals")}
          figure={goalFest.available ? goalFest.goals : undefined}
        >
          {goalFest.match ? <MatchLine match={goalFest.match} /> : null}
        </RecordTile>

        <RecordTile
          eyebrow={t("recordOffenceClub")}
          hint={t("recordOffenceClubHint")}
          caption={t("captionScored")}
          figure={offence.available ? offence.goals_for : undefined}
        >
          {offence.available && offence.team ? (
            <TeamLine team={offence.team} competition={offence.competition ?? null} slug={offence.competition_slug ?? null} />
          ) : null}
        </RecordTile>

        <RecordTile
          eyebrow={t("recordDefenceClub")}
          hint={t("recordDefenceClubHint")}
          caption={t("captionConceded")}
          figure={defence.available ? defence.goals_against : undefined}
        >
          {defence.available && defence.team ? (
            <TeamLine
              team={defence.team}
              competition={defence.competition ?? null}
              slug={defence.competition_slug ?? null}
              note={t("captionGames", { games: defence.played ?? 0 })}
            />
          ) : null}
        </RecordTile>

        <RecordTile
          eyebrow={t("recordCastle")}
          hint={t("recordCastleHint")}
          caption={t("captionCleanSheets")}
          figure={castle.available ? castle.clean_sheets : undefined}
        >
          {castle.available && castle.team ? (
            <TeamLine team={castle.team} competition={castle.competition ?? null} slug={castle.competition_slug ?? null} />
          ) : null}
        </RecordTile>

        <RecordTile
          eyebrow={t("recordCardsFixture")}
          hint={t("recordCardsFixtureHint")}
          caption={t("captionCards")}
          figure={cards.available ? cards.weighted_cards : undefined}
        >
          {cards.match ? <MatchLine match={cards.match} /> : null}
        </RecordTile>

        <RecordTile
          eyebrow={t("recordKeeperWall")}
          hint={t("recordKeeperWallHint")}
          caption={t("captionSaves")}
          figure={wall.available ? wall.saves : undefined}
        >
          {wall.available && wall.player ? (
            <>
              <PlayerLine player={wall.player} />
              {wall.match && <MatchLine match={wall.match} />}
            </>
          ) : null}
        </RecordTile>

        <RecordTile
          eyebrow={t("recordHighestRated")}
          hint={t("recordHighestRatedHint")}
          caption={t("captionRating")}
          figure={pinnacle.available ? (pinnacle.rating ?? 0).toFixed(2) : undefined}
        >
          {pinnacle.available && pinnacle.player ? (
            <>
              <PlayerLine player={pinnacle.player} />
              {pinnacle.match && <MatchLine match={pinnacle.match} />}
            </>
          ) : null}
        </RecordTile>
      </div>

      <RecordsCoachRead />

      <Provenance provenance={result.data} />
    </div>
  );
}

function RecordTile({
  eyebrow,
  hint,
  figure,
  caption,
  children,
}: {
  eyebrow: string;
  hint: string;
  figure?: ReactNode;
  caption: string;
  children?: ReactNode;
}) {
  return (
    <article className="records__tile">
      <span className="records__tile-eyebrow">{eyebrow}</span>
      <span className="records__tile-figure">{figure ?? "—"}</span>
      <span className="records__tile-caption">{caption}</span>
      <p className="records__tile-hint">{hint}</p>
      <span className="records__tile-who">{children}</span>
    </article>
  );
}

function PlayerLine({ player }: { player: RecordPlayer }) {
  return (
    <>
      <Link href={player.path}>{player.name}</Link>
      {player.team ? (
        <span className="records__tile-sub">
          <Link href={player.team.path ?? "/world"}>{player.team.name}</Link>
        </span>
      ) : null}
    </>
  );
}

function TeamLine({
  team,
  competition,
  slug,
  note,
}: {
  team: RecordTeam;
  competition: string | null;
  slug: string | null;
  note?: ReactNode;
}) {
  return (
    <>
      <Link href={team.path ?? "/world"}>{team.name}</Link>
      {competition ? (
        <span className="records__tile-sub">
          {slug ? <Link href={`/competition/${slug}`}>{competition}</Link> : competition}
          {note ? <> · {note}</> : null}
        </span>
      ) : null}
    </>
  );
}

function MatchLine({ match }: { match: RecordMatch }) {
  return (
    <span className="records__tile-sub">
      <Link href={match.path}>
        {match.home.name} {match.home_goals}–{match.away_goals} {match.away.name}
      </Link>
    </span>
  );
}
