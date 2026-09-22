"""Tactical Lab endpoints (spec §11–§13, §62, §65, §80).

Reads are public: a tactical system is a project-authored coaching structure, not a user's data, and
the board is only useful if a coach can send someone a link. Two rules shape what these handlers
return:

* the geometry is **recomputed** from the stored coordinates rather than read out of a stored
  conclusion, so the numbers on a page always match the dots on the same page;
* every response carries the metric formulas and the disclaimer, so no surface can show a measurement
  without also showing what it was measured from (spec §62).
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import current_user, limit
from app.models import TACTICS_DISCLAIMER, TacticalSystem, User, UserPlayer
from app.services.tactics.analysis import CHANGES, METRIC_KEYS, Shape, apply_change, metrics_of, shape_from_rows
from app.services.tactics.feedback import build_feedback, fit_rows
from app.services.tactics.plan import SYSTEM_COUNT, fingerprint, system_path
from app.services.tactics.sync import TACTICS_GATE, tactics_counts, tactics_tables_present

router = APIRouter(prefix="/tactics", tags=["tactics"])

NOT_FOUND: Final = {"code": "not_found", "message": "No such tactical system in this database"}
NOT_READY: Final = {"code": "tactics_not_synced", "message": "The tactical catalogue has not been stored on this database yet"}
HEADLINE_METRICS: Final = ("width", "depth", "spacing", "space_behind", "balance")

# Keys the detail response builds itself, so the stored copy inside `board` must not collide with it.
DETAIL_OWN_KEYS: Final = frozenset(
    {
        "data_origin",
        "is_demo_data",
        "disclaimer",
        "id",
        "slug",
        "path",
        "name",
        "formation",
        "temperament_key",
        "press_line_y",
        "block_depth",
        "defensive_narrowing",
        "content_hash",
        "metrics_in",
        "metrics_out",
    }
)


def _envelope(**payload: Any) -> dict[str, Any]:
    """Provenance first: `data_origin`, `is_demo_data` and the disclaimer are on every response."""
    return {
        "data_origin": "project-authored",
        "is_demo_data": False,
        "disclaimer": TACTICS_DISCLAIMER,
        **payload,
    }


def _require_catalogue(session: Session) -> None:
    if not tactics_tables_present(session):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=NOT_READY)


def _one(session: Session, ident: str) -> TacticalSystem:
    row = session.scalar(select(TacticalSystem).where(or_(TacticalSystem.slug == ident, TacticalSystem.id == ident)))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return row


def _metrics_map(shape: Shape) -> dict[str, dict[str, Any]]:
    return {metric.key: metric.to_dict() for metric in metrics_of(shape)}


def _headline(metrics: dict[str, dict[str, Any]]) -> dict[str, float]:
    return {key: float(metrics[key]["value"]) for key in HEADLINE_METRICS if key in metrics}


def _row_brief(row: TacticalSystem) -> dict[str, Any]:
    board = dict(row.board or {})
    in_metrics = _metrics_map(shape_from_rows(list(board.get("phase_in") or [])))
    out_metrics = _metrics_map(shape_from_rows(list(board.get("phase_out") or [])))
    return {
        "id": row.id,
        "slug": row.slug,
        "path": system_path(row.slug),
        "name": row.name,
        "formation": row.formation,
        "temperament_key": row.temperament_key,
        "temperament_label": board.get("temperament_label", row.temperament_key),
        "idea": board.get("idea", ""),
        "press_line_y": row.press_line_y,
        "block_depth": row.block_depth,
        "content_hash": row.content_hash,
        "in_possession": _headline(in_metrics),
        "out_of_possession": _headline(out_metrics),
        "strengths": list(board.get("strengths") or []),
        "risks": list(board.get("risks") or []),
        "data_origin": row.data_origin,
        "is_demo_data": row.is_demo_data,
    }


@router.get("/status")
def tactics_status(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """What the catalogue holds and how each number on a tactics page is produced."""
    limit(request, 60, 60, scope="tactics_status")
    _require_catalogue(db)
    sample = db.scalar(select(TacticalSystem).order_by(TacticalSystem.slug).limit(1))
    metrics = [] if sample is None else list(dict(sample.board or {}).get("metrics_in") or [])
    forms = sorted({str(row[0]) for row in db.execute(select(TacticalSystem.formation).distinct()).all()})
    temperaments = sorted({str(row[0]) for row in db.execute(select(TacticalSystem.temperament_key).distinct()).all()})
    return _envelope(
        ready=tactics_counts(db)["tactical_systems"] >= SYSTEM_COUNT,
        counts=tactics_counts(db),
        gate=dict(TACTICS_GATE),
        stored=int(db.scalar(select(func.count()).select_from(TacticalSystem)) or 0),
        catalogue_fingerprint=fingerprint(),
        formations=forms,
        temperaments=temperaments,
        metrics=metrics,
        metric_keys=list(METRIC_KEYS),
        changes=[change.to_dict() for change in CHANGES.values()],
        auto_sync=settings.tactics_auto_sync,
        units={"width": "metres across the outfield players", "depth": "metres from deepest to most advanced"},
        note="Coordinates are authored by this project; every figure below is measured from them on request, not stored as a conclusion.",
    )


@router.get("")
def list_systems(
    request: Request,
    formation: str | None = Query(default=None, max_length=20),
    temperament: str | None = Query(default=None, max_length=40),
    search: str | None = Query(default=None, max_length=60),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    limit(request, 120, 60, scope="tactics_list")
    _require_catalogue(db)
    stmt = select(TacticalSystem).order_by(TacticalSystem.formation, TacticalSystem.temperament_key)
    if formation:
        stmt = stmt.where(TacticalSystem.formation == formation)
    if temperament:
        stmt = stmt.where(TacticalSystem.temperament_key == temperament)
    if search:
        needle = f"%{search.lower()}%"
        stmt = stmt.where(or_(func.lower(TacticalSystem.name).like(needle), func.lower(TacticalSystem.formation).like(needle)))
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
    return _envelope(
        items=[_row_brief(row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
        formations=sorted({row.formation for row in rows} | ({formation} if formation else set())),
        temperaments=sorted({row.temperament_key for row in rows} | ({temperament} if temperament else set())),
    )


@router.get("/compare")
def compare_systems(
    request: Request,
    a: str = Query(min_length=1, max_length=160),
    b: str = Query(min_length=1, max_length=160),
    phase: str = Query(default="in", pattern="^(in|out)$"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Two boards, the same eight measurements, and the difference between them."""
    limit(request, 60, 60, scope="tactics_compare")
    _require_catalogue(db)
    left, right = _one(db, a), _one(db, b)
    left_shape = shape_from_rows(list((left.board or {}).get(f"phase_{phase}") or []))
    right_shape = shape_from_rows(list((right.board or {}).get(f"phase_{phase}") or []))
    left_metrics, right_metrics = _metrics_map(left_shape), _metrics_map(right_shape)
    rows = [
        {
            "key": key,
            "label": left_metrics[key]["label"],
            "unit": left_metrics[key]["unit"],
            "formula": left_metrics[key]["formula"],
            "a": left_metrics[key]["value"],
            "b": right_metrics[key]["value"],
            "delta": round(right_metrics[key]["value"] - left_metrics[key]["value"], 2),
        }
        for key in METRIC_KEYS
    ]
    return _envelope(
        phase=phase,
        a=_row_brief(left),
        b=_row_brief(right),
        metrics=rows,
        note="Both sides are measured from their stored coordinates with the same functions, so a difference is arithmetic and not a choice of wording.",
    )


