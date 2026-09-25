"""§23's shortlist (建立 shortlist): a list that stores membership, and borrows every figure.

The decision this module is built on is what *not* to save. §22's market listings snapshot the price an offer
was made at, and rightly — a listing is the record of an act, so the number has to stay what it was when a
seller refused it. A shortlist is the opposite kind of object: a live question, *who am I watching*. A rating
copied in at add-time would go on answering after the row behind it had been regenerated, scored a season, or
had its asking fee repriced by the valuation formula — and a stale figure on a live question is exactly what
§24's report exists to avoid.

So the two tables hold four facts about a player: that he is on the list, in which order, and the manager's own
note about him. Everything a read prints — age, band, foot, overall, potential, headroom, asking fee, the club
he is at now, the fit against a career's need — comes out of `search.pool()`, the same projection §23's search
sorts and cuts, on the request that shows it. Nothing here can go stale, because nothing here is a copy.

Two consequences are published rather than hidden:

* **A list can go stale about its own question, and says so.** The stored sentence is re-parsed and re-applied
  for every member on read, under `recheck`, so an item prints whether it still answers the phrase that found
  it. A list whose members no longer answer it is a fact about the world, and the honest response is to print it.
  The nesting is not decoration: an item's own `note` is the manager's words, and a computation about the
  list's sentence does not get to overwrite what somebody typed.
* **A list is not a ranking.** `position` is the order rows were added in; no score is computed across a list.
  Putting two players beside each other is §27's route, with the same refusal of a single number.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import Career, ScoutShortlist, ScoutShortlistItem, User
from app.services.scouting.requirements import parse_requirements
from app.services.scouting.search import Candidate, _meets, _role_fit, pool
from app.services.simulation import market
from app.services.simulation.market import MarketRefusal
from app.services.tactics.roles import ROLES, TACTICAL_ATTRIBUTES

#: What one account may hold, and how long each field of its own words may be. The routes refuse on these, so
#: `/scout/rules` publishes them rather than leaving a limit to be discovered by a 409.
MAX_SHORTLISTS: Final = 20
MAX_ITEMS: Final = 30
NAME_MAX: Final = 80
NOTE_MAX: Final = 240
QUERY_MAX: Final = 400

#: Every code a client can branch on. Each refusal leaves its figures beside its sentence, as §22's do.
REFUSALS: Final = (
    "name_required",
    "name_too_long",
    "name_taken",
    "query_too_long",
    "note_too_long",
    "too_many_shortlists",
    "shortlist_full",
    "no_such_shortlist",
    "no_such_player",
    "no_such_career",
    "already_listed",
    "not_listed",
)

#: Which answer each code deserves: a thing that is not there, a sentence that cannot be stored, and
#: everything else — a state the request would have to break, which is a conflict rather than a bug.
NOT_FOUND_CODES: Final = frozenset({"no_such_shortlist", "no_such_player", "no_such_career"})
UNPROCESSABLE_CODES: Final = frozenset({"name_required", "name_too_long", "query_too_long", "note_too_long"})
CONFLICT_CODES: Final = frozenset({"name_taken", "too_many_shortlists", "shortlist_full", "already_listed", "not_listed"})

MEMBERSHIP_RULE: Final = (
    "a shortlist row stores which player, in which order, and the manager's own note; `position` is insertion "
    "order, which is the only number about a player this schema keeps, and every other figure is read from "
    "`real_players` again on the request that shows it"
)


class ShortlistRefusal(RuntimeError):
    """A refusal that carries the figures behind its own sentence."""

    def __init__(self, code: str, message: str, **figures: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.figures = figures

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.figures}


def _count(session: Session, user: User) -> int:
    return int(session.scalar(select(func.count()).select_from(ScoutShortlist).where(ScoutShortlist.owner_id == user.id)) or 0)


def _items_held(session: Session, shortlist_id: str) -> int:
    return int(session.scalar(select(func.count()).select_from(ScoutShortlistItem).where(ScoutShortlistItem.shortlist_id == shortlist_id)) or 0)


def _owned(session: Session, user: User, ident: str) -> ScoutShortlist:
    """A list is reachable by its id, by its owner only; a foreign id reads the same as no id at all."""
    row = session.scalar(select(ScoutShortlist).where(ScoutShortlist.id == str(ident)))
    if row is None or row.owner_id != user.id:
        raise ShortlistRefusal(
            "no_such_shortlist",
            f"no shortlist of yours answers to {str(ident)!r} — a list is found by its id, and another account's id is answered the same way as one that was never issued",
            ident=str(ident),
            lists_held=_count(session, user),
        )
    return row


def _career_for(session: Session, user: User, ident: str | None) -> Career | None:
    """The career a list may be read against — and only ever the caller's own."""
    text = str(ident or "").strip()
    if not text:
        return None
    row = session.scalar(select(Career).where(Career.slug == text)) or session.scalar(select(Career).where(Career.id == text))
    if row is None or row.owner_id != user.id:
        raise ShortlistRefusal(
            "no_such_career",
            f"no career of yours is named {text!r}, so no squad need can be judged against it; a foreign career answers the same way as one that does not exist",
            career=text,
        )
    return row


