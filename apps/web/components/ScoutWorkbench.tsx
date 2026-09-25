"use client";

import Link from "next/link";
import { useState } from "react";

import { ScoutComparePanel } from "@/components/ScoutComparePanel";
import { ScoutReportPanel } from "@/components/ScoutReportPanel";
import { Panel } from "@/components/ui";
import { browserFetch, errorMessage } from "@/lib/api";
import type { ApiError } from "@/lib/types";
import type { Candidate, CompareView, ParseView, ReportView, ScoutRulesView, SearchView } from "@/lib/scout";

const money = (value: number) => value.toLocaleString("en-GB");
type Busy = "search" | "parse" | "report" | "compare" | null;

/**
 * §23's search, §24's report and §27's comparison on one screen, with the refusals kept visible.
 *
 * Four rules shape this component, and each one exists because the API already prints the evidence:
 *
 *  - **Words are checked before they are spent.** `POST /scout/parse` reads the sentence and touches no row,
 *    so "Check my words" is a separate button from "Search". A manager can see that 擅长推进 was refused
 *    before a candidate list makes it look like the foot or the role was filtered too.
 *  - **A refusal travels with the results.** `refused`, `assumptions`, `unaccounted` and `connectors_ignored`
 *    are printed above the table rather than dropped, because "12 left-footed strikers" is a lie the moment
 *    the foot was one of the phrases this vocabulary does not know.
 *  - **The waterfall is the proof.** Every filter shows how many rows entered it, how many it cut, and the
 *    rule it cut on — so a pool of 300 that answers 8 is checkable rather than a number to trust.
 *  - **A comparison has no winner.** §27's payload refuses to rank the pair as a whole, so the table here
 *    prints ten leaders (`split` included) and no summary figure. Nothing is added in the browser to make the
 *    pair feel settled.
 *
 * Rate limits are the server's to enforce (20 searches, reports and comparisons a minute); a `429` is shown
 * with the API's own sentence rather than retried quietly.
 */
