"""The shelf the Deep Dossier writes back to.

`deep_dossier.py` is deliberately stateless: the same focus, depth and seed always rebuild the
same chapter from the same committed corpus, and nothing survives the request. That is the right
contract for a *measurement* — but it means the world never grows. A reader who commissions a
chapter watches it disappear when the tab closes.

This module is the other half. A reader may bind one generated chapter into `dossier_volumes`;
from then on it has a stable slug, a shelf entry, a view counter and a permalink. The signature
`sha256(focus|depth|seed|locale)` is unique, so pressing "bind" twice returns the volume that
already exists instead of paying the gateway twice, and two readers who ask for the same chapter
share one shelf entry rather than duplicating the library.

The slug is readable (`european-cup-finals-1a2b3c4d`) because a permalink a reader can type is
worth more than an opaque id; the signature suffix keeps it unique without a counter.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import DossierVolume
from app.services.world.deep_dossier import DEPTH_TARGETS, compute_deep_dossier

MAX_FOCUS_CHARS = 160
MAX_SLUG_WORDS = 6


def normalise_focus(focus: str) -> str:
    """Collapse whitespace and cap the focus at the column's width."""
    return re.sub(r"\s+", " ", focus).strip()[:MAX_FOCUS_CHARS]


def volume_signature(focus: str, depth: str, seed: int, locale: str) -> str:
    """The content address of a generated chapter — the same four inputs, the same digest."""
    material = f"{normalise_focus(focus).casefold()}|{depth}|{seed}|{locale}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def volume_slug(focus: str, signature: str) -> str:
    """A readable, typeable slug: the first words of the focus plus eight hex characters."""
    words = re.findall(r"[a-z0-9]+", normalise_focus(focus).casefold())[:MAX_SLUG_WORDS]
    stem = "-".join(words) or "volume"
    return f"{stem[:56].strip('-')}-{signature[:8]}"


def _serialise(volume: DossierVolume, *, created: bool | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "slug": volume.slug,
        "focus": volume.focus,
        "depth": volume.depth,
        "seed": volume.seed,
        "locale": volume.locale,
        "chapter": volume.chapter,
        "source_count": volume.source_count,
        "estimated_input_tokens": volume.estimated_input_tokens,
        "input_tokens": volume.input_tokens,
        "cached_input_tokens": volume.cached_input_tokens,
        "verified": volume.verified,
        "view_count": volume.view_count,
        "created_at": volume.created_at.isoformat() if volume.created_at else None,
        "path": f"/world/dossier-library/{volume.slug}",
    }
    if created is not None:
        payload["created"] = created
    return payload


def _shelf_entry(volume: DossierVolume) -> dict[str, Any]:
    """The list view: enough to choose a volume, never the whole chapter."""
    return {
        "slug": volume.slug,
        "focus": volume.focus,
        "depth": volume.depth,
        "locale": volume.locale,
        "source_count": volume.source_count,
        "verified": volume.verified,
        "view_count": volume.view_count,
        "created_at": volume.created_at.isoformat() if volume.created_at else None,
        "path": f"/world/dossier-library/{volume.slug}",
        "excerpt": (volume.chapter or "").strip().split("\n\n")[0][:240],
    }


def find_volume(session: Session, slug: str) -> DossierVolume | None:
    return session.scalar(select(DossierVolume).where(DossierVolume.slug == slug))


def bind_volume(
    session: Session,
    *,
    focus: str,
    depth: str = "deep",
    seed: int = 0,
    locale: str = "en",
    provider: Any | None = None,
) -> dict[str, Any] | None:
    """Generate once, then keep forever. Returns None when the gateway produced no chapter.

    The dedupe check happens before the model call, so the second reader of the same chapter
    costs nothing. The unique constraint is still the authority: two simultaneous binds of the
    same signature can both miss the check, and the loser of the insert race returns the row the
    winner wrote rather than a 409.
    """
    clean = normalise_focus(focus)
    if not clean:
        return None
    if depth not in DEPTH_TARGETS:
        raise ValueError(f"unknown depth {depth!r}")
    signature = volume_signature(clean, depth, seed, locale)
    existing = session.scalar(select(DossierVolume).where(DossierVolume.signature == signature))
    if existing is not None:
        return _serialise(existing, created=False)

    result = compute_deep_dossier(clean, depth=depth, seed=seed, locale=locale, provider=provider)
    if not result.get("available") or not result.get("chapter"):
        return None

    volume = DossierVolume(
        slug=volume_slug(clean, signature),
        signature=signature,
        focus=clean,
        depth=depth,
        seed=seed,
        locale=locale,
        chapter=result["chapter"],
        source_count=int(result.get("source_count") or 0),
        estimated_input_tokens=int(result.get("estimated_input_tokens") or 0),
        input_tokens=int(result.get("input_tokens") or 0),
        cached_input_tokens=int(result.get("cached_input_tokens") or 0),
        verified=bool(result.get("verified")),
    )
    session.add(volume)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        winner = session.scalar(select(DossierVolume).where(DossierVolume.signature == signature))
        return _serialise(winner, created=False) if winner is not None else None
    session.refresh(volume)
    return _serialise(volume, created=True)


def list_volumes(session: Session, *, limit: int = 24, offset: int = 0, depth: str | None = None) -> dict[str, Any]:
    """Newest first; the count is the shelf's honest size, not the page's."""
    where = [DossierVolume.depth == depth] if depth else []
    total = session.scalar(select(func.count()).select_from(DossierVolume).where(*where)) or 0
    epic_total = session.scalar(
        select(func.count()).select_from(DossierVolume).where(DossierVolume.depth == "epic")
    ) or 0
    sources_total = session.scalar(select(func.coalesce(func.sum(DossierVolume.source_count), 0))) or 0
    rows = list(
        session.scalars(
            select(DossierVolume)
            .where(*where)
            .order_by(DossierVolume.created_at.desc(), DossierVolume.slug)
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return {
        "available": True,
        "total": total,
        "epic_total": int(epic_total),
        "sources_total": int(sources_total),
        "limit": limit,
        "offset": offset,
        "volumes": [_shelf_entry(row) for row in rows],
    }


def read_volume(session: Session, slug: str, *, count_view: bool = True) -> dict[str, Any] | None:
    """One volume by slug. A read through the public door counts a view; a test need not."""
    volume = find_volume(session, slug)
    if volume is None:
        return None
    if count_view:
        volume.view_count = (volume.view_count or 0) + 1
        session.commit()
        session.refresh(volume)
    return _serialise(volume)
