"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { browserFetch, errorMessage } from "@/lib/api";
import type { NotificationPrefs } from "@/lib/types";

/**
 * The tray's mute map, as three toggles in the account's own settings. A muted kind is
 * never written — the producer checks before inserting, so the tray stays empty by choice.
 * An untouched kind reads as wanted, which is what the door's map shows.
 */
export function NotificationPreferences() {
  const t = useTranslations("settings");
  const [mutes, setMutes] = useState<Record<string, boolean> | null>(null);
  const [busyKind, setBusyKind] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    browserFetch<NotificationPrefs>("/notifications/preferences")
      .then((result) => {
        if (!cancelled && result.ok) setMutes(result.data.mutes);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  async function toggle(kind: string, wanted: boolean) {
    setBusyKind(kind);
    setError(null);
    const result = await browserFetch<NotificationPrefs>("/notifications/preferences", {
      method: "PUT",
      body: { kind, wanted },
    });
    if (!result.ok) {
      setError(errorMessage(result.error, t("prefsFailed")));
      setBusyKind(null);
      return;
    }
    setMutes(result.data.mutes);
    setBusyKind(null);
  }

  if (!mutes) return null;

  const kinds: { key: string; labelKey: string }[] = [
    { key: "follower", labelKey: "prefsFollower" },
    { key: "comment", labelKey: "prefsComment" },
    { key: "reaction", labelKey: "prefsReaction" },
  ];

  return (
    <div className="stack-sm" data-testid="notification-prefs">
      <p className="muted world-section-note">{t("prefsNote")}</p>
      {kinds.map(({ key, labelKey }) => (
        <label className="check" key={key}>
          <input
            checked={mutes[key] !== false}
            disabled={busyKind === key}
            onChange={(event) => void toggle(key, event.target.checked)}
            type="checkbox"
          />
          <span>{t(labelKey)}</span>
        </label>
      ))}
      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}
    </div>
  );
}
