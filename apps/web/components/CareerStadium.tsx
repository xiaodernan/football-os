"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Panel } from "@/components/ui";
import { KeyValueGrid } from "@/components/world";
import { browserFetch, errorMessage } from "@/lib/api";
import type { CareerStadium, CareerStadiumWork } from "@/lib/types";

const money = (value: number) => value.toLocaleString("en-GB");

/**
 * The career's ground (M13 Phase 9 item 37).
 *
 * A stand is the first purchase that is not a player: the panel prints the club's stored seats, every
 * seat already bought, the capacity the next home gate will read and the published price of one more.
 * Buying posts to `/careers/{slug}/stadium`, then re-reads the page, so the balance, the timeline and
 * the history below are the server's stored rows rather than this component's arithmetic.
 */
export function CareerStadiumPanel({
  ident,
  view,
  remaining,
  units,
  limitation,
}: {
  ident: string;
  view: CareerStadium;
  remaining: number;
  units: string;
  limitation: string;
}) {
  const t = useTranslations("careerDetail");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [seats, setSeats] = useState(view.min_seats);
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const total = seats * view.seat_cost;
  const tooSmall = seats < view.min_seats;
  const tooLarge = seats > view.max_seats;
  const tooExpensive = total > remaining;
  const blocked = busy || tooSmall || tooLarge || tooExpensive;

  async function build() {
    setBusy(true);
    setAnswer(null);
    setError(null);
    const result = await browserFetch<{ built: boolean; work: CareerStadiumWork }>(
      `/careers/${encodeURIComponent(ident)}/stadium`,
      { method: "POST", body: { seats } },
    );
    if (!result.ok) {
      setError(`${result.error.code} — ${errorMessage(result.error, tCommon("requestFailed"))}`);
      setBusy(false);
      return;
    }
    setAnswer(
      t("stadiumBuilt", {
        seats: money(result.data.work.seats),
        capacity: money(result.data.work.capacity_after),
      }),
    );
    router.refresh();
    setBusy(false);
  }

  return (
    <Panel eyebrow={t("stadiumEyebrow", { ground: view.ground || view.club_name, rows: view.rows })} title={t("stadiumTitle")}>
      <div className="stack-sm">
        <p className="muted">{t("stadiumIntro")}</p>

        {!view.available ? (
          <div className="empty">
            <strong>{t("stadiumNoGroundTitle")}</strong>
            <p className="muted">{view.reason ?? t("stadiumNoGroundBody")}</p>
          </div>
        ) : (
          <>
            <KeyValueGrid
              rows={[
                [t("stadiumKvGround"), view.ground || view.club_name],
                [t("stadiumKvStored"), `${money(view.stored_capacity)}`],
                [t("stadiumKvBought"), `${money(view.bought_seats)}`],
                [t("stadiumKvCapacity"), `${money(view.capacity)}`],
                [t("stadiumKvGate"), `${money(view.gate_capacity)}`],
                [t("stadiumKvCost"), `${money(view.seat_cost)} ${units}${t("stadiumPerSeat")}`],
                [t("stadiumKvUpkeep"), `${money(view.upkeep_per_home_round)} ${units}${t("stadiumPerRound")}`],
                [t("stadiumKvSpent"), `${money(view.spent)} ${units}`],
                [t("stadiumKvUpkeepSpent"), `${money(view.upkeep_spent)} ${units}`],
                [t("stadiumKvLimit"), t("stadiumLimitValue", { min: money(view.min_seats), max: money(view.max_seats) })],
              ]}
            />
            <p className="mono muted">{view.capacity_source}</p>

            <div className="stack-sm">
              <h3 className="h3">{t("stadiumBuyTitle")}</h3>
              <label className="muted" htmlFor="stadium-seats">
                {t("stadiumSeatsLabel")}
              </label>
              <input
                id="stadium-seats"
                className="input"
                type="number"
                min={view.min_seats}
                max={view.max_seats}
                step={100}
                value={seats}
                onChange={(event) => setSeats(Number(event.target.value))}
              />
              <KeyValueGrid
                rows={[
                  [t("stadiumTotal"), `${money(total)} ${units}`],
                  [t("stadiumRemaining"), `${money(remaining)} ${units}`],
                ]}
              />
              {tooSmall ? <p className="notice notice--warn">{t("stadiumTooSmall", { min: money(view.min_seats) })}</p> : null}
              {tooLarge ? <p className="notice notice--warn">{t("stadiumTooLarge", { max: money(view.max_seats) })}</p> : null}
              {tooExpensive ? <p className="notice notice--warn">{t("stadiumTooExpensive", { balance: money(remaining) })}</p> : null}
              <button className="button button--ghost" type="button" onClick={build} disabled={blocked}>
                {busy ? t("stadiumBuying") : t("stadiumButton")}
              </button>
              {answer ? <p className="notice">{answer}</p> : null}
              {error ? <p className="notice notice--warn">{error}</p> : null}
            </div>
          </>
        )}

        <h3 className="h3">{t("stadiumHistoryTitle", { rows: view.rows })}</h3>
        {view.works.length === 0 ? (
          <div className="empty">
            <strong>{t("stadiumEmptyTitle")}</strong>
            <p className="muted">{t("stadiumEmptyBody")}</p>
          </div>
        ) : (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("stadiumThRound")}</th>
                  <th scope="col">{t("stadiumThSeats")}</th>
                  <th scope="col">{t("stadiumThAmount")}</th>
                  <th scope="col">{t("stadiumThBefore")}</th>
                  <th scope="col">{t("stadiumThAfter")}</th>
                  <th scope="col">{t("stadiumThBalance")}</th>
                  <th scope="col">{t("stadiumThBasis")}</th>
                </tr>
              </thead>
              <tbody>
                {view.works.map((work) => (
                  <tr key={work.id}>
                    <td className="num">{work.round_index}</td>
                    <td className="num">+{money(work.seats)}</td>
                    <td className="num">{money(work.amount)} {work.amount_units}</td>
                    <td className="num">{money(work.capacity_before)}</td>
                    <td className="num">{money(work.capacity_after)}</td>
                    <td className="num">{money(work.budget_after)}</td>
                    <td className="muted">{work.basis}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="muted">{view.note}</p>
        <p className="mono muted">
          {t("stadiumFormulaLabel")}: {view.formula}
        </p>
        <p className="notice notice--warn">{limitation}</p>
      </div>
    </Panel>
  );
}
