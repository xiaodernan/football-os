import Link from "next/link";
import { getTranslations } from "next-intl/server";

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
const COMPARED: { key: keyof SimSide; msg: string; digits?: number; unit?: string }[] = [
  { key: "possession_pct", msg: "mPossession", digits: 1, unit: "%" },
  { key: "goals", msg: "mGoals" },
  { key: "expected_goals", msg: "mXG", digits: 3 },
  { key: "shots", msg: "mShots" },
  { key: "shots_on_target", msg: "mShotsOnTarget" },
  { key: "big_chances", msg: "mBigChances" },
  { key: "passes", msg: "mPasses" },
  { key: "pass_completions", msg: "mPassesCompleted" },
  { key: "pass_accuracy_pct", msg: "mPassAccuracy", digits: 1, unit: "%" },
  { key: "press_attempts", msg: "mPressAttempts" },
  { key: "turnovers_won", msg: "mTurnoversWon" },
  { key: "high_turnovers_won", msg: "mHighTurnoversWon" },
  { key: "transitions", msg: "mTransitions" },
  { key: "corners_conceded", msg: "mCornersConceded" },
  { key: "fouls", msg: "mFouls" },
  { key: "yellow_cards", msg: "mYellowCards" },
  { key: "red_cards", msg: "mRedCards" },
  { key: "injuries", msg: "mInjuries" },
];

/** The engine's event type mapped to its catalogue key; an unknown type falls back to the raw type. */
const EVENT_KEY: Record<string, string> = {
  goal: "eGoal",
  shot_saved: "eSaved",
  shot_off_target: "eOffTarget",
  yellow_card: "eYellow",
  red_card: "eRed",
  injury: "eInjury",
};

/**
 * The club pages are addressed by slug, and a report only carries a team id, so the page resolves the
 * two hrefs through the public options route and passes them in. A side whose club is no longer in
 * the generated world renders without a link rather than pointing at a 404.
 */
export type SideHrefs = { home?: string; away?: string };