def _stored(row: ScoutShortlist) -> dict[str, Any]:
    """The stored columns, printed as what they are: words somebody typed, and a link."""
    return {
        "id": row.id,
        "name": row.name,
        "query": row.query,
        "role": row.role,
        "career_id": row.career_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "stored": ["name", "query", "role", "career link", "membership", "position", "note"],
        "not_stored": "every figure about a player — see `figures_from`",
    }


def _recheck(candidate: Candidate, query: str, role: str) -> dict[str, Any]:
    """Whether this row still answers the sentence the list was built from, computed on this read."""
    text = str(query or "").strip()
    if not text:
        return {
            "asked": None,
            "answers": [],
            "no_longer_answers": [],
            "filters_applied": 0,
            "note": "no sentence is stored on this list, so nothing is re-checked against it; the membership itself is still the record",
        }
    parsed = parse_requirements(text)
    filters = [item for item in parsed.requirements if item.kind != "sort"]
    answered: list[dict[str, Any]] = []
    lost: list[dict[str, Any]] = []
    for requirement in filters:
        ok, detail = _meets(candidate, requirement)
        (answered if ok else lost).append({"phrase": requirement.phrase, "kind": requirement.kind, **detail})
    return {
        "asked": text,
        "answers": answered,
        "no_longer_answers": lost,
        "refused": [{"phrase": item.phrase, "code": item.code, "message": item.message} for item in parsed.refused],
        "unaccounted": list(parsed.unaccounted),
        "filters_applied": len(filters),
        "note": "the stored sentence is parsed and applied again on this request, so a row that has stopped answering it says so instead of keeping the claim that got it listed",
    }


def _need(session: Session, career: Career | None, round_index: int | None) -> dict[str, Any] | None:
    if career is None:
        return None
    try:
        return market.club_need(session, career, round_index=int(round_index if round_index is not None else career.rounds_played))
    except MarketRefusal as error:
        return {"refused": error.to_dict()}


def list_shortlists(session: Session, user: User) -> dict[str, Any]:
    """This account's lists, each with how many players it holds, and the gate that checks this account's rows."""
    rows = list(session.scalars(select(ScoutShortlist).where(ScoutShortlist.owner_id == user.id).order_by(ScoutShortlist.created_at, ScoutShortlist.name)))
    careers: dict[str, str] = {}
    if links := {row.career_id for row in rows if row.career_id}:
        careers = {career.id: career.slug for career in session.scalars(select(Career).where(Career.id.in_(links)))}
    items = [
        {
            **_stored(row),
            "career": careers.get(row.career_id or ""),
            "players_listed": _items_held(session, row.id),
            "room_left": max(0, MAX_ITEMS - _items_held(session, row.id)),
        }
        for row in rows
    ]
    return {
        "items": items,
        "total": len(items),
        "limit": MAX_SHORTLISTS,
        "items_limit": MAX_ITEMS,
        "room_left": max(0, MAX_SHORTLISTS - len(items)),
        "rule": "only this account's lists are listed, and this route has no figures to list: these counts are of membership rows",
        "integrity": shortlist_problems(session, user),
    }


