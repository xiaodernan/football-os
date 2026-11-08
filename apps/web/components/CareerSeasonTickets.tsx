"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Panel } from "@/components/ui";
import { KeyValueGrid } from "@/components/world";
import { browserFetch, errorMessage } from "@/lib/api";
import type { CareerSeasonTickets, CareerSeasonTicketSale } from "@/lib/types";

const money = (value: number) => value.toLocaleString("en-GB");

/**
 * Season tickets (M13 Phase 10 item 46).
 *
 * The gate sells one crowd. This panel sells the same seat for every home league round before the
 * season starts, at a discount, and the seats it sells are then in the ground without being charged
 * again. The offer, the price and the block bounds are the API's; this component states the number
 * the manager picked and posts it to `/careers/{slug}/season-tickets`.
 */
export function CareerSeasonTicketsPanel({
  ident,
  view,
  limitation,
}: {
  ident: string;
  view: CareerSeasonTickets;
  limitation: string;
}) {
  const t = useTranslations("careerDetail");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [seats, setSeats] = useState(view.min_seats);
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const offBlock =
    !Number.isFinite(seats) ||
    seats < view.min_seats ||
    seats > view.max_seats ||
    seats % view.min_seats !== 0;

  async function sell() {
    setBusy(true);
    setAnswer(null);
    setError(null);
    const result = await browserFetch<{
      sold: boolean;
      sale: CareerSeasonTicketSale;
      season_tickets: CareerSeasonTickets;
    }>(`/careers/${encodeURIComponent(ident)}/season-tickets`, {
      method: "POST",
      body: { seats },
    });
    if (!result.ok) {
      setError(`${result.error.code} — ${errorMessage(result.error, tCommon("requestFailed"))}`);
      setBusy(false);
      return;
    }
    setAnswer(
      t("seasonTicketsSold", {
        seats: result.data.sale.seats,
        amount: money(result.data.sale.amount),
        units: result.data.sale.amount_units,
      }),
    );
    router.refresh();
    setBusy(false);
  }

  return (
    <Panel
      eyebrow={t("seasonTicketsEyebrow", { season: view.season, income: money(view.income) })}
      title={t("seasonTicketsTitle")}
    >
      <div className="stack-sm">
        <p className="muted">{t("seasonTicketsIntro")}</p>

        <KeyValueGrid
          rows={[
            [t("seasonTicketsKvSeason"), view.season],
            [
              t("seasonTicketsKvWindow"),
              t("seasonTicketsWindowValue", { round: view.first_round }),
            ],
            [t("seasonTicketsKvHomeRounds"), String(view.home_rounds)],
            [
              t("seasonTicketsKvPrice"),
              t("seasonTicketsPriceValue", {
                unit: money(view.unit_price),
                full: money(view.full_price),
                discount: view.discount_pct,
                units: view.price_units,
              }),
            ],
            [t("seasonTicketsKvMax"), money(view.max_seats)],
            [t("seasonTicketsKvIncome"), `${money(view.income)} ${view.price_units}`],
          ]}
        />

        {view.sold ? (
          <div className="empty">
            <strong>{t("seasonTicketsSoldTitle")}</strong>
            <p className="muted">
              {t("seasonTicketsSoldBody", {
                seats: view.sold.seats,
                amount: money(view.sold.amount),
                units: view.sold.amount_units,
                round: view.sold.round_index,
              })}
            </p>
          </div>
        ) : !view.available ? (
          <div className="empty">
            <strong>{t("seasonTicketsClosedTitle")}</strong>
            <p className="muted">{view.reason ?? t("seasonTicketsClosedBody")}</p>
          </div>
        ) : (
          <div className="stack-sm">
            <label className="muted" htmlFor="season-ticket-seats">
              {t("seasonTicketsSeatsLabel", { min: view.min_seats, max: view.max_seats })}
            </label>
            <input
              id="season-ticket-seats"
              className="input"
              type="number"
              min={view.min_seats}
              max={view.max_seats}
              step={view.min_seats}
              value={seats}
              onChange={(event) => setSeats(Number(event.target.value))}
            />
            {offBlock ? (
              <p className="notice notice--warn">
                {t("seasonTicketsOffBlock", { min: view.min_seats, max: view.max_seats })}
              </p>
            ) : null}
            <button className="button button--ghost" type="button" onClick={sell} disabled={busy || offBlock}>
              {busy ? t("seasonTicketsSelling") : t("seasonTicketsButton", { seats })}
            </button>
            {answer ? <p className="notice">{answer}</p> : null}
            {error ? <p className="notice notice--warn">{error}</p> : null}
          </div>
        )}

        {view.rows.length > 1 ? (
          <ul className="stack-sm">
            {view.rows.map((row) => (
              <li key={row.id} className="muted">
                {t("seasonTicketsRow", {
                  season: row.season,
                  seats: row.seats,
                  amount: money(row.amount),
                  units: row.amount_units,
                })}
              </li>
            ))}
          </ul>
        ) : null}

        <p className="muted">{view.note}</p>
        <p className="mono muted">
          {t("seasonTicketsFormulaLabel")}: {view.formula}
        </p>
        <p className="notice notice--warn">{limitation}</p>
      </div>
    </Panel>
  );
}
