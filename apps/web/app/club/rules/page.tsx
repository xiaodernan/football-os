import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

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
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("club");
  return {
    title: t("rulesMetaTitle"),
    description: t("rulesMetaDescription"),
    alternates: { canonical: absolute("/club/rules") },
    openGraph: {
      title: t("rulesOGTitle"),
      description: t("rulesOGDescription"),
      url: absolute("/club/rules"),
    },
  };
}

export default async function ClubRulesPage() {
  const t = await getTranslations("club");
  const [club, academy] = await Promise.all([
    serverFetch<ClubCapabilities>("/club/capabilities"),
    serverFetch<AcademyCapabilities>("/club/academy/capabilities"),
  ]);
  if (!club.ok || !academy.ok) {
    const missing = !club.ok ? "club" : "academy";
    return (
      <div className="container page stack">
        <WorldHead back={{ href: "/club", label: t("backLabelRules") }} eyebrow={t("errorBothDoors")} title={t("errorUnavailable")} />
        <div className="notice notice--warn">
          {t("errorMissing", { missing })}
        </div>
      </div>
    );
  }

  const rules = club.data;
  const edu = academy.data;

  // Helper to convert cap key to translation key
  const capKey = (key: string) => "cap" + key.replace(/_/g, "").replace(/^\w/, (c: string) => c.toUpperCase());

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/club", label: t("backLabelRules") }}
        eyebrow={t("eyebrowRules", { roles: rules.matrix.roles.length, perms: rules.matrix.permissions.length, clubRefusals: rules.refusals.length, academyRefusals: edu.refusals.length, clubDoors: rules.routes.length, academyDoors: edu.routes.length })}
        lede={t("ledeRules")}
        provenance={{ data_origin: rules.data_origin, is_demo_data: rules.is_demo_data }}
        title={t("titleRules")}
      />

      <Panel eyebrow={rules.matrix.rule} title={t("panel39Title")}>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("tableHeaderStanding39")}</th>
                <th scope="col">{t("tableHeaderMeaning39")}</th>
                <th scope="col">{t("tableHeaderRights39")}</th>
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
          {t("matrixDefault", { default: rules.matrix.default, stored: rules.matrix.stored, not_stored: rules.matrix.not_stored })}
        </p>
        <ul className="stack-sm" style={{ margin: "0.5rem 0 0", paddingLeft: "1.1rem" }}>
          {Object.entries(rules.matrix.scoped).map(([right, sentence]) => (
            <li data-scoped={right} key={right} style={{ fontSize: "0.86rem" }}>
              <span className="mono">{right}</span> — {sentence}
            </li>
          ))}
        </ul>
      </Panel>

      <Panel eyebrow={t("panel40Eyebrow", { minorAge: edu.minor_age })} title={t("panel40Title")}>
        <div className="grid grid-2">
          <div>
            <h3 className="panel__title">{t("consentPurposesTitle")}</h3>
            <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
              {edu.scopes.map((scope) => (
                <li className="mono" data-scope={scope} key={scope}>
                  {scope}
                  {edu.default_scopes.includes(scope) ? t("defaultScope", { scope }) : t("neverAssumed", { scope })}
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
            <h3 className="panel__title">{t("neverStoredTitle")}</h3>
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

      <Panel eyebrow={t("storedFieldsEyebrow", { tables: Object.keys(edu.stored_fields).length, columns: Object.values(edu.stored_fields).reduce((sum, columns) => sum + columns.length, 0) })} title={t("storedFieldsTitle")}>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("tableHeaderTable")}</th>
                <th scope="col">{t("tableHeaderColumns")}</th>
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
          {t("storedFieldsNote")}
        </p>
      </Panel>

      <Panel eyebrow={t("refusalsEyebrow", { club403: Object.values(rules.refusal_answers).filter((status) => status === 403).length, academy403: Object.values(edu.refusal_answers).filter((status) => status === 403).length })} title={t("refusalsTitle")}>
        <div className="grid grid-2">
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("tableHeaderCode39")}</th>
                  <th scope="col">{t("tableHeaderHTTP")}</th>
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
                  <th scope="col">{t("tableHeaderCode40")}</th>
                  <th scope="col">{t("tableHeaderHTTP")}</th>
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
          {t("sharedRefusals", { codes: edu.refusals_shared_with_club_tier.join(", ") })}
        </p>
      </Panel>

      <Panel eyebrow={t("capsEyebrow", { orgs: rules.max_organizations_per_user, members: rules.max_members_per_organization, teams: rules.max_teams_per_organization, squad: rules.max_squad_per_team, plans: edu.max_plans_per_organization, curricula: edu.max_curricula_per_organization, reviews: edu.max_assessments_per_plan, consents: edu.max_consents_per_guardian })} title={t("capsTitle")}>
        <div className="grid grid-2">
          <dl className="world-kv">
            {[
              ["name_max", rules.name_max],
              ["team_name_max", rules.team_name_max],
              ["note_max", rules.note_max],
              ["country", rules.country],
              ["kinds", rules.kinds.join(", ")],
              ["visibility_defaults", rules.visibility_defaults.join(", ")],
              ["addressing", rules.addressing],
              ["invitations", rules.invitations],
            ].map(([key, value]) => {
              const k = String(key);
              return (
                <div className="world-kv__row" key={k}>
                  <dt className="mono">{t(capKey(k))}</dt>
                  <dd style={{ textAlign: "right" }}>{value}</dd>
                </div>
              );
            })}
          </dl>
          <dl className="world-kv">
            {[
              ["axes", edu.axes.join(", ")],
              ["rating_range", edu.rating_range.join("–")],
              ["review_weeks_range", edu.review_weeks_range.join("–")],
              ["weekly_minutes", edu.max_weekly_minutes],
              ["focus_items_goals", `${edu.focus_items_max} / ${edu.goals_max}`],
              ["goal_keys", edu.goal_keys.join(", ")],
              ["feedback_assessment", `${edu.feedback_max} / ${edu.assessment_text_max} characters`],
              ["plan_statuses", edu.plan_statuses.join(", ")],
            ].map(([key, value]) => {
              const k = String(key);
              return (
                <div className="world-kv__row" key={k}>
                  <dt className="mono">{t(capKey(k))}</dt>
                  <dd style={{ textAlign: "right" }}>{value}</dd>
                </div>
              );
            })}
          </dl>
        </div>
      </Panel>

      <Panel eyebrow={t("doorsEyebrow", { counts: Object.entries(rules.counts).filter(([key]) => key !== "rule").map(([key, value]) => `${value} ${key}`).join(" · ") })} title={t("doorsTitle")}>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("tableHeaderMethods")}</th>
                <th scope="col">{t("tableHeaderDoor")}</th>
                <th scope="col">{t("tableHeaderPurpose")}</th>
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
          {t("doorsReadyNote", { clubReady: String(rules.ready), academyReady: String(edu.ready), clubRule: rules.ready_rule, countsRule: rules.counts.rule, eduRule: edu.counts.rule })}
        </p>
      </Panel>

      <Panel eyebrow={t("limitsEyebrow", { clubLimits: rules.limitations.length, academyLimits: edu.limitations.length })} title={t("limitsTitle")}>
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
        {t("footerNote", { consent: edu.consent })}
      </p>

      <Provenance extra={<span className="chip mono">{t("provenanceExtraRules")}</span>} provenance={{ data_origin: edu.data_origin, is_demo_data: edu.is_demo_data }} />
    </div>
  );
}