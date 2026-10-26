"""Career Mode (spec §20): a season played through the M6 engine, judged by stated objectives.

Three rules keep this honest in the same way the single-match layer is honest.

1. **Nothing invented twice.** A round is decided by `run_simulation`, so the only match model in the
   product plays career fixtures too; the career row stores the inputs and the outcome of each round,
   not a second set of numbers the engine could contradict.
2. **Aggregates are summed, not stored.** The record, the mini-table and every objective verdict are
   computed from `career_fixtures` on the request, each with the formula that produced it. `points` and
   `outcome` on a fixture are copies of what the linked match said — kept so a career still reads after
   its report is deleted — and `_consistency` re-checks them against the live match when it exists.
3. **The fixture list is a rotation, not a shuffle.** Opponents are the clubs of the career's own
   competition ordered by slug, taken in turn, with home and away alternating per cycle. A reader can
   reproduce round 7 without a random number, which is the point of calling it fictional.

The philosophy is *stated intent*: it shapes what the page says the manager asked for, and the engine
reads the tactical system rather than the word. The budget is not stated intent any more — §22's
market spends it, a fee is a row, and a signed player changes the eleven that gets selected, so
`play_round` composes the squad from the club's stored rows plus this career's own moves as of the
round being played. `limitations()` says which of these claims the build can actually support.
"""

from __future__ import annotations

import hashlib
from typing import Any, Final

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import OBJECTIVE_FORMULA, Career, CareerAppearance, CareerFixture, Competition, RealPlayer, SimulationMatch, Team
from app.services.simulation.carry_over import carry_over_view, record_appearances, training_loads
from app.services.simulation.development import DEVELOPMENT_RATE, DEVELOPMENT_TAU, TRAINING_MINUTES_PER_UNIT, development_summary
from app.services.simulation.ledger import ledger_view
from app.services.simulation.profile import SquadOverlay, team_profile
from app.services.simulation.service import run_simulation
from app.services.simulation.squad import squad_as_of
from app.services.world.names import slugify

SEED_SPACE: Final = 2_147_483_647
POINTS_FOR: Final = {"W": 3, "D": 1, "L": 0}
CAREER_DISCLAIMER: Final = (
    "A career is a fiction this platform plays with itself: the club is a generated club, every fixture is "
    "decided by the labelled simulation engine, and no result here reports a real match, a real competition "
    "or a real season."
)

#: The development curve the `development` block projects, in the same published-formula discipline as the
#: carry-over condition. `τ`, `rate` and the training conversion are the authored constants in `development`;
#: the expression is spelled out here so the page prints it beside the numbers, and the two stay in lockstep
#: by import.
DEVELOPMENT_FORMULA: Final = (
    "developed(value, potential, minutes) = value + (potential − value)·(1 − e^(−minutes/τ))·rate, "
    f"τ = {DEVELOPMENT_TAU:g} minutes, rate = {DEVELOPMENT_RATE:g}; effective_minutes = match_minutes "
    f"+ {TRAINING_MINUTES_PER_UNIT:g}·training_load_units (the world's sessions for the player); each "
    "attribute climbs toward the player's stored potential from his stored (or floored) value and saturates "
    "so it never crosses potential — recomputed from the rows on every read, never written back"
)


class WindowClosed(RuntimeError):
    """A challenge run has used every round its scenario allowed.

    Its own error rather than a bare `ValueError`, because the two answer differently on the wire: a
    career that cannot play has a bad request behind it (409 `cannot_play`), while a closed window is
    the scenario doing its job and answers 409 `window_closed` with the numbers that closed it.
    """

    #: §51's rule made visible on the class: the one code this error answers with, registered in
    #: `answers.ANSWERS` by the market and transfer-sim tiers, so a router reads the status from the
    #: table rather than spelling it beside the raise.
    code: Final = "window_closed"

    def __init__(self, *, played: int, window: int, challenge_slug: str) -> None:
        super().__init__(f"this challenge's window closed after {played} of {window} rounds")
        self.played = played
        self.window = window
        self.challenge_slug = challenge_slug

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "challenge_slug": self.challenge_slug,
            "rounds_played": self.played,
            "window_rounds": self.window,
        }


