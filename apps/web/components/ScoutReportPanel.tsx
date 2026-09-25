"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { KeyValueGrid } from "@/components/world";
import { money } from "@/lib/scout";
import type { GroupScore, ReportView } from "@/lib/scout";

const GROUPS = ["technical", "physical", "mental", "tactical"] as const;

/**
 * §24's thirteen fields, printed with the sentence that produced each figure.
 *
 * The page adds nothing to a report and subtracts nothing from it: a field that came back `null` is printed
 * as `null` with the reason, because §24's `team_fit` and `comparison` are only real when a career or a second
 * player was actually asked for. `recommendation.decided_by` is shown beside the verdict so the ladder can be
 * checked against the numbers above it, and every group line carries `measured` and `missing` — an average over
 * six attributes is not the same claim as an average over twenty-seven.
 */
export function ScoutReportPanel({ report }: { report: ReportView }) {
  const player = report.player;
  return (
    <div className="stack-sm">
      <div className="row wrap" style={{ gap: "0.6rem" }}>
        <Link className="world-link" href={player.path}>
          {player.name}
        </Link>
        <span className="chip mono">
          {player.age} · {player.position} · {player.band}
        </span>
        <span className="chip mono">{player.preferred_foot}-foot</span>
        {player.club && (
          <span className="chip mono">
            at <Link href={player.club.path}>{player.club.name}</Link>
          </span>
        )}
        <span className={player.observed ? "badge badge--live" : "badge badge--demo"}>{player.observed ? "OBSERVED" : "NO APPEARANCES"}</span>
        <span className={`badge ${report.recommendation.verdict === "sign now" ? "badge--live" : "badge--demo"}`}>{report.recommendation.verdict.toUpperCase()}</span>
      </div>

      <p className="notice">
        <strong>{report.recommendation.verdict}</strong> — decided by{" "}
        {report.recommendation.decided_by.map((figure) => (
          <span className="chip mono" key={figure}>
            {figure}
          </span>
        ))}
        <span className="muted"> · {report.recommendation.note}</span>
      </p>

      <div className="tac-cards">
        <div className="tac-card">
          <strong>Current level</strong>
          <KeyValueGrid
            rows={[
              ["Overall", <span className="num" key="o">{report.current_level.overall}</span>],
              [
                "Recomputed",
                <span className="num" key="r">
                  {report.current_level.recomputed} · {report.current_level.agrees_with_stored ? "agrees with the stored column" : "DISAGREES with the stored column"}
                </span>,
              ],
              [
                "Percentile",
                <span key="p">
                  <span className="num">{(report.current_level.share_of_pool * 100).toFixed(1)}%</span> of {report.current_level.players_in_pool} rows ·{" "}
                  <span className="num">{(report.current_level.share_of_band * 100).toFixed(1)}%</span> inside {report.current_level.band} ({report.current_level.players_in_band} rows)
                </span>,
              ],
              ["Archetype", `${report.current_level.archetype} · match ${report.current_level.archetype_match}`],
            ]}
          />
          <p className="muted mono">{report.current_level.rule}</p>
        </div>

        <div className="tac-card">
          <strong>Potential</strong>
          <KeyValueGrid
            rows={[
              ["Ceiling", <span className="num" key="c">{report.potential.potential}</span>],
              ["Headroom", <span className="num" key="h">{report.potential.headroom}</span>],
              ["Age curve", <span className="num" key="a">{report.potential.age_curve}</span>],
              ["Years past peak", <span className="num" key="y">{report.potential.years_past_peak}</span>],
            ]}
          />
          <p className="muted mono">{report.potential.rule}</p>
        </div>
      </div>

      <div className="world-tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Group</th>
              <th scope="col" className="num">Mean</th>
              <th scope="col" className="num">Measured</th>
              <th scope="col">Strongest</th>
              <th scope="col">Weakest</th>
              <th scope="col">Missing keys</th>
            </tr>
          </thead>
          <tbody>
            {GROUPS.map((group) => (
              <GroupRow key={group} score={report[group]} />
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted mono">{report.technical.rule}</p>

      {report.role_fit ? (
        <div className="stack-sm">
          <strong>
            Role fit · {report.role_fit.role} — {report.role_fit.label} <span className="chip mono">{report.role_fit.board_band}</span>
          </strong>
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Attribute</th>
                  <th scope="col" className="num">Demanded</th>
                  <th scope="col" className="num">Have</th>
                  <th scope="col" className="num">Gap</th>
                  <th scope="col">Verdict</th>
                </tr>
              </thead>
              <tbody>
                {report.role_fit.rows.map((row) => (
                  <tr key={row.attribute}>
                    <td className="mono">{row.attribute}</td>
                    <td className="num">{row.demanded}</td>
                    <td className="num">{row.have}</td>
                    <td className="num">{row.gap > 0 ? `+${row.gap}` : row.gap}</td>
                    <td>
                      <span className={row.verdict === "short" ? "badge badge--demo" : "badge badge--live"}>{row.verdict.toUpperCase()}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted">
            mean gap <span className="mono">{report.role_fit.mean_gap}</span> over {report.role_fit.covered_attributes} attributes · {report.role_fit.verdict} · {report.role_fit.formula}
          </p>
          <p className="muted">{report.role_fit.risk}</p>
        </div>
      ) : (
        <p className="muted">
          <span className="mono">role_fit: null</span> — no role was asked for, so there is no fit to print. The role codes this catalogue holds are published by{" "}
          <span className="mono">GET /api/v1/scout/rules</span>.
        </p>
      )}

      {report.team_fit ? (
        <div className="stack-sm">
          <strong>
            Team fit · {report.team_fit.club.name} needs {report.team_fit.needed_band}
          </strong>
          <KeyValueGrid
            rows={[
              ["Fit", <span className="num" key="f">{report.team_fit.fit}</span>],
              ["Club stores in band", <span className="num" key="s">{report.team_fit.club_stores_in_band}</span>],
              ["Candidate already lists there", String(report.team_fit.candidate_already_lists_there)],
              ["Bands", JSON.stringify(report.team_fit.bands)],
            ]}
          />
          <p className="muted mono">
            {report.team_fit.formula} · {report.team_fit.rule}
          </p>
        </div>
      ) : (
        <p className="muted">
          <span className="mono">team_fit: null</span> — no career was named, so no club&rsquo;s weakest band was judged. This is §24&rsquo;s field left unanswered rather than filled with a number that belongs to no
          club.
        </p>
      )}

      <div className="stack-sm">
        <strong>Risk · {report.risk.length} factor{report.risk.length === 1 ? "" : "s"}</strong>
        {report.risk.length === 0 ? (
          <p className="muted">No factor matched. That is not the same as no risk — it means none of the published thresholds was crossed by this row.</p>
        ) : (
          <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
            {report.risk.map((factor) => (
              <li key={factor.factor}>
                <span className="chip mono">{factor.factor}</span> <span className="num">{String(factor.value)}</span>
                <div className="muted">{factor.rule}</div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="stack-sm">
        <strong>Cost</strong>
        <KeyValueGrid
          rows={[
            ["Asking fee", <span className="num" key="af">{money(report.cost.asking_fee)}</span>],
            ["Weekly wage", <span className="num" key="ww">{money(report.cost.weekly_wage)}</span>],
            ["Season wage", <span className="num" key="sw">{money(report.cost.season_wage)}</span>],
            ["Wage share of fee", <span className="num" key="ws">{report.cost.wage_share_of_fee}</span>],
            ["Release clause", <span className="num" key="rc">{money(report.cost.release_clause)}</span>],
            ["Contract years", <span className="num" key="cy">{report.cost.contract_years}</span>],
            ["Value for money", <span className="num" key="vf">{report.cost.value_for_money}</span>],
            ["Components", <span className="mono" key="cp">{JSON.stringify(report.cost.components)}</span>],
            ...(report.cost.against_career_budget
              ? ([[
                  "Against this budget",
                  <span key="ab">
                    <span className="num">{money(report.cost.against_career_budget.budget)}</span> {report.cost.against_career_budget.units} · share{" "}
                    <span className="num">{String(report.cost.against_career_budget.share_of_budget)}</span> · fits without selling:{" "}
                    {String(report.cost.against_career_budget.fits_without_selling)}
                  </span>,
                ]] as [string, ReactNode][])
              : []),
          ]}
        />
        <p className="muted mono">
          {report.cost.formula} · {report.cost.note}
        </p>
      </div>

      <p className="muted">
        {report.comparison ? (
          <>
            Comparison against <Link href={report.comparison.other.path}>{report.comparison.other.name}</Link> — overall <span className="num">{report.comparison.overall}</span>, headroom{" "}
            <span className="num">{report.comparison.headroom}</span>, fee <span className="num">{money(report.comparison.asking_fee)}</span>, value for money{" "}
            <span className="num">{report.comparison.value_for_money}</span>. {report.comparison.rule}
          </>
        ) : (
          <span className="mono">comparison: null</span>
        )}
      </p>

      <p className="muted">{report.limitations.join(" · ")}</p>
    </div>
  );
}

function GroupRow({ score }: { score: GroupScore }) {
  return (
    <tr>
      <td>
        <strong>{score.group}</strong>
      </td>
      <td className="num">{score.mean}</td>
      <td className="num">
        {score.measured} of {score.measured + score.missing.length}
      </td>
      <td className="mono">
        {score.strongest} <span className="num">{score.attributes[score.strongest]}</span>
      </td>
      <td className="mono">
        {score.weakest} <span className="num">{score.attributes[score.weakest]}</span>
      </td>
      <td className="muted mono">{score.missing.length ? score.missing.join(", ") : "none"}</td>
    </tr>
  );
}
