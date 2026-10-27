/**
 * The season's story (M13 Phase 2): the biggest win, the worst loss, the runs, the clean sheets and
 * the home/away split, retold from the career's own played rounds.
 *
 * `career_view["highlights"]` is a retrospective over rounds already played, so it cannot disagree
 * with the record beside it. The page prints the wire figures and the API's own formula; it does no
 * arithmetic of its own, so the story cannot drift from the fixtures it is told from.
 */

import { Panel } from "@/components/ui";
import { KeyValueGrid } from "@/components/world";
import type { CareerHighlightMeeting, CareerHighlights } from "@/lib/types";

type Translator = (key: string, values?: Record<string, string | number | Date>) => string;

const SPLIT_ROWS = [
  { key: "played", labelKey: "thPlayed" },
  { key: "won", labelKey: "highlightsThWon" },
  { key: "drawn", labelKey: "highlightsThDrawn" },
  { key: "lost", labelKey: "highlightsThLost" },
  { key: "goals_for", labelKey: "highlightsThFor" },
  { key: "goals_against", labelKey: "highlightsThAgainst" },
  { key: "points", labelKey: "rowPoints" },
] as const;

function meetingLine(t: Translator, meeting: CareerHighlightMeeting) {
  return t("highlightsMeeting", {
    round: meeting.round_index,
    venue: meeting.side === "home" ? t("opponentH2hVenueHome") : t("opponentH2hVenueAway"),
    gf: meeting.club_goals,
    ga: meeting.opponent_goals,
    opponent: meeting.opponent_name ?? "",
  });
}

export function CareerHighlights({
  t,
  view,
  limitation,
}: {
  t: Translator;
  view: CareerHighlights;
  limitation: string;
}) {
  return (
    <Panel
      eyebrow={t("highlightsEyebrow", { count: view.played ?? 0 })}
      title={t("highlightsTitle")}
    >
      {view.available ? (
        <div className="stack-sm">
          <KeyValueGrid
            rows={[
              [
                t("highlightsBiggestWin"),
                view.biggest_win ? (
                  meetingLine(t, view.biggest_win)
                ) : (
                  <span className="muted">{t("highlightsNoMeeting")}</span>
                ),
              ],
              [
                t("highlightsWorstLoss"),
                view.worst_loss ? (
                  meetingLine(t, view.worst_loss)
                ) : (
                  <span className="muted">{t("highlightsNoMeeting")}</span>
                ),
              ],
              [t("highlightsWinRun"), `${view.longest_winning_run}`],
              [t("rowUnbeaten"), `${view.longest_unbeaten_run}`],
              [t("highlightsCleanSheets"), `${view.clean_sheets}`],
              [t("highlightsFailedToScore"), `${view.failed_to_score}`],
            ]}
          />
          <p className="muted">{t("highlightsSplitTitle")}</p>
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("highlightsThMeasure")}</th>
                  <th scope="col">{t("opponentH2hVenueHome")}</th>
                  <th scope="col">{t("opponentH2hVenueAway")}</th>
                </tr>
              </thead>
              <tbody>
                {SPLIT_ROWS.map((row) => (
                  <tr key={row.key}>
                    <th scope="row">{t(row.labelKey)}</th>
                    <td className="num">{view.home ? view.home[row.key] : "—"}</td>
                    <td className="num">{view.away ? view.away[row.key] : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted mono">{view.formula}</p>
          <p className="muted">{view.note}</p>
        </div>
      ) : (
        <div className="empty">
          <strong>{t("highlightsNoneTitle")}</strong>
          <p className="muted">{view.reason}</p>
        </div>
      )}
      <p className="notice notice--warn">{limitation}</p>
    </Panel>
  );
}