def limitations() -> dict[str, str]:
    """What this layer does not claim, in the words the page prints."""
    return {
        "budget": (
            "The budget is spent, not stated: every fee a career paid or received is a row in "
            "career_squad_moves, and the balance is that sum against the figure on the career row. Read "
            "/api/v1/transfers/{career} for the arithmetic and the formula it prints. What the budget does "
            "not do is constrain the fixtures by itself — only a deal that was actually made changes the squad."
        ),
        "wages": (
            "A deal's weekly wage is now charged: each round the engine plays writes one "
            "career_wage_charges row whose fee is the sum of the wages of the deals this career holds at "
            "the start of that round, and the balance drops by it. What is not charged is the club's own "
            "stored squad — those players came with the job. And nothing follows a missed payment: there is "
            "no default, no board reaction and no transfer embargo, only a balance that goes negative and "
            "stops the market spending from it."
        ),
        "carry_over": (
            "A played round now carries into the next one. Every player the engine selected is traced in "
            "career_appearances at the fixture's full length, and the round after it reads a condition figure off "
            "those rows plus the world's training sessions for each player; that condition weights the eleven's "
            "form index, which is the number the engine's fatigue term already reads. What does not change is a "
            "player's *stored* attributes: those same fixture minutes are projected into a development curve in the "
            "separate `development` block, but that block is read-only — recomputed from the rows on every read and "
            "never written back — so the squad the rest of the page reads keeps the attributes the world gave it. "
            "Nothing rests a tired player, and a club nobody manages has no trace, so its side is measured off its "
            "rows exactly as it always was."
        ),
        "projections": (
            "The `development`, `affordability`, `contracts`, `board`, `head_to_head` and `next_fixture_brief` blocks "
            "are read-only projections recomputed from this career's own rows on every read: fixture minutes and "
            "training projected toward potential, a wage runway and a signing preview, a deal book whose projected "
            "expiry nothing enforces, a season pace projection against the objectives, this career's record against "
            "one opponent, and the engine's own band measurements of the next fixture's two sides. None of them "
            "writes a stored attribute, expires or renews a contract, triggers a board decision or keeps a counter — "
            "each is what the rows imply, printed beside the formula that produced it."
        ),
        "ledger": (
            "The season ledger sums this career's own `sim_events` rows: goals, attempts, cards and injuries per "
            "player, each event credited to the side that printed it. Two things keep it honest and one keeps it "
            "short. It is recomputed from the rows on every read, never stored as a counter; it prints its goal "
            "total beside the fixture list's own `club_goals` for the same matches and names both when they disagree; "
            "and a match simulated before the events table has no rows, so its fixture is reported as untraced "
            "rather than as a scoreless appearance. What the ledger does not do is rank players across clubs or "
            "compare a season against a league table, and it cannot credit a save to a goalkeeper: every chance "
            "event names the player who took the shot, not the one who stopped it."
        ),
        "scouting": (
            "The market offers the best-rated players in each band with this club's weakest band filled first. It is a "
            "rule over stored rows, not a scout's opinion, and it does not search for a player matching a description "
            "— that is the AI Scout (spec §23) and it is not built."
        ),
        "philosophy": (
            "The philosophy is recorded and shown beside the tactical system the manager chose. The engine reads the "
            "system, not the label — a possession career and a counter-attack career differ because of the board, "
            "not because of the word."
        ),
        "table": (
            "The table is built from the fixtures this career played and no others. It is not the competition's "
            "league table, which lives in /world/competitions and comes from the generated world's own results."
        ),
        "objectives": "Objectives are compared with the sums of this career's own rows. No promotion, relegation or prize follows.",
    }


def _digest_seed(career_id: str, round_index: int) -> int:
    """A round's seed: reproducible from the career and the round number alone."""
    digest = hashlib.blake2b(f"{career_id}:{round_index}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") % SEED_SPACE


def resolve_club(session: Session, ident: str) -> Team:
    club = session.scalar(select(Team).where(or_(Team.id == ident, Team.slug == ident)))
    if club is None:
        raise ValueError(f"no such club in the generated world: {ident}")
    return club


def competition_clubs(session: Session, competition_id: str | None, *, exclude_id: str) -> list[Team]:
    if competition_id is None:
        return []
    return list(session.scalars(select(Team).where(Team.competition_id == competition_id, Team.id != exclude_id).order_by(Team.slug)).all())


