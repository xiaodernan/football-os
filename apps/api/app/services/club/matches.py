"""§39's Matches row: the fixtures a tenant arranges, and the answer the engine gives when one is played.

The tier's other nouns record something that happened to a child or a team. This one arranges a date first and
plays it afterwards, which is why it is two tables and one service: an arrangement is the tenant's own words,
a result is the engine's. Four things hold it to the rest of the club OS:

* **No scoreline is stored here.** The goals, the per-block ledger, the timeline and every counted figure live
  in `sim_matches` and `sim_events`; a fixture keeps a pointer (`match_id`, `match_slug`), the report's
  `digest`, the `model_version` that produced it and the `seed` the caller chose, so the number a page prints
  is read from the row that owns it. A stored score would disagree with a re-played match the next morning,
  which is the mistake §40 already refused for `progress` and §41 for `load_units`.
* **The side that plays is the tenant's sheet, not the world club it is bound to.** `team_profile` reads a
  world club's own players and then applies an overlay, so the tenant's eleven enters as
  `SquadOverlay(added=<the sheet's players>, removed=<that club's stored squad>)` and the engine selects from
  exactly the rows the tenant holds. That is the same mechanism §22 built for a career's signings, used here
  in the opposite direction — and no change to the engine.
* **The eleven is recorded, and only when it can be.** `career._trace_round` checks the names it is about to
  write against the names in the stored report, and leaves a round untraced rather than attribute a load to
  players who may not have played it. A club fixture does the same thing for the same reason: when the two
  disagree, the result stands (the engine's row *is* the truth) and the answer prints
  `appearances_written: 0` beside the reason.
* **A child on that sheet still needs their guardian.** Every minor in the selection passes the same scope gate
  that opens a plan or records a session, so a match record about a child sits behind the same yes. The scope it
  asks for is `plan`, which is §40's word for a record of that child's development work and the same one §41's
  attendance gate asks for (`sessions.py:198`): an appearance row is that kind of record, and the tier has no
  fourth purpose to invent for it.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import ClubFixture, ClubMatchAppearance, ClubTeam, ClubTeamMember, Organization, RealPlayer, SimulationMatch, User
from app.models import Team as WorldTeam
from app.services.club.academy import _clip, _is_minor, _iso, _player_of, _require_scope, _today
from app.services.club.organizations import ClubRefusal, require, resolve_team
from app.services.simulation.profile import SquadOverlay, team_profile
from app.services.simulation.service import BLOCK_MINUTES, MINUTES_CHOICES, run_simulation
from app.services.simulation.squad import MIN_KEEPERS, MIN_PLAYERS_FOR_XI

MAX_FIXTURES_PER_ORGANIZATION: Final = 200
SIDES: Final = ("home", "away")
COMPETITION_MAX: Final = 120
NOTE_MAX: Final = 280
NAMED_MAX: Final = 40
#: The engine plays a fixed set of block lengths, and `/simulate/options` publishes them. A range invented here
#: would be a second rule about the same input — the door that takes the minutes and the door that stores them
#: would disagree, which is the §42 class of defect. So the club tier imports the choice set instead of drawing
#: a band around it, and refuses anything outside it with its own code.
DEFAULT_MINUTES: Final = 90

#: What a listing sums over, printed beside the figure it produced rather than paraphrased by a page.
FORMULAS: Final = {
    "played": "count of the rows in this list whose `status` is `played`",
    "appearances": "one row per player the engine selected, written when the eleven rebuilt from this tenant's rows matches the eleven the stored report names",
    "fixture_total": "count of this tenant's fixture rows, before any team or status filter",
}

#: Every code this part of the tier can answer with. An absence is a 404, a caller-correctable figure a 422, a
#: collision with a row that already exists a 409 — and 403 stays the permission matrix's single meaning.
REFUSALS: Final = (
    "no_such_fixture",
    "no_such_world_club",
    "no_world_side",
    "no_opponent_side",
    "side_shape",
    "fixture_limit",
    "side_taken",
    "fixture_played",
    "minutes_choice",
    "named_limit",
    "not_on_sheet",
    "opponent_is_own_club",
    "can_not_field",
    "date_in_future",
    "date_shape",
    "text_too_long",
)

NOT_FOUND_CODES: Final = frozenset({"no_such_fixture"})
UNPROCESSABLE_CODES: Final = frozenset(
    {
        "no_world_side",
        "no_opponent_side",
        "side_shape",
        "minutes_choice",
        "named_limit",
        "not_on_sheet",
        "opponent_is_own_club",
        "can_not_field",
        "date_in_future",
        "date_shape",
        "text_too_long",
    }
)
CONFLICT_CODES: Final = frozenset({"fixture_limit", "side_taken", "fixture_played"})
FORBIDDEN_CODES: Final[frozenset[str]] = frozenset()

#: `date_shape` and `text_too_long` are §40's and `no_such_world_club` is §39's, already registered by the
#: team door as a 404 — the opponent lookup answers with that code and that status rather than inventing a
#: synonym, so an absent club is absent at both doors. `assemble()` refuses a tier that claims one code twice
#: with two answers, which is what the draft did before this line was true.
PUBLISHED: Final = tuple(code for code in REFUSALS if code not in {"date_shape", "text_too_long", "no_such_world_club"})

CAPS: Final = {
    "max_fixtures_per_organization": MAX_FIXTURES_PER_ORGANIZATION,
    "sides": list(SIDES),
    "competition_max": COMPETITION_MAX,
    "fixture_note_max": NOTE_MAX,
    "named_max": NAMED_MAX,
    # The engine's own vocabulary, printed as the choices it accepts rather than as a band this tier drew.
    "minute_choices": list(MINUTES_CHOICES),
    "default_minutes": DEFAULT_MINUTES,
    "block_minutes": BLOCK_MINUTES,
    "needs_players": MIN_PLAYERS_FOR_XI,
    "needs_keepers": MIN_KEEPERS,
}

LIMITATION: Final = (
    "a fixture is arranged against a club in the generated world, and a tenant's team can only be played once it "
    "has been placed in that ladder; the eleven is the tenant's own sheet, applied over the club it is bound to. "
    "A club fixture plays with the bound club's formation, because §39's Tactics row is unwritten, and it carries "
    "no fatigue: a condition index comes from a career's appearance ledger, which these fixtures do not read"
)


def fixture_counts(session: Session, *, ready: bool) -> dict[str, Any]:
    """The rulebook's count of fixture rows — 0 rather than a crash when this database has no such table."""
    if not ready:
        return {"fixtures": 0, "fixture_appearances": 0}
    return {
        "fixtures": int(session.scalar(select(func.count()).select_from(ClubFixture)) or 0),
        "fixture_appearances": int(session.scalar(select(func.count()).select_from(ClubMatchAppearance)) or 0),
    }


