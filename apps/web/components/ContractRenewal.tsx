"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { browserFetch, errorMessage } from "@/lib/api";
import type { CareerContractRenewal } from "@/lib/types";

const money = (value: number) => value.toLocaleString("en-GB");

/**
 * The renewal quote on one held deal (M13 Phase 7 item 26).
 *
 * The figures are the contract book's own `renewal` block: fee, new wage, the bill after replacing the
 * old wage and the board's ceiling. The button posts the player and the quoted years; the page is then
 * re-read, so the expiry column and the ledger show what the server stored rather than what this
 * component hoped it would store.
 */
export function ContractRenewal({
  ident,
  player,
  playerName,
  quote,
}: {
  ident: string;
  player: string;
  playerName: string;
  quote: CareerContractRenewal | null;
}) {
  const t = useTranslations("careerDetail");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [refused, setRefused] = useState<string | null>(null);
  const [wage, setWage] = useState<number | null>(null);

  if (!quote) return <span className="muted">—</span>;

  const offer = quote;
  const offeredWage = wage ?? quote.weekly_wage;
  const blocked = !quote.can_renew;
  const reason = !quote.fee_affordable
    ? t("renewalFeeShort", { fee: `${money(quote.fee)} ${quote.fee_units}`, balance: `${money(quote.balance_after_fee + quote.fee)} ${quote.fee_units}` })
    : t("renewalWageShort", {
        bill: `${money(quote.wage_bill_after)} ${quote.fee_units}`,
        ceiling: `${money(quote.wage_ceiling)} ${quote.fee_units}`,
      });

  async function run() {
    setBusy(true);
    setAnswer(null);
    setRefused(null);
    const result = await browserFetch<{ detail?: { expiry_round?: number } }>(`/transfers/${encodeURIComponent(ident)}/renew`, {
      method: "POST",
      body: { player, years: offer.years, wage: offeredWage },
    });
    if (!result.ok) {
      setRefused(`${result.error.code} — ${errorMessage(result.error, tCommon("requestFailed"))}`);
      setBusy(false);
      return;
    }
    const round = result.data?.detail?.expiry_round;
    setAnswer(typeof round === "number" ? t("renewedTo", { round }) : t("renewed"));
    router.refresh();
    setBusy(false);
  }

  return (
    <div className="stack-sm">
      <p className="muted">
        {t("renewalOffer", {
          years: quote.years,
          fee: `${money(quote.fee)} ${quote.fee_units}`,
          wage: `${money(quote.weekly_wage)} ${quote.fee_units}`,
        })}
      </p>
      <label className="muted" htmlFor={`renew-wage-${player}`}>
        {t("renewalWageLabel")}
      </label>
      <input
        id={`renew-wage-${player}`}
        className="input"
        type="number"
        min={5}
        step={5}
        value={offeredWage}
        onChange={(event) => setWage(Number(event.target.value))}
      />
      {blocked ? (
        <p className="muted">{t("renewalBlocked", { reason })}</p>
      ) : (
        <button className="button button--ghost" type="button" onClick={run} disabled={busy} aria-label={t("renewAria", { player: playerName })}>
          {busy ? t("renewing") : t("renewButton")}
        </button>
      )}
      {answer ? <p className="notice">{answer}</p> : null}
      {refused ? <p className="notice notice--warn">{refused}</p> : null}
    </div>
  );
}
