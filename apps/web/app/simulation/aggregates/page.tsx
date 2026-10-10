import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Panel } from "@/components/ui";
import { WorldHead, WorldUnavailable } from "@/components/world";
import { currentUser, serverFetch } from "@/lib/server";
import { readWorld } from "@/lib/world";
import type { CompetitionList, SimAggLeagueRules } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Simulation aggregates",
  description: "Cross-career league ledgers and player aggregates, summed from sim_events.",
  robots: { index: false, follow: false },
};

/**
 * The index the two aggregate doors' back links promised: `/simulation/aggregates/league` and
 * `/simulation/aggregates` were both dead until this page existed — the walk's console gate
 * caught the 404s. One ledger per competition, reached through the world's own competition
 * list; the player door is explained rather than enumerated (the world has hundreds of players,
 * and a list nobody paged through is not an index).
 */
export default async function AggregatesIndexPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fsimulation%2Faggregates");

  const [comps, rules] = await Promise.all([
    readWorld<CompetitionList>("/world/competitions", { page_size: 50 }),
    serverFetch<SimAggLeagueRules>("/simulation/aggregates/rules"),
  ]);

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/simulate", label: "Simulation" }}
        eyebrow="Cross-career aggregates · summed, never stored"
        title="Simulation aggregates"
        lede="Two read-only doors over the match events every career stored. Nothing here is written: a ledger is a sum over sim_events rows, recomputed on each request, and its consistency check is printed beside it."
      />

      <Panel eyebrow="League ledgers" title="One ledger per competition">
        {comps.ok ? (
          <div className="stack-sm">
            <ul className="list">
              {comps.data.items.map((competition) => (
                <li className="list__item" key={competition.slug}>
                  <Link className="h3" href={`/simulation/aggregates/league/${competition.slug}`}>
                    {competition.name}
                  </Link>
                  <span className="muted" style={{ fontSize: "0.82rem" }}>
                    {competition.kind} · {competition.team_count} teams · {competition.season}
                  </span>
                </li>
              ))}
            </ul>
            <p className="muted world-section-note">
              A competition whose careers stored no events still answers — its totals are zero, and the page says so rather than
              pretending the season never happened.
            </p>
          </div>
        ) : (
          <WorldUnavailable message={comps.message} title="League ledgers" />
        )}
      </Panel>

      <Panel eyebrow="Player aggregates" title="One ledger per player">
        <div className="stack-sm">
          <p className="muted">
            The player door aggregates one player&apos;s events across every career whose fixtures they appeared in. It is reached from a
            player, not from a list: the world&apos;s player pages are the way in.
          </p>
          <Link className="btn btn--sm" href="/world/players">
            Browse the world&apos;s players
          </Link>
        </div>
      </Panel>

      {rules.ok && (
        <Panel eyebrow="The vocabulary door" title="What the rules endpoint publishes">
          <dl className="world-kv">
            <div className="world-kv__row">
              <dt>node kinds</dt>
              <dd className="mono">{rules.data.node_kinds.join(", ")}</dd>
            </div>
            <div className="world-kv__row">
              <dt>edge verbs</dt>
              <dd className="mono">{rules.data.edge_verbs.join(", ")}</dd>
            </div>
          </dl>
          <p className="muted world-section-note" style={{ marginTop: "0.7rem" }}>
            The same vocabulary the graph surface walks, printed here because an aggregate that will not name its own shape is a number
            with no address.
          </p>
        </Panel>
      )}
    </div>
  );
}
