"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { browserFetch } from "@/lib/api";
import type { CareerOptions, CareerView } from "@/lib/types";

/**
 * Opening a career: a club from the generated world, a name, a stated intent and at least one
 * objective to be judged by.
 *
 * The form sends choices, never numbers it computed. Budget and philosophy go as stated intent
 * because that is all they are in this build — the API's `limitations` block says so on every read,
 * and the page repeats it rather than letting a large budget read as a constraint that was applied.
 * Objectives are the one place a visitor decides what success means, so an empty list is refused
 * here as well as by the server.
 */
const KIND_ORDER = ["points", "wins", "goal_difference", "unbeaten"];

type ObjectiveDraft = { kind: string; target: string; label: string };

export function CareerForm({ options }: { options: CareerOptions }) {
  const router = useRouter();
  // The `career` namespace was fully translated and read by nobody — this form and its page were English
  // literals under a translated nav. Each string below comes from the catalogue now, so the reader's
  // chosen language reaches the form itself, not just the bar above it.
  const t = useTranslations("career");
  const tc = useTranslations("career");
  const [club, setClub] = useState(options.clubs[0]?.slug ?? "");
  const [manager, setManager] = useState("");
  const [philosophy, setPhilosophy] = useState(options.philosophies.includes("balanced") ? "balanced" : options.philosophies[0] ?? "");
  const [system, setSystem] = useState("");
  const [budget, setBudget] = useState("250000");
  const [objectives, setObjectives] = useState<ObjectiveDraft[]>([{ kind: "points", target: "7", label: "" }]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clubFormation = options.clubs.find((row) => row.slug === club)?.formation ?? "";
  const systems = useMemo(
    () => options.systems.filter((row) => row.formation === clubFormation),
    [options.systems, clubFormation],
  );

  function setObjective(index: number, patch: Partial<ObjectiveDraft>) {
    setObjectives((current) => current.map((row, at) => (at === index ? { ...row, ...patch } : row)));
  }

  async function submit() {
    setBusy(true);
    setError(null);
    const chosen = objectives
      .filter((row) => row.target.trim() !== "")
      .map((row) => ({ kind: row.kind, target: Number(row.target.trim()), label: row.label.trim() || undefined }));
    if (chosen.length === 0) {
      setError(t("objectiveRequired"));
      setBusy(false);
      return;
    }
    if (manager.trim().length < 2) {
      setError(t("managerNameRequired"));
      setBusy(false);
      return;
    }
    const result = await browserFetch<CareerView>("/careers", {
      method: "POST",
      body: {
        club,
        manager_name: manager.trim(),
        philosophy,
        system: system || null,
        budget: Number(budget) || 0,
        objectives: chosen,
        season: "2026",
      },
    });
    if (!result.ok) {
      setError(`${result.error.code}: ${result.error.message}`);
      setBusy(false);
      return;
    }
    // Navigate instead of rendering the POST body: the season page reads the rows back the same way
    // every other page does, so the client cannot show a career the server did not keep.
    router.push(`/career/${encodeURIComponent(result.data.career.slug)}`);
    router.refresh();
  }

  return (
    <div className="stack">
      <div className="grid grid-2">
        <label className="field">
          <span>{t("club")}</span>
          <select aria-label={t("club")} onChange={(event) => setClub(event.target.value)} value={club}>
            {options.clubs.map((row) => (
              <option key={row.slug} value={row.slug}>
                {row.name} · {row.formation} · {row.overall}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("managerName")}</span>
          <input aria-label={t("managerName")} onChange={(event) => setManager(event.target.value)} placeholder={t("enterManagerName")} type="text" value={manager} />
        </label>
        <label className="field">
          <span>{t("philosophy")} {tc("statedIntent")}</span>
          <select aria-label={t("philosophy")} onChange={(event) => setPhilosophy(event.target.value)} value={philosophy}>
            {options.philosophies.map((row) => (
              <option key={row} value={row}>
                {row}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("tacticalSystemLabel")}</span>
          <select aria-label={t("tacticalSystem")} onChange={(event) => setSystem(event.target.value)} value={system}>
            <option value="">
              {tc("clubDefault", { formation: clubFormation || tc("noShape") })}
            </option>
            {systems.map((row) => (
              <option key={row.slug} value={row.slug}>
                {row.label ?? row.slug}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>
            {t("budget")} ({options.budget_units})
          </span>
          <input aria-label={t("budget")} min={0} onChange={(event) => setBudget(event.target.value)} type="number" value={budget} />
        </label>
        <p className="muted" role="note">
          {t("budgetHelp")} {t("wageBillHelp")}
        </p>
      </div>

      <div className="stack-sm">
        <span className="eyebrow">{t("objectives")} · {t("atLeastOne")}</span>
        {objectives.map((row, index) => (
          <div className="row wrap sim-row" key={`objective-${index}`}>
            <select aria-label={`${t("objectiveKind")} ${index + 1}`} onChange={(event) => setObjective(index, { kind: event.target.value })} value={row.kind}>
              {KIND_ORDER.filter((kind) => options.objective_kinds[kind]).map((kind) => (
                <option key={kind} value={kind}>
                  {kind}
                </option>
              ))}
            </select>
            <input aria-label={t("target")} onChange={(event) => setObjective(index, { target: event.target.value })} placeholder={t("target")} size={6} type="number" value={row.target} />
            <input aria-label={t("label")} onChange={(event) => setObjective(index, { label: event.target.value })} placeholder={options.objective_kinds[row.kind]} type="text" value={row.label} />
            {index > 0 && (
              <button className="btn btn--ghost btn--sm" onClick={() => setObjectives((current) => current.filter((_, at) => at !== index))} type="button">
                {t("removeObjective")}
              </button>
            )}
          </div>
        ))}
        {objectives.length < 4 && (
          <button className="btn btn--ghost btn--sm" onClick={() => setObjectives((current) => [...current, { kind: "wins", target: "", label: "" }])} type="button">
            {t("addObjective")}
          </button>
        )}
      </div>

      <div className="row wrap" style={{ gap: "0.6rem" }}>
        <button className="btn" disabled={busy} onClick={submit} type="button">
          {busy ? tc("opening") : t("startCareer")}
        </button>
        <span className="muted">{tc("upToCareers", { max: options.max_careers_per_user })}</span>
      </div>

      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}
    </div>
  );
}
