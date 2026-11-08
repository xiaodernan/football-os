"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Panel } from "@/components/ui";
import { KeyValueGrid } from "@/components/world";
import { browserFetch, errorMessage } from "@/lib/api";
import type { CareerTickets } from "@/lib/types";

const money = (value: number) => value.toLocaleString("en-GB");

/**
 * The career's gate price (M13 Phase 10 item 44).
 *
 * One number trades a crowd against a price per head: the panel prints the setting, the demand it
 * draws and the revenue it indexes against a neutral price, then posts the chosen step to
 * `/careers/{slug}/tickets` and re-reads the page. The arithmetic is the API's; this component only
 * states which step the manager picked and whether it is one of the published steps.
 */
export function CareerTicketsPanel({
  ident,
  view,
  limitation,
}: {
  ident: string;
  view: CareerTickets;
  limitation: string;
}) {
  const t = useTranslations("careerDetail");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [price, setPrice] = useState(view.price_pct);
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const offStep =
    !Number.isFinite(price) || price < view.min_pct || price > view.max_pct || price % view.step_pct !== 0;

  async function apply() {
    setBusy(true);
    setAnswer(null);
    setError(null);
    const result = await browserFetch<{ priced: boolean; tickets: CareerTickets }>(
      `/careers/${encodeURIComponent(ident)}/tickets`,
      { method: "PUT", body: { price_pct: price } },
    );
    if (!result.ok) {
      setError(`${result.error.code} — ${errorMessage(result.error, tCommon("requestFailed"))}`);
      setBusy(false);
      return;
    }
    setAnswer(
      t("ticketApplied", {
        price: result.data.tickets.price_pct,
        demand: result.data.tickets.demand_pct,
        revenue: result.data.tickets.revenue_index,
      }),
    );
    router.refresh();
    setBusy(false);
  }

  return (
    <Panel eyebrow={t("ticketEyebrow", { price: view.price_pct })} title={t("ticketTitle")}>
      <div className="stack-sm">
        <p className="muted">{t("ticketIntro")}</p>

        {!view.available ? (
          <div className="empty">
            <strong>{t("ticketNoGateTitle")}</strong>
            <p className="muted">{view.reason ?? t("ticketNoGateBody")}</p>
          </div>
        ) : (
          <>
            <KeyValueGrid
              rows={[
                [t("ticketKvPrice"), `${view.price_pct}%`],
                [t("ticketKvBase"), `${money(view.base_price)} ${view.price_units}${t("ticketPerSeat")}`],
                [t("ticketKvDemand"), `${view.demand_pct}%`],
                [t("ticketKvRevenue"), `${view.revenue_index}`],
                [t("ticketKvBest"), `${view.best_price_pct}% → ${view.best_revenue_index}`],
                [
                  t("ticketKvBounds"),
                  t("ticketBoundsValue", { min: view.min_pct, max: view.max_pct, step: view.step_pct }),
                ],
              ]}
            />

            <div className="stack-sm">
              <label className="muted" htmlFor="ticket-price">
                {t("ticketPriceLabel")}
              </label>
              <input
                id="ticket-price"
                className="input"
                type="number"
                min={view.min_pct}
                max={view.max_pct}
                step={view.step_pct}
                value={price}
                onChange={(event) => setPrice(Number(event.target.value))}
              />
              {offStep ? (
                <p className="notice notice--warn">
                  {t("ticketOffStep", { min: view.min_pct, max: view.max_pct, step: view.step_pct })}
                </p>
              ) : null}
              <button className="button button--ghost" type="button" onClick={apply} disabled={busy || offStep}>
                {busy ? t("ticketSaving") : t("ticketButton")}
              </button>
              {answer ? <p className="notice">{answer}</p> : null}
              {error ? <p className="notice notice--warn">{error}</p> : null}
            </div>
          </>
        )}

        <p className="muted">{view.note}</p>
        <p className="mono muted">
          {t("ticketFormulaLabel")}: {view.formula}
        </p>
        <p className="notice notice--warn">{limitation}</p>
      </div>
    </Panel>
  );
}
