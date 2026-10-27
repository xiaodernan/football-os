/**
 * The next opponent, read two ways (ROADMAP Phase 2 item 8): this career's own record against them,
 * and the engine's band-by-band measurement of the two sides.
 *
 * Both blocks are published by `career_view["head_to_head"]` and `career_view["next_fixture_brief"]`
 * and both are recomputed from the rows on every read. The page prints their figures, notes and
 * formulas; it does no arithmetic of its own beyond formatting a number to three decimals, so the
 * comparison cannot drift from the measurement the engine will play. The head-to-head is this
 * career's fixtures against this opponent and nothing else — not the opponent's record against
 * everyone — and the brief is a comparison, not a forecast: no scoreline is predicted.
 */

import { Panel } from "@/components/ui";
import { KeyValueGrid } from "@/components/world";
import type { CareerHeadToHead, CareerNextFixtureBrief } from "@/lib/types";

type Translator = (key: string, values?: Record<string, string | number | Date>) => string;

const BANDS = ["attack", "midfield", "defence", "keeper", "press"] as const;

const BAND_LABELS: Record<(typeof BANDS)[number], string> = {
  attack: "bandLabelAttack",
  midfield: "bandLabelMidfield",
  defence: "bandLabelDefence",
  keeper: "bandLabelKeeper",
  press: "bandLabelPress",
};

const fixed = (value: number) => value.toFixed(3);
const signed = (value: number) => `${value > 0 ? "+" : ""}${value.toFixed(3)}`;

export function CareerNextOpponent({
  t,
  headToHead,
  brief,
  limitation,
}: {
  t: Translator;
  headToHead: CareerHeadToHead | undefined;
  brief: CareerNextFixtureBrief | undefined;
  limitation: string;
}) {
  const named = brief?.available ? t("opponentEyebrow", { round: brief.round_index ?? 0, opponent: brief.opponent_name ?? "" }) : t("opponentEyebrowNone");
  const h2h = headToHead;
  const played = h2h?.played ?? 0;
  const meetings = h2h?.meetings ?? [];
  const profile = brief?.available ? brief.career : undefined;
  const rival = brief?.available ? brief.opponent : undefined;
  const delta = brief?.delta ?? {};
  const label = (band: string) => {
    const key = BAND_LABELS[band as keyof typeof BAND_LABELS];
    return key ? t(key) : band;
  };
  const stronger = (brief?.stronger_bands ?? []).map(label);
  const weaker = (brief?.weaker_bands ?? []).map(label);

  return (
    <Panel eyebrow={named} title={t("opponentTitle")}>
      <div className="stack-sm">
        <h3 className="h3">{t("opponentH2hTitle")}</h3>
        {!h2h?.available ? (
          <p className="muted">{h2h?.reason}</p>
        ) : played === 0 ? (
          <div className="empty">
            <strong>{t("opponentH2hEmptyTitle")}</strong>
            <p className="muted">{h2h.note}</p>
          </div>
        ) : (
          <>
            <KeyValueGrid
              rows={[
                [t("opponentH2hMeetings"), `${played}`],
                [
                  t("opponentH2hRecord"),
                  t("opponentH2hRecordValue", {
                    won: h2h.won ?? 0,
                    drawn: h2h.drawn ?? 0,
                    lost: h2h.lost ?? 0,
                  }),
                ],
                [t("opponentH2hGoals"), `${h2h.goals_for ?? 0} – ${h2h.goals_against ?? 0}`],
                [t("opponentH2hDifference"), `${h2h.goal_difference ?? 0}`],
                [t("opponentH2hPoints"), `${h2h.points ?? 0}`],
              ]}
            />
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{t("opponentH2hThMeeting")}</th>
                    <th scope="col">{t("opponentH2hThWhere")}</th>
                    <th scope="col">{t("opponentH2hThResult")}</th>
                    <th scope="col">{t("opponentH2hThOutcome")}</th>
                  </tr>
                </thead>
                <tbody>
                  {meetings.map((meeting) => (
                    <tr key={meeting.round_index}>
                      <td className="num">{meeting.round_index}</td>
                      <td className="muted">{meeting.side === "home" ? t("opponentH2hVenueHome") : t("opponentH2hVenueAway")}</td>
                      <td className="num">
                        {meeting.club_goals}–{meeting.opponent_goals}
                      </td>
                      <td>
                        <span className={meeting.outcome === "W" ? "badge badge--live" : "badge badge--demo"}>{meeting.outcome}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted">{h2h.note}</p>
            <p className="mono muted">
              {t("opponentH2hFormulaLabel")}: {h2h.formula}
            </p>
          </>
        )}

        <h3 className="h3">{t("opponentBriefTitle")}</h3>
        {!brief?.available || !profile || !rival ? (
          <p className="muted">{brief?.reason}</p>
        ) : (
          <>
            <KeyValueGrid
              rows={[
                [t("opponentBriefPlayedAt"), brief.venue_name ?? "—"],
                [t("opponentBriefFormation"), `${profile.formation} · ${rival.formation}`],
                [
                  t("opponentBriefSystem"),
                  `${profile.system_slug || t("opponentBriefDefaultSystem")} · ${rival.system_slug || t("opponentBriefDefaultSystem")}`,
                ],
                [t("opponentBriefOverall"), `${fixed(profile.overall)} · ${fixed(rival.overall)}`],
                [t("opponentBriefForm"), `${fixed(profile.form)} · ${fixed(rival.form)}`],
              ]}
            />
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{t("opponentBriefThBand")}</th>
                    <th scope="col">{t("opponentBriefThCareer")}</th>
                    <th scope="col">{t("opponentBriefThOpponent")}</th>
                    <th scope="col">{t("opponentBriefThDelta")}</th>
                  </tr>
                </thead>
                <tbody>
                  {BANDS.map((band) => (
                    <tr key={band}>
                      <td>{t(BAND_LABELS[band])}</td>
                      <td className="num">{fixed(profile.bands[band])}</td>
                      <td className="num">{fixed(rival.bands[band])}</td>
                      <td className="num mono">{signed(delta[band])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {stronger.length > 0 ? <p>{t("opponentBriefStronger", { bands: stronger.join(", ") })}</p> : null}
            {weaker.length > 0 ? <p>{t("opponentBriefWeaker", { bands: weaker.join(", ") })}</p> : null}
            {stronger.length === 0 && weaker.length === 0 ? <p>{t("opponentBriefLevel")}</p> : null}
            <p className="muted">{brief.note}</p>
            <p className="mono muted">
              {t("opponentBriefFormulaLabel")}: {brief.formula}
            </p>
          </>
        )}

        <p className="notice notice--warn">{limitation}</p>
      </div>
    </Panel>
  );
}
