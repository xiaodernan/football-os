"""§39 and §41's permissions: a role is stored, what it grants is published, and the default is deny.

The rule this module exists to enforce is one sentence: *a member of one organisation cannot read another's
rows*. Everything else here is in service of making that checkable rather than scattered.

Three choices are worth stating:

* **The role is data and the matrix is code.** `organization_members.role` is the only thing stored about what
  a person may do. Storing permissions per row would let one membership drift away from its title with no
  record of when or by whom, and the question a member actually asks — *why can this person see that?* —
  would stop having an answer. `matrix()` is therefore published by the API, and a page shows it instead of
  paraphrasing it.
* **Unknown role grants nothing, and that is louder than an empty list.** `permissions_of("team_boss")` returns
  nothing, and `grant()` says so in words. A typo in a role string must not quietly become a person with a
  title and no access, because the opposite failure — a typo with a name nobody checked — is how a tenant
  leaks. Both are refused at the door that sets the role, so the silent case cannot be reached by the API.
* **Only an active membership grants anything.** An `invited` person has a row and no rights; a `revoked` one
  keeps the row, for the audit trail, and loses the rights. That is the whole reason `status` is a string and
  not a deletion.
"""

from __future__ import annotations

from typing import Any, Final

ROLES: Final = ("owner", "director", "coach", "analyst", "scout", "parent")

#: Every right the tiers below can ask about. Adding one here and not to a row of the matrix is caught by the
#: suite: the matrix must cover its own vocabulary.
PERMISSIONS: Final = (
    "org.rename",
    "org.member.invite",
    "org.member.role",
    "org.member.revoke",
    "org.delete",
    "team.create",
    "team.edit",
    "team.delete",
    "squad.read",
    "squad.write",
    "plan.read_all",
    "plan.write",
)

#: What each role holds. `parent` holds nothing yet: §40 gives it a right scoped to one child's own plan, and
#: until that tier exists an empty row is the honest answer rather than a claim about it.
_MATRIX: Final[dict[str, tuple[str, ...]]] = {
    "owner": PERMISSIONS,
    "director": ("org.rename", "org.member.invite", "org.member.role", "org.member.revoke", "team.create", "team.edit", "team.delete", "squad.read", "squad.write", "plan.read_all"),
    "coach": ("team.edit", "squad.read", "squad.write", "plan.read_all", "plan.write"),
    "analyst": ("squad.read", "plan.read_all", "plan.write"),
    "scout": ("squad.read",),
    "parent": (),
}

ROLE_MEANING: Final[dict[str, str]] = {
    "owner": "the account that opened the organisation, and the one that cannot be revoked while it stands alone",
    "director": "runs the whole tenant's roster and staffing, but cannot delete the tenant or hand over ownership",
    "coach": "works with the teams they are staffed on: selection, squad notes, and the plans of their own players",
    "analyst": "reads the squad and writes reports and plans, and does not touch staffing or teams",
    "scout": "sees a squad list and nothing else — the §23 tools a scout uses are their own account's, not the tenant's",
    "parent": "grants nothing yet; §40 replaces this row with a right scoped to one named child",
}


def is_role(value: str) -> bool:
    return str(value) in ROLES


def permissions_of(role: str) -> tuple[str, ...]:
    """What a role grants. Anything unknown grants nothing, and `matrix()` says which roles are known."""
    return _MATRIX.get(str(role).strip().lower(), ())


def may(role: str, permission: str) -> bool:
    """The one question every route asks. Written as a membership-level helper so no route can invent a rule."""
    return str(permission) in permissions_of(role)


def grant(role: str, status: str) -> dict[str, Any]:
    """The answer a member is shown about their own standing, including the two ways it grants nothing."""
    active = str(status) == "active"
    known = is_role(role)
    return {
        "role": role,
        "status": status,
        "active": active,
        "known_role": known,
        "permissions": list(permissions_of(role)) if (active and known) else [],
        "why": (
            "the role stored on this membership is not one of the published roles, so it grants nothing"
            if not known
            else "an invitation grants nothing until the person invited accepts it"
            if str(status) == "invited"
            else "a revoked membership keeps its row for the record and grants nothing"
            if str(status) == "revoked"
            else ROLE_MEANING.get(str(role), "")
        ),
    }


def matrix() -> dict[str, Any]:
    """The whole published picture: which roles exist, which rights they hold, and what the default is."""
    return {
        "roles": list(ROLES),
        "permissions": list(PERMISSIONS),
        "matrix": {role: list(permissions_of(role)) for role in ROLES},
        "meaning": dict(ROLE_MEANING),
        "statuses": ["active", "invited", "revoked"],
        "default": "deny — a role that is not in this matrix, and a membership that is not active, hold nothing",
        "stored": "role and status on the membership row",
        "not_stored": "permissions — they are read from this table every time, so a role change cannot be half-applied",
        "rule": "one rule sits under all of it: a member of one organisation can read and change nothing in another",
    }