def club_fixture_ready(session: Session) -> bool:
    """Whether this database has the two tables this tier writes, the same question §40 asks of its own."""
    from sqlalchemy import inspect

    existing = set(inspect(session.get_bind()).get_table_names())
    return {"club_fixtures", "club_match_appearances"} <= existing


def _fixtures_of(session: Session, organization: Organization) -> list[ClubFixture]:
    return list(session.scalars(select(ClubFixture).where(ClubFixture.organization_id == organization.id).order_by(ClubFixture.scheduled_on.desc(), ClubFixture.id)))


def _fixture(session: Session, organization: Organization, ident: str) -> ClubFixture:
    """A fixture is found by id inside its own tenant, and nowhere else."""
    row = session.get(ClubFixture, str(ident))
    if row is None or row.organization_id != organization.id:
        raise ClubRefusal("no_such_fixture", f"no fixture of this tenant answers to {str(ident)!r}", fixture=str(ident), organization=organization.slug)
    return row


def _world_club(session: Session, ident: Any) -> WorldTeam:
    """A club in the generated world, by slug or by id — the same two spellings §39's team door accepts."""
    text = str(ident or "").strip()
    world = session.scalar(select(WorldTeam).where(WorldTeam.slug == text)) or session.get(WorldTeam, text)
    if world is None:
        raise ClubRefusal("no_such_world_club", f"no club in the generated world is named {text!r}, so nothing can be played against it", world_team=text)
    return world


