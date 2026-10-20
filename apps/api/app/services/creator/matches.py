"""Match analyses: §36's fourth kind of content, anchored to a played fixture and copying none of it.

§36 lists six kinds of content a user can create. The fourth is a **Match Analysis** - an author's
reading of a played match, published beside the fixture rather than copied out of it.

The rule is the one the program, the tactical guide and the player analysis were built on: **a
publication stores an address, never a copy**. A match analysis stores its title, its own summary, a
visibility and the address of a row in `real_matches`. It stores no score, no shot count and no
sentence about the match. Every measurement a read shows is computed from the match row's own stored
score and `stats` on that read, so an analysis and the fixture it is about cannot disagree.

`match_hash` is the one thing stored *about* the match, and it is not a figure: it is the content
address the match carried when the analysis was written. A read compares it with the world's and
reports `moved` when they differ, while still measuring the match as it reads now. A match revised
by a later world sync is therefore still readable and says it moved.

The analysis is anchored, not merely related: the match is resolved **at publication**, so a reading
of a fixture the world does not hold is refused there rather than surfacing as a broken page. A
fixture that has not been played is refused too - it has no result to read. If the world later
retires the match, the analysis's own address answers absence (`no_such_match`).
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import CreatorMatchAnalysis, RealMatch, Team, User, utc_today
from app.services.creator.publishing import (
    VISIBILITIES,
    CreatorRefusal,
    _slug_of,
    _text,
    ensure_profile,
    visible_authors,
)
from app.services.world.plan import web_path

#: How many match analyses one creator may publish.
MAX_MATCH_ANALYSES_PER_CREATOR: Final = 60
MATCH_TITLE_MAX: Final = 160
MATCH_SLUG_MAX: Final = 80
MATCH_SUMMARY_MAX: Final = 600
MATCH_ANCHOR_MAX: Final = 200

#: The tier's own vocabulary for this noun, published by the rules door beside the others'.
FORMULAS: Final = {
    "match_analyses": "count of every match-analysis row this database holds",
    "moved": "whether the anchored match's content address now differs from the one stored when the analysis was written; every metric is still computed from the match's own columns on this read",
    "metrics": "the five measurements are computed from the anchored match's stored score and match stats on this request, and each metric prints its own formula",
}

METRIC_FORMULAS: Final = {
    "total_goals": "home_goals + away_goals, read from the match row",
    "goal_margin": "abs(home_goals - away_goals), read from the match row",
    "shot_accuracy": "(shots_on_target.home + shots_on_target.away) / (shots.home + shots.away); 0 when the row records no shot",
    "chance_conversion": "(home_goals + away_goals) / (shots.home + shots.away); 0 when the row records no shot",
    "possession_edge": "possession.home - possession.away, in percentage points",
}
METRIC_UNITS: Final = {
    "total_goals": "goals",
    "goal_margin": "goals",
    "shot_accuracy": "share of shots on target",
    "chance_conversion": "goals per shot",
    "possession_edge": "percentage points",
}

LIMITATION: Final = (
    "a match analysis stores a title, its own summary, a visibility and the address of a played fixture in the "
    "generated world - never a score, a shot count or a sentence about the match. Every measurement is computed "
    "from the match row's own stored score and stats when the analysis is read, so a revised fixture cannot leave "
    "the analysis quoting the old result; a match that has changed since the analysis was written says so through "
    "`moved`, a fixture the world no longer holds answers as absence, and a fixture that has not been played is "
    "refused because it has no result to read"
)


def _ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 2) if denominator else 0.0


def _pair(stats: dict[str, Any], key: str) -> tuple[float, float]:
    pair = dict(stats.get(key) or {})
    return float(pair.get("home") or 0), float(pair.get("away") or 0)


def _visibility(visibility: Any) -> str:
    word = str(visibility or "").strip().lower()
    if word not in VISIBILITIES:
        raise CreatorRefusal(
            "match_visibility",
            f"a match analysis is {' or '.join(repr(item) for item in VISIBILITIES)}; {word!r} would select nobody and the door cannot tell that from a mistake",
            sent=word,
            visibilities=list(VISIBILITIES),
        )
    return word


def _played(match: RealMatch) -> bool:
    return match.status == "completed" and match.home_goals is not None and match.away_goals is not None


def _match(session: Session, ident: Any) -> RealMatch:
    """The fixture an analysis is anchored to. An anchor that names nothing refuses at publication."""
    key = str(ident or "").strip()
    if not key:
        raise CreatorRefusal(
            "no_such_match",
            "a match analysis names the fixture it is about, and this one names none",
            match=key,
        )
    row = session.scalar(select(RealMatch).where(or_(RealMatch.slug == key, RealMatch.id == key)))
    if row is None:
        raise CreatorRefusal(
            "no_such_match",
            f"the generated world holds no fixture called {key!r}, so an analysis anchored to it would have nothing to read",
            match=key,
        )
    if not _played(row):
        raise CreatorRefusal(
            "match_not_played",
            f"the fixture {row.slug!r} is {row.status!r} and carries no score, so an analysis of it would have no result to read",
            match=row.slug,
            status=row.status,
        )
    return row


def _analysis(session: Session, ident: str) -> CreatorMatchAnalysis:
    row = session.get(CreatorMatchAnalysis, str(ident))
    if row is None:
        raise CreatorRefusal("no_such_match_analysis", f"no match analysis answers to {str(ident)!r}", analysis=str(ident))
    return row


def _owned(session: Session, analysis_id: str, actor_id: str) -> CreatorMatchAnalysis:
    row = _analysis(session, analysis_id)
    if row.author_id != actor_id:
        raise CreatorRefusal("no_such_match_analysis", f"no match analysis of yours answers to {str(analysis_id)!r}", analysis=str(analysis_id))
    return row


def _anchored(session: Session, row: CreatorMatchAnalysis) -> RealMatch | None:
    return session.scalar(select(RealMatch).where(RealMatch.slug == row.match_slug))


def _match_brief(session: Session, match: RealMatch | None, slug: str) -> dict[str, Any]:
    """The pointer as a reader follows it, never a copy of what waits at the other end."""
    if match is None:
        return {"slug": slug, "home": None, "away": None, "kickoff_at": None, "status": None, "path": None}
    home = session.get(Team, match.home_team_id)
    away = session.get(Team, match.away_team_id)
    return {
        "slug": match.slug,
        "home": home.name if home else None,
        "away": away.name if away else None,
        "kickoff_at": match.kickoff_at.isoformat(),
        "status": match.status,
        "path": web_path("match", match.slug),
    }


def _measures(match: RealMatch) -> dict[str, Any]:
    """The match measured now from its own stored score and stats, each metric beside its formula."""
    home_goals = int(match.home_goals or 0)
    away_goals = int(match.away_goals or 0)
    stats = dict(match.stats or {})
    shots_home, shots_away = _pair(stats, "shots")
    on_home, on_away = _pair(stats, "shots_on_target")
    possession_home, possession_away = _pair(stats, "possession")
    shots = shots_home + shots_away
    values = {
        "total_goals": home_goals + away_goals,
        "goal_margin": abs(home_goals - away_goals),
        "shot_accuracy": _ratio(on_home + on_away, shots),
        "chance_conversion": _ratio(home_goals + away_goals, shots),
        "possession_edge": round(possession_home - possession_away, 2),
    }
    return {
        key: {"value": value, "unit": METRIC_UNITS[key], "formula": METRIC_FORMULAS[key]}
        for key, value in values.items()
    }


def match_counts(session: Session, *, ready: bool) -> dict[str, int]:
    """The rulebook's count of this tier's match-analysis table."""
    if not ready:
        return {"match_analyses": 0}
    return {
        "match_analyses": int(session.scalar(select(func.count()).select_from(CreatorMatchAnalysis)) or 0),
    }


def publish_match_analysis(
    session: Session,
    actor_id: str,
    *,
    match: Any,
    title: Any,
    summary: Any = "",
    visibility: Any = "public",
) -> dict[str, Any]:
    """Publish a reading of a fixture: the anchor, a title, a visibility and the author's words."""
    ensure_profile(session, actor_id)
    anchored = _match(session, match)
    wanted_title = _text(title, MATCH_TITLE_MAX, "match_title", "match analysis title", required=True)
    wanted_visibility = _visibility(visibility)
    wanted_summary = _text(summary, MATCH_SUMMARY_MAX, "match_summary", "match analysis summary", required=False)

    mine = int(
        session.scalar(
            select(func.count()).select_from(CreatorMatchAnalysis).where(CreatorMatchAnalysis.author_id == actor_id)
        )
        or 0
    )
    if mine >= MAX_MATCH_ANALYSES_PER_CREATOR:
        raise CreatorRefusal(
            "match_limit",
            f"a creator may publish {MAX_MATCH_ANALYSES_PER_CREATOR} match analyses and this account has {mine}",
            analyses=mine,
            max=MAX_MATCH_ANALYSES_PER_CREATOR,
        )

    slug = _slug_of(wanted_title)[:MATCH_SLUG_MAX]
    taken = session.scalar(
        select(CreatorMatchAnalysis).where(
            CreatorMatchAnalysis.author_id == actor_id, CreatorMatchAnalysis.slug == slug
        )
    )
    if taken is not None:
        raise CreatorRefusal(
            "slug_taken",
            f"this account already publishes a match analysis called {slug!r}, and a reader cannot tell two analyses apart by a name",
            slug=slug,
        )

    row = CreatorMatchAnalysis(
        id=new_public_id("cma"),
        author_id=actor_id,
        slug=slug,
        title=wanted_title,
        summary=wanted_summary,
        visibility=wanted_visibility,
        match_slug=anchored.slug,
        match_hash=anchored.content_hash,
        published_on=utc_today(),
        data_origin="user",
        is_demo_data=False,
    )
    session.add(row)
    session.commit()
    return read_match_analysis(session, row.id, actor_id)


