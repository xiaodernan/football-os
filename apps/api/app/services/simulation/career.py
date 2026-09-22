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

The budget and philosophy are *stated intent*: they shape what the page says the manager asked for, and
nothing in the engine reads them yet — transfers and finance are later slices, and `limitations()` says
so rather than letting a budget look like a constraint that was tested.
"""

from __future__ import annotations

import hashlib
from typing import Any, Final

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import OBJECTIVE_FORMULA, Career, CareerFixture, Competition, SimulationMatch, Team
from app.services.simulation.service import run_simulation
from app.services.world.names import slugify

SEED_SPACE: Final = 2_147_483_647
POINTS_FOR: Final = {"W": 3, "D": 1, "L": 0}
CAREER_DISCLAIMER: Final = (
    "A career is a fiction this platform plays with itself: the club is a generated club, every fixture is "
    "decided by the labelled simulation engine, and no result here reports a real match, a real competition "
    "or a real season."
)


def limitations() -> dict[str, str]:
    """What this layer does not claim, in the words the page prints."""
    return {
        "budget": (
            f"The budget is stated intent carried on the career row ({'career credits'}). Nothing spends it yet: there is no transfer market, so no fixture was affected by a large or a small number."
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


def next_fixture_plan(session: Session, career: Career) -> dict[str, Any]:
    """Which club is next, on which side, and where it is played."""
    round_index = career.rounds_played + 1
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


def play_round(session: Session, career: Career) -> tuple[CareerFixture, SimulationMatch]:
    """Play the next round through the engine and record it against the career."""
    if career.status != "active":
        raise ValueError("this career is retired; open a new one to keep playing")
    plan = next_fixture_plan(session, career)
    if not plan["available"]:
        raise ValueError(str(plan["reason"]))
    home_id, away_id = (career.club_id or "", plan["opponent_team_id"]) if plan["side"] == "home" else (plan["opponent_team_id"], career.club_id or "")
    match = run_simulation(
        session,
        owner_id=career.owner_id,
        home_team_id=home_id,
        away_team_id=away_id,
        home_system=(career.system_slug or None) if plan["side"] == "home" else None,
        away_system=None if plan["side"] == "home" else (career.system_slug or None),
        seed=int(plan["seed"]),
        minutes=90,
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


def career_view(session: Session, career: Career, *, include_fixtures: bool = True) -> dict[str, Any]:
    rows = fixtures_of(session, career)
    record = record_of(rows)
    view: dict[str, Any] = {
        "career": {
            "id": career.id,
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
            "data_origin": career.data_origin,
            "is_demo_data": career.is_demo_data,
        },
        "record": record,
        "objectives": objectives_of(career, record),
        "table": mini_table(rows, career),
        "consistency": _consistency(session, rows),
        "model_versions": sorted({row.model_version for row in rows if row.model_version}),
        "limitations": limitations(),
        "disclaimer": CAREER_DISCLAIMER,
        "data_origin": "simulation",
        "is_demo_data": True,
        "demo_data": True,
    }
    if include_fixtures:
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
    "career_view",
    "competition_clubs",
    "create_career",
    "fixtures_of",
    "limitations",
    "mini_table",
    "next_fixture_plan",
    "objectives_of",
    "play_round",
    "record_of",
    "resolve_club",
]
