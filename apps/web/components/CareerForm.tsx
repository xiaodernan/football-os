"use client";

import { useRouter } from "next/navigation";
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
      setError("Name at least one objective with a target, so the season can be judged against something.");
      setBusy(false);
      return;
    }
    if (manager.trim().length < 2) {
      setError("A manager name of at least two characters is required — the career is printed with it.");
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
          <span>Club (generated)</span>
          <select aria-label="Club" onChange={(event) => setClub(event.target.value)} value={club}>
            {options.clubs.map((row) => (
              <option key={row.slug} value={row.slug}>
                {row.name} · {row.formation} · {row.overall}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Manager name</span>
          <input aria-label="Manager name" onChange={(event) => setManager(event.target.value)} placeholder="How the season is signed" type="text" value={manager} />
        </label>
        <label className="field">
          <span>Philosophy (stated intent)</span>
          <select aria-label="Philosophy" onChange={(event) => setPhilosophy(event.target.value)} value={philosophy}>
            {options.philosophies.map((row) => (
              <option key={row} value={row}>
                {row}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Tactical system — the part the engine reads</span>
          <select aria-label="Tactical system" onChange={(event) => setSystem(event.target.value)} value={system}>
            <option value="">Club default ({clubFormation || "no shape"})</option>
            {systems.map((row) => (
              <option key={row.slug} value={row.slug}>
                {row.label ?? row.slug}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>
            Budget ({options.budget_units})
          </span>
          <input aria-label="Budget" min={0} onChange={(event) => setBudget(event.target.value)} type="number" value={budget} />
        </label>
        <p className="muted" role="note">
          This is what the transfer market gets to spend: an offer priced above the balance left is refused, and every
          round played charges the wages of the deals the club holds. A budget still changes no fixture by itself — only
          a deal that was actually made changes the eleven.
        </p>
      </div>

      <div className="stack-sm">
        <span className="eyebrow">Objectives · at least one</span>
        {objectives.map((row, index) => (
          <div className="row wrap sim-row" key={`objective-${index}`}>
            <select aria-label={`objective ${index + 1} kind`} onChange={(event) => setObjective(index, { kind: event.target.value })} value={row.kind}>
              {KIND_ORDER.filter((kind) => options.objective_kinds[kind]).map((kind) => (
                <option key={kind} value={kind}>
                  {kind}
                </option>
              ))}
            </select>
            <input aria-label="target" onChange={(event) => setObjective(index, { target: event.target.value })} placeholder="target" size={6} type="number" value={row.target} />
            <input aria-label="label" onChange={(event) => setObjective(index, { label: event.target.value })} placeholder={options.objective_kinds[row.kind]} type="text" value={row.label} />
            {index > 0 && (
              <button className="btn btn--ghost btn--sm" onClick={() => setObjectives((current) => current.filter((_, at) => at !== index))} type="button">
                Remove
              </button>
            )}
          </div>
        ))}
        {objectives.length < 4 && (
          <button className="btn btn--ghost btn--sm" onClick={() => setObjectives((current) => [...current, { kind: "wins", target: "", label: "" }])} type="button">
            Add an objective
          </button>
        )}
      </div>

      <div className="row wrap" style={{ gap: "0.6rem" }}>
        <button className="btn" disabled={busy} onClick={submit} type="button">
          {busy ? "Opening…" : "Open this career"}
        </button>
        <span className="muted">Up to {options.max_careers_per_user} per account. Every fixture is decided by the labelled simulation engine.</span>
      </div>

      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}
    </div>
  );
}
