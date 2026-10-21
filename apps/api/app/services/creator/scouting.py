"""Scouting lists: §36's sixth kind of content, a selection of footballers addressed rather than copied.

§36 lists six kinds of content a user can create. The sixth is a **Scouting List** - an author's
selection of players, published as the addresses of those players and the author's own note on each.

The rule is the one the tactical guide, the player analysis and the match analysis were built on:
**a publication stores an address, never a copy**. A list stores its title, its own summary, a
visibility and, for each selection, the address of a row in `real_players`, the content address that
player carried at publication, and the author's words. It stores no name, position, overall, club or
sentence about a player. Every attribute a read shows is read from the world's row on that read.

The witness is per entry, because the anchors are: a read compares each entry's stored hash with its
player's current one, so a single refreshed footballer says `moved` on their own line while the rest
of the list stands still. A player the world has retired leaves a bare address (`retired: true`, the
brief's fields null) rather than erasing the list - a list is a selection of many addresses, and one
retirement is not the end of the author's other selections. That is deliberately not the shape a
single-anchor analysis uses, where the retired anchor is absence: there the whole content is about
that one row.

The anchors are resolved **at publication**, so a list naming a footballer the world does not hold
is refused there rather than surfacing as a page with broken rows. Two entries naming the same
footballer are refused too: a list cannot hold two notes on one address and still say which is the
reading.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import CreatorScoutingEntry, CreatorScoutingList, RealPlayer, Team, User
from app.services.creator.publishing import (
    VISIBILITIES,
    CreatorRefusal,
    _slug_of,
    _text,
    ensure_profile,
    visible_authors,
)
from app.services.world.plan import web_path

#: How many scouting lists one creator may publish.
MAX_SCOUTING_LISTS_PER_CREATOR: Final = 40
SCOUTING_LIST_TITLE_MAX: Final = 160
SCOUTING_LIST_SLUG_MAX: Final = 80
SCOUTING_LIST_SUMMARY_MAX: Final = 600
#: A list is a shortlist an author can argue for, not the whole world.
SCOUTING_PLAYERS_MIN: Final = 1
SCOUTING_PLAYERS_MAX: Final = 50
SCOUTING_NOTE_MAX: Final = 300
SCOUTING_ANCHOR_MAX: Final = 200

#: The tier's own vocabulary for this noun, published by the rules door beside the others'.
FORMULAS: Final = {
    "players": "count of the entry rows this list holds - one per selection, so it is a number of addresses, not a measurement of any player",
    "moved": "count of entries whose player's content address now differs from the one stored when the list was published; every attribute is still read from the player's own columns on this read",
    "retired": "count of entries whose player the world no longer holds at that address, read on this request",
    "scouting_lists": "count of every scouting-list row this database holds",
    "scouting_entries": "count of every selection row this database holds across all lists",
}

LIMITATION: Final = (
    "a scouting list stores a title, its own summary, a visibility and, for each selection, the address of a "
    "footballer, the content address that player carried at publication and the author's own note - never a "
    "name, a position, an overall, a club or a sentence about the player. Every attribute a read shows is read "
    "from the world's player row on that read, so a refreshed world cannot leave the list describing last "
    "season's squad; a player revised since the list was written says so through `moved` on their own entry, and "
    "a player the world has retired leaves a bare address rather than erasing the author's other selections"
)


def _visibility(visibility: Any) -> str:
    word = str(visibility or "").strip().lower()
    if word not in VISIBILITIES:
        raise CreatorRefusal(
            "scouting_list_visibility",
            f"a scouting list is {' or '.join(repr(item) for item in VISIBILITIES)}; {word!r} would select nobody and the door cannot tell that from a mistake",
            sent=word,
            visibilities=list(VISIBILITIES),
        )
    return word


def _player(session: Session, ident: Any) -> RealPlayer:
    """The world player one selection names. An address that names nothing refuses at publication."""
    key = str(ident or "").strip()
    if not key:
        raise CreatorRefusal(
            "no_such_scouted_player",
            "a scouting list names a player on every line, and this line names none",
            player=key,
        )
    row = session.scalar(select(RealPlayer).where(or_(RealPlayer.slug == key, RealPlayer.id == key)))
    if row is None:
        raise CreatorRefusal(
            "no_such_scouted_player",
            f"the generated world holds no player called {key!r}, so a list naming them would have nothing to read",
            player=key,
        )
    return row


def _entries(session: Session, players: Any) -> list[dict[str, Any]]:
    """The selections, in the order they were sent, each resolved to the world's own address."""
    raw = list(players or [])
    if len(raw) < SCOUTING_PLAYERS_MIN or len(raw) > SCOUTING_PLAYERS_MAX:
        raise CreatorRefusal(
            "scouting_players",
            f"a scouting list holds between {SCOUTING_PLAYERS_MIN} and {SCOUTING_PLAYERS_MAX} players and this one has {len(raw)}",
            players=len(raw),
            min=SCOUTING_PLAYERS_MIN,
            max=SCOUTING_PLAYERS_MAX,
        )
    resolved: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise CreatorRefusal("scouting_players", f"selection {index + 1} is not a selection", position=index + 1)
        player = _player(session, entry.get("player"))
        if player.slug in seen:
            raise CreatorRefusal(
                "scouting_duplicate_player",
                f"selection {index + 1} names {player.slug!r}, which selection {seen[player.slug]} already names; a list cannot hold two notes on one address",
                player=player.slug,
                first=seen[player.slug],
                again=index + 1,
            )
        seen[player.slug] = index + 1
        resolved.append(
            {
                "position": index + 1,
                "player": player.slug,
                "hash": player.content_hash,
                "note": _text(entry.get("note"), SCOUTING_NOTE_MAX, "scouting_note", "scouting note", required=False),
            }
        )
    return resolved