@router.get("/{ident}")
def system_detail(ident: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """One system: both phases' boards, the measurements, the graded verdicts and the roles in the field."""
    limit(request, 120, 60, scope="tactics_detail")
    _require_catalogue(db)
    row = _one(db, ident)
    board = dict(row.board or {})
    in_shape = shape_from_rows(list(board.get("phase_in") or []))
    out_shape = shape_from_rows(list(board.get("phase_out") or []))
    # The columns and the recomputed metrics win over the stored copies; the rest of the board is
    # served as-is. Set parity with `sync._columns_for`, which is what puts them in there.
    served = {key: value for key, value in board.items() if key not in DETAIL_OWN_KEYS}
    return _envelope(
        **served,
        id=row.id,
        slug=row.slug,
        path=system_path(row.slug),
        name=row.name,
        formation=row.formation,
        temperament_key=row.temperament_key,
        press_line_y=row.press_line_y,
        block_depth=row.block_depth,
        defensive_narrowing=row.defensive_narrowing,
        content_hash=row.content_hash,
        metrics_in=[metric.to_dict() for metric in metrics_of(in_shape)],
        metrics_out=[metric.to_dict() for metric in metrics_of(out_shape)],
        transform_note=(
            "The out-of-possession board is the same eleven players rescaled so their vertical span is exactly "
            f"{row.block_depth} m with the top at {row.press_line_y} m, and their width multiplied by "
            f"{row.defensive_narrowing}. Nothing is drawn twice."
        ),
        changes=[change.to_dict() for change in CHANGES.values()],
        data_origin=row.data_origin,
        is_demo_data=row.is_demo_data,
    )


@router.get("/{ident}/counterfactual")
def counterfactual(
    ident: str,
    request: Request,
    change: str = Query(min_length=1, max_length=40),
    phase: str = Query(default="in", pattern="^(in|out)$"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """ "What happens if…" — the stored board, one named change, and every measurement that moved."""
    limit(request, 60, 60, scope="tactics_counterfactual")
    _require_catalogue(db)
    row = _one(db, ident)
    selected = CHANGES.get(change)
    if selected is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "unknown_change", "message": f"change must be one of {sorted(CHANGES)}"},
        )
    board = dict(row.board or {})
    shape = shape_from_rows(list(board.get(f"phase_{phase}") or []))
    moved = apply_change(shape, selected)
    before = _metrics_map(shape)
    after = _metrics_map(moved)
    diff = [
        {
            "key": key,
            "label": before[key]["label"],
            "unit": before[key]["unit"],
            "formula": before[key]["formula"],
            "before": before[key]["value"],
            "after": after[key]["value"],
            "delta": round(after[key]["value"] - before[key]["value"], 2),
            "moved": abs(after[key]["value"] - before[key]["value"]) >= 0.05,
        }
        for key in METRIC_KEYS
    ]
    # A coordinate that would have left the pitch is clamped back onto it, and the page says so:
    # silently moving a player 3 m less than asked would make every number downstream a lie.
    clamped: list[dict[str, Any]] = []
    for slot, point, actual in zip(shape.slots, shape.points, moved.points, strict=True):
        asked = selected.desired(slot, point)
        if asked != actual:
            clamped.append(
                {
                    "role": slot.role,
                    "asked": {"x": round(asked.x, 2), "y": round(asked.y, 2)},
                    "placed": {"x": round(actual.x, 2), "y": round(actual.y, 2)},
                }
            )
    return _envelope(
        system=_row_brief(row),
        change=selected.to_dict(),
        phase=phase,
        board_before=shape.as_dict(),
        board_after=moved.as_dict(),
        metrics=diff,
        moved_count=sum(1 for item in diff if item["moved"]),
        clamped=clamped,
        recomputed=True,
        note="Computed from the stored coordinates on this request; the answer is never read out of a stored conclusion.",
    )


@router.get("/{ident}/feedback")
def system_feedback(ident: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """A tactical analysis whose every statement is anchored to a passage this project wrote.

    Nothing here is a model's opinion: each topic is a retrieval query, and a topic whose retrieval
    fails the corpus's answerability gates is returned in `ungrounded` rather than written as prose
    (spec §13, §29; `AI_POLICY.md` §3).
    """
    limit(request, 30, 60, scope="tactics_feedback")
    _require_catalogue(db)
    row = _one(db, ident)
    payload = {
        "slug": row.slug,
        "name": row.name,
        "formation": row.formation,
        "temperament_key": row.temperament_key,
        "board": dict(row.board or {}),
    }
    return build_feedback(db, payload).to_dict()


@router.get("/{ident}/fit")
def system_fit(
    ident: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """How this account's player compares with what the shape's roles demand — arithmetic, not praise."""
    limit(request, 30, 60, scope="tactics_fit")
    _require_catalogue(db)
    row = _one(db, ident)
    player = db.scalar(select(UserPlayer).where(UserPlayer.user_id == user.id).order_by(UserPlayer.created_at))
    if player is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "no_player", "message": "Create your player profile first"})
    demands = dict((row.board or {}).get("demands") or {})
    return _envelope(
        system={"slug": row.slug, "name": row.name, "formation": row.formation, "temperament_key": row.temperament_key, "path": system_path(row.slug)},
        player={
            "id": player.id,
            "name": player.name,
            "position": player.position,
            "archetype": player.archetype,
            "overall": player.overall,
            "attributes_from": "this account's progression ledger (XP events), not a provider or a model",
        },
        fit=fit_rows(demands, dict(player.attributes or {})),
        note=(
            "Attribute values come from your own progression ledger (XP → skill points → bounded attribute "
            "deltas), and the demands come from the roles this shape fields. No model decided either number."
        ),
    )