def _selection(session: Session, organization: Organization, team: ClubTeam, named: Any, *, gate_minors: bool) -> list[RealPlayer]:
    """The players a fixture will be played with: this tenant's sheet, resolved to the people behind them.

    An empty `named` means the whole sheet — a coach who arranged a fixture before picking an eleven is not
    arranging nothing — and every name sent has to already be on that sheet, so a fixture cannot quietly widen
    who a tenant fields. The ids stored are the ones the addresses resolved *to*, not the strings a caller
    typed: §42's attendance row learned that the hard way, and the read below looks each player up by primary
    key to print their slug, age and band.
    """
    on_sheet = {str(member.player_id): member for member in session.scalars(select(ClubTeamMember).where(ClubTeamMember.team_id == team.id))}
    wanted = [str(item).strip() for item in list(named or []) if str(item).strip()]
    if len(wanted) > NAMED_MAX:
        raise ClubRefusal("named_limit", f"a fixture names at most {NAMED_MAX} players and this one names {len(wanted)}", named=len(wanted), max=NAMED_MAX)
    chosen: dict[str, RealPlayer] = {}
    for spelling in wanted:
        person = _player_of(session, organization, spelling, on_sheet=False)
        if person.id not in on_sheet:
            raise ClubRefusal(
                "not_on_sheet",
                f"{team.name}'s sheet holds {len(on_sheet)} player(s) and this fixture names {person.name}, who is not among them",
                team=team.name,
                player=person.slug,
                on_sheet=len(on_sheet),
            )
        chosen[person.id] = person
    rows = list(chosen.values()) or [player for pid in on_sheet if (player := session.get(RealPlayer, pid)) is not None]
    if gate_minors:
        for person in rows:
            if _is_minor(int(person.age)):
                _require_scope(session, organization, person, "plan")
    return rows


def _can_field(players: list[RealPlayer]) -> dict[str, Any]:
    """The 11-and-a-keeper question, asked of the tenant's own selection.

    The figures come from `simulation.squad`'s constants so a tenant's sheet is judged by the same arithmetic a
    career's is; the sentence is this tier's, because the published rule it would otherwise quote begins "a
    career keeps a side on the pitch…", and a tenant's U16 sheet is not a career.
    """
    keepers = sum(1 for player in players if player.position == "GK")
    return {
        "ok": len(players) >= MIN_PLAYERS_FOR_XI and keepers >= MIN_KEEPERS,
        "players": len(players),
        "keepers": keepers,
        "needs_players": MIN_PLAYERS_FOR_XI,
        "needs_keepers": MIN_KEEPERS,
        "rule": f"a side is fielded only while the names on it reach {MIN_PLAYERS_FOR_XI} and at least {MIN_KEEPERS} of them is a goalkeeper; these are the counts that decided it",
    }


def fixture_view(session: Session, row: ClubFixture) -> dict[str, Any]:
    team = session.get(ClubTeam, row.team_id)
    world = session.get(WorldTeam, row.opponent_team_id) if row.opponent_team_id else None
    bound = session.get(WorldTeam, team.world_team_id) if (team is not None and team.world_team_id) else None
    match = session.get(SimulationMatch, row.match_id) if row.match_id else None
    appearances = int(session.scalar(select(func.count()).select_from(ClubMatchAppearance).where(ClubMatchAppearance.fixture_id == row.id)) or 0)
    named = [session.get(RealPlayer, pid) for pid in list(row.named or [])]
    return {
        "id": row.id,
        "team": (
            {
                "id": team.id,
                "name": team.name,
                "age_group": team.age_group,
                "world_team": ({"slug": bound.slug, "name": bound.name} if bound is not None else None),
            }
            if team
            else None
        ),
        "opponent": ({"id": world.id, "slug": world.slug, "name": world.name, "path": f"/team/{world.slug}"} if world else None),
        "opponent_name": row.opponent_name,
        "side": row.side,
        "competition": row.competition,
        "scheduled_on": row.scheduled_on,
        "status": row.status,
        "named": [{"slug": person.slug, "name": person.name, "position": person.position, "age": int(person.age), "is_minor": _is_minor(int(person.age))} for person in named if person is not None],
        "named_gone": len(named) - len([person for person in named if person is not None]),
        "appearances": appearances,
        "match": (
            {"slug": match.slug, "digest": match.digest, "model_version": match.model_version, "seed": int(match.seed), "minutes": int(match.minutes), "path": f"/simulations/{match.slug}"}
            if match
            else None
        ),
        "note": row.note,
        "recorded_on": row.created_at.isoformat() if row.created_at else None,
    }