def create_shortlist(session: Session, user: User, *, name: str, query: str = "", role: str = "", career: str | None = None) -> dict[str, Any]:
    """Open a list. The only things recorded are its name and the words it came out of."""
    label = str(name).strip()
    if not label:
        raise ShortlistRefusal("name_required", "a shortlist needs a name to be found by; an empty one cannot be listed, renamed back, or pointed at on purpose", limit=MAX_SHORTLISTS)
    if len(label) > NAME_MAX:
        raise ShortlistRefusal("name_too_long", f"{label[:24]!r}… is {len(label)} characters and this column holds {NAME_MAX}", length=len(label), max=NAME_MAX)
    if len(str(query)) > QUERY_MAX:
        raise ShortlistRefusal("query_too_long", f"the sentence stored beside a list is capped at {QUERY_MAX} characters and this one is {len(str(query))}", length=len(str(query)), max=QUERY_MAX)
    held = _count(session, user)
    if held >= MAX_SHORTLISTS:
        raise ShortlistRefusal(
            "too_many_shortlists",
            f"this account already holds {MAX_SHORTLISTS} lists, which is the cap; delete one before adding another, rather than paging through a wall of them",
            held=held,
            limit=MAX_SHORTLISTS,
        )
    link = _career_for(session, user, career)
    row = ScoutShortlist(id=new_public_id("ssl"), owner_id=user.id, name=label, query=str(query).strip(), role=str(role).strip().upper(), career_id=link.id if link else None)
    session.add(row)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ShortlistRefusal("name_taken", f"this account already has a list called {label!r}; two lists under one name cannot be asked which is which", name=label) from error
    return {
        "shortlist": _stored(row),
        "career": link.slug if link else None,
        "players_listed": 0,
        "room_left": MAX_ITEMS,
        "rule": "nothing about a player has been stored here: this row is a name and the words it came from",
    }


def shortlist_view(session: Session, user: User, ident: str, *, round_index: int | None = None) -> dict[str, Any]:
    """One list, with every figure read off the stored rows again on this request."""
    row = _owned(session, user, ident)
    items = list(session.scalars(select(ScoutShortlistItem).where(ScoutShortlistItem.shortlist_id == row.id).order_by(ScoutShortlistItem.position, ScoutShortlistItem.id)))
    candidates = {candidate.player.id: candidate for candidate in pool(session)}
    career: Career | None = session.get(Career, row.career_id) if row.career_id else None
    if career is not None and career.owner_id != user.id:
        career = None
    need = _need(session, career, round_index)
    band = str(need["needed_band"]) if need and "needed_band" in need else ""
    role_key = row.role if row.role in ROLES else ""

    printed: list[dict[str, Any]] = []
    gone: list[dict[str, Any]] = []
    for item in items:
        candidate = candidates.get(item.player_id)
        if candidate is None:
            gone.append({"player_id": item.player_id, "position": int(item.position), "note": item.note})
            continue
        printed.append(
            {
                "position": int(item.position),
                "note": item.note,
                "added_at": item.created_at.isoformat() if item.created_at else None,
                "player": candidate.to_dict(
                    wanted_attributes=sorted(set(TACTICAL_ATTRIBUTES)),
                    answers=[],
                    fit=(dict(market.tactical_fit(candidate.player, band), formula=market.FIT_FORMULA) if band else None),
                    role_fit=(_role_fit(candidate, role_key) if role_key else None),
                ),
                # The re-check is nested rather than merged: `note` on an item is the manager's own words about
                # the player, and a sentence the list computed about that sentence does not get to overwrite it.
                "recheck": _recheck(candidate, row.query, row.role),
            }
        )

    return {
        "shortlist": _stored(row),
        "career": ({"slug": career.slug, "club_name": career.club_name, "rounds_played": int(career.rounds_played)} if career else None),
        "need": need,
        "items": printed,
        "gone_from_the_world": gone,
        "counts": {
            "membership_rows": len(items),
            "printed": len(printed),
            "answered_everything": sum(1 for entry in printed if entry["recheck"]["asked"] and not entry["recheck"]["no_longer_answers"]),
            "answered_nothing": sum(1 for entry in printed if entry["recheck"]["asked"] and not entry["recheck"]["answers"]),
            "no_sentence_to_answer": sum(1 for entry in printed if not entry["recheck"]["asked"]),
        },
        "room_left": max(0, MAX_ITEMS - len(items)),
        "figures_from": "`real_players` read again on this request through §23's own candidate projection, so no figure on a list can disagree with the search that found it",
        "rules": rules(),
        "limitations": limitations(),
        "data_origin": "synthetic",
        "is_demo_data": True,
        "account_content": "the name, the sentence, the order and the notes are this account's own words; the players, clubs and figures beside them are generated fiction",
        "disclaimer": market.MARKET_DISCLAIMER,
        "demo_data": True,
    }


