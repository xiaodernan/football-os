import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

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
  const tn = await getTranslations("nav");
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
            [t("kvAxisChange"), progress.axis_change ? Object.entries(progress.axis_change).map(([k, v]) => `${k}: ${v}`).join(", ") : "—"],
            [t("kvOneReviewNotDirection"), progress.one_review_is_not_a_direction ? t("yes") : t("no")],
            [t("kvNotAColumn"), progress.not_a_column ?? "—"],
            [t("kvFocusItemsGoals"), `${caps?.focus_items_max ?? "—"} / {caps?.goals_max ?? "—"}`],
            [t("kvFeedbackAssessment"), `${caps?.feedback_max ?? "—"} / {caps?.assessment_text_max ?? "—"} characters`],
            [t("kvPlanStatuses"), caps?.plan_statuses?.join(", ") ?? "—"],
          ]}
        />
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          {Object.entries(progress.formulas).map(([k, v]) => `${k}: ${v}`).join("; ")}
        </p>
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          {view.limitations.join("; ")}
        </p>
      </Panel>

      <Panel eyebrow={t("reviewsEyebrow", { count: view.assessments.length })} title={t("reviewsTitle")}>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("tableHeaderReview")}</th>
                <th scope="col">{t("tableHeaderDate2")}</th>
                <th scope="col">{t("tableHeaderCoach2")}</th>
                <th scope="col">{t("tableHeaderOverall")}</th>
                <th scope="col">{t("tableHeaderAxes")}</th>
                <th scope="col">{t("tableHeaderGoals")}</th>
                <th scope="col">{t("tableHeaderFeedback")}</th>
                <th scope="col">{t("tableHeaderAssessment")}</th>
                <th scope="col">{tc("delete")}</th>
              </tr>
            </thead>
            <tbody>
              {view.assessments.map((row) => (
                <tr data-review={row.id} key={row.id}>
                  <td className="mono">{row.id.slice(0, 8)}…</td>
                  <td className="mono">{row.assessed_on.slice(0, 16)}</td>
                  <td>{row.areas || "—"}</td>
                  <td className="num">{row.overall_observed ?? "—"}</td>
                  <td className="muted">{Object.keys(row.ratings).join(", ") || "—"}</td>
                  <td className="muted">{row.strengths || "—"}</td>
                  <td className="muted" style={{ fontSize: "0.8rem" }}>{view.feedback.length > 0 ? view.feedback[0].message : "—"}</td>
                  <td className="muted" style={{ fontSize: "0.8rem" }}>{row.areas || "—"}</td>
                  <td>
                    <EraseRow action="review-erase" label={tc("delete")} path={`/club/academy/${encodeURIComponent(ident)}/plans/${encodeURIComponent(plan)}/reviews/${encodeURIComponent(row.id)}`} what="review" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          {Object.entries(progress.formulas).map(([k, v]) => `${k}: ${v}`).join("; ")}
        </p>
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          {view.limitations.join("; ")}
        </p>
      </Panel>

      <Provenance extra={<span className="chip mono">{t("provenanceExtraPlan")}</span>} provenance={{ data_origin: view.plan.data_origin, is_demo_data: view.plan.is_demo_data }} />
    </div>
  );
}