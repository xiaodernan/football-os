"""Player analyses: §36's third kind of content, anchored to a stored player and copying none of him.

§36 lists six kinds of content a user can create. The first, a Training Program, landed as its own
object; the second, a Tactical Guide, is an address into the tactical catalogue. The third is a
**Player Analysis** - an author's reading of a footballer, published beside the player rather than
copied out of him.

The rule is the tier's own, applied to a person: **a publication stores an address, never a copy**.
An analysis stores its title, its own summary, a visibility and the address of a row in
`real_players`. It stores no rate, no total and no sentence about the player. Every measurement a
read shows is computed from the player's own stored columns on that read, so the analysis and the
world door cannot disagree about the same footballer.

`player_hash` is the one thing stored *about* the player, and it is not a figure: it is the content
address the player carried when the analysis was written. A read compares it with the world's and
reports `moved` when they differ, while still measuring the player as he reads now. That is the
witness `guide_citations.cited_text_hash` is: a pointer plus what it pointed at, so a later read can
say *this is not the revision the author wrote about* without ever repeating the old numbers.

The analysis is anchored, not merely related: the player is resolved **at publication**, so an
analysis naming a player the world does not hold is refused there rather than surfacing as a broken
page. If the world later retires the player, the analysis's own address answers absence
(`no_such_analysed_player`) - the honest answer for a reading whose subject is gone.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import CreatorPlayerAnalysis, RealPlayer, Team, User, utc_today
from app.services.creator.publishing import (
    VISIBILITIES,
    CreatorRefusal,
    _slug_of,
    _text,
    ensure_profile,
    visible_authors,
)
from app.services.world.plan import web_path

#: How many player analyses one creator may publish.
MAX_PLAYER_ANALYSES_PER_CREATOR: Final = 80
ANALYSIS_TITLE_MAX: Final = 160
ANALYSIS_SLUG_MAX: Final = 80
ANALYSIS_SUMMARY_MAX: Final = 600
PLAYER_SLUG_MAX: Final = 160

#: The tier's own vocabulary for this noun, published by the rules door beside the guide's and the program's.
FORMULAS: Final = {
    "player_analyses": "count of every player-analysis row this database holds",
    "moved": "whether the anchored player's content address now differs from the one stored when the analysis was written; every metric is still computed from the player's stored columns on this read",
    "metrics": "the five measurements are computed from the anchored player's own stored columns on this request, and each metric prints its own formula",
}

METRIC_FORMULAS: Final = {
    "minutes_per_appearance": "minutes / appearances; 0 when appearances is 0",
    "goal_contributions_per_90": "(goals + assists) * 90 / minutes; 0 when minutes is 0",
    "scoring_rate": "goals / appearances; 0 when appearances is 0",
    "availability": "minutes / (90 * appearances); 0 when appearances is 0",
    "cards_per_90": "(yellow_cards + red_cards) * 90 / minutes; 0 when minutes is 0",
}

METRIC_UNITS: Final = {
    "minutes_per_appearance": "minutes",
    "goal_contributions_per_90": "per 90 minutes",
    "scoring_rate": "goals per appearance",
    "availability": "share of 90 minutes",
    "cards_per_90": "cards per 90 minutes",
}

LIMITATION: Final = (
    "a player analysis stores a title, its own summary, a visibility and the address of a player in the generated "
    "world - never a total, a rate or a sentence about the player. Every measurement is computed from the player's "
    "own stored columns when the analysis is read, so a refreshed world cannot leave the analysis quoting last "
    "season's output; a player that has changed since the analysis was written says so through `moved`, and a player "
    "the world no longer holds answers as absence"
)


def _ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 2) if denominator else 0.0


def _visibility(visibility: Any) -> str:
    word = str(visibility or "").strip().lower()
    if word not in VISIBILITIES:
        raise CreatorRefusal(
            "analysis_visibility",
            f"a player analysis is {' or '.join(repr(item) for item in VISIBILITIES)}; {word!r} would select nobody and the door cannot tell that from a mistake",
            sent=word,
            visibilities=list(VISIBILITIES),
        )
    return word


def _player(session: Session, ident: Any) -> RealPlayer:
    """The world player an analysis is anchored to. An anchor that names nothing refuses at publication."""
    key = str(ident or "").strip()
    if not key:
        raise CreatorRefusal(
            "no_such_analysed_player",
            "a player analysis names the player it is about, and this one names none",
            player=key,
        )
    row = session.scalar(select(RealPlayer).where(or_(RealPlayer.slug == key, RealPlayer.id == key)))
    if row is None:
        raise CreatorRefusal(
            "no_such_analysed_player",
            f"the generated world holds no player called {key!r}, so an analysis anchored to them would have nothing to read",
            player=key,
        )
    return row


def _analysis(session: Session, ident: str) -> CreatorPlayerAnalysis:
    row = session.get(CreatorPlayerAnalysis, str(ident))
    if row is None:
        raise CreatorRefusal("no_such_analysis", f"no player analysis answers to {str(ident)!r}", analysis=str(ident))
    return row


def _owned(session: Session, analysis_id: str, actor_id: str) -> CreatorPlayerAnalysis:
    row = _analysis(session, analysis_id)
    if row.author_id != actor_id:
        # Somebody else's analysis is answered as absence, exactly as this tier answers a guide that is not yours.
        raise CreatorRefusal("no_such_analysis", f"no player analysis of yours answers to {str(analysis_id)!r}", analysis=str(analysis_id))
    return row


def _anchored(session: Session, row: CreatorPlayerAnalysis) -> RealPlayer | None:
    return session.scalar(select(RealPlayer).where(RealPlayer.slug == row.player_slug))


def _player_brief(session: Session, player: RealPlayer | None, slug: str) -> dict[str, Any]:
    """The pointer as a reader follows it, never a copy of what waits at the other end."""
    if player is None:
        return {"slug": slug, "name": None, "position": None, "overall": None, "team": None, "path": None}
    team = session.get(Team, player.team_id) if player.team_id else None
    return {
        "slug": player.slug,
        "name": player.name,
        "position": player.position,
        "overall": player.overall,
        "team": team.name if team else None,
        "path": web_path("player", player.slug),
    }


def _measures(player: RealPlayer) -> dict[str, Any]:
    """The player measured now from his own stored columns, each metric beside its formula."""
    appearances = int(player.appearances or 0)
    minutes = int(player.minutes or 0)
    goals = int(player.goals or 0)
    assists = int(player.assists or 0)
    cards = int(player.yellow_cards or 0) + int(player.red_cards or 0)
    values = {
        "minutes_per_appearance": _ratio(minutes, appearances),
        "goal_contributions_per_90": _ratio((goals + assists) * 90, minutes),
        "scoring_rate": _ratio(goals, appearances),
        "availability": _ratio(minutes, 90 * appearances),
        "cards_per_90": _ratio(cards * 90, minutes),
    }
    return {
        key: {"value": value, "unit": METRIC_UNITS[key], "formula": METRIC_FORMULAS[key]}
        for key, value in values.items()
    }


def analysis_counts(session: Session, *, ready: bool) -> dict[str, int]:
    """The rulebook's count of this tier's player-analysis table."""
    if not ready:
        return {"player_analyses": 0}
    return {
        "player_analyses": int(session.scalar(select(func.count()).select_from(CreatorPlayerAnalysis)) or 0),
    }


def publish_player_analysis(
    session: Session,
    actor_id: str,
    *,
    player: Any,
    title: Any,
    summary: Any = "",
    visibility: Any = "public",
) -> dict[str, Any]:
    """Publish a reading of a footballer: the anchor, a title, a visibility and the author's words."""
    ensure_profile(session, actor_id)
    anchored = _player(session, player)
    wanted_title = _text(title, ANALYSIS_TITLE_MAX, "analysis_title", "player analysis title", required=True)
    wanted_visibility = _visibility(visibility)
    wanted_summary = _text(summary, ANALYSIS_SUMMARY_MAX, "analysis_summary", "player analysis summary", required=False)

    mine = int(
        session.scalar(
            select(func.count()).select_from(CreatorPlayerAnalysis).where(CreatorPlayerAnalysis.author_id == actor_id)
        )
        or 0
    )
    if mine >= MAX_PLAYER_ANALYSES_PER_CREATOR:
        raise CreatorRefusal(
            "analysis_limit",
            f"a creator may publish {MAX_PLAYER_ANALYSES_PER_CREATOR} player analyses and this account has {mine}",
            analyses=mine,
            max=MAX_PLAYER_ANALYSES_PER_CREATOR,
        )

    slug = _slug_of(wanted_title)[:ANALYSIS_SLUG_MAX]
    taken = session.scalar(
        select(CreatorPlayerAnalysis).where(
            CreatorPlayerAnalysis.author_id == actor_id, CreatorPlayerAnalysis.slug == slug
        )
    )
    if taken is not None:
        raise CreatorRefusal(
            "slug_taken",
            f"this account already publishes a player analysis called {slug!r}, and a reader cannot tell two analyses apart by a name",
            slug=slug,
        )

    row = CreatorPlayerAnalysis(
        id=new_public_id("cpa"),
        author_id=actor_id,
        slug=slug,
        title=wanted_title,
        summary=wanted_summary,
        visibility=wanted_visibility,
        player_slug=anchored.slug,
        player_hash=anchored.content_hash,
        published_on=utc_today(),
        data_origin="user",
        is_demo_data=False,
    )
    session.add(row)
    session.commit()
    return read_player_analysis(session, row.id, actor_id)


