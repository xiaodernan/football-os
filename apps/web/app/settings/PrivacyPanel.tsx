"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { browserFetch, errorMessage } from "@/lib/api";

import "./settings.css";

/**
 * Data rights panel (spec §61).
 *
 * `mode="export"`  → download the raw JSON the API returns for this account.
 * `mode="delete"`  → destructive: remove players, sessions, XP and attribute history.
 * `mode="account"` → destructive: erase the account, its private media and its owned data.
 */

type ExportPayload = {
  user: { id: string; email: string; display_name: string; role: string; created_at: string };
  players: unknown[];
  sessions: unknown[];
  xp_events: unknown[];
  format_version: number;
};

type DeletePayload = { deleted_players: number; message: string };

type OrganizationRow = { slug: string; name: string; other_active_members?: number; other_active_owners?: number; reason?: string };

type AccountPreview = {
  can_delete: boolean;
  confirmation: { phrase: string; password_required: boolean };
  deletes: {
    rows: Record<string, number>;
    rows_total: number;
    video_assets: number;
    video_bytes: number;
    organizations: OrganizationRow[];
  };
  retained_anonymized: { rows: Record<string, number>; identity_removed: boolean; basis: string };
  organizations_left: OrganizationRow[];
  blocking_organizations: OrganizationRow[];
};

type AccountDeletePayload = {
  deleted: boolean;
  rows_erased: number;
  video_assets_erased: number;
  files_removed: number;
  bytes_removed: number;
  organizations_deleted: string[];
  organizations_left: string[];
  identity_retained: boolean;
  message: string;
};

type Mode = "export" | "delete" | "account";

const CONFIRM_WORD = "DELETE";

export function PrivacyPanel({ mode = "export" }: { mode?: Mode }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportSummary, setExportSummary] = useState<string | null>(null);
  const [confirmText, setConfirmText] = useState("");
  const [deleted, setDeleted] = useState<DeletePayload | null>(null);
  const [accountPreview, setAccountPreview] = useState<AccountPreview | null>(null);
  const [accountPassword, setAccountPassword] = useState("");
  const [accountDeleted, setAccountDeleted] = useState<AccountDeletePayload | null>(null);

  useEffect(() => {
    if (mode !== "account") return;
    let cancelled = false;
    browserFetch<AccountPreview>("/auth/account").then((result) => {
      if (cancelled) return;
      if (!result.ok) {
        if (result.status === 401) {
          router.push("/login");
          return;
        }
        setError(errorMessage(result.error, "The deletion preview failed."));
        return;
      }
      setAccountPreview(result.data);
    });
    return () => {
      cancelled = true;
    };
  }, [mode, router]);

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

  async function deleteAccount() {
    if (!accountPreview?.can_delete || confirmText.trim() !== CONFIRM_WORD || !accountPassword || busy) return;
    setBusy(true);
    setError(null);
    const result = await browserFetch<AccountDeletePayload>("/auth/account", {
      method: "DELETE",
      body: { confirm: CONFIRM_WORD, password: accountPassword },
    });
    if (!result.ok) {
      setBusy(false);
      if (result.status === 401) {
        router.push("/login");
        return;
      }
      setError(errorMessage(result.error, "The account deletion failed."));
      return;
    }
    setAccountDeleted(result.data);
    setAccountPassword("");
    setConfirmText("");
    window.setTimeout(() => {
      router.replace("/");
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

  if (mode === "account") {
    const blocking = accountPreview?.blocking_organizations ?? [];
    const deletedRows = Object.entries(accountPreview?.deletes.rows ?? {}).filter(([, count]) => count > 0);
    return (
      <div className="st-danger">
        <div className="st-danger__title">Delete my entire account</div>
        <p>
          This removes the account, its player and training records, AI history, boards, simulations, community
          posts, shares and uploaded video originals and frames. Tenant records remain only when another active
          owner still holds the tenant. Audit records stay as aggregate actions with no account id.
        </p>
        {!accountDeleted ? (
          <>
            {accountPreview ? (
              <div className="st-result">
                <strong>{accountPreview.deletes.rows_total} account-linked row(s) and {accountPreview.deletes.video_assets} video asset(s) are in scope.</strong>
                {deletedRows.length > 0 && (
                  <span className="muted mono" style={{ fontSize: "0.78rem" }}>
                    {deletedRows.map(([table, count]) => `${table}: ${count}`).join(" · ")}
                  </span>
                )}
                {accountPreview.organizations_left.length > 0 && (
                  <span>
                    {accountPreview.organizations_left.length} tenant(s) keep their rows because another active owner remains.
                  </span>
                )}
              </div>
            ) : (
              <div className="notice st-result">Reading the deletion inventory…</div>
            )}
            {blocking.length > 0 && (
              <div className="notice notice--warn st-result">
                <strong>Tenant ownership blocks deletion.</strong>
                <span>
                  {blocking.map((row) => `${row.name} (${row.slug})`).join(", ")} would be left without an owner.
                  Delete the tenant or transfer ownership first.
                </span>
              </div>
            )}
            <div className="field">
              <label className="field__label" htmlFor="st-account-password">
                Current password
              </label>
              <input
                id="st-account-password"
                className="input"
                type="password"
                value={accountPassword}
                onChange={(event) => setAccountPassword(event.target.value)}
                autoComplete="current-password"
              />
            </div>
            <div className="field">
              <label className="field__label" htmlFor="st-account-confirm">
                Type {CONFIRM_WORD} to confirm
              </label>
              <input
                id="st-account-confirm"
                className="input"
                value={confirmText}
                onChange={(event) => setConfirmText(event.target.value)}
                autoComplete="off"
                spellCheck={false}
                placeholder={CONFIRM_WORD}
              />
              <span className="field__hint">The password and phrase are both required. Nothing is removed if either is wrong.</span>
            </div>
            <div className="st-confirm">
              <button
                className="btn btn--danger"
                type="button"
                onClick={deleteAccount}
                disabled={!accountPreview?.can_delete || confirmText !== CONFIRM_WORD || !accountPassword || busy}
              >
                {busy ? "Deleting account…" : "Delete account permanently"}
              </button>
            </div>
          </>
        ) : (
          <div className="notice st-result">
            <strong>{accountDeleted.rows_erased} row(s) erased; {accountDeleted.files_removed} private file(s) removed.</strong>
            <span>{accountDeleted.message}</span>
            <span className="muted mono" style={{ fontSize: "0.78rem" }}>
              identity_retained={String(accountDeleted.identity_retained)}
            </span>
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              Returning to the signed-out home page…
            </span>
          </div>
        )}
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
