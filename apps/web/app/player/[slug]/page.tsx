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
  const result = await load(slug);
  const player = result.ok ? result.data.player : null;
  const name = player?.name ?? slug.replace(/-/g, " ");
  const club = player?.club?.name;
  return pageMetadata({
    title: `${name}${club ? ` — ${club}` : ""}`,
    description: player
      ? `${player.position} · ${player.overall} overall · ${player.goals} goals and ${player.assists} assists in ${player.minutes} minutes. ${player.summary.slice(0, 120)}`
      : "Player profile in the FOOTBALL OS generated football world.",
    path: `/player/${slug}`,
  });
}

export default async function PlayerDetailPage({ params }: Props) {
  const { slug } = await params;
  const tw = await getTranslations("world");
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
        back={{ href: "/world/players", label: "All players" }}
        eyebrow={`Football World · ${player.position} · ${player.nation}`}
        lede={player.summary}
        provenance={result.data}
        title={player.name}
      >
        <div className="tag-list" style={{ marginTop: "0.75rem" }}>
          <span className="world-pos">{player.position}</span>
          {player.secondary_positions.map((position) => (
            <span className="world-pos" key={position} title="Secondary position">
              {position}
            </span>
          ))}
          <span className="chip num">{player.overall} OVR</span>
          <span className="chip num" title="Ceiling the generator assigned from age and level, not a scout's grade.">
            {player.potential} POT
          </span>
          <span className="chip">{player.age} yrs</span>
          <span className="chip">{player.height_cm === null ? "height: not recorded" : `${player.height_cm} cm`}</span>
          <span className="chip">{player.preferred_foot} foot</span>
          <span className="chip">{player.archetype}</span>
          <span className="chip">
            club: <EntityLink href={player.club?.path} label={player.club?.name} fallback="no club" />
          </span>
          <span className="chip">
            league: <CompetitionLink competition={player.competition} />
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
        <Panel eyebrow={`${season.season} season`} title="Season totals">
          <div className="stack">
            <KeyValueGrid
              rows={[
                ["Appearances", season.appearances],
                ["Starts", season.starts],
                ["Minutes", season.minutes],
                ["Goals", season.goals],
                ["Assists", season.assists],
                ["Clean sheets", season.clean_sheets],
                ["Yellow / red", `${season.yellow_cards} / ${season.red_cards}`],
                ["Rating", season.rating.toFixed(2)],
                ["Matches stored", season.matches_stored],
                ["Archetype fit", `${Math.round(player.archetype_match * 100)}%`],
                ["Form index", player.form.toFixed(2)],
              ]}
            />
            <div className={`notice ${consistent ? "" : "notice--warn"}`}>
              <span className="eyebrow">Consistency</span>
              <p>
                <span className="mono">{season.stored_from}</span> — {season.consistency_check}.
              </p>
            </div>
            {method.season_totals && (
              <p className="muted world-section-note">
                season totals: <span className="mono">{method.season_totals}</span>
              </p>
            )}
          </div>
        </Panel>

        <Panel eyebrow={`highest six of ${attributes.length}`} title="Attribute profile">
          <div className="stack">
            <AttributeRadar label={`${player.name} attribute profile`} size={260} values={radar} />
            <p className="muted world-section-note">
              The full list is below; the radar shows the six highest so the shape is readable. Nothing here is a scouted grade — see the
              derivation notes.
            </p>
          </div>
        </Panel>
      </div>

      <div className="grid grid-2">
        <Panel eyebrow="Why each number is what it is" title="Derivation">
          <ReasonList items={player.derivation_reasons} title="Rules that produced this profile" />
        </Panel>
        <Panel eyebrow="recent_form" title="Last five appearances">
          {recentForm.length > 0 ? (
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col">Match</th>
                    <th scope="col">Role</th>
                    <th scope="col">Min</th>
                    <th scope="col">G</th>
                    <th scope="col">A</th>
                    <th scope="col">Rating</th>
                  </tr>
                </thead>
                <tbody>
                  {recentForm.map((row) => (
                    <tr key={row.match_id}>
                      <td className="muted mono">{formatDay(row.kickoff_at)}</td>
                      <td>
                        <Link className="world-link" href={row.match_path}>
                          match centre
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
            <span className="unavailable">No appearance recorded in the stored lines.</span>
          )}
        </Panel>
      </div>

      <Panel eyebrow={`${trainingLog.sessions} sessions · ${trainingLog.total_minutes} min`} title={tw("trainingLogLink")}>
        <div className="stack">
          <KeyValueGrid
            rows={[
              ["Sessions", trainingLog.sessions],
              ["Minutes", trainingLog.total_minutes],
              ["Load units", trainingLog.total_load],
              ["Mean RPE", trainingLog.sessions === 0 ? "—" : trainingLog.mean_rpe],
              ["Focus areas", trainingLog.categories.length === 0 ? "—" : trainingLog.categories.join(", ")],
              ["Drills used", trainingLog.drills.length],
            ]}
          />
          {trainingLog.items.length > 0 ? (
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col">Drill</th>
                    <th scope="col">Focus</th>
                    <th scope="col">Diff</th>
                    <th scope="col">Min</th>
                    <th scope="col">RPE</th>
                    <th scope="col">Load</th>
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
            <span className="unavailable">No session recorded for this player.</span>
          )}
          <div className={`notice ${trainingConsistent ? "" : "notice--warn"}`}>
            <span className="eyebrow">Consistency</span>
            <p>
              <span className="mono">{trainingLog.load_formula}</span> —{" "}
              {trainingConsistent
                ? `the totals above equal the ${trainingLog.items.length} rows printed here`
                : `totals and rows disagree: ${trainingLog.total_minutes}/${trainedMinutes} minutes, ${trainingLog.total_load}/${trainedLoad} load`}.
            </p>
          </div>
          <p className="muted world-section-note">
            These rows are this entry in{" "}
            <Link className="world-link" href="/world/training">
              the training log for the whole world
            </Link>
            , newest first. Nothing here is tracked data: a session is a catalogue drill the generator assigned to a synthetic player, and the
            load figure is the minutes and RPE in the two columns beside it multiplied. Drill names link into the Training Academy, which asks
            for an account; nothing else on this page does.
          </p>
        </div>
      </Panel>

      <Panel eyebrow={`${attributes.length} attributes, 1–99`} title="Full attribute list">
        <div className="grid grid-2">
          {attributes.map(([key, value]) => (
            <Meter key={key} label={key.replace(/_/g, " ")} value={value} />
          ))}
        </div>
      </Panel>

      <Panel eyebrow={`${statLines.length} rows · one per appearance`} title="Every stored statistic line">
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Competition</th>
                <th scope="col">Pos</th>
                <th scope="col">Min</th>
                <th scope="col">G</th>
                <th scope="col">A</th>
                <th scope="col">Shots</th>
                <th scope="col">On tgt</th>
                <th scope="col">Passes</th>
                <th scope="col">Key</th>
                <th scope="col">Tkl</th>
                <th scope="col">Int</th>
                <th scope="col">Sv</th>
                <th scope="col">Foul</th>
                <th scope="col">Rating</th>
                <th scope="col">Match</th>
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
                    <EntityLink href={line.match_path} label="centre" fallback="—" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {method.rating && (
          <p className="muted world-section-note" style={{ marginTop: "0.6rem" }}>
            rating formula: <span className="mono">{method.rating}</span>
          </p>
        )}
      </Panel>

      <Provenance provenance={result.data} />
    </div>
  );
}