def _view(session: Session, row: CreatorPlayerAnalysis) -> dict[str, Any]:
    player = _anchored(session, row)
    if player is None:
        raise CreatorRefusal(
            "no_such_analysed_player",
            f"the generated world no longer holds {row.player_slug!r}, so this analysis has nothing to read",
            analysis=row.id,
            player=row.player_slug,
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
        "player": _player_brief(session, player, row.player_slug),
        "moved": player.content_hash != row.player_hash,
        "metrics": _measures(player),
        "formulas": dict(FORMULAS),
        "rule": LIMITATION,
    }


def _reachable(session: Session, analysis_id: str, viewer_id: str) -> CreatorPlayerAnalysis:
    """One analysis, if this reader may reach it. An analysis they may not reach is answered as absence."""
    row = _analysis(session, analysis_id)
    if row.visibility == "followers" and row.author_id not in set(visible_authors(session, viewer_id)):
        raise CreatorRefusal("no_such_analysis", f"no player analysis answers to {str(analysis_id)!r}", analysis=str(analysis_id))
    return row


def read_player_analysis(session: Session, analysis_id: str, viewer_id: str) -> dict[str, Any]:
    """One player analysis, with its player measured on this read."""
    row = _reachable(session, analysis_id, viewer_id)
    return _view(session, row)


