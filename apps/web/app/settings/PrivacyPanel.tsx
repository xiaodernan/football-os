"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { browserFetch, errorMessage } from "@/lib/api";

import "./settings.css";

/**
 * Data rights panel (spec §61).
 *
 * `mode="export"`  → download the raw JSON the API returns for this account.
 * `mode="delete"`  → destructive: remove players, sessions, XP and attribute history.
 */

type ExportPayload = {
  user: { id: string; email: string; display_name: string; role: string; created_at: string };
  players: unknown[];
  sessions: unknown[];
  xp_events: unknown[];
  format_version: number;
};

type DeletePayload = { deleted_players: number; message: string };

type Mode = "export" | "delete";

const CONFIRM_WORD = "DELETE";

export function PrivacyPanel({ mode = "export" }: { mode?: Mode }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportSummary, setExportSummary] = useState<string | null>(null);
  const [confirmText, setConfirmText] = useState("");
  const [deleted, setDeleted] = useState<DeletePayload | null>(null);

  async function downloadExport() {
    setBusy(true);
    setError(null);
    setExportSummary(null);
    const result = await browserFetch<ExportPayload>("/progress/export");
    setBusy(false);
    if (!result.ok) {
      if (result.status === 401) {
        router.push("/login");
        return;
      }
      setError(errorMessage(result.error, "The export request failed."));
      return;
    }
    const payload = result.data;
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "footballos-export.json";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setExportSummary(
      `Downloaded footballos-export.json — ${payload.players?.length ?? 0} player(s), ${
        payload.sessions?.length ?? 0
      } session(s), ${payload.xp_events?.length ?? 0} XP event(s), format v${payload.format_version ?? 1}.`,
    );
  }

  async function deletePlayerData() {
    if (confirmText.trim() !== CONFIRM_WORD || busy) return;
    setBusy(true);
    setError(null);
    const result = await browserFetch<DeletePayload>("/progress/player-data", { method: "DELETE" });
    if (!result.ok) {
      setBusy(false);
      if (result.status === 401) {
        router.push("/login");
        return;
      }
      setError(errorMessage(result.error, "The delete request failed."));
      return;
    }
    setDeleted(result.data);
    setConfirmText("");
    // Show the API's own receipt for a moment, then leave the now-empty progress routes.
    window.setTimeout(() => {
      router.push("/");
      router.refresh();
    }, 3500);
  }

  if (mode === "export") {
    return (
      <div className="st-copy">
        <p>
          Export hands you the raw JSON the API holds for this account: profile fields, players with their attribute
          records, training sessions and XP events. No PDF or report generator exists server-side, so the file is saved
          by your browser.
        </p>
        <div className="st-actions">
          <button className="btn" type="button" onClick={downloadExport} disabled={busy}>
            {busy ? "Preparing export…" : "Export my data"}
          </button>
          <span className="muted mono">footballos-export.json</span>
        </div>
        {exportSummary && <div className="notice st-result">{exportSummary}</div>}
        {error && <div className="notice notice--warn st-result">{error}</div>}
      </div>
    );
  }

  return (
    <div className="st-danger">
      <div className="st-danger__title">Delete my player data</div>
      <p>
        This removes your <strong>players, training sessions, XP events and attribute history</strong>. It keeps the
        account itself (email, role, plan) — account deletion is a separate API action and is not wired into this screen.
      </p>
      {!deleted ? (
        <>
          <div className="field">
            <label className="field__label" htmlFor="st-delete-confirm">
              Type {CONFIRM_WORD} to confirm
            </label>
            <input
              id="st-delete-confirm"
              className="input"
              value={confirmText}
              onChange={(event) => setConfirmText(event.target.value)}
              autoComplete="off"
              spellCheck={false}
              placeholder={CONFIRM_WORD}
            />
            <span className="field__hint">Irreversible on this demo database. The button stays disabled until it matches.</span>
          </div>
          <div className="st-confirm">
            <button
              className="btn btn--danger"
              type="button"
              onClick={deletePlayerData}
              disabled={busy || confirmText !== CONFIRM_WORD}
            >
              {busy ? "Deleting…" : "Delete player data"}
            </button>
          </div>
        </>
      ) : (
        <div className="notice st-result">
          <strong>{deleted.deleted_players} player profile(s) deleted.</strong>
          <span>{deleted.message}</span>
          <span className="muted" style={{ fontSize: "0.82rem" }}>
            Returning to home…
          </span>
        </div>
      )}
      {error && <div className="notice notice--warn st-result">{error}</div>}
    </div>
  );
}
