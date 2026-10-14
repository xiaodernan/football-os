import { getTranslations } from "next-intl/server";
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
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("market");
  return {
    title: t("metaTitle"),
    description: t("metaDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/career") },
  };
}

type Props = { params: Promise<{ slug: string }> };

const money = (value: number) => value.toLocaleString("en-GB");

export default async function CareerMarketPage({ params }: Props) {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fcareer");
  const t = await getTranslations("market");
  const { slug } = await params;
  if (!slug || slug.length > 80) notFound();

  const result = await serverFetch<MarketView>(`/transfers/${encodeURIComponent(slug)}`);
  if (!result.ok) {
    if (result.status === 404) notFound();
    return <WorldUnavailable message={result.error.message} title={t("metaTitle")} />;
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
        back={{ href: `/career/${encodeURIComponent(career.slug)}`, label: t("backLabel") }}
        eyebrow={`${career.club_name}${t("eyebrowSuffix", { round: career.market_round })}`}
        lede={t("lede")}
        provenance={{ data_origin: view.data_origin, is_demo_data: view.is_demo_data, disclaimer: view.disclaimer }}
        title={`${career.club_name}${t("titleSuffix")}`}
      />

      <div className="grid grid-4">
        <Stat hint={budget.units} label={t("statBudgetLabel")} value={money(budget.budget)} />
        <Stat hint={t("statSpentHint", { count: budget.moves })} label={t("statSpentLabel")} value={money(budget.spent)} />
        <Stat hint={t("statReceivedHint")} label={t("statReceivedLabel")} value={money(budget.received)} />
        <Stat hint={budget.formula} label={t("statRemainingLabel")} value={money(budget.remaining)} />
      </div>

      <p className="muted">
        <span className="mono">{budget.formula}</span>
      </p>
      <p className="notice notice--warn">
        {budget.wage_note} {money(budget.wage_committed_per_week)} {budget.units}{t("wageWeekPrefix")}
        {t("wageDeals", { count: budget.wage_players })}{t("wageStands")}{money(budget.wages_paid)} {budget.units}{t("wagePaidPrefix")}
        {t("wageRounds", { count: budget.wage_rows })}{t("wageSuffix")}
      </p>

      <Panel eyebrow={t("buyingEyebrow", { count: view.listings.length, band: need.needed_band })} title={t("buyingTitle")}>
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
        <Panel eyebrow={need.formula} title={t("needTitle")}>
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
                [t("kvWeakestBand"), need.needed_band],
                [t("kvPositionsStaffs"), need.positions_in_band.join(", ")],
                [t("kvJudgedOn"), need.judged_on.join(", ")],
                [t("kvFormation"), need.formation],
                [t("kvTacticalSystem"), need.system_slug || t("kvOwnSystem")],
                [
                  t("kvSquadUsed"),
                  need.squad_applied ? (
                    <span className="mono" key="applied">
                      {need.squad_applied}
                    </span>
                  ) : (
                    t("kvNoSquadChange")
                  ),
                ],
              ]}
            />
            <p className="muted">{view.rules.need}</p>
          </div>
        </Panel>

        <Panel eyebrow={t("squadEyebrow", { squad: account.squad_now, keepers: account.keepers })} title={t("squadTitle")}>
          <div className="stack-sm">
            <KeyValueGrid
              rows={[
                [t("kvStoredByWorld"), `${account.stored_in_world}`],
                [t("kvFieldedHere"), `${account.signed_in}`],
                [t("kvDeparted"), `${account.departed}`],
                [t("kvAsOfRound"), `${account.as_of_round}`],
                [
                  t("kvCanFieldSide"),
                  <span className={fielding.ok ? "badge badge--live" : "badge badge--demo"} key="field">
                    {fielding.ok ? t("yes") : t("no")}
                  </span>,
                ],
                [t("kvRule"), fielding.rule],
              ]}
            />
            <p className="muted">{account.rule} {t("squadRuleNote")}</p>
          </div>
        </Panel>
      </div>

      <Panel eyebrow={t("ledgerEyebrow", { rows: view.moves.length, signed: view.totals.signed, withdrawn: view.totals.withdrawn })} title={t("ledgerTitle")}>
        {view.moves.length === 0 ? (
          <div className="empty">
            <strong>{t("emptyNoMove")}</strong>
            <p className="muted">{t("emptyNoMoveBody")}</p>
          </div>
        ) : (
          <div className="world-tablewrap">
            <table className="table" data-testid="ledger">
              <thead>
                <tr>
                  <th scope="col">{t("thRound")}</th>
                  <th scope="col">{t("thMove")}</th>
                  <th scope="col">{t("thPlayer")}</th>
                  <th scope="col">{t("thFromTo")}</th>
                  <th scope="col">{t("thFee")}</th>
                  <th scope="col">{t("thBalanceAfter")}</th>
                  <th scope="col">{t("thWage")}</th>
                  <th scope="col">{t("thContract")}</th>
                  <th scope="col">{t("thEffect")}</th>
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
                      {move.detail ? (
                        <p className="muted" key={move.id}>
                          {move.detail}
                        </p>
                      ) : null}
                    </td>
                    <td>{move.counterparty_name || "—"}</td>
                    <td className="num">
                      {move.cash === "out" ? "−" : "+"}
                      {money(move.fee)} {move.fee_units}
                    </td>
                    <td className="num mono">{money(move.budget_after)}</td>
                    <td className="num">{move.weekly_wage ? t("wageCell", { amount: money(move.weekly_wage) }) : "—"}</td>
                    <td className="num">
                      {move.kind === "wage"
                        ? "—"
                        : `${t("contractYears", { years: move.contract_years })}${move.loan_until_round ? t("contractUntil", { round: move.loan_until_round }) : ""}`}
                    </td>
                    <td className="muted">{move.effect}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted">
          {budget.budget.toLocaleString("en-GB")}{t("footerStated")}
          {budget.received ? t("footerReceived", { amount: money(budget.received) }) : ""}
          {budget.spent ? t("footerSpent", { amount: money(budget.spent) }) : ""}
          {budget.wages_paid ? t("footerWages", { amount: money(budget.wages_paid) }) : ""}={" "}
          <strong className="mono">{money(budget.remaining)} {budget.units}</strong>
          {t("footerTail")}
        </p>
      </Panel>

      <Panel eyebrow={t("rulesEyebrow", { count: Object.keys(view.rules).length })} title={t("rulesTitle")}>
        <div className="stack-sm">
          <KeyValueGrid rows={Object.entries(view.rules).map(([key, expression]) => [key, <span className="mono" key={key}>{expression}</span>])} />
          <div className="tag-list">
            <span className="chip mono">{t("chipBoardSize", { n: view.constants.market_size })}</span>
            <span className="chip mono">{t("chipOffersPerPlayer", { n: view.constants.negotiation_rounds })}</span>
            <span className="chip mono">{t("chipFloor", { percent: Math.round(view.constants.negotiation_floor_share * 100) })}</span>
            <span className="chip mono">{t("chipClause", { share: view.constants.release_clause_share })}</span>
            <span className="chip mono">{t("chipLoanFee", { percent: Math.round(view.constants.loan_fee_share * 100) })}</span>
            <span className="chip mono">{t("chipSaleProceeds", { percent: Math.round(view.constants.sell_proceeds_share * 100) })}</span>
          </div>
          <p className="muted">
            {t("ageCurveNote")}
            <span className="mono">{view.constants.age_curve.map((row) => `${row.ages}→×${row.weight}`).join("  ")}</span>
          </p>
          <p className="notice">{view.market.note}</p>
        </div>
      </Panel>

      <Provenance provenance={{ data_origin: view.data_origin, is_demo_data: view.is_demo_data, disclaimer: view.disclaimer }} />
    </div>
  );
}