def next_fixture_plan(session: Session, career: Career, *, round_index: int | None = None) -> dict[str, Any]:
    """Which club is next, on which side, and where it is played.

    `round_index` lets a caller ask about a round it has not reached yet — the rotation is a pure function of
    the round number, so §M7's transfer simulation can look at the next three fixtures without pretending a
    round has been played. Left out, it is the round after the last one this career actually played, which is
    what every caller here has always meant.
    """
    round_index = career.rounds_played + 1 if round_index is None else max(1, int(round_index))
    opponents = competition_clubs(session, career.competition_id, exclude_id=career.club_id or "")
    if not opponents:
        return {"available": False, "reason": "the career's club has no competition to rotate through", "round_index": round_index}
    cycle, position = divmod(round_index - 1, len(opponents))
    opponent = opponents[position]
    home = cycle % 2 == 0
    venue_club = career.club_name if home else opponent.name
    stadium = session.scalar(select(Team.stadium).where(Team.id == (career.club_id if home else opponent.id)))
    return {
        "available": True,
        "round_index": round_index,
        "side": "home" if home else "away",
        "opponent_team_id": opponent.id,
        "opponent_name": opponent.name,
        "opponent_short": opponent.short_name,
        "venue_name": stadium or "",
        "venue_club": venue_club,
        "cycle": cycle + 1,
        "of": len(opponents),
        "rotation": f"opponents ordered by slug, position {position + 1} of {len(opponents)} in cycle {cycle + 1}; a career plays every club at home in its first cycle and away in its second",
        "seed": _digest_seed(career.id, round_index),
    }


def create_career(
    session: Session,
    *,
    owner_id: str,
    club: Team,
    manager_name: str,
    philosophy: str,
    system_slug: str,
    budget: int,
    objectives: list[dict[str, Any]],
    season: str,
) -> Career:
    """Open a career. The club's competition is copied from the world row, never asked for.

    The two names are read with their own selects rather than through a lazy relationship, so a
    detached or freshly loaded club row works the same way and the career keeps the name it was
    opened with even after the world is regenerated.
    """
    slug = slugify(f"{manager_name}-{club.short_name or club.name}")[:70]
    if session.scalar(select(Career.id).where(Career.slug == slug)):
        slug = f"{slug}-{new_public_id('c')[-4:]}"[:80]
    career = Career(
        id=new_public_id("car"),
        slug=slug,
        owner_id=owner_id,
        manager_name=manager_name,
        club_id=club.id,
        club_name=club.name,
        club_short=club.short_name,
        competition_id=club.competition_id,
        competition_name=session.scalar(select(Competition.name).where(Competition.id == club.competition_id)) or "",
        season=season,
        philosophy=philosophy,
        system_slug=system_slug,
        budget=budget,
        objectives=objectives,
        status="active",
    )
    session.add(career)
    session.commit()
    session.refresh(career)
    return career


def _trace_round(
    session: Session,
    career: Career,
    *,
    round_index: int,
    match: SimulationMatch,
    overlay: SquadOverlay | None,
    opponent_name: str,
) -> None:
    """Write one appearance row per player this round selected (spec §20).

    The eleven is rebuilt from the same rows the engine played with — the club's squad, the career's
    moves as of this round, the system that staffed the formation — and then checked against the names
    in the stored report. If the two disagree the round is left untraced rather than recorded: a load
    attributed to players who may not have played it would corrupt every round after it. `carry_over`
    reports a played round with no rows as the defect it is, so refusing here cannot go unnoticed.
    """
    side = "home" if match.home_team_id == career.club_id else "away"
    profile = team_profile(session, career.club_id or "", system_slug=career.system_slug or None, squad=overlay)
    recorded = [str(row.get("player", "")) for row in list(match.report.get("sides", {}).get(side, {}).get("lineup", [])) if isinstance(row, dict)]
    selected = [name for _player_id, _slug, name, _position, _band in profile.selected]
    if recorded and recorded != selected:
        return
    record_appearances(
        session,
        career,
        round_index=round_index,
        lineup=list(profile.selected),
        side=side,
        minutes=int(match.minutes),
        opponent_name=opponent_name,
    )


