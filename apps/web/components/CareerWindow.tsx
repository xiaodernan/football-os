/**
 * The signing window the career's next deal would use (M13 Phase 2 item 5): the round the market would
 * read, the season it falls in, and the season's window ranges measured in that season's rounds.
 *
 * The API decides which range contains the next round and publishes the counts of it; the page prints
 * the wire figures and highlights the range whose label matches `in_window`, doing no arithmetic of its
 * own. A career with no horizon has no window to police — the API reads it open and says so — and a
 * closed window names the round and season the next one opens at rather than implying one.
 */

import { Panel } from "@/components/ui";
import { KeyValueGrid } from "@/components/world";
import type { CareerWindow } from "@/lib/types";

type Translator = (key: string, values?: Record<string, string | number | Date>) => string;

export function CareerWindow({
  t,
  view,
  limitation,
}: {
  t: Translator;
  view: CareerWindow;
  limitation: string;
}) {
  const open = view.state === "open";
  const hasRange = view.window_from_round !== null && view.window_to_round !== null;
  const opens = view.opens_at_round !== null && view.opens_at_season !== null;

  return (
    <Panel
      eyebrow={t("signingWindowEyebrow", {
        round: view.round,
        season: view.season_index,
        state: open ? t("signingWindowStateOpen") : t("signingWindowStateClosed"),
      })}
      title={t("signingWindowTitle")}
    >
      <div className="stack-sm">
        <KeyValueGrid
          rows={[
            [t("signingWindowKvNextRound"), `${view.round}`],
            [
              t("signingWindowKvSeason"),
              <span key="season">
                {t("signingWindowSeasonValue", { season: view.season_index, rounds: view.season_rounds })} ·{" "}
                <span className="mono">{view.season_source}</span>
              </span>,
            ],
            [
              t("signingWindowKvRange"),
              hasRange
                ? t("signingWindowRangeValue", { from: view.window_from_round ?? 0, to: view.window_to_round ?? 0 })
                : "—",
            ],
            [t("signingWindowKvPlayed"), `${view.played_in_window}`],
            [t("signingWindowKvLeft"), `${view.signing_rounds_left}`],
            [
              t("signingWindowKvOpens"),
              open
                ? t("signingWindowOpenNow")
                : opens
                  ? t("signingWindowOpensValue", {
                      round: view.opens_at_round ?? 0,
                      season: view.opens_at_season ?? 0,
                      rounds: view.opens_in_rounds,
                    })
                  : "—",
            ],
          ]}
        />

        {view.windows.length === 0 ? (
          <div className="empty">
            <strong>{t("signingWindowNoSeasonTitle")}</strong>
            <p className="muted">{t("signingWindowNoSeasonBody")}</p>
          </div>
        ) : (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("signingWindowThFrom")}</th>
                  <th scope="col">{t("signingWindowThTo")}</th>
                  <th scope="col">{t("signingWindowThLabel")}</th>
                </tr>
              </thead>
              <tbody>
                {view.windows.map((window) => {
                  const current = window.label === view.in_window;
                  return (
                    <tr key={`${window.from_round}-${window.to_round}`}>
                      <td className="num">{window.from_round}</td>
                      <td className="num">{window.to_round}</td>
                      <td>
                        <span className={current ? "badge badge--live" : "badge badge--demo"}>
                          {window.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!open && opens ? (
              <p className="notice">
                {t("signingWindowClosedNotice", {
                  round: view.opens_at_round ?? 0,
                  season: view.opens_at_season ?? 0,
                  rounds: view.opens_in_rounds,
                })}
              </p>
            ) : null}
            <p className="mono muted">
              {t("signingWindowFormulaLabel")}: {view.formula}
            </p>
          </div>
        )}

        <p className="notice notice--warn">{limitation}</p>
      </div>
    </Panel>
  );
}