def list_player_analyses(session: Session, viewer_id: str, *, creator: str | None = None, limit: int = 20) -> dict[str, Any]:
    """The shelf of player analyses as far as this reader may reach, with each player named live."""
    following = visible_authors(session, viewer_id)[1:]
    own = creator is not None and str(creator) == viewer_id
    allowed = list(VISIBILITIES) if own else (["public", "followers"] if (creator is not None and str(creator) in following) else ["public"])
    statement = select(CreatorPlayerAnalysis).where(CreatorPlayerAnalysis.visibility.in_(allowed))
    if creator is not None:
        statement = statement.where(CreatorPlayerAnalysis.author_id == str(creator))
    total = int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = list(
        session.scalars(
            statement.order_by(CreatorPlayerAnalysis.published_on.desc(), CreatorPlayerAnalysis.id.desc()).limit(
                max(1, min(int(limit), 100))
            )
        ).all()
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        player = _anchored(session, row)
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
                "player": _player_brief(session, player, row.player_slug),
                "moved": player is None or player.content_hash != row.player_hash,
            }
        )
    return {
        "items": items,
        "total": total,
        "limit": int(MAX_PLAYER_ANALYSES_PER_CREATOR),
        "creator": str(creator) if creator is not None else None,
        "formulas": dict(FORMULAS),
        "rule": LIMITATION,
    }


def erase_player_analysis(session: Session, actor_id: str, analysis_id: str) -> dict[str, Any]:
    """Erase your own player analysis. The player it was about is untouched."""
    row = _owned(session, analysis_id, actor_id)
    erased = row.id
    session.delete(row)
    session.commit()
    return {"status": "erased", "analysis": erased}


def rules(session: Session, *, ready: bool) -> dict[str, Any]:
    """This noun's own vocabulary, published beside the guide's and the program's."""
    return {
        "analysis_caps": {
            "analysis_max": MAX_PLAYER_ANALYSES_PER_CREATOR,
            "analysis_title_max": ANALYSIS_TITLE_MAX,
            "analysis_slug_max": ANALYSIS_SLUG_MAX,
            "analysis_summary_max": ANALYSIS_SUMMARY_MAX,
            "player_slug_max": PLAYER_SLUG_MAX,
        },
        "analysis_formulas": dict(FORMULAS),
        "analysis_counts": analysis_counts(session, ready=ready),
        "analysis_rule": LIMITATION,
    }
