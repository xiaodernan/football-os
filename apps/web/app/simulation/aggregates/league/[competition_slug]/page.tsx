import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { Panel } from "@/components/ui";
import { JsonLd, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { SimAggLeagueLedger } from "@/lib/types";

import "../../../../../styles/tactics.css";
import "../../../../../styles/simulate.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "League Ledger",
  description: "Cross-career league-wide ledger summed from sim_events.",
  robots: { index: false, follow: false },
};

export default async function LeagueLedgerPage({ params }: { params: Promise<{ competition_slug: string }> }) {
  const { competition_slug } = await params;

  const user = await currentUser();
  if (!user) redirect(`/login?next=%2Fsimulation%2Faggregates%2Fleague%2F${encodeURIComponent(competition_slug)}`);

  const ledgerResult = await serverFetch<SimAggLeagueLedger>(`/simulation/aggregates/league/${encodeURIComponent(competition_slug)}`);
  if (!ledgerResult.ok) {
    if (ledgerResult.status === 404 || ledgerResult.error.code === "not_found") notFound();
    return <WorldUnavailable detail={ledgerResult.error.message} message="The league ledger door did not answer." title="League Ledger" />;
  }

  const ledger = ledgerResult.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/simulation/aggregates", label: "Simulation aggregates" }}
        eyebrow={`${ledger.fixtures_played} fixtures · ${ledger.players_with_events} players · ${ledger.totals.goals} goals`}
        lede="Every figure below is a sum over sim_events rows from all careers whose club is in this competition. The ledger is a pure read: nothing is stored, and the consistency check compares the same season's goals from the event rows against the career's own fixture list."
        title={ledger.competition.name}
      >
        <div className="tag-list" style={{ marginTop: "0.7rem" }}>
          <span className="chip mono" title="Competition slug" data-competition-slug>{ledger.competition.slug}</span>
          <span className="chip num">{ledger.fixtures_traced} traced / {ledger.fixtures_played} played</span>
          <span className="chip num">{ledger.players_with_events} players with events</span>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CreativeWork",
          name: `${ledger.competition.name} — League Ledger`,
          url: absolute(`/simulation/aggregates/league/${ledger.competition.slug}`),
          license: "Private to the platform; derived from synthetic demo data",
          isAccessibleForFree: false,
        }}
      />

      <div className="tac-boards">
        <Panel eyebrow="Sum over all clubs in this competition" title="League totals" data-testid="league-totals">
          <div className="grid grid-3">
            <div className="stack-sm">
              <dt className="muted">Total events</dt>
              <dd className="num mono">{ledger.totals.events}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Goals</dt>
              <dd className="num mono">{ledger.totals.goals}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Expected goals</dt>
              <dd className="num mono">{ledger.totals.expected_goals.toFixed(3)}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Attempts</dt>
              <dd className="num mono">{ledger.totals.attempts}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Yellow cards</dt>
              <dd className="num mono">{ledger.totals.yellow_cards}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Red cards</dt>
              <dd className="num mono">{ledger.totals.red_cards}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Injuries</dt>
              <dd className="num mono">{ledger.totals.injuries}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Expected goals</dt>
              <dd className="num mono">{ledger.totals.expected_goals.toFixed(3)}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">Fixtures traced</dt>
              <dd className="num mono">{ledger.fixtures_traced} / {ledger.fixtures_played}</dd>
            </div>
          </div>
          <p className="tac-formula">{ledger.formula}</p>
          <p className="tac-formula">{ledger.consistency_formula}</p>
          <p className="tac-formula">{ledger.attribution_formula}</p>
          <p className="notice notice--warn">{ledger.disclaimer}</p>
        </Panel>

        <Panel eyebrow={`${ledger.fixtures_traced} fixtures traced · ${ledger.fixtures_untraced} untraced`} title="Consistency" data-testid="league-consistency">
          <p className="muted">{ledger.consistency}</p>
        </Panel>

        <Panel eyebrow={`${ledger.totals.events} events · ${ledger.players_with_events} players with events`} title="By event type" data-testid="league-by-type">
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
                {Object.entries(ledger.by_type).map(([type, entry]) => (
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

        <Panel eyebrow={`${ledger.unattributed.events.ambiguous} ambiguous · ${ledger.unattributed.events.unnamed} unnamed`} title="Unattributed" data-testid="league-unattributed">
          {ledger.unattributed.ambiguous_names.length > 0 && (
            <p className="muted world-section-note">
              Ambiguous names: {ledger.unattributed.ambiguous_names.join(", ")}
            </p>
          )}
          {ledger.unattributed.unnamed_names.length > 0 && (
            <p className="muted world-section-note">
              Unnamed: {ledger.unattributed.unnamed_names.join(", ")}
            </p>
          )}
          {ledger.unattributed.ambiguous_names.length === 0 && ledger.unattributed.unnamed_names.length === 0 && (
            <p className="muted">No unattributed events.</p>
          )}
        </Panel>

        <Panel eyebrow={`${ledger.players_with_events} players · ${ledger.players_shown} shown`} title="Top players" data-testid="league-players">
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
                {ledger.players.map((player) => (
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
          {ledger.truncated && (
            <p className="muted world-section-note">
              Showing {ledger.players_shown} of {ledger.players_with_events} players.
            </p>
          )}
        </Panel>

        <Provenance
          provenance={{ data_origin: ledger.data_origin, is_demo_data: ledger.is_demo_data, disclaimer: ledger.disclaimer }}
          extra={<span className="chip">{ledger.scope}</span>}
        />
      </div>
    </div>
  );
}
