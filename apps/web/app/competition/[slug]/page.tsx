import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Panel } from "@/components/ui";
import { EntityLink, JsonLd, KeyValueGrid, MatchRow, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute, pageMetadata } from "@/lib/site";
import { cleanParams, readWorld } from "@/lib/world";
import type { CompetitionDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

async function load(slug: string, season?: string) {
  return readWorld<CompetitionDetail>(`/world/competitions/${encodeURIComponent(slug)}`, season ? { season } : undefined);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const result = await load(slug);
  const competition = result.ok ? result.data.competition : null;
  const name = competition?.name ?? slug.replace(/-/g, " ");
  return pageMetadata({
    title: `${name} — ${competition?.kind === "league" ? "league" : "cup"}`,
    description: competition
      ? `${competition.summary.slice(0, 220)}`
      : "Competition page in the FOOTBALL OS generated football world.",
    path: `/competition/${slug}`,
  });
}

export default async function CompetitionDetailPage({ params, searchParams }: Props) {
  const [{ slug }, rawQuery] = await Promise.all([params, searchParams]);
  const query = cleanParams(rawQuery);
  const result = await load(slug, query.season);

  if (!result.ok) {
    if (result.notFound) notFound();
    return <WorldUnavailable message={result.message} />;
  }

  const { competition, standings, teams, fixtures, completed, scheduled, format_note: formatNote, season } = result.data;
  const path = `/competition/${competition.slug}`;
  const isLeague = standings.length > 0;
  const entrants = teams.filter((team): team is NonNullable<typeof team> => Boolean(team));

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world/competitions", label: "All competitions" }}
        eyebrow={`Football World · ${competition.kind} · tier ${competition.tier} · ${competition.region}`}
        lede={competition.summary}
        provenance={result.data}
        title={competition.name}
      >
        <div className="tag-list" style={{ marginTop: "0.75rem" }}>
          <span className="chip">{competition.country}</span>
          <span className="chip">{season}</span>
          <span className="chip num">{completed} played</span>
          <span className="chip num">{scheduled} scheduled</span>
          <span className="chip num">{teams.length} clubs</span>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "SportsOrganization",
          name: competition.name,
          description: competition.summary,
          url: absolute(path),
          sport: "Association Football",
          member: entrants.slice(0, 40).map((team) => ({ "@type": "SportsTeam", name: team.name, url: absolute(team.path) })),
        }}
      />

      <Panel eyebrow="What this page is allowed to claim" title="Format &amp; provenance">
        <div className="stack">
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            {formatNote}
          </p>
          <KeyValueGrid
            rows={[
              ["Format", competition.kind],
              ["Tier", competition.tier],
              ["Region", competition.region],
              ["Country", competition.country],
              ["Season shown", season],
              ["Rows on this page", `${completed + scheduled} fixtures · ${standings.length} table rows`],
            ]}
          />
        </div>
      </Panel>

      <Panel eyebrow={`${standings.length} clubs with at least one played fixture`} title="Table">
        {isLeague ? (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Club</th>
                  <th scope="col">P</th>
                  <th scope="col">W</th>
                  <th scope="col">D</th>
                  <th scope="col">L</th>
                  <th scope="col">GF</th>
                  <th scope="col">GA</th>
                  <th scope="col">GD</th>
                  <th scope="col">Pts</th>
                </tr>
              </thead>
              <tbody>
                {standings.map((row) => (
                  <tr key={row.team_id}>
                    <td className="num muted">{row.position}</td>
                    <td>
                      <EntityLink href={row.team?.path} label={row.name} />
                    </td>
                    <td className="num">{row.played}</td>
                    <td className="num">{row.won}</td>
                    <td className="num">{row.drawn}</td>
                    <td className="num">{row.lost}</td>
                    <td className="num">{row.goals_for}</td>
                    <td className="num">{row.goals_against}</td>
                    <td className="num">{row.goal_difference > 0 ? `+${row.goal_difference}` : row.goal_difference}</td>
                    <td className="num" style={{ fontWeight: 700 }}>
                      {row.points}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="stack-sm">
            <span className="unavailable">No league table</span>
            <p className="muted" style={{ fontSize: "0.9rem" }}>
              This is a {competition.kind}: progression is the bracket of {fixtures.length} drawn fixtures below, so a points table would be
              invented rather than read. The clubs that take part are listed under “Entrants”.
            </p>
          </div>
        )}
      </Panel>

      <Panel eyebrow={`${entrants.length} clubs`} title="Entrants">
        <div className="tag-list">
          {entrants.map((team) => (
            <Link className="chip" href={team.path} key={team.id}>
              {team.name}
            </Link>
          ))}
        </div>
      </Panel>

      <Panel eyebrow={`${fixtures.length} fixtures in ${season}`} title="Fixtures &amp; results">
        <ul className="world-list">
          {fixtures.map((match) => (
            <MatchRow match={match} key={match.id} />
          ))}
        </ul>
      </Panel>

      <Provenance provenance={result.data} />
    </div>
  );
}
