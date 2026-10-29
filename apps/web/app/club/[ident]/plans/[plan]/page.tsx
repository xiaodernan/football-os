import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { AcademySharePanel } from "@/components/AcademySharePanel";
import { PlanTools } from "@/components/AcademyTools";
import { Panel } from "@/components/ui";
import { KeyValueGrid, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { refusalFigures, type AcademyCapabilities, type PlanView } from "@/lib/club";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import { EraseRow } from "@/components/SessionReportTools";

import "../../../../../styles/tactics.css";

export const dynamic = "force-dynamic";

/**
 * One child's development plan, printed the way §40 asks for it: every figure with the arithmetic that
 * produced it beside it.
 *
 * The route is not a convention this page invented. `GET …/academy/{ident}/plans` publishes
 * `path: "/club/{slug}/plans/{id}"` on each row, so the API names this URL and a link it sends a visitor
 * to must answer.
 *
 * `progress` is the reason to read the payload rather than a summary of it. There is no `progress` column
 * in any table — the tier stores reviews and nothing else — so each number here is computed from this
 * plan's own rows on the request that shows it, and `formulas` states the computation in the same response.
 * Where the history cannot support a figure, the API sends `null` and a sentence saying why, and both are
 * printed: a plan with one review has a change of nothing, and `one_review_is_not_a_direction` is the
 * answer's own words for that.
 */
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("club");
  return {
    title: t("planMetaTitle"),
    description: t("planMetaDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/club") },
  };
}

type Props = { params: Promise<{ ident: string; plan: string }> };