def scouting_counts(session: Session, *, ready: bool) -> dict[str, int]:
    """The rulebook's counts of this tier's scouting tables."""
    if not ready:
        return {"scouting_lists": 0, "scouting_entries": 0}
    return {
        "scouting_lists": int(session.scalar(select(func.count()).select_from(CreatorScoutingList)) or 0),
        "scouting_entries": int(session.scalar(select(func.count()).select_from(CreatorScoutingEntry)) or 0),
    }


def _list(session: Session, ident: str) -> CreatorScoutingList:
    row = session.get(CreatorScoutingList, str(ident))
    if row is None:
        raise CreatorRefusal("no_such_scouting_list", f"no scouting list answers to {str(ident)!r}", list=str(ident))
    return row


def _owned(session: Session, list_id: str, actor_id: str) -> CreatorScoutingList:
    row = _list(session, list_id)
    if row.author_id != actor_id:
        raise CreatorRefusal("no_such_scouting_list", f"no scouting list of yours answers to {str(list_id)!r}", list=str(list_id))
    return row


def _entries_of(session: Session, list_id: str) -> list[CreatorScoutingEntry]:
    return list(
        session.scalars(
            select(CreatorScoutingEntry)
            .where(CreatorScoutingEntry.list_id == list_id)
            .order_by(CreatorScoutingEntry.position)
        ).all()
    )


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


def _entry_shape(session: Session, entry: CreatorScoutingEntry) -> dict[str, Any]:
    player = session.scalar(select(RealPlayer).where(RealPlayer.slug == entry.player_slug))
    retired = player is None
    return {
        "position": entry.position,
        "player": _player_brief(session, player, entry.player_slug),
        "note": entry.note,
        "retired": retired,
        "moved": player is not None and player.content_hash != entry.player_hash,
    }


def publish_scouting_list(
    session: Session,
    actor_id: str,
    *,
    title: Any,
    summary: Any = "",
    visibility: Any = "public",
    players: Any = None,
) -> dict[str, Any]:
    """Publish a scouting list: a title, a visibility and the players the author selected."""
    ensure_profile(session, actor_id)
    wanted_title = _text(title, SCOUTING_LIST_TITLE_MAX, "scouting_list_title", "scouting list title", required=True)
    wanted_visibility = _visibility(visibility)
    resolved = _entries(session, players)

    mine = int(
        session.scalar(
            select(func.count()).select_from(CreatorScoutingList).where(CreatorScoutingList.author_id == actor_id)
        )
        or 0
    )
    if mine >= MAX_SCOUTING_LISTS_PER_CREATOR:
        raise CreatorRefusal(
            "scouting_list_limit",
            f"a creator may publish {MAX_SCOUTING_LISTS_PER_CREATOR} scouting lists and this account has {mine}",
            lists=mine,
            max=MAX_SCOUTING_LISTS_PER_CREATOR,
        )

    slug = _slug_of(wanted_title)[:SCOUTING_LIST_SLUG_MAX]
    taken = session.scalar(
        select(CreatorScoutingList).where(
            CreatorScoutingList.author_id == actor_id, CreatorScoutingList.slug == slug
        )
    )
    if taken is not None:
        raise CreatorRefusal(
            "slug_taken",
            f"this account already publishes a scouting list called {slug!r}, and a reader cannot tell two lists apart by a name",
            slug=slug,
        )

    row = CreatorScoutingList(
        id=new_public_id("csl"),
        author_id=actor_id,
        slug=slug,
        title=wanted_title,
        summary=_text(summary, SCOUTING_LIST_SUMMARY_MAX, "scouting_list_summary", "scouting list summary", required=False),
        visibility=wanted_visibility,
    )
    session.add(row)
    # The entries carry a plain FK and no ORM relationship, so the unit of work would insert them
    # before their parent; the flush is what makes the order the schema requires.
    session.flush()
    for entry in resolved:
        session.add(
            CreatorScoutingEntry(
                id=new_public_id("cse"),
                list_id=row.id,
                position=entry["position"],
                player_slug=entry["player"],
                player_hash=entry["hash"],
                note=entry["note"],
            )
        )
    session.commit()
    return read_scouting_list(session, row.id, actor_id)


