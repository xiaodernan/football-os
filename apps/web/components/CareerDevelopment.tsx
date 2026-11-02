/**
 * The minutes-based development curve (M13 item 4), now written back: every played round writes one
 * `career_developments` row per player it selected, and `squad_as_of` reads the latest row before a
 * round as that round's eleven. The block prints both the projection and the applied rows — the round a
 * player's latest write came from, and the round the next snapshot starts deciding from — while the
 * world's stored `real_players` rows stay what the generator wrote.
 *
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
      eyebrow={t("developmentEyebrow", { count: view.applied_players })}
      title={t("developmentTitle")}
    >
      <div className="stack-sm">
        <KeyValueGrid
          rows={[
            [t("developmentKvPlayers"), `${view.applied_players} / ${view.players_developed}`],
            [t("developmentKvMinutes"), `${view.total_minutes.toLocaleString("en-GB")}`],
            [t("developmentKvTau"), `${view.tau}`],
            [t("developmentKvRate"), `${view.rate}`],
            [t("thRound"), `${view.last_applied_round || "—"}`],
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
                  <th scope="col">{t("thRound")}</th>
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
                      <td className="num">{row.applied_round ?? "—"}</td>
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
