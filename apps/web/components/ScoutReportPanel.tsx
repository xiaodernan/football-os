"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
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
  const ts = useTranslations("scout");
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
        <span className={player.observed ? "badge badge--live" : "badge badge--demo"}>{player.observed ? ts("observed") : ts("noAppearances")}</span>
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
          <strong>{ts("currentLevelTitle")}</strong>
          <KeyValueGrid
            rows={[
              [ts("kvOverall"), <span className="num" key="o">{report.current_level.overall}</span>],
              [
                ts("kvRecomputed"),
                <span className="num" key="r">
                  {report.current_level.recomputed} ·{" "}
                  {report.current_level.agrees_with_stored ? ts("agreesWithStored") : ts("disagreesWithStored")}
                </span>,
              ],
              [
                ts("kvPercentile"),
                <span key="p">
                  {ts.rich("percentOfPool", {
                    value: (report.current_level.share_of_pool * 100).toFixed(1),
                    rows: report.current_level.players_in_pool,
                    num: (chunks) => <span className="num">{chunks}</span>,
                  })}{" "}
                  ·{" "}
                  {ts.rich("percentOfBand", {
                    value: (report.current_level.share_of_band * 100).toFixed(1),
                    band: report.current_level.band,
                    rows: report.current_level.players_in_band,
                    num: (chunks) => <span className="num">{chunks}</span>,
                  })}
                </span>,
              ],
              [
                ts("kvArchetype"),
                `${report.current_level.archetype} · ${ts("archetypeMatch", { value: report.current_level.archetype_match })}`,
              ],
            ]}
          />
          <p className="muted mono">{report.current_level.rule}</p>
        </div>

        <div className="tac-card">
          <strong>{ts("potentialTitle")}</strong>
          <KeyValueGrid
            rows={[
              [ts("kvCeiling"), <span className="num" key="c">{report.potential.potential}</span>],
              [ts("kvHeadroom"), <span className="num" key="h">{report.potential.headroom}</span>],
              [ts("kvAgeCurve"), <span className="num" key="a">{report.potential.age_curve}</span>],
              [ts("kvYearsPastPeak"), <span className="num" key="y">{report.potential.years_past_peak}</span>],
            ]}
          />
          <p className="muted mono">{report.potential.rule}</p>
        </div>
      </div>

      <div className="world-tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{ts("thGroup")}</th>
              <th scope="col" className="num">{ts("thMean")}</th>
              <th scope="col" className="num">{ts("thMeasured")}</th>
              <th scope="col">{ts("thStrongest")}</th>
              <th scope="col">{ts("thWeakest")}</th>
              <th scope="col">{ts("thMissingKeys")}</th>
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
            {ts("roleFitTitle", {
              role: report.role_fit.role,
              label: report.role_fit.label,
            })}{" "}
            <span className="chip mono">{report.role_fit.board_band}</span>
          </strong>
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{ts("thAttribute")}</th>
                  <th scope="col" className="num">{ts("thDemanded")}</th>
                  <th scope="col" className="num">{ts("thHave")}</th>
                  <th scope="col" className="num">{ts("thGap")}</th>
                  <th scope="col">{ts("thVerdict")}</th>
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
            {ts("meanGap", {
              gap: report.role_fit.mean_gap,
              attributes: report.role_fit.covered_attributes,
              verdict: report.role_fit.verdict,
              formula: report.role_fit.formula,
            })}
          </p>
          <p className="muted">{report.role_fit.risk}</p>
        </div>
      ) : (
        <p className="muted">
          <span className="mono">role_fit: null</span> {ts("roleFitNull")}
        </p>
      )}

      {report.team_fit ? (
        <div className="stack-sm">
          <strong>
            {ts("teamFitTitle", {
              club: report.team_fit.club.name,
              band: report.team_fit.needed_band,
            })}
          </strong>
          <KeyValueGrid
            rows={[
              [ts("kvFit"), <span className="num" key="f">{report.team_fit.fit}</span>],
              [ts("kvClubStoresInBand"), <span className="num" key="s">{report.team_fit.club_stores_in_band}</span>],
              [ts("kvCandidateListsThere"), String(report.team_fit.candidate_already_lists_there)],
              [ts("kvBands"), JSON.stringify(report.team_fit.bands)],
            ]}
          />
          <p className="muted mono">
            {report.team_fit.formula} · {report.team_fit.rule}
          </p>
        </div>
      ) : (
        <p className="muted">
          <span className="mono">team_fit: null</span> {ts("teamFitNull")}
        </p>
      )}

      <div className="stack-sm">
        <strong>{ts("riskTitle", { count: report.risk.length })}</strong>
        {report.risk.length === 0 ? (
          <p className="muted">{ts("noRiskFactors")}</p>
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
        <strong>{ts("costTitle")}</strong>
        <KeyValueGrid
          rows={[
            [ts("kvAskingFee"), <span className="num" key="af">{money(report.cost.asking_fee)}</span>],
            [ts("kvWeeklyWage"), <span className="num" key="ww">{money(report.cost.weekly_wage)}</span>],
            [ts("kvSeasonWage"), <span className="num" key="sw">{money(report.cost.season_wage)}</span>],
            [ts("kvWageShareOfFee"), <span className="num" key="ws">{report.cost.wage_share_of_fee}</span>],
            [ts("kvReleaseClause"), <span className="num" key="rc">{money(report.cost.release_clause)}</span>],
            [ts("kvContractYears"), <span className="num" key="cy">{report.cost.contract_years}</span>],
            [ts("kvValueForMoney"), <span className="num" key="vf">{report.cost.value_for_money}</span>],
            [ts("kvComponents"), <span className="mono" key="cp">{JSON.stringify(report.cost.components)}</span>],
            ...(report.cost.against_career_budget
              ? ([[
                  ts("kvAgainstBudget"),
                  <span key="ab">
                    {ts("budgetRow", {
                      budget: money(report.cost.against_career_budget.budget),
                      units: report.cost.against_career_budget.units,
                      share: String(report.cost.against_career_budget.share_of_budget),
                      fits: String(report.cost.against_career_budget.fits_without_selling),
                    })}
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
            {ts("comparisonAgainst")} <Link href={report.comparison.other.path}>{report.comparison.other.name}</Link>{" "}
            {ts("comparisonLine", {
              overall: report.comparison.overall,
              headroom: report.comparison.headroom,
              fee: money(report.comparison.asking_fee),
              value: report.comparison.value_for_money,
            })}{" "}
            {report.comparison.rule}
          </>
        ) : (
          <span className="mono">{ts("comparisonNull")}</span>
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