def play_round(session: Session, career: Career) -> tuple[CareerFixture, SimulationMatch]:
    """Play the next round through the engine and record it against the career.

    A career opened from a live challenge (spec §21) carries a round window, and this is the only path
    that can play a round — so the window is enforced here rather than by a rule each caller is
    trusted to remember. An open career stores a window of 0 and is never limited.
    """
    if career.status != "active":
        raise ValueError("this career is retired; open a new one to keep playing")
    window = int(career.challenge_window or 0)
    if window and int(career.rounds_played) >= window:
        raise WindowClosed(played=int(career.rounds_played), window=window, challenge_slug=career.challenge_slug)
    plan = next_fixture_plan(session, career)
    if not plan["available"]:
        raise ValueError(str(plan["reason"]))
    home_id, away_id = (career.club_id or "", plan["opponent_team_id"]) if plan["side"] == "home" else (plan["opponent_team_id"], career.club_id or "")
    # The squad this career has at the start of this round — the club's stored rows with every transfer
    # made before it applied (spec §22). `None` until the market is used, which keeps a career that has
    # not bought anyone playing exactly the club the world generated.
    overlay = squad_as_of(session, career, int(plan["round_index"]))
    match = run_simulation(
        session,
        owner_id=career.owner_id,
        home_team_id=home_id,
        away_team_id=away_id,
        home_system=(career.system_slug or None) if plan["side"] == "home" else None,
        away_system=None if plan["side"] == "home" else (career.system_slug or None),
        seed=int(plan["seed"]),
        minutes=90,
        home_squad=overlay if home_id == (career.club_id or "") else None,
        away_squad=overlay if away_id == (career.club_id or "") else None,
    )
    club_goals = match.home_goals if plan["side"] == "home" else match.away_goals
    opponent_goals = match.away_goals if plan["side"] == "home" else match.home_goals
    outcome = "W" if club_goals > opponent_goals else "L" if club_goals < opponent_goals else "D"
    fixture = CareerFixture(
        id=new_public_id("cf"),
        career_id=career.id,
        round_index=int(plan["round_index"]),
        match_id=match.id,
        match_slug=match.slug,
        digest=match.digest,
        model_version=match.model_version,
        seed=match.seed,
        side=plan["side"],
        opponent_team_id=plan["opponent_team_id"],
        opponent_name=plan["opponent_name"],
        opponent_short=plan["opponent_short"],
        venue_name=plan["venue_name"],
        club_goals=club_goals,
        opponent_goals=opponent_goals,
        outcome=outcome,
        points=POINTS_FOR[outcome],
    )
    career.rounds_played = int(plan["round_index"])
    session.add(fixture)
    session.commit()
    session.refresh(fixture)
    session.refresh(career)
    # The round is played, so it leaves a trace: who was selected, at how many minutes (spec §20). This
    # is what the next round's condition is read from, and what makes a career's ninth fixture differ
    # from its first when nothing else about the squad changed.
    _trace_round(
        session,
        career,
        round_index=int(plan["round_index"]),
        match=match,
        overlay=overlay,
        opponent_name=str(plan["opponent_name"]),
    )
    # The round is played, so the deals held for it are paid for (spec §22). A local import because
    # `market` reaches through `challenges`, which imports this module — the cycle is the layering, not
    # an accident: a challenge is a career, and a career's money is the market's business.
    from app.services.simulation.market import pay_wages

    pay_wages(session, career, round_index=int(plan["round_index"]))
    return fixture, match


def fixtures_of(session: Session, career: Career) -> list[CareerFixture]:
    return list(session.scalars(select(CareerFixture).where(CareerFixture.career_id == career.id).order_by(CareerFixture.round_index)).all())


def _longest_unbeaten(rows: list[CareerFixture]) -> int:
    best = run = 0
    for row in rows:
        run = run + 1 if row.outcome in ("W", "D") else 0
        best = max(best, run)
    return best


def record_of(rows: list[CareerFixture]) -> dict[str, Any]:
    """The career's own record, summed from its rows."""
    won = sum(1 for row in rows if row.outcome == "W")
    drawn = sum(1 for row in rows if row.outcome == "D")
    lost = sum(1 for row in rows if row.outcome == "L")
    scored = sum(row.club_goals for row in rows)
    conceded = sum(row.opponent_goals for row in rows)
    points = sum(row.points for row in rows)
    return {
        "played": len(rows),
        "won": won,
        "drawn": drawn,
        "lost": lost,
        "goals_for": scored,
        "goals_against": conceded,
        "goal_difference": scored - conceded,
        "points": points,
        "points_formula": "sum(career_fixtures.points), win 3 / draw 1 / loss 0",
        "goal_difference_formula": "sum(club_goals) - sum(opponent_goals)",
        "unbeaten_run": _longest_unbeaten(rows),
        "form": [row.outcome for row in rows][-5:],
    }


def _blank_club(club_id: str | None, name: str, short: str) -> dict[str, Any]:
    """A row of the mini-table before any fixture has touched it, so an empty career still has a club in it."""
    return {"club_id": club_id, "name": name, "short_name": short, "played": 0, "goals_for": 0, "goals_against": 0, "points": 0}