def add_player(session: Session, user: User, ident: str, *, player: str, note: str = "") -> dict[str, Any]:
    """Put a stored player on a list. The player is looked up first, so a wrong slug never becomes a row."""
    row = _owned(session, user, ident)
    slug = str(player).strip()
    if len(str(note)) > NOTE_MAX:
        raise ShortlistRefusal("note_too_long", f"a note is capped at {NOTE_MAX} characters and this one is {len(str(note))}", length=len(str(note)), max=NOTE_MAX)
    candidate = next((item for item in pool(session) if item.player.slug == slug), None)
    if candidate is None:
        raise ShortlistRefusal("no_such_player", f"no stored player answers to {slug!r}, so nothing can be listed under that name", ident=slug)
    held = _items_held(session, row.id)
    if held >= MAX_ITEMS:
        raise ShortlistRefusal("shortlist_full", f"{row.name!r} already holds {MAX_ITEMS} players, which is the cap for one list", shortlist=row.id, held=held, limit=MAX_ITEMS)
    if session.scalar(select(ScoutShortlistItem.id).where(ScoutShortlistItem.shortlist_id == row.id, ScoutShortlistItem.player_id == candidate.player.id)):
        raise ShortlistRefusal(
            "already_listed",
            f"{candidate.player.name} is already on {row.name!r}; a second row for one player would make the list's own count lie about how many players it holds",
            shortlist=row.id,
            player=slug,
        )
    item = ScoutShortlistItem(id=new_public_id("ssli"), shortlist_id=row.id, player_id=candidate.player.id, note=str(note).strip(), position=held + 1)
    session.add(item)
    session.commit()
    return {
        "shortlist": _stored(row),
        "added": {"position": item.position, "player": slug, "name": candidate.player.name, "note": item.note},
        "now_lists": held + 1,
        "room_left": max(0, MAX_ITEMS - held - 1),
        "stored": {"player_id": item.player_id, "position": item.position, "note": item.note},
        "not_stored": "age, overall, potential, asking fee or any other figure — each is read from the player's row on the next request",
        "rule": MEMBERSHIP_RULE,
    }


