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
  const t = useTranslations("simulate");
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
          {busy === "replay" ? t("replayBusy") : t("replayBtn")}
        </button>
        <button className="btn btn--ghost" disabled={busy !== null} onClick={remove} type="button">
          {busy === "delete" ? t("deleteBusy") : t("deleteThis")}
        </button>
      </div>

      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}

      {replay && !replay.possible && (
        <p className="notice notice--warn" role="status">
          {t("replayUnable", { reason: replay.reason ?? t("clubGone") })}
        </p>
      )}

      {replay?.possible && (
        <div className="stack-sm" data-testid="sim-replay" role="status">
          <p className={replay.identical ? "notice" : "notice notice--warn"}>
            {replay.identical
              ? t("replayIdentical", { version: String(replay.model_version), replayed: String(replay.replayed_digest) })
              : t("replayNotIdentical", { stored: String(replay.stored_digest), replayed: String(replay.replayed_digest) })}
          </p>
          <div className="tag-list">
            <span className="chip mono">{t("storedDigestChip", { digest: String(replay.stored_digest) })}</span>
            <span className="chip mono">{t("replayedDigestChip", { digest: String(replay.replayed_digest) })}</span>
            <span className="chip mono">{t("pageDigestChip", { digest })}</span>
            <span className="chip mono">{t("modelChip", { version: String(replay.model_version) })}</span>
          </div>
        </div>
      )}
    </div>
  );
}
