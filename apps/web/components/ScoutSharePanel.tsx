"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Panel } from "@/components/ui";
import { browserFetch, errorMessage } from "@/lib/api";
import type { ApiError } from "@/lib/types";
import type { ReportView, ScoutShareLedger, ScoutShareRecord } from "@/lib/scout";

type Props = { asked: ReportView["asked_for"] | null };

type Busy = "load" | "open" | "revoke" | null;

function publicPath(token: string): string {
  return `/scout/shared/${encodeURIComponent(token)}`;
}

function shortToken(token: string | null): string {
  if (!token) return "—";
  return `${token.slice(0, 8)}...${token.slice(-6)}`;
}

/**
 * §24's public link control.
 *
 * The question comes from the report above rather than from a form here: a link is minted over the exact player,
 * role, career, comparator and round that produced the report a reader is looking at, so a page can never advertise
 * a question nobody asked. The server owns the token and the ledger; every write is followed by a read of
 * `/scout/shares`, so the table below shows the rows the API now holds rather than the body a successful press
 * happened to return.
 *
 * A closed row keeps its question and loses its token — a dead key is not printed for a reader to try. Each live
 * token is also a link to the public page, and each live row can be closed from here, because a ledger that could
 * only revoke its newest link would be a ledger with a blind spot.
 */
export function ScoutSharePanel({ asked }: Props) {
  const ts = useTranslations("scout");
  const [ledger, setLedger] = useState<ScoutShareLedger | null>(null);
  const [fault, setFault] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState<Busy>(null);
  const [copied, setCopied] = useState("");

  const load = useCallback(async () => {
    setBusy("load");
    const result = await browserFetch<ScoutShareLedger>("/scout/shares");
    if (result.ok) {
      setLedger(result.data);
      setFault(null);
    } else {
      setFault(result.error);
    }
    setBusy(null);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const live = ledger?.shares.find((row) => row.live) ?? null;
  const figures = fault?.details && typeof fault.details === "object" ? JSON.stringify(fault.details) : "";

  async function openLink() {
    if (!asked) return;
    setBusy("open");
    const result = await browserFetch<ScoutShareRecord>("/scout/share", {
      method: "POST",
      body: {
        player: asked.player,
        role: asked.role,
        career: asked.career,
        compare_to: asked.compare_to,
        round_index: asked.round_index,
      },
    });
    if (!result.ok) {
      setFault(result.error);
      setBusy(null);
      return;
    }
    setCopied("");
    await load();
  }

  async function closeLink(token: string) {
    setBusy("revoke");
    const result = await browserFetch<ScoutShareRecord>(`/scout/share/${encodeURIComponent(token)}`, { method: "DELETE" });
    if (!result.ok) {
      setFault(result.error);
      setBusy(null);
      return;
    }
    setCopied("");
    await load();
  }

  async function copyLink(token: string) {
    const url = `${window.location.origin}${publicPath(token)}`;
    try {
      await navigator.clipboard.writeText(url);
    } finally {
      setCopied(url);
    }
  }

  return (
    <Panel
      eyebrow={ts("shareEyebrow", {
        live: ledger?.counts.live ?? 0,
        closed: ledger?.counts.revoked ?? 0,
        max: ledger?.max_live ?? 0,
      })}
      title={ts("shareTitle")}
    >
      <div className="stack-sm" data-scout-share-panel>
        <p className="muted" style={{ fontSize: "0.86rem" }}>
          {ts("shareReadsLive")}
        </p>

        {fault && (
          <p className="notice notice--warn" data-scout-share-fault>
            <strong>{fault.code ?? "error"}</strong> — {errorMessage(fault, ts("requestFailed"))}
            {figures ? <span className="mono"> {figures}</span> : null}
          </p>
        )}

        {!asked && <p className="notice" data-scout-share-needs-report>{ts("shareNeedsReport")}</p>}

        {asked && (
          <div className="row wrap" style={{ gap: "0.55rem" }}>
            <button className="btn btn--primary" data-scout-share-open disabled={busy !== null} onClick={() => void openLink()} type="button">
              {busy === "open" ? ts("shareOpening") : ts("shareOpen")}
            </button>
            {live?.token && (
              <>
                <Link className="btn" data-scout-share-view href={publicPath(live.token)} rel="noreferrer" target="_blank">
                  {ts("shareView")}
                </Link>
                <button className="btn" data-scout-share-copy disabled={busy !== null} onClick={() => void copyLink(live.token as string)} type="button">
                  {ts("shareCopy")}
                </button>
              </>
            )}
          </div>
        )}

        {copied && (
          <p className="muted mono" data-scout-share-copied={copied} style={{ fontSize: "0.82rem" }}>
            {ts("shareLinkReady", { value: copied })}
          </p>
        )}

        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{ts("shareThState")}</th>
                <th scope="col">{ts("shareThToken")}</th>
                <th scope="col">{ts("thPlayer")}</th>
                <th scope="col">{ts("shareThRole")}</th>
                <th scope="col">{ts("shareThCareer")}</th>
                <th scope="col">{ts("shareThOpened")}</th>
                <th scope="col">{ts("shareThClosed")}</th>
              </tr>
            </thead>
            <tbody>
              {(ledger?.shares ?? []).map((row) => (
                <tr data-scout-share-row={row.share} key={row.share}>
                  <td>
                    <span className={row.live ? "badge badge--live" : "badge"}>{row.live ? ts("shareLiveBadge") : ts("shareClosedBadge")}</span>
                    {row.live && row.token && (
                      <button className="btn btn--danger" data-scout-share-revoke={row.share} disabled={busy !== null} onClick={() => void closeLink(row.token as string)} type="button">
                        {ts("shareRevoke")}
                      </button>
                    )}
                  </td>
                  <td className="mono">
                    {row.live && row.token ? (
                      <Link href={publicPath(row.token)} rel="noreferrer" target="_blank">
                        {shortToken(row.token)}
                      </Link>
                    ) : (
                      shortToken(null)
                    )}
                  </td>
                  <td className="mono">{row.player}</td>
                  <td className="mono">{row.role ?? "—"}</td>
                  <td className="mono">{row.career ?? "—"}</td>
                  <td className="muted mono">{row.opened_at?.slice(0, 16) ?? "—"}</td>
                  <td className="muted mono">{row.revoked_at?.slice(0, 16) ?? "—"}</td>
                </tr>
              ))}
              {ledger !== null && ledger.shares.length === 0 && (
                <tr>
                  <td className="muted" colSpan={7} data-scout-share-none>
                    {ts("shareNone")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Panel>
  );
}
