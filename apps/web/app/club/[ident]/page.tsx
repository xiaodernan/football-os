import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { AcademyTools, ConsentTable } from "@/components/AcademyTools";
import { TenantTools } from "@/components/ClubTools";
import { Panel } from "@/components/ui";
import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import {
  refusalFigures,
  type AcademyCapabilities,
  type ConsentList,
  type CurriculumList,
  type OrganizationView,
  type PlanList,
} from "@/lib/club";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";

import "../../../styles/tactics.css";

export const dynamic = "force-dynamic";

/**
 * One tenant's page: who stands in it, what their standing holds, which sheets exist and which children
 * have a guardian's yes.
 *
 * Two things shape it. The first is §39's isolation sentence, printed rather than paraphrased: a member of
 * one organisation reads nothing of another, and an outsider's knock on this URL is answered with
 * `no_such_organization` — a 404 that this page renders as *not found*, never as *forbidden*, because a
 * 403 here would confirm the tenant exists. The second is §40's: a minor on a sheet with no consent row is
 * a tenant that cannot write a plan for them, so the consent table sits on the same screen as the squad
 * that needs it, with `under_18` counted from the sheets beside it.
 *
 * The academy panels are re-read from the API on every visit. Where the caller's standing does not reach a
 * door, the refusal is printed as a refusal — an empty list and a refused read are different facts, and
 * collapsing them would be the page's own lie.
 */
export const metadata: Metadata = {
  title: "Organisation",
  description: "A club tenant's members, standings, team sheets, guardian consents and development plans.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/club") },
};

type Props = { params: Promise<{ ident: string }> };

/** A door the caller does not reach, shown as the answer it is. */
function Refused({ label, status, message, figures }: { label: string; status: number; message: string; figures: string[] }) {
  return (
    <div className="notice notice--warn" data-refused={label}>
      <p style={{ margin: 0 }}>
        <span className="mono">{status}</span> — {message}
      </p>
      {figures.length > 0 && (
        <p className="muted mono" style={{ fontSize: "0.8rem", margin: "0.35rem 0 0" }}>
          {figures.join(" · ")}
        </p>
      )}
    </div>
  );
}