async function SideName({ side, href }: { side: SimSide; href?: string }) {
  const t = await getTranslations("simulate");
  const label = side.name;
  const shape = side.system_name || t("ownFormation");
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

export async function ScoreLine({ report, hrefs }: { report: SimReport; hrefs?: SideHrefs }) {
  const t = await getTranslations("simulate");
  const winner = report.score.winner.side;
  return (
    <div className="world-scoreline" data-testid="sim-score">
      <SideName href={hrefs?.home} side={report.sides.home} />
      <div className="world-scoreline__score">
        <span className="num">
          {report.score.home} – {report.score.away}
        </span>
        <span className="chip" style={{ fontSize: "0.7rem" }}>
          {winner === "draw" ? t("modelledDraw") : t("modelWinner", { name: report.score.winner.name })}
        </span>
      </div>
      <div className="world-scoreline__side world-scoreline__side--away">
        <SideName href={hrefs?.away} side={report.sides.away} />
      </div>
    </div>
  );
}

export async function SideComparison({ report }: { report: SimReport }) {
  const t = await getTranslations("simulate");
  return (
    <div className="world-tablewrap">
      <table className="table" data-testid="sim-totals">
        <thead>
          <tr>
            <th scope="col">{t("thMetric")}</th>
            <th scope="col">{report.sides.home.short_name}</th>
            <th scope="col">{report.sides.away.short_name}</th>
          </tr>
        </thead>
        <tbody>
          {COMPARED.map((row) => (
            <tr key={String(row.key)}>
              <td>{t(row.msg)}</td>
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

export async function EventTimeline({ events }: { events: SimEvent[] }) {
  const t = await getTranslations("simulate");
  if (events.length === 0) {
    return (
      <p className="muted world-section-note" data-testid="sim-events">
        {t("timelineEmpty")}
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
            <strong>{EVENT_KEY[event.type] ? t(EVENT_KEY[event.type]) : event.type}</strong>
            <span className="muted"> — {event.detail}</span>
            {event.expected_goals !== undefined && (
              <span className="tac-formula"> xG {num(event.expected_goals, 3)}</span>
            )}
            {event.from_press && <span className="chip" style={{ marginLeft: "0.35rem" }}>{t("fromPress")}</span>}
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
export async function BlockTable({ blocks }: { blocks: SimBlock[] }) {
  const t = await getTranslations("simulate");
  return (
    <div className="world-tablewrap">
      <table className="table" data-testid="sim-blocks">
        <thead>
          <tr>
            <th scope="col">{t("blockThBlock")}</th>
            <th scope="col">{t("blockThHomeG")}</th>
            <th scope="col">{t("blockThXG")}</th>
            <th scope="col">{t("blockThShots")}</th>
            <th scope="col">{t("blockThPoss")}</th>
            <th scope="col">{t("blockThAwayG")}</th>
            <th scope="col">{t("blockThXG")}</th>
            <th scope="col">{t("blockThShots")}</th>
            <th scope="col">{t("blockThPoss")}</th>
            <th scope="col">{t("blockThHomeMult")}</th>
            <th scope="col">{t("blockThAwayMult")}</th>
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
              <td className="tac-formula">{multipliers(block.home, t)}</td>
              <td className="tac-formula">{multipliers(block.away, t)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function multipliers(row: SimBlock["home"], t: Awaited<ReturnType<typeof getTranslations>>): string {
  return t("multiplierLine", {
    volume: num(row.volume, 3),
    quality: num(row.chance_quality, 3),
    fatigue: num(row.fatigue, 3),
    lateSpace: num(row.late_space, 3),
    stretch: num(row.stretch, 3),
    opponentOpen: num(row.opponent_opening, 3),
    manAttack: num(row.man_down_attack, 2),
    manConcede: num(row.man_down_concede, 2),
  });
}

/** The eleven the profile selected, so a named scorer can be checked against the squad on the page. */
export async function LineupList({ side }: { side: SimSide }) {
  const t = await getTranslations("simulate");
  return (
    <div className="stack-sm">
      <span className="eyebrow">{t("lineupEyebrow", { short: side.short_name, count: side.lineup.length })}</span>
      <div className="world-tablewrap">
        <table className="table" data-testid="sim-lineup">
          <thead>
            <tr>
              <th scope="col">{t("lineupThBand")}</th>
              <th scope="col">{t("lineupThPlayer")}</th>
              <th scope="col">{t("lineupThPosition")}</th>
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
export async function InputList({ side }: { side: SimSide }) {
  const t = await getTranslations("simulate");
  return (
    <div className="stack-sm">
      <div className="tag-list">
        <span className="chip mono">{t("indicesChip", { short: side.short_name })}</span>
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
              <th scope="col">{t("inputsThInput")}</th>
              <th scope="col">{t("inputsThValue")}</th>
              <th scope="col">{t("inputsThHow")}</th>
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
          {t("noTactics")}
        </p>
      )}
    </div>
  );
}

/** The engine's own claims: coefficients, the formula each rate uses, and what it refuses to model. */
export async function ModelPanel({ model }: { model: SimModel }) {
  const t = await getTranslations("simulate");
  return (
    <div className="stack">
      <p className="notice">{model.calibration}</p>
      <div className="world-tablewrap">
        <table className="table" data-testid="sim-model">
          <thead>
            <tr>
              <th scope="col">{t("thRate")}</th>
              <th scope="col">{t("thExpression")}</th>
              <th scope="col">{t("thReads")}</th>
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
        <span className="eyebrow">{t("coefficientsEyebrow")}</span>
        <div className="tag-list">
          {Object.entries(model.coefficients).map(([key, value]) => (
            <span className="chip mono" key={key}>
              {key} {value}
            </span>
          ))}
        </div>
      </div>
      <div className="stack-sm">
        <span className="eyebrow">{t("notModelEyebrow")}</span>
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
