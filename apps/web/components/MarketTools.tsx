"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";

import { browserFetch, errorMessage } from "@/lib/api";
import type { Fielding, Listing, MarketBudget, MarketRefusalDetail, MarketView, NegotiationResult, SquadAccount, SquadPlayer, Transferable } from "@/lib/market";

type Action = "open" | "negotiate" | "buy" | "clause" | "loan" | "sell" | "release";
type Acknowledged = { text: string; figures: string[] } | null;

const money = (value: number) => value.toLocaleString("en-GB");

/**
 * The translator as the two module-level helpers below see it. They are not components, so they cannot
 * call `useTranslations` themselves, and this is the whole of what they need from it: a key and its ICU
 * values in, a string out. Declared as a shape rather than imported so the helpers stay testable without
 * a React tree.
 */
type Translate = (key: string, values?: Record<string, string | number>) => string;

/**
 * The §22 market as something a manager can actually do, on one career's own terms.
 *
 * Three rules shape this component:
 *
 *  - **Loading a page never reprices.** The offers are priced by `POST /transfers/{career}/market`, so
 *    opening the window for the round is a button, not a side effect of a visit.
 *  - **Every table shows server truth.** After a deal the page is *re-read* (`router.refresh()`), and the
 *    rows arrive back as props. Nothing here keeps its own running balance, so a balance on screen is one
 *    the next `GET` would also print.
 *  - **A refusal is shown with its figures.** The API answers `409` with the fee and the balance, the
 *    clause and the price, the player and keeper counts. Those are the whole point of an arithmetic
 *    market, so they are printed rather than collapsed into "it failed".
 *
 * The seller's answer to an offer is the interesting one: `countered` moves the price on the stored row,
 * so the table cell re-reads with the new number, and the third attempt is the last one the rule allows.
 */
