/**
 * The seasons behind the one being played (M13 Phase 2 item 8): every boundary decision the career has
 * written, each set beside the record its own fixture rows still sum to.
 *
 * The API recomputes the record and the pace from `career_fixtures` on the read and prints the stored
 * verdict separately, so a fixture list edited after the fact shows as the API's own re-check sentence
 * rather than as a quiet correction here. The panel does no arithmetic of its own: the two published
 * lines, the span and the pace are the API's numbers, and the verdict is the row's stored word.
 */

import { Panel } from "@/components/ui";
import { KeyValueGrid } from "@/components/world";
import type { CareerRecord, CareerSeasons as CareerSeasonsView } from "@/lib/types";

type Translator = (key: string, values?: Record<string, string | number | Date>) => string;

/** The four verdicts `close_season` writes, each to the copy this panel prints it with. */
const VERDICT_KEYS: Record<string, string> = {
  promoted: "seasonsPromoted",
  relegated: "seasonsRelegated",
  stayed: "seasonsStayed",
  challenge: "seasonsChallenge",
};

function verdictLabel(t: Translator, verdict: string): string {
  const key = VERDICT_KEYS[verdict];
  return key ? t(key) : verdict;
}

export function CareerSeasons({
  t,
  view,
  lifetime,
  limitation,
}: {
  t: Translator;
  view: CareerSeasonsView;
  lifetime: CareerRecord;
  limitation: string;
}) {
  const current = view.current;
  const competition = current.competition;
  return (
    <Panel
      eyebrow={t("seasonsEyebrow", { index: current.season_index, season: current.season })}
      title={t("seasonsTitle")}
    >
      <div className="stack-sm">
        <KeyValueGrid
          rows={[
            [
              t("seasonsCurrentLabel"),
              competition
                ? t("seasonsCurrentValue", {
                    season: current.season,
                    competition: competition.name,
                    tier: competition.tier,
                  })
                : t("seasonsNoCompetition"),
            ],
            [
              t("seasonsSpanLabel"),
              current.last_round === null
                ? t("seasonsSpanOpen")
                : t("seasonsRoundsValue", {
                    first: current.first_round,
                    last: current.last_round,
                    rounds: current.rounds,
                  }),
            ],
            [t("seasonsPaceLabel"), current.points_per_round === null ? "—" : `${current.points_per_round}`],
            [
              t("seasonsLineLabel"),
              current.line === null ? t("seasonsNoLine") : t("seasonsLineValue", { line: current.line }),
            ],
            [
              t("seasonsAtThisPaceLabel"),
              current.points_per_round === null
                ? "—"
                : current.at_this_pace === null
                  ? t("seasonsNoLine")
                  : verdictLabel(t, current.at_this_pace),
            ],
            [
              t("seasonsLinesLabel"),
              t("seasonsLinesValue", { promotion: view.lines.promotion, relegation: view.lines.relegation }),
            ],
            [
              t("seasonsLifetimeLabel"),
              t("seasonsLifetimeValue", {
                played: lifetime.played,
                won: lifetime.won,
                drawn: lifetime.drawn,
                lost: lifetime.lost,
              }),
            ],
          ]}
        />

        <h3 className="h3">{t("seasonsClosedTitle")}</h3>
        {view.closed.length === 0 ? (
          <div className="empty">
            <strong>{t("seasonsEmptyTitle")}</strong>
            <p className="muted">{t("seasonsEmptyBody")}</p>
          </div>
        ) : (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("seasonsThSeason")}</th>
                  <th scope="col">{t("seasonsThLeague")}</th>
                  <th scope="col">{t("seasonsThRounds")}</th>
                  <th scope="col">{t("seasonsThPace")}</th>
                  <th scope="col">{t("seasonsThVerdict")}</th>
                  <th scope="col">{t("seasonsThNext")}</th>
                </tr>
              </thead>
              <tbody>
                {view.closed.map((block) => (
                  <tr key={block.season_index}>
                    <td>{t("seasonsSeasonCell", { index: block.season_index, season: block.season })}</td>
                    <td>{t("seasonsLeagueValue", { name: block.competition.name, tier: block.competition.tier })}</td>
                    <td className="num">
                      {t("seasonsRoundsValue", {
                        first: block.first_round,
                        last: block.last_round,
                        rounds: block.rounds,
                      })}
                    </td>
                    <td className="num">
                      {block.points_per_round === null ? "—" : `${block.points_per_round}`}
                      {block.recheck ? <div className="muted">{block.recheck}</div> : null}
                    </td>
                    <td>
                      <span
                        className={
                          block.verdict === "promoted" || block.verdict === "relegated"
                            ? "badge badge--live"
                            : "badge badge--demo"
                        }
                      >{verdictLabel(t, block.verdict)}</span>
                    </td>
                    <td>
                      {block.next_competition ? block.next_competition.name : <span className="muted">{t("seasonsNoMove")}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="muted">{current.note}</p>
        <p className="mono muted">
          {t("seasonsFormulaLabel")}: {view.formula}
        </p>
        <p className="notice notice--warn">{limitation}</p>
      </div>
    </Panel>
  );
}
