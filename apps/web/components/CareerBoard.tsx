/**
 * The season at its current pace (ROADMAP Phase 2 item 8): the career's own record extended over the
 * season's horizon, and each additive objective set against that pace.
 *
 * Every figure comes from `careerView["board"]`, which the API recomputes from the career's fixture
 * rows on the read. The page prints the API's numbers and formula and does no arithmetic of its own, so
 * the projection cannot drift from the record it is derived from. An unbeaten run is a streak, not a
 * sum, so the API reports it as it stands and this panel prints it that way rather than extrapolating.
 */

import { Panel } from "@/components/ui";
import { KeyValueGrid } from "@/components/world";
import type { CareerBoard as CareerBoardView } from "@/lib/types";

type Translator = (key: string, values?: Record<string, string | number | Date>) => string;

export function CareerBoard({
  t,
  view,
  limitation,
}: {
  t: Translator;
  view: CareerBoardView;
  limitation: string;
}) {
  const projected = view.projected;
  const hasProjection = Object.keys(projected).length > 0;
  const offPace = view.objectives.filter((objective) => objective.on_pace === false).length;
  return (
    <Panel
      eyebrow={t("boardEyebrow", { played: view.played, rounds: view.season_rounds })}
      title={t("boardTitle")}
    >
      <div className="stack-sm">
        <KeyValueGrid
          rows={[
            [
              t("boardHorizonLabel"),
              t("boardHorizonValue", { rounds: view.season_rounds, source: view.season_source }),
            ],
            [t("boardPointsPaceLabel"), view.points_per_round === null ? "—" : `${view.points_per_round}`],
            [t("boardGoalsPaceLabel"), view.goals_for_per_round === null ? "—" : `${view.goals_for_per_round}`],
            [
              t("boardProjectedLabel"),
              hasProjection
                ? t("boardProjectedValue", {
                    wins: projected.wins ?? 0,
                    points: projected.points ?? 0,
                    goalDifference: projected.goal_difference ?? 0,
                  })
                : t("boardNothingProjected"),
            ],
            [
              t("boardOnTrackLabel"),
              view.on_track === null
                ? t("boardUnprojectable")
                : view.on_track
                  ? t("boardAllOnTrack")
                  : t("boardSomeOffPace", { off: offPace }),
            ],
          ]}
        />

        <h3 className="h3">{t("boardObjectivesTitle")}</h3>
        {view.objectives.length === 0 ? (
          <div className="empty">
            <strong>{t("boardEmptyTitle")}</strong>
            <p className="muted">{t("boardEmptyBody")}</p>
          </div>
        ) : (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("boardThObjective")}</th>
                  <th scope="col">{t("boardThAsked")}</th>
                  <th scope="col">{t("boardThNow")}</th>
                  <th scope="col">{t("boardThProjected")}</th>
                  <th scope="col">{t("boardThPace")}</th>
                </tr>
              </thead>
              <tbody>
                {view.objectives.map((objective) => (
                  <tr key={objective.kind}>
                    <td>{objective.label}</td>
                    <td className="num">{objective.target}</td>
                    <td className="num">{objective.actual}</td>
                    <td className="num">{objective.projected === null ? "—" : objective.projected}</td>
                    <td>
                      {objective.on_pace === null ? (
                        <span className="muted">{t("boardAsItStands")}</span>
                      ) : (
                        <span className={objective.on_pace ? "badge badge--live" : "badge badge--demo"}>
                          {objective.on_pace ? t("boardOnPace") : t("boardOffPace")}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="muted">{view.note}</p>
        <p className="mono muted">
          {t("boardFormulaLabel")}: {view.formula}
        </p>
        <p className="notice notice--warn">{limitation}</p>
      </div>
    </Panel>
  );
}
