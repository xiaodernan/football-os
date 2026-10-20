import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { AttributeRadar } from "@/components/AttributeRadar";
import { Meter, Panel, ReasonList } from "@/components/ui";
import {
  CompetitionLink,
  EntityLink,
  JsonLd,
  KeyValueGrid,
  Provenance,
  WorldHead,
  WorldUnavailable,
  formatDay,
} from "@/components/world";
import { absolute, pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { PlayerDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

async function load(slug: string) {
  return readWorld<PlayerDetail>(`/world/players/${encodeURIComponent(slug)}`);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const tp = await getTranslations("worldPlayer");
  const result = await load(slug);
  const player = result.ok ? result.data.player : null;
  const name = player?.name ?? slug.replace(/-/g, " ");
  const club = player?.club?.name;
  return pageMetadata({
    title: `${name}${club ? ` — ${club}` : ""}`,
    description: player
      ? `${player.position} · ${player.overall} overall · ${player.goals} goals and ${player.assists} assists in ${player.minutes} minutes. ${player.summary.slice(0, 120)}`
      : tp("metaDescriptionFallback"),
    path: `/player/${slug}`,
  });
}

export default async function PlayerDetailPage({ params }: Props) {
  const { slug } = await params;
  const tw = await getTranslations("world");
  const tp = await getTranslations("worldPlayer");
  const result = await load(slug);

  if (!result.ok) {
    if (result.notFound) notFound();
    return <WorldUnavailable message={result.message} />;
  }

  const {
    player,
    season_stats: season,
    recent_form: recentForm,
    stat_lines: statLines,
    training_log: trainingLog,
    method,
  } = result.data;
  const attributes = Object.entries(player.attributes).sort(([, a], [, b]) => b - a);
  const radar = attributes.slice(0, 6).map(([key, value]) => ({ key, label: key.replace(/_/g, " "), value }));
  const path = `/player/${player.slug}`;
  const consistent = season.consistency_check.startsWith("totals equal");
  const trainedMinutes = trainingLog.items.reduce((sum, row) => sum + row.duration_min, 0);
  const trainedLoad = trainingLog.items.reduce((sum, row) => sum + row.load_units, 0);
  const trainingConsistent = trainedMinutes === trainingLog.total_minutes && trainedLoad === trainingLog.total_load;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world/players", label: tp("backLabel") }}
        eyebrow={tp("eyebrow", { world: tw("title"), position: player.position, nation: player.nation })}
        lede={player.summary}
        provenance={result.data}
        title={player.name}
      >
        <div className="tag-list" style={{ marginTop: "0.75rem" }}>
          <span className="world-pos">{player.position}</span>
          {player.secondary_positions.map((position) => (
            <span className="world-pos" key={position} title={tp("secondaryPosition")}>
              {position}
            </span>
          ))}
          <span className="chip num">{player.overall} OVR</span>
          <span className="chip num" title={tp("potentialHint")}>
            {player.potential} POT
          </span>
          <span className="chip">{player.age} yrs</span>
          <span className="chip">
            {player.height_cm === null ? tp("heightNotRecorded") : tp("heightValue", { height: player.height_cm })}
          </span>
          <span className="chip">{tp("foot", { foot: player.preferred_foot })}</span>
          <span className="chip">{player.archetype}</span>
          <span className="chip">
            {tp("clubLabel")} <EntityLink href={player.club?.path} label={player.club?.name} fallback={tp("noClub")} />
          </span>
          <span className="chip">
            {tp("leagueLabel")} <CompetitionLink competition={player.competition} />
          </span>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Athlete",
          name: player.name,
          description: player.summary,
          url: absolute(path),
          sport: "Association Football",
          nationality: player.nation,
          height: player.height_cm === null ? undefined : `${player.height_cm}cm`,
          additionalProperty: [
            { name: "position", value: player.position },
            { name: "overall", value: player.overall },
            { name: "season", value: season.season },
            { name: "goals", value: season.goals },
            { name: "assists", value: season.assists },
          ],
          team: player.club
            ? { "@type": "SportsTeam", name: player.club.name, url: absolute(player.club.path) }
            : undefined,
        }}
      />

      <div className="grid grid-2">
        <Panel eyebrow={tp("seasonEyebrow", { season: season.season })} title={tp("seasonTotalsTitle")}>
          <div className="stack">
            <KeyValueGrid
              rows={[
                [tp("rowAppearances"), season.appearances],
                [tp("rowStarts"), season.starts],
                [tp("rowMinutes"), season.minutes],
                [tp("rowGoals"), season.goals],
                [tp("rowAssists"), season.assists],
                [tp("rowCleanSheets"), season.clean_sheets],
                [tp("rowCards"), `${season.yellow_cards} / ${season.red_cards}`],
                [tp("rowRating"), season.rating.toFixed(2)],
                [tp("rowMatchesStored"), season.matches_stored],
                [tp("rowArchetypeFit"), `${Math.round(player.archetype_match * 100)}%`],
                [tp("rowFormIndex"), player.form.toFixed(2)],
              ]}
            />
            <div className={`notice ${consistent ? "" : "notice--warn"}`}>
              <span className="eyebrow">{tp("consistency")}</span>
              <p>
                <span className="mono">{season.stored_from}</span> — {season.consistency_check}.
              </p>
            </div>
            {method.season_totals && (
              <p className="muted world-section-note">
                {tp("seasonTotalsNote", { formula: method.season_totals })}
              </p>
            )}
          </div>
        </Panel>

        <Panel eyebrow={tp("attributeEyebrow", { count: attributes.length })} title={tp("attributeTitle")}>
          <div className="stack">
            <AttributeRadar label={tp("radarLabel", { name: player.name })} size={260} values={radar} />
            <p className="muted world-section-note">{tp("attributeNote")}</p>
          </div>
        </Panel>
      </div>

      <div className="grid grid-2">
        <Panel eyebrow={tp("derivationEyebrow")} title={tp("derivationTitle")}>
          <ReasonList items={player.derivation_reasons} title={tp("derivationReasonTitle")} />
        </Panel>
        <Panel eyebrow={tp("recentFormEyebrow")} title={tp("recentFormTitle")}>
          {recentForm.length > 0 ? (
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{tp("thDate")}</th>
                    <th scope="col">{tp("thMatch")}</th>
                    <th scope="col">{tp("thRole")}</th>
                    <th scope="col">{tp("thMin")}</th>
                    <th scope="col">{tp("thGoalsShort")}</th>
                    <th scope="col">{tp("thAssistsShort")}</th>
                    <th scope="col">{tp("rowRating")}</th>
                  </tr>
                </thead>
                <tbody>
                  {recentForm.map((row) => (
                    <tr key={row.match_id}>
                      <td className="muted mono">{formatDay(row.kickoff_at)}</td>
                      <td>
                        <Link className="world-link" href={row.match_path}>
                          {tp("matchCentre")}
                        </Link>
                      </td>
                      <td className="muted">{row.role}</td>
                      <td className="num">{row.minutes}</td>
                      <td className="num">{row.goals}</td>
                      <td className="num">{row.assists}</td>
                      <td className="num">{row.rating.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <span className="unavailable">{tp("noAppearance")}</span>
          )}
        </Panel>
      </div>

      <Panel
        eyebrow={tp("trainingEyebrow", { sessions: trainingLog.sessions, minutes: trainingLog.total_minutes })}
        title={tw("trainingLogLink")}
      >
        <div className="stack">
          <KeyValueGrid
            rows={[
              [tp("rowSessions"), trainingLog.sessions],
              [tp("rowMinutes"), trainingLog.total_minutes],
              [tp("rowLoadUnits"), trainingLog.total_load],
              [tp("rowMeanRpe"), trainingLog.sessions === 0 ? "—" : trainingLog.mean_rpe],
              [tp("rowFocusAreas"), trainingLog.categories.length === 0 ? "—" : trainingLog.categories.join(", ")],
              [tp("rowDrillsUsed"), trainingLog.drills.length],
            ]}
          />
          {trainingLog.items.length > 0 ? (
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{tp("thDate")}</th>
                    <th scope="col">{tp("thDrill")}</th>
                    <th scope="col">{tp("thFocus")}</th>
                    <th scope="col">{tp("thDiff")}</th>
                    <th scope="col">{tp("thMin")}</th>
                    <th scope="col">{tp("thRpe")}</th>
                    <th scope="col">{tp("thLoad")}</th>
                  </tr>
                </thead>
                <tbody>
                  {trainingLog.items.map((row) => (
                    <tr key={row.id}>
                      <td className="muted mono">{row.date}</td>
                      <td>
                        <Link className="world-link" href={row.drill_path}>
                          {row.drill_title}
                        </Link>
                      </td>
                      <td className="muted">{row.category}</td>
                      <td className="num">{row.difficulty}</td>
                      <td className="num">{row.duration_min}</td>
                      <td className="num">{row.rpe}</td>
                      <td className="num">{row.load_units}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <span className="unavailable">{tp("noSession")}</span>
          )}
          <div className={`notice ${trainingConsistent ? "" : "notice--warn"}`}>
            <span className="eyebrow">{tp("consistency")}</span>
            <p>
              <span className="mono">{trainingLog.load_formula}</span> —{" "}
              {trainingConsistent
                ? tp("totalsAgree", { count: trainingLog.items.length })
                : tp("totalsDisagree", {
                    totalMinutes: trainingLog.total_minutes,
                    trainedMinutes,
                    totalLoad: trainingLog.total_load,
                    trainedLoad,
                  })}
              .
            </p>
          </div>
          <p className="muted world-section-note">
            {tp("trainingNoteLead")} {" "}
            <Link className="world-link" href="/world/training">
              {tp("trainingLogLinkText")}
            </Link>
            {tp("trainingNoteTail")}
          </p>
        </div>
      </Panel>

      <Panel eyebrow={tp("attributesEyebrow", { count: attributes.length })} title={tp("attributesTitle")}>
        <div className="grid grid-2">
          {attributes.map(([key, value]) => (
            <Meter key={key} label={key.replace(/_/g, " ")} value={value} />
          ))}
        </div>
      </Panel>

      <Panel eyebrow={tp("statLinesEyebrow", { count: statLines.length })} title={tp("statLinesTitle")}>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{tp("thDate")}</th>
                <th scope="col">{tp("thCompetition")}</th>
                <th scope="col">{tp("thPos")}</th>
                <th scope="col">{tp("thMin")}</th>
                <th scope="col">{tp("thGoalsShort")}</th>
                <th scope="col">{tp("thAssistsShort")}</th>
                <th scope="col">{tp("thShots")}</th>
                <th scope="col">{tp("thOnTarget")}</th>
                <th scope="col">{tp("thPasses")}</th>
                <th scope="col">{tp("thKey")}</th>
                <th scope="col">{tp("thTkl")}</th>
                <th scope="col">{tp("thInt")}</th>
                <th scope="col">{tp("thSv")}</th>
                <th scope="col">{tp("thFoul")}</th>
                <th scope="col">{tp("rowRating")}</th>
                <th scope="col">{tp("thMatch")}</th>
              </tr>
            </thead>
            <tbody>
              {statLines.map((line) => (
                <tr key={line.id}>
                  <td className="muted mono">{formatDay(line.kickoff_at)}</td>
                  <td className="muted">{line.competition?.name ?? "—"}</td>
                  <td>
                    <span className="world-pos">{line.position}</span>
                  </td>
                  <td className="num">{line.minutes}</td>
                  <td className="num">{line.goals}</td>
                  <td className="num">{line.assists}</td>
                  <td className="num">{line.shots}</td>
                  <td className="num">{line.shots_on_target}</td>
                  <td className="num muted">
                    {line.passes_accurate}/{line.passes}
                  </td>
                  <td className="num">{line.key_passes}</td>
                  <td className="num">{line.tackles}</td>
                  <td className="num">{line.interceptions}</td>
                  <td className="num">{line.saves}</td>
                  <td className="num">{line.fouls}</td>
                  <td className="num">{line.rating.toFixed(2)}</td>
                  <td>
                    <EntityLink href={line.match_path} label={tp("centre")} fallback="—" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {method.rating && (
          <p className="muted world-section-note" style={{ marginTop: "0.6rem" }}>
            {tp("ratingNote", { formula: method.rating })}
          </p>
        )}
      </Panel>

      <Provenance provenance={result.data} />
    </div>
  );
}