def mini_table(rows: list[CareerFixture], career: Career) -> list[dict[str, Any]]:
    """A table over the clubs this career has met, from this career's fixtures only."""
    clubs: dict[str, dict[str, Any]] = {career.club_id or "": _blank_club(career.club_id, career.club_name, career.club_short)}
    for row in rows:
        for key, name, short, scored, against, points in (
            (career.club_id or "", career.club_name, career.club_short, row.club_goals, row.opponent_goals, row.points),
            (row.opponent_team_id or "", row.opponent_name, row.opponent_short, row.opponent_goals, row.club_goals, POINTS_FOR[{"W": "L", "L": "W", "D": "D"}[row.outcome]]),
        ):
            entry = clubs.setdefault(key, _blank_club(key, name, short))
            entry["played"] = entry.get("played", 0) + 1
            entry["goals_for"] = entry.get("goals_for", 0) + scored
            entry["goals_against"] = entry.get("goals_against", 0) + against
            entry["points"] = entry.get("points", 0) + points
    table = list(clubs.values())
    for entry in table:
        gf, ga = entry["goals_for"], entry["goals_against"]
        entry["goal_difference"] = gf - ga
        entry["is_career_club"] = entry["club_id"] == (career.club_id or "")
    table.sort(key=lambda entry: (-entry["points"], -entry["goal_difference"], -entry["goals_for"], str(entry["name"])))
    for position, entry in enumerate(table, start=1):
        entry["position"] = position
    return table


HEAD_TO_HEAD_FORMULA: Final = (
    "played/won/drawn/lost and goals are sums over career_fixtures where opponent_team_id = this opponent; "
    "points are 3 per win, 1 per draw, 0 per loss"
)


def head_to_head(session: Session, career: Career, opponent_team_id: str | None) -> dict[str, Any]:
    """This career's own record against one opponent, summed from its fixtures and nothing else.

    A page that showed the opponent's record against everyone, or this career's record against all
    opponents, would be answering a different question. This answers the one a manager asks before a
    fixture: how have *we* done against *them*.
    """
    if not opponent_team_id:
        return {
            "available": False,
            "reason": "there is no next opponent to compare against",
            "formula": HEAD_TO_HEAD_FORMULA,
            "data_origin": "simulation",
            "is_demo_data": True,
        }
    rows = [row for row in fixtures_of(session, career) if row.opponent_team_id == opponent_team_id]
    if not rows:
        return {
            "available": True,
            "opponent_team_id": opponent_team_id,
            "opponent_name": "",
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_difference": 0,
            "points": 0,
            "meetings": [],
            "formula": HEAD_TO_HEAD_FORMULA,
            "note": "this career has not met this opponent yet",
            "data_origin": "simulation",
            "is_demo_data": True,
        }
    won = sum(1 for row in rows if row.outcome == "W")
    drawn = sum(1 for row in rows if row.outcome == "D")
    lost = sum(1 for row in rows if row.outcome == "L")
    scored = sum(int(row.club_goals) for row in rows)
    conceded = sum(int(row.opponent_goals) for row in rows)
    return {
        "available": True,
        "opponent_team_id": opponent_team_id,
        "opponent_name": rows[0].opponent_name,
        "played": len(rows),
        "won": won,
        "drawn": drawn,
        "lost": lost,
        "goals_for": scored,
        "goals_against": conceded,
        "goal_difference": scored - conceded,
        "points": sum(int(row.points) for row in rows),
        "meetings": [
            {
                "round_index": row.round_index,
                "side": row.side,
                "club_goals": row.club_goals,
                "opponent_goals": row.opponent_goals,
                "outcome": row.outcome,
            }
            for row in rows[-5:]
        ],
        "formula": HEAD_TO_HEAD_FORMULA,
        "note": "only this career's own fixtures; it is not the opponent's record against anyone else",
        "data_origin": "simulation",
        "is_demo_data": True,
    }


NEXT_FIXTURE_FORMULA: Final = (
    "bands are the engine's own band indices ((mean of the band's attributes − 28) ÷ 68) measured on the same rows "
    "the fixture will be played from; delta = career band − opponent band, so a positive delta is this career's side "
    "stronger in that band"
)


