import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { PlanTools } from "@/components/AcademyTools";
import { Panel } from "@/components/ui";
import { KeyValueGrid, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { refusalFigures, type AcademyCapabilities, type PlanView } from "@/lib/club";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";

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
export const metadata: Metadata = {
  title: "Development plan",
  description: "A child's development plan: its reviews, the progress measured from them, and the consent that lets it exist.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/club") },
};

type Props = { params: Promise<{ ident: string; plan: string }> };

export default async function AcademyPlanPage({ params }: Props) {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fclub");

  const { ident, plan } = await params;
  if (!ident || !plan || plan === "plans") notFound();

  const [result, academyRules] = await Promise.all([
    serverFetch<PlanView>(`/club/academy/${encodeURIComponent(ident)}/plans/${encodeURIComponent(plan)}`),
    serverFetch<AcademyCapabilities>("/club/academy/capabilities"),
  ]);
  if (!result.ok) {
    if (result.status === 404) notFound();
    return <WorldUnavailable detail={refusalFigures(result.error.details).join(" · ")} message={`${result.error.code}: ${result.error.message}`} title="Development plan" />;
  }

  const view = result.data;
  const progress = view.progress;
  const axes = academyRules.ok ? academyRules.data.axes : [];
  const range: [number, number] = academyRules.ok ? academyRules.data.rating_range : [0, 100];

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: `/club/${encodeURIComponent(view.organization)}`, label: `Back to ${view.organization}` }}
        eyebrow={`${view.plan.status} · opened ${view.plan.created_at.slice(0, 10)} · every ${view.plan.review_weeks} weeks`}
        lede={`${view.player.name} is ${view.player.age} today and was ${view.plan.age_at_open} when this plan opened. ${view.aged_past_minority ? "They have passed the minority threshold since, which changes nothing already written." : ""}`}
        provenance={{ data_origin: view.plan.data_origin, is_demo_data: view.plan.is_demo_data }}
        title={`Plan for ${view.player.name}`}
      />

      <Panel eyebrow={`${view.author.display_name} (${view.author.role}) · your standing: ${view.your_standing.role}`} title="Who this plan belongs to">
        <KeyValueGrid
          rows={[
            ["Child", <Link className="world-link" href={view.player.path} key="child">{view.player.name}</Link>],
            ["Age now / at open", `${view.player.age} / ${view.plan.age_at_open}`],
            ["Minor at open", String(view.plan.minor_at_open)],
            ["Position", view.player.position],
            ["World rating", view.player.overall],
            ["Potential", view.player.potential],
            ["Sheet", view.team ?? "not tied to one team"],
            ["Curriculum", view.curriculum ?? "none named"],
            ["Read through", view.your_standing.read_through],
            ["Scopes held on this child", view.your_standing.scopes_held.join(", ") || "none"],
          ]}
        />
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          {view.figures_from}
        </p>
      </Panel>

      <Panel eyebrow="no column stores any of this — it is arithmetic over the reviews below" title="Progress">
        <KeyValueGrid
          rows={[
            ["Reviews filed", progress.assessments],
            ["Opened on / days open", `${progress.opened_on} · ${progress.plan_days_open}`],
            ["First review / latest", `${progress.first_assessed_on ?? "none"} · ${progress.last_assessed_on ?? "none"}`],
            ["Span measured", `${progress.span_days} days`],
            ["Due by cadence / behind", `${progress.reviews_due_by_cadence} · ${progress.reviews_behind}`],
            ["Days since review / due in", `${progress.days_since_review} · ${progress.due_in_days}`],
            ["Overall first / last", `${progress.overall_first ?? "—"} · ${progress.overall_last ?? "—"}`],
            ["Overall change", progress.overall_change ?? "not a direction yet"],
          ]}
        />
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Axis</th>
                <th scope="col">Mean over this plan</th>
                <th scope="col">Change first → last</th>
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
        {progress.axis_change_unrated_at_one_end.length > 0 && (
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            Rated at one end of the history and not the other, so no change is claimed for: {progress.axis_change_unrated_at_one_end.join(", ")}.
          </p>
        )}
        {progress.one_review_is_not_a_direction && (
          <div className="notice notice--warn" data-honest="one review">
            <p style={{ margin: 0 }}>
              {progress.assessments} review — a direction cannot be measured from one point, so `overall_change` and every axis change are null on this page.
            </p>
          </div>
        )}
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
          {progress.measured_from} {progress.not_a_column}
        </p>
      </Panel>

      <Panel eyebrow={`${view.assessments.length} review(s) filed`} title="Assessments">
        {view.assessments.length === 0 ? (
          <div className="empty">
            <strong>No review yet</strong>
            <p className="muted">The cadence above is measured against the plan&apos;s own age, so a plan can already be behind before its first row exists.</p>
          </div>
        ) : (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Assessed on</th>
                  {axes.map((axis) => (
                    <th key={axis} scope="col">
                      {axis}
                    </th>
                  ))}
                  <th scope="col">Mean of rated axes</th>
                  <th scope="col">World rating that day</th>
                  <th scope="col">Not rated</th>
                  <th scope="col">Strengths / areas / next</th>
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
                    <td className="num">{row.mean_rating}</td>
                    <td className="num">{row.overall_observed}</td>
                    <td className="muted">{row.axes_missing.join(", ") || "—"}</td>
                    <td className="muted" style={{ fontSize: "0.8rem" }}>
                      {row.strengths || "—"} / {row.areas || "—"} / {row.next_focus || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {view.assessments[0] && <p className="muted" style={{ fontSize: "0.82rem" }}>{view.assessments[0].measured_from}</p>}
      </Panel>

      <Panel eyebrow={`${view.feedback.length} note(s) · ${view.withheld.coach_feedback} of them not shown to you`} title="Coach feedback">
        {view.feedback.length === 0 ? (
          <p className="muted">Nothing written to this plan yet.</p>
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
          <p style={{ margin: 0 }}>
            {view.withheld.rule}
          </p>
          {view.withheld.video_evidence > 0 && <p className="muted" style={{ margin: "0.3rem 0 0", fontSize: "0.82rem" }}>{view.withheld.why_video}</p>}
        </div>
      </Panel>

      <Panel eyebrow={`${view.evidence.length} clip citation(s) · a citation is a label and a window, not a way to watch`} title="Video evidence">
        {view.evidence.length === 0 ? (
          <p className="muted">No footage is cited by this plan.</p>
        ) : (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Label</th>
                  <th scope="col">Window</th>
                  <th scope="col">Clip</th>
                  <th scope="col">Linked review</th>
                  <th scope="col">Cited</th>
                </tr>
              </thead>
              <tbody>
                {view.evidence.map((row) => (
                  <tr data-evidence={row.id} key={row.id}>
                    <td>{row.label || "—"}</td>
                    <td className="num">
                      {row.t_start}–{row.t_end}s ({row.window_seconds}s)
                    </td>
                    <td className="muted">{row.clip ? `${row.clip.title} · ${row.clip.duration_s}s` : row.clip_present ? "row gone" : "no clip row"}</td>
                    <td className="mono">{row.assessment_id ?? "—"}</td>
                    <td className="muted">{row.linked_at?.slice(0, 10) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {view.evidence[0] && <p className="muted" style={{ fontSize: "0.82rem" }}>{view.evidence[0].playback}</p>}
      </Panel>

      <Panel eyebrow={`${view.integrity.clean ? "checks clean" : `${view.integrity.problems.length} problem(s)`} · ${Object.entries(view.integrity.checked).map(([key, value]) => `${value} ${key}`).join(", ")}`} title="The consent this plan stands on">
        <p className="muted" style={{ fontSize: "0.84rem" }}>
          {view.integrity.rule}
        </p>
        {view.consented_by && (
          <p className="mono" style={{ fontSize: "0.8rem" }}>
            consent {view.consented_by.consent} · guardian {view.consented_by.guardian} · scopes {view.consented_by.scopes.join(", ")}
          </p>
        )}
        {view.not_stored && (
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            never stored here: {view.not_stored}
          </p>
        )}
      </Panel>

      <Panel eyebrow={`${axes.length} published axes · ${range[0]}–${range[1]} · the write doors of this plan`} title="Write to this plan">
        <PlanTools axes={axes} ident={view.organization} plan={view.plan.id} range={range} />
      </Panel>

      <Panel eyebrow={`${view.limitations.length} limits the API states on this response`} title="What this tier does not do">
        <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
          {view.limitations.map((line) => (
            <li className="muted" key={line} style={{ fontSize: "0.86rem" }}>
              {line}
            </li>
          ))}
        </ul>
      </Panel>

      <Provenance extra={<span className="chip mono">{view.your_standing.staff ? "staff copy" : "guardian copy"}</span>} provenance={{ data_origin: view.plan.data_origin, is_demo_data: view.plan.is_demo_data }} />
    </div>
  );
}
