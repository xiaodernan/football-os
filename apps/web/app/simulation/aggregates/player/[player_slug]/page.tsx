import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { Panel } from "@/components/ui";
import { JsonLd, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { SimAggPlayerAggregate } from "@/lib/types";

import "../../styles/tactics.css";
import "../../styles/simulate.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Player Career Aggregate",
  description: "Cross-career player aggregate summed from sim_events.",
  robots: { index: false, follow: false },
};

export default async function PlayerAggregatePage({ params }: { params: Promise<{ player_slug: string }> }) {
  const { player_slug } = await params;

  const user = await currentUser();
  if (!user) redirect(`/login?next=%2Fsimulation%2Faggregates%2Fplayer%2F${encodeURIComponent(player_slug)}`);

  const result = await serverFetch<SimAggPlayerAggregate>(`/simulation/aggregates/player/${encodeURIComponent(player_slug)}`);
  if (!result.ok) {
    if (result.status === 404 || result.error.code === "not_found") notFound();
    return <WorldUnavailable detail={result.error.message} message="The player aggregate door did not answer." title="Player Career Aggregate" />;
  }

  const aggregate = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/simulation/aggregates", label: "Simulation aggregates" }}
        eyebrow={`${aggregate.careers.length} careers · ${aggregate.fixtures_played} fixtures · ${aggregate.totals.goals} goals`}
        lede="Every figure below is a sum over sim_events rows from all careers that have a player with this slug. The aggregate is a pure read: nothing is stored, and the consistency check compares the same events against themselves."
        title={aggregate.player.name}
      >
        <div className="tag-list" style={{ marginTop: "0.7rem" }}>
          <span className="chip mono" title="Player slug">{aggregate.player.slug}</span>
          <span className="chip mono" title="Position">{aggregate.player.position ?? "—"}</span>
          <span className="chip num">{aggregate.fixtures_played} fixtures</span>
          <span className="chip num">{aggregate.totals.goals} goals</span>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CreativeWork",
          name: `${aggregate.player.name} — Career Aggregate`,
          url: absolute(`/simulation/aggregates/player/${player_slug}`),
          license: "Private to the platform; derived from synthetic demo data",
          isAccessibleForFree: false,
        }}
      />

      <div className="tac-boards">
        <Panel eyebrow={`${aggregate.careers.length} career${aggregate.careers.length === 1 ? "" : "s"}`} title="Careers">
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Career</th>
                  <th scope="col">Club</th>
                  <th scope="col">Slug</th>
                </tr>
              </thead>
              <tbody>
                {aggregate.careers.map((career) => (
                  <tr key={career.id}>
                    <td className="mono">{career.slug}</td>
                    <td className="mono">{career.club_name} ({career.club_short})</td>
                    <td className="mono">{career.slug}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel eyebrow="Sum over all careers" title="Totals">
          <div className="grid grid-3">
            <div className="stack-sm">
              <dt className="muted">Total events</dt>
              <dd className="num mono">{aggregate.totals.events}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Goals</dt>
              <dd className="num mono">{aggregate.totals.goals}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Expected goals</dt>
              <dd className="num mono">{aggregate.totals.expected_goals.toFixed(3)}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Attempts</dt>
              <dd className="num mono">{aggregate.totals.attempts}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Yellow cards</dt>
              <dd className="num mono">{aggregate.totals.yellow_cards}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Red cards</dt>
              <dd className="num mono">{aggregate.totals.red_cards}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Injuries</dt>
              <dd className="num mono">{aggregate.totals.injuries}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Expected goals</dt>
              <dd className="num mono">{aggregate.totals.expected_goals.toFixed(3)}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Fixtures played</dt>
              <dd className="num mono">{aggregate.fixtures_played}</dd>
            </div>
          </div>
          <p className="tac-formula">{aggregate.formula}</p>
          <p className="tac-formula">{aggregate.consistency_formula}</p>
          <p className="tac-formula">{aggregate.attribution_formula}</p>
          <p className="notice notice--warn">{aggregate.disclaimer}</p>
        </Panel>

        <Panel eyebrow={`${aggregate.fixtures_traced} fixtures traced · ${aggregate.fixtures_untraced} untraced`} title="Consistency">
          <p className="muted">{aggregate.consistency}</p>
        </Panel>

        <Panel eyebrow={`${aggregate.totals.events} events · ${aggregate.players_with_events} players with events`} title="By event type">
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Type</th>
                  <th scope="col">Events</th>
                  <th scope="col">Identified</th>
                  <th scope="col">Ambiguous</th>
                  <th scope="col">Unnamed</th>
                  <th scope="col">Expected goals</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(aggregate.by_type).map(([type, entry]) => (
                  <tr key={type}>
                    <td className="mono">{type}</td>
                    <td className="num mono">{entry.events}</td>
                    <td className="num mono">{entry.identified}</td>
                    <td className="num mono">{entry.ambiguous}</td>
                    <td className="num mono">{entry.unnamed}</td>
                    <td className="num mono">{entry.expected_goals.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel eyebrow={`${aggregate.unattributed.events.ambiguous} ambiguous · ${aggregate.unattributed.events.unnamed} unnamed`} title="Unattributed">
          {aggregate.unattributed.ambiguous_names.length > 0 && (
            <p className="muted world-section-note">
              Ambiguous names: {aggregate.unattributed.ambiguous_names.join(", ")}
            </p>
          )}
          {aggregate.unattributed.unnamed_names.length > 0 && (
            <p className="muted world-section-note">
              Unnamed: {aggregate.unattributed.unnamed_names.join(", ")}
            </p>
          )}
          {aggregate.unattributed.ambiguous_names.length === 0 && aggregate.unattributed.unnamed_names.length === 0 && (
            <p className="muted">No unattributed events.</p>
          )}
        </Panel>

        <Panel eyebrow={`${aggregate.players_with_events} players with events · ${aggregate.players_shown} shown`} title="Players">
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Player</th>
                  <th scope="col">Position</th>
                  <th scope="col">Matches</th>
                  <th scope="col">Goals</th>
                  <th scope="col">Attempts</th>
                  <th scope="col">xG</th>
                  <th scope="col">Yellow</th>
                  <th scope="col">Red</th>
                  <th scope="col">Injuries</th>
                </tr>
              </thead>
              <tbody>
                {aggregate.players.map((player) => (
                  <tr key={player.player_id}>
                    <td>
                      <Link className="world-link" href={player.player_path ?? "#"}>
                        {player.name}
                      </Link>
                    </td>
                    <td className="mono">{player.position}</td>
                    <td className="num mono">{player.matches_with_events}</td>
                    <td className="num mono">{player.goals}</td>
                    <td className="num mono">{player.attempts}</td>
                    <td className="num mono">{player.expected_goals.toFixed(3)}</td>
                    <td className="num mono">{player.yellow_cards}</td>
                    <td className="num mono">{player.red_cards}</td>
                    <td className="num mono">{player.injuries}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {aggregate.truncated && (
            <p className="muted world-section-note">
              Showing {aggregate.players_shown} of {aggregate.players_with_events} players.
            </p>
          )}
        </Panel>

        <Provenance
          provenance={{ data_origin: aggregate.data_origin, is_demo_data: aggregate.is_demo_data, disclaimer: aggregate.disclaimer }}
          extra={<span className="chip">{aggregate.scope}</span>}
        />
      </div>
    </div>
  );
}