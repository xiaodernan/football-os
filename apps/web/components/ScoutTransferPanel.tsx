"use client";

import { useState } from "react";
import type { ReactNode } from "react";

import { KeyValueGrid } from "@/components/world";
import { Panel } from "@/components/ui";
import { SIM_INDEX_ORDER, money } from "@/lib/scout";
import type { Candidate, SimRules, TransferSimView } from "@/lib/scout";
import { browserFetch, errorMessage } from "@/lib/api";
import type { ApiError } from "@/lib/types";

/**
 * M7's transfer simulation: what would be different if this career signed the player in front of you.
 *
 * The panel is a question asked of arithmetic, not a transaction offered to a manager, and four rules keep it
 * honest about that:
 *
 *  - **Nothing is written.** This route never buys. `POST /transfers/{career}/buy` is the door that moves a
 *    player, charges the budget and writes a move row, and the panel says so in the payload's own words rather
 *    than in copy the page invented.
 *  - **The two scorelines of a round share one seed.** Each round prints its seed twice and the digest the engine
 *    produced for each side, so the only thing that can differ between the two lines is the eleven — and a reader
 *    can see that rather than take it on trust.
 *  - **A fixture is one sample.** The pre-dice part of the answer — the band indices and the possession share —
 *    is printed beside the scorelines, because a single better result is not evidence of a better side.
 *  - **The money is two questions.** The fee against the balance, and the wage against what the career will be
 *    charged every round it plays. A deal that fits the first can still fail the second.
 */
