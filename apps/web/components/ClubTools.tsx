"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { browserFetch } from "@/lib/api";
import { refusalFigures, type ClubRules, type InvitationItem, type MemberRow, type TeamView } from "@/lib/club";

type Note = { text: string; figures: string[]; refused: boolean; action: string };

/**
 * One runner for every club write, so no form here can report success it did not get.
 *
 * A call that the API refused is printed with its code, its sentence and the figures that came with it —
 * the cap, the length, the name — because §39's refusals are the rule rather than a shrug. A call that
 * succeeded does **not** render its own response body as the new state: `router.refresh()` re-reads the
 * page, so what appears on screen is what a `GET` says the tenant now is. That is the difference between
 * a form that shows a write and a form that shows a lie the server never kept.
 */
export function useClubCall() {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<Note | null>(null);

  async function call(action: string, path: string, init: { method?: string; body?: unknown } = {}) {
    setBusy(action);
    const method = (init.method ?? "POST").toUpperCase();
    const result = await browserFetch<Record<string, unknown>>(path, { method, body: init.body });
    setBusy(null);
    if (!result.ok) {
      setNote({ action, refused: true, text: `${method} ${path} was refused with ${result.status}`, figures: [`${result.error.code}: ${result.error.message}`, ...refusalFigures(result.error.details)] });
      return null;
    }
    setNote({ action, refused: false, text: `${method} ${path} answered ${result.status}. Everything below was re-read from the server after it.`, figures: [] });
    router.refresh();
    return result.data;
  }

  return { busy, call, note };
}

