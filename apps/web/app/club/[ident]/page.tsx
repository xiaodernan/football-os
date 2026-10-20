import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { AcademyTools, ConsentTable } from "@/components/AcademyTools";
import { TenantTools } from "@/components/ClubTools";
import { EraseNotes, EraseRow, ReportSaver, SessionRecorder } from "@/components/SessionReportTools";
import { FixtureArranger } from "@/components/MatchTools";
import { NoticeBoard } from "@/components/NoticeBoardTools";
import { Panel } from "@/components/ui";
import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import {
  refusalFigures,
  type AcademyCapabilities,
  type AccountEntitlements,
  type AnnouncementList,
  type ClubCapabilities,
  type ConsentList,
  type CurriculumList,
  type FixtureList,
  type OrganizationView,
  type PlanList,
  type ReportList,
  type SessionList,
  type TenantEntitlements,
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
 *
 * §41's two rows are here for the same reason: the session log is a table whose load column the page adds up
 * itself before believing the total beside it, and a saved report is a question whose answer the page prints
 * as the door computes it now — not as it came back the day the question was written.
 */
export const metadata: Metadata = {
  title: "Organisation",
  description: "A club tenant's members, standings, team sheets, guardian consents, development plans, its session log and the questions it keeps.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/club") },
};

type Props = { params: Promise<{ ident: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

/**
 * The host's own calendar day, because the API's `today` is `date.today()` in this same process's timezone.
 * `toISOString()` would hand the forms a UTC day, which is a different date for part of every day — and the
 * session door refuses a date in the future, so a form pre-filled from the wrong calendar would be refused
 * for a typo its own page made.
 */
function localDay(offsetDays = 0): string {
  const day = new Date(Date.now() + offsetDays * 86_400_000);
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
}

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

export default async function ClubTenantPage({ params, searchParams }: Props) {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fclub");

  const [{ ident }, query] = await Promise.all([params, searchParams]);
  const tc = await getTranslations("common");
  const t = await getTranslations("club");
  if (!ident || ident.length > 160 || ident === "rules") notFound();
  // The board's audience filter is the door's own query parameter, so the page hands it over untouched and prints
  // whatever comes back — including the 422 that says the word selected nobody. Narrowing the rows here instead
  // would publish a `total` the server never printed.
  const audience = typeof query.audience === "string" && query.audience.trim() !== "" ? query.audience : null;

  const first = await serverFetch<OrganizationView>(`/club/${encodeURIComponent(ident)}`);
  if (!first.ok) {
    if (first.status === 404) notFound();
    return <WorldUnavailable detail={refusalFigures(first.error.details).join(" · ")} message={first.error.message} title={t("tenantMetaTitle")} />;
  }
  const view = first.data;

  // The academy doors are read after the tenant itself resolves: a stranger never reaches them, and the
  // caller's standing decides which of them answer at all.
  const [consents, curricula, plans, academyRules, sessions, reports, entitlements, mine, fixtures, rulebook, notices] = await Promise.all([
    serverFetch<ConsentList>(`/club/academy/${encodeURIComponent(ident)}/consents`),
    serverFetch<CurriculumList>(`/club/academy/${encodeURIComponent(ident)}/curricula`),
    serverFetch<PlanList>(`/club/academy/${encodeURIComponent(ident)}/plans`),
    serverFetch<AcademyCapabilities>("/club/academy/capabilities"),
    serverFetch<SessionList>(`/club/academy/${encodeURIComponent(ident)}/sessions`),
    serverFetch<ReportList>(`/club/academy/${encodeURIComponent(ident)}/reports`),
    serverFetch<TenantEntitlements>(`/club/${encodeURIComponent(ident)}/entitlements`),
    serverFetch<AccountEntitlements>("/entitlements/me"),
    // §39's calendar and the rulebook that publishes its vocabulary: the arrangement form takes its sides, its
    // block lengths and the counts a side must reach from `fixture_caps`, and its day from the listing itself.
    serverFetch<FixtureList>(`/club/${encodeURIComponent(ident)}/fixtures`),
    serverFetch<ClubCapabilities>("/club/capabilities"),
    // §39's board. The listing carries its own `caps`, so the poster form is built from the door that answered
    // rather than from a second leg that might not have.
    serverFetch<AnnouncementList>(`/club/${encodeURIComponent(ident)}/announcements${audience ? `?audience=${encodeURIComponent(audience)}` : ""}`),
  ]);

  const minors = view.teams.reduce((sum, team) => sum + team.minors_on_sheet, 0);
  // The load total is the API's, and the column beside it is the API's too — so the page can add the
  // column up itself and say whether the two agree, instead of printing a sum on trust.
  const printedLoad = sessions.ok ? sessions.data.items.reduce((sum, row) => sum + row.load_units, 0) : 0;
  const loadAgrees = sessions.ok && Math.abs(printedLoad - sessions.data.total_load_units) < 0.05;
  // The meter arrives as three columns and one derived figure, so the page subtracts the two it printed and says
  // whether the third holds — `remaining` is arithmetic over a ceiling and a count, and nothing stores it.
  const meterRows = entitlements.ok ? entitlements.data.items : [];
  const meterAgrees = meterRows.length > 0 && meterRows.every((row) => row.remaining === Math.max(0, row.limit - row.used));
  // What the two write forms open with. The session form takes its date from the door that would refuse it —
  // `GET …/sessions` prints the day a `scheduled_on` is compared against — because this page is rendered once and
  // used for as long as it is open: a date read from this process's clock at render time can be yesterday by the
  // time somebody presses the button, and a form whose own default the server refuses is a bug the page caused.
  // The report window has no such rule (a window may end in the future), so it opens on the host's calendar.
  const sessionDay = sessions.ok ? sessions.data.today : localDay();
  const today = localDay();
  const defaultFrom = localDay(-30);

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/club", label: t("backLabel") }}
        eyebrow={`${view.organization.slug} · you are ${view.my_grant.role} here · ${view.my_grant.permissions.length} of ${view.rules.matrix.permissions.length} rights`}
        lede={view.my_grant.why}
        provenance={{ data_origin: view.data_origin, is_demo_data: view.is_demo_data }}
        title={view.organization.name}
      />

      <Panel eyebrow={`${view.counts.active_members} active member(s) · ${view.counts.owners} owner(s) · ${view.counts.teams} of {view.rules.max_teams_per_organization} sheets · ${view.counts.players_on_sheets} squad rows`} title={t("titleWhatTenantHolds")}>
        <div className="grid grid-2">
          <div>
            <dl className="world-kv">
              <div className="world-kv__row">
                <dt>{t("labelKind")}</dt>
                <dd>{view.organization.kind}</dd>
              </div>
              <div className="world-kv__row">
                <dt>{t("labelCountry")}</dt>
                <dd className="mono">{view.organization.country || "—"}</dd>
              </div>
              <div className="world-kv__row">
                <dt>{t("labelDefaultVisibility")}</dt>
                <dd>{view.organization.visibility_default}</dd>
              </div>
              <div className="world-kv__row">
                <dt>{t("labelOpened")}</dt>
                <dd className="mono">{view.organization.created_at.slice(0, 16)} UTC</dd>
              </div>
              <div className="world-kv__row">
                <dt>{t("labelInvitedMembers")}</dt>
                <dd className="num">{view.counts.invited_members}</dd>
              </div>
              <div className="world-kv__row">
                <dt>{t("labelMinorsOnSheet")}</dt>
                <dd className="num">{minors}</dd>
              </div>
            </dl>
          </div>
          <div className="stack">
            <div className={view.integrity.clean ? "notice" : "notice notice--warn"} data-integrity={String(view.integrity.clean)}>
              <p style={{ margin: 0 }}>
                {view.integrity.clean ? t("integrityClean", { checked: Object.entries(view.integrity.checked).map(([key, value]) => `${value} ${key}`).join(", ") }) : t("integrityProblems", { count: view.integrity.problems.length, checked: Object.entries(view.integrity.checked).map(([key, value]) => `${value} ${key}`).join(", ") })}
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

      <Panel eyebrow={`${view.members.length} row(s) · a standing changes only here, and only a row can change it`} title={t("titleMembers")}>
        <TenantTools ident={view.organization.slug} members={view.members} rules={view.rules} teams={view.teams} />
      </Panel>

      <Panel
        eyebrow={fixtures.ok ? t("eyebrowFixtures", { total: fixtures.data.total, played: fixtures.data.played }) : t("fixturesDoorMissing")}
        title={t("titleFixtures")}
      >
        {fixtures.ok ? (
          rulebook.ok ? (
            <FixtureArranger caps={rulebook.data.fixture_caps} ident={view.organization.slug} list={fixtures.data} teams={view.teams} />
          ) : (
            // No form without the door's own vocabulary: a page that drew its own sides, block lengths or head
            // count would be teaching a caller to be refused by a rule the page invented.
            <p className="muted">{t("fixturesRulebookMissing")}</p>
          )
        ) : (
          <Refused figures={refusalFigures(fixtures.error.details)} label="fixtures" message={fixtures.error.message} status={fixtures.status} />
        )}
        {rulebook.ok && (
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            {rulebook.data.fixture_limitation}
          </p>
        )}
      </Panel>

      <Panel
        eyebrow={
          notices.ok
            ? t("eyebrowNotices", { total: notices.data.total, held: notices.data.announcements_held, limit: notices.data.limit, audience: audience ? ` · filtered to ${audience}` : "" })
            : t("noticesDoorMissing")
        }
        title={t("titleNotices")}
      >
        {notices.ok ? (
          <NoticeBoard audience={audience} caps={notices.data.caps} ident={view.organization.slug} list={notices.data} />
        ) : (
          <Refused figures={refusalFigures(notices.error.details)} label="notices" message={notices.error.message} status={notices.status} />
        )}
        {rulebook.ok && (
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            {rulebook.data.announcement_limitation}
          </p>
        )}
      </Panel>

      <Panel eyebrow={consents.ok ? t("eyebrowConsents", { total: consents.data.total, under18: consents.data.under_18, minorAge: academyRules.ok ? academyRules.data.minor_age : 18 }) : t("consentsDoorMissing")} title={t("titleConsents")}>
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

      <Panel eyebrow={curricula.ok ? t("eyebrowCurricula", { total: curricula.data.total, limit: curricula.data.limit }) : t("curriculaDoorMissing")} title={t("titleCurricula")}>
        {curricula.ok ? (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("tableHeaderCurriculum")}</th>
                  <th scope="col">{t("tableHeaderAgeBand")}</th>
                  <th scope="col">{t("tableHeaderWeeklyMinutes")}</th>
                  <th scope="col">{t("tableHeaderPhases")}</th>
                  <th scope="col">{t("tableHeaderUnassigned")}</th>
                  <th scope="col">{t("tableHeaderPlansUsing")}</th>
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

      <Panel eyebrow={plans.ok ? t("eyebrowPlans", { total: plans.data.total, minors: plans.data.minors_in_list, minorAge: academyRules.ok ? academyRules.data.minor_age : 18, readThrough: plans.data.read_through }) : t("plansDoorMissing")} title={t("titlePlans")}>
        {plans.ok ? (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("tableHeaderChild")}</th>
                  <th scope="col">{t("tableHeaderAge")}</th>
                  <th scope="col">{tc("status")}</th>
                  <th scope="col">{t("tableHeaderReviewCadence")}</th>
                  <th scope="col">{t("tableHeaderReviewsFiled")}</th>
                  <th scope="col">{t("tableHeaderGoals")}</th>
                  <th scope="col">{t("tableHeaderProgress")}</th>
                  <th scope="col">{t("tableHeaderFocus")}</th>
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
                      {row.progress ?? t("progressNotYet")}
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

      <Panel eyebrow={t("eyebrowTierLimits", { count: view.limitations.length })} title={t("titleTierLimits")}>
        <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
          {view.limitations.map((line) => (
            <li className="muted" key={line} style={{ fontSize: "0.86rem" }}>
              {line}
            </li>
          ))}
        </ul>
      </Panel>

      <Panel eyebrow={sessions.ok ? t("eyebrowSessions", { total: sessions.data.total, load: sessions.data.total_load_units, readThrough: sessions.data.read_through }) : t("sessionsDoorMissing")} title={t("titleSessions")}>
        {sessions.ok ? (
          <div className="stack">
            {academyRules.ok ? (
              <SessionRecorder formula={sessions.data.formulas.load_units} ident={ident} limits={academyRules.data.session_limits} teams={view.teams} today={sessionDay} />
            ) : (
              // No form without the door's own ceilings. This page used to fall back to a `60`, an `8`, a `280` and
              // a `[1, 2, 3, 4]` of its own whenever the rulebook door did not answer, and every one of those was a
              // number the API never published — a form that invites a caller past a cap it invented is worse here
              // than a blank that says which door is missing.
              <p className="muted" style={{ fontSize: "0.86rem" }}>
                {t("sessionRulebookMissing")}
              </p>
            )}
            <p className="muted" data-session-day={sessions.data.today} style={{ fontSize: "0.86rem", margin: 0 }}>
              {t("sessionDateNote", { today: sessions.data.today, guessed: today })} {sessions.data.today_rule}
            </p>
            <EraseNotes id="session-erase-wall">
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{t("tableHeaderDate")}</th>
                    <th scope="col">{t("tableHeaderSlot")}</th>
                    <th scope="col">{t("tableHeaderTeam")}</th>
                    <th scope="col">{t("tableHeaderCurriculum")}</th>
                    <th scope="col">{t("tableHeaderDuration")}</th>
                    <th scope="col">{t("tableHeaderRPE")}</th>
                    <th scope="col">{t("tableHeaderLoad")}</th>
                    <th scope="col">{t("tableHeaderFocus")}</th>
                    <th scope="col">{t("tableHeaderCoach")}</th>
                    <th scope="col">{t("tableHeaderAttendees")}</th>
                    <th scope="col">{t("tableHeaderNote")}</th>
                    <th scope="col">{t("tableHeaderErase")}</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.data.items.map((row) => (
                    <tr data-session={row.id} key={row.id}>
                      <td className="mono">{row.scheduled_on.slice(0, 10)}</td>
                      <td className="num">{row.slot}</td>
                      <td>{row.team?.name || "—"}</td>
                      <td className="muted">{row.curriculum || "—"}</td>
                      <td className="num">{row.duration_min} min</td>
                      <td className="num">{row.rpe}</td>
                      <td className="num" title="duration_min × rpe ÷ 60, over this row's own two columns">
                        {row.load_units.toFixed(2)}
                      </td>
                      <td className="muted">{row.focus.join(", ") || "—"}</td>
                      <td>{row.coach?.display_name || "—"}</td>
                      <td className="num">
                        {row.attendees.length} / {row.attendees.length + row.attendees_gone}
                      </td>
                      <td className="muted">{row.note || "—"}</td>
                      <td>
                        <EraseRow action="session-erase" label={tc("delete")} path={`/club/academy/${encodeURIComponent(ident)}/sessions/${encodeURIComponent(row.id)}`} what="session" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            </EraseNotes>
            <p className="muted" data-load-check={loadAgrees ? "agrees" : "mismatch"} style={{ fontSize: "0.82rem" }}>
              {loadAgrees ? t("loadAgrees", { count: sessions.data.items.length, printed: printedLoad.toFixed(2), api: sessions.data.total_load_units.toFixed(2) }) : t("loadMismatch", { count: sessions.data.items.length, printed: printedLoad.toFixed(2), api: sessions.data.total_load_units.toFixed(2) })}
            </p>
            <p className="muted" style={{ fontSize: "0.82rem" }}>
              {sessions.data.formulas.total_load_units} · {sessions.data.read_through}
            </p>
          </div>
        ) : (
          <Refused figures={refusalFigures(sessions.error.details)} label="sessions" message={sessions.error.message} status={sessions.status} />
        )}
      </Panel>

      <Panel eyebrow={reports.ok ? t("eyebrowReports", { total: reports.data.total, limit: reports.data.limit, kinds: reports.data.kinds.join(", ") }) : t("reportsDoorMissing")} title={t("titleReports")}>
        {reports.ok ? (
          <div className="stack">
            {academyRules.ok ? (
              <ReportSaver
                defaultFrom={defaultFrom}
                ident={ident}
                kinds={reports.data.kinds}
                limits={academyRules.data.report_limits}
                teams={view.teams}
                today={today}
              />
            ) : (
              <p className="muted" style={{ fontSize: "0.86rem" }}>
                {t("reportRulebookMissing")}
              </p>
            )}
            <EraseNotes id="report-erase-wall">
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{t("tableHeaderKind")}</th>
                    <th scope="col">{t("tableHeaderWindow")}</th>
                    <th scope="col">{t("tableHeaderTeam2")}</th>
                    <th scope="col">{t("tableHeaderAskedBy")}</th>
                    <th scope="col">{t("tableHeaderAskedOn")}</th>
                    <th scope="col">{t("tableHeaderSessions")}</th>
                    <th scope="col">{t("tableHeaderLoad2")}</th>
                    <th scope="col">{t("tableHeaderAnswer")}</th>
                    <th scope="col">{t("tableHeaderErase2")}</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.data.items.map((row) => (
                    <tr data-report={row.id} key={row.id}>
                      <td>
                        <span className="badge badge--demo">{row.kind}</span>
                      </td>
                      <td className="muted">
                        {row.window_from.slice(0, 10)} → {row.window_to.slice(0, 10)} ({row.window_days ?? "?"} day(s))
                      </td>
                      <td>{row.team?.name || "all"}</td>
                      <td>{row.asked_by?.display_name || "—"}</td>
                      <td className="mono">{row.asked_on?.slice(0, 16) || "—"}</td>
                      <td className="num">{row.body.sessions ?? "—"}</td>
                      <td className="num">{row.body.total_load_units?.toFixed(2) ?? "—"}</td>
                      <td className="muted" style={{ fontSize: "0.8rem" }}>
                        {row.body.empty_window ? t("emptyWindow") : (row.body.formulas.total_load_units ?? "recomputed on read")}
                      </td>
                      <td>
                        <EraseRow action="report-erase" label={tc("delete")} path={`/club/academy/${encodeURIComponent(ident)}/reports/${encodeURIComponent(row.id)}`} what="question" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            </EraseNotes>
            <p className="muted" style={{ fontSize: "0.82rem" }}>
              {reports.data.rule}
            </p>
          </div>
        ) : (
          <Refused figures={refusalFigures(reports.error.details)} label="reports" message={reports.error.message} status={reports.status} />
        )}
      </Panel>

      <Panel
        eyebrow={entitlements.ok ? t("eyebrowEntitlements", { plan: entitlements.data.plan, ceilings: meterRows.length, asOf: entitlements.data.as_of }) : t("entitlementsDoorMissing")}
        title={t("titleEntitlements")}
      >
        {entitlements.ok ? (
          <div className="stack">
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{t("tableHeaderFeature")}</th>
                    <th scope="col">{t("tableHeaderCeiling")}</th>
                    <th scope="col">{t("tableHeaderUsed")}</th>
                    <th scope="col">{t("tableHeaderRemaining")}</th>
                    <th scope="col">{t("tableHeaderPeriod")}</th>
                    <th scope="col">{t("tableHeaderActRows")}</th>
                    <th scope="col">{t("tableHeaderRefusedToday")}</th>
                  </tr>
                </thead>
                <tbody>
                  {entitlements.data.items.map((row) => (
                    <tr data-entitlement={row.feature} key={row.feature}>
                      <td className="mono">{row.feature}</td>
                      <td className="num">{row.limit}</td>
                      <td className="num">{row.used}</td>
                      <td className="num">{row.remaining}</td>
                      <td>{row.period}</td>
                      <td className="num">{row.acts}</td>
                      <td>{row.enforced ? t("refusedYes") : t("refusedNo")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted" data-meter-check={meterAgrees ? "agrees" : "mismatch"} style={{ fontSize: "0.82rem" }}>
              {meterAgrees ? t("meterAgrees", { count: meterRows.length }) : t("meterMismatch", { count: meterRows.length })}
            </p>
            <p className="muted" style={{ fontSize: "0.82rem" }}>
              {entitlements.data.formula}
            </p>
            <p className="notice" style={{ fontSize: "0.86rem" }}>
              {entitlements.data.enforced_rule}
            </p>
            <p className="muted" style={{ fontSize: "0.82rem" }}>
              {entitlements.data.plan_rule}
            </p>
            <p className="muted" style={{ fontSize: "0.82rem" }}>
              {entitlements.data.tier_limits.members} members and {entitlements.data.tier_limits.teams} teams are what §39's own doors refuse on — {entitlements.data.tier_limits.rule}
            </p>
            <p className="muted" style={{ fontSize: "0.82rem" }}>
              {entitlements.data.no_payment}
            </p>
            {mine.ok ? (
              <p className="muted" data-account-meter={mine.data.items.map((row) => row.feature).join(",")} style={{ fontSize: "0.82rem" }}>
                {mine.data.display_name} as an account is a separate subject on {mine.data.plan}:{" "}
                {mine.data.items.map((row) => `${row.feature} ${row.used} of ${row.limit} per ${row.period}${row.enforced ? ", refused on today" : ", not refused on today"}`).join("; ") ||
                  t("accountMeterNothing")}
                .
              </p>
            ) : (
              <Refused figures={refusalFigures(mine.error.details)} label="account-meter" message={mine.error.message} status={mine.status} />
            )}
          </div>
        ) : (
          <Refused figures={refusalFigures(entitlements.error.details)} label="entitlements" message={entitlements.error.message} status={entitlements.status} />
        )}
      </Panel>

      <Provenance extra={<span className="chip mono">{t("provenanceExtra2", { teams: view.teams.length, players: view.counts.players_on_sheets })}</span>} provenance={{ data_origin: view.data_origin, is_demo_data: view.is_demo_data }} />
    </div>
  );
}