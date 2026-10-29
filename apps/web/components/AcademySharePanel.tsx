"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Panel } from "@/components/ui";
import { browserFetch, errorMessage } from "@/lib/api";
import type { AcademyShareLedger, AcademyShareMinted, AcademyShareRecord } from "@/lib/club";
import type { ApiError } from "@/lib/types";

type Props = { ident: string; plan: string };

type Busy = "load" | "open" | "revoke" | null;

function publicPath(token: string): string {
  return `/academy/shared/${encodeURIComponent(token)}`;
}

function shortToken(token: string | null): string {
  if (!token) return "—";
  return `${token.slice(0, 8)}...${token.slice(-6)}`;
}

/**
 * §40's public plan link control, on the plan it is about.
 *
 * A link is minted over *this* plan — the one the reader is looking at — rather than from a question typed here,
 * so a page cannot advertise a plan that does not exist. A link over a minor's plan is refused until a granted
 * `plan` consent names that child; the refusal is the API's and is printed with its figures.
 *
 * Every write is followed by a read of `/club/academy/shares`, so the table shows the rows the API now holds
 * rather than the body a successful press happened to return. A closed row keeps its plan and child and loses its
 * token: a dead key is not printed for a reader to try.
 */
export function AcademySharePanel({ ident, plan }: Props) {
  const ts = useTranslations("club");
  const [ledger, setLedger] = useState<AcademyShareLedger | null>(null);
  const [fault, setFault] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState<Busy>(null);
  const [copied, setCopied] = useState("");

  const load = useCallback(async () => {
    setBusy("load");
    const result = await browserFetch<AcademyShareLedger>("/club/academy/shares");
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

  const live = ledger?.shares.find((row) => row.live && row.plan === plan) ?? null;
  const figures = fault?.details && typeof fault.details === "object" ? JSON.stringify(fault.details) : "";

  async function openLink() {
    setBusy("open");
    const result = await browserFetch<AcademyShareMinted>(`/club/academy/${encodeURIComponent(ident)}/plans/${encodeURIComponent(plan)}/share`, { method: "POST" });
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
    const result = await browserFetch<AcademyShareRecord>(`/club/academy/shares/${encodeURIComponent(token)}`, { method: "DELETE" });
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
      await navigator.clipboard?.writeText(url);
    } catch {
      // A denied clipboard is not a failed action: the URL printed below is the fallback, selectable by hand.
    } finally {
      setCopied(url);
    }
  }

  return (
    <Panel
      eyebrow={ts("sharePlanEyebrow", {
        live: ledger?.counts.live ?? 0,
        closed: ledger?.counts.revoked ?? 0,
        max: ledger?.max_live ?? 0,
      })}
      title={ts("sharePlanTitle")}
    >
      <div className="stack-sm" data-academy-share-panel>
        <p className="muted" style={{ fontSize: "0.86rem" }}>
          {ts("sharePlanReadsLive")}
        </p>

        {fault && (
          <p className="notice notice--warn" data-academy-share-fault>
            <strong>{fault.code ?? "error"}</strong> — {errorMessage(fault, ts("requestFailed"))}
            {figures ? <span className="mono"> {figures}</span> : null}
          </p>
        )}

        <div className="row wrap" style={{ gap: "0.55rem" }}>
          <button className="btn btn--primary" data-academy-share-open disabled={busy !== null} onClick={() => void openLink()} type="button">
            {busy === "open" ? ts("sharePlanOpening") : ts("sharePlanOpen")}
          </button>
          {live?.token && (
            <>
              <Link className="btn" data-academy-share-view href={publicPath(live.token)} rel="noreferrer" target="_blank">
                {ts("sharePlanView")}
              </Link>
              <button className="btn" data-academy-share-copy disabled={busy !== null} onClick={() => void copyLink(live.token as string)} type="button">
                {ts("sharePlanCopy")}
              </button>
            </>
          )}
        </div>

        {copied && (
          <p className="muted mono" data-academy-share-copied={copied} style={{ fontSize: "0.82rem" }}>
            {ts("sharePlanLinkReady", { value: copied })}
          </p>
        )}

        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{ts("sharePlanThState")}</th>
                <th scope="col">{ts("sharePlanThToken")}</th>
                <th scope="col">{ts("sharePlanThPlan")}</th>
                <th scope="col">{ts("sharePlanThChild")}</th>
                <th scope="col">{ts("sharePlanThOpened")}</th>
                <th scope="col">{ts("sharePlanThClosed")}</th>
              </tr>
            </thead>
            <tbody>
              {(ledger?.shares ?? []).map((row) => (
                <tr data-academy-share-row={row.share} key={row.share}>
                  <td>
                    <span className={row.live ? "badge badge--live" : "badge"}>{row.live ? ts("sharePlanLive") : ts("sharePlanClosed")}</span>
                    {row.live && row.token && (
                      <button className="btn btn--danger" data-academy-share-revoke={row.share} disabled={busy !== null} onClick={() => void closeLink(row.token as string)} type="button">
                        {ts("sharePlanRevoke")}
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
                  <td className="mono">{row.plan}</td>
                  <td className="mono">{row.player?.slug ?? "—"}</td>
                  <td className="muted mono">{row.opened_at?.slice(0, 16) ?? "—"}</td>
                  <td className="muted mono">{row.revoked_at?.slice(0, 16) ?? "—"}</td>
                </tr>
              ))}
              {ledger !== null && ledger.shares.length === 0 && (
                <tr>
                  <td className="muted" colSpan={6} data-academy-share-none>
                    {ts("sharePlanNone")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {ledger?.rule && (
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            {ledger.rule}
          </p>
        )}
      </div>
    </Panel>
  );
}
