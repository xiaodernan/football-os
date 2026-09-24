"""A career's squad as it stood in one particular round (spec §22).

This module exists because of one sentence in the market design: a signed striker has to change the
eleven the engine plays. `profile.team_profile` selects a side from the club's stored `real_players`
rows, so either transfers rewrite those rows — which would corrupt the generated world every other
page reads — or the squad is *composed* at read time from the world's rows plus the career's own
moves. This file does the second.

Three rules:

1. **As of the round, not as of today.** A match stored against round 4 was decided by the squad that
   existed before round 4, so a replay rebuilds the overlay from the moves whose `round_index` is at
   or before that fixture's. Get this wrong and a career's old matches quietly change result after a
   later signing, which is the one thing a deterministic engine must never do.
2. **The last move wins.** A player bought and then sold is neither in nor out; a player sold and
   bought back is in. `career_squad_moves` stays an append-only history and the squad is derived.
3. **A loan expires.** A loaned player is in the squad for the rounds the deal covered and gone
   afterwards, without a row being written when the calendar passes them by.
4. **The same read carries the load.** §20's condition map is composed beside the arrivals and
   departures from the career's appearance rows for the rounds *before* this one, so a replay rebuilds
   the tiredness the side actually had as well as the personnel it actually had. A round 1 with no
   history is the one case where both are empty and the club is its stored self.

Nothing here invents a player: the arrivals are the stored `real_players` rows themselves, so the
attributes the engine reads are the ones on file, and a signed player whose row has vanished is named
in the overlay's label rather than replaced with a plausible stand-in.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Career, CareerFixture, CareerSquadMove, RealPlayer, Team
from app.services.simulation.carry_over import condition_map
from app.services.simulation.profile import SquadOverlay

# Which kinds bring a player in and which take them out. Kept as data so the overlay and the refusal
# messages agree with each other without either restating the other.
IN_KINDS: Final = ("buy", "loan")
OUT_KINDS: Final = ("sell", "release")
MIN_PLAYERS_FOR_XI: Final = 11
MIN_KEEPERS: Final = 1
SQUARD_RULE: Final = (
    "a career keeps a side on the pitch only while its squad holds at least 11 players and at least 1 of them is a goalkeeper; the counts beside this rule are the ones that decided it"
)


def moves_as_of(session: Session, career_id: str, round_index: int) -> list[CareerSquadMove]:
    """Every move the career had made by the start of `round_index`, oldest first."""
    return list(
        session.scalars(
            select(CareerSquadMove)
            .where(CareerSquadMove.career_id == career_id, CareerSquadMove.round_index <= round_index)
            .order_by(CareerSquadMove.round_index, CareerSquadMove.created_at, CareerSquadMove.id)
        ).all()
    )


def effective_kind(move: CareerSquadMove, round_index: int) -> str:
    """What a move does to the squad in this round: an expired loan takes the player out by another name.

    Reads rather than writes — the row's own `kind` says what was agreed at the time, and nothing here
    edits a stored history to say otherwise.
    """
    if move.kind == "loan" and round_index > int(move.loan_until_round or 0):
        return "loan_out"
    return move.kind


def squad_state(session: Session, career: Career, round_index: int) -> dict[str, str]:
    """player id → whether the career's moves leave them in or out of the club in this round.

    Only players a move touched appear here; everyone else is whatever the world's rows say.
    """
    state: dict[str, str] = {}
    for move in moves_as_of(session, career.id, round_index):
        state[move.player_id] = effective_kind(move, round_index)
    return state


def squad_as_of(session: Session, career: Career, round_index: int) -> SquadOverlay | None:
    """The overlay that turns the club's stored rows into the squad this career plays with.

    `None` when the career has changed nothing by that round: no move applied, and no played round to
    carry load from. Either half of that can hold on its own — a career that never used the market still
    gets an overlay from round 2 onwards, because §20's carry-over is a change to the side too.
    """
    if not career.club_id:
        return None
    condition = condition_map(session, career.id, round_index=round_index)
    stored = {player.id: player for player in session.scalars(select(RealPlayer).where(RealPlayer.team_id == career.club_id))}
    added: list[RealPlayer] = []
    removed: set[str] = set()
    missing: list[str] = []
    for player_id, kind in squad_state(session, career, round_index).items():
        if kind in IN_KINDS:
            if player_id in stored:
                continue  # back at the club it was on all along; the world's rows say so without help from us.
            player = session.get(RealPlayer, player_id)
            if player is None:
                missing.append(player_id)
                continue
            added.append(player)
        elif player_id in stored:
            removed.add(player_id)
    if not added and not removed and not missing and not condition:
        return None
    label = ""
    if added or removed or missing:
        label = f"{career.slug} squad as of round {round_index}: {len(added)} signed in, {len(removed)} departed" + (f", {len(missing)} signed player(s) no longer stored" if missing else "")
    return SquadOverlay(
        added=tuple(sorted(added, key=lambda player: (-player.overall, player.slug))),
        removed=frozenset(removed),
        label=label,
        condition=condition,
    )


def current_squad(session: Session, career: Career) -> tuple[list[RealPlayer], dict[str, Any]]:
    """The players this career's club can field right now, with the account of how that was read.

    The second value is what a selling page prints beside the list: the world's row count, the
    arrivals, the departures, and the rule a departure has to leave standing.
    """
    round_index = int(career.rounds_played) + 1
    stored = list(session.scalars(select(RealPlayer).where(RealPlayer.team_id == (career.club_id or "")).order_by(RealPlayer.slug)).all())
    by_id = {player.id: player for player in stored}
    stored_ids = set(by_id)
    moves = moves_as_of(session, career.id, round_index)
    signed_in = departed = 0
    for player_id, kind in squad_state(session, career, round_index).items():
        if kind in IN_KINDS:
            player = session.get(RealPlayer, player_id)
            if player is not None:
                by_id[player_id] = player
                if player_id not in stored_ids:
                    signed_in += 1
        elif by_id.pop(player_id, None) is not None:
            departed += 1
    squad = sorted(by_id.values(), key=lambda player: (-player.overall, player.slug))
    account = {
        "club_id": career.club_id,
        "club_name": session.scalar(select(Team.name).where(Team.id == (career.club_id or ""))) or career.club_name,
        "as_of_round": round_index,
        "stored_in_world": len(stored),
        "signed_in": signed_in,
        "departed": departed,
        "moves": len(moves),
        "squad_now": len(squad),
        "keepers": sum(1 for player in squad if player.position == "GK"),
        "rule": SQUARD_RULE,
    }
    return squad, account


def can_field_side(squad: list[RealPlayer], *, dropping_id: str | None = None) -> dict[str, Any]:
    """Whether the squad still satisfies the rule that keeps a side on the pitch, after one departure."""
    kept = [player for player in squad if player.id != (dropping_id or "")]
    keepers = sum(1 for player in kept if player.position == "GK")
    return {
        "ok": len(kept) >= MIN_PLAYERS_FOR_XI and keepers >= MIN_KEEPERS,
        "players": len(kept),
        "keepers": keepers,
        "needs_players": MIN_PLAYERS_FOR_XI,
        "needs_keepers": MIN_KEEPERS,
        "rule": SQUARD_RULE,
    }


def replay_squads(session: Session, match_id: str, home_team_id: str, away_team_id: str) -> tuple[SquadOverlay | None, SquadOverlay | None, dict[str, Any]]:
    """The overlays a stored match must be replayed with, found through the career that recorded it.

    Returns a note beside them, because a replay that used a different eleven than the one that played
    would report a changed squad as a broken engine — the note is what makes the difference legible.
    """
    fixtures = list(session.scalars(select(CareerFixture).where(CareerFixture.match_id == match_id)).all())
    if not fixtures:
        return None, None, {"note": "no career recorded this match, so both sides are their clubs' stored squads"}
    if len(fixtures) > 1:
        return None, None, {"note": f"{len(fixtures)} careers point at this one match report, so the squad it played with cannot be attributed"}
    fixture = fixtures[0]
    career = session.get(Career, fixture.career_id)
    if career is None or not career.club_id:
        return None, None, {"note": f"career {fixture.career_id} that recorded this match is no longer stored, so its squad changes are gone with it"}
    if career.club_id not in (home_team_id, away_team_id):
        return None, None, {"note": f"career {career.slug} records this match but manages neither club in it"}
    overlay = squad_as_of(session, career, int(fixture.round_index))
    if overlay is None:
        return (
            None,
            None,
            {
                "career_slug": career.slug,
                "round_index": fixture.round_index,
                "note": f"career {career.slug} had made no squad move before round {fixture.round_index}, so both sides are their clubs' stored squads",
            },
        )
    side = "home" if career.club_id == home_team_id else "away"
    detail = {
        "career_slug": career.slug,
        "round_index": fixture.round_index,
        "side": side,
        "applied": overlay.summary,
        "note": f"replayed with {overlay.summary}",
    }
    return (overlay, None, detail) if side == "home" else (None, overlay, detail)


__all__ = [
    "IN_KINDS",
    "MIN_KEEPERS",
    "MIN_PLAYERS_FOR_XI",
    "OUT_KINDS",
    "SQUARD_RULE",
    "can_field_side",
    "current_squad",
    "effective_kind",
    "moves_as_of",
    "replay_squads",
    "squad_as_of",
    "squad_state",
]