export function ScoutWorkbench({ rules }: { rules: ScoutRulesView }) {
  const [query, setQuery] = useState("");
  const [career, setCareer] = useState("");
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState<Busy>(null);
  const [fault, setFault] = useState<ApiError | null>(null);
  const [parsed, setParsed] = useState<ParseView | null>(null);
  const [searched, setSearched] = useState<SearchView | null>(null);
  const [report, setReport] = useState<{ slug: string; data: ReportView | null } | null>(null);
  const [sides, setSides] = useState<{ left: string | null; right: string | null }>({ left: null, right: null });
  const [compared, setCompared] = useState<CompareView | null>(null);

  const slots = [sides.left, sides.right].filter(Boolean) as string[];

  async function ask(route: "parse" | "search" | "report" | "compare", body: Record<string, unknown>) {
    const result = await browserFetch<ParseView | SearchView | ReportView | CompareView>(`/scout/${route}`, { method: "POST", body });
    if (!result.ok) {
      setFault(result.error);
      return null;
    }
    setFault(null);
    return result.data;
  }

  async function checkWords() {
    if (!query.trim()) return;
    setBusy("parse");
    const data = await ask("parse", { query });
    setParsed(data ? (data as ParseView) : null);
    setBusy(null);
  }

  async function runSearch() {
    setBusy("search");
    const body: Record<string, unknown> = { query, limit: 20 };
    if (career.trim()) body.career = career.trim();
    if (role.trim()) body.role = role.trim();
    const data = await ask("search", body);
    if (data) {
      setSearched(data as SearchView);
      setParsed(null);
      setSides({ left: null, right: null });
      setCompared(null);
      setReport(null);
    }
    setBusy(null);
  }

  async function openReport(slug: string) {
    setBusy("report");
    const body: Record<string, unknown> = { player: slug };
    if (role.trim()) body.role = role.trim();
    if (career.trim()) body.career = career.trim();
    const data = await ask("report", body);
    if (data) setReport({ slug, data: data as ReportView });
    setBusy(null);
  }

  /** A side is chosen by pressing its slot button again; a third player replaces the right slot. */
  function pick(slug: string) {
    const next = { ...sides };
    if (next.left === slug) next.left = null;
    else if (next.right === slug) next.right = null;
    else if (!next.left) next.left = slug;
    else if (!next.right) next.right = slug;
    else next.right = slug;
    setSides(next);
    setCompared(null);
  }

  async function runCompare() {
    if (!sides.left || !sides.right) return;
    setBusy("compare");
    const data = await ask("compare", { left: sides.left, right: sides.right });
    setCompared(data ? (data as CompareView) : null);
    setBusy(null);
  }

  return (
    <div className="stack">
      <Panel eyebrow={`${String(rules.integrity.counts.players_stored)} stored players · ${rules.attributes.length} attributes · ${Object.keys(rules.roles).length} roles`} title="Ask the scout in your own words">
        <div className="stack-sm">
          <div className="row wrap" style={{ gap: "0.6rem" }}>
            <input
              aria-label="Scouting request"
              className="grow"
              maxLength={400}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void runSearch();
              }}
              placeholder="e.g. 找一个 22 岁以下、左脚、能踢 CM、预算 2000 万以下的球员"
              value={query}
            />
            <input aria-label="Role to judge the fit against" className="mono" list="scout-roles" maxLength={16} onChange={(event) => setRole(event.target.value)} placeholder="role (optional)" value={role} />
            <input aria-label="Career slug" className="mono" maxLength={80} onChange={(event) => setCareer(event.target.value)} placeholder="career slug (optional)" value={career} />
          </div>
          <datalist id="scout-roles">
            {Object.entries(rules.roles).map(([code, entry]) => (
              <option key={code} value={code}>
                {entry.label}
              </option>
            ))}
          </datalist>
          <div className="row wrap" style={{ gap: "0.6rem" }}>
            <button className="btn btn--primary" disabled={busy !== null || !query.trim()} onClick={() => void runSearch()} type="button">
              {busy === "search" ? "Searching…" : "Search the world"}
            </button>
            <button className="btn" disabled={busy !== null || !query.trim()} onClick={() => void checkWords()} type="button">
              {busy === "parse" ? "Reading…" : "Check my words first"}
            </button>
            <span className="muted">
              <span className="mono">career</span> lets a search rank against the band this club is thinnest in; <span className="mono">role</span> adds a fit column and is quoted by the report. Neither is a guess about
              who you are.
            </span>
          </div>
          {fault && (
            <p className="notice notice--warn">
              <strong>{fault.code}</strong> — {errorMessage(fault)}
              {fault.details ? <span className="mono"> {JSON.stringify(fault.details)}</span> : null}
            </p>
          )}
          {!rules.integrity.clean && (
            <ul className="notice notice--warn">
              {rules.integrity.problems.map((problem) => (
                <li key={problem}>{problem}</li>
              ))}
            </ul>
          )}
        </div>
      </Panel>

      {parsed && (
        <Panel eyebrow={`POST /scout/parse · ${parsed.filters_applied} filter${parsed.filters_applied === 1 ? "" : "s"} · no row read`} title="What your sentence would filter">
          <div data-testid="scout-parse" className="stack-sm">
            <RequirementList requirements={parsed.requirements} />
            <RefusalBlock refused={parsed.refused} assumptions={parsed.assumptions} unaccounted={parsed.unaccounted} />
            <p className="muted">{parsed.note}</p>
          </div>
        </Panel>
      )}

      {searched && (
        <>
          <Panel eyebrow={`${searched.total_matches} match${searched.total_matches === 1 ? "" : "es"} of ${searched.rows_examined} rows examined · sorted by ${searched.sort.key}`} title="Candidates">
            <div className="stack-sm">
              <RefusalBlock refused={searched.refused} assumptions={searched.assumptions} unaccounted={searched.unaccounted} />
              {searched.truncated && <p className="notice">Only the first {searched.returned} of {searched.total_matches} are printed — `truncated` is the API saying so, not the pool being that size.</p>}
              <div className="world-tablewrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">Player</th>
                      <th scope="col">Age</th>
                      <th scope="col">Band</th>
                      <th scope="col">Foot</th>
                      <th scope="col" className="num">Overall</th>
                      <th scope="col" className="num">Potential</th>
                      <th scope="col" className="num">Headroom</th>
                      <th scope="col" className="num">Asking fee</th>
                      <th scope="col">Answers</th>
                      <th scope="col">Report</th>
                      <th scope="col">Compare</th>
                    </tr>
                  </thead>
                  <tbody>
                    {searched.candidates.map((candidate) => (
                      <CandidateRow
                        busy={busy}
                        candidate={candidate}
                        key={candidate.slug}
                        onCompare={() => pick(candidate.slug)}
                        onReport={() => void openReport(candidate.slug)}
                        slots={slots}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="muted">{searched.scan_note}</p>
            </div>
          </Panel>

          <Panel eyebrow={`${searched.waterfall.length} cuts · applied in the order the request stated them`} title="How the pool was cut">
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Requirement</th>
                    <th scope="col">Phrase</th>
                    <th scope="col" className="num">Rows in</th>
                    <th scope="col" className="num">Cut</th>
                    <th scope="col" className="num">Rows out</th>
                    <th scope="col">Rule</th>
                  </tr>
                </thead>
                <tbody>
                  {searched.waterfall.map((step, index) => (
                    <tr data-cut-row={index} key={`${step.kind}-${step.phrase}-${String(index)}`}>
                      <td className="mono">{step.kind}</td>
                      <td>{step.phrase}</td>
                      <td className="num">{step.rows_in}</td>
                      <td className="num">−{step.cut}</td>
                      <td className="num">{step.rows_out}</td>
                      <td className="muted">
                        {step.rule}
                        {step.example_of_a_row_dropped ? <span className="mono"> · dropped example: {JSON.stringify(step.example_of_a_row_dropped)}</span> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted">{searched.waterfall_rule}</p>
          </Panel>

          {report?.data && (
            <Panel eyebrow={`POST /scout/report · ${report.data.fields.length} fields · ${report.data.player.name}`} title="Scouting report">
              <div data-testid="scout-report">
                <ScoutReportPanel report={report.data} />
              </div>
            </Panel>
          )}

          <Panel eyebrow={slots.length === 2 ? `${slots[0]} against ${slots[1]}` : "choose two candidates with the A and B buttons"} title="Player A against Player B">
            <div className="stack-sm">
              <div className="row wrap" style={{ gap: "0.6rem" }}>
                <button className="btn btn--primary" disabled={busy !== null || slots.length !== 2} onClick={() => void runCompare()} type="button">
                  {busy === "compare" ? "Comparing…" : "Compare the pair"}
                </button>
                <span className="muted mono">A: {sides.left ?? "—"} · B: {sides.right ?? "—"}</span>
              </div>
              {compared ? (
                <div data-testid="scout-compare">
                  <ScoutComparePanel compared={compared} />
                </div>
              ) : (
                <p className="muted">{rules.comparison.no_single_score}</p>
              )}
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}

function CandidateRow({
  candidate,
  slots,
  busy,
  onReport,
  onCompare,
}: {
  candidate: Candidate;
  slots: string[];
  busy: Busy;
  onReport: () => void;
  onCompare: () => void;
}) {
  const slot = slots.indexOf(candidate.slug);
  return (
    <tr data-candidate={candidate.slug}>
      <td>
        <Link className="world-link" href={candidate.path}>
          {candidate.name}
        </Link>
        <div className="muted mono">
          {candidate.position} · {candidate.archetype}
        </div>
      </td>
      <td className="num">{candidate.age}</td>
      <td className="mono">{candidate.band}</td>
      <td className="mono">{candidate.preferred_foot}</td>
      <td className="num">{candidate.overall}</td>
      <td className="num">{candidate.potential}</td>
      <td className="num">{candidate.headroom}</td>
      <td className="num">{money(candidate.valuation.asking_fee)}</td>
      <td className="muted">
        {candidate.answers.map((answer) => (
          <span className="chip mono" key={`${answer.kind}-${answer.phrase}`}>
            {answer.phrase}
          </span>
        ))}
        {!candidate.observed && <span className="badge badge--demo">UNOBSERVED</span>}
      </td>
      <td>
        <button className="btn btn--sm" data-report={candidate.slug} disabled={busy !== null} onClick={onReport} type="button">
          Report
        </button>
      </td>
      <td>
        <button aria-label={`Select ${candidate.name} for comparison`} className={slot >= 0 ? "btn btn--sm btn--primary" : "btn btn--sm"} data-slot={candidate.slug} disabled={busy !== null} onClick={onCompare} type="button">
          {slot === 0 ? "A" : slot === 1 ? "B" : "vs"}
        </button>
      </td>
    </tr>
  );
}

/** Every requirement the request produced, with the rule it will cut or rank on and where it came from. */
function RequirementList({ requirements }: { requirements: ParseView["requirements"] }) {
  if (!requirements.length) return <p className="muted">No filter came from this sentence — a search over it would rank the whole stored pool.</p>;
  return (
    <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
      {requirements.map((item) => (
        <li key={`${item.kind}-${item.phrase}`}>
          <span className="chip mono">{item.kind}</span> <strong>{item.phrase}</strong> <span className="muted mono">{String(item.value ?? "")}</span>
          <div className="muted">
            {item.rule} · <span className="mono">{item.source}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}

/** The honesty block: what was refused, what was assumed, what was ignored, and what was left unaccounted. */
function RefusalBlock({ refused, assumptions, unaccounted }: { refused: ParseView["refused"]; assumptions: string[]; unaccounted: string[] }) {
  if (!refused.length && !assumptions.length && !unaccounted.length) return null;
  return (
    <div className="stack-sm">
      {unaccounted.length > 0 && (
        <ul className="notice notice--warn">
          {unaccounted.map((phrase) => (
            <li key={phrase}>
              <span className="mono">{phrase}</span> was neither parsed nor refused, which should not happen — report it rather than trusting this search
            </li>
          ))}
        </ul>
      )}
      {refused.length > 0 && (
        <ul className="notice notice--warn">
          {refused.map((item) => (
            <li key={item.phrase}>
              <strong className="mono">{item.phrase}</strong> — {item.message}
              {item.suggestions.length > 0 && (
                <div className="muted">
                  closest in the catalogue: {item.suggestions.map((suggestion) => <span className="chip mono" key={suggestion}>{suggestion}</span>)}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {assumptions.length > 0 && (
        <ul className="notice">
          {assumptions.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
