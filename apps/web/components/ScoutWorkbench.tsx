"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { ScoutComparePanel } from "@/components/ScoutComparePanel";
import { ScoutShortlistPanel } from "@/components/ScoutShortlistPanel";
import { ScoutTransferPanel } from "@/components/ScoutTransferPanel";
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
  const tw = useTranslations("scout");
  // The `scout` namespace is 99 keys and was read by nobody: this whole screen was English literals above a
  // fully translated catalogue, so a Chinese reader got a Chinese nav bar and an English page. Every string
  // below already had a key — this component was the largest single gap §81 had left.
  const t = useTranslations("scout");
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
      <Panel eyebrow={t("rulesEyebrow", { players: String(rules.integrity.counts.players_stored), attributes: String(rules.attributes.length), roles: String(Object.keys(rules.roles).length) })} title={t("askTitle")}>
        <div className="stack-sm">
          <div className="row wrap" style={{ gap: "0.6rem" }}>
            <input
              aria-label={tw("requestAria")}
              className="grow"
              maxLength={400}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void runSearch();
              }}
              placeholder={t("placeholder")}
              value={query}
            />
            <input aria-label={tw("roleAria")} className="mono" list="scout-roles" maxLength={16} onChange={(event) => setRole(event.target.value)} placeholder={t("roleLabel")} value={role} />
            <input aria-label={tw("careerSlugAria")} className="mono" maxLength={80} onChange={(event) => setCareer(event.target.value)} placeholder={t("careerLabel")} value={career} />
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
              {busy === "search" ? t("searching") : t("searchWorld")}
            </button>
            <button className="btn" disabled={busy !== null || !query.trim()} onClick={() => void checkWords()} type="button">
              {busy === "parse" ? t("parsing") : t("checkWords")}
            </button>
            <span className="muted">{t("careerHelps")}</span>
          </div>
          {fault && (
            <p className="notice notice--warn">
              <strong>{fault.code}</strong> — {errorMessage(fault, t("requestFailed"))}
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
        <Panel eyebrow={t("parseEyebrow", { filters: parsed.filters_applied })} title={t("parseTitle")}>
          <div data-testid="scout-parse" className="stack-sm">
            <RequirementList requirements={parsed.requirements} />
            <RefusalBlock refused={parsed.refused} assumptions={parsed.assumptions} unaccounted={parsed.unaccounted} />
            <p className="muted">{parsed.note}</p>
          </div>
        </Panel>
      )}

      {searched && (
        <>
          <Panel eyebrow={t("resultsEyebrow", { matches: searched.total_matches, rows: searched.rows_examined, sort: searched.sort.key })} title={t("resultsTitle")}>
            <div className="stack-sm">
              <RefusalBlock refused={searched.refused} assumptions={searched.assumptions} unaccounted={searched.unaccounted} />
              {searched.truncated && (
                <p className="notice">
                  {tw("onlyFirst", { returned: searched.returned, total: searched.total_matches })}
                </p>
              )}
              <div className="world-tablewrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">{t("player")}</th>
                      <th scope="col">{t("age")}</th>
                      <th scope="col">{t("band")}</th>
                      <th scope="col">{t("foot")}</th>
                      <th scope="col" className="num">{t("overall")}</th>
                      <th scope="col" className="num">{t("potential")}</th>
                      <th scope="col" className="num">{t("headroomColumn")}</th>
                      <th scope="col" className="num">{t("askingFee")}</th>
                      <th scope="col">{t("answers")}</th>
                      <th scope="col">{t("report")}</th>
                      <th scope="col">{t("compare")}</th>
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

          <Panel eyebrow={t("waterfallEyebrow", { cuts: searched.waterfall.length })} title={t("waterfallTitle")}>
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{tw("thRequirement")}</th>
                    <th scope="col">{tw("thPhrase")}</th>
                    <th scope="col" className="num">{tw("thRowsIn")}</th>
                    <th scope="col" className="num">{tw("thCut")}</th>
                    <th scope="col" className="num">{tw("thRowsOut")}</th>
                    <th scope="col">{tw("thRule")}</th>
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
                        {step.example_of_a_row_dropped ? <span className="mono"> · {t("droppedExample")} {JSON.stringify(step.example_of_a_row_dropped)}</span> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted">{searched.waterfall_rule}</p>
          </Panel>

          {report?.data && (
            <Panel eyebrow={t("reportEyebrow", { fields: report.data.fields.length, player: report.data.player.name })} title={t("reportTitle")}>
              <div data-testid="scout-report">
                <ScoutReportPanel report={report.data} />
              </div>
            </Panel>
          )}

          <Panel eyebrow={slots.length === 2 ? `${slots[0]} against ${slots[1]}` : t("chooseTwo")} title={t("compareTitle")}>
            <div className="stack-sm">
              <div className="row wrap" style={{ gap: "0.6rem" }}>
                <button className="btn btn--primary" disabled={busy !== null || slots.length !== 2} onClick={() => void runCompare()} type="button">
                  {busy === "compare" ? t("comparing") : t("comparePair")}
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

          {/* The list is where a search ends up, so it sits after the comparison rather than before it. */}
          <ScoutShortlistPanel candidates={searched.candidates} rules={rules.shortlists} searchedQuery={searched.query ?? ""} />

          {/* The simulation is what a scouted name is for: the last panel, after the search, the report, the pair and the list. */}
          <ScoutTransferPanel candidates={searched.candidates} career={career} rules={rules.transfer_simulation} />
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
  const t = useTranslations("scout");
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
          {t("report")}
        </button>
      </td>
      <td>
        <button aria-label={t("selectForComparison", { name: candidate.name })} className={slot >= 0 ? "btn btn--sm btn--primary" : "btn btn--sm"} data-slot={candidate.slug} disabled={busy !== null} onClick={onCompare} type="button">
          {slot === 0 ? "A" : slot === 1 ? "B" : "vs"}
        </button>
      </td>
    </tr>
  );
}

/** Every requirement the request produced, with the rule it will cut or rank on and where it came from. */
function RequirementList({ requirements }: { requirements: ParseView["requirements"] }) {
  const t = useTranslations("scout");
  if (!requirements.length) return <p className="muted">{t("noFilter")}</p>;
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
  const tw = useTranslations("scout");
  if (!refused.length && !assumptions.length && !unaccounted.length) return null;
  return (
    <div className="stack-sm">
      {unaccounted.length > 0 && (
        <ul className="notice notice--warn">
          {unaccounted.map((phrase) => (
            <li key={phrase}>
              <span className="mono">{phrase}</span> {tw("unaccountedTail")}
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
                  {tw("closestInCatalogue")}{" "}
                  {item.suggestions.map((suggestion) => (
                    <span className="chip mono" key={suggestion}>
                      {suggestion}
                    </span>
                  ))}
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
