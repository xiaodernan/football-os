"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { browserFetch } from "@/lib/api";

type OptState = { me: { visible: boolean }; leaders: unknown[]; leaders_visible: number };

/**
 * The opt-in button, posted as JSON to the same door the page reads. Visibility is the
 * account's own choice: nothing else changes when this flips — the page keeps working either way.
 */
export function LeaderboardToggle({ me }: { me: { visible: boolean } }) {
  const t = useTranslations("leaderboard");
  const [visible, setVisible] = useState(me.visible);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  async function toggle() {
    setBusy(true);
    setFailed(false);
    const next = !visible;
    const result = await browserFetch<{ leaderboard_visible: boolean }>("/leaderboard", {
      method: "POST",
      body: { enabled: next },
    });
    if (result.ok) {
      setVisible(result.data.leaderboard_visible);
    } else {
      setFailed(true);
    }
    setBusy(false);
  }

  return (
    <div className="notice notice--info">
      <p>{visible ? t("meNoteOptedIn") : t("meNoteOptedOut")}</p>
      <div className="row" style={{ marginTop: "0.6rem", gap: "0.5rem" }}>
        <button className="btn" type="button" disabled={busy} onClick={() => void toggle()}>
          {busy ? t("optWorking") : visible ? t("optOut") : t("optIn")}
        </button>
        {failed && <span className="muted">{t("requestFailed")}</span>}
      </div>
    </div>
  );
}