export default async function AcademyPlanPage({ params }: Props) {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fclub");

  const t = await getTranslations("club");
  const tc = await getTranslations("common");
  const { ident, plan } = await params;
  if (!ident || !plan || plan === "plans") notFound();

  const [result, academyRules] = await Promise.all([
    serverFetch<PlanView>(`/club/academy/${encodeURIComponent(ident)}/plans/${encodeURIComponent(plan)}`),
    serverFetch<AcademyCapabilities>("/club/academy/capabilities"),
  ]);
  if (!result.ok) {
    if (result.status === 404) notFound();
    return <WorldUnavailable detail={refusalFigures(result.error.details).join(" · ")} message={`${result.error.code}: ${result.error.message}`} title={t("planErrorTitle")} />;
  }

  const view = result.data;
  const progress = view.progress;
  const caps = academyRules.ok ? academyRules.data : null;
  const axes = caps?.axes ?? [];
  const range: [number, number] = caps?.rating_range ?? [0, 100];

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: `/club/${encodeURIComponent(view.organization)}`, label: t("planBackLabel", { org: view.organization }) }}
        eyebrow={t("planEyebrow", { status: view.plan.status, date: view.plan.created_at.slice(0, 10), weeks: view.plan.review_weeks })}
        lede={t("planLede", { name: view.player.name, age: view.player.age, ageAtOpen: view.plan.age_at_open, minorNote: view.aged_past_minority ? t("minorNotePassed") : "" })}
        provenance={{ data_origin: view.plan.data_origin, is_demo_data: view.plan.is_demo_data }}
        title={t("planTitle", { name: view.player.name })}
      />

      <Panel eyebrow={t("panelWhoEyebrow", { author: view.author.display_name, role: view.author.role, standing: view.your_standing.role })} title={t("panelWhoTitle")}>
        <KeyValueGrid
          rows={[
            [t("kvChild"), <Link className="world-link" href={view.player.path} key="child">{view.player.name}</Link>],
            [t("kvAgeNowOpen"), `${view.player.age} / ${view.plan.age_at_open}`],
            [t("kvMinorAtOpen"), String(view.plan.minor_at_open)],
            [t("kvPosition"), view.player.position],
            [t("kvWorldRating"), view.player.overall],
            [t("kvPotential"), view.player.potential],
            [t("kvSheet"), view.team ?? t("notTiedToOneTeam")],
            [t("kvCurriculum"), view.curriculum ?? t("noneNamed")],
            [t("kvReadThrough"), view.your_standing.read_through],
            [t("kvScopesHeld"), view.your_standing.scopes_held.join(", ") || t("noneNamed")],
          ]}
        />
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          {view.figures_from}
        </p>
      </Panel>

      <Panel eyebrow={t("progressEyebrow")} title={t("progressTitle")}>
        <KeyValueGrid
          rows={[
            [t("kvReviewsFiled"), progress.assessments],
            [t("kvOpenedDaysOpen"), `${progress.opened_on} · ${progress.plan_days_open}`],
            [t("kvFirstLatest"), `${progress.first_assessed_on ?? t("noneNamed")} · ${progress.last_assessed_on ?? t("noneNamed")}`],
            [t("kvSpanMeasured"), `${progress.span_days} days`],
            [t("kvDueCadenceBehind"), `${progress.reviews_due_by_cadence} · ${progress.reviews_behind}`],
            [t("kvDaysSinceDue"), `${progress.days_since_review} · ${progress.due_in_days}`],
            [t("kvOverallFirstLast"), `${progress.overall_first ?? "—"} · ${progress.overall_last ?? "—"}`],
            [t("kvOverallChange"), progress.overall_change ?? "—"],
            [t("kvAxisChange"), progress.axis_change ? Object.entries(progress.axis_change).map(([k, v]) => `${k}: ${v}`).join(", ") : "—"],
            [t("kvOneReviewNotDirection"), progress.one_review_is_not_a_direction ? tc("yes") : tc("no")],
            [t("kvNotAColumn"), progress.not_a_column ?? "—"],
            [t("kvFocusItemsGoals"), `${caps?.focus_items_max ?? "—"} / {caps?.goals_max ?? "—"}`],
            [t("kvFeedbackAssessment"), `${caps?.feedback_max ?? "—"} / {caps?.assessment_text_max ?? "—"} characters`],
            [t("kvPlanStatuses"), caps?.plan_statuses?.join(", ") ?? "—"],
          ]}
          />
        {progress.assessments === 1 && (
          <div className="notice notice--warn" data-honest="one review">
            <p style={{ margin: 0 }}>{t("oneReviewNotice", { count: progress.assessments })}</p>
          </div>
        )}
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("tableHeaderAxis")}</th>
                <th scope="col">{t("tableHeaderAxisMean")}</th>
                <th scope="col">{t("tableHeaderAxisChange")}</th>
              </tr>
            </thead>
            <tbody>
              {axes.map((axis) => (
                <tr data-axis={axis} key={axis}>
                  <td className="mono">{axis}</td>
                  <td className="num">{progress.axis_means?.[axis] ?? "—"}</td>
                  <td className="num">{progress.axis_change?.[axis] ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {progress.axis_change_unrated_at_one_end?.length > 0 && (
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            {t("axisUnratedOneEnd", { axes: progress.axis_change_unrated_at_one_end.join(", ") })}
          </p>
        )}
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          {t("progressMeasuredFrom", { source: progress.measured_from })}
        </p>
        <dl className="world-kv">
          {Object.entries(progress.formulas).map(([figure, formula]) => (
            <div className="world-kv__row" data-formula={figure} key={figure}>
              <dt className="mono">{figure}</dt>
              <dd style={{ textAlign: "left" }} className="muted">
                {formula}
              </dd>
            </div>
          ))}
        </dl>
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          {view.limitations.join("; ")}
        </p>
      </Panel>

      <Panel eyebrow={t("reviewsEyebrow", { count: view.assessments.length })} title={t("reviewsTitle")}>
        {view.assessments.length === 0 ? (
          <div className="empty">
            <strong>{t("noReviewYet")}</strong>
            <p className="muted">{t("noReviewYetNote")}</p>
          </div>
        ) : (
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("tableHeaderAssessedOn")}</th>
                {axes.map((axis) => (
                  <th key={axis} scope="col">
                    {axis}
                  </th>
                ))}
                <th scope="col">{t("tableHeaderMeanRated")}</th>
                <th scope="col">{t("tableHeaderWorldRating")}</th>
                <th scope="col">{t("tableHeaderNotRated")}</th>
                <th scope="col">{t("tableHeaderStrengthsAreasNext")}</th>
                <th scope="col">{tc("delete")}</th>
              </tr>
            </thead>
            <tbody>
              {view.assessments.map((row) => (
                <tr data-assessment={row.id} key={row.id}>
                  <td className="mono">{row.assessed_on}</td>
                  {axes.map((axis) => (
                    <td className="num" key={axis}>
                      {row.ratings[axis] ?? "—"}
                    </td>
                  ))}
                  <td className="num">{row.mean_rating ?? "—"}</td>
                  <td className="num">{row.overall_observed ?? "—"}</td>
                  <td className="muted">{row.axes_missing?.join(", ") || "—"}</td>
                  <td className="muted" style={{ fontSize: "0.8rem" }}>
                    {row.strengths || "—"} / {row.areas || "—"} / {row.next_focus || "—"}
                  </td>
                  <td>
                    <EraseRow action="review-erase" label={tc("delete")} path={`/club/academy/${encodeURIComponent(ident)}/plans/${encodeURIComponent(plan)}/reviews/${encodeURIComponent(row.id)}`} whatKey="rowReview" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        )}
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          {Object.entries(progress.formulas).map(([k, v]) => `${k}: ${v}`).join("; ")}
        </p>
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          {view.limitations.join("; ")}
        </p>
      </Panel>

      <Panel
        eyebrow={t("feedbackEyebrow", { count: view.feedback.length, withheld: view.withheld.coach_feedback })}
        title={t("feedbackTitle")}
      >
        {view.feedback.length === 0 ? (
          <p className="muted">{t("feedbackEmpty")}</p>
        ) : (
          <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
            {view.feedback.map((row) => (
              <li data-feedback={row.id} key={row.id}>
                <span className="mono" style={{ fontSize: "0.78rem" }}>
                  {row.written_at.slice(0, 16)} · {row.seen_as}
                </span>
                <div>{row.message}</div>
              </li>
            ))}
          </ul>
        )}
        <div className="notice" data-withheld={view.withheld.coach_feedback}>
          <p style={{ margin: 0 }}>{view.withheld.rule}</p>
          {view.withheld.video_evidence > 0 && (
            <p className="muted" style={{ margin: "0.3rem 0 0", fontSize: "0.82rem" }}>
              {view.withheld.why_video}
            </p>
          )}
        </div>
      </Panel>

      <Panel
        eyebrow={t("evidenceEyebrow", { count: view.evidence.length })}
        title={t("evidenceTitle")}
      >
        {view.evidence.length === 0 ? (
          <p className="muted">{t("evidenceEmpty")}</p>
        ) : (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("tableHeaderLabel")}</th>
                  <th scope="col">{t("tableHeaderWindow")}</th>
                  <th scope="col">{t("tableHeaderClip")}</th>
                  <th scope="col">{t("tableHeaderLinkedReview")}</th>
                  <th scope="col">{t("tableHeaderCited")}</th>
                </tr>
              </thead>
              <tbody>
                {view.evidence.map((row) => (
                  <tr data-evidence={row.id} key={row.id}>
                    <td>{row.label || "—"}</td>
                    <td className="num">
                      {row.t_start}–{row.t_end}s ({row.window_seconds}s)
                    </td>
                    <td className="muted">
                      {row.clip
                        ? `${row.clip.title} · ${row.clip.duration_s}s`
                        : row.clip_present
                          ? t("clipGone")
                          : t("noClipRow")}
                    </td>
                    <td className="mono">{row.assessment_id ?? "—"}</td>
                    <td className="muted">{row.linked_at?.slice(0, 10) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {view.evidence[0] && (
          <p className="muted" style={{ fontSize: "0.82rem" }}>{view.evidence[0].playback}</p>
        )}
      </Panel>

      <Panel
        eyebrow={t("consentEyebrow", {
          checks: view.integrity.clean ? t("checksClean") : t("problemCount", { count: view.integrity.problems.length }),
          checked: Object.entries(view.integrity.checked).map(([key, value]) => `${value} ${key}`).join(", "),
        })}
        title={t("consentTitle")}
      >
        <p className="muted" style={{ fontSize: "0.84rem" }}>
          {view.integrity.rule}
        </p>
        {view.consented_by && (
          <p className="mono" style={{ fontSize: "0.8rem" }}>
            {t("consentLine", {
              consent: view.consented_by.consent,
              guardian: view.consented_by.guardian,
              scopes: view.consented_by.scopes.join(", "),
            })}
          </p>
        )}
        {view.not_stored && (
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            {t("neverStoredHere", { values: view.not_stored })}
          </p>
        )}
      </Panel>

      <AcademySharePanel ident={view.organization} plan={view.plan.id} />

      <Panel
        eyebrow={t("writePanelEyebrow", { count: axes.length, from: range[0], to: range[1] })}
        title={t("writePanelTitle")}
      >
        <PlanTools axes={axes} ident={view.organization} plan={view.plan.id} range={range} />
      </Panel>

      <Provenance extra={<span className="chip mono">{t("provenanceExtraPlan")}</span>} provenance={{ data_origin: view.plan.data_origin, is_demo_data: view.plan.is_demo_data }} />
    </div>
  );
}