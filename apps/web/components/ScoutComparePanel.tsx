"use client";

import Link from "next/link";

import { LEADER_LABELS, figure, leaderTone, money } from "@/lib/scout";
import type { CompareDimension, CompareSide, CompareView, Measure, TotalsCheck } from "@/lib/scout";

/** §27 asks for ten dimensions in this order; the payload prints them in this order, and so does the page. */
const OPEN_BY_DEFAULT = new Set(["technical", "age", "context"]);

/**
 * The payload names the two sides `left` and `right`; this page has already labelled them A and B, so a badge
 * that said `LEFT` above a column headed `A` would be a second vocabulary for the same two players. The other
 * four answers are the payload's own and are printed as it words them.
 */
function leaderText(leader: string): string {
  if (leader === "left") return "A AHEAD";
  if (leader === "right") return "B AHEAD";
  return (LEADER_LABELS[leader] ?? leader).toUpperCase();
}

/**
 * §27's ten dimensions, printed as ten answers instead of one.
 *
 * The page has no summary figure to compute, which is the point: a reader who wants one number for the pair
 * would have to add one here, and adding one here is exactly what the spec rules out. Each dimension is a
 * leader plus the measures underneath it, and every measure shows its own `delta` and the `source` it was read
 * from, so a `split` is not a shrug — it is two sides winning named figures.
 */
export function ScoutComparePanel({ compared }: { compared: CompareView }) {
  return (
    <div className="stack-sm">
      <div className="tac-cards">
        <SideCard side={compared.left} label="A" />
        <SideCard side={compared.right} label="B" />
      </div>

      <p className="notice">{compared.no_single_score}</p>

      <div className="row wrap" style={{ gap: "0.5rem" }}>
        <span className="chip mono">
          {compared.counts.dimensions} dimensions · {compared.counts.measures} measures
        </span>
        {Object.entries(compared.counts.dimension_leaders).map(([leader, count]) => (
          <span className={`chip mono ${leaderTone(leader) === "demo" ? "" : "chip--accent"}`} key={leader}>
            {leaderText(leader)}: {count}
          </span>
        ))}
      </div>

      <p className="muted mono">
        overall A {compared.overall_line.left} · B {compared.overall_line.right} · delta {compared.overall_line.delta}
      </p>
      <p className="muted">{compared.overall_line.note}</p>

      {compared.dimensions.map((dimension) => (
        <DimensionBlock dimension={dimension} key={dimension.dimension} />
      ))}

      <div className="world-tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Side</th>
              <th scope="col" className="num">Stored minutes</th>
              <th scope="col" className="num">Minutes in lines</th>
              <th scope="col" className="num">Stored goals</th>
              <th scope="col" className="num">Goals in lines</th>
              <th scope="col" className="num">Appearances</th>
              <th scope="col" className="num">Lines</th>
              <th scope="col">Agree</th>
            </tr>
          </thead>
          <tbody>
            <TotalsRow label="A" check={compared.totals_check.left} />
            <TotalsRow label="B" check={compared.totals_check.right} />
          </tbody>
        </table>
      </div>
      <p className="muted">{compared.totals_check.rule}</p>
      <p className="muted">{compared.measure_rule}</p>
      <p className="muted">{compared.limitations.join(" · ")}</p>
    </div>
  );
}

function SideCard({ side, label }: { side: CompareSide; label: string }) {
  return (
    <div className="tac-card">
      <div className="row wrap" style={{ gap: "0.5rem" }}>
        <span className="badge badge--live">{label}</span>
        <Link className="world-link" href={side.path}>
          {side.name}
        </Link>
        <span className="chip mono">
          {side.age} · {side.position} · {side.band}
        </span>
        <span className="chip mono">
          {side.overall} / {side.potential}
        </span>
        <span className="chip mono">{money(side.asking_fee)}</span>
      </div>
      <p className="muted">
        {side.club ? (
          <>
            at <Link href={side.club.path}>{side.club.name}</Link> (overall {side.club.overall})
          </>
        ) : (
          "lists at no club in this world"
        )}
        {side.competition ? ` · ${side.competition.name}, tier ${side.competition.tier}` : ""}
      </p>
      <p className="muted mono">
        {side.stat_lines} stat lines · {side.minutes_in_lines} minutes behind the rates
      </p>
      {!side.observed && <span className="badge badge--demo">NO APPEARANCES</span>}
    </div>
  );
}

function DimensionBlock({ dimension }: { dimension: CompareDimension }) {
  const scorable = dimension.measures.filter((measure) => measure.leader !== "unknown" && measure.leader !== "not_scorable").length;
  return (
    <details className="tac-card" data-dimension={dimension.dimension} open={OPEN_BY_DEFAULT.has(dimension.dimension)}>
      <summary>
        <strong>{dimension.dimension}</strong>{" "}
        <span className={`badge ${leaderTone(dimension.leader) === "demo" ? "badge--demo" : "badge--live"}`}>{leaderText(dimension.leader)}</span>{" "}
        <span className="muted mono">
          {dimension.measures.length} measures · {scorable} scorable
        </span>
      </summary>
      <p className="muted">{dimension.source}</p>
      {dimension.note && <p className="muted">{dimension.note}</p>}
      <div className="world-tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Measure</th>
              <th scope="col" className="num">A</th>
              <th scope="col" className="num">B</th>
              <th scope="col" className="num">Delta</th>
              <th scope="col">Direction</th>
              <th scope="col">Leader</th>
              <th scope="col">Read from</th>
            </tr>
          </thead>
          <tbody>
            {dimension.measures.map((measure) => (
              <MeasureRow measure={measure} key={measure.key} />
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted mono">{dimension.rule}</p>
    </details>
  );
}

function MeasureRow({ measure }: { measure: Measure }) {
  const gap: string[] = [];
  if (measure.missing?.length) gap.push(`missing on ${measure.missing.join(" + ")}`);
  if (measure.unobserved?.length) gap.push(`no lines for ${measure.unobserved.join(" + ")}`);
  return (
    <tr data-measure={measure.key}>
      <td className="mono">
        {measure.key}
        {measure.unit ? <div className="muted">{measure.unit}</div> : null}
        {gap.length ? <div className="muted mono">{gap.join(" · ")}</div> : null}
      </td>
      <td className="num">{figure(measure.left)}</td>
      <td className="num">{figure(measure.right)}</td>
      <td className="num">{measure.delta === null ? "—" : measure.delta > 0 ? `+${measure.delta}` : String(measure.delta)}</td>
      <td className="mono muted">{measure.direction}</td>
      <td>
        <span className={`badge ${leaderTone(measure.leader) === "demo" ? "badge--demo" : "badge--live"}`}>{leaderText(measure.leader)}</span>
      </td>
      <td className="muted mono">{measure.source}</td>
    </tr>
  );
}

function TotalsRow({ label, check }: { label: string; check: TotalsCheck }) {
  return (
    <tr>
      <td className="mono">{label}</td>
      <td className="num">{check.stored_minutes}</td>
      <td className="num">{check.lines_minutes}</td>
      <td className="num">{check.stored_goals}</td>
      <td className="num">{check.lines_goals}</td>
      <td className="num">{check.stored_appearances}</td>
      <td className="num">{check.lines}</td>
      <td>
        <span className={check.agree ? "badge badge--live" : "badge badge--demo"}>{check.agree ? "AGREE" : "DISAGREE"}</span>
      </td>
    </tr>
  );
}
