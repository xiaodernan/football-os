"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
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
  const t = useTranslations("challenges");
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
      setError(t("startError"));
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
          <span>{t("scenario")}</span>
          <select aria-label={t("scenario")} onChange={(event) => setSlug(event.target.value)} value={slug}>
            {catalogue.challenges.map((row) => (
              <option key={row.slug} value={row.slug}>
                {t("scenarioOption", { name: row.name, rounds: row.window_rounds, difficulty: row.difficulty })}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("managerName")}</span>
          <input aria-label={t("managerName")} onChange={(event) => setManager(event.target.value)} placeholder={t("managerPlaceholder")} type="text" value={manager} />
        </label>
        {wantsClub ? (
          <label className="field">
            <span>{t("clubChoose")}</span>
            <select aria-label={t("club")} onChange={(event) => setClub(event.target.value)} value={club}>
              {catalogue.clubs.map((row) => (
                <option key={row.slug} value={row.slug}>
                  {t("clubOption", { name: row.name, formation: row.formation, overall: row.overall })}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <label className="field">
            <span>{t("competitionLabel")}</span>
            <select aria-label={t("competition")} onChange={(event) => setCompetition(event.target.value)} value={competition}>
              {catalogue.competitions.map((row) => (
                <option key={row.slug} value={row.slug}>
                  {t("competitionOption", { name: row.name, clubs: row.clubs })}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="field">
          <span>{t("systemLabel")}</span>
          <select aria-label={t("system")} onChange={(event) => setSystem(event.target.value)} value={system}>
            <option value="">{wantsClub ? t("systemDefaultClub", { shape: clubFormation || t("noShape") }) : t("systemDefaultMeasured")}</option>
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
          {busy ? t("startButtonBusy") : t("startButton")}
        </button>
        <span className="muted">
          {t("perAccount", { max: catalogue.max_runs_per_user })}
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
  const t = useTranslations("challenges");
  return (
    <div className="stack-sm" data-testid="challenge-scenario">
      <p className="notice">{scenario.brief}</p>
      <div className="tag-list">
        <span className="chip mono">{t("cardWindow", { rounds: scenario.window_rounds })}</span>
        <span className="chip mono">{t("cardPhilosophy", { philosophy: scenario.philosophy })}</span>
        <span className="chip mono">{t("cardBudget", { budget: scenario.budget.toLocaleString("en-GB"), units: scenario.budget_units })}</span>
        {scenario.objectives.map((objective) => (
          <span className="chip mono" key={objective.kind}>
            {t("cardObjective", { kind: objective.kind, target: objective.target })}
          </span>
        ))}
      </div>
    </div>
  );
}

/** The measurement the club came from, printed in the response that carried it. */
function OpenedRun({ opened }: { opened: ChallengeRunView }) {
  const t = useTranslations("challenges");
  const tc = useTranslations("common");
  const choice = opened.club_choice;
  const ranking = (choice?.ranking ?? []).filter((row) => row.measurable && typeof row.overall === "number");
  const lowest = ranking.reduce<number | null>((min, row) => (min === null || Number(row.overall) < min ? Number(row.overall) : min), null);
  return (
    <div className="stack-sm" data-testid="challenge-club-choice" role="status">
      <p className="notice">
        {t("runOpenedPre")}<strong>{opened.career.club_name}</strong>{t("runOpenedUnder")}{opened.challenge?.name}.{" "}
        {choice?.how}
      </p>
      {choice?.selector === "weakest" && ranking.length > 0 && (
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("measuredHeader")}</th>
                <th scope="col">{t("elevenHeader")}</th>
              </tr>
            </thead>
            <tbody>
              {ranking.map((row) => (
                <tr key={row.name}>
                  <td>{row.name}</td>
                  <td className="mono">
                    {row.overall}
                    {choice.chosen.name === row.name ? t("taken") : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="tag-list">
        <span className="chip mono">{t("lowestMeasured", { lowest: lowest ?? "—" })}</span>
        <span className="chip mono">{t("yourClubMeasured", { overall: choice?.chosen.overall ?? t("youNamedClub") })}</span>
        <span className="chip mono">{t("gapRunnerUp", { gap: choice?.gap_to_runner_up ?? "—" })}</span>
        <span className="chip mono">{t("catalogueLabel", { fp: opened.run?.fingerprint ?? "" })}</span>
      </div>
      <p className="muted">{opened.verdict?.closed_by} {opened.verdict?.judged_on}</p>
      <Link className="btn btn--sm" href={`/challenges/runs/${encodeURIComponent(opened.career.slug)}`}>
        {tc("open")}{t("openTheRun")}
      </Link>
    </div>
  );
}
