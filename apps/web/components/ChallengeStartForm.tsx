"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import Link from "next/link";

import { browserFetch } from "@/lib/api";
import type { ChallengeCatalogue, ChallengeEntry, ChallengeRunView } from "@/lib/types";

/**
 * Starting a run of a scenario (spec §21).
 *
 * The form sends the two things the caller is allowed to choose — which club or competition, and which
 * tactical system — plus a name. It cannot send a window, a budget, an objective or a philosophy: those
 * belong to the scenario, and the server accepts no field for them, so a target cannot be negotiated
 * down at the moment of opening.
 *
 * What the response adds is the part worth keeping on screen: the **measurement** behind a `weakest`
 * club. Each scenario that hands you the weakest club returns the rating it gave every club in that
 * competition, so the page can print the ranking the choice came from rather than asserting the club is
 * weak. That only exists in this response, which is why the panel is rendered here instead of after a
 * redirect — the run page shows the club it gave, not the arithmetic that selected it.
 */
export function ChallengeStartForm({ catalogue }: { catalogue: ChallengeCatalogue }) {
  const router = useRouter();
  const first = catalogue.challenges[0];
  const [slug, setSlug] = useState(first?.slug ?? "");
  const [manager, setManager] = useState("");
  const [competition, setCompetition] = useState(catalogue.competitions[0]?.slug ?? "");
  const [club, setClub] = useState(catalogue.clubs[0]?.slug ?? "");
  const [system, setSystem] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [opened, setOpened] = useState<ChallengeRunView | null>(null);

  const scenario = catalogue.challenges.find((row) => row.slug === slug);
  const wantsClub = scenario?.club_selector === "any";
  const clubFormation = catalogue.clubs.find((row) => row.slug === club)?.formation ?? "";
  const systems = useMemo(
    () => (wantsClub && clubFormation ? catalogue.systems.filter((row) => row.formation === clubFormation) : catalogue.systems),
    [catalogue.systems, clubFormation, wantsClub],
  );

  async function submit() {
    if (!scenario) return;
    setBusy(true);
    setError(null);
    setOpened(null);
    if (manager.trim().length < 2) {
      setError("A manager name of at least two characters is required — the run is printed with it.");
      setBusy(false);
      return;
    }
    const result = await browserFetch<ChallengeRunView>(`/challenges/${encodeURIComponent(scenario.slug)}/start`, {
      method: "POST",
      body: {
        manager_name: manager.trim(),
        club: wantsClub ? club : null,
        competition: wantsClub ? null : competition,
        system: system || null,
        season: "2026",
      },
    });
    if (!result.ok) {
      setError(`${result.error.code}: ${result.error.message}`);
      setBusy(false);
      return;
    }
    setOpened(result.data);
    router.refresh();
    setBusy(false);
  }

  return (
    <div className="stack">
      <div className="grid grid-2">
        <label className="field">
          <span>Scenario</span>
          <select aria-label="Scenario" onChange={(event) => setSlug(event.target.value)} value={slug}>
            {catalogue.challenges.map((row) => (
              <option key={row.slug} value={row.slug}>
                {row.name} · {row.window_rounds} rounds · {row.difficulty}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Manager name</span>
          <input aria-label="Manager name" onChange={(event) => setManager(event.target.value)} placeholder="How the run is signed" type="text" value={manager} />
        </label>
        {wantsClub ? (
          <label className="field">
            <span>Club (you choose it)</span>
            <select aria-label="Club" onChange={(event) => setClub(event.target.value)} value={club}>
              {catalogue.clubs.map((row) => (
                <option key={row.slug} value={row.slug}>
                  {row.name} · {row.formation} · {row.overall}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <label className="field">
            <span>Competition to take the weakest club from</span>
            <select aria-label="Competition" onChange={(event) => setCompetition(event.target.value)} value={competition}>
              {catalogue.competitions.map((row) => (
                <option key={row.slug} value={row.slug}>
                  {row.name} · {row.clubs} clubs
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="field">
          <span>Tactical system — the part the engine reads</span>
          <select aria-label="Tactical system" onChange={(event) => setSystem(event.target.value)} value={system}>
            <option value="">{wantsClub ? `Club default (${clubFormation || "no shape"})` : "Club default, whichever club the measurement picks"}</option>
            {systems.map((row) => (
              <option key={row.slug} value={row.slug}>
                {row.label ?? row.slug}
              </option>
            ))}
          </select>
        </label>
      </div>

      {scenario && <ScenarioSummary scenario={scenario} />}

      <div className="row wrap" style={{ gap: "0.6rem" }}>
        <button className="btn" disabled={busy || !scenario} onClick={submit} type="button">
          {busy ? "Opening the run…" : "Start this run"}
        </button>
        <span className="muted">
          Up to {catalogue.max_runs_per_user} per account. The window, the budget and the objectives come from the scenario and are not offered here.
        </span>
      </div>

      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}

      {opened && !busy && <OpenedRun opened={opened} />}
    </div>
  );
}

function ScenarioSummary({ scenario }: { scenario: ChallengeEntry }) {
  return (
    <div className="stack-sm" data-testid="challenge-scenario">
      <p className="notice">{scenario.brief}</p>
      <div className="tag-list">
        <span className="chip mono">window: {scenario.window_rounds} rounds</span>
        <span className="chip mono">philosophy: {scenario.philosophy}</span>
        <span className="chip mono">budget: {scenario.budget.toLocaleString("en-GB")} {scenario.budget_units}</span>
        {scenario.objectives.map((objective) => (
          <span className="chip mono" key={objective.kind}>
            {objective.kind} ≥ {objective.target}
          </span>
        ))}
      </div>
    </div>
  );
}

/** The measurement the club came from, printed in the response that carried it. */
function OpenedRun({ opened }: { opened: ChallengeRunView }) {
  const choice = opened.club_choice;
  const ranking = (choice?.ranking ?? []).filter((row) => row.measurable && typeof row.overall === "number");
  const lowest = ranking.reduce<number | null>((min, row) => (min === null || Number(row.overall) < min ? Number(row.overall) : min), null);
  return (
    <div className="stack-sm" data-testid="challenge-club-choice" role="status">
      <p className="notice">
        Run opened: <strong>{opened.career.club_name}</strong> under {opened.challenge?.name}.{" "}
        {choice?.how}
      </p>
      {choice?.selector === "weakest" && ranking.length > 0 && (
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Club measured</th>
                <th scope="col">Selected eleven (OVR mean on the engine&apos;s 0–1 scale)</th>
              </tr>
            </thead>
            <tbody>
              {ranking.map((row) => (
                <tr key={row.name}>
                  <td>{row.name}</td>
                  <td className="mono">
                    {row.overall}
                    {choice.chosen.name === row.name ? " ← taken" : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="tag-list">
        <span className="chip mono">lowest measured: {lowest ?? "—"}</span>
        <span className="chip mono">your club measured: {choice?.chosen.overall ?? "you named this club"}</span>
        <span className="chip mono">gap to runner-up: {choice?.gap_to_runner_up ?? "—"}</span>
        <span className="chip mono">catalogue: {opened.run?.fingerprint}</span>
      </div>
      <p className="muted">{opened.verdict?.closed_by} {opened.verdict?.judged_on}</p>
      <Link className="btn btn--sm" href={`/challenges/runs/${encodeURIComponent(opened.career.slug)}`}>
        Open the run
      </Link>
    </div>
  );
}
