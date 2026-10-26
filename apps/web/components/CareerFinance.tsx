/**
 * The career's finance book (ROADMAP Phase 2 item 6): what the balance covers, and where it has been.
 *
 * Everything here comes from `careerView["affordability"]`, which the API recomputes on the read from
 * `career_squad_moves` and `career_wage_charges`. The page renders the figures and the formula the
 * block publishes; it does not do arithmetic of its own, so the runway and the timeline cannot drift
 * from the balance they are derived from. The zero-deal `signing` block is deliberately not printed
 * as a preview — a preview of a move at no fee and no wage states nothing. The transfers page will
 * print the same arithmetic for a real listing.
 */

import { Panel } from "@/components/ui";
import { KeyValueGrid } from "@/components/world";
import type { AffordabilityView } from "@/lib/types";

type Translator = (key: string, values?: Record<string, string | number | Date>) => string;

const money = (value: number) => value.toLocaleString("en-GB");

export function CareerFinance({
  t,
  view,
  limitation,
}: {
  t: Translator;
  view: AffordabilityView;
  limitation: string;
}) {
  const timeline = view.timeline;
  const unit = timeline.units;
  return (
    <Panel eyebrow={t("financeEyebrow")} title={t("financeTitle")}>
      <div className="stack-sm">
        <KeyValueGrid
          rows={[
            [t("rowFinanceRemaining"), `${money(view.remaining)} ${view.units}`],
            [t("rowFinanceWeeklyBill"), `${money(view.weekly_wage_bill)} ${view.units}`],
            [t("rowFinanceWagePlayers"), `${view.wage_players}`],
            [
              t("rowFinanceRunway"),
              view.wage_runway_rounds === null
                ? t("financeRunwayNone")
                : t("financeRunwayRounds", { rounds: view.wage_runway_rounds }),
            ],
            [
              t("financeRunwayFormula"),
              <span className="mono" key="runway-formula">
                {view.formula}
              </span>,
            ],
          ]}
        />
        <p className="muted">{view.note}</p>

        <h3 className="h3">{t("timelineTitle")}</h3>
        {timeline.entries === 0 ? (
          <div className="empty">
            <strong>{t("timelineEmptyTitle")}</strong>
            <p className="muted">{t("timelineEmptyBody")}</p>
          </div>
        ) : (
          <>
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{t("thTimelineRound")}</th>
                    <th scope="col">{t("thTimelineEntry")}</th>
                    <th scope="col">{t("thTimelineChange")}</th>
                    <th scope="col">{t("thTimelineBalance")}</th>
                    <th scope="col">{t("thTimelineStored")}</th>
                  </tr>
                </thead>
                <tbody>
                  {timeline.rows.map((row, index) => (
                    <tr key={`${row.round_index}-${row.kind}-${index}`}>
                      <td className="num">{row.round_index}</td>
                      <td>
                        <span className="badge badge--demo">{row.kind}</span> {row.label}
                      </td>
                      <td className="num">
                        {row.delta > 0 ? "+" : row.delta < 0 ? "−" : ""}
                        {money(Math.abs(row.delta))} {unit}
                      </td>
                      <td className="num mono">{money(row.balance)}</td>
                      <td className="num mono">
                        {money(row.stored_budget_after)}{" "}
                        <span className={row.agrees ? "badge badge--live" : "badge badge--demo"}>
                          {row.agrees ? t("timelineAgrees") : t("timelineDisagrees")}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted">
              {t("timelineSummary", {
                shown: timeline.entries_shown,
                entries: timeline.entries,
                opening: `${money(timeline.opening_balance)} ${unit}`,
                closing: `${money(timeline.closing_balance)} ${unit}`,
              })}
            </p>
            {timeline.truncated ? (
              <p className="notice">
                {t("timelineTruncated", { shown: timeline.entries_shown, total: timeline.entries })}
              </p>
            ) : null}
            <p className={timeline.disagreements > 0 ? "notice notice--warn" : "muted"}>
              {timeline.disagreements > 0
                ? t("timelineDisagreements", { count: timeline.disagreements })
                : t("timelineAllAgree")}
            </p>
          </>
        )}
        <p className="muted">{timeline.note}</p>
        <p className="mono muted">
          {t("timelineFormula")}: {timeline.formula}
        </p>
        <p className="notice notice--warn">{limitation}</p>
      </div>
    </Panel>
  );
}
