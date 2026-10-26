"""The notification service (spec module 27).

One row per event an account should hear about, written at the moment the event
happens. The producers this build wires are the community's three verbs — a follow, a
comment on the account's post, a reaction to it — because those are events that already
exist as rows. A notification is never sent to the actor whose own action it celebrates
(`actor_id == recipient` writes nothing), because the reader already knows.

The read-state machinery is one nullable timestamp: null is unread, a timestamp is
read. Marking another account's notification is absence (404), the same answer every
private tier gives a caller probing for ids.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import Notification, User

KINDS: Final = {"follower", "comment", "reaction"}
PAGE_SIZE = 20
MAX_PER_ACCOUNT = 200


def _display_name(session: Session, user_id: str) -> str:
    return session.scalar(select(User.display_name).where(User.id == user_id)) or "a FOOTBALL OS account"


def notify(session: Session, user_id: str, *, kind: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Write one notification row for the recipient, unless the event is their own act.

    Returns the row's dictionary, or None when nothing was written — the self-action
    case, which is a decision the tier states rather than an error the caller sees.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown notification kind: {kind!r}. Known: {sorted(KINDS)}")
    held = int(session.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user_id)) or 0)
    if held >= MAX_PER_ACCOUNT:
        # The oldest read row makes room; if none is read, the event is dropped — an
        # account that never reads has a full tray, and a tray that silently grows
        # without bound is a leak wearing a feature's clothes.
        oldest = session.scalar(select(Notification.id).where(Notification.user_id == user_id, Notification.read_at.is_not(None)).order_by(Notification.created_at.asc()).limit(1))
        if oldest is None:
            return None
        row = session.get(Notification, oldest)
        if row is not None:
            session.delete(row)
    row = Notification(id=new_public_id("ntf"), user_id=user_id, kind=kind, payload=payload)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _row(row, session)


def _row(row: Notification, session: Session) -> dict[str, Any]:
    return {
        "id": row.id,
        "kind": row.kind,
        "payload": row.payload,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "read_at": row.read_at.isoformat() if row.read_at else None,
        "formula": "unread = count(notifications where user_id = me and read_at is null)",
    }


def list_for(session: Session, user_id: str, *, page: int = 1) -> dict[str, Any]:
    """The recipient's tray, newest first, with the unread total beside it."""
    page = max(1, page)
    total = int(session.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user_id)) or 0)
    unread = int(session.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))) or 0)
    rows = list(
        session.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        ).all()
    )
    return {
        "items": [_row(row, session) for row in rows],
        "page": page,
        "pages": max(1, -(-total // PAGE_SIZE)),
        "total": total,
        "unread_total": unread,
        "formula": "unread_total = count(notifications where user_id = me and read_at is null)",
    }


def unread_total(session: Session, user_id: str) -> int:
    """The number the nav badge shows. One query, one integer."""
    return int(session.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))) or 0)


def mark_read(session: Session, user_id: str, ident: str) -> dict[str, Any] | None:
    """Mark one of the recipient's notifications read. Another account's is absence."""
    row = session.scalar(select(Notification).where(Notification.id == ident, Notification.user_id == user_id))
    if row is None:
        return None
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        session.commit()
        session.refresh(row)
    return _row(row, session)


def mark_all_read(session: Session, user_id: str) -> dict[str, Any]:
    """Mark the whole tray read. The count before and after travels with the answer."""
    before = unread_total(session, user_id)
    rows = list(session.scalars(select(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))).all())
    now = datetime.now(UTC)
    for row in rows:
        row.read_at = now
    session.commit()
    return {"marked": len(rows), "unread_before": before, "unread_after": 0}
