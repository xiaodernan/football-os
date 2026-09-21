import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Panel, ReasonList } from "@/components/ui";
import {
  CompetitionLink,
  Crest,
  EntityLink,
  JsonLd,
  KeyValueGrid,
  MatchRow,
  Provenance,
  WorldHead,
  WorldUnavailable,
  formatDay,
} from "@/components/world";
import { absolute, pageMetadata } from "@/lib/site";
import { brandColor, readWorld } from "@/lib/world";
import type { TeamDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

async function load(slug: string) {
  return readWorld<TeamDetail>(`/world/teams/${encodeURIComponent(slug)}`);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const result = await load(slug);
  const team = result.ok ? result.data.team : null;
  const name = team?.name ?? slug.replace(/-/g, " ");
  return pageMetadata({
    title: `${name} — club profile`,
    description: team
      ? `${team.summary.slice(0, 220)} Every figure is generated demo data.`
      : "Club profile in the FOOTBALL OS generated football world.",
    path: `/team/${slug}`,
  });
}

export default async function TeamDetailPage({ params }: Props) {
  const { slug } = await params;
  const result = await load(slug);

  if (!result.ok) {
    if (result.notFound) notFound();
    return <WorldUnavailable message={result.message} />;
  }

  const { team, squad, fixtures, recent_stat_lines: recentLines, squad_notes: squadNotes } = result.data;
  const path = `/team/${team.slug}`;
  const played = fixtures.filter((match) => match.status === "completed");
  const upcoming = fixtures.filter((match) => match.status !== "completed");
  const lineGroups = recentLines.reduce<Record<string, typeof recentLines>>((groups, line) => {
    const key = line.match_slug ?? "unknown";
    (groups[key] ??= []).push(line);
    return groups;
  }, {});

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world/teams", label: "All clubs" }}
        eyebrow={`Football World · club · ${team.nation}`}
        lede={team.summary}
        provenance={result.data}
        title={team.name}
      >
        <div className="row wrap" style={{ gap: "0.5rem", marginTop: "0.75rem" }}>
          <Crest color={brandColor(team.brand_color)} name={team.short_name || team.name} />
          <div className="tag-list">
            <span className="chip mono">{team.short_name}</span>
            <span className="chip">{team.formation}</span>
            <span className="chip num">{team.overall} OVR</span>
            <span className="chip num">{team.squad_size} in squad</span>
            <span className="chip">
              <CompetitionLink competition={team.competition} />
            </span>
            <span className="chip">{team.season}</span>
          </div>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "SportsTeam",
          name: team.name,
          description: team.summary,
          url: absolute(path),
          sport: "Association Football",
          address: { "@type": "PostalAddress", addressLocality: team.city, addressCountry: team.nation },
          ...(team.competition
            ? { organizer: { "@type": "SportsOrganization", name: team.competition.name, url: absolute(team.competition.path) } }
            : {}),
          athlete: squad.slice(0, 25).map((player) => ({ "@type": "Person", name: player.name, url: absolute(player.path) })),
        }}
      />

      <div className="grid grid-2">
        <Panel eyebrow="Ground & staff" title="Identity">
          <KeyValueGrid
            rows={[
              ["City", team.city],
              ["Ground", team.stadium],
              ["Capacity", team.capacity.toLocaleString("en-GB")],
              ["Manager", team.manager_name],
              ["Shape", <span className="mono" key="shape">{team.formation}</span>],
              ["Season", team.season],
              [
                "League",
                team.competition ? (
                  <Link className="world-link" href={team.competition.path}>
                    {team.competition.name}
                  </Link>
                ) : (
                  <span className="unavailable">no league</span>
                ),
              ],
              [
                "Mean overall",
                <span key="mean-overall" title="Averaged over the stored squad rows — not an independent rating.">{team.overall}</span>,
              ],
            ]}
          />
        </Panel>

        <Panel eyebrow="How to read this club" title="Derivation notes">
          <div className="stack">
            <ReasonList items={squadNotes} title="What these numbers are" />
            <p className="muted world-section-note">
              {played.length} played and {upcoming.length} unplayed fixtures in this view — the 40 most recent by kick-off. Unplayed rows
              show a kick-off time and nothing else.
            </p>
          </div>
        </Panel>
      </div>

      <Panel eyebrow={`${squad.length} registered`} title="Squad">
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Pos</th>
                <th scope="col">Name</th>
                <th scope="col">Age</th>
                <th scope="col">Nation</th>
                <th scope="col">Foot</th>
                <th scope="col">OVR</th>
                <th scope="col">POT</th>
                <th scope="col">Goals</th>
                <th scope="col">Assists</th>
                <th scope="col">Minutes</th>
                <th scope="col">Rating</th>
              </tr>
            </thead>
            <tbody>
              {squad.map((player) => (
                <tr key={player.id}>
                  <td>
                    <span className="world-pos">{player.position}</span>
                  </td>
                  <td>
                    <EntityLink href={player.path} label={player.name} />
                  </td>
                  <td className="num">{player.age}</td>
                  <td className="muted">{player.nation}</td>
                  <td className="muted">{player.preferred_foot}</td>
                  <td className="num">{player.overall}</td>
                  <td className="num muted">{player.potential}</td>
                  <td className="num">{player.goals}</td>
                  <td className="num">{player.assists}</td>
                  <td className="num muted">{player.minutes}</td>
                  <td className="num">{player.rating.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted world-section-note" style={{ marginTop: "0.6rem" }}>
          Ordered by overall, then name. Height is omitted where the generator left it blank rather than shown as 0 cm.
        </p>
      </Panel>

      <div className="grid grid-2">
        <Panel eyebrow={`${played.length} results`} title="Played">
          {played.length > 0 ? (
            <ul className="world-list">
              {played.slice(0, 12).map((match) => (
                <MatchRow match={match} key={match.id} />
              ))}
            </ul>
          ) : (
            <span className="unavailable">No completed fixture stored for this club.</span>
          )}
        </Panel>
        <Panel eyebrow={`${upcoming.length} to come`} title="Scheduled">
          {upcoming.length > 0 ? (
            <ul className="world-list">
              {upcoming.slice(0, 12).map((match) => (
                <MatchRow match={match} key={match.id} />
              ))}
            </ul>
          ) : (
            <span className="unavailable">Nothing scheduled in this view.</span>
          )}
        </Panel>
      </div>

      {Object.keys(lineGroups).length > 0 && (
        <Panel eyebrow="From real_player_match_stats" title="Per-match lines, most recent games">
          <div className="stack">
            {Object.entries(lineGroups)
              .slice(0, 3)
              .map(([matchSlug, lines]) => (
                <div className="stack-sm" key={matchSlug}>
                  <p className="eyebrow">
                    <Link className="world-link" href={lines[0]?.match_path ?? "/world/matches"}>
                      {formatDay(lines[0]?.kickoff_at)} · {lines[0]?.competition?.name ?? "match"} · {lines.length} lines
                    </Link>
                  </p>
                  <div className="world-tablewrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th scope="col">Player</th>
                          <th scope="col">Role</th>
                          <th scope="col">Min</th>
                          <th scope="col">G</th>
                          <th scope="col">A</th>
                          <th scope="col">Shots</th>
                          <th scope="col">Passes</th>
                          <th scope="col">Tkl</th>
                          <th scope="col">Rating</th>
                        </tr>
                      </thead>
                      <tbody>
                        {lines.map((line) => (
                          <tr key={line.id}>
                            <td>
                              <EntityLink href={line.player?.path} label={line.player?.name} />
                            </td>
                            <td className="muted">{line.role}</td>
                            <td className="num">{line.minutes}</td>
                            <td className="num">{line.goals}</td>
                            <td className="num">{line.assists}</td>
                            <td className="num">{line.shots}</td>
                            <td className="num muted">
                              {line.passes_accurate}/{line.passes}
                            </td>
                            <td className="num">{line.tackles}</td>
                            <td className="num">{line.rating.toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
          </div>
        </Panel>
      )}

      <Provenance provenance={result.data} />
    </div>
  );
}