export function ScoutTransferPanel({ candidates, rules, career }: { candidates: Candidate[]; rules: SimRules; career: string }) {
  const [player, setPlayer] = useState("");
  const [rounds, setRounds] = useState(String(rules.default_rounds));
  const [slug, setSlug] = useState(career);
  const [view, setView] = useState<TransferSimView | null>(null);
  const [fault, setFault] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    if (!slug.trim() || !player) return;
    setBusy(true);
    const result = await browserFetch<TransferSimView>("/scout/simulate-transfer", { method: "POST", body: { career: slug.trim(), player, rounds: Number(rounds) || rules.default_rounds } });
    setBusy(false);
    if (result.ok) {
      setView(result.data);
      setFault(null);
    } else {
      setFault(result.error);
    }
  }

  const figures = fault?.details && typeof fault.details === "object" ? JSON.stringify(fault.details) : "";
  const cost = view?.cost;
  const projection = view?.projection;

  return (
    <div className="stack" data-testid="scout-transfer">
      <Panel eyebrow={`a projection over ${rules.default_rounds}-${rules.max_rounds} future fixtures · it writes ${rules.writes.split(":")[0]}`} title="What if this career signed him?">
        <div className="stack-sm">
          <div className="row wrap" style={{ gap: "0.6rem" }}>
            <input aria-label="Career to simulate for" className="mono" maxLength={80} onChange={(event) => setSlug(event.target.value)} placeholder="career slug" value={slug} />
            <select aria-label="Player to simulate signing" className="grow mono" disabled={busy || candidates.length === 0} onChange={(event) => setPlayer(event.target.value)} value={player}>
              <option value="">{candidates.length ? "one of the players this search just returned" : "run a search first"}</option>
              {candidates.map((candidate) => (
                <option key={candidate.slug} value={candidate.slug}>
                  {candidate.name} · {candidate.age} · {candidate.band} · {candidate.overall}/{candidate.potential}
                </option>
              ))}
            </select>
            <input aria-label="Fixtures to project" className="mono" max={rules.max_rounds} min={1} onChange={(event) => setRounds(event.target.value)} style={{ width: "6.5rem" }} type="number" value={rounds} />
            <button className="btn btn--primary" disabled={busy || !player || !slug.trim()} onClick={() => void run()} type="button">
              {busy ? "Projecting…" : "Simulate the signing"}
            </button>
          </div>
          <p className="muted mono">{rules.seed_rule}</p>
          {fault && (
            <p className="notice notice--warn" data-sim="refusal">
              <strong>{fault.code ?? "error"}</strong> — {errorMessage(fault)}
              {figures ? <span className="mono"> {figures}</span> : null}
            </p>
          )}
          {!view && !fault && <p className="muted">Choose a career and a player. Nothing you do here moves a player, spends a budget, or reaches a seller — that is what makes the answer a projection rather than a decision.</p>}
        </div>
      </Panel>

      {view && cost && projection && (
        <>
          <Panel eyebrow={`${view.career.club_name} · round ${view.career.rounds_played} played · ${view.career.formation}${view.career.window ? ` · window ${view.career.window}` : ""}`} title={`The deal: ${view.player.name}`}>
            <div className="stack-sm">
              <div className="row wrap" style={{ gap: "0.5rem" }}>
                <a className="world-link" href={view.player.path}>
                  {view.player.name}
                </a>
                <span className="chip mono">
                  {view.player.age} · {view.player.position} · {view.player.band} · {view.player.preferred_foot}-foot
                </span>
                <span className="chip mono">
                  {view.player.overall} / {view.player.potential} · headroom {view.player.headroom}
                </span>
                <span className="chip mono">{view.player.archetype}</span>
                {view.player.from_club && (
                  <span className="chip mono">
                    at <a href={view.player.from_club.path}>{view.player.from_club.name}</a>
                  </span>
                )}
                <span className={`badge ${view.need.this_player_fills_it ? "badge--live" : "badge--demo"}`}>{view.need.this_player_fills_it ? `FILLS THE NEED IN ${view.need.needed_band.toUpperCase()}` : `DOES NOT FILL ${view.need.needed_band.toUpperCase()}`}</span>
              </div>
              <KeyValueGrid
                rows={[
                  ["Asking fee", <span className="num" key="af">{money(cost.asking_fee)}</span>],
                  ["Release clause", <span className="num" key="rc">{money(cost.release_clause)}</span>],
                  ["Weekly wage", <span className="num" key="ww">{money(cost.weekly_wage)}</span>],
                  ["Season wage", <span className="num" key="sw">{money(cost.season_wage)}</span>],
                  ["Contract years", <span className="num" key="cy">{cost.contract_years}</span>],
                  ["Left in the budget", <span className="num" key="rem">{money(cost.remaining_now)} {cost.units}</span>],
                  [
                    "Affordable by the fee",
                    <span key="aff">
                      <span className={`badge ${cost.affordable_by_fee ? "badge--live" : "badge--demo"}`}>{cost.affordable_by_fee ? "YES" : "NO"}</span> <span className="muted mono">headroom after the fee: {money(cost.headroom_after_fee)}</span>
                    </span>,
                  ],
                  ["Wage committed per week now", <span className="num" key="wc">{money(cost.wage_committed_per_week)}</span>],
                  ["…and with this player", <span className="num" key="wa">{money(cost.wage_after_this_player_per_week)}</span>],
                  ["Season wage after this player", <span className="num" key="saw">{money(cost.season_wage_after)}</span>],
                  ["Rounds the leftovers pay for", <span className="num" key="rw">{cost.rounds_the_wage_bills_for}</span>],
                  ["Tactical fit for that need", <span className="num" key="fit">{String(view.fit.fit)} · {view.fit.formula}</span>],
                  ["Squad", <span key="sq">{view.squad.size_before} → {view.squad.size_after} · a side can be fielded now: {String(view.squad.fielding_before.ok)} · after: {String(view.squad.fielding_after.ok)}</span>],
                ]}
              />
              <p className="muted">{cost.note}</p>
              <p className="muted">{cost.valuation_note}</p>
              <p className="muted mono">{cost.budget_formula}</p>
              <p className="muted">{view.squad.rule}</p>
            </div>
          </Panel>

          <Panel eyebrow={`the eleven the engine would play, before and after · ${projection.rounds_projected} of ${projection.rounds_asked} fixtures projected`} title="What changes about the side">
            <div className="stack-sm">
              <div className="world-tablewrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">Index</th>
                      <th scope="col" className="num">
                        Without
                      </th>
                      <th scope="col" className="num">
                        With
                      </th>
                      <th scope="col" className="num">
                        Delta
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {SIM_INDEX_ORDER.filter((key) => key in view.side.before.indices).map((key) => (
                      <tr data-sim-index={key} key={key}>
                        <td className="mono">{key}</td>
                        <td className="num">{view.side.before.indices[key]}</td>
                        <td className="num">{view.side.after.indices[key]}</td>
                        <td className="num">{view.side.indices_delta[key] > 0 ? `+${view.side.indices_delta[key]}` : view.side.indices_delta[key]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="muted" data-sim="eleven">
                {view.side.eleven_unchanged ? (
                  <>
                    <span className="mono">the eleven does not change</span> — he would be a squad addition, not a starter: {view.squad.size_before} rows become {view.squad.size_after}, and the same eleven is selected.
                  </>
                ) : (
                  <>
                    <span className="mono">the eleven changes:</span> in — {view.side.comes_in.map((row) => `${row.name} (${row.position})`).join(", ")} · out — {view.side.goes_out.map((row) => `${row.name} (${row.position})`).join(", ") || "nobody"}.
                  </>
                )}
              </p>
              <p className="muted">{view.side.rule}</p>
            </div>
          </Panel>

          <Panel eyebrow={`each round replayed twice at one seed · better ${projection.better} · same ${projection.same} · worse ${projection.worse}`} title="The fixtures, with and without him">
            <div className="stack-sm">
              <div className="world-tablewrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">Round</th>
                      <th scope="col">Fixture</th>
                      <th scope="col" className="num">
                        Seed
                      </th>
                      <th scope="col">Without</th>
                      <th scope="col">With the signing</th>
                      <th scope="col">Same seed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {projection.rounds.map((line) => (
                      <tr data-sim-round={line.round_index} key={line.round_index}>
                        <td className="num">{line.round_index}</td>
                        <td>
                          {line.side === "home" ? "vs" : "at"} {line.opponent}
                          <div className="muted">{line.venue}</div>
                        </td>
                        <td className="num mono">{line.seed}</td>
                        <td>
                          <span className="mono">
                            {line.without.for}-{line.without.against}
                          </span>{" "}
                          {line.without.outcome} <span className="muted mono">poss {line.without.possession} · {line.without.digest.slice(0, 12)}</span>
                        </td>
                        <td>
                          <span className="mono">
                            {line.with_signing.for}-{line.with_signing.against}
                          </span>{" "}
                          {line.with_signing.outcome} <span className="muted mono">poss {line.with_signing.possession} · {line.with_signing.digest.slice(0, 12)}</span>
                        </td>
                        <td>
                          <span className={line.without.seed === line.with_signing.seed ? "badge badge--live" : "badge badge--demo"}>{line.without.seed === line.with_signing.seed ? "ONE SEED" : "SEEDS DIFFER"}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <KeyValueGrid
                rows={[
                  ["Without him", <span key="wo">{projection.totals.without.goals}-{projection.totals.without.against} · {projection.totals.without.points} points</span>],
                  ["With him", <span key="wi">{projection.totals.with_signing.goals}-{projection.totals.with_signing.against} · {projection.totals.with_signing.points} points</span>],
                  [
                    "Difference",
                    <span className="mono" key="d">
                      points {projection.points_delta > 0 ? `+${projection.points_delta}` : projection.points_delta} · goals for {projection.goals_for_delta > 0 ? `+${projection.goals_for_delta}` : projection.goals_for_delta} · against {projection.goals_against_delta > 0 ? `+${projection.goals_against_delta}` : projection.goals_against_delta}
                    </span>,
                  ],
                  ...(projection.stopped_at ? ([[`Stopped at round ${projection.stopped_at.round_index}`, projection.stopped_at.reason] as [string, string]] as [string, ReactNode][]) : []),
                ]}
              />
              <p className="notice">{projection.one_sample}</p>
              <p className="muted mono">{view.rules.price_from}</p>
              <p className="muted mono">{view.rules.fixtures_from}</p>
            </div>
          </Panel>

          <Panel eyebrow="the part of this answer you can check" title="What this simulation does not do">
            <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
              {view.what_this_does_not_do.map((line) => (
                <li className="muted" key={line}>
                  {line}
                </li>
              ))}
            </ul>
            <p className="muted">{view.limitations.join(" · ")}</p>
            <p className="muted mono">
              {view.data_origin} · is_demo_data: {String(view.is_demo_data)} · {view.disclaimer}
            </p>
          </Panel>
        </>
      )}
    </div>
  );
}