def _view(session: Session, row: CreatorMatchAnalysis) -> dict[str, Any]:
    match = _anchored(session, row)
    if match is None:
        raise CreatorRefusal(
            "no_such_match",
            f"the generated world no longer holds {row.match_slug!r}, so this analysis has nothing to read",
            analysis=row.id,
            match=row.match_slug,
        )
    if not _played(match):
        raise CreatorRefusal(
            "match_not_played",
            f"the fixture {match.slug!r} is {match.status!r} and carries no score, so this analysis has no result to read",
            analysis=row.id,
            match=match.slug,
            status=match.status,
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
        "match": _match_brief(session, match, row.match_slug),
        "moved": match.content_hash != row.match_hash,
        "metrics": _measures(match),
        "formulas": dict(FORMULAS),
        "rule": LIMITATION,
    }


def _reachable(session: Session, analysis_id: str, viewer_id: str) -> CreatorMatchAnalysis:
    """One analysis, if this reader may reach it. An analysis they may not reach is answered as absence."""
    row = _analysis(session, analysis_id)
    if row.visibility == "followers" and row.author_id not in set(visible_authors(session, viewer_id)):
        raise CreatorRefusal("no_such_match_analysis", f"no match analysis answers to {str(analysis_id)!r}", analysis=str(analysis_id))
    return row


