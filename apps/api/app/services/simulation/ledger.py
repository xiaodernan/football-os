"""The cross-match ledger (ROADMAP item 10): what `sim_events` was stored to answer.

A match report can only be read one match at a time. A manager's actual question is about a *season* —
who has scored for this club, who is carrying the bookings, who has taken the most chances — and asking
it of `sim_matches.report` means loading every report the career touched and picking JSON out of it in
Python. The rows exist so that this file can ask it in two grouped queries instead.

Two disciplines, both inherited from the table this reads:

* **Everything is summed from stored rows, on the request.** No counter is kept on the career, no figure
  is cached in a report. The SQL below is the whole computation, so a page that prints 7 goals is printing
  what `sim_events` says right now.
* **A sum is published beside the number it has to agree with.** The club's goal events are compared with
  `career_fixtures.club_goals`, which the career service copied out of the same reports at a different
  moment by a different route. Two code paths that agree are worth more than one that says so. When they
  disagree, `consistency` names both figures — it does not quietly prefer either, and it does not treat a
  fixture whose match was deleted as a disagreement, because that is a missing row, not a wrong one.

What the ledger deliberately does not do is reach past the club: an event is counted for the side that
printed it (`team_id`), so a player who signed away in January keeps only the events produced in this
club's shirt, and the same player's goals elsewhere belong to a different career's ledger.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Career, CareerAppearance, CareerFixture, SimulationEvent
from app.services.simulation.engine import SIMULATION_DISCLAIMER
from app.services.simulation.events import ATTRIBUTION_FORMULA

# How a row in this ledger came to be, in the reader's terms.
LEDGER_FORMULA = (
    "sim_events rows of this career's own fixtures, grouped by (player_id, event_type) and counted, each event belonging to the side that printed it — a player with no event of these types has no row"
)
# The second reader: the same season's goals, from the career's own fixture rows.
CONSISTENCY_FORMULA = "goal events credited to this club on sim_events, against career_fixtures.club_goals summed over the same matches"

_CHANCE_TYPES = ("goal", "shot_saved", "shot_off_target")
_LEDGER_TYPES = ("goal", "shot_saved", "shot_off_target", "yellow_card", "red_card", "injury")
# Generous enough that the cap only bites on an abnormal career — and `truncated` says so when it does.
LEDGER_LIMIT = 40

#: Goals per 90, read from the minutes `career_appearances` stored for this career's rounds.
PER90_FORMULA = (
    "goals per 90 = goals ÷ career_appearances minutes × 90, for a player with at least one appearance minute; a "
    "player with no appearance minutes has no per-90 (None, not zero), and the per-90 leaderboard ignores players "
    "under the minimum-minutes floor so one substitute goal cannot top it"
)
#: The minutes floor below which a player is not ranked on per-90.
_PER90_MIN_MINUTES = 90


def fixtures_of_career(session: Session, career: Career) -> list[CareerFixture]:
    """Every fixture this career played, in round order, played or not."""
    return list(session.scalars(select(CareerFixture).where(CareerFixture.career_id == career.id).order_by(CareerFixture.round_index)).all())


def _totals_by_type(session: Session, match_ids: list[str], club_id: str | None) -> dict[str, dict[str, Any]]:
    """Every event of this career's fixtures that belongs to the club's own side, by type."""
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
    """One row per player the club's events named, with each event type counted beside that name."""
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
    if club_id:
        stmt = stmt.where(SimulationEvent.team_id == club_id)
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
        if event_type in _CHANCE_TYPES:
            row["attempts"] += number
            row["expected_goals"] += float(xg)
        if event_type == "yellow_card":
            row["yellow_cards"] += number
        if event_type == "red_card":
            row["red_cards"] += number
        if event_type == "injury":
            row["injuries"] += number
        if event_type in _LEDGER_TYPES:
            row["events_by_type"][event_type] = row["events_by_type"].get(event_type, 0) + number
    # A second, much smaller query, because the count a row needs is not one the grouped result can give:
    # `count(distinct match_id)` inside the event-type grouping answers "in how many matches did this
    # player score", and no sum or maximum of those is the number of matches the player appears in at all.
    footprint = (
        select(SimulationEvent.player_id, func.count(func.distinct(SimulationEvent.match_id)))
        .where(SimulationEvent.match_id.in_(match_ids))
        .where(SimulationEvent.attribution == "identified")
        .group_by(SimulationEvent.player_id)
    )
    if club_id:
        footprint = footprint.where(SimulationEvent.team_id == club_id)
    for player_id, matches in session.execute(footprint):
        if str(player_id) in by_player:
            by_player[str(player_id)]["matches_with_events"] = int(matches)
    rows: list[dict[str, Any]] = list(by_player.values())
    for row in rows:
        row["expected_goals"] = round(row["expected_goals"], 3)
    rows.sort(key=lambda row: (-row["goals"], -row["attempts"], -(row["yellow_cards"] + row["red_cards"]), str(row["name"])))
    return rows


