"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { browserFetch, errorMessage } from "@/lib/api";

/**
 * The tray's two read-state verbs, as client fetches rather than HTML forms: a form whose
 * action is an API route navigates the browser to the JSON answer, and the reader lands on
 * raw bytes instead of the tray they were reading. After either verb the page refreshes, so
 * the unread arithmetic and the nav badge repaint from the door's own answer.
 */
export function MarkAllButton({ unreadTotal }: { unreadTotal: number }) {
  const router = useRouter();
  const t = useTranslations("notifications");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (unreadTotal <= 0) return null;

  async function markAll() {
    setBusy(true);
    setError(null);
    const result = await browserFetch("/notifications/read-all", { method: "POST" });
    if (!result.ok) {
      setError(errorMessage(result.error, t("markFailed")));
      setBusy(false);
      return;
    }
    router.refresh();
    setBusy(false);
  }

  return (
    <div className="stack-sm">
      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}
      <button className="btn btn--ghost btn--sm" disabled={busy} onClick={() => void markAll()} type="button">
        {busy ? t("working") : t("markAll")}
      </button>
    </div>
  );
}

export function MarkReadButton({ id }: { id: string }) {
  const router = useRouter();
  const t = useTranslations("notifications");
  const [busy, setBusy] = useState(false);

  async function markOne() {
    setBusy(true);
    const result = await browserFetch(`/notifications/${id}/read`, { method: "POST" });
    if (!result.ok) {
      setBusy(false);
      return;
    }
    router.refresh();
    setBusy(false);
  }

  return (
    <button className="btn btn--ghost btn--sm" disabled={busy} onClick={() => void markOne()} type="button">
      {busy ? t("working") : t("markRead")}
    </button>
  );
}
