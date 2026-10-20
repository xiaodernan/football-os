"""Tactical guides: §36's second kind of content, anchored to a stored system and copying none of it.

§36 lists six kinds of content a user can create. The first, a Training Program, landed as its own
object; the second is a **Tactical Guide** - an author's reading of a shape, published beside the
shape rather than copied out of it.

The rule this module is built on is the one §35 put under citations, applied to a different noun:
**a publication stores an address, never a copy**. A tactical guide stores its title, its own
summary, a visibility and the address of a row in `tactical_systems`. It stores no width, no depth,
no coordinate and no sentence about the shape. Every measurement a read shows is computed from the
system's own stored dots on that read, by `services/tactics/analysis.py` - the same function the
`/tactics` door answers with - so a guide and the system it is about cannot disagree.

`system_hash` is the one thing stored *about* the system, and it is not a figure: it is the content
address the system carried when the guide was written. A read compares it with the catalogue's and
reports `moved` when they differ, while still measuring the system as it reads now. That is exactly
the witness `guide_citations.cited_text_hash` is: a pointer plus what it pointed at, so a later read
can say *this is not the revision the author wrote about* without ever repeating the old numbers.

The guide is anchored, not merely related: the system is resolved **at publication**, so a guide
naming a system the catalogue does not hold is refused there rather than surfacing as a broken page.
If the catalogue later retires the system, the guide's own address answers absence (`no_such_system`)
- the honest answer for a reading whose subject is gone.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import CreatorTacticalGuide, TacticalSystem, User, utc_today
from app.services.creator.publishing import (
    VISIBILITIES,
    CreatorRefusal,
    _slug_of,
    _text,
    ensure_profile,
    visible_authors,
)
from app.services.tactics.analysis import metrics_for_rows
from app.services.tactics.plan import system_path

#: How many tactical guides one creator may publish.
MAX_TACTICAL_GUIDES_PER_CREATOR: Final = 60
TACTICAL_TITLE_MAX: Final = 160
TACTICAL_SLUG_MAX: Final = 80
TACTICAL_SUMMARY_MAX: Final = 600
SYSTEM_SLUG_MAX: Final = 160

#: The tier's own vocabulary for this noun, published by the rules door beside the guide's and the program's.
FORMULAS: Final = {
    "tactical_guides": "count of every tactical-guide row this database holds",
    "moved": "whether the anchored system's content address now differs from the one stored when the guide was written; every metric is still computed from the system's dots on this read",
    "metrics": "the two phases' measurements are computed from the anchored system's stored dots on this request by `services/tactics/analysis.py`, and each metric prints its own formula",
}

LIMITATION: Final = (
    "a tactical guide stores a title, its own summary, a visibility and the address of a system in the tactical "
    "catalogue - never a metric, a coordinate or a sentence about the shape. Every measurement is computed from the "
    "system's own dots when the guide is read, so a revised catalogue cannot leave the guide quoting the old geometry; "
    "a system that has changed since the guide was written says so through `moved`, and a system the catalogue no "
    "longer holds answers as absence"
)


def _visibility(visibility: Any) -> str:
    word = str(visibility or "").strip().lower()
    if word not in VISIBILITIES:
        raise CreatorRefusal(
            "tactical_visibility",
            f"a tactical guide is {' or '.join(repr(item) for item in VISIBILITIES)}; {word!r} would select nobody and the door cannot tell that from a mistake",
            sent=word,
            visibilities=list(VISIBILITIES),
        )
    return word


def _system(session: Session, ident: Any) -> TacticalSystem:
    """The catalogue system a guide is anchored to. An anchor that names nothing refuses at publication."""
    key = str(ident or "").strip()
    if not key:
        raise CreatorRefusal(
            "no_such_system",
            "a tactical guide names the system it is about, and this one names none",
            system=key,
        )
    row = session.scalar(select(TacticalSystem).where(or_(TacticalSystem.slug == key, TacticalSystem.id == key)))
    if row is None:
        raise CreatorRefusal(
            "no_such_system",
            f"the tactical catalogue holds no system called {key!r}, so a guide anchored to it would have nothing to read",
            system=key,
        )
    return row


def _guide(session: Session, ident: str) -> CreatorTacticalGuide:
    row = session.get(CreatorTacticalGuide, str(ident))
    if row is None:
        raise CreatorRefusal("no_such_tactical", f"no tactical guide answers to {str(ident)!r}", guide=str(ident))
    return row


def _owned(session: Session, guide_id: str, actor_id: str) -> CreatorTacticalGuide:
    row = _guide(session, guide_id)
    if row.author_id != actor_id:
        # Somebody else's guide is answered as absence, exactly as this tier answers a guide that is not yours.
        raise CreatorRefusal("no_such_tactical", f"no tactical guide of yours answers to {str(guide_id)!r}", guide=str(guide_id))
    return row


def _anchored(session: Session, row: CreatorTacticalGuide) -> TacticalSystem | None:
    return session.scalar(select(TacticalSystem).where(TacticalSystem.slug == row.system_slug))


def _system_brief(system: TacticalSystem | None, slug: str) -> dict[str, Any]:
    """The pointer as a reader follows it, never a copy of what waits at the other end."""
    if system is None:
        return {"slug": slug, "name": None, "formation": None, "path": None}
    return {"slug": system.slug, "name": system.name, "formation": system.formation, "path": system_path(system.slug)}


def _measures(system: TacticalSystem) -> dict[str, Any]:
    """The system measured now, both phases, by the tactics tier's own function."""
    board = dict(system.board or {})
    return {
        "phase_in": metrics_for_rows(list(board.get("phase_in") or [])),
        "phase_out": metrics_for_rows(list(board.get("phase_out") or [])),
    }


