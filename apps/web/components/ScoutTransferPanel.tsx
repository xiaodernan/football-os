"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
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
  const ts = useTranslations("scout");
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
      <Panel
        eyebrow={ts("transferEyebrow", {
          from: rules.default_rounds,
          to: rules.max_rounds,
          writes: rules.writes.split(":")[0],
        })}
        title={ts("transferTitle")}
      >
        <div className="stack-sm">
          <div className="row wrap" style={{ gap: "0.6rem" }}>
            <input aria-label={ts("careerAria")} className="mono" maxLength={80} onChange={(event) => setSlug(event.target.value)} placeholder={ts("careerPlaceholder")} value={slug} />
            <select aria-label={ts("playerAria")} className="grow mono" disabled={busy || candidates.length === 0} onChange={(event) => setPlayer(event.target.value)} value={player}>
              <option value="">{candidates.length ? ts("oneOfCandidates") : ts("runSearchFirst")}</option>
              {candidates.map((candidate) => (
                <option key={candidate.slug} value={candidate.slug}>
                  {candidate.name} · {candidate.age} · {candidate.band} · {candidate.overall}/{candidate.potential}
                </option>
              ))}
            </select>
            <input aria-label={ts("fixturesAria")} className="mono" max={rules.max_rounds} min={1} onChange={(event) => setRounds(event.target.value)} style={{ width: "6.5rem" }} type="number" value={rounds} />
            <button className="btn btn--primary" disabled={busy || !player || !slug.trim()} onClick={() => void run()} type="button">
              {busy ? ts("projecting") : ts("simulateSigning")}
            </button>
          </div>
          <p className="muted mono">{rules.seed_rule}</p>
          {fault && (
            <p className="notice notice--warn" data-sim="refusal">
              <strong>{fault.code ?? "error"}</strong> — {errorMessage(fault)}
              {figures ? <span className="mono"> {figures}</span> : null}
            </p>
          )}
          {!view && !fault && <p className="muted">{ts("chooseFirst")}</p>}
        </div>
      </Panel>

      {view && cost && projection && (
        <>
          <Panel
            eyebrow={`${view.career.club_name} · round ${view.career.rounds_played} played · ${view.career.formation}${view.career.window ? ` · window ${view.career.window}` : ""}`}
            title={ts("dealTitle", { name: view.player.name })}
          >
            <div className="stack-sm">
              <div className="row wrap" style={{ gap: "0.5rem" }}>
                <a className="world-link" href={view.player.path}>
                  {view.player.name}
                </a>
                <span className="chip mono">
                  {view.player.age} · {view.player.position} · {view.player.band} · {view.player.preferred_foot}-foot
                </span>
                <span className="chip mono">
                  {view.player.overall} / {view.player.potential} · {ts("headroom", { value: view.player.headroom })}
                </span>
                <span className="chip mono">{view.player.archetype}</span>
                {view.player.from_club && (
                  <span className="chip mono">
                    {ts("atClub")}{" "}
                    <a href={view.player.from_club.path}>{view.player.from_club.name}</a>
                  </span>
                )}
                <span className={`badge ${view.need.this_player_fills_it ? "badge--live" : "badge--demo"}`}>
                  {view.need.this_player_fills_it
                    ? ts("fillsNeed", { band: view.need.needed_band.toUpperCase() })
                    : ts("doesNotFill", { band: view.need.needed_band.toUpperCase() })}
                </span>
              </div>
              <KeyValueGrid
                rows={[
                  [ts("kvAskingFee"), <span className="num" key="af">{money(cost.asking_fee)}</span>],
                  [ts("kvReleaseClause"), <span className="num" key="rc">{money(cost.release_clause)}</span>],
                  [ts("kvWeeklyWage"), <span className="num" key="ww">{money(cost.weekly_wage)}</span>],
                  [ts("kvSeasonWage"), <span className="num" key="sw">{money(cost.season_wage)}</span>],
                  [ts("kvContractYears"), <span className="num" key="cy">{cost.contract_years}</span>],
                  [ts("kvLeftInBudget"), <span className="num" key="rem">{money(cost.remaining_now)} {cost.units}</span>],
                  [
                    ts("kvAffordable"),
                    <span key="aff">
                      <span className={`badge ${cost.affordable_by_fee ? "badge--live" : "badge--demo"}`}>{cost.affordable_by_fee ? ts("yes") : ts("no")}</span>{" "}
                      <span className="muted mono">
                        {ts("headroomAfterFee", { value: money(cost.headroom_after_fee) })}
                      </span>
                    </span>,
                  ],
                  [ts("kvWageCommitted"), <span className="num" key="wc">{money(cost.wage_committed_per_week)}</span>],
                  [ts("kvWageWithPlayer"), <span className="num" key="wa">{money(cost.wage_after_this_player_per_week)}</span>],
                  [ts("kvSeasonWageAfter"), <span className="num" key="saw">{money(cost.season_wage_after)}</span>],
                  [ts("kvRoundsLeftovers"), <span className="num" key="rw">{cost.rounds_the_wage_bills_for}</span>],
                  [ts("kvTacticalFit"), <span className="num" key="fit">{String(view.fit.fit)} · {view.fit.formula}</span>],
                  [
                    ts("kvSquad"),
                    <span key="sq">
                      {ts("squadRow", {
                        before: view.squad.size_before,
                        after: view.squad.size_after,
                        beforeOk: String(view.squad.fielding_before.ok),
                        afterOk: String(view.squad.fielding_after.ok),
                      })}
                    </span>,
                  ],
                ]}
              />
              <p className="muted">{cost.note}</p>
              <p className="muted">{cost.valuation_note}</p>
              <p className="muted mono">{cost.budget_formula}</p>
              <p className="muted">{view.squad.rule}</p>
            </div>
          </Panel>

          <Panel
            eyebrow={ts("sideEyebrow", {
              projected: projection.rounds_projected,
              asked: projection.rounds_asked,
            })}
            title={ts("sideTitle")}
          >
            <div className="stack-sm">
              <div className="world-tablewrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">{ts("thIndex")}</th>
                      <th scope="col" className="num">
                        {ts("thWithout")}
                      </th>
                      <th scope="col" className="num">
                        {ts("thWith")}
                      </th>
                      <th scope="col" className="num">
                        {ts("thDelta")}
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
                    <span className="mono">{ts("elevenUnchanged")}</span>{" "}
                    {ts("elevenUnchangedNote", {
                      before: view.squad.size_before,
                      after: view.squad.size_after,
                    })}
                  </>
                ) : (
                  <>
                    <span className="mono">{ts("elevenChanges")}</span>{" "}
                    {ts("elevenChangesNote", {
                      comes: view.side.comes_in.map((row) => `${row.name} (${row.position})`).join(", "),
                      goes: view.side.goes_out.map((row) => `${row.name} (${row.position})`).join(", ") || ts("nobody"),
                    })}
                  </>
                )}
              </p>
              <p className="muted">{view.side.rule}</p>
            </div>
          </Panel>

          <Panel
            eyebrow={ts("fixturesEyebrow", {
              better: projection.better,
              same: projection.same,
              worse: projection.worse,
            })}
            title={ts("fixturesTitle")}
          >
            <div className="stack-sm">
              <div className="world-tablewrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">{ts("thRound")}</th>
                      <th scope="col">{ts("thFixture")}</th>
                      <th scope="col" className="num">
                        {ts("thSeed")}
                      </th>
                      <th scope="col">{ts("thWithout")}</th>
                      <th scope="col">{ts("thWithSigning")}</th>
                      <th scope="col">{ts("thSameSeed")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {projection.rounds.map((line) => (
                      <tr data-sim-round={line.round_index} key={line.round_index}>
                        <td className="num">{line.round_index}</td>
                        <td>
                          {line.side === "home" ? ts("versus") : ts("awayAt")} {line.opponent}
                          <div className="muted">{line.venue}</div>
                        </td>
                        <td className="num mono">{line.seed}</td>
                        <td>
                          <span className="mono">
                            {line.without.for}-{line.without.against}
                          </span>{" "}
                          {line.without.outcome}{" "}
                          <span className="muted mono">
                            {ts("possession", { value: line.without.possession })} · {line.without.digest.slice(0, 12)}
                          </span>
                        </td>
                        <td>
                          <span className="mono">
                            {line.with_signing.for}-{line.with_signing.against}
                          </span>{" "}
                          {line.with_signing.outcome}{" "}
                          <span className="muted mono">
                            {ts("possession", { value: line.with_signing.possession })} ·{" "}
                            {line.with_signing.digest.slice(0, 12)}
                          </span>
                        </td>
                        <td>
                          <span className={line.without.seed === line.with_signing.seed ? "badge badge--live" : "badge badge--demo"}>
                            {line.without.seed === line.with_signing.seed ? ts("oneSeed") : ts("seedsDiffer")}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <KeyValueGrid
                rows={[
                  [
                    ts("kvWithoutHim"),
                    <span key="wo">
                      {projection.totals.without.goals}-{projection.totals.without.against} ·{" "}
                      {ts("pointsLabel", { points: projection.totals.without.points })}
                    </span>,
                  ],
                  [
                    ts("kvWithHim"),
                    <span key="wi">
                      {projection.totals.with_signing.goals}-{projection.totals.with_signing.against} ·{" "}
                      {ts("pointsLabel", { points: projection.totals.with_signing.points })}
                    </span>,
                  ],
                  [
                    ts("kvDifference"),
                    <span className="mono" key="d">
                      {ts("differenceRow", {
                        points: projection.points_delta > 0 ? `+${projection.points_delta}` : projection.points_delta,
                        for: projection.goals_for_delta > 0 ? `+${projection.goals_for_delta}` : projection.goals_for_delta,
                        against:
                          projection.goals_against_delta > 0
                            ? `+${projection.goals_against_delta}`
                            : projection.goals_against_delta,
                      })}
                    </span>,
                  ],
                  ...(projection.stopped_at
                    ? ([
                        [
                          ts("stoppedAt", { round: projection.stopped_at.round_index }),
                          projection.stopped_at.reason,
                        ],
                      ] as [string, ReactNode][])
                    : []),
                ]}
              />
              <p className="notice">{projection.one_sample}</p>
              <p className="muted mono">{view.rules.price_from}</p>
              <p className="muted mono">{view.rules.fixtures_from}</p>
            </div>
          </Panel>

          <Panel eyebrow={ts("doesNotDoEyebrow")} title={ts("doesNotDoTitle")}>
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
