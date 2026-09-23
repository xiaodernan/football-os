import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { Panel, Stat } from "@/components/ui";
import { MarketTools } from "@/components/MarketTools";
import { KeyValueGrid, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { MarketView } from "@/lib/market";

import "../../../../styles/tactics.css";
import "../../../../styles/simulate.css";

export const dynamic = "force-dynamic";

/**
 * One career's transfer market (spec §22). `noindex` for the same reason the season page is, and it sits
 * under `/career`, which `robots.ts` already disallows — so a page an account would not want crawled
 * cannot become crawlable by being given a new prefix.
 */
export const metadata: Metadata = {
  title: "Transfer market",
  description: "What one career can buy, what its club is short of, what it has already spent, and the arithmetic every figure came from.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/career") },
};

type Props = { params: Promise<{ slug: string }> };

const money = (value: number) => value.toLocaleString("en-GB");

export default async function CareerMarketPage({ params }: Props) {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fcareer");
  const { slug } = await params;
  if (!slug || slug.length > 80) notFound();

  const result = await serverFetch<MarketView>(`/transfers/${encodeURIComponent(slug)}`);
  if (!result.ok) {
    if (result.status === 404) notFound();
    return <WorldUnavailable message={result.error.message} title="Transfer market" />;
  }

  const view = result.data;
  const career = view.career;
  const budget = view.budget;
  const need = view.need;
  const account = view.squad.account;
  const fielding = view.squad.fielding;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: `/career/${encodeURIComponent(career.slug)}`, label: "Back to the season" }}
        eyebrow={`${career.club_name} · round ${career.market_round} · private to this account`}
        lede="A market, not a shop: the board is picked from the band this club is weakest in, every price is the valuation formula recomputed from a stored player row, and the balance is the sum of this career's own move rows. Nothing here was observed; every figure is printed with the expression that made it."
        provenance={{ data_origin: view.data_origin, is_demo_data: view.is_demo_data, disclaimer: view.disclaimer }}
        title={`${career.club_name} · transfer market`}
      />

      <div className="grid grid-4">
        <Stat hint={budget.units} label="Stated budget" value={money(budget.budget)} />
        <Stat hint={`${budget.moves} move${budget.moves === 1 ? "" : "s"} on the ledger`} label="Spent on arrivals" value={money(budget.spent)} />
        <Stat hint="from sales only" label="Received" value={money(budget.received)} />
        <Stat hint={budget.formula} label="Remaining" value={money(budget.remaining)} />
      </div>

      <p className="muted">
        <span className="mono">{budget.formula}</span>
      </p>
      <p className="notice notice--warn">{budget.wage_note} {money(budget.wage_committed_per_week)} {budget.units} a week is committed by the deals on file.</p>

      <Panel eyebrow={`${view.listings.length} priced offers · need: ${need.needed_band}`} title="Buying">
        <MarketTools
          account={account}
          allowed={view.transfers_allowed}
          budget={budget}
          deals={view.deals}
          fielding={fielding}
          ident={career.slug}
          listings={view.listings}
          loanRounds={view.constants.default_loan_rounds}
          marketSize={view.constants.market_size}
          need={need}
          round={career.market_round}
          squad={view.squad.players}
          totals={view.totals}
        />
      </Panel>

      <div className="grid grid-2">
        <Panel eyebrow={need.formula} title="What this club is short of, measured">
          <div className="stack-sm">
            <div className="row wrap" style={{ gap: "0.5rem" }}>
              {Object.entries(need.bands).map(([band, value]) => (
                <span className={band === need.needed_band ? "badge badge--demo" : "chip mono"} key={band}>
                  {band} {value.toFixed(3)}
                </span>
              ))}
            </div>
            <KeyValueGrid
              rows={[
                ["Weakest band", need.needed_band],
                ["Positions it staffs", need.positions_in_band.join(", ")],
                ["Judged on", need.judged_on.join(", ")],
                ["Formation", need.formation],
                ["Tactical system", need.system_slug || "the club's own"],
                [
                  "Squad the reading used",
                  need.squad_applied ? (
                    <span className="mono" key="applied">
                      {need.squad_applied}
                    </span>
                  ) : (
                    "the club's stored squad — this career has changed nothing yet"
                  ),
                ],
              ]}
            />
            <p className="muted">{view.rules.need}</p>
          </div>
        </Panel>

        <Panel eyebrow={`${account.squad_now} players · ${account.keepers} keepers`} title="The squad a deal has to leave standing">
          <div className="stack-sm">
            <KeyValueGrid
              rows={[
                ["Stored by the world", `${account.stored_in_world}`],
                ["Fielded here because this career brought them", `${account.signed_in}`],
                ["The world stored them, this career let them go", `${account.departed}`],
                ["Read as of round", `${account.as_of_round}`],
                [
                  "Can field a side",
                  <span className={fielding.ok ? "badge badge--live" : "badge badge--demo"} key="field">
                    {fielding.ok ? "YES" : "NO"}
                  </span>,
                ],
                ["Rule", fielding.rule],
              ]}
            />
            <p className="muted">{account.rule} The world&apos;s own player rows are never rewritten by a deal: an arrival or a departure is a row in this career&apos;s ledger, composed into the eleven when the round is read.</p>
          </div>
        </Panel>
      </div>

      <Panel eyebrow={`${view.moves.length} row${view.moves.length === 1 ? "" : "s"} · ${view.totals.signed} signed, ${view.totals.withdrawn} withdrawn`} title="The ledger the balance is summed from">
        {view.moves.length === 0 ? (
          <div className="empty">
            <strong>No move recorded</strong>
            <p className="muted">The balance above is the figure the career opened with. It only moves when a deal is written here, and a deal that is not a row cannot be spent.</p>
          </div>
        ) : (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Round</th>
                  <th scope="col">Move</th>
                  <th scope="col">Player</th>
                  <th scope="col">From / to</th>
                  <th scope="col">Fee</th>
                  <th scope="col">Balance after</th>
                  <th scope="col">Wage</th>
                  <th scope="col">Contract</th>
                  <th scope="col">Effect</th>
                </tr>
              </thead>
              <tbody>
                {view.moves.map((move) => (
                  <tr key={move.id}>
                    <td className="num">{move.round_index}</td>
                    <td>
                      <span className={move.side === "in" ? "badge badge--live" : "badge badge--demo"}>{move.kind}</span>
                    </td>
                    <td>
                      {move.player_path ? (
                        <Link className="world-link" href={move.player_path}>
                          {move.player_name}
                        </Link>
                      ) : (
                        move.player_name
                      )}
                    </td>
                    <td>{move.counterparty_name || "—"}</td>
                    <td className="num">
                      {move.side === "in" ? "−" : "+"}
                      {money(move.fee)} {move.fee_units}
                    </td>
                    <td className="num mono">{money(move.budget_after)}</td>
                    <td className="num">{move.weekly_wage ? `${money(move.weekly_wage)}/wk` : "—"}</td>
                    <td className="num">{move.contract_years}y{move.loan_until_round ? ` · until r${move.loan_until_round}` : ""}</td>
                    <td className="muted">{move.effect}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted">
          {budget.budget.toLocaleString("en-GB")} stated {budget.received ? `+ ${money(budget.received)} received ` : ""}
          {budget.spent ? `− ${money(budget.spent)} spent ` : ""}= <strong className="mono">{money(budget.remaining)} {budget.units}</strong>, and the same number is printed beside every offer as the
          balance a deal has to fit inside.
        </p>
      </Panel>

      <Panel eyebrow={`${Object.keys(view.rules).length} published expressions`} title="The rules this market is made of">
        <div className="stack-sm">
          <KeyValueGrid rows={Object.entries(view.rules).map(([key, expression]) => [key, <span className="mono" key={key}>{expression}</span>])} />
          <div className="tag-list">
            <span className="chip mono">board size: {view.constants.market_size}</span>
            <span className="chip mono">offers per player: {view.constants.negotiation_rounds}</span>
            <span className="chip mono">floor: {Math.round(view.constants.negotiation_floor_share * 100)}% of asking</span>
            <span className="chip mono">clause: ×{view.constants.release_clause_share} asking</span>
            <span className="chip mono">loan fee: {Math.round(view.constants.loan_fee_share * 100)}% of price</span>
            <span className="chip mono">sale proceeds: {Math.round(view.constants.sell_proceeds_share * 100)}% of valuation</span>
          </div>
          <p className="muted">
            Age is the one input a club cannot train, so the curve is stated as bands rather than fitted:{" "}
            <span className="mono">{view.constants.age_curve.map((row) => `${row.ages}→×${row.weight}`).join("  ")}</span>
          </p>
          <p className="notice">{view.market.note}</p>
        </div>
      </Panel>

      <Provenance provenance={{ data_origin: view.data_origin, is_demo_data: view.is_demo_data, disclaimer: view.disclaimer }} />
    </div>
  );
}
