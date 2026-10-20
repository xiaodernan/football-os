"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { CallNote, useClubCall } from "@/components/ClubTools";
import { Panel } from "@/components/ui";
import { browserFetch } from "@/lib/api";
import type { PortfolioRules, PortfolioShareLedger, PortfolioShareRecord } from "@/lib/portfolio";

type Props = {
  rules: PortfolioRules;
  initialLedger: PortfolioShareLedger | null;
  initialFault?: string;
};

function publicPath(token: string): string {
  return `/portfolio/shared/${encodeURIComponent(token)}`;
}

function shortToken(token: string | null): string {
  if (!token) return "closed";
  return `${token.slice(0, 8)}...${token.slice(-6)}`;
}

/**
 * §38's public link control.
 *
 * The server owns the ledger; this component never invents a token or a section count. Every write is followed by
 * a read of `/portfolio/shares`, so the table below the form shows the rows the API now holds rather than the
 * response body a successful press happened to return.
 */
export function PortfolioSharePanel({ rules, initialLedger, initialFault = "" }: Props) {
  const t = useTranslations("common");
  const td = useTranslations("portfolio");
  const { busy, call, note } = useClubCall();
  const [ledger, setLedger] = useState<PortfolioShareLedger | null>(initialLedger);
  const [fault, setFault] = useState(initialFault);
  const [selected, setSelected] = useState<string[]>(
    initialLedger?.shares.find((row) => row.live)?.sections ?? rules.share.publishable.filter((key) => !rules.share.minor_blocked.includes(key)),
  );
  const [copied, setCopied] = useState("");

  const live = ledger?.shares.find((row) => row.live) ?? null;
  const liveId = live?.share ?? null;
  const titleByKey = Object.fromEntries(rules.sections.map((row) => [row.section, row.title]));

  const loadLedger = useCallback(async () => {
    const result = await browserFetch<PortfolioShareLedger>("/portfolio/shares");
    if (result.ok) {
      setLedger(result.data);
      setFault("");
      return result.data;
    }
    setFault(`${result.error.code}: ${result.error.message}`);
    return null;
  }, []);

  useEffect(() => {
    if (!initialLedger) void loadLedger();
  }, [initialLedger, loadLedger]);

  useEffect(() => {
    if (liveId && live) setSelected(live.sections);
  }, [liveId, live]);

  function toggle(section: string) {
    setSelected((current) => (current.includes(section) ? current.filter((key) => key !== section) : [...current, section]));
  }

  async function openLink() {
    const result = await call("open", "/portfolio/share", { body: { sections: selected } });
    if (result) {
      await loadLedger();
      setCopied("");
    }
  }

  async function closeLink(token: string) {
    const result = await call("revoke", `/portfolio/share/${encodeURIComponent(token)}`, { method: "DELETE" });
    if (result) {
      await loadLedger();
      setCopied("");
    }
  }

  async function copyLink(token: string) {
    const url = `${window.location.origin}${publicPath(token)}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(url);
    } catch {
      setCopied(url);
    }
  }

  return (
    <Panel
      eyebrow={`${ledger?.counts.live ?? 0} live · ${ledger?.counts.revoked ?? 0} closed · ${rules.share.minor_age} is the age at which the videos rule changes`}
      title={td("publicLinkTitle")}
    >
      <div className="stack-sm" data-portfolio-share-panel>
        <p className="muted" style={{ fontSize: "0.86rem" }}>
          {td("linkReadsLive")}
        </p>

        {fault && (
          <div className="notice notice--warn" data-portfolio-share-read-fault>
            <p style={{ margin: 0 }}>{fault}</p>
          </div>
        )}

        <fieldset className="stack-sm" disabled={busy !== null} style={{ border: 0, margin: 0, padding: 0 }}>
          <legend className="eyebrow">{td("publishableSections")}</legend>
          <div className="grid grid-3" data-portfolio-share-sections>
            {rules.share.publishable.map((section) => {
              const blockedForMinor = rules.share.minor_blocked.includes(section);
              return (
                <label className="field" key={section} style={{ cursor: "pointer" }}>
                  <span className="row wrap" style={{ alignItems: "center", gap: "0.45rem" }}>
                    <input
                      checked={selected.includes(section)}
                      data-portfolio-share-section={section}
                      onChange={() => toggle(section)}
                      type="checkbox"
                    />
                    <span>{titleByKey[section] ?? section}</span>
                  </span>
                  <span className="muted mono" style={{ fontSize: "0.76rem" }}>
                    {section}{blockedForMinor ? " · blocked on a minor's link" : ""}
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>

        <div className="row wrap" style={{ gap: "0.55rem" }}>
          <button className="btn btn--primary" data-portfolio-share-open disabled={busy !== null} onClick={() => void openLink()} type="button">
            {busy === "open" ? "Opening..." : live ? "Update public link" : "Open public link"}
          </button>
          {live?.token && (
            <>
              <Link className="btn" data-portfolio-share-view href={publicPath(live.token)} rel="noreferrer" target="_blank">
                {td("viewPublicPage", { view: t("view") })}
              </Link>
              <button className="btn" data-portfolio-share-copy disabled={busy !== null} onClick={() => void copyLink(live.token as string)} type="button">
                {td("copyLink")}
              </button>
              <button className="btn btn--danger" data-portfolio-share-revoke disabled={busy !== null} onClick={() => void closeLink(live.token as string)} type="button">
                {busy === "revoke" ? `${t("close")}…` : `${t("close")} link`}
              </button>
            </>
          )}
        </div>

        {copied && (
          <p className="muted mono" data-portfolio-share-copied={copied} style={{ fontSize: "0.82rem" }}>
            {td("linkReady", { value: copied })}
          </p>
        )}

        <CallNote note={note} />

        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{td("thState")}</th>
                <th scope="col">{td("thToken")}</th>
                <th scope="col">{td("thSections")}</th>
                <th scope="col">{td("thOpened")}</th>
                <th scope="col">{td("thClosed")}</th>
              </tr>
            </thead>
            <tbody>
              {(ledger?.shares ?? []).map((row: PortfolioShareRecord) => (
                <tr data-portfolio-share-row={row.share} key={row.share}>
                  <td>
                    <span className={row.live ? "badge badge--live" : "badge"}>
                      {row.live ? td("linkLive") : td("linkClosed")}
                    </span>
                  </td>
                  <td className="mono">{shortToken(row.token)}</td>
                  <td className="mono">{row.sections.join(", ") || td("noSections")}</td>
                  <td className="muted mono">{row.opened_at?.slice(0, 16) ?? td("unknownTime")}</td>
                  <td className="muted mono">{row.revoked_at?.slice(0, 16) ?? "-"}</td>
                </tr>
              ))}
              {(ledger?.shares ?? []).length === 0 && (
                <tr>
                  <td className="muted" colSpan={5}>{td("noPublicLink")}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Panel>
  );
}