def create_fixture(
    session: Session,
    user: User,
    ident: str,
    *,
    team: str,
    opponent: str,
    scheduled_on: str,
    side: str = "home",
    competition: str = "",
    named: Any = None,
    note: str = "",
) -> dict[str, Any]:
    """Arrange one fixture. Nothing here is a figure about a match, because no match has been played."""
    organization, _ = require(session, user, ident, "match.write")
    sheet_team = resolve_team(session, organization, team)
    day = _iso(scheduled_on, label="a fixture date")
    if str(side) not in SIDES:
        raise ClubRefusal("side_shape", f"a fixture is played at {SIDES[0]} or {SIDES[1]}; {side!r} is neither", sent=str(side), sides=list(SIDES))
    if day > _today().isoformat():
        raise ClubRefusal("date_in_future", f"a fixture is arranged against a date that has arrived so the result can be recorded; {day} has not", scheduled_on=day, today=_today().isoformat())
    held = len(_fixtures_of(session, organization))
    if held >= MAX_FIXTURES_PER_ORGANIZATION:
        raise ClubRefusal("fixture_limit", f"this tenant already arranges {MAX_FIXTURES_PER_ORGANIZATION} fixtures, which is the cap", held=held, limit=MAX_FIXTURES_PER_ORGANIZATION)
    world = _world_club(session, opponent)
    # The engine publishes one rule about a fixture's two sides and this tier does not get to waive it: "a
    # fixture needs two different clubs; the model has no self-play". A tenant whose sheet is bound to a world
    # club cannot be arranged against that same club — its own eleven would meet its own squad.
    if sheet_team.world_team_id and sheet_team.world_team_id == world.id:
        raise ClubRefusal(
            "opponent_is_own_club",
            f"{sheet_team.name} is placed in the world's ladder as {world.name}, and the model plays no side against itself",
            team=sheet_team.name,
            world_team=world.slug,
        )
    clash = session.scalar(
        select(func.count())
        .select_from(ClubFixture)
        .where(ClubFixture.organization_id == organization.id, ClubFixture.team_id == sheet_team.id, ClubFixture.scheduled_on == day, ClubFixture.side == str(side))
    )
    if clash:
        raise ClubRefusal(
            "side_taken", f"{sheet_team.name} is already at {side} on {day}; the other side of a tie, or the next date, is a different fixture", team=sheet_team.name, scheduled_on=day, side=str(side)
        )
    players = _selection(session, organization, sheet_team, named, gate_minors=True)
    row = ClubFixture(
        id=new_public_id("cfx"),
        organization_id=organization.id,
        team_id=sheet_team.id,
        opponent_team_id=world.id,
        opponent_name=world.name,
        side=str(side),
        competition=_clip(competition, COMPETITION_MAX, label="a competition name"),
        scheduled_on=day,
        status="scheduled",
        named=[person.id for person in players],
        note=_clip(note, NOTE_MAX, label="a fixture note"),
    )
    session.add(row)
    session.commit()
    return {
        "fixture": fixture_view(session, row),
        "fixtures": held + 1,
        "limit": MAX_FIXTURES_PER_ORGANIZATION,
        "fielding": _can_field(players),
        "rule": "an arrangement stores the promise and nothing else: the scoreline, the timeline and the ratings belong to the engine's own row and appear when the fixture is played",
        "demo_data": False,
    }


def list_fixtures(session: Session, user: User, ident: str, *, team: str | None = None, status: str | None = None, since: str | None = None) -> dict[str, Any]:
    """The tenant's calendar, newest first, with the figures on it counted from the rows it names."""
    organization, member = require(session, user, ident, "match.read")
    rows = _fixtures_of(session, organization)
    if team:
        wanted = resolve_team(session, organization, team)
        rows = [row for row in rows if row.team_id == wanted.id]
    if status:
        rows = [row for row in rows if row.status == str(status)]
    if since:
        start = _iso(since, label="a since date")
        rows = [row for row in rows if row.scheduled_on >= start]
    played = [row for row in rows if row.status == "played"]
    competitions: dict[str, int] = {}
    for row in rows:
        key = row.competition or "uncupplied"
        competitions[key] = competitions.get(key, 0) + 1
    return {
        "organization": organization.slug,
        "items": [fixture_view(session, row) for row in rows],
        "total": len(rows),
        "played": len(played),
        "unplayed": len(rows) - len(played),
        "appearances": sum(int(session.scalar(select(func.count()).select_from(ClubMatchAppearance).where(ClubMatchAppearance.fixture_id == row.id)) or 0) for row in rows),
        "by_competition": competitions,
        "fixtures_held": len(_fixtures_of(session, organization)),
        "limit": MAX_FIXTURES_PER_ORGANIZATION,
        "role": member.role,
        "read_through": "match.read",
        "today": _today().isoformat(),
        "formulas": dict(FORMULAS),
        "rule": "every figure here is counted from the rows on this page, and none of them is stored — a listing and a read cannot disagree because neither of them adds anything up twice",
        "demo_data": False,
    }


