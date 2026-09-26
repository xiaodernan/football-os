import type { Metadata } from "next";
import Link from "next/link";

import { Panel } from "@/components/ui";
import { Provenance, WorldHead } from "@/components/world";
import { type AcademyCapabilities, type ClubCapabilities } from "@/lib/club";
import { absolute } from "@/lib/site";
import { serverFetch } from "@/lib/server";

import "../../../styles/tactics.css";

export const dynamic = "force-dynamic";

/**
 * The published rulebook for §39 and §40, on one page, readable by nobody in particular.
 *
 * Both API doors it renders are open without an account — `GET /club/capabilities` says so in its own
 * purpose line, and §40's says the same for a guardian who has to read the rules before agreeing to them.
 * This page is therefore the only `/club` route that may be indexed: everything under `/club` that shows
 * a real tenant is behind a session and disallowed, while a matrix of roles, a list of caps and a table of
 * refusal codes are the terms of the service, which is exactly what a public page is for.
 *
 * Nothing is summarised. The sentences are the API's, and where the two tiers share a word — `refusals`,
 * `counts`, `limitations` — the two columns stay apart, because §40's set is disjoint from §39's and a
 * merged table would hide the one fact that makes the split checkable.
 */
export const metadata: Metadata = {
  title: "Club and academy rulebook",
  description: "The permission matrix, caps, refusal codes, stored columns and door guide for club tenancies and youth academies, published before sign-in.",
  alternates: { canonical: absolute("/club/rules") },
  openGraph: {
    title: "Club and academy rulebook",
    description: "Roles, rights, caps, refusals and stored columns for FOOTBALL OS club tenancies and youth academies.",
    url: absolute("/club/rules"),
  },
};

