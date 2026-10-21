"""Account-level erasure (spec §61, M12): one preview, one confirmed transaction, no retained identity.

The database already cascades every row whose foreign key points at `users.id`, but a cascade is not a data
right by itself. Some account-linked rows deliberately have no foreign key (jobs, model calls, RAG queries,
usage events, audit logs), uploaded video bytes live outside the database, and an account may be the last owner
of a tenant that other people still use. Those are the reasons this module exists instead of a single
`session.delete(user)`.

The rule is deliberately conservative for organisations: a tenant with other active members survives only when
another active owner remains. If the departing account is the last owner and anyone else is still standing in
the tenant, erasure is refused before any row or file is touched; deleting the tenant silently would destroy
somebody else's records.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import Base
from app.core.security import new_public_id
from app.models import (
    AuditLog,
    Job,
    KnowledgeQuery,
    ModelCall,
    Organization,
    OrganizationMember,
    RevokedToken,
    UsageEvent,
    User,
    VideoAsset,
)

ACCOUNT_DELETE_PHRASE: Final = "DELETE"

#: The account-linked rows the database **cannot** cascade, because their id columns carry no foreign key
#: to `users.id` — and what happens to each of them: `deleted` removes the row, `anonymised` keeps the
#: row and takes the account id out of it.
#:
#: The list is a contract, and a contract in a service rots the day a table is added. A census holds it
#: against the schema (`tests/test_account_erasure_coverage.py`): every table that holds an account's row
#: without a foreign key to `users.id` must be named here, with its fate, or the erasure would leave it
#: behind and the inventory would not say so.
NO_FOREIGN_KEY_ACCOUNT_ROWS: Final[dict[str, str]] = {
    "audit_logs.user_id": "anonymised",
    "jobs.user_id": "deleted",
    "model_calls.user_id": "anonymised",
    "knowledge_queries.user_id": "deleted",
    "revoked_tokens.user_id": "deleted",
    "usage_events.subject_id": "deleted",
}

#: The column names a table uses when it holds an account's id. A table with one of these and no
#: foreign key to `users.id` cannot be cascaded, so the erasure has to say what happens to it.
ACCOUNT_ID_COLUMN_NAMES: Final[frozenset[str]] = frozenset(
    {"user_id", "owner_id", "author_id", "account_id", "created_by"}
)


class AccountDeletionBlocked(RuntimeError):
    """The account is the last owner of a tenant that still has other active members."""

    def __init__(self, organizations: list[dict[str, Any]]) -> None:
        super().__init__("Transfer or delete every tenant that would be left without an owner")
        self.organizations = organizations


class AccountDeletionStorageError(RuntimeError):
    """A private file could not be removed, so the database transaction must not begin."""


def _count(session: Session, model: Any, *conditions: Any) -> int:
    return int(session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)


def _user_foreign_key_counts(session: Session, user_id: str) -> tuple[dict[str, int], dict[str, int]]:
    """Count every column that points at `users.id`, split by what will happen to its row.

    Reading the contract from metadata keeps the preview honest when a new user-owned table is added: it appears
    in the inventory on the next request rather than silently joining the erasure without being disclosed.
    """
    erased: dict[str, int] = {}
    retained: dict[str, int] = {}
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            for foreign_key in column.foreign_keys:
                if foreign_key.target_fullname != "users.id":
                    continue
                count = _count(session, table, column == user_id)
                if not count:
                    continue
                key = f"{table.name}.{column.name}"
                if str(foreign_key.ondelete).upper() == "SET NULL":
                    retained[key] = count
                else:
                    erased[key] = count
    return erased, retained


def _no_foreign_key_counts(session: Session, user_id: str) -> dict[str, int]:
    """Account-linked rows the DB cannot cascade because their id columns have no foreign key."""
    counts = {
        "audit_logs.user_id": _count(session, AuditLog, AuditLog.user_id == user_id),
        "jobs.user_id": _count(session, Job, Job.user_id == user_id),
        "model_calls.user_id": _count(session, ModelCall, ModelCall.user_id == user_id),
        "knowledge_queries.user_id": _count(session, KnowledgeQuery, KnowledgeQuery.user_id == user_id),
        "revoked_tokens.user_id": _count(session, RevokedToken, RevokedToken.user_id == user_id),
        "usage_events.subject_id": _count(session, UsageEvent, UsageEvent.subject_kind == "user", UsageEvent.subject_id == user_id),
    }
    # The contract above and the rows below are one list. If they drift, the erasure would leave a row
    # behind and the inventory would not have said so.
    missing = set(NO_FOREIGN_KEY_ACCOUNT_ROWS) - set(counts)
    unexpected = set(counts) - set(NO_FOREIGN_KEY_ACCOUNT_ROWS)
    if missing or unexpected:
        raise RuntimeError(
            "the account erasure's table list has drifted from its contract: "
            f"missing {sorted(missing)}, unexpected {sorted(unexpected)}"
        )
    return counts


def _organizations(session: Session, user: User) -> list[Organization]:
    created = set(session.scalars(select(Organization.id).where(Organization.created_by == user.id)).all())
    joined = set(session.scalars(select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user.id)).all())
    rows = [session.get(Organization, ident) for ident in sorted(created | joined)]
    return [row for row in rows if row is not None]


def organization_plan(session: Session, user: User) -> dict[str, list[dict[str, Any]]]:
    """What deleting this account does to each tenant, decided before anything is changed."""
    deleted: list[dict[str, Any]] = []
    left: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for organization in _organizations(session, user):
        other_active = _count(
            session,
            OrganizationMember,
            OrganizationMember.organization_id == organization.id,
            OrganizationMember.user_id != user.id,
            OrganizationMember.status == "active",
        )
        other_owners = _count(
            session,
            OrganizationMember,
            OrganizationMember.organization_id == organization.id,
            OrganizationMember.user_id != user.id,
            OrganizationMember.role == "owner",
            OrganizationMember.status == "active",
        )
        row = {
            "id": organization.id,
            "slug": organization.slug,
            "name": organization.name,
            "other_active_members": other_active,
            "other_active_owners": other_owners,
        }
        if other_active == 0:
            row["action"] = "delete"
            row["reason"] = "no other active member remains, so the empty tenant and its rows go with the account"
            deleted.append(row)
        elif other_owners > 0:
            row["action"] = "leave"
            row["reason"] = "another active owner remains, so the membership goes and the tenant's rows stay"
            left.append(row)
        else:
            row["action"] = "blocked"
            row["reason"] = "this is the last active owner; transfer ownership or delete the tenant first"
            blocked.append(row)
    return {"deleted": deleted, "left": left, "blocked": blocked}


def _video_assets(session: Session, user_id: str) -> list[VideoAsset]:
    return list(session.scalars(select(VideoAsset).where(VideoAsset.owner_id == user_id)).all())


def _safe_private_path(path: Path) -> Path:
    root = Path(settings.storage_dir).resolve()
    candidate = path.resolve()
    if candidate != root and root not in candidate.parents:
        raise AccountDeletionStorageError(f"refusing to remove a path outside private storage: {candidate}")
    return candidate


def _unlink_assets(assets: list[VideoAsset]) -> dict[str, int]:
    """Remove original clips and sampled frames; refuse the database transaction if any removal fails."""
    files_removed = 0
    directories_removed = 0
    bytes_removed = 0
    root = Path(settings.storage_dir).resolve()
    for asset in assets:
        original = _safe_private_path(root / asset.storage_key)
        frames = _safe_private_path(root / "frames" / asset.id)
        try:
            if original.exists() or original.is_symlink():
                bytes_removed += original.stat().st_size
                original.unlink()
                files_removed += 1
            if frames.exists() or frames.is_symlink():
                children = sorted(frames.rglob("*"), key=lambda item: len(item.parts), reverse=True)
                for child in children:
                    if child.is_symlink() or child.is_file():
                        bytes_removed += child.stat().st_size
                        child.unlink(missing_ok=True)
                        files_removed += 1
                    elif child.is_dir():
                        child.rmdir()
                frames.rmdir()
                directories_removed += 1
        except OSError as error:
            raise AccountDeletionStorageError(f"could not remove stored media for {asset.id}: {error}") from error
    return {"files_removed": files_removed, "directories_removed": directories_removed, "bytes_removed": bytes_removed}


def preview(session: Session, user: User) -> dict[str, Any]:
    """The deletion receipt before confirmation: what goes, what stays anonymous, and what blocks it."""
    erased, retained = _user_foreign_key_counts(session, user.id)
    erased.update(_no_foreign_key_counts(session, user.id))
    organizations = organization_plan(session, user)
    assets = _video_assets(session, user.id)
    private_bytes = sum(max(0, int(asset.size_bytes)) for asset in assets)
    return {
        "can_delete": not organizations["blocked"],
        "confirmation": {"phrase": ACCOUNT_DELETE_PHRASE, "password_required": True},
        "deletes": {
            "rows": erased,
            "rows_total": sum(erased.values()),
            "video_assets": len(assets),
            "video_bytes": private_bytes,
            "organizations": organizations["deleted"],
        },
        "retained_anonymized": {
            "rows": {**retained, "model_calls.user_id": _count(session, ModelCall, ModelCall.user_id == user.id)},
            "identity_removed": True,
            "basis": "operational and tenant records keep their facts while every account id and free-text audit detail is removed",
        },
        "organizations_left": organizations["left"],
        "blocking_organizations": organizations["blocked"],
        "rules": {
            "confirm": f"send {{\"confirm\": \"{ACCOUNT_DELETE_PHRASE}\", \"password\": \"…\"}}; a wrong phrase or password removes nothing",
            "organisations": "a last active owner cannot delete their account while other active members still use the tenant",
            "media": "video originals and sampled frames are removed from private storage before the database transaction starts",
            "audit": "prior audit rows are kept as aggregate action records with no account id and no free-text detail",
        },
    }


def erase(session: Session, user: User) -> dict[str, Any]:
    """Erase the account after the caller has verified the phrase and password."""
    plan = organization_plan(session, user)
    if plan["blocked"]:
        raise AccountDeletionBlocked(plan["blocked"])

    erased, retained = _user_foreign_key_counts(session, user.id)
    erased.update(_no_foreign_key_counts(session, user.id))
    assets = _video_assets(session, user.id)
    media = _unlink_assets(assets)

    account_id = user.id
    account_role = user.role
    account_plan = user.plan
    organizations_deleted = [row["slug"] for row in plan["deleted"]]
    organizations_left = [row["slug"] for row in plan["left"]]

    for organization in _organizations(session, user):
        if any(row["id"] == organization.id for row in plan["deleted"]):
            session.delete(organization)
    session.flush()

    # No-FK rows are removed explicitly. Model calls and audit logs are retained without the account id, so
    # provider cost totals and operational action counts survive while the account's identity does not.
    session.execute(delete(Job).where(Job.user_id == account_id))
    session.execute(delete(KnowledgeQuery).where(KnowledgeQuery.user_id == account_id))
    session.execute(delete(RevokedToken).where(RevokedToken.user_id == account_id))
    session.execute(delete(UsageEvent).where(UsageEvent.subject_kind == "user", UsageEvent.subject_id == account_id))
    session.execute(update(ModelCall).where(ModelCall.user_id == account_id).values(user_id=None))
    session.execute(update(AuditLog).where(AuditLog.user_id == account_id).values(user_id=None, detail={}))

    audit = AuditLog(
        id=new_public_id("aud"),
        user_id=None,
        action="account.deleted",
        detail={
            "rows_erased": sum(erased.values()),
            "assets_erased": len(assets),
            "organizations_deleted": len(organizations_deleted),
            "organizations_left": len(organizations_left),
            "identity_retained": False,
            "role_category_retained": account_role,
            "plan_category_retained": account_plan,
        },
    )
    session.add(audit)
    session.delete(user)
    session.commit()

    return {
        "deleted": True,
        "rows_erased": sum(erased.values()),
        "video_assets_erased": len(assets),
        "files_removed": media["files_removed"],
        "bytes_removed": media["bytes_removed"],
        "organizations_deleted": organizations_deleted,
        "organizations_left": organizations_left,
        "retained_anonymized_rows": sum(retained.values()),
        "audit_id": audit.id,
        "identity_retained": False,
        "message": "Account and private media erased. Only aggregate operational records remain, without the account id.",
    }


__all__ = [
    "ACCOUNT_DELETE_PHRASE",
    "AccountDeletionBlocked",
    "AccountDeletionStorageError",
    "erase",
    "organization_plan",
    "preview",
]