def next_fixture_brief(session: Session, career: Career, *, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    """The next fixture's two sides as the engine measures them, side by side.

    Both profiles come from `team_profile` — the career's with its transfer overlay and chosen system, the
    opponent's from its stored rows — so the comparison is the engine's own measurement of the eleven it
    will play, not a second estimate. It is a comparison, not a forecast: no scoreline is predicted.
    """
    plan = plan or next_fixture_plan(session, career)
    if not plan.get("available"):
        return {"available": False, "reason": str(plan.get("reason", "no next fixture")), "data_origin": "simulation", "is_demo_data": True}
    overlay = squad_as_of(session, career, int(plan["round_index"]))
    try:
        mine = team_profile(session, career.club_id or "", system_slug=career.system_slug or None, squad=overlay)
        theirs = team_profile(session, str(plan["opponent_team_id"]))
    except LookupError as error:
        return {"available": False, "reason": str(error), "data_origin": "simulation", "is_demo_data": True}
    bands = ("attack", "midfield", "defence", "keeper", "press")
    mine_bands = {band: round(float(getattr(mine, band)), 3) for band in bands}
    theirs_bands = {band: round(float(getattr(theirs, band)), 3) for band in bands}
    delta = {band: round(mine_bands[band] - theirs_bands[band], 3) for band in bands}
    return {
        "available": True,
        "round_index": int(plan["round_index"]),
        "side": plan["side"],
        "opponent_name": plan["opponent_name"],
        "venue_name": plan["venue_name"],
        "career": {
            "team_id": mine.team_id,
            "name": mine.name,
            "formation": mine.formation,
            "system_slug": mine.system_slug,
            "bands": mine_bands,
            "overall": round(float(mine.overall), 3),
            "form": round(float(mine.form), 3),
        },
        "opponent": {
            "team_id": theirs.team_id,
            "name": theirs.name,
            "formation": theirs.formation,
            "system_slug": theirs.system_slug,
            "bands": theirs_bands,
            "overall": round(float(theirs.overall), 3),
            "form": round(float(theirs.form), 3),
        },
        "delta": delta,
        "stronger_bands": [band for band in bands if delta[band] > 0],
        "weaker_bands": [band for band in bands if delta[band] < 0],
        "formula": NEXT_FIXTURE_FORMULA,
        "note": "the engine's own measurement of the same rows it will play; a comparison, not a forecast",
        "data_origin": "simulation",
        "is_demo_data": True,
    }


def objectives_of(career: Career, record: dict[str, Any]) -> list[dict[str, Any]]:
    actual_by_kind = {
        "wins": record["won"],
        "points": record["points"],
        "goal_difference": record["goal_difference"],
        "unbeaten": record["unbeaten_run"],
    }
    report: list[dict[str, Any]] = []
    for objective in career.objectives or []:
        kind = str(objective.get("kind", ""))
        target = int(objective.get("target", 0))
        actual = int(actual_by_kind.get(kind, 0))
        report.append(
            {
                "kind": kind,
                "label": str(objective.get("label") or kind),
                "target": target,
                "actual": actual,
                "met": actual >= target,
                "formula": OBJECTIVE_FORMULA.get(kind, "not a recognised objective kind"),
            }
        )
    return report


#: The season projection's arithmetic, published beside the numbers so a reader can reproduce it.
BOARD_FORMULA: Final = (
    "projected = round(actual ÷ played × season_rounds), where season_rounds is the challenge's window when it has "
    "one, else a double round-robin over the competition's clubs (2 × clubs); only additive objectives (wins, "
    "points, goal difference) are projected — an unbeaten run is a streak, not a sum, so it is reported as it stands"
)


def season_horizon(session: Session, career: Career) -> dict[str, Any]:
    """How many rounds a full season is for this career, and where that number comes from.

    A challenge career carries its own round window; an open career's competition is the horizon, and the
    career's fixture list rotates through its clubs home and away, so a full season is a double round-robin
    over them. With no competition the horizon is 0 and nothing is projected rather than guessed at.
    """
    window = int(career.challenge_window or 0)
    if window > 0:
        return {"rounds": window, "source": "the challenge's own round window"}
    opponents = competition_clubs(session, career.competition_id, exclude_id=career.club_id or "")
    return {"rounds": 2 * len(opponents), "source": "a double round-robin over the competition's clubs (home and away)"}


def board_view(session: Session, career: Career, rows: list[CareerFixture], record: dict[str, Any]) -> dict[str, Any]:
    """Where the season is heading at the current pace, and whether the board's targets are on track.

    A linear projection over the career's own played rounds, never a stored figure: the board reads the same
    sums the record prints, so it cannot drift from them. Only additive objectives are projected; an unbeaten
    run is a streak, not a sum, so it is reported as it stands rather than extrapolated.
    """
    horizon = season_horizon(session, career)
    rounds = int(horizon["rounds"])
    played = int(record["played"])
    additive = {"wins": int(record["won"]), "points": int(record["points"]), "goal_difference": int(record["goal_difference"])}
    projected = {kind: round(value / played * rounds) for kind, value in additive.items()} if played > 0 and rounds > 0 else {}
    verdicts: list[dict[str, Any]] = []
    for verdict in objectives_of(career, record):
        kind = str(verdict["kind"])
        projected_actual = projected.get(kind)
        verdicts.append(
            {
                **verdict,
                "projected": projected_actual,
                "on_pace": None if projected_actual is None else projected_actual >= int(verdict["target"]),
            }
        )
    trackable = [item["on_pace"] for item in verdicts if item["on_pace"] is not None]
    return {
        "season_rounds": rounds,
        "season_source": horizon["source"],
        "played": played,
        "points_per_round": round(int(record["points"]) / played, 3) if played else None,
        "goals_for_per_round": round(int(record["goals_for"]) / played, 3) if played else None,
        "projected": projected,
        "objectives": verdicts,
        "on_track": all(trackable) if trackable else None,
        "formula": BOARD_FORMULA,
        "note": (
            "a linear pace projection over the rounds played so far, not a forecast: the board reads the same sums "
            "the record prints, and an objective with no additive projection is reported as it stands"
        ),
        "data_origin": "simulation",
        "is_demo_data": True,
    }


def _consistency(session: Session, rows: list[CareerFixture]) -> str:
    """Re-read each fixture's linked match and confirm the copied score still agrees."""
    if not rows:
        return "no fixture has been played, so there is nothing to re-check yet"
    missing = 0
    checked = 0
    mismatched: list[str] = []
    for row in rows:
        match = session.get(SimulationMatch, row.match_id) if row.match_id else None
        if match is None:
            missing += 1
            continue
        home, away = (row.club_goals, row.opponent_goals) if row.side == "home" else (row.opponent_goals, row.club_goals)
        checked += 1
        if (home, away) != (match.home_goals, match.away_goals):
            mismatched.append(row.match_slug)
    if mismatched:
        return f"{len(mismatched)} of {checked} re-checked fixtures disagree with their match report: {', '.join(mismatched[:3])}"
    if missing:
        return f"{checked} of {len(rows)} fixtures re-checked against their stored match report; {missing} point at a report that is no longer stored"
    return f"{checked} of {len(rows)} fixtures re-checked against their stored match report; all agree"


def _affordability(session: Session, career: Career) -> dict[str, Any]:
    """The finance standing, read through a local import: `market` reaches `challenges`, which imports this module."""
    from app.services.simulation.market import affordability_view

    return affordability_view(session, career)


def _contracts(session: Session, career: Career) -> dict[str, Any]:
    """The deal book, read through the same local import for the same cycle reason as `_affordability`."""
    from app.services.simulation.market import contract_book

    return contract_book(session, career, season_rounds=int(season_horizon(session, career)["rounds"]))


def development_view(session: Session, career: Career) -> dict[str, Any]:
    """A read-only projection of how the career's players have developed from fixture minutes (M13 item 4).

    Sums each player's appearance minutes across the whole career, then projects the developed attribute
    set toward that player's stored potential using the deterministic curve in `development`. The result
    is recomputed from the rows on every read and never written back, so the squad the rest of the page
    reads keeps its stored attributes and the projection moves only as the career is actually played.
    """
    appearances = list(session.scalars(select(CareerAppearance).where(CareerAppearance.career_id == career.id)).all())
    by_player: dict[str, int] = {}
    for row in appearances:
        player_id = str(row.player_id)
        by_player[player_id] = by_player.get(player_id, 0) + int(row.minutes)
    if not by_player:
        return {
            "players_developed": 0,
            "total_minutes": 0,
            "top_developed": [],
            "tau": DEVELOPMENT_TAU,
            "rate": DEVELOPMENT_RATE,
            "development_formula": DEVELOPMENT_FORMULA,
            "note": (
                "no career appearances on file yet, so no fixture-minutes development can be projected; "
                "the squad reads its stored attributes exactly as before"
            ),
            "data_origin": "simulation",
            "is_demo_data": True,
        }
    players = {player.id: player for player in session.scalars(select(RealPlayer).where(RealPlayer.id.in_(list(by_player)))).all()}
    training = training_loads(session, list(by_player))
    developed: list[dict[str, Any]] = []
    for player_id, minutes in by_player.items():
        player = players.get(player_id)
        if player is None:
            continue
        training_units = training.get(player_id, 0)
        effective = int(minutes) + int(round(TRAINING_MINUTES_PER_UNIT * training_units))
        summary = development_summary(minutes_played=effective, potential=player.potential, attributes=player.attributes)
        developed.append(
            {
                "player_id": player_id,
                "player_name": player.name,
                "player_slug": player.slug,
                "position": player.position,
                "minutes": int(minutes),
                "training_units": training_units,
                "effective_minutes": effective,
                "potential": player.potential,
                "before": summary["before"],
                "after": summary["after"],
                "delta": summary["delta"],
            }
        )
    developed.sort(key=lambda item: (-item["minutes"], str(item["player_name"])))
    return {
        "players_developed": len(developed),
        "total_minutes": sum(item["minutes"] for item in developed),
        "top_developed": developed[:11],
        "tau": DEVELOPMENT_TAU,
        "rate": DEVELOPMENT_RATE,
        "development_formula": DEVELOPMENT_FORMULA,
        "note": (
            "projected only: the stored squad attributes elsewhere on this page are unchanged; this is what the "
            "match minutes and the world's training load imply if the season's development is applied, recomputed "
            "from the rows on every read"
        ),
        "data_origin": "simulation",
        "is_demo_data": True,
    }


def career_view(session: Session, career: Career, *, include_fixtures: bool = True) -> dict[str, Any]:
    rows = fixtures_of(session, career)
    record = record_of(rows)
    view: dict[str, Any] = {
        "career": {            "id": career.id,
            "slug": career.slug,
            "manager_name": career.manager_name,
            "club_name": career.club_name,
            "club_short": career.club_short,
            "club_id": career.club_id,
            "club_path": f"/team/{_club_slug(session, career)}" if career.club_id else None,
            "competition_name": career.competition_name,
            "season": career.season,
            "philosophy": career.philosophy,
            "system_slug": career.system_slug,
            "system_path": f"/tactics/{career.system_slug}" if career.system_slug else None,
            "budget": career.budget,
            "budget_units": career.budget_units,
            "rounds_played": career.rounds_played,
            "status": career.status,
            "challenge_slug": career.challenge_slug,
            "challenge_window": career.challenge_window,
            "data_origin": career.data_origin,
            "is_demo_data": career.is_demo_data,
        },
        "record": record,
        "objectives": objectives_of(career, record),
        "board": board_view(session, career, rows, record),
        "table": mini_table(rows, career),
        "consistency": _consistency(session, rows),
        "carry_over": carry_over_view(session, career, next_round=int(career.rounds_played) + 1),
        "development": development_view(session, career),
        "affordability": _affordability(session, career),
        "contracts": _contracts(session, career),
        "model_versions": sorted({row.model_version for row in rows if row.model_version}),
        "limitations": limitations(),
        "disclaimer": CAREER_DISCLAIMER,
        "data_origin": "simulation",
        "is_demo_data": True,
        "demo_data": True,
    }
    if include_fixtures:
        plan = next_fixture_plan(session, career)
        view["head_to_head"] = head_to_head(session, career, plan.get("opponent_team_id") if plan.get("available") else None)
        view["next_fixture_brief"] = next_fixture_brief(session, career, plan=plan)
        view["ledger"] = ledger_view(session, career)
        view["fixtures"] = [
            {
                "round_index": row.round_index,
                "side": row.side,
                "opponent_name": row.opponent_name,
                "opponent_short": row.opponent_short,
                "opponent_path": f"/team/{_team_slug(session, row.opponent_team_id)}",
                "venue_name": row.venue_name,
                "club_goals": row.club_goals,
                "opponent_goals": row.opponent_goals,
                "outcome": row.outcome,
                "points": row.points,
                "digest": row.digest,
                "seed": row.seed,
                "model_version": row.model_version,
                "match_slug": row.match_slug,
                "match_path": f"/simulate/{row.match_slug}" if row.match_slug else None,
                "match_still_stored": bool(row.match_id),
            }
            for row in rows
        ]
    return view


def _club_slug(session: Session, career: Career) -> str:
    return _team_slug(session, career.club_id)


def _team_slug(session: Session, team_id: str | None) -> str:
    if not team_id:
        return ""
    return str(session.scalar(select(Team.slug).where(Team.id == team_id)) or "")


__all__ = [
    "CAREER_DISCLAIMER",
    "OBJECTIVE_FORMULA",
    "POINTS_FOR",
    "BOARD_FORMULA",
    "HEAD_TO_HEAD_FORMULA",
    "NEXT_FIXTURE_FORMULA",
    "WindowClosed",
    "board_view",
    "career_view",
    "competition_clubs",
    "development_view",
    "create_career",
    "fixtures_of",
    "head_to_head",
    "limitations",
    "mini_table",
    "next_fixture_brief",
    "next_fixture_plan",
    "objectives_of",
    "play_round",
    "record_of",
    "resolve_club",
    "season_horizon",
]
