"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
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
  const t = useTranslations("video");
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

  return (
    <div className="stack-sm">
      <div className="row wrap" style={{ gap: "0.5rem" }}>
        <button className="btn btn--primary btn--sm" disabled={busy !== null} onClick={() => call("analyse")} type="button">
          {busy === "analyse" ? t("analysing") : status === "analysed" ? t("analyseAgain") : t("analyse")}
        </button>
        <button className="btn btn--danger btn--sm" disabled={busy !== null} onClick={() => call("delete")} type="button">
          {busy === "delete" ? `${t("deleteClip")}…` : t("deleteClip")}
        </button>
      </div>
      <p className="muted world-section-note">{t("toolsNote")}</p>
      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}
    </div>
  );
}
