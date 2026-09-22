"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/**
 * Analyse and delete, the two actions a clip's owner can take.
 *
 * `analyse` runs the pipeline inside the request and answers with the report, so the button just
 * waits and then refreshes the server-rendered page: the numbers on screen come from the same read
 * path as everything else, not from a copy the client kept for itself.
 */
export function VideoTools({ assetId, status }: { assetId: string; status: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState<null | "analyse" | "delete">(null);
  const [error, setError] = useState<string | null>(null);

  async function call(action: "analyse" | "delete") {
    setBusy(action);
    setError(null);
    try {
      const response = await fetch(`/api/v1/video/${encodeURIComponent(assetId)}${action === "analyse" ? "/analyse" : ""}`, {
        method: action === "analyse" ? "POST" : "DELETE",
        credentials: "same-origin",
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        const detail = (payload as { detail?: { code?: string; message?: string } } | null)?.detail;
        setError(detail?.message ? `${detail.code ?? "failed"}: ${detail.message}` : `Request failed (${response.status}).`);
        setBusy(null);
        return;
      }
      if (action === "delete") {
        router.push("/video");
        router.refresh();
        return;
      }
      router.refresh();
    } catch (cause) {
      setError(`The request could not be completed: ${String(cause).slice(0, 120)}`);
    }
    setBusy(null);
  }

  return (
    <div className="stack-sm">
      <div className="row wrap" style={{ gap: "0.5rem" }}>
        <button className="btn btn--primary btn--sm" disabled={busy !== null} onClick={() => call("analyse")} type="button">
          {busy === "analyse" ? "Measuring frames…" : status === "analysed" ? "Analyse again" : "Analyse this clip"}
        </button>
        <button className="btn btn--danger btn--sm" disabled={busy !== null} onClick={() => call("delete")} type="button">
          {busy === "delete" ? "Deleting…" : "Delete clip and file"}
        </button>
      </div>
      <p className="muted world-section-note">
        Analysis runs in this request and records a job row for itself; there is no queue and no worker, and the page says so rather than
        showing a progress bar that nothing is feeding.
      </p>
      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}
    </div>
  );
}