def tactical_counts(session: Session, *, ready: bool) -> dict[str, int]:
    """The rulebook's count of this tier's tactical-guide table."""
    if not ready:
        return {"tactical_guides": 0}
    return {
        "tactical_guides": int(session.scalar(select(func.count()).select_from(CreatorTacticalGuide)) or 0),
    }


def publish_tactical_guide(
    session: Session,
    actor_id: str,
    *,
    system: Any,
    title: Any,
    summary: Any = "",
    visibility: Any = "public",
) -> dict[str, Any]:
    """Publish a reading of a shape: the anchor, a title, a visibility and the author's words."""
    ensure_profile(session, actor_id)
    anchored = _system(session, system)
    wanted_title = _text(title, TACTICAL_TITLE_MAX, "tactical_title", "tactical guide title", required=True)
    wanted_visibility = _visibility(visibility)
    wanted_summary = _text(summary, TACTICAL_SUMMARY_MAX, "tactical_summary", "tactical guide summary", required=False)

    mine = int(
        session.scalar(
            select(func.count()).select_from(CreatorTacticalGuide).where(CreatorTacticalGuide.author_id == actor_id)
        )
        or 0
    )
    if mine >= MAX_TACTICAL_GUIDES_PER_CREATOR:
        raise CreatorRefusal(
            "tactical_limit",
            f"a creator may publish {MAX_TACTICAL_GUIDES_PER_CREATOR} tactical guides and this account has {mine}",
            guides=mine,
            max=MAX_TACTICAL_GUIDES_PER_CREATOR,
        )

    slug = _slug_of(wanted_title)[:TACTICAL_SLUG_MAX]
    taken = session.scalar(
        select(CreatorTacticalGuide).where(
            CreatorTacticalGuide.author_id == actor_id, CreatorTacticalGuide.slug == slug
        )
    )
    if taken is not None:
        raise CreatorRefusal(
            "slug_taken",
            f"this account already publishes a tactical guide called {slug!r}, and a reader cannot tell two guides apart by a name",
            slug=slug,
        )

    row = CreatorTacticalGuide(
        id=new_public_id("ctg"),
        author_id=actor_id,
        slug=slug,
        title=wanted_title,
        summary=wanted_summary,
        visibility=wanted_visibility,
        system_slug=anchored.slug,
        system_hash=anchored.content_hash,
        published_on=utc_today(),
        data_origin="user",
        is_demo_data=False,
    )
    session.add(row)
    session.commit()
    return read_tactical_guide(session, row.id, actor_id)