def read_match_analysis(session: Session, analysis_id: str, viewer_id: str) -> dict[str, Any]:
    """One match analysis, with its fixture measured on this read."""
    row = _reachable(session, analysis_id, viewer_id)
    return _view(session, row)


def list_match_analyses(session: Session, viewer_id: str, *, creator: str | None = None, limit: int = 20) -> dict[str, Any]:
    """The shelf of match analyses as far as this reader may reach, with each fixture named live."""
    following = visible_authors(session, viewer_id)[1:]
    own = creator is not None and str(creator) == viewer_id
    allowed = list(VISIBILITIES) if own else (["public", "followers"] if (creator is not None and str(creator) in following) else ["public"])
    statement = select(CreatorMatchAnalysis).where(CreatorMatchAnalysis.visibility.in_(allowed))
    if creator is not None:
        statement = statement.where(CreatorMatchAnalysis.author_id == str(creator))
    total = int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = list(
        session.scalars(
            statement.order_by(CreatorMatchAnalysis.published_on.desc(), CreatorMatchAnalysis.id.desc()).limit(
                max(1, min(int(limit), 100))
            )
        ).all()
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        match = _anchored(session, row)
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
                "match": _match_brief(session, match, row.match_slug),
                "moved": match is None or match.content_hash != row.match_hash,
            }
        )
    return {
        "items": items,
        "total": total,
        "limit": int(MAX_MATCH_ANALYSES_PER_CREATOR),
        "creator": str(creator) if creator is not None else None,
        "formulas": dict(FORMULAS),
        "rule": LIMITATION,
    }


def erase_match_analysis(session: Session, actor_id: str, analysis_id: str) -> dict[str, Any]:
    """Erase your own match analysis. The fixture it was about is untouched."""
    row = _owned(session, analysis_id, actor_id)
    erased = row.id
    session.delete(row)
    session.commit()
    return {"status": "erased", "analysis": erased}


def rules(session: Session, *, ready: bool) -> dict[str, Any]:
    """This noun's own vocabulary, published beside the guide's, the program's and the player analysis's."""
    return {
        "match_caps": {
            "match_analysis_max": MAX_MATCH_ANALYSES_PER_CREATOR,
            "match_title_max": MATCH_TITLE_MAX,
            "match_slug_max": MATCH_SLUG_MAX,
            "match_summary_max": MATCH_SUMMARY_MAX,
            "match_anchor_max": MATCH_ANCHOR_MAX,
        },
        "match_formulas": dict(FORMULAS),
        "match_counts": match_counts(session, ready=ready),
        "match_rule": LIMITATION,
    }