export function MarketTools({
  ident,
  allowed,
  budget,
  listings,
  deals,
  need,
  squad,
  account,
  fielding,
  totals,
  round,
  marketSize,
  loanRounds,
}: {
  ident: string;
  allowed: Transferable;
  budget: MarketBudget;
  listings: Listing[];
  deals: Listing[];
  need: MarketView["need"];
  squad: SquadPlayer[];
  account: SquadAccount;
  fielding: Fielding;
  totals: MarketView["totals"];
  round: number;
  marketSize: number;
  loanRounds: number;
}) {
  const t = useTranslations("market");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [busy, setBusy] = useState<Action | null>(null);
  const [offers, setOffers] = useState<Record<string, string>>({});
  const [answer, setAnswer] = useState<Acknowledged>(null);
  const [refused, setRefused] = useState<Acknowledged>(null);

  const blocked = !allowed.ok;

  async function run(action: Action, path: string, body?: unknown) {
    setBusy(action);
    setAnswer(null);
    setRefused(null);
    const result = await browserFetch<MarketView & { result?: NegotiationResult }>(`/transfers/${encodeURIComponent(ident)}${path}`, { method: "POST", body });
    if (!result.ok) {
      const detail = (result.error.details ?? {}) as MarketRefusalDetail;
      setRefused({
        text: `${result.error.code} — ${errorMessage(result.error, tCommon("requestFailed"))}`,
        figures: figuresOf(detail, t),
      });
      setBusy(null);
      return;
    }
    const view = result.data;
    // A negotiation is answered by the seller's own ladder, so its figures are the offer, the price it
    // came back at and the floor the rule would not go under. Everything else is answered by the balance.
    const figures = view.result
      ? [
          t("figCameBack", { amount: money(view.result.price) }),
          t("figAsking", { amount: money(view.result.asking) }),
          t("figFloor", { amount: money(view.result.floor) }),
          t("figOffersLeft", { count: view.result.attempts_left }),
          view.result.formula,
        ]
      : [
          t("figLeft", { amount: money(view.budget.remaining), units: view.budget.units }),
          t("figPlayersShort", { n: view.squad.account.squad_now }),
          t("figKeepersShort", { n: view.squad.account.keepers }),
        ];
    setAnswer({ text: sentenceFor(action, view, t), figures: figures.filter(Boolean) });
    router.refresh();
    setBusy(null);
  }

  function open() {
    void run("open", "/market");
  }

  function negotiate(row: Listing) {
    const raw = offers[row.id] ?? "";
    const value = Number(raw.replace(/[^\d]/g, ""));
    if (!Number.isFinite(value) || raw === "") {
      setRefused({ text: t("negotiateError"), figures: [] });
      return;
    }
    void run("negotiate", "/negotiate", { listing: row.id, offer: value });
  }

  const offerFor = (row: Listing) => (
    <div className="row wrap" style={{ gap: "0.35rem" }}>
      <input
        aria-label={t("ariaOffer", { name: row.player_name })}
        className="input"
        inputMode="numeric"
        onChange={(event) => setOffers({ ...offers, [row.id]: event.target.value })}
        placeholder={String(row.current_price)}
        style={{ width: "8.5rem" }}
        type="text"
        value={offers[row.id] ?? ""}
      />
      <button className="btn btn--sm btn--ghost" data-act="offer" disabled={busy !== null || blocked || row.attempts_left === 0} onClick={() => negotiate(row)} type="button">
        {busy === "negotiate" ? t("askingBusy") : t("offerBtn")}
      </button>
      <button className="btn btn--sm" data-act="sign" disabled={busy !== null || blocked || !row.affordable} onClick={() => void run("buy", "/buy", { listing: row.id })} type="button">
        {busy === "buy" ? t("signingBusy") : t("signBtn", { amount: money(row.current_price) })}
      </button>
      {row.clause_required && (
        <button className="btn btn--sm btn--ghost" data-act="clause" disabled={busy !== null || blocked} onClick={() => void run("clause", "/buy", { listing: row.id, use_clause: true })} type="button">
          {busy === "clause" ? t("clauseBusy") : t("clauseBtn", { amount: money(row.release_clause) })}
        </button>
      )}
      <button className="btn btn--sm btn--ghost" data-act="loan" disabled={busy !== null || blocked} onClick={() => void run("loan", "/loan", { listing: row.id, rounds: loanRounds })} type="button">
        {busy === "loan" ? t("loanBusy") : t("loanBtn", { rounds: loanRounds })}
      </button>
    </div>
  );

  return (
    <div className="stack-sm" data-testid="market-tools">
      {blocked && (
        <p className="notice notice--warn" data-testid="market-blocked" role="status">
          <strong>{allowed.code}</strong> — {allowed.message}{" "}
          {allowed.constraint === "no_transfers" ? t("noteNoTransfers", { enforced_by: allowed.enforced_by ?? t("noteCheckedEveryMove") }) : ""}
        </p>
      )}

      <div className="row wrap" style={{ gap: "0.6rem" }}>
        <button className="btn" data-testid="market-open" disabled={busy !== null || blocked} onClick={open} type="button">
          {busy === "open" ? t("openBusy") : totals.listed > 0 ? t("reopenBtn", { round }) : t("openBtn", { round })}
        </button>
        <span className="chip mono">{t("chipOffersOnShelf", { listed: totals.listed, size: marketSize })}</span>
        <span className="chip mono">{t("chipSquadKeepers", { players: account.squad_now, keepers: account.keepers })}</span>
        <span className="chip mono">{t("chipBalance", { amount: money(budget.remaining), units: budget.units })}</span>
      </div>

      {refused && (
        <p className="notice notice--warn" data-testid="market-refused" role="status">
          {refused.text}
          {refused.figures.length > 0 && (
            <>
              {" "}
              <span className="mono">{refused.figures.join(" · ")}</span>
            </>
          )}
        </p>
      )}

      {answer && (
        <p className="notice" data-testid="market-answer" role="status">
          {answer.text} <span className="mono">{answer.figures.join(" · ")}</span>
        </p>
      )}

      {listings.length === 0 ? (
        <div className="empty">
          <strong>{t("emptyNoOffers")}</strong>
          <p className="muted">{t("emptyNoOffersBody", { round })}</p>
        </div>
      ) : (
        <div className="world-tablewrap">
          <table className="table">
            <caption className="muted">
              {t("boardNeedPre")}
              <strong>{need.needed_band}</strong>
              {t("boardNeedPositions", { positions: need.positions_in_band.join(", ") })}
              {need.squad_applied || t("boardNeedSquad")}
            </caption>
            <thead>
              <tr>
                <th scope="col">{t("buyThPlayer")}</th>
                <th scope="col">{t("buyThPos")}</th>
                <th scope="col">{t("buyThAge")}</th>
                <th scope="col">{t("buyThOvr")}</th>
                <th scope="col">{t("buyThPot")}</th>
                <th scope="col">{t("buyThFrom")}</th>
                <th scope="col">{t("buyThAsking")}</th>
                <th scope="col">{t("buyThNow")}</th>
                <th scope="col">{t("buyThClause")}</th>
                <th scope="col">{t("buyThWage")}</th>
                <th scope="col">{t("buyThFit")}</th>
                <th scope="col">{t("buyThOffers")}</th>
                <th scope="col">{t("buyThSigning")}</th>
                <th scope="col">{t("buyThDeal")}</th>
              </tr>
            </thead>
            <tbody>
              {listings.map((row) => (
                <tr data-listing={row.id} key={row.id}>
                  <td>
                    <Link className="world-link" href={row.player_path}>
                      {row.player_name}
                    </Link>
                    {row.band === need.needed_band && <span className="badge badge--live">{t("badgeAnswersNeed")}</span>}
                  </td>
                  <td>{row.position}</td>
                  <td className="num">{row.age}</td>
                  <td className="num">{row.overall}</td>
                  <td className="num">{row.potential}</td>
                  <td>
                    {row.from_team_path ? (
                      <Link className="world-link" href={row.from_team_path}>
                        {row.from_team_name}
                      </Link>
                    ) : (
                      row.from_team_name
                    )}
                    {row.rival && <span className="badge badge--demo">{t("badgeRival")}</span>}
                  </td>
                  <td className="num">{money(row.asking_fee)}</td>
                  <td className="num">
                    {money(row.current_price)}
                    {row.current_price !== row.asking_fee && <span className="muted">{t("chipMoved")}</span>}
                  </td>
                  <td className="num">{money(row.release_clause)}</td>
                  <td className="num">{money(row.weekly_wage)}</td>
                  <td className="num">{row.tactical_fit.toFixed(3)}</td>
                  <td className="num">
                    {t("attemptsLeft", { n: row.attempts_left })}
                    <span className="muted">{row.last_offer > 0 ? t("lastOffer", { amount: money(row.last_offer) }) : ""}</span>
                  </td>
                  <td className="num" data-signing={row.id}>
                    <span className={row.signing.fee_affordable ? "badge badge--live" : "badge badge--demo"}>
                      {row.signing.fee_affordable ? t("buySigningFits") : t("buySigningOver")}
                    </span>
                    <p className="muted">
                      {row.signing.fee_affordable
                        ? t("buySigningLeft", { amount: money(row.signing.remaining_after_fee), units: budget.units })
                        : t("buySigningShort", { amount: money(Math.abs(row.signing.remaining_after_fee)), units: budget.units })}
                    </p>
                    <p className="muted">
                      {t("buySigningBill", { amount: money(row.signing.new_weekly_wage_bill) })}
                      {" · "}
                      {row.signing.new_wage_runway_rounds === null
                        ? t("buySigningNoRunway")
                        : t("buySigningRunway", { rounds: row.signing.new_wage_runway_rounds })}
                    </p>
                    {row.signing.wage_ceiling > 0 && (
                      <p className="muted" data-wage-ceiling={row.id}>
                        {row.signing.wage_affordable
                          ? t("buySigningCeilingOkay", { amount: money(row.signing.wage_headroom_after ?? 0) })
                          : t("buySigningCeilingOver", { amount: money(Math.abs(row.signing.wage_headroom_after ?? 0)) })}
                      </p>
                    )}
                  </td>
                  <td>{offerFor(row)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {deals.length > 0 && (
        <p className="muted">
          <span className="mono">{deals.length}</span>
          {t("dealsNote", { count: deals.length })}
        </p>
      )}

      <div className="world-tablewrap">
        <table className="table">
          <caption className="muted">
            {t("sellingCaption", { club: account.club_name, stored: account.stored_in_world, round: account.as_of_round, signed: account.signed_in, departed: account.departed })}
          </caption>
          <thead>
            <tr>
              <th scope="col">{t("sellThPlayer")}</th>
              <th scope="col">{t("sellThPos")}</th>
              <th scope="col">{t("sellThBand")}</th>
              <th scope="col">{t("sellThAge")}</th>
              <th scope="col">{t("sellThOvr")}</th>
              <th scope="col">{t("sellThPot")}</th>
              <th scope="col">{t("sellThWorth")}</th>
              <th scope="col">{t("sellThSaleBrings")}</th>
              <th scope="col">{t("sellThWage")}</th>
              <th scope="col">{t("sellThLetGo")}</th>
            </tr>
          </thead>
          <tbody>
            {squad.map((row) => (
              <tr data-player={row.player_id} key={row.player_id}>
                <td>
                  <Link className="world-link" href={row.player_path}>
                    {row.name}
                  </Link>
                </td>
                <td>{row.position}</td>
                <td>{row.band}</td>
                <td className="num">{row.age}</td>
                <td className="num">{row.overall}</td>
                <td className="num">{row.potential}</td>
                <td className="num">{money(row.asking_fee)}</td>
                <td className="num">{money(row.sell_proceeds)}</td>
                <td className="num">{money(row.weekly_wage)}</td>
                <td>
                  <div className="row wrap" style={{ gap: "0.35rem" }}>
                    <button
                      className="btn btn--sm btn--ghost"
                      data-act="sell"
                      data-player={row.player_id}
                      disabled={busy !== null || blocked}
                      onClick={() => void run("sell", "/sell", { player: row.slug })}
                      type="button"
                    >
                      {busy === "sell" ? t("sellBusy") : t("sellBtn", { amount: money(row.sell_proceeds) })}
                    </button>
                    <button className="btn btn--sm btn--ghost" data-act="release" data-player={row.player_id} disabled={busy !== null || blocked} onClick={() => void run("release", "/release", { player: row.slug })} type="button">
                      {busy === "release" ? t("releaseBusy") : t("releaseBtn")}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className={fielding.ok ? "muted" : "notice notice--warn"} data-testid="fielding-rule">
        {fielding.rule}
        {t("fieldingReads", { players: fielding.players, keepers: fielding.keepers, plural: fielding.keepers === 1 ? "" : "s", rule: account.rule })}
      </p>
    </div>
  );
}

/** The figures a refusal carried, in the order a reader checks them. */
function figuresOf(detail: MarketRefusalDetail, t: Translate): string[] {
  const out: string[] = [];
  if (typeof detail.fee === "number") out.push(t("figFee", { amount: money(detail.fee) }));
  if (typeof detail.remaining === "number") out.push(t("figBalance", { amount: money(detail.remaining) }));
  if (typeof detail.current_price === "number") out.push(t("figPrice", { amount: money(detail.current_price) }));
  if (typeof detail.release_clause === "number") out.push(t("figClause", { amount: money(detail.release_clause) }));
  if (typeof detail.asking === "number") out.push(t("figAsking", { amount: money(detail.asking) }));
  if (typeof detail.attempts === "number") out.push(t("figOffersMade", { n: detail.attempts }));
  if (typeof detail.players === "number")
    out.push(
      t("figPlayers", {
        players: detail.players,
        keepers: detail.keepers ?? 0,
        needs_players: detail.needs_players ?? "?",
        needs_keepers: detail.needs_keepers ?? "?",
      }),
    );
  if (typeof detail.squad_size === "number")
    out.push(t("figSquad", { round: detail.as_of_round ?? "?", size: detail.squad_size }));
  if (typeof detail.formula === "string" && detail.formula) out.push(detail.formula);
  return out;
}

/** What the server's own re-read says just happened, in the words this page prints. */
function sentenceFor(action: Action, view: MarketView, t: Translate): string {
  const last = view.moves[view.moves.length - 1];
  // `String(...)` on the two fields the ledger may hold as `null` — `player_name` and `counterparty_name`.
  // The literals this slice replaced interpolated them straight into a template, so a null printed `null`;
  // ICU prints a null value as the empty string, which would move the same wart somewhere quieter. `String`
  // keeps the rendered bytes what they were. Making the empty case read well is a separate change with its
  // own evidence, not a side effect of a translation.
  switch (action) {
    case "open":
      return view.market.opened
        ? t("openPriced", { round: view.market.round_index, listed: view.totals.listed })
        : t("openNone");
    case "negotiate":
      return t("negotiateAnswered");
    case "buy":
    case "clause":
      return last
        ? t("buySigned", { name: String(last.player_name), amount: money(last.fee), units: last.fee_units, effect: last.effect })
        : t("buySignedFallback");
    case "loan":
      return last
        ? t("loanArrived", { name: String(last.player_name), round: last.loan_until_round, amount: money(last.fee), units: last.fee_units, effect: last.effect })
        : t("loanArrivedFallback");
    case "sell":
      return last
        ? t("sellSold", { name: String(last.player_name), counterparty: String(last.counterparty_name), amount: money(last.fee), units: last.fee_units, effect: last.effect })
        : t("sellSoldFallback");
    case "release":
      return last ? t("releaseDone", { name: String(last.player_name), effect: last.effect }) : t("releaseDoneFallback");
  }
}