def drop_player(session: Session, user: User, ident: str, *, player: str) -> dict[str, Any]:
    """Take a player off a list. The rows that stay keep the positions they had."""
    row = _owned(session, user, ident)
    slug = str(player).strip()
    candidate = next((item for item in pool(session) if item.player.slug == slug), None)
    item = None
    if candidate is not None:
        item = session.scalar(select(ScoutShortlistItem).where(ScoutShortlistItem.shortlist_id == row.id, ScoutShortlistItem.player_id == candidate.player.id))
    if item is None:
        raise ShortlistRefusal(
            "not_listed",
            f"{slug!r} is not on {row.name!r}, so there is nothing here to take off it",
            shortlist=row.id,
            player=slug,
            listed=sorted(entry["player"]["slug"] for entry in shortlist_view(session, user, row.id)["items"]),
        )
    session.delete(item)
    session.commit()
    held = _items_held(session, row.id)
    return {
        "shortlist": _stored(row),
        "removed": slug,
        "now_lists": held,
        "room_left": max(0, MAX_ITEMS - held),
        "rule": "the membership row is gone; the player's own row is untouched, and so is every other list he is on",
    }


def update_list(session: Session, user: User, ident: str, *, name: str | None = None, query: str | None = None, role: str | None = None, career: str | None = None) -> dict[str, Any]:
    """Change the words on a list. The players on it are not touched, because they are not stored in words."""
    row = _owned(session, user, ident)
    changed: dict[str, Any] = {}
    if name is not None:
        label = str(name).strip()
        if not label:
            raise ShortlistRefusal("name_required", "a list cannot be renamed into nothing; it would still have to be found by something", name=name)
        if len(label) > NAME_MAX:
            raise ShortlistRefusal("name_too_long", f"{label[:24]!r}… is {len(label)} characters and this column holds {NAME_MAX}", length=len(label), max=NAME_MAX)
        row.name = changed["name"] = label
    if query is not None:
        if len(str(query)) > QUERY_MAX:
            raise ShortlistRefusal("query_too_long", f"the sentence beside a list is capped at {QUERY_MAX} characters and this one is {len(str(query))}", length=len(str(query)), max=QUERY_MAX)
        row.query = changed["query"] = str(query).strip()
    if role is not None:
        row.role = changed["role"] = str(role).strip().upper()
    if career is not None:
        link = _career_for(session, user, career)
        row.career_id = changed["career_id"] = link.id if link else None
    session.commit()
    return {
        "shortlist": _stored(row),
        "changed": changed,
        "rule": "changing the words changes what the next read re-checks every member against; no stored figure is involved, because none is stored",
    }


def delete_list(session: Session, user: User, ident: str) -> dict[str, Any]:
    """Delete a list. Its membership rows go with it, by the schema's own cascade rather than by this code."""
    row = _owned(session, user, ident)
    held = _items_held(session, row.id)
    session.delete(row)
    session.commit()
    return {"deleted": True, "shortlist": ident, "players_left_off": held, "rule": "the cascade removes the membership rows; no player row is involved, and nothing is written back to him"}


def rules() -> dict[str, Any]:
    """The limits and the promises, published rather than implied."""
    return {
        "max_shortlists_per_user": MAX_SHORTLISTS,
        "max_items_per_shortlist": MAX_ITEMS,
        "name_max": NAME_MAX,
        "note_max": NOTE_MAX,
        "query_max": QUERY_MAX,
        "stored": "a name, the sentence it was built from, an optional role and career link, and which players are on it in which order",
        "not_stored": "every figure about a player: age, band, foot, overall, potential, headroom, asking fee, club and fit are read from the stored rows on the request that shows them",
        "why_not": "§22 snapshots a listing's price because an offer was made at that number; a shortlist answers a live question, so a copied rating would keep claiming after the row behind it had moved",
        "rechecked_on_read": "the stored sentence is parsed and applied again for every member, so an item prints whether it still answers the phrase that found it",
        "position": "insertion order, not a ranking — no score is computed across a list, and §27's comparison is the route that puts two players side by side",
        "visibility": "a list is reachable only by its id, only by its own account; another account's id answers as one that does not exist",
        "rule": MEMBERSHIP_RULE,
        "codes": list(REFUSALS),
    }