def _season_leaders(session: Session, career: Career, players: list[dict[str, Any]], *, appearances: list[CareerAppearance] | None = None) -> dict[str, Any]:
    """The season's leaders, with goals per 90 read from the appearance minutes the rounds stored.

    The player rows are the ledger's own; this adds each player's appearance count and minutes from
    `career_appearances`, then names the top of four categories. A player with no appearance minutes has no
    per-90 rather than a zero, and the per-90 board ignores anyone under the minutes floor. `appearances`
    lets the career view hand in the rows it already fetched rather than read the table again.
    """
    if not players:
        return {"leaders": {}, "per90_formula": PER90_FORMULA, "per90_min_minutes": _PER90_MIN_MINUTES, "note": "no player has an event in this career's fixtures yet"}
    if appearances is not None:
        agg: dict[str, list[int]] = {}
        for row in appearances:
            slug = str(row.player_slug or "")
            slot = agg.setdefault(slug, [0, 0])
            slot[0] += int(row.minutes)
            slot[1] += 1
        by_slug = {slug: (minutes, apps) for slug, (minutes, apps) in agg.items()}
    else:
        appearance = (
            select(
                CareerAppearance.player_slug,
                func.coalesce(func.sum(CareerAppearance.minutes), 0).label("minutes"),
                func.count().label("appearances"),
            )
            .where(CareerAppearance.career_id == career.id)
            .group_by(CareerAppearance.player_slug)
        )
        by_slug = {str(slug): (int(minutes), int(apps)) for slug, minutes, apps in session.execute(appearance)}
    for row in players:
        minutes, apps = by_slug.get(str(row.get("slug") or ""), (0, 0))
        row["appearances"] = apps
        row["minutes"] = minutes
        row["goals_per90"] = round(row["goals"] / minutes * 90, 2) if minutes > 0 else None
        row["cards"] = int(row["yellow_cards"]) + int(row["red_cards"])

    def leader(key: str, *, minimum_minutes: int = 0) -> dict[str, Any] | None:
        pool = [row for row in players if int(row["minutes"]) >= minimum_minutes and row.get(key) is not None]
        if not pool:
            return None
        best = max(pool, key=lambda row: (row[key], row["goals"]))
        return {"player_id": best["player_id"], "player_slug": best["slug"], "player_name": best["name"], "value": best[key]}

    return {
        "leaders": {
            "top_scorer": leader("goals"),
            "top_xg": leader("expected_goals"),
            "most_cards": leader("cards"),
            "best_per90": leader("goals_per90", minimum_minutes=_PER90_MIN_MINUTES),
        },
        "per90_min_minutes": _PER90_MIN_MINUTES,
        "per90_formula": PER90_FORMULA,
        "note": "per-90 uses the career_appearances minutes this career's rounds stored; a player with no appearance minutes has no per-90 rather than a zero",
    }


def _unattributed_names(session: Session, match_ids: list[str], club_id: str | None) -> dict[str, list[str]]:
    """The names this ledger could not turn into a player, so no total silently stands for them."""
    if not match_ids:
        return {"ambiguous": [], "unnamed": []}
    stmt = select(SimulationEvent.attribution, SimulationEvent.player_name).where(SimulationEvent.match_id.in_(match_ids)).where(SimulationEvent.attribution.in_(("ambiguous", "unnamed"))).distinct()
    if club_id:
        stmt = stmt.where(SimulationEvent.team_id == club_id)
    found: dict[str, set[str]] = {"ambiguous": set(), "unnamed": set()}
    for attribution, name in session.execute(stmt):
        # Distinct rows rather than a grouped string aggregate: `group_concat` is SQLite and `string_agg`
        # is Postgres, and a ledger has to give the same answer on both engines this project tests on.
        # An empty name is an event that named no one at all, which the `unnamed` count already carries.
        if str(name or "").strip():
            found[str(attribution)].add(str(name).strip())
    return {kind: sorted(names) for kind, names in found.items()}