export function CallNote({ note }: { note: Note | null }) {
  if (!note) return null;
  return (
    <div className={note.refused ? "notice notice--warn" : "notice"} data-note={note.action}>
      <p style={{ margin: 0 }}>{note.text}</p>
      {note.figures.length > 0 && (
        <ul className="stack-sm" style={{ margin: "0.4rem 0 0", paddingLeft: "1.1rem" }}>
          {note.figures.map((figure) => (
            <li className="mono" key={figure} style={{ fontSize: "0.84rem" }}>
              {figure}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** `POST /club`. The slug is derived from the name by the service and is not a field here. */
export function ClubCreateForm({ rules, roomLeft }: { rules: ClubRules; roomLeft: number }) {
  const t = useTranslations("club");
  const { busy, call, note } = useClubCall();
  const [name, setName] = useState("");
  const [kind, setKind] = useState(rules.kinds.includes("club") ? "club" : rules.kinds[0]);
  const [country, setCountry] = useState("");
  const [visibility, setVisibility] = useState(rules.visibility_defaults.includes("members") ? "members" : rules.visibility_defaults[0]);

  return (
    <div className="stack">
      <div className="grid grid-2">
        <label className="field">
          <span>{t("createNameLabel", { max: rules.name_max })}</span>
          <input aria-label={t("createNameAria")} onChange={(event) => setName(event.target.value)} placeholder={t("createNamePlaceholder")} type="text" value={name} />
        </label>
        <label className="field">
          <span>{t("createKindLabel")}</span>
          <select aria-label={t("createKindAria")} onChange={(event) => setKind(event.target.value)} value={kind}>
            {rules.kinds.map((row) => (
              <option key={row} value={row}>
                {row}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("createCountryLabel")}</span>
          <input aria-label={t("createCountryAria")} onChange={(event) => setCountry(event.target.value)} placeholder={t("createCountryPlaceholder")} type="text" value={country} />
        </label>
        <label className="field">
          <span>{t("createVisibilityLabel")}</span>
          <select aria-label={t("createVisibilityAria")} onChange={(event) => setVisibility(event.target.value)} value={visibility}>
            {rules.visibility_defaults.map((row) => (
              <option key={row} value={row}>
                {row}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="row wrap">
        <button
          className="btn"
          data-testid="club-create"
          disabled={busy !== null || name.trim().length === 0 || roomLeft <= 0}
          onClick={() => void call("create", "/club", { body: { name: name.trim(), kind, country: country.trim(), visibility_default: visibility } })}
          type="button"
        >
          {busy === "create"
            ? t("createOpening")
            : roomLeft <= 0
              ? t("createLimit", { max: rules.max_organizations_per_user })
              : t("createOpen")}
        </button>
        <span className="muted" style={{ fontSize: "0.84rem" }}>
          {t("createSeats", { left: roomLeft, max: rules.max_organizations_per_user })}{" "}
          {rules.founder}
        </span>
      </div>
      <CallNote note={note} />
    </div>
  );
}

/** An invitation is a row that waits; accepting it is the moment a role starts granting anything. */
export function InvitationTools({ items }: { items: InvitationItem[] }) {
  const t = useTranslations("common");
  const tc = useTranslations("club");
  const { busy, call, note } = useClubCall();
  return (
    <div className="stack">
      <div className="world-tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{tc("thOrganisation")}</th>
              <th scope="col">{tc("thOfferedStanding")}</th>
              <th scope="col">{tc("thInvited")}</th>
              <th scope="col">{tc("thAnswer")}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <tr key={row.membership}>
                <td>{row.name}</td>
                <td>
                  <span className="badge badge--demo">{row.role}</span>
                </td>
                <td className="muted">{row.invited_at.slice(0, 16)} UTC</td>
                <td>
                  <div className="row wrap">
                    <button className="btn btn--sm" data-act="accept" disabled={busy !== null} onClick={() => void call(`accept-${row.organization}`, `/club/${encodeURIComponent(row.organization)}/accept`, { body: {} })} type="button">
                      {t("accept")}
                    </button>
                    <button className="btn btn--sm btn--ghost" data-act="decline" disabled={busy !== null} onClick={() => void call(`decline-${row.organization}`, `/club/${encodeURIComponent(row.organization)}/decline`, { body: {} })} type="button">
                      {t("decline")}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <CallNote note={note} />
    </div>
  );
}

/**
 * The tenant's own doors: staffing, sheets, the name, and closing the whole thing.
 *
 * Nothing here is disabled by a guess about roles. Every control is rendered and the API answers —
 * `insufficient_role` with the permission and the held list beside it — so the page shows the matrix as
 * it is enforced rather than as a screenshot of what a designer expected.
 */
export function TenantTools({ ident, members, teams, rules }: { ident: string; members: MemberRow[]; teams: TeamView[]; rules: ClubRules }) {
  const t = useTranslations("common");
  const tc = useTranslations("club");
  const { busy, call, note } = useClubCall();
  const [email, setEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("coach");
  const [roles, setRoles] = useState<Record<string, string>>({});
  const [teamName, setTeamName] = useState("");
  const [ageGroup, setAgeGroup] = useState("u16");
  const [stage, setStage] = useState("youth");
  const [worldTeam, setWorldTeam] = useState("");
  const [sheets, setSheets] = useState<Record<string, { player: string; note: string }>>({});
  const [rename, setRename] = useState({ name: "", kind: "", country: "", visibility_default: "" });

  const roleOf = (row: MemberRow) => roles[row.email] ?? row.role;

  return (
    <div className="stack">
      <div className="grid grid-2">
        <label className="field">
          <span>{tc("inviteEmailLabel")}</span>
          <input aria-label={tc("inviteEmailAria")} onChange={(event) => setEmail(event.target.value)} placeholder={tc("inviteEmailPlaceholder")} type="text" value={email} />
        </label>
        <label className="field">
          <span>{tc("inviteStandingLabel")}</span>
          <select aria-label={tc("inviteRoleAria")} onChange={(event) => setInviteRole(event.target.value)} value={inviteRole}>
            {rules.matrix.roles.map((row) => (
              <option key={row} value={row}>
                {row} — {rules.matrix.meaning[row]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="row wrap">
        <button className="btn btn--sm" data-testid="club-invite" disabled={busy !== null || email.trim().length === 0} onClick={() => void call("invite", `/club/${encodeURIComponent(ident)}/invites`, { body: { email: email.trim(), role: inviteRole } })} type="button">
          {busy === "invite" ? tc("inviteWriting") : tc("inviteAction")}
        </button>
        <span className="muted" style={{ fontSize: "0.84rem" }}>
          {tc("inviteWaiting", {
            count: members.filter((row) => row.status === "invited").length,
          })}{" "}
          {rules.invitations}
        </span>
      </div>

      <div className="world-tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{tc("thMember")}</th>
              <th scope="col">{tc("thStanding")}</th>
              <th scope="col">{t("status")}</th>
              <th scope="col">{tc("thRightsHeld")}</th>
              <th scope="col">{tc("thChangeRevoke")}</th>
            </tr>
          </thead>
          <tbody>
            {members.map((row) => (
              <tr data-member={row.email} key={row.id}>
                <td>
                  {row.display_name}
                  <div className="muted mono" style={{ fontSize: "0.78rem" }}>
                    {row.email}
                  </div>
                </td>
                <td>
                  <select aria-label={tc("roleForAria", { email: row.email })} disabled={busy !== null} onChange={(event) => setRoles({ ...roles, [row.email]: event.target.value })} value={roleOf(row)}>
                    {rules.matrix.roles.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <span className={row.status === "active" ? "badge badge--live" : "badge badge--demo"}>{row.status.toUpperCase()}</span>
                  {!row.known_role && <span className="chip mono">{tc("roleNotInMatrix")}</span>}
                </td>
                <td className="muted" style={{ fontSize: "0.8rem" }}>
                  {row.permissions.length} of {rules.matrix.permissions.length}
                  <div className="muted" style={{ fontSize: "0.76rem" }}>
                    {row.why}
                  </div>
                </td>
                <td>
                  <div className="row wrap">
                    <button className="btn btn--sm btn--ghost" data-act="set-role" disabled={busy !== null || roleOf(row) === row.role} onClick={() => void call(`role-${row.email}`, `/club/${encodeURIComponent(ident)}/members`, { body: { email: row.email, role: roleOf(row) }, method: "PATCH" })} type="button">
                      {tc("setRole")}
                    </button>
                    <button className="btn btn--sm btn--ghost" data-act="revoke" disabled={busy !== null || row.status !== "active"} onClick={() => void call(`revoke-${row.email}`, `/club/${encodeURIComponent(ident)}/members/${encodeURIComponent(row.email)}`, { method: "DELETE" })} type="button">
                      {tc("revoke")}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="panel__title">{tc("addTeamSheetTitle")}</h3>
      <div className="grid grid-2">
        <label className="field">
          <span>{tc("teamNameLabel", { max: rules.team_name_max })}</span>
          <input aria-label={tc("teamNameAria")} maxLength={rules.team_name_max} onChange={(event) => setTeamName(event.target.value)} placeholder={tc("teamNamePlaceholder")} type="text" value={teamName} />
        </label>
        <label className="field">
          <span>{tc("ageBandLabel")}</span>
          <input aria-label={tc("ageGroupAria")} onChange={(event) => setAgeGroup(event.target.value)} type="text" value={ageGroup} />
        </label>
        <label className="field">
          <span>{tc("stageLabel")}</span>
          <input aria-label={tc("stageAria")} onChange={(event) => setStage(event.target.value)} type="text" value={stage} />
        </label>
        <label className="field">
          <span>{tc("worldClubLabel")}</span>
          <input aria-label={tc("worldTeamAria")} onChange={(event) => setWorldTeam(event.target.value)} placeholder={tc("worldTeamPlaceholder")} type="text" value={worldTeam} />
        </label>
      </div>
      <div className="row wrap">
        <button className="btn btn--sm" data-testid="team-create" disabled={busy !== null || teamName.trim().length === 0 || teams.length >= rules.max_teams_per_organization} onClick={() => void call("team", `/club/${encodeURIComponent(ident)}/teams`, { body: { name: teamName.trim(), age_group: ageGroup, stage, world_team: worldTeam.trim() || null } })} type="button">
          {busy === "team"
            ? tc("teamAdding")
            : teams.length >= rules.max_teams_per_organization
              ? tc("teamLimit", { max: rules.max_teams_per_organization })
              : tc("teamAdd")}
        </button>
        <span className="muted" style={{ fontSize: "0.84rem" }}>
          {tc("teamSheetsUsed", {
            count: teams.length,
            max: rules.max_teams_per_organization,
          })}
        </span>
      </div>

      {teams.map((team) => (
        <div className="panel" data-team={team.id} key={team.id}>
          <div className="row wrap" style={{ alignItems: "baseline", justifyContent: "space-between" }}>
            <div>
              <strong>{team.name}</strong> <span className="muted">· {team.age_group} · {team.stage}</span>
            </div>
            <div className="row wrap">
              <span className="chip mono">
                {tc("onSheet", { count: team.squad_size, max: rules.max_squad_per_team })}
              </span>
              <span className="chip mono">{tc("under18", { count: team.minors_on_sheet })}</span>
              <button className="btn btn--sm btn--ghost" data-act="team-delete" disabled={busy !== null} onClick={() => void call(`team-${team.id}`, `/club/${encodeURIComponent(ident)}/teams/${encodeURIComponent(team.id)}`, { method: "DELETE" })} type="button">
                {tc("deleteSheet")}
              </button>
            </div>
          </div>
          <div className="grid grid-2">
            <label className="field">
              <span>{tc("playerSlugLabel")}</span>
              <input aria-label={tc("playerForAria", { team: team.name })} onChange={(event) => setSheets({ ...sheets, [team.id]: { player: event.target.value, note: sheets[team.id]?.note ?? "" } })} placeholder={tc("playerSlugPlaceholder")} type="text" value={sheets[team.id]?.player ?? ""} />
            </label>
            <label className="field">
              <span>{tc("noteLabel", { max: rules.note_max })}</span>
              <input aria-label={tc("noteForAria", { team: team.name })} maxLength={rules.note_max} onChange={(event) => setSheets({ ...sheets, [team.id]: { player: sheets[team.id]?.player ?? "", note: event.target.value } })} type="text" value={sheets[team.id]?.note ?? ""} />
            </label>
          </div>
          <div className="row wrap">
            <button className="btn btn--sm" data-act="squad-add" disabled={busy !== null || (sheets[team.id]?.player ?? "").trim().length === 0 || team.room_left <= 0} onClick={() => void call(`squad-${team.id}`, `/club/${encodeURIComponent(ident)}/teams/${encodeURIComponent(team.id)}/players`, { body: { player: (sheets[team.id]?.player ?? "").trim(), note: sheets[team.id]?.note ?? "" } })} type="button">
              {busy === `squad-${team.id}`
                ? tc("squadAdding")
                : team.room_left <= 0
                  ? tc("sheetFull", { max: rules.max_squad_per_team })
                  : tc("putOnSheet")}
            </button>
          </div>
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{tc("thPlayer")}</th>
                  <th scope="col">{tc("thAge")}</th>
                  <th scope="col">{tc("thPosition")}</th>
                  <th scope="col">{tc("thOverall")}</th>
                  <th scope="col">{tc("thPotential")}</th>
                  <th scope="col">{tc("thNote")}</th>
                  <th scope="col">{tc("thOff")}</th>
                </tr>
              </thead>
              <tbody>
                {team.squad.map((row) => (
                  <tr data-player={row.slug} key={row.player_id}>
                    <td>
                      <a className="world-link" href={row.path}>
                        {row.name}
                      </a>
                    </td>
                    <td className="num">
                      {row.age}
                      {row.is_minor && <span className="chip mono">{tc("minorChip")}</span>}
                    </td>
                    <td className="mono">{row.position}</td>
                    <td className="num">{row.overall}</td>
                    <td className="num">{row.potential}</td>
                    <td className="muted">{row.note || "—"}</td>
                    <td>
                      <button className="btn btn--sm btn--ghost" data-act="squad-drop" disabled={busy !== null} onClick={() => void call(`drop-${row.slug}`, `/club/${encodeURIComponent(ident)}/teams/${encodeURIComponent(team.id)}/players/${encodeURIComponent(row.slug)}`, { method: "DELETE" })} type="button">
                        {tc("takeOff")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ fontSize: "0.8rem" }}>
            {team.figures_from}
          </p>
        </div>
      ))}

      <h3 className="panel__title">{tc("tenantNameTitle")}</h3>
      <div className="grid grid-2">
        <label className="field">
          <span>{tc("newNameLabel")}</span>
          <input aria-label={tc("renameAria")} maxLength={rules.name_max} onChange={(event) => setRename({ ...rename, name: event.target.value })} type="text" value={rename.name} />
        </label>
        <label className="field">
          <span>{tc("newKindLabel")}</span>
          <select aria-label={tc("newKindAria")} onChange={(event) => setRename({ ...rename, kind: event.target.value })} value={rename.kind}>
            <option value="">{tc("leaveAsIs")}</option>
            {rules.kinds.map((row) => (
              <option key={row} value={row}>
                {row}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{tc("newCountryLabel")}</span>
          <input aria-label={tc("newCountryAria")} onChange={(event) => setRename({ ...rename, country: event.target.value })} type="text" value={rename.country} />
        </label>
        <label className="field">
          <span>{tc("newVisibilityLabel")}</span>
          <select aria-label={tc("newVisibilityAria")} onChange={(event) => setRename({ ...rename, visibility_default: event.target.value })} value={rename.visibility_default}>
            <option value="">{tc("leaveAsIs")}</option>
            {rules.visibility_defaults.map((row) => (
              <option key={row} value={row}>
                {row}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="row wrap">
        <button className="btn btn--sm" data-testid="club-rename" disabled={busy !== null} onClick={() => void call("rename", `/club/${encodeURIComponent(ident)}`, { body: rename, method: "PATCH" })} type="button">
          {t("apply")}
        </button>
        <button className="btn btn--sm btn--ghost" data-testid="club-close" disabled={busy !== null} onClick={() => void call("close", `/club/${encodeURIComponent(ident)}`, { method: "DELETE" })} type="button">
          {t("close")} {tc("closeOrganisation")}
        </button>
      </div>
      <CallNote note={note} />
    </div>
  );
}
