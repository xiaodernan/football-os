import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Panel } from "@/components/ui";
import { KeyValueGrid, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { SimulatorForm } from "@/components/SimulatorForm";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { SimList, SimOptions } from "@/lib/types";

import "../../styles/tactics.css";
import "../../styles/simulate.css";

export const dynamic = "force-dynamic";

/**
 * A simulation is model output about fictional clubs, and which fixtures an account chooses to play
 * is the account's own, so this page is not published: `robots: noindex`, disallowed in robots.ts, and
 * absent from the sitemap. The clubs and systems it offers are already public under `/world` and
 * `/tactics`; nothing new is exposed by the picker, and nothing here can be indexed as a fact.
 */
export const metadata: Metadata = {
  title: "Match simulator",
  description: "Play a fixture between two generated clubs from their stored squads and an authored tactical system.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/simulate") },
};

export default async function SimulateIndexPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fsimulate");

  const [choices, played] = await Promise.all([
    serverFetch<SimOptions>("/simulate/options"),
    serverFetch<SimList>("/simulate"),
  ]);
  if (!choices.ok) {
    return <WorldUnavailable eyebrow="Match simulator" message={choices.error.message} title="Match simulator" />;
  }
  const options = choices.data;
  if (!options.ready) {
    return (
      <WorldUnavailable
        eyebrow="Match simulator"
        message="The simulator plays from stored squads, and the generated world is not present in full yet."
        title="Match simulator"
      />
    );
  }

  const engine = options.engine;
  const listing = played.ok ? played.data : null;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/my-football", label: "My Football" }}
        eyebrow={`${user.display_name} · simulations are private to this account`}
        lede="Two clubs from the generated world, the eleven each formation actually selects, and the metres of the tactical system they are playing. The model then plays the match block by block and keeps every number it used."
        provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: options.disclaimer }}
        title="Match simulator"
      />

      <Panel eyebrow={`${options.teams.length} clubs · ${options.systems.length} authored systems`} title="Play a fixture">
        <SimulatorForm options={options} />
      </Panel>

      <Panel eyebrow={engine.version} title="What the model claims about itself">
        <div className="stack">
          <p className="notice">{engine.calibration}</p>
          <div className="grid grid-2">
            <KeyValueGrid
              rows={[
                ["Engine", <span className="mono" key="engine">{engine.name}</span>],
                ["Block length", `${engine.block_minutes}'`],
                ["Lengths offered", engine.minute_choices.map((choice) => `${choice}'`).join(" · ")],
                ["Inputs are read from", <span className="mono" key="inputs">{engine.inputs_are_from.join(", ")}</span>],
              ]}
            />
            <KeyValueGrid
              rows={[
                ["Authored tactical systems", String(options.systems.length)],
                ["Clubs on offer", String(options.teams.length)],
                ["Named rates", String(engine.factors.length)],
                [
                  "Kept by this account",
                  listing ? `${listing.total} of ${listing.limit_per_user}` : "not read",
                ],
              ]}
            />
          </div>
          <div className="stack-sm">
            <span className="eyebrow">Every rate names its formula</span>
            <div className="world-tablewrap">
              <table className="table" data-testid="sim-rates">
                <thead>
                  <tr>
                    <th scope="col">Rate</th>
                    <th scope="col">Expression</th>
                    <th scope="col">What it reads</th>
                  </tr>
                </thead>
                <tbody>
                  {engine.factors.map((factor) => (
                    <tr key={factor.key}>
                      <td className="mono">{factor.key}</td>
                      <td className="tac-formula">{factor.expression}</td>
                      <td className="muted">{factor.reads}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <p className="muted world-section-note">
            A scoreline from here is a description of what this model does with these inputs. It is not a forecast, and the clubs
            are not real.{" "}
            <Link className="world-link" href="/knowledge">
              The knowledge library
            </Link>{" "}
            explains what the numbers mean in football terms; it does not vouch for any single match.
          </p>
        </div>
      </Panel>

      <Panel
        action={
          <Link className="btn btn--ghost btn--sm" href="/career">
            Run a season instead
          </Link>
        }
        eyebrow={listing ? `${listing.total} of ${listing.limit_per_user} kept` : "not read"}
        title="This account’s matches"
      >
        {!listing ? (
          <p className="notice notice--warn">
            The list could not be read: {played.ok ? "the report arrived without a list" : `${played.error.code}: ${played.error.message}`}.
          </p>
        ) : listing.items.length === 0 ? (
          <div className="empty">
            <strong>No matches played yet</strong>
            <span className="muted">Pick two clubs above and the report will appear here once it has been stored.</span>
          </div>
        ) : (
          <section className="tac-cards">
            {listing.items.map((match) => (
              <Link className="tac-card" href={match.path} key={match.id}>
                <span className="tac-card__name">
                  {match.home_summary.short_name} {match.score.home} – {match.score.away} {match.away_summary.short_name}
                </span>
                <span className="tac-card__meta">
                  {match.minutes}&apos; · {match.home_summary.name} v {match.away_summary.name}
                </span>
                <div className="tac-card__metrics">
                  <span className="chip num">xG {match.home_summary.expected_goals} – {match.away_summary.expected_goals}</span>
                  <span className="chip num">
                    shots {match.home_summary.shots} – {match.away_summary.shots}
                  </span>
                  <span className="chip mono" title="The seed that replays this row exactly">
                    seed {match.seed}
                  </span>
                  <span className="chip mono">{match.digest}</span>
                </div>
              </Link>
            ))}
          </section>
        )}
      </Panel>

      <Provenance
        provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: options.disclaimer }}
        extra={<span className="chip">stored rows keep the seed, so a match can be re-derived and its digest compared</span>}
      />
    </div>
  );
}
