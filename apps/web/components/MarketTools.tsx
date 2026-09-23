"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";

import { browserFetch } from "@/lib/api";
import type { Fielding, Listing, MarketBudget, MarketRefusalDetail, MarketView, NegotiationResult, SquadAccount, SquadPlayer, Transferable } from "@/lib/market";

type Action = "open" | "negotiate" | "buy" | "clause" | "loan" | "sell" | "release";
type Acknowledged = { text: string; figures: string[] } | null;

const money = (value: number) => value.toLocaleString("en-GB");

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
        text: `${result.error.code} — ${result.error.message}`,
        figures: figuresOf(detail),
      });
      setBusy(null);
      return;
    }
    const view = result.data;
    // A negotiation is answered by the seller's own ladder, so its figures are the offer, the price it
    // came back at and the floor the rule would not go under. Everything else is answered by the balance.
    const figures = view.result
      ? [`came back at ${money(view.result.price)}`, `asking ${money(view.result.asking)}`, `floor ${money(view.result.floor)}`, `${view.result.attempts_left} offer${view.result.attempts_left === 1 ? "" : "s"} left`, view.result.formula]
      : [`${money(view.budget.remaining)} ${view.budget.units} left`, `${view.squad.account.squad_now} players`, `${view.squad.account.keepers} goalkeepers`];
    setAnswer({ text: sentenceFor(action, view), figures: figures.filter(Boolean) });
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
      setRefused({ text: "negotiate: an offer has to be a number of credits before the seller can answer it.", figures: [] });
      return;
    }
    void run("negotiate", "/negotiate", { listing: row.id, offer: value });
  }

  const offerFor = (row: Listing) => (
    <div className="row wrap" style={{ gap: "0.35rem" }}>
      <input
        aria-label={`offer for ${row.player_name}`}
        className="input"
        inputMode="numeric"
        onChange={(event) => setOffers({ ...offers, [row.id]: event.target.value })}
        placeholder={String(row.current_price)}
        style={{ width: "8.5rem" }}
        type="text"
        value={offers[row.id] ?? ""}
      />
      <button className="btn btn--sm btn--ghost" data-act="offer" disabled={busy !== null || blocked || row.attempts_left === 0} onClick={() => negotiate(row)} type="button">
        {busy === "negotiate" ? "Asking…" : "Offer"}
      </button>
      <button className="btn btn--sm" data-act="sign" disabled={busy !== null || blocked || !row.affordable} onClick={() => void run("buy", "/buy", { listing: row.id })} type="button">
        {busy === "buy" ? "Signing…" : `Sign ${money(row.current_price)}`}
      </button>
      {row.clause_required && (
        <button className="btn btn--sm btn--ghost" data-act="clause" disabled={busy !== null || blocked} onClick={() => void run("clause", "/buy", { listing: row.id, use_clause: true })} type="button">
          {busy === "clause" ? "Paying the clause…" : `Clause ${money(row.release_clause)}`}
        </button>
      )}
      <button className="btn btn--sm btn--ghost" data-act="loan" disabled={busy !== null || blocked} onClick={() => void run("loan", "/loan", { listing: row.id, rounds: loanRounds })} type="button">
        {busy === "loan" ? "Loan…" : `Loan ${loanRounds}r`}
      </button>
    </div>
  );

  return (
    <div className="stack-sm" data-testid="market-tools">
      {blocked && (
        <p className="notice notice--warn" data-testid="market-blocked" role="status">
          <strong>{allowed.code}</strong> — {allowed.message} {allowed.constraint === "no_transfers" ? `The scenario forbids transfers, and the market is what enforces it (${allowed.enforced_by ?? "checked on every move"}).` : ""}
        </p>
      )}

      <div className="row wrap" style={{ gap: "0.6rem" }}>
        <button className="btn" data-testid="market-open" disabled={busy !== null || blocked} onClick={open} type="button">
          {busy === "open" ? "Pricing round…" : totals.listed > 0 ? `Re-open the market for round ${round}` : `Open the market for round ${round}`}
        </button>
        <span className="chip mono">
          {totals.listed} of {marketSize} offers on the shelf
        </span>
        <span className="chip mono">{account.squad_now} players · {account.keepers} keepers</span>
        <span className="chip mono">
          balance {money(budget.remaining)} {budget.units}
        </span>
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
          <strong>No offers priced yet</strong>
          <p className="muted">
            Press “Open the market for round {round}”. The board picks the best-rated players in the band this club is short in — the need is measured from the engine&apos;s own band indices, not chosen by
            an adjective — and prices each one with the expression printed at the foot of this page.
          </p>
        </div>
      ) : (
        <div className="world-tablewrap">
          <table className="table">
            <caption className="muted">
              The need this board was picked against: <strong>{need.needed_band}</strong> ({need.positions_in_band.join(", ")}) — {need.squad_applied || "the club's stored squad, unchanged by this career"}
            </caption>
            <thead>
              <tr>
                <th scope="col">Player</th>
                <th scope="col">Pos</th>
                <th scope="col">Age</th>
                <th scope="col">Ovr</th>
                <th scope="col">Pot</th>
                <th scope="col">From</th>
                <th scope="col">Asking</th>
                <th scope="col">Now</th>
                <th scope="col">Clause</th>
                <th scope="col">Wage</th>
                <th scope="col">Fit</th>
                <th scope="col">Offers</th>
                <th scope="col">Deal</th>
              </tr>
            </thead>
            <tbody>
              {listings.map((row) => (
                <tr data-listing={row.id} key={row.id}>
                  <td>
                    <Link className="world-link" href={row.player_path}>
                      {row.player_name}
                    </Link>
                    {row.band === need.needed_band && <span className="badge badge--live"> answers the need</span>}
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
                    {row.rival && <span className="badge badge--demo"> rival</span>}
                  </td>
                  <td className="num">{money(row.asking_fee)}</td>
                  <td className="num">
                    {money(row.current_price)}
                    {row.current_price !== row.asking_fee && <span className="muted"> · moved</span>}
                  </td>
                  <td className="num">{money(row.release_clause)}</td>
                  <td className="num">{money(row.weekly_wage)}</td>
                  <td className="num">{row.tactical_fit.toFixed(3)}</td>
                  <td className="num">
                    {row.attempts_left} left<span className="muted">{row.last_offer > 0 ? ` · last ${money(row.last_offer)}` : ""}</span>
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
          <span className="mono">{deals.length}</span> closed {deals.length === 1 ? "deal is" : "deals are"} off the shelf and stay in the squad table below — a signed listing is not repriced, and a loan
          returns to its own club when its rounds run out.
        </p>
      )}

      <div className="world-tablewrap">
        <table className="table">
          <caption className="muted">
            Selling from {account.club_name}: the world stores {account.stored_in_world} players for this club. As of round {account.as_of_round}, {account.signed_in} of the players this career fields were
            brought in by its own moves and {account.departed} the world stored here are gone. These are the squad&apos;s counts, not the ledger&apos;s: a signing that is later sold again leaves no trace on either
            number, while both of its fees stay in this career&apos;s ledger.
          </caption>
          <thead>
            <tr>
              <th scope="col">Player</th>
              <th scope="col">Pos</th>
              <th scope="col">Band</th>
              <th scope="col">Age</th>
              <th scope="col">Ovr</th>
              <th scope="col">Pot</th>
              <th scope="col">Worth</th>
              <th scope="col">Sale brings</th>
              <th scope="col">Wage</th>
              <th scope="col">Let go</th>
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
                      {busy === "sell" ? "Selling…" : `Sell ${money(row.sell_proceeds)}`}
                    </button>
                    <button className="btn btn--sm btn--ghost" data-act="release" data-player={row.player_id} disabled={busy !== null || blocked} onClick={() => void run("release", "/release", { player: row.slug })} type="button">
                      {busy === "release" ? "Releasing…" : "Release"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className={fielding.ok ? "muted" : "notice notice--warn"} data-testid="fielding-rule">
        {fielding.rule} This squad reads {fielding.players} players and {fielding.keepers} goalkeeper{fielding.keepers === 1 ? "" : "s"}. {account.rule}
      </p>
    </div>
  );
}

/** The figures a refusal carried, in the order a reader checks them. */
function figuresOf(detail: MarketRefusalDetail): string[] {
  const out: string[] = [];
  if (typeof detail.fee === "number") out.push(`fee ${money(detail.fee)}`);
  if (typeof detail.remaining === "number") out.push(`balance ${money(detail.remaining)}`);
  if (typeof detail.current_price === "number") out.push(`price ${money(detail.current_price)}`);
  if (typeof detail.release_clause === "number") out.push(`clause ${money(detail.release_clause)}`);
  if (typeof detail.asking === "number") out.push(`asking ${money(detail.asking)}`);
  if (typeof detail.attempts === "number") out.push(`offers made ${detail.attempts}`);
  if (typeof detail.players === "number") out.push(`${detail.players} players, ${detail.keepers ?? 0} keepers (needs ${detail.needs_players ?? "?"}/${detail.needs_keepers ?? "?"})`);
  if (typeof detail.squad_size === "number") out.push(`squad as of round ${detail.as_of_round ?? "?"}: ${detail.squad_size}`);
  if (typeof detail.formula === "string" && detail.formula) out.push(detail.formula);
  return out;
}

/** What the server's own re-read says just happened, in the words this page prints. */
function sentenceFor(action: Action, view: MarketView): string {
  const last = view.moves[view.moves.length - 1];
  switch (action) {
    case "open":
      return view.market.opened ? `Round ${view.market.round_index} priced: ${view.totals.listed} offers on the shelf.` : "The market answered with no offers.";
    case "negotiate":
      return "The seller has answered; the price beside the player is the one on file now.";
    case "buy":
    case "clause":
      return last ? `${last.player_name} signed for ${money(last.fee)} ${last.fee_units}. ${last.effect}` : "The signing went through.";
    case "loan":
      return last ? `${last.player_name} arrives on loan until round ${last.loan_until_round} for ${money(last.fee)} ${last.fee_units}. ${last.effect}` : "The loan went through.";
    case "sell":
      return last ? `${last.player_name} sold to ${last.counterparty_name} for ${money(last.fee)} ${last.fee_units}. ${last.effect}` : "The sale went through.";
    case "release":
      return last ? `${last.player_name} released for nothing. ${last.effect}` : "The release went through.";
  }
}
