import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { ClubCreateForm, InvitationTools } from "@/components/ClubTools";
import { Panel } from "@/components/ui";
import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { refusalFigures, type ClubCapabilities, type InvitationList, type OrganizationList } from "@/lib/club";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";

import "../../styles/tactics.css";

export const dynamic = "force-dynamic";

/**
 * The §39 tenancy index: which organisations this account stands in, which invitations are waiting for an
 * answer, and the door that opens a new one.
 *
 * Private for the obvious reason — a list of the clubs you belong to is not content for a crawler — while
 * the rulebook it quotes is deliberately public at `/club/rules`, because §39 publishes the permission
 * matrix before anybody signs in, and a rule you cannot read until you have already agreed to it is not a
 * rule.
 */
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("club");
  return {
    title: t("metaTitle"),
    description: t("metaDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/club") },
  };
}

export default async function ClubIndexPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fclub");

  const tc = await getTranslations("common");
  const tn = await getTranslations("nav");
  const t = await getTranslations("club");
  const [owned, invited, rules] = await Promise.all([
    serverFetch<OrganizationList>("/club"),
    serverFetch<InvitationList>("/club/invitations"),
    serverFetch<ClubCapabilities>("/club/capabilities"),
  ]);
  if (!owned.ok) return <WorldUnavailable detail={refusalFigures(owned.error.details).join(" · ")} message={owned.error.message} title={t("errorMyClubs")} />;
  if (!rules.ok) return <WorldUnavailable message={t("errorRulebook")} title={t("errorMyClubs")} />;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/", label: tn("home") }}
        eyebrow={`${user.display_name} · ${owned.data.total} of ${owned.data.limit} organisations`}
        lede={t("headLede")}
        provenance={{ data_origin: rules.data.data_origin, is_demo_data: rules.data.is_demo_data }}
        title={t("headTitle")}
      />

      {invited.ok && invited.data.items.length > 0 && (
        <Panel eyebrow={t("eyebrowInvitations", { total: invited.data.total })} title={t("titleInvitations")}>
          <InvitationTools items={invited.data.items} />
          <p className="muted" style={{ fontSize: "0.84rem" }}>
            {invited.data.rule}
          </p>
        </Panel>
      )}

      <Panel eyebrow={t("eyebrowCreateOrg", { total: owned.data.total, limit: owned.data.limit, room: owned.data.room_left })} title={t("titleCreateOrg")}>
        <ClubCreateForm roomLeft={owned.data.room_left} rules={rules.data} />
      </Panel>

      {owned.data.items.length === 0 ? (
        <div className="empty">
          <strong>{t("emptyTitle")}</strong>
          <p className="muted">
            {owned.data.rule}
          </p>
        </div>
      ) : (
        <Panel eyebrow={t("eyebrowWhereYouStand", { count: owned.data.items.length })} title={t("titleWhereYouStand")}>
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("tableHeaderOrganisation")}</th>
                  <th scope="col">{t("tableHeaderKind")}</th>
                  <th scope="col">{t("tableHeaderStanding")}</th>
                  <th scope="col">{t("tableHeaderMembers")}</th>
                  <th scope="col">{t("tableHeaderTeams")}</th>
                  <th scope="col">{tc("status")}</th>
                </tr>
              </thead>
              <tbody>
                {owned.data.items.map((row) => (
                  <tr data-organization={row.slug} key={row.slug}>
                    <td>
                      <Link className="world-link" href={row.path}>
                        {row.name}
                      </Link>
                    </td>
                    <td className="muted">{row.kind}</td>
                    <td>
                      <span className="badge badge--demo">{row.role}</span>
                    </td>
                    <td className="num">{row.active_members}</td>
                    <td className="num">{row.teams}</td>
                    <td>
                      <span className={row.status === "active" ? "badge badge--live" : "badge badge--demo"}>{row.status.toUpperCase()}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ fontSize: "0.84rem" }}>
            {owned.data.rule}
          </p>
        </Panel>
      )}

      <Panel eyebrow={t("eyebrowMatrix", { roles: rules.data.matrix.roles.length, perms: rules.data.matrix.permissions.length, doors: rules.data.routes.length })} title={t("titleMatrix")}>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("tableHeaderStanding2")}</th>
                <th scope="col">{t("tableHeaderRights")}</th>
                <th scope="col">{t("tableHeaderMeaning")}</th>
              </tr>
            </thead>
            <tbody>
              {rules.data.matrix.roles.map((role) => (
                <tr data-role={role} key={role}>
                  <td className="mono">{role}</td>
                  <td className="num">{rules.data.matrix.matrix[role].length}</td>
                  <td className="muted">{rules.data.matrix.meaning[role]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted" style={{ fontSize: "0.84rem" }}>
          {rules.data.matrix.rule} Read the whole matrix, the caps and the refusal table at <Link className="world-link" href="/club/rules">/club/rules</Link>.
        </p>
      </Panel>

      <p className="muted" style={{ fontSize: "0.84rem" }}>{rules.data.addressing}</p>

      <Panel eyebrow={t("eyebrowLimits", { count: rules.data.limitations.length })} title={t("titleLimits")}>
        <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
          {rules.data.limitations.map((line) => (
            <li className="muted" key={line} style={{ fontSize: "0.86rem" }}>
              {line}
            </li>
          ))}
        </ul>
      </Panel>

      <Provenance extra={<span className="chip mono">{t("provenanceExtra")}</span>} provenance={{ data_origin: rules.data.data_origin, is_demo_data: rules.data.is_demo_data }} />
    </div>
  );
}