def _traced_match_ids(session: Session, match_ids: list[str]) -> set[str]:
    """Which of this career's stored matches actually have event rows to read.

    A match simulated before migration 0014 has none, and one whose report was written by a build that
    never reached `write_timeline` has none either. Those fixtures are a gap in this ledger's data, not a
    0-0 scoreline, and the difference is published rather than averaged away.
    """
    if not match_ids:
        return set()
    stmt = select(SimulationEvent.match_id).where(SimulationEvent.match_id.in_(match_ids)).distinct()
    return {str(match_id) for match_id in session.scalars(stmt).all()}


def _consistency(goals_from_events: int, club_goals: int, traced: int, untraced: int) -> str:
    """The two readings of the same season, said out loud whether or not they agree."""
    if not traced:
        return (
            f"{untraced} played fixture(s) of this career carry no event rows at all, so there is nothing here to compare with the fixture list yet"
            if untraced
            else "this career has played no fixture with a stored match, so every figure in this ledger is a sum over no rows"
        )
    missing = f"; {untraced} played fixture(s) have no rows to read, which is a gap rather than a disagreement" if untraced else ""
    if goals_from_events != club_goals:
        return (
            f"{goals_from_events} goal(s) on the event rows against {club_goals} on this career's fixture list, over "
            f"{traced} traced fixture(s): the two disagree and neither figure is rewritten by this page{missing}"
        )
    return f"{goals_from_events} goal(s) on the event rows and {club_goals} on this career's fixture list, over {traced} traced fixture(s): the two readings agree{missing}"


def ledger_view(session: Session, career: Career, *, appearances: list[CareerAppearance] | None = None, fixtures: list[CareerFixture] | None = None) -> dict[str, Any]:
    """This career's season as the event rows give it: per-player counts, and the checks beside them."""
    fixtures = fixtures if fixtures is not None else fixtures_of_career(session, career)
    played = [row for row in fixtures if row.match_id]
    match_ids = [str(row.match_id) for row in played if row.match_id]
    club_id = career.club_id or None
    totals = _totals_by_type(session, match_ids, club_id)
    players = _player_rows(session, match_ids, club_id)
    leaders = _season_leaders(session, career, players, appearances=appearances)
    names = _unattributed_names(session, match_ids, club_id)
    traced_ids = _traced_match_ids(session, match_ids)
    traced = len(traced_ids)
    # Fixtures whose stored match has been deleted, and matches whose rows never arrived, are both counted
    # here: this is the number of rounds the career played that the ledger cannot read.
    untraced = len(fixtures) - traced
    goals = int(totals.get("goal", {}).get("events", 0))
    club_goals = sum(int(row.club_goals) for row in played if str(row.match_id) in traced_ids)
    shown = players[:LEDGER_LIMIT]
    unattributed_events = {kind: sum(int(entry.get(kind, 0)) for entry in totals.values()) for kind in ("ambiguous", "unnamed")}
    return {
        "club": {"team_id": club_id, "name": career.club_name, "short": career.club_short},
        "players": shown,
        "players_with_events": len(players),
        "players_shown": len(shown),
        "truncated": len(players) > len(shown),
        "leaders": leaders,
        "totals": {
            "events": sum(int(entry["events"]) for entry in totals.values()),
            "goals": goals,
            "attempts": sum(int(totals.get(kind, {}).get("events", 0)) for kind in _CHANCE_TYPES),
            "expected_goals": round(sum(float(entry["expected_goals"]) for kind, entry in totals.items() if kind in _CHANCE_TYPES), 3),
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
        "scope": (
            f"only events whose side is this career's club ({career.club_short})"
            if club_id
            else "this career row carries no club id, so both sides of every fixture are counted together — the per-player rows below are not a single club's squad"
        ),
        "source": "sim_events rows" if traced else "no traced fixture",
        "formula": LEDGER_FORMULA,
        "consistency_formula": CONSISTENCY_FORMULA,
        "attribution_formula": ATTRIBUTION_FORMULA,
        "disclaimer": SIMULATION_DISCLAIMER,
        "data_origin": "simulation",
        "is_demo_data": True,
    }


__all__ = ["CONSISTENCY_FORMULA", "LEDGER_FORMULA", "LEDGER_LIMIT", "PER90_FORMULA", "fixtures_of_career", "ledger_view"]
