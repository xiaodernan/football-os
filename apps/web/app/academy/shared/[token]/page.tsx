import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { KeyValueGrid, WorldHead, WorldUnavailable } from "@/components/world";
import { Panel } from "@/components/ui";
import type { PublicPlan } from "@/lib/club";
import { sharedMetadata } from "@/lib/site";
import { serverFetch } from "@/lib/server";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ token: string }> };

/**
 * §40's development plan handed to somebody without an account — the other half of Phase 5's share work.
 *
 * The page is a live read, not a copy: the API recomputes `progress` from the plan's own review rows on every
 * request, so a review filed after the link was minted is here and a review erased from the private side is gone.
 * What the page does *not* carry is the point of the tier: no name, no exact age, no position, no rating, no team,
 * no coach, no free text and no clip. `redacted` prints every omission with its reason, because a minimised page
 * and a thin page look alike from outside and only one of them is a decision.
 *
 * A link is a door, not a publication: noindex, and the canonical belongs to `/club`, the surface that mints the
 * next one.
 */
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { token } = await params;
  const t = await getTranslations("club");
  return sharedMetadata({
    title: t("sharedPlanMetaTitle"),
    description: t("sharedPlanMetaDescription"),
    sharePath: `/academy/shared/${encodeURIComponent(token)}`,
    canonicalPath: "/club",
  });
}

export default async function SharedPlanPage({ params }: Props) {
  const { token } = await params;
  const t = await getTranslations("club");
  const tc = await getTranslations("common");
  const tn = await getTranslations("nav");
  const result = await serverFetch<PublicPlan>(`/club/academy/shared/${encodeURIComponent(token)}`);

  if (!result.ok) {
    if (result.status === 404) notFound();
    return (
      <WorldUnavailable
        detail={result.error.message}
        message={t("sharedPlanUnavailable")}
        title={t("sharedPlanUnavailableTitle")}
      />
    );
  }

  const view = result.data;
  const progress = view.progress;
  const axes = Object.keys(progress.axis_means);
  const opened = view.shared.opened_at.slice(0, 16);

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/", label: tn("home") }}
        eyebrow={t("sharedPlanEyebrow", { organization: view.shared.organization.name, opened })}
        lede={t("sharedPlanLede")}
        title={t("sharedPlanTitle")}
      />

      <Panel eyebrow={t("sharedPlanCountsEyebrow", { stage: view.plan.stage })} title={t("sharedPlanCountsTitle")}>
        <KeyValueGrid
          rows={[
            [t("sharedPlanKVStatus"), view.plan.status],
            [t("sharedPlanKVFocus"), view.plan.focus.join(", ") || t("noneNamed")],
            [t("sharedPlanKVGoals"), view.plan.goals.map((goal) => `${goal.title} (${goal.measure} by ${goal.by})`).join("; ") || t("noneNamed")],
            [t("sharedPlanKVReviewWeeks"), progress.reviews_due_by_cadence],
            [t("sharedPlanKVStage"), view.plan.stage],
            [t("sharedPlanKVMinor"), String(view.plan.minor_at_open)],
            [t("sharedPlanKVFeedback"), `${view.counts.feedback} · ${view.counts.feedback_shared_with_guardian}`],
            [t("sharedPlanKVClip"), view.counts.evidence],
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
            [t("kvOverallFirstLast"), `${progress.overall_first ?? "—"} · ${progress.overall_last ?? "—"}`],
            [t("kvOverallChange"), progress.overall_change ?? "—"],
            [t("kvAxisChange"), Object.entries(progress.axis_change).map(([axis, change]) => `${axis}: ${change}`).join(", ") || "—"],
            [t("kvOneReviewNotDirection"), progress.one_review_is_not_a_direction ? tc("yes") : tc("no")],
            [t("kvNotAColumn"), progress.not_a_column],
          ]}
        />
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
                  <td className="num">{progress.axis_means[axis] ?? "—"}</td>
                  <td className="num">{progress.axis_change[axis] ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          {t("progressMeasuredFrom", { source: progress.measured_from })}
        </p>
      </Panel>

      <Panel eyebrow={t("sharedPlanReviewsEyebrow", { count: view.assessments.length })} title={t("reviewsTitle")}>
        {view.assessments.length === 0 ? (
          <p className="muted">{t("sharedPlanNoReview")}</p>
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
                </tr>
              </thead>
              <tbody>
                {view.assessments.map((row) => (
                  <tr data-assessment={row.assessed_on} key={row.assessed_on}>
                    <td className="mono">{row.assessed_on}</td>
                    {axes.map((axis) => (
                      <td className="num" key={axis}>
                        {row.ratings[axis] ?? "—"}
                      </td>
                    ))}
                    <td className="num">{row.mean_rating ?? "—"}</td>
                    <td className="num">{row.overall_observed}</td>
                    <td className="muted">{row.axes_missing.join(", ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel eyebrow={t("sharedPlanRedactedEyebrow", { count: view.redacted.length })} title={t("sharedPlanRedactedTitle")}>
        <p className="muted" style={{ fontSize: "0.84rem" }}>
          {t("sharedPlanRedactedLede")}
        </p>
        <ul className="stack-sm" data-redacted style={{ margin: 0, paddingLeft: "1.1rem" }}>
          {view.redacted.map((item) => (
            <li className="muted" data-redacted-field={item.field} key={item.field} style={{ fontSize: "0.86rem" }}>
              <span className="mono">{item.field}</span> — {item.why}
            </li>
          ))}
        </ul>
        <p className="muted" style={{ fontSize: "0.84rem" }}>
          {view.shared.note}
        </p>
      </Panel>

      <p className="muted" style={{ fontSize: "0.84rem" }}>
        {t("sharedPlanNeedOwn")} <Link className="world-link" href="/club">{t("sharedPlanOpenClub")}</Link>.
      </p>
    </div>
  );
}
