import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

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
export const metadata: Metadata = {
  title: "My clubs",
  description: "The organisations your account stands in, the invitations waiting for an answer, and the standing each one grants.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/club") },
};

export default async function ClubIndexPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fclub");

  const [owned, invited, rules] = await Promise.all([
    serverFetch<OrganizationList>("/club"),
    serverFetch<InvitationList>("/club/invitations"),
    serverFetch<ClubCapabilities>("/club/capabilities"),
  ]);
  if (!owned.ok) return <WorldUnavailable detail={refusalFigures(owned.error.details).join(" · ")} message={owned.error.message} title="My clubs" />;
  if (!rules.ok) return <WorldUnavailable message="The club rulebook could not be read, so this page has nothing to check its numbers against." title="My clubs" />;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/", label: "Home" }}
        eyebrow={`${user.display_name} · ${owned.data.total} of ${owned.data.limit} organisations`}
        lede="An organisation here is a tenant: it has members, each with one standing from a published matrix, and a member of one tenant can read nothing of another. The matrix, the caps and every refusal code are printed at /club/rules, which needs no account."
        provenance={{ data_origin: rules.data.data_origin, is_demo_data: rules.data.is_demo_data }}
        title="Club tenancies"
      />

      {invited.ok && invited.data.items.length > 0 && (
        <Panel eyebrow={`${invited.data.total} invitation(s) · accepting is what grants the standing`} title="Invitations addressed to you">
          <InvitationTools items={invited.data.items} />
          <p className="muted" style={{ fontSize: "0.84rem" }}>
            {invited.data.rule}
          </p>
        </Panel>
      )}

      <Panel eyebrow={`${owned.data.total} of ${owned.data.limit} used · ${owned.data.room_left} seat(s) left`} title="Open an organisation">
        <ClubCreateForm roomLeft={owned.data.room_left} rules={rules.data} />
      </Panel>

      {owned.data.items.length === 0 ? (
        <div className="empty">
          <strong>You stand in no organisation yet</strong>
          <p className="muted">
            {owned.data.rule}
          </p>
        </div>
      ) : (
        <Panel eyebrow={`${owned.data.items.length} listed · nothing here is a public page`} title="Where you stand">
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Organisation</th>
                  <th scope="col">Kind</th>
                  <th scope="col">Your standing</th>
                  <th scope="col">Members</th>
                  <th scope="col">Teams</th>
                  <th scope="col">Status</th>
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

      <Panel eyebrow={`${rules.data.matrix.roles.length} standings · ${rules.data.matrix.permissions.length} rights · ${rules.data.routes.length} published doors`} title="What the matrix says about the seat you are in">
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Standing</th>
                <th scope="col">Rights</th>
                <th scope="col">Meaning</th>
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

      <Panel eyebrow={`${rules.data.limitations.length} limits, stated by the API on every read`} title="What this tier does not do">
        <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
          {rules.data.limitations.map((line) => (
            <li className="muted" key={line} style={{ fontSize: "0.86rem" }}>
              {line}
            </li>
          ))}
        </ul>
      </Panel>

      <Provenance extra={<span className="chip mono">an organisation and its members are user data; the players a sheet lists stay the world&apos;s</span>} provenance={{ data_origin: rules.data.data_origin, is_demo_data: rules.data.is_demo_data }} />
    </div>
  );
}
