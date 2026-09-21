import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Panel, ReasonList } from "@/components/ui";
import {
  EntityLink,
  JsonLd,
  KeyValueGrid,
  OriginBadge,
  Provenance,
  WorldHead,
  WorldUnavailable,
  formatMoment,
} from "@/components/world";
import { absolute, pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { MatchDetail, StatPair } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

async function load(slug: string) {
  return readWorld<MatchDetail>(`/world/matches/${encodeURIComponent(slug)}`);
}

function isPair(value: number | StatPair | Record<string, string>): value is StatPair {
  return typeof value === "object" && "home" in value && "away" in value;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const result = await load(slug);
  const match = result.ok ? result.data.match : null;
  const title = match ? `${match.home?.name ?? "Home"} v ${match.away?.name ?? "Away"}` : slug.replace(/-/g, " ");
  return pageMetadata({
    title: `${title} — match centre`,
    description: match
      ? `${match.round_label}, ${match.season}. ${match.status === "completed" ? match.summary : "Scheduled: no score exists for this fixture yet."}`
      : "Match centre in the FOOTBALL OS generated football world.",
    path: `/match/${slug}`,
  });
}

export default async function MatchDetailPage({ params }: Props) {
  const { slug } = await params;
  const result = await load(slug);

  if (!result.ok) {
    if (result.notFound) notFound();
    return <WorldUnavailable message={result.message} />;
  }

  const { match, line_ups: lineUps, stat_lines: statLines, available, note, method, goals_check: goalsCheck } = result.data;
  const path = `/match/${match.slug}`;
  const title = `${match.home?.name ?? "Home"} v ${match.away?.name ?? "Away"}`;
  const metrics = Object.entries(match.stats).filter(
    ([key, value]) => key !== "method" && (typeof value === "number" || isPair(value)),
  ) as [string, number | StatPair][];
  const played = available && match.home_goals !== null && match.away_goals !== null;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world/matches", label: "All fixtures" }}
        eyebrow={`Football World · ${match.competition?.name ?? "fixture"} · ${match.round_label}`}
        lede={match.summary}
        provenance={result.data}
        title={title}
      >
        <div className="world-scoreline" style={{ marginTop: "0.9rem" }}>
          <div className="world-scoreline__side">
            <EntityLink href={match.home?.path} label={match.home?.name} />
            <span className="muted world-section-note">home</span>
          </div>
          <div className="world-scoreline__score">
            {played ? (
              <span className="num">
                {match.home_goals} – {match.away_goals}
              </span>
            ) : (
              <span className="unavailable">no score yet</span>
            )}
            <span className="eyebrow">{played ? "full time" : match.status}</span>
          </div>
          <div className="world-scoreline__side world-scoreline__side--away">
            <EntityLink href={match.away?.path} label={match.away?.name} />
            <span className="muted world-section-note">away</span>
          </div>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "SportsEvent",
          name: title,
          description: match.summary,
          url: absolute(path),
          startDate: match.kickoff_at,
          eventStatus: played ? "https://schema.org/EventCompleted" : "https://schema.org/EventScheduled",
          eventAttendance: typeof match.stats.attendance === "number" ? match.stats.attendance : undefined,
          location: { "@type": "SportsLocation", name: match.venue.name, address: match.venue.city },
          homeTeam: match.home ? { "@type": "SportsTeam", name: match.home.name, url: absolute(match.home.path) } : undefined,
          awayTeam: match.away ? { "@type": "SportsTeam", name: match.away.name, url: absolute(match.away.path) } : undefined,
          organizer: match.competition
            ? { "@type": "SportsOrganization", name: match.competition.name, url: absolute(match.competition.path) }
            : undefined,
          sport: "Association Football",
        }}
      />

      {!played && (
        <div className="notice notice--warn">
          {note ?? "This fixture has not been played, so there is nothing to report."} A scheduled row stores NULL for the score, so no
          placeholder is rendered — see the kick-off time below.
        </div>
      )}

      <div className="grid grid-2">
        <Panel eyebrow="Fixture" title="When &amp; where">
          <KeyValueGrid
            rows={[
              ["Kick-off", <span className="mono" key="kickoff">{formatMoment(match.kickoff_at)}</span>],
              ["Venue", `${match.venue.name}, ${match.venue.city}`],
              ["Competition", match.competition ? <Link className="world-link" href={match.competition.path}>{match.competition.name}</Link> : "—"],
              ["Season", match.season],
              ["Round", match.round_label],
              ["Status", match.status],
              ["Attendance", typeof match.stats.attendance === "number" ? match.stats.attendance.toLocaleString("en-GB") : <span className="unavailable">not recorded</span>],
            ]}
          />
        </Panel>

        <Panel
          eyebrow="The score is made of these"
          title="Team statistics"
          action={<OriginBadge provenance={match} />}
        >
          {metrics.length > 0 ? (
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Home</th>
                    <th scope="col">Metric</th>
                    <th scope="col">Away</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.map(([key, value]) => (
                    <tr key={key}>
                      <td className="num" style={{ textAlign: "right" }}>
                        {isPair(value) ? (typeof value.home === "number" ? value.home.toFixed(1).replace(/\.0$/, "") : "—") : "—"}
                      </td>
                      <td className="muted center" style={{ textTransform: "capitalize" }}>
                        {key.replace(/_/g, " ")}
                      </td>
                      <td className="num">
                        {isPair(value) ? (typeof value.away === "number" ? value.away.toFixed(1).replace(/\.0$/, "") : "—") : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <span className="unavailable">No team statistics stored: this fixture has not been played.</span>
          )}
          {played && (
            <div className="row wrap" style={{ gap: "0.5rem", marginTop: "0.6rem" }}>
              <span className="chip" title="Every goal in the score must belong to a player line.">
                goals in score: {goalsCheck.match_goals}
              </span>
              <span className="chip" title="Summed from the per-player lines.">
                goals in lines: {goalsCheck.line_up_goals}
              </span>
              {goalsCheck.match_goals === goalsCheck.line_up_goals ? (
                <span className="badge badge--live">RECONCILES</span>
              ) : (
                <span className="badge badge--demo">DOES NOT RECONCILE</span>
              )}
            </div>
          )}
        </Panel>
      </div>

      {played && (
        <div className="grid grid-2">
          {(["home", "away"] as const).map((side) => {
            const group = lineUps[side];
            return (
              <Panel
                eyebrow={`${side} · ${group.starters.length} starters, ${group.substitutes.length} used from the bench`}
                title={group.team?.name ?? "Team"}
                key={side}
              >
                <div className="world-tablewrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th scope="col">Role</th>
                        <th scope="col">Player</th>
                        <th scope="col">Pos</th>
                        <th scope="col">Min</th>
                        <th scope="col">G</th>
                        <th scope="col">A</th>
                        <th scope="col">Sh</th>
                        <th scope="col">P</th>
                        <th scope="col">Tk</th>
                        <th scope="col">Sv</th>
                        <th scope="col">Rt</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...group.starters, ...group.substitutes].map((line) => (
                        <tr key={line.id}>
                          <td className="muted">{line.role}</td>
                          <td>
                            <EntityLink href={line.player?.path} label={line.player?.name} />
                          </td>
                          <td>
                            <span className="world-pos">{line.position}</span>
                          </td>
                          <td className="num">{line.minutes}</td>
                          <td className="num">{line.goals}</td>
                          <td className="num">{line.assists}</td>
                          <td className="num">{line.shots}</td>
                          <td className="num muted">
                            {line.passes_accurate}/{line.passes}
                          </td>
                          <td className="num">{line.tackles}</td>
                          <td className="num">{line.saves}</td>
                          <td className="num">{line.rating.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
            );
          })}
        </div>
      )}

      {played && statLines.length > 0 && (
        <Panel eyebrow={`${statLines.length} stored lines · nothing entered twice`} title="Who scored">
          {statLines.some((line) => line.goals > 0) ? (
            <ul className="reasons">
              {statLines
                .filter((line) => line.goals > 0)
                .map((line) => (
                  <li className="reasons__item" key={line.id}>
                    <strong>{line.goals}×</strong> <EntityLink href={line.player?.path} label={line.player?.name} />{" "}
                    <span className="muted">
                      ({line.team_id === match.home?.id ? "home" : "away"}, {line.minutes}&#39;, rating {line.rating.toFixed(2)})
                    </span>
                  </li>
                ))}
            </ul>
          ) : (
            <span className="unavailable">No player line in this fixture records a goal.</span>
          )}
          <p className="muted world-section-note" style={{ marginTop: "0.6rem" }}>
            The two tables above are these same rows split by side: the score, the team statistics and the per-player lines all come from
            the one stored fixture, so they cannot disagree.
          </p>
        </Panel>
      )}

      {Object.keys(method).length > 0 && (
        <Panel eyebrow="No model, no feed" title="How each figure was produced">
          <ReasonList items={Object.entries(method).map(([key, value]) => `${key}: ${value}`)} title="Formulas" />
        </Panel>
      )}

      <Provenance provenance={result.data} />
    </div>
  );
}
