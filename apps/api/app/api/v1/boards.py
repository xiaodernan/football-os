"""User tactics boards: create, edit, share by token (spec §13 "Tactical Board", §21 sharing, §61 privacy).

Ownership rules first: everything under `/boards` needs a session, and a board the caller does not
own reads as 404 (`ownership_or_admin`) rather than 403 — the difference matters only to an attacker
probing for ids. The one public door is `GET /boards/shared/{token}`, which is read-only, returns no
owner identity, and is worth less than nothing to a crawler because the token is 32 random bytes:
an unshared board has no URL at all, and revoking clears the token instead of deleting the work.

Coordinates are validated on the way in, and metrics are recomputed on the way out, so what a shared
board displays is a measurement of the dots it shows.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, limit, new_public_id, ownership_or_admin
from app.models import TacticBoard, User
from app.services.tactics.boards import BOARD_LIMIT_PER_USER, block_settings, derive_block, metrics_for, problems_with
from app.services.tactics.plan import system_by_slug
from app.services.tactics.roles import ROLES
from app.services.world.names import slugify

router = APIRouter(prefix="/boards", tags=["tactics-boards"])

NOT_FOUND: Final = {"code": "not_found", "message": "No such board for this account"}
USER_DISCLAIMER = (
    "This board was arranged by a FOOTBALL OS user, not by the project. Its measurements are computed from "
    "the positions they placed, which makes them a description of this drawing and not of any real team."
)


class BoardIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    note: str = Field(default="", max_length=500)
    origin_system: str | None = Field(default=None, max_length=160)
    phase_in: list[dict[str, Any]] | None = None
    phase_out: list[dict[str, Any]] | None = None
    derive_block: bool = False
    block: dict[str, float] | None = None


class BoardPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    phase_in: list[dict[str, Any]] | None = None
    phase_out: list[dict[str, Any]] | None = None
    derive_block: bool = False
    block: dict[str, float] | None = None


class VisibilityIn(BaseModel):
    visibility: str = Field(min_length=4, max_length=12)


def _row(board: TacticBoard, *, owner: bool = True, share_url: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": board.id,
        "slug": board.slug,
        "name": board.name,
        "note": board.note,
        "origin_system": board.origin_system,
        "visibility": board.visibility if owner else "shared",
        "phase_in": board.phase_in,
        "phase_out": board.phase_out,
        "metrics_in": metrics_for(board.phase_in),
        "metrics_out": metrics_for(board.phase_out),
        "roles": [ROLES[role].to_dict() for role in {str(row.get("role", "")) for row in board.phase_in} if role in ROLES],
        "updated_at": board.updated_at.isoformat() if board.updated_at else None,
        "data_origin": board.data_origin,
        "is_demo_data": board.is_demo_data,
        "disclaimer": USER_DISCLAIMER,
    }
    if owner:
        payload["share_url"] = share_url
        payload["shared_at"] = board.shared_at.isoformat() if board.shared_at else None
    payload["path"] = f"/tactics/board/{board.slug}"
    return payload


def _mine(db: Session, user: User) -> list[TacticBoard]:
    return list(db.scalars(select(TacticBoard).where(TacticBoard.owner_id == user.id).order_by(TacticBoard.updated_at.desc())).all())


def _one(db: Session, user: User, ident: str) -> TacticBoard:
    board = db.scalar(select(TacticBoard).where(or_(TacticBoard.slug == ident, TacticBoard.id == ident)))
    if board is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    ownership_or_admin(user, board.owner_id, "board")
    return board


def _validated(payload: BoardIn | BoardPatchIn, *, current: TacticBoard | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve the two phases to store, then refuse the whole write if either is not eleven players.

    A patch may move only the possession shape and ask for the block to be derived from it — that is
    the "press these eleven back into a block" action, and it runs through the same transform the
    authored catalogue was built with, so the result is checkable against a formula rather than
    guessed by the browser.
    """
    if isinstance(payload, BoardIn):
        phase_in = list(payload.phase_in or [])
        phase_out = list(payload.phase_out or [])
        origin = payload.origin_system
    else:
        phase_in = list(payload.phase_in or (current.phase_in if current else []))
        phase_out = list(payload.phase_out or (current.phase_out if current else []))
        origin = None

    block = block_settings(payload.block)
    if payload.derive_block or not phase_out:
        phase_out = derive_block(phase_in, block) if phase_in else phase_out

    problems = problems_with(phase_in, label="phase_in") + problems_with(phase_out, label="phase_out")
    if origin and system_by_slug(origin) is None:
        problems.append(f"origin_system {origin!r} is not a stored tactical system")
    if problems:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_board", "message": "; ".join(problems[:6]), "problems": problems},
        )
    return phase_in, phase_out


