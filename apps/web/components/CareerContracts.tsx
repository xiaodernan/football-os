/**
 * The deal book (M13 Phase 2): when each held deal's stored terms project it to expire, and the
 * squad's stored age profile beside it.
 *
 * `career_view["contracts"]` is a projection, not an enforcement — nothing in this build expires or
 * renews a contract, so the expiry column reads "projected" and every row carries the basis the
 * projection read. The page prints the wire figures, the API's own basis strings and its formula; it
 * does no arithmetic of its own, so the book cannot drift from the terms the market stored.
 */

import { Panel } from "@/components/ui";
import { KeyValueGrid } from "@/components/world";
import type { CareerContracts } from "@/lib/types";

type Translator = (key: string, values?: Record<string, string | number | Date>) => string;

const KIND_LABELS: Record<string, string> = {
  buy: "contractsKindBuy",
  loan: "contractsKindLoan",
  loan_out: "contractsKindLoanOut",
};

const BANDS = [
  ["under_21", "contractsBandUnder21"],
  ["21_to_25", "contractsBand2125"],
  ["26_to_29", "contractsBand2629"],
  ["30_to_33", "contractsBand3033"],
  ["34_plus", "contractsBand34"],
] as const;

export function CareerContracts({
  t,
  view,
  limitation,
}: {
  t: Translator;
  view: CareerContracts;
  limitation: string;
}) {
  const ages = view.age_profile;
  const risk = ages.retirement_risk.map((entry) => entry.player_name).join(", ");

  return (
    <Panel
      eyebrow={t("contractsEyebrow", { deals: view.deals, expiring: view.expiring_soon })}
      title={t("contractsTitle")}
    >
      <div className="stack-sm">
        <KeyValueGrid
          rows={[
            [t("contractsCurrentRound"), t("contractsRoundValue", { current: view.current_round, seasonRounds: view.season_rounds })],
            [t("contractsDealsHeld"), `${view.deals}`],
            [t("contractsWageTotal"), `${view.total_weekly_wage.toLocaleString("en-GB")} ${view.units}`],
            [t("contractsWageExpiring"), `${view.expiring_weekly_wage.toLocaleString("en-GB")} ${view.units}`],
            [t("contractsWarningWindow"), t("contractsWarningValue", { rounds: view.warning_rounds })],
          ]}
        />

        {view.rows.length === 0 ? (
          <div className="empty">
            <strong>{t("contractsNoDealsTitle")}</strong>
            <p className="muted">{view.note}</p>
          </div>
        ) : (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("thPlayer")}</th>
                  <th scope="col">{t("contractsThKind")}</th>
                  <th scope="col">{t("contractsThWage")}</th>
                  <th scope="col">{t("contractsThSigned")}</th>
                  <th scope="col">{t("contractsThExpires")}</th>
                  <th scope="col">{t("contractsThRemaining")}</th>
                  <th scope="col">{t("contractsThBasis")}</th>
                </tr>
              </thead>
              <tbody>
                {view.rows.map((row) => (
                  <tr key={`${row.player_id}-${row.signed_round}`}>
                    <td>{row.player_name}</td>
                    <td>
                      <span className={row.expiring_soon ? "badge badge--demo" : "badge badge--live"}>
                        {t(KIND_LABELS[row.kind] ?? "contractsNoExpiry")}
                      </span>
                    </td>
                    <td className="num">{row.weekly_wage.toLocaleString("en-GB")}</td>
                    <td className="num">{row.signed_round}</td>
                    <td className="num">{row.expiry_round ?? <span className="muted">{t("contractsNoExpiry")}</span>}</td>
                    <td className="num">
                      {row.rounds_remaining ?? "—"}{" "}
                      {row.expiring_soon ? <span className="badge badge--demo">{t("contractsExpiringSoon")}</span> : null}
                    </td>
                    <td className="muted">{row.basis}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted">{view.note}</p>
            <p className="mono muted">
              {t("contractsFormulaLabel")}: {view.formula}
            </p>
          </div>
        )}

        <h3 className="h3">{t("contractsAgeTitle")}</h3>
        <KeyValueGrid
          rows={[
            [t("contractsAgePlayers"), `${ages.players}`],
            [t("contractsAgeMean"), ages.mean === null ? "—" : `${ages.mean}`],
            [t("contractsAgeMedian"), ages.median === null ? "—" : `${ages.median}`],
            [t("contractsAgeRetirement"), `${ages.retirement_age}+`],
            [
              t("contractsRiskLabel"),
              risk ? (
                risk
              ) : (
                <span className="muted">{t("contractsRiskNone")}</span>
              ),
            ],
          ]}
        />
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("contractsAgeThBand")}</th>
                <th scope="col">{t("contractsAgeThPlayers")}</th>
              </tr>
            </thead>
            <tbody>
              {BANDS.map(([key, labelKey]) => (
                <tr key={key}>
                  <td>{t(labelKey)}</td>
                  <td className="num">{ages.bands[key]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted">{ages.note}</p>

        <p className="notice notice--warn">{limitation}</p>
      </div>
    </Panel>
  );
}