export default async function ClubRulesPage() {
  const [club, academy] = await Promise.all([
    serverFetch<ClubCapabilities>("/club/capabilities"),
    serverFetch<AcademyCapabilities>("/club/academy/capabilities"),
  ]);
  if (!club.ok || !academy.ok) {
    const missing = !club.ok ? "club" : "academy";
    return (
      <div className="container page stack">
        <WorldHead back={{ href: "/club", label: "My clubs" }} eyebrow="both doors are public, so a failure here is the API being down" title="The rulebook is unavailable" />
        <div className="notice notice--warn">
          The {missing} capabilities door did not answer, and a rulebook rewritten from memory would not be a rulebook. Nothing is substituted.
        </div>
      </div>
    );
  }

  const rules = club.data;
  const edu = academy.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/club", label: "My clubs" }}
        eyebrow={`${rules.matrix.roles.length} standings · ${rules.matrix.permissions.length} rights · ${rules.refusals.length} + ${edu.refusals.length} refusal codes · ${rules.routes.length} + ${edu.routes.length} door lines`}
        lede="What a club tenant may do, what a youth academy may hold about a child, and what both refuse. This page reads two API doors that need no account, prints their own sentences, and changes none of them."
        provenance={{ data_origin: rules.data_origin, is_demo_data: rules.is_demo_data }}
        title="Club and academy rulebook"
      />

      <Panel eyebrow={rules.matrix.rule} title="§39 · who holds what">
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Standing</th>
                <th scope="col">Meaning</th>
                <th scope="col">Rights</th>
              </tr>
            </thead>
            <tbody>
              {rules.matrix.roles.map((role) => (
                <tr data-role={role} key={role}>
                  <td className="mono">{role}</td>
                  <td className="muted">{rules.matrix.meaning[role]}</td>
                  <td className="mono" style={{ fontSize: "0.78rem" }}>
                    {rules.matrix.matrix[role].join(", ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted" style={{ fontSize: "0.84rem" }}>
          {rules.matrix.default} {rules.matrix.stored}. {rules.matrix.not_stored}
        </p>
        <ul className="stack-sm" style={{ margin: "0.5rem 0 0", paddingLeft: "1.1rem" }}>
          {Object.entries(rules.matrix.scoped).map(([right, sentence]) => (
            <li data-scoped={right} key={right} style={{ fontSize: "0.86rem" }}>
              <span className="mono">{right}</span> — {sentence}
            </li>
          ))}
        </ul>
      </Panel>

      <Panel eyebrow={`${edu.minor_age} is the threshold: at or under it, a plan needs a guardian's row first`} title="§40 · what may be recorded about a child">
        <div className="grid grid-2">
          <div>
            <h3 className="panel__title">Purposes a consent names</h3>
            <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
              {edu.scopes.map((scope) => (
                <li className="mono" data-scope={scope} key={scope}>
                  {scope}
                  {edu.default_scopes.includes(scope) ? " · in the default set" : " · never assumed"}
                </li>
              ))}
            </ul>
            <p className="muted" style={{ fontSize: "0.84rem" }}>
              {edu.consent_scopes.rule}
            </p>
            <p className="muted" style={{ fontSize: "0.84rem" }}>
              {edu.consent} {edu.guardianship}
            </p>
          </div>
          <div>
            <h3 className="panel__title">What this tier never holds</h3>
            <ul className="stack-sm mono" style={{ margin: 0, paddingLeft: "1.1rem" }}>
              {edu.never_stored.map((line) => (
                <li data-never={line} key={line} style={{ fontSize: "0.84rem" }}>
                  {line}
                </li>
              ))}
            </ul>
            <p className="muted" style={{ fontSize: "0.84rem" }}>
              {edu.video}
            </p>
          </div>
        </div>
      </Panel>

      <Panel eyebrow={`${Object.keys(edu.stored_fields).length} tables · ${Object.values(edu.stored_fields).reduce((sum, columns) => sum + columns.length, 0)} columns, and the list is the minimisation`} title="Every column the academy writes">
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Table</th>
                <th scope="col">Columns</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(edu.stored_fields).map(([table, columns]) => (
                <tr data-table={table} key={table}>
                  <td className="mono">{table}</td>
                  <td className="muted" style={{ fontSize: "0.8rem" }}>
                    {columns.join(", ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted" style={{ fontSize: "0.84rem" }}>
          A field a coach types that is not on this list has nowhere to be stored, which is why posting a home address to a review answers with the review and no address in it.
        </p>
      </Panel>

      <Panel eyebrow={`${rules.refusal_answers ? Object.values(rules.refusal_answers).filter((status) => status === 403).length : 0} of §39's codes are a 403 · ${Object.values(edu.refusal_answers).filter((status) => status === 403).length} of §40's own, and its four shared codes carry §39's answer`} title="Refusals, and the status each one means">
        <div className="grid grid-2">
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">§39 code</th>
                  <th scope="col">HTTP</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(rules.refusal_answers).map(([code, status]) => (
                  <tr data-club-refusal={code} key={code}>
                    <td className="mono">{code}</td>
                    <td className="num">{status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">§40 code</th>
                  <th scope="col">HTTP</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(edu.refusal_answers)
                  .filter(([code]) => !edu.refusals_shared_with_club_tier.includes(code))
                  .map(([code, status]) => (
                    <tr data-academy-refusal={code} key={code}>
                      <td className="mono">{code}</td>
                      <td className="num">{status}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
        <p className="muted" style={{ fontSize: "0.84rem" }}>
          Shared with §39 and answered by it: {edu.refusals_shared_with_club_tier.join(", ")}. One code means one thing, so a page can branch on the fix rather than on the mood.
        </p>
      </Panel>

      <Panel eyebrow={`§39: ${rules.max_organizations_per_user} tenants · ${rules.max_members_per_organization} members · ${rules.max_teams_per_organization} sheets · ${rules.max_squad_per_team} a side — §40: ${edu.max_plans_per_organization} plans · ${edu.max_curricula_per_organization} curricula · ${edu.max_assessments_per_plan} reviews · ${edu.max_consents_per_guardian} claims`} title="Caps, stated as numbers">
        <div className="grid grid-2">
          <dl className="world-kv">
            {[
              ["name_max", rules.name_max],
              ["team_name_max", rules.team_name_max],
              ["note_max", rules.note_max],
              ["country", rules.country],
              ["kinds", rules.kinds.join(", ")],
              ["visibility defaults", rules.visibility_defaults.join(", ")],
              ["addressing", rules.addressing],
              ["invitations", rules.invitations],
            ].map(([key, value]) => (
              <div className="world-kv__row" key={String(key)}>
                <dt className="mono">{key}</dt>
                <dd style={{ textAlign: "right" }}>{value}</dd>
              </div>
            ))}
          </dl>
          <dl className="world-kv">
            {[
              ["axes", edu.axes.join(", ")],
              ["rating_range", edu.rating_range.join("–")],
              ["review_weeks_range", edu.review_weeks_range.join("–")],
              ["weekly minutes", edu.max_weekly_minutes],
              ["focus items / goals", `${edu.focus_items_max} / ${edu.goals_max}`],
              ["goal keys", edu.goal_keys.join(", ")],
              ["feedback / assessment text", `${edu.feedback_max} / ${edu.assessment_text_max} characters`],
              ["plan statuses", edu.plan_statuses.join(", ")],
            ].map(([key, value]) => (
              <div className="world-kv__row" key={String(key)}>
                <dt className="mono">{key}</dt>
                <dd style={{ textAlign: "right" }}>{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Panel>

      <Panel eyebrow={`counts published live: ${Object.entries(rules.counts).filter(([key]) => key !== "rule").map(([key, value]) => `${value} ${key}`).join(" · ")}`} title="The doors, and what each is for">
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Methods</th>
                <th scope="col">Door</th>
                <th scope="col">Purpose</th>
              </tr>
            </thead>
            <tbody>
              {[...rules.routes, ...edu.routes].map((door) => (
                <tr data-door={door.path} key={`${door.methods.join("")}${door.path}`}>
                  <td className="mono">{door.methods.join(", ")}</td>
                  <td className="mono">{door.path}</td>
                  <td className="muted">{door.purpose}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted" style={{ fontSize: "0.84rem" }}>
          Both tiers say whether their tables exist: §39 <span className="mono">ready: {String(rules.ready)}</span>, §40 <span className="mono">ready: {String(edu.ready)}</span>. {rules.counts.rule} {edu.counts.rule}
        </p>
      </Panel>

      <Panel eyebrow={`${rules.limitations.length} + ${edu.limitations.length} sentences the API attaches to every read`} title="Limits, in the API's words">
        <div className="grid grid-2">
          <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
            {rules.limitations.map((line) => (
              <li className="muted" key={line} style={{ fontSize: "0.85rem" }}>
                {line}
              </li>
            ))}
          </ul>
          <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
            {edu.limitations.map((line) => (
              <li className="muted" key={line} style={{ fontSize: "0.85rem" }}>
                {line}
              </li>
            ))}
          </ul>
        </div>
      </Panel>

      <p className="muted" style={{ fontSize: "0.86rem" }}>
        An account with a tenant of its own: <Link className="world-link" href="/club">/club</Link>. A guardian reading this before answering for a child: the row you grant is the only record of your yes, and withdrawing it stops new writes without touching what is already held — {edu.consent}
      </p>

      <Provenance extra={<span className="chip mono">the two tiers&apos; refusal sets are disjoint by design</span>} provenance={{ data_origin: edu.data_origin, is_demo_data: edu.is_demo_data }} />
    </div>
  );
}