export default async function ClubTenantPage({ params }: Props) {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fclub");

  const { ident } = await params;
  if (!ident || ident.length > 160 || ident === "rules") notFound();

  const first = await serverFetch<OrganizationView>(`/club/${encodeURIComponent(ident)}`);
  if (!first.ok) {
    if (first.status === 404) notFound();
    return <WorldUnavailable detail={refusalFigures(first.error.details).join(" · ")} message={first.error.message} title="Organisation" />;
  }
  const view = first.data;

  // The academy doors are read after the tenant itself resolves: a stranger never reaches them, and the
  // caller's standing decides which of them answer at all.
  const [consents, curricula, plans, academyRules] = await Promise.all([
    serverFetch<ConsentList>(`/club/academy/${encodeURIComponent(ident)}/consents`),
    serverFetch<CurriculumList>(`/club/academy/${encodeURIComponent(ident)}/curricula`),
    serverFetch<PlanList>(`/club/academy/${encodeURIComponent(ident)}/plans`),
    serverFetch<AcademyCapabilities>("/club/academy/capabilities"),
  ]);

  const minors = view.teams.reduce((sum, team) => sum + team.minors_on_sheet, 0);

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/club", label: "My clubs" }}
        eyebrow={`${view.organization.slug} · you are ${view.my_grant.role} here · ${view.my_grant.permissions.length} of ${view.rules.matrix.permissions.length} rights`}
        lede={view.my_grant.why}
        provenance={{ data_origin: view.data_origin, is_demo_data: view.is_demo_data }}
        title={view.organization.name}
      />

      <Panel eyebrow={`${view.counts.active_members} active member(s) · ${view.counts.owners} owner(s) · ${view.counts.teams} of ${view.rules.max_teams_per_organization} sheets · ${view.counts.players_on_sheets} squad rows`} title="What this tenant holds">
        <div className="grid grid-2">
          <div>
            <dl className="world-kv">
              <div className="world-kv__row">
                <dt>Kind</dt>
                <dd>{view.organization.kind}</dd>
              </div>
              <div className="world-kv__row">
                <dt>Country</dt>
                <dd className="mono">{view.organization.country || "—"}</dd>
              </div>
              <div className="world-kv__row">
                <dt>Default visibility</dt>
                <dd>{view.organization.visibility_default}</dd>
              </div>
              <div className="world-kv__row">
                <dt>Opened</dt>
                <dd className="mono">{view.organization.created_at.slice(0, 16)} UTC</dd>
              </div>
              <div className="world-kv__row">
                <dt>Invited, not answered</dt>
                <dd className="num">{view.counts.invited_members}</dd>
              </div>
              <div className="world-kv__row">
                <dt>Members under 18 on a sheet</dt>
                <dd className="num">{minors}</dd>
              </div>
            </dl>
          </div>
          <div className="stack">
            <div className={view.integrity.clean ? "notice" : "notice notice--warn"} data-integrity={String(view.integrity.clean)}>
              <p style={{ margin: 0 }}>
                Integrity check: {view.integrity.clean ? "clean" : `${view.integrity.problems.length} problem(s)`} over {Object.entries(view.integrity.checked).map(([key, value]) => `${value} ${key}`).join(", ")}.
              </p>
              {view.integrity.problems.map((problem) => (
                <p className="mono" key={problem} style={{ fontSize: "0.8rem", margin: "0.3rem 0 0" }}>
                  {problem}
                </p>
              ))}
            </div>
            <p className="muted" style={{ fontSize: "0.82rem" }}>
              {view.integrity.rule}
            </p>
            <p className="muted" style={{ fontSize: "0.82rem" }}>
              {view.isolation_rule}
            </p>
          </div>
        </div>
      </Panel>

      <Panel eyebrow={`${view.members.length} row(s) · a standing changes only here, and only a row can change it`} title="Members and standings">
        <TenantTools ident={view.organization.slug} members={view.members} rules={view.rules} teams={view.teams} />
      </Panel>

      <Panel eyebrow={consents.ok ? `${consents.data.total} consent row(s) · ${consents.data.under_18} child(ren) under ${academyRules.ok ? academyRules.data.minor_age : 18} on a sheet` : "the consent door did not answer"} title="Guardian consent">
        {consents.ok ? (
          <>
            <ConsentTable consents={consents.data} ident={view.organization.slug} />
            <p className="muted" style={{ fontSize: "0.82rem" }}>
              {consents.data.rule}
            </p>
          </>
        ) : (
          <Refused figures={refusalFigures(consents.error.details)} label="consents" message={consents.error.message} status={consents.status} />
        )}
        {academyRules.ok && (
          <AcademyTools
            ident={view.organization.slug}
            scopes={academyRules.data.consent_scopes}
            sheets={
              // One row per child, however many sheets carry them: the first team named wins, and a
              // duplicate option would only let a guardian press the same button twice.
              Object.values(
                view.teams.reduce<Record<string, { age: number; is_minor: boolean; name: string; slug: string; team: string }>>((byChild, team) => {
                  for (const row of team.squad) {
                    if (!byChild[row.slug]) byChild[row.slug] = { age: row.age, is_minor: row.is_minor, name: row.name, slug: row.slug, team: team.name };
                  }
                  return byChild;
                }, {}),
              )
            }
          />
        )}
      </Panel>

      <Panel eyebrow={curricula.ok ? `${curricula.data.total} of ${curricula.data.limit} curricula · no curriculum names a child` : "the curriculum door did not answer"} title="Training curricula">
        {curricula.ok ? (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Curriculum</th>
                  <th scope="col">Age band</th>
                  <th scope="col">Weekly minutes</th>
                  <th scope="col">Phases</th>
                  <th scope="col">Unassigned</th>
                  <th scope="col">Plans using it</th>
                </tr>
              </thead>
              <tbody>
                {curricula.data.items.map((row) => (
                  <tr data-curriculum={row.id} key={row.id}>
                    <td>{row.name}</td>
                    <td className="muted">{row.age_group}</td>
                    <td className="num">{row.weekly_minutes}</td>
                    <td className="num">
                      {row.phase_count} · {row.phase_minutes} min
                    </td>
                    <td className="num">{row.unassigned_minutes}</td>
                    <td className="num">{row.plans_using_it}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {curricula.data.items.map((row) => (
              <p className="muted" data-formula={row.id} key={`formula-${row.id}`} style={{ fontSize: "0.8rem" }}>
                {row.name}: {row.formulas.unassigned_minutes}
              </p>
            ))}
          </div>
        ) : (
          <Refused figures={refusalFigures(curricula.error.details)} label="curricula" message={curricula.error.message} status={curricula.status} />
        )}
        {curricula.ok && <p className="muted" style={{ fontSize: "0.82rem" }}>{curricula.data.rule}</p>}
      </Panel>

      <Panel eyebrow={plans.ok ? `${plans.data.total} plan(s), ${plans.data.minors_in_list} of them a child under ${academyRules.ok ? academyRules.data.minor_age : 18}'s · read through ${plans.data.read_through}` : "the plan door did not answer"} title="Development plans">
        {plans.ok ? (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Child</th>
                  <th scope="col">Age</th>
                  <th scope="col">Status</th>
                  <th scope="col">Review cadence</th>
                  <th scope="col">Reviews filed</th>
                  <th scope="col">Goals</th>
                  <th scope="col">Progress</th>
                  <th scope="col">Focus</th>
                </tr>
              </thead>
              <tbody>
                {plans.data.items.map((row) => (
                  <tr data-plan={row.id} key={row.id}>
                    <td>
                      <Link className="world-link" href={row.path}>
                        {row.player.name}
                      </Link>
                    </td>
                    <td className="num">
                      {row.player.age}
                      {row.player.is_minor && <span className="chip mono"> minor</span>}
                    </td>
                    <td>
                      <span className={row.status === "active" ? "badge badge--live" : "badge badge--demo"}>{row.status.toUpperCase()}</span>
                    </td>
                    <td className="num">every {row.review_weeks} weeks</td>
                    <td className="num">{row.assessments}</td>
                    <td className="num">{row.goals}</td>
                    <td className="num" title="null means one review or none: a direction cannot be measured from one point">
                      {row.progress ?? "not yet"}
                    </td>
                    <td className="muted">{row.focus.join(", ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted" style={{ fontSize: "0.82rem" }}>
              {plans.data.formulas.progress} {plans.data.rule}
            </p>
          </div>
        ) : (
          <Refused figures={refusalFigures(plans.error.details)} label="plans" message={plans.error.message} status={plans.status} />
        )}
      </Panel>

      <Panel eyebrow={`${view.limitations.length} limits the API states on this very response`} title="What this tier does not do">
        <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
          {view.limitations.map((line) => (
            <li className="muted" key={line} style={{ fontSize: "0.86rem" }}>
              {line}
            </li>
          ))}
        </ul>
      </Panel>

      <Provenance extra={<span className="chip mono">{view.teams.length} sheet(s), {view.counts.players_on_sheets} squad row(s) — pointers to the world&apos;s players, not copies</span>} provenance={{ data_origin: view.data_origin, is_demo_data: view.is_demo_data }} />
    </div>
  );
}