def limitations() -> list[str]:
    return [
        "a shortlist is not a ranking: `position` records the order players were added, and no figure is computed across the members of a list",
        "membership is not observation — putting a player on a list is a fact about the account, and it changes nothing about him: no form, no contract, no interest from a club",
        "the re-check on read applies only the sentence stored on the list; filters stated field by field on the search route are not stored here, so they are not re-checked either",
        "a membership row cannot outlive the player it names — the foreign key cascades, so the list loses him the moment the world does; `gone_from_the_world` is the guard for a read whose pool no longer answers with a stored row, and it is reported rather than printed as a blank",
        "no offer, bid, negotiation or contract happens through a shortlist; §22's market routes are the only doors that move a player or money",
        "a list is private to its account: it is not published, not indexed, not shareable, and every figure on it is generated fiction about a generated player",
    ]


def shortlist_problems(session: Session, user: User) -> dict[str, Any]:
    """This account's own storage, checked against the pool the next read will see.

    What it refuses to tolerate: a membership row for a player who is not in the pool without saying so, a
    `position` that repeats or starts anywhere but at one, one player twice on one list, and a figure on a
    read that the player's own row does not say.
    """
    problems: list[str] = []
    rows = list(session.scalars(select(ScoutShortlist).where(ScoutShortlist.owner_id == user.id)))
    candidates = {candidate.player.id: candidate for candidate in pool(session)}
    total_items = 0
    for row in rows:
        items = list(session.scalars(select(ScoutShortlistItem).where(ScoutShortlistItem.shortlist_id == row.id).order_by(ScoutShortlistItem.position, ScoutShortlistItem.id)))
        total_items += len(items)
        if len({item.player_id for item in items}) != len(items):
            problems.append(f"{row.id}: {len(items)} membership rows for {len({item.player_id for item in items})} distinct players")
        positions = [int(item.position) for item in items]
        if positions and positions != list(range(1, len(positions) + 1)):
            problems.append(f"{row.id}: positions are {positions}, which is not 1..{len(positions)}")
        if len(row.name) > NAME_MAX:
            problems.append(f"{row.id}: a name of {len(row.name)} characters does not fit the {NAME_MAX} this column holds")
        printed = {str(entry["player"]["slug"]): entry for entry in shortlist_view(session, user, row.id)["items"]}
        for item in items:
            candidate = candidates.get(item.player_id)
            if candidate is None:
                continue
            entry = printed.get(candidate.player.slug)
            if entry is None:  # a stored row the view cannot find is the failure itself, not a gap to skip
                problems.append(f"{item.id}: a membership row the view does not print for {candidate.player.slug}")
                continue
            player = candidate.player
            figures = entry["player"]
            if int(figures["overall"]) != int(player.overall) or int(figures["age"]) != int(player.age) or int(figures["headroom"]) != int(player.potential) - int(player.overall):
                problems.append(f"{item.id}: the view prints figures the stored row does not say for {player.slug}")
    return {
        "clean": not problems,
        "problems": problems,
        "checked": {"shortlists": len(rows), "membership_rows": total_items, "players_in_pool": len(candidates)},
        "rule": "every stored membership row is re-read against `real_players` through the same pool this request sees, so a list cannot print a figure its own search would deny",
    }


def shortlist_ready(session: Session) -> bool:
    """The tier is ready when there is a stored pool for a list to hold players from."""
    return bool(pool(session))


def shortlist_counts(session: Session) -> dict[str, Any]:
    return {
        "shortlists_stored": int(session.scalar(select(func.count()).select_from(ScoutShortlist)) or 0),
        "membership_rows_stored": int(session.scalar(select(func.count()).select_from(ScoutShortlistItem)) or 0),
        "lists_per_user_limit": MAX_SHORTLISTS,
        "items_per_list_limit": MAX_ITEMS,
        "rule": "both counts are of stored membership only; the figures a list prints come from `real_players` on each read",
    }