def _view(session: Session, row: CreatorScoutingList) -> dict[str, Any]:
    entries = _entries_of(session, row.id)
    shapes = [_entry_shape(session, entry) for entry in entries]
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
        "entries": shapes,
        "figures": {
            "players": len(shapes),
            "moved": sum(1 for shape in shapes if shape["moved"]),
            "retired": sum(1 for shape in shapes if shape["retired"]),
        },
        "formulas": dict(FORMULAS),
        "rule": LIMITATION,
    }


def _reachable(session: Session, list_id: str, viewer_id: str) -> CreatorScoutingList:
    """One list, if this reader may reach it. A list they may not reach is answered as absence."""
    row = _list(session, list_id)
    if row.visibility == "followers" and row.author_id not in set(visible_authors(session, viewer_id)):
        raise CreatorRefusal("no_such_scouting_list", f"no scouting list answers to {str(list_id)!r}", list=str(list_id))
    return row


def read_scouting_list(session: Session, list_id: str, viewer_id: str) -> dict[str, Any]:
    """One scouting list, with every selection read from the world's player row on this read."""
    row = _reachable(session, list_id, viewer_id)
    return _view(session, row)


def list_scouting_lists(
    session: Session, viewer_id: str, *, creator: str | None = None, limit: int = 20
) -> dict[str, Any]:
    """The shelf of scouting lists as far as this reader may reach, each named by its own size."""
    following = visible_authors(session, viewer_id)[1:]
    own = creator is not None and str(creator) == viewer_id
    allowed = list(VISIBILITIES) if own else (
        ["public", "followers"] if (creator is not None and str(creator) in following) else ["public"]
    )
    statement = select(CreatorScoutingList).where(CreatorScoutingList.visibility.in_(allowed))
    if creator is not None:
        statement = statement.where(CreatorScoutingList.author_id == str(creator))
    total = int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = list(
        session.scalars(
            statement.order_by(CreatorScoutingList.published_on.desc(), CreatorScoutingList.id.desc()).limit(
                max(1, min(int(limit), 100))
            )
        ).all()
    )
    items: list[dict[str, Any]] = []
    for row in rows:
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
                "players": int(
                    session.scalar(
                        select(func.count())
                        .select_from(CreatorScoutingEntry)
                        .where(CreatorScoutingEntry.list_id == row.id)
                    )
                    or 0
                ),
            }
        )
    return {
        "items": items,
        "total": total,
        "limit": int(MAX_SCOUTING_LISTS_PER_CREATOR),
        "creator": str(creator) if creator is not None else None,
        "formulas": dict(FORMULAS),
        "rule": LIMITATION,
    }


def erase_scouting_list(session: Session, actor_id: str, list_id: str) -> dict[str, Any]:
    """Erase your own scouting list. The players it named are untouched."""
    row = _owned(session, list_id, actor_id)
    erased = row.id
    session.delete(row)
    session.commit()
    return {"status": "erased", "list": erased}


def rules(session: Session, *, ready: bool) -> dict[str, Any]:
    """This noun's own vocabulary, published beside the guide's, the program's and the analyses'."""
    return {
        "scouting_list_caps": {
            "scouting_list_max": MAX_SCOUTING_LISTS_PER_CREATOR,
            "scouting_list_title_max": SCOUTING_LIST_TITLE_MAX,
            "scouting_list_slug_max": SCOUTING_LIST_SLUG_MAX,
            "scouting_list_summary_max": SCOUTING_LIST_SUMMARY_MAX,
            "scouting_players_min": SCOUTING_PLAYERS_MIN,
            "scouting_players_max": SCOUTING_PLAYERS_MAX,
            "scouting_note_max": SCOUTING_NOTE_MAX,
            "scouting_anchor_max": SCOUTING_ANCHOR_MAX,
        },
        "scouting_list_formulas": dict(FORMULAS),
        "scouting_list_counts": scouting_counts(session, ready=ready),
        "scouting_list_rule": LIMITATION,
    }
