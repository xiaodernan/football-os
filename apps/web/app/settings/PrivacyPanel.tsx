"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
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
  const t = useTranslations("settings");
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
        setError(errorMessage(result.error, t("previewFailed")));
        return;
      }
      setAccountPreview(result.data);
    });
    return () => {
      cancelled = true;
    };
  }, [mode, router, t]);

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
      setError(errorMessage(result.error, t("exportFailed")));
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
      t("exportSummary", {
        players: payload.players?.length ?? 0,
        sessions: payload.sessions?.length ?? 0,
        events: payload.xp_events?.length ?? 0,
        version: payload.format_version ?? 1,
      }),
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
      setError(errorMessage(result.error, t("deleteFailed")));
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
      setError(errorMessage(result.error, t("accountDeleteFailed")));
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
        <p>{t("exportDescription")}</p>
        <div className="st-actions">
          <button className="btn" type="button" onClick={downloadExport} disabled={busy}>
            {busy ? t("preparingExport") : t("exportData")}
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
        <div className="st-danger__title">{t("deleteAccountHeading")}</div>
        <p>{t("accountDescription")}</p>
        {!accountDeleted ? (
          <>
            {accountPreview ? (
              <div className="st-result">
                <strong>
                  {t("inScope", { rows: accountPreview.deletes.rows_total, assets: accountPreview.deletes.video_assets })}
                </strong>
                {deletedRows.length > 0 && (
                  <span className="muted mono" style={{ fontSize: "0.78rem" }}>
                    {deletedRows.map(([table, count]) => `${table}: ${count}`).join(" · ")}
                  </span>
                )}
                {accountPreview.organizations_left.length > 0 && (
                  <span>{t("tenantsKept", { count: accountPreview.organizations_left.length })}</span>
                )}
              </div>
            ) : (
              <div className="notice st-result">{t("readingInventory")}</div>
            )}
            {blocking.length > 0 && (
              <div className="notice notice--warn st-result">
                <strong>{t("tenantBlocks")}</strong>
                <span>
                  {t(
                    "blockedBy",
                    { names: blocking.map((row) => `${row.name} (${row.slug})`).join(", ") },
                  )}
                </span>
              </div>
            )}
            <div className="field">
              <label className="field__label" htmlFor="st-account-password">
                {t("currentPassword")}
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
                {t("typeConfirm", { word: CONFIRM_WORD })}
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
              <span className="field__hint">{t("confirmHint")}</span>
            </div>
            <div className="st-confirm">
              <button
                className="btn btn--danger"
                type="button"
                onClick={deleteAccount}
                disabled={!accountPreview?.can_delete || confirmText !== CONFIRM_WORD || !accountPassword || busy}
              >
                {busy ? t("deletingAccount") : t("deleteAccountTitle")}
              </button>
            </div>
          </>
        ) : (
          <div className="notice st-result">
            <strong>{t("rowsErased", { rows: accountDeleted.rows_erased, files: accountDeleted.files_removed })}</strong>
            <span>{accountDeleted.message}</span>
            <span className="muted mono" style={{ fontSize: "0.78rem" }}>
              identity_retained={String(accountDeleted.identity_retained)}
            </span>
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              {t("returningSignedOut")}
            </span>
          </div>
        )}
        {error && <div className="notice notice--warn st-result">{error}</div>}
      </div>
    );
  }

  return (
    <div className="st-danger">
      <div className="st-danger__title">{t("deletePlayerHeading")}</div>
      <p>
        {t.rich("playerDescription", {
          strong: (chunks) => <strong>{chunks}</strong>,
        })}
      </p>
      {!deleted ? (
        <>
          <div className="field">
            <label className="field__label" htmlFor="st-delete-confirm">
              {t("typeConfirm", { word: CONFIRM_WORD })}
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
            <span className="field__hint">{t("playerConfirmHint")}</span>
          </div>
          <div className="st-confirm">
            <button
              className="btn btn--danger"
              type="button"
              onClick={deletePlayerData}
              disabled={busy || confirmText !== CONFIRM_WORD}
            >
              {busy ? t("deleting") : t("deletePlayerButton")}
            </button>
          </div>
        </>
      ) : (
        <div className="notice st-result">
          <strong>{t("playersDeleted", { count: deleted.deleted_players })}</strong>
          <span>{deleted.message}</span>
          <span className="muted" style={{ fontSize: "0.82rem" }}>
            {t("returningHome")}
          </span>
        </div>
      )}
      {error && <div className="notice notice--warn st-result">{error}</div>}
    </div>
  );
}