def fixture_detail(session: Session, user: User, ident: str, fixture_ident: str) -> dict[str, Any]:
    """One fixture, and — when it has been played — the engine's own numbers read through its row."""
    organization, member = require(session, user, ident, "match.read")
    row = _fixture(session, organization, fixture_ident)
    view = fixture_view(session, row)
    match = session.get(SimulationMatch, row.match_id) if row.match_id else None
    answer: dict[str, Any] = {
        "fixture": view,
        "role": member.role,
        "formulas": dict(FORMULAS),
        "fielding": _can_field([person for person in (session.get(RealPlayer, pid) for pid in list(row.named or [])) if person is not None]),
        "demo_data": False,
    }
    if match is not None:
        # Every number under `report` is the engine's, printed from the row it wrote: this tier reads it and
        # stores none of it, so a corrected model version cannot leave a stale scoreline behind.
        answer["report"] = {
            "slug": match.slug,
            "digest": match.digest,
            "model_version": match.model_version,
            "seed": int(match.seed),
            "minutes": int(match.minutes),
            # The engine publishes its own score under `score`: two goal counts and the winner's side, name and
            # team id. Naming it `scoreline` here would be a second word for a figure the sim tier already
            # publishes, and a page reading one door's key would find null behind the other's.
            "score": match.report.get("score"),
            "sides": match.report.get("sides"),
            "path": f"/simulations/{match.slug}",
        }
        answer["report_rule"] = "the score and the per-side blocks are the stored report of the match this fixture points at, read back from `sim_matches` on this request; the club tier holds no copy"
    return answer


