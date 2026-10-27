/**
 * The youth academy's outcomes (M13 item 7): the career's under-21 squad players judged against the
 * eleven the engine's own selection picks from the same squad — graduation measured, not drawn.
 *
 * `career_view["academy"]` is a read-only projection recomputed on every read and never written back,
 * the same discipline the development block states. The page prints the wire figures, the verdict the
 * wire's own closed set names, and the API's formulas and note; it does no arithmetic of its own.
 */

import { Panel } from "@/components/ui";
import { KeyValueGrid } from "@/components/world";
import type { CareerAcademy, CareerAcademyTrainee } from "@/lib/types";

type Translator = (key: string, values?: Record<string, string | number | Date>) => string;

function verdictLabel(t: Translator, verdict: string) {
  if (verdict === "selected") return t("academyVerdictSelected");
  if (verdict === "next_in_line") return t("academyVerdictNextInLine");
  if (verdict === "off_the_pace") return t("academyVerdictOffThePace");
  return verdict;
}

/** One text node per cell: adjacent expressions would gain React's `<!-- -->` separators and no reader could match the row. */
function storedCell(row: CareerAcademyTrainee) {
  return `${row.stored_overall}→${row.projected_overall.toFixed(1)}`;
}

function standingCell(t: Translator, row: CareerAcademyTrainee) {
  const standing = t("academyStanding", {
    rank: row.band_rank ?? 0,
    size: row.band_size,
    seats: row.seats_in_band,
  });
  if (row.gap_to_last_seat === null) return standing;
  return `${standing} · ${t("academyGap", { gap: row.gap_to_last_seat })}`;
}

export function CareerAcademy({
  t,
  view,
  limitation,
}: {
  t: Translator;
  view: CareerAcademy;
  limitation: string;
}) {
  return (
    <Panel
      eyebrow={t("academyEyebrow", { count: view.class_size, ceiling: view.youth_age_max })}
      title={t("academyTitle")}
    >
      <div className="stack-sm">
        {view.available && view.trainees.length > 0 ? (
          <>
            <KeyValueGrid
              rows={[
                [t("academyKvClass"), `${view.class_size}`],
                [t("academyKvSelected"), `${view.selected_count}`],
                [t("academyKvNextInLine"), `${view.next_in_line_count}`],
                [t("academyKvSquad"), `${view.squad_size}`],
                [t("academyKvFormation"), `${view.formation ?? "—"}`],
                [t("academyKvCeiling"), `${view.youth_age_max}`],
              ]}
            />
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{t("thPlayer")}</th>
                    <th scope="col">{t("thPosition")}</th>
                    <th scope="col">{t("academyThAge")}</th>
                    <th scope="col">{t("developmentThMinutes")}</th>
                    <th scope="col">{t("academyThStored")}</th>
                    <th scope="col">{t("academyThHeadroom")}</th>
                    <th scope="col">{t("academyThStanding")}</th>
                    <th scope="col">{t("academyThVerdict")}</th>
                  </tr>
                </thead>
                <tbody>
                  {view.trainees.map((row) => (
                    <tr key={row.player_id}>
                      <td>{row.player_name}</td>
                      <td className="num">{row.position}</td>
                      <td className="num">{row.age}</td>
                      <td className="num">{row.minutes.toLocaleString("en-GB")}</td>
                      <td className="num">{storedCell(row)}</td>
                      <td className="num">{row.potential_headroom}</td>
                      <td className="muted">{standingCell(t, row)}</td>
                      <td>
                        <span
                          className={
                            row.verdict === "selected"
                              ? "badge badge--live"
                              : row.verdict === "off_the_pace"
                                ? "badge badge--demo"
                                : "badge"
                          }
                        >
                          {verdictLabel(t, row.verdict)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="muted">{view.note}</p>
              <p className="mono muted">{view.academy_formula}</p>
              <div className="stack-sm">
                <strong>{t("academyFormulasHeading")}</strong>
                <ul>
                  {Object.entries(view.formulas).map(([figure, sentence]) => (
                    <li key={figure} className="muted">
                      <span className="mono">{figure.replace(/_/g, " ")}</span>
                      {` — ${sentence}`}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </>
        ) : (
          <div className="empty">
            <strong>{t("academyNoneTitle")}</strong>
            <p className="muted">{view.reason}</p>
          </div>
        )}

        <p className="notice notice--warn">{limitation}</p>
      </div>
    </Panel>
  );
}
