"""Cross-career and league-wide aggregates (M6 item 10 open item): reads that span multiple careers.

The ROADMAP open item reads: "no cross-career or league-wide aggregate reads these rows".
This module adds read-only aggregate endpoints that span multiple careers — the rows already
exist in sim_events, sim_matches, sim_events; this module just asks questions across them.

Two aggregate surfaces:
* **League ledger** — one competition's played fixtures, summed across all careers whose
  club is in that competition. The club is the unit, not the career; a club may have
  multiple careers (one per account), but a fixture belongs to one club.
* **Player career aggregate** — all sim_events rows for a given player across all careers
  they've played in (the player is identified by real_player or by slug across careers).

Both are pure reads: summed from sim_events/sim_matches at request time, no stored
aggregates, same scope/focus rules as the per-career ledger.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Career, CareerFixture, Competition, SimulationEvent, SimulationMatch, Team
from app.services.simulation.engine import SIMULATION_DISCLAIMER
from app.services.simulation.events import ATTRIBUTION_FORMULA

# Re-use the same constants as the per-career ledger
_CHANCE_TYPES = ("goal", "shot_saved", "shot_off_target")
_LEDGER_TYPES = ("goal", "shot_saved", "shot_off_target", "yellow_card", "red_card", "injury")
LEDGER_LIMIT = 40

# Formula strings shared with the per-career ledger
LEDGER_FORMULA = (
    "sim_events rows of this career's own fixtures, grouped by (player_id, event_type) and counted, "
    "each event belonging to the side that printed it — a player with no event of these types has no row"
)
CONSISTENCY_FORMULA = "goal events credited to this club on sim_events, against career_fixtures.club_goals summed over the same matches"
ATTRIBUTION_FORMULA = ATTRIBUTION_FORMULA


def _totals_by_type(session: Session, match_ids: list[str], club_id: str | None) -> dict[str, dict[str, Any]]:
    """Every event of these fixtures that belongs to the given club, by type."""
    if not match_ids:
        return {}
    stmt = (
        select(
            SimulationEvent.event_type,
            SimulationEvent.attribution,
            func.count().label("n"),
            func.coalesce(func.sum(SimulationEvent.expected_goals), 0.0).label("xg"),
        )
        .where(SimulationEvent.match_id.in_(match_ids))
        .group_by(SimulationEvent.event_type, SimulationEvent.attribution)
    )
    if club_id:
        stmt = stmt.where(SimulationEvent.team_id == club_id)
    totals: dict[str, dict[str, Any]] = {}
    for event_type, attribution, count, xg in session.execute(stmt):
        entry = totals.setdefault(event_type, {"events": 0, "identified": 0, "ambiguous": 0, "unnamed": 0, "expected_goals": 0.0})
        entry["events"] += int(count)
        entry["expected_goals"] += float(xg)
        entry[attribution if attribution in ("identified", "ambiguous", "unnamed") else "unnamed"] += int(count)
    for entry in totals.values():
        entry["expected_goals"] = round(entry["expected_goals"], 3)
    return totals


def _player_rows(session: Session, match_ids: list[str], club_id: str | None) -> list[dict[str, Any]]:
    """One row per player the events named, with each event type counted beside that name."""
    if not match_ids:
        return []
    stmt = (
        select(
            SimulationEvent.player_id,
            SimulationEvent.player_slug,
            SimulationEvent.player_name,
            SimulationEvent.position,
            SimulationEvent.event_type,
            func.count().label("n"),
            func.coalesce(func.sum(SimulationEvent.expected_goals), 0.0).label("xg"),
        )
        .where(SimulationEvent.match_id.in_(match_ids))
        .where(SimulationEvent.attribution == "identified")
        .group_by(
            SimulationEvent.player_id,
            SimulationEvent.player_slug,
            SimulationEvent.player_name,
            SimulationEvent.position,
            SimulationEvent.event_type,
        )
    )
    by_player: dict[str, dict[str, Any]] = {}
    for player_id, slug, name, position, event_type, count, xg in session.execute(stmt):
        row = by_player.setdefault(
            str(player_id),
            {
                "player_id": player_id,
                "slug": slug,
                "player_path": f"/player/{slug}" if slug else None,
                "name": name,
                "position": position,
                "matches_with_events": 0,
                "goals": 0,
                "attempts": 0,
                "expected_goals": 0.0,
                "yellow_cards": 0,
                "red_cards": 0,
                "injuries": 0,
                "events_by_type": {},
            },
        )
        number = int(count)
        if event_type == "goal":
            row["goals"] += number
        if event_type in ("goal", "shot_saved", "shot_off_target"):
            row["attempts"] += number
            row["expected_goals"] += float(xg)
        if event_type == "yellow_card":
            row["yellow_cards"] += number
        if event_type == "red_card":
            row["red_cards"] += number
        if event_type == "injury":
            row["injuries"] += number
        if event_type in ("goal", "shot_saved", "shot_off_target", "yellow_card", "red_card", "injury"):
            row["events_by_type"][event_type] = row["events_by_type"].get(event_type, 0) + number
    # footprint: distinct matches per player
    footprint = (
        select(SimulationEvent.player_id, func.count(func.distinct(SimulationEvent.match_id)))
        .where(SimulationEvent.match_id.in_(match_ids))
        .where(SimulationEvent.attribution == "identified")
        .group_by(SimulationEvent.player_id)
    )
    for player_id, matches in session.execute(footprint):
        if str(player_id) in by_player:
            by_player[str(player_id)]["matches_with_events"] = int(matches)
    rows: list[dict[str, Any]] = list(by_player.values())
    for row in rows:
        row["expected_goals"] = round(row["expected_goals"], 3)
    rows.sort(key=lambda row: (-row["goals"], -row["attempts"], -(row["yellow_cards"] + row["red_cards"]), str(row["name"])))
    return rows


def _unattributed_names(session: Session, match_ids: list[str], club_id: str | None) -> dict[str, list[str]]:
    if not match_ids:
        return {"ambiguous": [], "unnamed": []}
    stmt = select(SimulationEvent.attribution, SimulationEvent.player_name).where(SimulationEvent.match_id.in_(match_ids)).where(SimulationEvent.attribution.in_(("ambiguous", "unnamed"))).distinct()
    if club_id:
        stmt = stmt.where(SimulationEvent.team_id == club_id)
    found: dict[str, set[str]] = {"ambiguous": set(), "unnamed": set()}
    for attribution, name in session.execute(stmt):
        if str(name or "").strip():
            found[str(attribution)].add(str(name).strip())
    return {kind: sorted(names) for kind, names in found.items()}


def _traced_match_ids(session: Session, match_ids: list[str]) -> set[str]:
    if not match_ids:
        return set()
    stmt = select(SimulationEvent.match_id).where(SimulationEvent.match_id.in_(match_ids)).distinct()
    return {str(match_id) for match_id in session.scalars(stmt).all()}


def _consistency(goals_from_events: int, club_goals: int, traced: int, untraced: int) -> str:
    if not traced:
        return (
            f"{untraced} played fixture(s) carry no event rows at all, so there is nothing here to compare with the fixture list yet"
            if untraced
            else "this career has played no fixture with a stored match, so every figure in this ledger is a sum over no rows"
        )
    missing = f"; {untraced} played fixture(s) have no rows to read, which is a gap rather than a disagreement" if untraced else ""
    if goals_from_events != club_goals:
        return (
            f"{goals_from_events} goal(s) on the event rows against {club_goals} on the fixture list, over "
            f"{traced} traced fixture(s): the two disagree and neither figure is rewritten{missing}"
        )
    return f"{goals_from_events} goal(s) on the event rows and {club_goals} on the fixture list, over {traced} traced fixture(s): the two readings agree{missing}"


def _fixtures_of_careers(session: Session, career_ids: list[str]) -> list[CareerFixture]:
    """All fixtures of these careers, in round order."""
    if not career_ids:
        return []
    return list(
        session.scalars(
            select(CareerFixture)
            .where(CareerFixture.career_id.in_(career_ids))
            .order_by(CareerFixture.career_id, CareerFixture.round_index)
        ).all()
    )


def _match_ids_of_fixtures(fixtures: list[CareerFixture]) -> list[str]:
    return [str(row.match_id) for row in fixtures if row.match_id]


def _club_ids_of_careers(session: Session, career_ids: list[str]) -> list[str]:
    if not career_ids:
        return []
    return [
        str(row[0]) for row in
        session.execute(select(Career.club_id).where(Career.id.in_(career_ids)).where(Career.club_id.is_not(None)).distinct())
    ]


def _career_ids_by_club(session: Session, club_id: str) -> list[str]:
    return [str(row[0]) for row in session.execute(select(Career.id).where(Career.club_id == club_id))]


def _league_fixtures(session: Session, competition_id: str) -> list[CareerFixture]:
    """All played fixtures of careers whose club is in this competition."""
    club_ids = [str(row[0]) for row in session.execute(select(Team.id).where(Team.competition_id == competition_id))]
    if not club_ids:
        return []
    career_ids = []
    for cid in club_ids:
        career_ids.extend(_career_ids_by_club(session, cid))
    return _fixtures_of_careers(session, career_ids)


def league_ledger_view(session: Session, competition: Competition) -> dict[str, Any]:
    """League-wide ledger: all careers whose club is in this competition, summed together.
    
    The club is the unit of aggregation (a club may have multiple careers, one per account).
    A fixture belongs to one club, so we filter by the club's career fixtures.
    """
    fixtures = _league_fixtures(session, competition.id)
    played = [row for row in fixtures if row.match_id]
    match_ids = _match_ids_of_fixtures(played)
    club_ids = _club_ids_of_careers(session, [str(row.career_id) for row in played])
    
    # Since a fixture belongs to one club, we sum across all clubs in the competition
    # by not filtering to a single club_id (the per-fixture club_id is already the fixture's club)
    totals = _totals_by_type(session, match_ids, club_id=None)  # no single club filter
    players = _player_rows(session, match_ids, club_id=None)
    names = _unattributed_names(session, match_ids, club_id=None)
    
    traced_ids = _traced_match_ids(session, match_ids)
    traced = len(traced_ids)
    untraced = len(fixtures) - traced
    
    goals = int(totals.get("goal", {}).get("events", 0))
    # club_goals: sum of club_goals for traced fixtures of all clubs in this competition
    club_goals = sum(int(row.club_goals) for row in played if str(row.match_id) in traced_ids)
    
    shown = players[:LEDGER_LIMIT]
    unattributed_events = {kind: sum(int(entry.get(kind, 0)) for entry in totals.values()) for kind in ("ambiguous", "unnamed")}
    
    return {
        "competition": {"id": competition.id, "slug": competition.slug, "name": competition.name},
        "players": shown,
        "players_with_events": len(players),
        "players_shown": len(shown),
        "truncated": len(players) > len(shown),
        "totals": {
            "events": sum(int(entry["events"]) for entry in totals.values()),
            "goals": goals,
            "attempts": sum(int(totals.get(kind, {}).get("events", 0)) for kind in ("goal", "shot_saved", "shot_off_target")),
            "expected_goals": round(sum(float(entry["expected_goals"]) for kind, entry in totals.items() if kind in ("goal", "shot_saved", "shot_off_target")), 3),
            "yellow_cards": int(totals.get("yellow_card", {}).get("events", 0)),
            "red_cards": int(totals.get("red_card", {}).get("events", 0)),
            "injuries": int(totals.get("injury", {}).get("events", 0)),
        },
        "by_type": totals,
        "fixtures_played": len(fixtures),
        "fixtures_traced": traced,
        "fixtures_untraced": untraced,
        "club_goals_traced": club_goals,
        "unattributed": {
            "events": unattributed_events,
            "ambiguous_names": names["ambiguous"],
            "unnamed_names": names["unnamed"],
        },
        "consistency": _consistency(goals, club_goals, traced, untraced),
        "scope": f"all careers whose club is in competition {competition.name}",
        "source": "sim_events rows" if traced else "no traced fixture",
        "formula": LEDGER_FORMULA,
        "consistency_formula": CONSISTENCY_FORMULA,
        "attribution_formula": ATTRIBUTION_FORMULA,
        "disclaimer": SIMULATION_DISCLAIMER,
        "data_origin": "simulation",
        "is_demo_data": True,
    }


def player_career_aggregate_view(session: Session, career_ids: list[str], player_slug: str) -> dict[str, Any]:
    """Aggregate of one player across all careers they've played in.
    
    The player is identified by their slug (which is unique per career, but a real
    player may have multiple careers — one per account). We find all careers that
    have a player with this slug and sum their events.
    """
    fixtures = _fixtures_of_careers(session, career_ids)
    played = [row for row in fixtures if row.match_id]
    match_ids = _match_ids_of_fixtures(played)
    
    # Get the player's name/position from CareerAppearance
    from app.models import CareerAppearance
    sample_appearance = session.scalar(
        select(CareerAppearance)
        .where(CareerAppearance.career_id.in_(career_ids))
        .where(CareerAppearance.player_slug == player_slug)
    )
    player_name = sample_appearance.player_name if sample_appearance else player_slug
    player_position = sample_appearance.position if sample_appearance else None
    
    totals = _totals_by_type(session, match_ids, club_id=None)
    players = _player_rows(session, match_ids, club_id=None)
    # Filter to just this player
    player_rows = [p for p in players if p["slug"] == player_slug]
    names = _unattributed_names(session, match_ids, club_id=None)
    
    traced_ids = _traced_match_ids(session, match_ids)
    traced = len(traced_ids)
    untraced = len(fixtures) - traced
    
    goals = int(totals.get("goal", {}).get("events", 0))
    
    shown = players[:LEDGER_LIMIT]
    unattributed_events = {kind: sum(int(entry.get(kind, 0)) for entry in totals.values()) for kind in ("ambiguous", "unnamed")}
    
    return {
        "player": {"slug": player_slug, "name": player_name, "position": player_position},
        "careers": [{"id": c.id, "slug": c.slug, "club_name": c.club_name, "club_short": c.club_short} for c in careers],
        "players": shown,
        "players_with_events": len(players),
        "players_shown": len(shown),
        "truncated": len(players) > len(shown),
        "totals": {
            "events": sum(int(entry["events"]) for entry in totals.values()),
            "goals": goals,
            "attempts": sum(int(totals.get(kind, {}).get("events", 0)) for kind in ("goal", "shot_saved", "shot_off_target")),
            "expected_goals": round(sum(float(entry["expected_goals"]) for kind, entry in totals.items() if kind in ("goal", "shot_saved", "shot_off_target")), 3),
            "yellow_cards": int(totals.get("yellow_card", {}).get("events", 0)),
            "red_cards": int(totals.get("red_card", {}).get("events", 0)),
            "injuries": int(totals.get("injury", {}).get("events", 0)),
        },
        "by_type": totals,
        "fixtures_played": len(fixtures),
        "fixtures_traced": traced,
        "fixtures_untraced": untraced,
        "unattributed": {
            "events": unattributed_events,
            "ambiguous_names": names["ambiguous"],
            "unnamed_names": names["unnamed"],
        },
        "consistency": _consistency(goals, 0, traced, untraced),  # no club_goals for cross-career
        "scope": f"all careers with player slug {player_slug}",
        "source": "sim_events rows" if traced else "no traced fixture",
        "formula": LEDGER_FORMULA,
        "consistency_formula": CONSISTENCY_FORMULA,
        "attribution_formula": ATTRIBUTION_FORMULA,
        "disclaimer": SIMULATION_DISCLAIMER,
        "data_origin": "simulation",
        "is_demo_data": True,
    }


__all__ = [
    "CONSISTENCY_FORMULA",
    "LEDGER_FORMULA",
    "LEDGER_LIMIT",
    "league_ledger_view",
    "player_career_aggregate_view",
]