def play_fixture(session: Session, user: User, ident: str, fixture_ident: str, *, seed: int | None = None, minutes: int = DEFAULT_MINUTES) -> dict[str, Any]:
    """Play one fixture through the engine, and record the eleven that played it.

    The overlay is the whole trick: the tenant's sheet is added and the bound world club's own squad removed, so
    `team_profile` selects from the players this tenant holds while the engine keeps its single entry point. The
    stored report's own names are then checked against that selection before a single appearance row is written.
    """
    organization, _ = require(session, user, ident, "match.write")
    row = _fixture(session, organization, fixture_ident)
    if row.status == "played":
        raise ClubRefusal(
            "fixture_played",
            "this fixture was already played, and the answer it gave stands; re-playing it would be a second result for one date",
            fixture=row.id,
            match_slug=row.match_slug,
            digest=row.digest,
        )
    team = session.get(ClubTeam, row.team_id)
    if team is None or not team.world_team_id:
        raise ClubRefusal(
            "no_world_side",
            f"{(team.name if team else 'this team')} is not placed in the world's ladder, so the engine has no side to line it up",
            fixture=row.id,
            team=(team.name if team else str(row.team_id)),
        )
    if not row.opponent_team_id:
        raise ClubRefusal("no_opponent_side", "the club this fixture was arranged against is no longer in the world, so nothing can be played against it", fixture=row.id, opponent=row.opponent_name)
    block = int(minutes)
    if block not in MINUTES_CHOICES:
        raise ClubRefusal(
            "minutes_choice",
            f"a fixture is played over one of the engine's own block lengths {list(MINUTES_CHOICES)} minutes; {block} is not one of them",
            minutes=block,
            choices=list(MINUTES_CHOICES),
        )
    players = _selection(session, organization, team, row.named, gate_minors=True)
    fielding = _can_field(players)
    if not fielding["ok"]:
        raise ClubRefusal(
            "can_not_field",
            f"a side needs {fielding['needs_players']} names and {fielding['needs_keepers']} of them a goalkeeper; this fixture has {fielding['players']} and {fielding['keepers']}",
            **fielding,
        )

    base_ids = frozenset(str(pid) for pid in session.scalars(select(RealPlayer.id).where(RealPlayer.team_id == team.world_team_id)))
    overlay = SquadOverlay(added=tuple(players), removed=base_ids, label=f"{team.name} — the tenant's own sheet")
    profile = team_profile(session, team.world_team_id, squad=overlay)
    match = run_simulation(
        session,
        owner_id=user.id,
        home_team_id=(team.world_team_id if row.side == "home" else row.opponent_team_id),
        away_team_id=(row.opponent_team_id if row.side == "home" else team.world_team_id),
        home_squad=(overlay if row.side == "home" else None),
        away_squad=(None if row.side == "home" else overlay),
        seed=seed,
        minutes=block,
    )
    recorded = [str(entry.get("player", "")) for entry in list(match.report.get("sides", {}).get(row.side, {}).get("lineup", [])) if isinstance(entry, dict)]
    selected = [name for _pid, _slug, name, _position, _band in profile.selected]
    written = 0
    reason = ""
    if recorded and recorded == selected:
        # `career._trace_round` writes when `recorded` is empty as well, because a match stored before lineups
        # were written must still carry its load. This tier is newer than that backlog and has no rows to
        # rescue, so an empty lineup is treated as a disagreement rather than as permission.
        for player_id, slug, name, position, band in profile.selected:
            session.add(
                ClubMatchAppearance(
                    id=new_public_id("cma"),
                    organization_id=organization.id,
                    fixture_id=row.id,
                    player_id=player_id,
                    player_slug=slug,
                    player_name=name,
                    position=position,
                    band=band,
                    side=row.side,
                    minutes=block,
                    note=f"selected by the engine from this tenant's sheet and played the fixture's full {block} minutes as modelled",
                )
            )
        written = len(profile.selected)
    else:
        # The result stands — the engine's row is the truth about the match — but the appearance rows do not, and
        # the answer says so. §20 already refused to attribute a load to players who may not have played it.
        reason = "the eleven this tenant's rows select does not match the eleven the stored report names, so no appearance was recorded"
    row.status = "played"
    row.match_id = match.id
    row.match_slug = match.slug
    row.digest = match.digest
    row.model_version = match.model_version
    session.commit()
    answer: dict[str, Any] = {
        "fixture": fixture_view(session, row),
        "match_slug": match.slug,
        "digest": match.digest,
        "model_version": match.model_version,
        "seed": int(match.seed),
        "appearances_written": written,
        "fielding": fielding,
        "score": match.report.get("score"),
        "formulas": {"score": "the engine's own stored report, read from `sim_matches` — this tier keeps a pointer and a digest, never the goals", "appearances": FORMULAS["appearances"]},
        "rule": "a fixture is played once: the result is the engine's row, the eleven is this tenant's sheet, and the numbers are read back rather than copied",
        "demo_data": False,
    }
    if reason:
        answer["appearances_refused"] = reason
    return answer


def delete_fixture(session: Session, user: User, ident: str, fixture_ident: str) -> dict[str, Any]:
    """Erase one arrangement. The engine's match row and the players it named both outlive it."""
    organization, _ = require(session, user, ident, "match.erase")
    row = _fixture(session, organization, fixture_ident)
    held = len(_fixtures_of(session, organization))
    played = row.match_slug
    session.delete(row)
    session.commit()
    return {
        "deleted": True,
        "id": fixture_ident,
        "fixtures": held - 1,
        "match_kept": played,
        "rule": "the tenant's record of the fixture is gone with its appearance rows, and the match the engine played stays in its own table for whoever it was played for",
        "demo_data": False,
    }


__all__ = [
    "CAPS",
    "CONFLICT_CODES",
    "DEFAULT_MINUTES",
    "FORBIDDEN_CODES",
    "FORMULAS",
    "LIMITATION",
    "MAX_FIXTURES_PER_ORGANIZATION",
    "NAMED_MAX",
    "NOT_FOUND_CODES",
    "PUBLISHED",
    "REFUSALS",
    "SIDES",
    "UNPROCESSABLE_CODES",
    "club_fixture_ready",
    "create_fixture",
    "delete_fixture",
    "fixture_counts",
    "fixture_detail",
    "fixture_view",
    "list_fixtures",
    "play_fixture",
]
