"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

/**
 * Analyse, queue a background run, and delete — the actions a clip's owner can take.
 *
 * `analyse` runs the pipeline inside the request and answers with the report; the button waits and
 * then refreshes the server-rendered page. `queue` does not wait inside the request at all: it asks
 * the server to put a `QUEUED` job row on the board, and the worker process measures the clip. The
 * button then polls the job's own status endpoint and refreshes when the row settles — the numbers on
 * screen always come from the read path, never from a copy the client kept for itself.
 */
export function VideoTools({ assetId, status }: { assetId: string; status: string }) {
  const router = useRouter();
  const t = useTranslations("video");
  const [busy, setBusy] = useState<null | "analyse" | "delete" | "queue">(null);
  const [error, setError] = useState<string | null>(null);
  const [queueStatus, setQueueStatus] = useState<string | null>(null);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

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
        setError(detail?.message ? `${detail.code ?? "failed"}: ${detail.message}` : t("errRequest", { status: response.status }));
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
      setError(t("errComplete", { cause: String(cause).slice(0, 120) }));
    }
    setBusy(null);
  }

  async function queue() {
    setBusy("queue");
    setError(null);
    setQueueStatus(null);
    try {
      const response = await fetch(`/api/v1/video/${encodeURIComponent(assetId)}/analyse?background=true`, {
        method: "POST",
        credentials: "same-origin",
      });
      const payload = (await response.json().catch(() => null)) as { job_id?: string; status?: string } | null;
      if (!response.ok || !payload?.job_id) {
        const detail = (payload as { detail?: { code?: string; message?: string } } | null)?.detail;
        setError(detail?.message ? `${detail.code ?? "failed"}: ${detail.message}` : t("errRequest", { status: response.status }));
        setBusy(null);
        return;
      }
      setQueueStatus(payload.status ?? "QUEUED");
      await pollJob(payload.job_id);
    } catch (cause) {
      setError(t("errComplete", { cause: String(cause).slice(0, 120) }));
    }
    setBusy(null);
  }

  async function pollJob(jobId: string) {
    // Two minutes of patience, two seconds at a time; a clip analysis is minutes of ffmpeg work, so the
    // poll stops short of it and says what it knows. The job row keeps the outcome either way.
    for (let attempt = 0; attempt < 60; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      if (!mounted.current) return;
      try {
        const response = await fetch(`/api/v1/jobs/${encodeURIComponent(jobId)}`, { credentials: "same-origin" });
        if (!response.ok) continue;
        const payload = (await response.json()) as { status?: string; error?: string | null };
        if (!payload.status) continue;
        setQueueStatus(payload.status);
        if (payload.status === "COMPLETED") {
          router.refresh();
          return;
        }
        if (payload.status === "FAILED") {
          setError(t("queueFailed", { error: String(payload.error ?? "unknown").slice(0, 160) }));
          return;
        }
        if (payload.status === "CANCELLED") return;
      } catch {
        // A failed poll is not a verdict; the loop keeps asking.
      }
    }
    if (mounted.current) setError(t("queuePending"));
  }

  return (
    <div className="stack-sm">
      <div className="row wrap" style={{ gap: "0.5rem" }}>
        <button className="btn btn--primary btn--sm" disabled={busy !== null} onClick={() => call("analyse")} type="button">
          {busy === "analyse" ? t("analysing") : status === "analysed" ? t("analyseAgain") : t("analyse")}
        </button>
        <button className="btn btn--ghost btn--sm" disabled={busy !== null} onClick={queue} type="button">
          {busy === "queue" ? t("queueing") : t("queueAnalyse")}
        </button>
        <button className="btn btn--danger btn--sm" disabled={busy !== null} onClick={() => call("delete")} type="button">
          {busy === "delete" ? `${t("deleteClip")}…` : t("deleteClip")}
        </button>
      </div>
      {queueStatus && <p className="chip mono">{queueStatus === "QUEUED" ? t("queueQueued") : queueStatus === "RUNNING" ? t("queueRunning") : queueStatus === "COMPLETED" ? t("queueDone") : queueStatus}</p>}
      <p className="muted world-section-note">{t("toolsNote")}</p>
      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}
    </div>
  );
}
