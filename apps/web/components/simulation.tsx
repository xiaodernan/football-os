import Link from "next/link";

import "../styles/tactics.css";

import type { SimBlock, SimEvent, SimModel, SimReport, SimSide } from "@/lib/types";

/**
 * The read-side of M6: the pieces that render an engine report without adding a number of their own.
 *
 * Two rules hold here. A figure is printed with the unit the report gives it, and every multiplier is
 * printed as the model produced it — including the ones that did nothing (a `man_down_attack` of 1.0
 * is the honest statement that nobody was sent off). The formula strings are the model's own text,
 * never a paraphrase, so a reader can compare what the page says with what the digest covers.
 */

function num(value: number, digits = 0): string {
  return value.toLocaleString("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** `side` is which of the two the row belongs to; `null` prints both. */
const COMPARED: { key: keyof SimSide; label: string; digits?: number; unit?: string }[] = [
  { key: "possession_pct", label: "Possession", digits: 1, unit: "%" },
  { key: "goals", label: "Goals" },
  { key: "expected_goals", label: "Expected goals", digits: 3 },
  { key: "shots", label: "Shots" },
  { key: "shots_on_target", label: "Shots on target" },
  { key: "big_chances", label: "Big chances" },
  { key: "passes", label: "Passes" },
  { key: "pass_completions", label: "Passes completed" },
  { key: "pass_accuracy_pct", label: "Pass accuracy", digits: 1, unit: "%" },
  { key: "press_attempts", label: "Press attempts" },
  { key: "turnovers_won", label: "Turnovers won" },
  { key: "high_turnovers_won", label: "Turnovers won in the final third" },
  { key: "transitions", label: "Transition shots" },
  { key: "corners_conceded", label: "Corners conceded" },
  { key: "fouls", label: "Fouls" },
  { key: "yellow_cards", label: "Yellow cards" },
  { key: "red_cards", label: "Red cards" },
  { key: "injuries", label: "Injuries" },
];

/**
 * The club pages are addressed by slug, and a report only carries a team id, so the page resolves the
 * two hrefs through the public options route and passes them in. A side whose club is no longer in
 * the generated world renders without a link rather than pointing at a 404.
 */
export type SideHrefs = { home?: string; away?: string };

function SideName({ side, href }: { side: SimSide; href?: string }) {
  const label = side.name;
  const shape = side.system_name || "the club's own formation";
  return (
    <div className="world-scoreline__side">
      {href ? (
        <Link className="world-link" href={href}>
          {label}
        </Link>
      ) : (
        <span>{label}</span>
      )}
      <span className="muted" style={{ fontSize: "0.78rem" }}>
        {side.formation} · {shape}
      </span>
    </div>
  );
}

export function ScoreLine({ report, hrefs }: { report: SimReport; hrefs?: SideHrefs }) {
  const winner = report.score.winner.side;
  return (
    <div className="world-scoreline" data-testid="sim-score">
      <SideName href={hrefs?.home} side={report.sides.home} />
      <div className="world-scoreline__score">
        <span className="num">
          {report.score.home} – {report.score.away}
        </span>
        <span className="chip" style={{ fontSize: "0.7rem" }}>
          {winner === "draw" ? "Modelled draw" : `Model winner: ${report.score.winner.name}`}
        </span>
      </div>
      <div className="world-scoreline__side world-scoreline__side--away">
        <SideName href={hrefs?.away} side={report.sides.away} />
      </div>
    </div>
  );
}

export function SideComparison({ report }: { report: SimReport }) {
  return (
    <div className="world-tablewrap">
      <table className="table" data-testid="sim-totals">
        <thead>
          <tr>
            <th scope="col">Metric</th>
            <th scope="col">{report.sides.home.short_name}</th>
            <th scope="col">{report.sides.away.short_name}</th>
          </tr>
        </thead>
        <tbody>
          {COMPARED.map((row) => (
            <tr key={String(row.key)}>
              <td>{row.label}</td>
              <td className="num mono">
                {num(Number(report.sides.home[row.key]), row.digits ?? 0)}
                {row.unit ?? ""}
              </td>
              <td className="num mono">
                {num(Number(report.sides.away[row.key]), row.digits ?? 0)}
                {row.unit ?? ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const EVENT_LABEL: Record<string, string> = {
  goal: "Goal",
  shot_saved: "Saved",
  shot_off_target: "Off target",
  yellow_card: "Yellow",
  red_card: "Red",
  injury: "Injury",
};

export function EventTimeline({ events }: { events: SimEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="muted world-section-note" data-testid="sim-events">
        The model produced no goal-bound event, card or injury in this match. An empty timeline is a result, not a missing
        fetch — the totals above add up to it.
      </p>
    );
  }
  return (
    <div className="timeline" data-testid="sim-events">
      {events.map((event, index) => (
        <div className="timeline__row" key={`${event.minute}-${event.type}-${index}`}>
          <span className="mono muted">
            {event.minute}&apos;{event.score ? ` · ${event.score}` : ""}
          </span>
          <span>
            <strong>{EVENT_LABEL[event.type] ?? event.type}</strong>
            <span className="muted"> — {event.detail}</span>
            {event.expected_goals !== undefined && (
              <span className="tac-formula"> xG {num(event.expected_goals, 3)}</span>
            )}
            {event.from_press && <span className="chip" style={{ marginLeft: "0.35rem" }}>from a won turnover</span>}
          </span>
          <span className="row" style={{ gap: "0.35rem" }}>
            <span className="chip mono">{event.team}</span>
            {event.position && <span className="chip">{event.position}</span>}
          </span>
        </div>
      ))}
    </div>
  );
}

/** One row per block, both sides: the scoreboard and the multipliers the model applied to it. */
export function BlockTable({ blocks }: { blocks: SimBlock[] }) {
  return (
    <div className="world-tablewrap">
      <table className="table" data-testid="sim-blocks">
        <thead>
          <tr>
            <th scope="col">Block</th>
            <th scope="col">Home G</th>
            <th scope="col">xG</th>
            <th scope="col">Shots</th>
            <th scope="col">Poss</th>
            <th scope="col">Away G</th>
            <th scope="col">xG</th>
            <th scope="col">Shots</th>
            <th scope="col">Poss</th>
            <th scope="col">Home multipliers</th>
            <th scope="col">Away multipliers</th>
          </tr>
        </thead>
        <tbody>
          {blocks.map((block) => (
            <tr key={`${block.minute_from}-${block.minute_to}`}>
              <td className="mono">
                {block.minute_from}–{block.minute_to}
              </td>
              <td className="num">{block.home.goals}</td>
              <td className="num mono">{num(block.home.expected_goals, 2)}</td>
              <td className="num">{block.home.shots}</td>
              <td className="num mono">{num(block.home.possession_pct, 1)}</td>
              <td className="num">{block.away.goals}</td>
              <td className="num mono">{num(block.away.expected_goals, 2)}</td>
              <td className="num">{block.away.shots}</td>
              <td className="num mono">{num(block.away.possession_pct, 1)}</td>
              <td className="tac-formula">{multipliers(block.home)}</td>
              <td className="tac-formula">{multipliers(block.away)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function multipliers(row: SimBlock["home"]): string {
  return `vol ${num(row.volume, 3)} · quality ${num(row.chance_quality, 3)} · fatigue ${num(row.fatigue, 3)} · late space ${num(
    row.late_space,
    3,
  )} · stretch ${num(row.stretch, 3)} · opponent open ${num(row.opponent_opening, 3)} · man-down ${num(
    row.man_down_attack,
    2,
  )}/${num(row.man_down_concede, 2)}`;
}

/** The eleven the profile selected, so a named scorer can be checked against the squad on the page. */
export function LineupList({ side }: { side: SimSide }) {
  return (
    <div className="stack-sm">
      <span className="eyebrow">{`${side.short_name} — the ${side.lineup.length} the shape selected`}</span>
      <div className="world-tablewrap">
        <table className="table" data-testid="sim-lineup">
          <thead>
            <tr>
              <th scope="col">Band</th>
              <th scope="col">Player</th>
              <th scope="col">Position</th>
            </tr>
          </thead>
          <tbody>
            {side.lineup.map((row, index) => (
              <tr key={`${row.player}-${index}`}>
                <td className="chip">{row.band}</td>
                <td>{row.player}</td>
                <td className="mono">{row.position}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** What went into a side: the metres of the chosen system and the formula behind every index. */
export function InputList({ side }: { side: SimSide }) {
  return (
    <div className="stack-sm">
      <div className="tag-list">
        <span className="chip mono">{side.short_name} indices</span>
        {Object.entries(side.indices).map(([key, value]) => (
          <span className="chip" key={key}>
            {key} {num(value, 3)}
          </span>
        ))}
      </div>
      <div className="world-tablewrap">
        <table className="table" data-testid="sim-inputs">
          <thead>
            <tr>
              <th scope="col">Measured input</th>
              <th scope="col">Value</th>
              <th scope="col">How it was obtained</th>
            </tr>
          </thead>
          <tbody>
            {side.inputs.factors.map((factor) => (
              <tr key={factor.key}>
                <td>{factor.label}</td>
                <td className="num mono">
                  {num(factor.value, 2)} {factor.unit}
                </td>
                <td className="tac-formula">{factor.formula}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {Object.keys(side.inputs.tactics).length === 0 && (
        <p className="muted world-section-note">
          No tactical system was chosen for this side, so the shape metrics are empty: the match was played from the club&apos;s
          own formation and nothing was measured from a pitch shape.
        </p>
      )}
    </div>
  );
}

/** The engine's own claims: coefficients, the formula each rate uses, and what it refuses to model. */
export function ModelPanel({ model }: { model: SimModel }) {
  return (
    <div className="stack">
      <p className="notice">{model.calibration}</p>
      <div className="world-tablewrap">
        <table className="table" data-testid="sim-model">
          <thead>
            <tr>
              <th scope="col">Rate</th>
              <th scope="col">Formula</th>
              <th scope="col">What it reads</th>
            </tr>
          </thead>
          <tbody>
            {model.factors.map((factor) => (
              <tr key={factor.key}>
                <td className="mono">{factor.key}</td>
                <td className="tac-formula">{factor.expression}</td>
                <td className="muted">{factor.reads}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="stack-sm">
        <span className="eyebrow">Coefficients as shipped</span>
        <div className="tag-list">
          {Object.entries(model.coefficients).map(([key, value]) => (
            <span className="chip mono" key={key}>
              {key} {value}
            </span>
          ))}
        </div>
      </div>
      <div className="stack-sm">
        <span className="eyebrow">What this model does not model</span>
        <ul className="reasons">
          {model.what_it_does_not_model.map((item, index) => (
            <li className="reasons__item" key={`${item}-${index}`}>
              {item}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
