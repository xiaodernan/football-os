/**
 * The minutes-based development curve (M13 item 4): what the career's stored appearance minutes and the
 * world's training load imply each player's attributes would become, if the season's development were
 * applied.
 *
 * `career_view["development"]` is a projection, not a write — the stored squad the rest of this page
 * reads keeps its own attributes, and the block is recomputed from the appearance rows on every read.
 * The page prints the wire figures, the attribute keys the wire keys its before/after dicts with, and
 * the API's own formula and note; it does no arithmetic of its own.
 */

import { Panel } from "@/components/ui";
import { KeyValueGrid } from "@/components/world";
import type { CareerDevelopment, CareerDevelopmentPlayer } from "@/lib/types";

type Translator = (key: string, values?: Record<string, string | number | Date>) => string;

/** The wire keys the attribute dicts by machine name; the printed label is that name, spaced. */
function moved(row: CareerDevelopmentPlayer) {
  return Object.entries(row.delta)
    .filter(([, delta]) => delta !== 0)
    .map(([attribute]) => `${attribute.replace(/_/g, " ")} ${row.before[attribute]}→${row.after[attribute]}`);
}

export function CareerDevelopment({
  t,
  view,
  limitation,
}: {
  t: Translator;
  view: CareerDevelopment;
  limitation: string;
}) {
  return (
    <Panel
      eyebrow={t("developmentEyebrow", { count: view.players_developed })}
      title={t("developmentTitle")}
    >
      <div className="stack-sm">
        <KeyValueGrid
          rows={[
            [t("developmentKvPlayers"), `${view.players_developed}`],
            [t("developmentKvMinutes"), `${view.total_minutes.toLocaleString("en-GB")}`],
            [t("developmentKvTau"), `${view.tau}`],
            [t("developmentKvRate"), `${view.rate}`],
          ]}
        />

        {view.top_developed.length === 0 ? (
          <div className="empty">
            <strong>{t("developmentNoneTitle")}</strong>
            <p className="muted">{view.note}</p>
          </div>
        ) : (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("thPlayer")}</th>
                  <th scope="col">{t("thPosition")}</th>
                  <th scope="col">{t("developmentThMinutes")}</th>
                  <th scope="col">{t("thTrainingLoad")}</th>
                  <th scope="col">{t("developmentThEffective")}</th>
                  <th scope="col">{t("developmentThPotential")}</th>
                  <th scope="col">{t("thTimelineChange")}</th>
                </tr>
              </thead>
              <tbody>
                {view.top_developed.map((row) => {
                  const movedAttributes = moved(row);
                  return (
                    <tr key={row.player_id}>
                      <td>{row.player_name}</td>
                      <td className="num">{row.position}</td>
                      <td className="num">{row.minutes.toLocaleString("en-GB")}</td>
                      <td className="num">{row.training_units}</td>
                      <td className="num">{row.effective_minutes.toLocaleString("en-GB")}</td>
                      <td className="num">{row.potential}</td>
                      <td className="muted mono">
                        {movedAttributes.length > 0 ? movedAttributes.join(" · ") : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="muted">{view.note}</p>
            <p className="mono muted">{view.development_formula}</p>
          </div>
        )}

        <p className="notice notice--warn">{limitation}</p>
      </div>
    </Panel>
  );
}