def _view(session: Session, row: CreatorTacticalGuide) -> dict[str, Any]:
    system = _anchored(session, row)
    if system is None:
        raise CreatorRefusal(
            "no_such_system",
            f"the tactical catalogue no longer holds {row.system_slug!r}, so this guide has nothing to read",
            guide=row.id,
            system=row.system_slug,
        )
    author = session.get(User, row.author_id)
    return {
        "id": row.id,
        "slug": row.slug,
        "title": row.title,
        "summary": row.summary,
        "visibility": row.visibility,
        "published_on": row.published_on,
        "data_origin": row.data_origin,
        "is_demo_data": row.is_demo_data,
        "author": {"id": row.author_id, "display_name": author.display_name if author else ""},
        "system": _system_brief(system, row.system_slug),
        "moved": system.content_hash != row.system_hash,
        "metrics": _measures(system),
        "formulas": dict(FORMULAS),
        "rule": LIMITATION,
    }


def _reachable(session: Session, guide_id: str, viewer_id: str) -> CreatorTacticalGuide:
    """One guide, if this reader may reach it. A guide they may not reach is answered as absence."""
    row = _guide(session, guide_id)
    if row.visibility == "followers" and row.author_id not in set(visible_authors(session, viewer_id)):
        raise CreatorRefusal("no_such_tactical", f"no tactical guide answers to {str(guide_id)!r}", guide=str(guide_id))
    return row


def read_tactical_guide(session: Session, guide_id: str, viewer_id: str) -> dict[str, Any]:
    """One tactical guide, with its system measured on this read."""
    row = _reachable(session, guide_id, viewer_id)
    return _view(session, row)


def list_tactical_guides(session: Session, viewer_id: str, *, creator: str | None = None, limit: int = 20) -> dict[str, Any]:
    """The shelf of tactical guides as far as this reader may reach, with each anchor named live."""
    following = visible_authors(session, viewer_id)[1:]
    own = creator is not None and str(creator) == viewer_id
    allowed = list(VISIBILITIES) if own else (["public", "followers"] if (creator is not None and str(creator) in following) else ["public"])
    statement = select(CreatorTacticalGuide).where(CreatorTacticalGuide.visibility.in_(allowed))
    if creator is not None:
        statement = statement.where(CreatorTacticalGuide.author_id == str(creator))
    total = int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = list(
        session.scalars(
            statement.order_by(CreatorTacticalGuide.published_on.desc(), CreatorTacticalGuide.id.desc()).limit(
                max(1, min(int(limit), 100))
            )
        ).all()
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        system = _anchored(session, row)
        author = session.get(User, row.author_id)
        items.append(
            {
                "id": row.id,
                "slug": row.slug,
                "title": row.title,
                "summary": row.summary,
                "visibility": row.visibility,
                "published_on": row.published_on,
                "author": {"id": row.author_id, "display_name": author.display_name if author else ""},
                "system": _system_brief(system, row.system_slug),
                "moved": system is None or system.content_hash != row.system_hash,
            }
        )
    return {
        "items": items,
        "total": total,
        "limit": int(MAX_TACTICAL_GUIDES_PER_CREATOR),
        "creator": str(creator) if creator is not None else None,
        "formulas": dict(FORMULAS),
        "rule": LIMITATION,
    }


def erase_tactical_guide(session: Session, actor_id: str, guide_id: str) -> dict[str, Any]:
    """Erase your own tactical guide. The system it was about is untouched."""
    row = _owned(session, guide_id, actor_id)
    erased = row.id
    session.delete(row)
    session.commit()
    return {"status": "erased", "guide": erased}


def rules(session: Session, *, ready: bool) -> dict[str, Any]:
    """This noun's own vocabulary, published beside the guide's and the program's."""
    return {
        "tactical_caps": {
            "tactical_guide_max": MAX_TACTICAL_GUIDES_PER_CREATOR,
            "tactical_title_max": TACTICAL_TITLE_MAX,
            "tactical_slug_max": TACTICAL_SLUG_MAX,
            "tactical_summary_max": TACTICAL_SUMMARY_MAX,
            "system_slug_max": SYSTEM_SLUG_MAX,
        },
        "tactical_formulas": dict(FORMULAS),
        "tactical_counts": tactical_counts(session, ready=ready),
        "tactical_rule": LIMITATION,
    }
