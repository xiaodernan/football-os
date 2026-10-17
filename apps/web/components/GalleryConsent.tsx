"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { browserFetch, errorMessage } from "@/lib/api";

/**
 * M9's consent story, on the owner's side: one button to list a board in the public
 * gallery, one to withdraw it. The sentence the catalogue carries is the one the
 * reader acts on — it says what becomes public (name, measurements, display name),
 * that it is revocable, and that revocation removes the board from the gallery
 * without deleting it.
 */
export function GalleryConsent({ slug, listed }: { slug: string; listed: boolean }) {
  const router = useRouter();
  const t = useTranslations("tactics");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function call(action: "list" | "unlist") {
    setBusy(true);
    setError(null);
    const result =
      action === "list"
        ? await browserFetch(`/boards/${encodeURIComponent(slug)}/list-publicly`, { method: "POST" })
        : await browserFetch(`/boards/${encodeURIComponent(slug)}/list-publicly`, { method: "DELETE" });
    if (!result.ok) {
      setError(errorMessage(result.error, t("consentFailed")));
      setBusy(false);
      return;
    }
    router.refresh();
    setBusy(false);
  }

  return (
    <div className="stack-sm">
      <span className={`chip ${listed ? "chip--accent" : ""}`}>{listed ? t("consentListed") : t("consentUnlisted")}</span>
      <p className="muted world-section-note">{t("consentSentence")}</p>
      <div>
        {listed ? (
          <button className="btn btn--warn btn--sm" disabled={busy} onClick={() => void call("unlist")} type="button">
            {busy ? t("consentWorking") : t("consentWithdraw")}
          </button>
        ) : (
          <button className="btn btn--primary btn--sm" disabled={busy} onClick={() => void call("list")} type="button">
            {busy ? t("consentWorking") : t("consentList")}
          </button>
        )}
      </div>
      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}
    </div>
  );
}
