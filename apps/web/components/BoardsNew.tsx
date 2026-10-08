"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { browserFetch, errorMessage } from "@/lib/api";

/**
 * "New board": copy one of the 50 authored systems into the account's own space, or start empty.
 *
 * The positions come from the API (the authored system's own two phases), so a new board begins as a
 * real arrangement with real measurements rather than eleven dots stacked at the centre of the pitch.
 */
export function BoardsNew({ systems }: { systems: { slug: string; name: string }[] }) {
  const router = useRouter();
  const t = useTranslations("common");
  const [origin, setOrigin] = useState(systems[0]?.slug ?? "");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    if (!origin) return;
    setBusy(true);
    setError(null);
    const source = await browserFetch<{ phase_in: unknown[]; phase_out: unknown[] }>(`/tactics/${encodeURIComponent(origin)}`);
    if (!source.ok) {
      setBusy(false);
      setError(errorMessage(source.error, "The authored system could not be read."));
      return;
    }
    const created = await browserFetch<{ slug: string }>("/boards", {
      method: "POST",
      body: {
        name: name.trim() || "My board",
        origin_system: origin,
        phase_in: source.data.phase_in,
        phase_out: source.data.phase_out,
      },
    });
    setBusy(false);
    if (!created.ok) {
      setError(errorMessage(created.error, "The board could not be created."));
      return;
    }
    router.push(`/tactics/boards/${created.data.slug}`);
    router.refresh();
  }

  return (
    <div className="stack-sm">
      <div className="grid grid-2">
        <label className="field">
          <span className="field__label">Start from</span>
          <select className="select" name="origin" onChange={(event) => setOrigin(event.target.value)} value={origin}>
            {systems.map((system) => (
              <option key={system.slug} value={system.slug}>
                {system.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field__label">Name it</span>
          <input
            className="input"
            maxLength={120}
            name="name"
            onChange={(event) => setName(event.target.value)}
            placeholder={systems.find((system) => system.slug === origin)?.name ?? "My board"}
            type="text"
            value={name}
          />
        </label>
      </div>
      <div>
        <button className="btn btn--primary btn--sm" disabled={busy || !origin} onClick={create} type="button">
          {busy ? `${t("create")}…` : `${t("create")} and edit`}
        </button>
      </div>
      <p className="muted world-section-note">
        The copy keeps the authored system&apos;s exact coordinates, so its first measurements are the system&apos;s. After that the
        board is yours: nothing here writes back to the catalogue.
      </p>
      {error && <p className="notice notice--warn">{error}</p>}
    </div>
  );
}
