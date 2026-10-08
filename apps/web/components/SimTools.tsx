"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { browserFetch } from "@/lib/api";
import type { SimReplay } from "@/lib/types";

/**
 * The two things an owner can do with a stored match: ask the model to play it again, and delete it.
 *
 * The replay check is not a decoration. It re-runs `simulate_match` from the stored inputs on the
 * server and compares the digest with the one on file, so the page can say either &quot;this row is
 * reproducible&quot; or &quot;it is not&quot; — the latter meaning the engine changed without its version
 * changing, which is the failure this milestone would rather surface than hide.
 */
export function SimTools({ ident, digest }: { ident: string; digest: string }) {
  const router = useRouter();
  const t = useTranslations("common");
  const [busy, setBusy] = useState<null | "replay" | "delete">(null);
  const [error, setError] = useState<string | null>(null);
  const [replay, setReplay] = useState<SimReplay | null>(null);

  async function check() {
    setBusy("replay");
    setError(null);
    const result = await browserFetch<SimReplay>(`/simulate/${encodeURIComponent(ident)}/replay`);
    if (!result.ok) setError(`${result.error.code}: ${result.error.message}`);
    else setReplay(result.data);
    setBusy(null);
  }

  async function remove() {
    setBusy("delete");
    setError(null);
    const result = await browserFetch<null>(`/simulate/${encodeURIComponent(ident)}`, { method: "DELETE" });
    if (!result.ok) {
      setError(`${result.error.code}: ${result.error.message}`);
      setBusy(null);
      return;
    }
    router.push("/simulate");
    router.refresh();
  }

  return (
    <div className="stack-sm">
      <div className="row wrap" style={{ gap: "0.6rem" }}>
        <button className="btn btn--ghost" disabled={busy !== null} onClick={check} type="button">
          {busy === "replay" ? "Replaying…" : "Replay and compare"}
        </button>
        <button className="btn btn--ghost" disabled={busy !== null} onClick={remove} type="button">
          {busy === "delete" ? `${t("delete")}…` : `${t("delete")} this match`}
        </button>
      </div>

      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}

      {replay && !replay.possible && (
        <p className="notice notice--warn" role="status">
          The check could not run: {replay.reason ?? "one of the clubs is no longer in the generated world"}. The stored digest
          stays what it was — nothing here pretends to have re-derived it.
        </p>
      )}

      {replay?.possible && (
        <div className="stack-sm" data-testid="sim-replay" role="status">
          <p className={replay.identical ? "notice" : "notice notice--warn"}>
            {replay.identical
              ? `Identical. Playing the same two squads, systems, length and seed through ${replay.model_version} produced ${replay.replayed_digest} again, which is the digest on this row.`
              : `Not identical. The row says ${replay.stored_digest} and a fresh run says ${replay.replayed_digest}. The engine moved without its version moving, so this match is no longer reproducible and is kept as a record of what was claimed.`}
          </p>
          <div className="tag-list">
            <span className="chip mono">stored digest: {replay.stored_digest}</span>
            <span className="chip mono">replayed digest: {replay.replayed_digest}</span>
            <span className="chip mono">this page&rsquo;s digest: {digest}</span>
            <span className="chip mono">model: {replay.model_version}</span>
          </div>
        </div>
      )}
    </div>
  );
}