@router.get("")
def list_boards(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """The account's own boards, newest first, with their recomputed measurements."""
    limit(request, 60, 60, scope="boards_list")
    boards = _mine(db, user)
    return {
        "items": [_row(board) for board in boards],
        "total": len(boards),
        "limit_per_user": BOARD_LIMIT_PER_USER,
        "data_origin": "user",
        "disclaimer": USER_DISCLAIMER,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_board(
    payload: BoardIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Start a board — from one of the 50 authored systems, or from the caller's own positions."""
    limit(request, 20, 60, scope="boards_create")
    if int(db.scalar(select(func.count()).select_from(TacticBoard).where(TacticBoard.owner_id == user.id)) or 0) >= BOARD_LIMIT_PER_USER:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "board_limit", "message": f"{BOARD_LIMIT_PER_USER} boards per account is the current ceiling"},
        )
    phase_in, phase_out = _validated(payload)
    slug = slugify(f"{payload.name}-{user.id[-4:]}")[:150]
    if db.scalar(select(TacticBoard).where(TacticBoard.slug == slug)):
        slug = f"{slug}-{secrets.token_hex(2)}"[:150]
    board = TacticBoard(
        id=new_public_id("tbd"),
        owner_id=user.id,
        slug=slug,
        name=payload.name.strip(),
        note=payload.note.strip(),
        origin_system=payload.origin_system,
        phase_in=phase_in,
        phase_out=phase_out,
        visibility="private",
        data_origin="user",
        is_demo_data=False,
    )
    db.add(board)
    db.commit()
    db.refresh(board)
    return _row(board)


@router.get("/{ident}")
def read_board(
    ident: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    limit(request, 60, 60, scope="boards_read")
    return _row(_one(db, user, ident))


@router.patch("/{ident}")
def update_board(
    ident: str,
    payload: BoardPatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Save the board after dragging: positions are revalidated, metrics recomputed."""
    limit(request, 60, 60, scope="boards_update")
    board = _one(db, user, ident)
    phase_in, phase_out = _validated(payload, current=board)
    if payload.name:
        board.name = payload.name.strip()
    if payload.note is not None:
        board.note = payload.note.strip()
    board.phase_in = phase_in
    board.phase_out = phase_out
    board.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(board)
    return _row(board)


# `response_model=None` is required because `from __future__ import annotations` turns the return
# annotation into the string "None", which FastAPI would otherwise try to model as a response body
# for a 204.
@router.delete("/{ident}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_board(
    ident: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    limit(request, 20, 60, scope="boards_delete")
    board = _one(db, user, ident)
    db.delete(board)
    db.commit()


@router.post("/{ident}/share")
def share_board(
    ident: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Hand out a link. The token is created on first share and reused, so an old link keeps working."""
    limit(request, 10, 60, scope="boards_share")
    board = _one(db, user, ident)
    if not board.share_token:
        board.share_token = secrets.token_hex(16)
        board.shared_at = datetime.now(UTC)
    board.visibility = "shared"
    db.commit()
    db.refresh(board)
    return {"id": board.id, "slug": board.slug, "share_token": board.share_token, "share_url": f"/tactics/board/{board.slug}?token={board.share_token}", "visibility": board.visibility}


@router.post("/{ident}/revoke")
def revoke_share(
    ident: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """The link stops working immediately; the board itself stays."""
    limit(request, 10, 60, scope="boards_revoke")
    board = _one(db, user, ident)
    board.share_token = None
    board.visibility = "private"
    db.commit()
    db.refresh(board)
    return {"id": board.id, "slug": board.slug, "visibility": board.visibility, "share_url": None}


@router.get("/shared/{token}")
def read_shared(token: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """The public read-only view. No account, no owner identity, and no way to reach it by guessing."""
    limit(request, 60, 60, scope="boards_shared_read")
    board = db.scalar(select(TacticBoard).where(TacticBoard.share_token == token, TacticBoard.visibility == "shared"))
    if board is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "This link no longer points at a board"})
    row = _row(board, owner=False)
    row["owner"] = {"name": "a FOOTBALL OS account", "id": None}
    row["path"] = f"/tactics/board/{board.slug}"
    return row
