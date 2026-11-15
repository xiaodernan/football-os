"""The season, matchday by matchday — the league's story told with arithmetic alone.

The almanac honours individuals; the story tells the season in three chapters; the record book keeps
marks. This module walks the tier-1 league's completed fixtures in kickoff order, holds the table
running week by week, and answers one question the rest of the world tier cannot: when did the title
become champions'-points-vs-everyone-else's-ceiling, and what did the season look like on the way.

Deterministic end to end. Every figure is a walk over `real_matches` — no provider, no stored
figure, no invented anything. `round_label` values are read straight ("Matchday 7", with the two
`game N` replays carried into their base matchday); an unwritten world publishes `available: false`
rather than a filled card.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RealMatch, Team
from app.services.world.almanac import _top_league

ROUND_SPLIT = re.compile(r"^Matchday\s+(\d+)(?:\s+game\s+(\d+))?", re.IGNORECASE)


def _round_of(label: str | None) -> int | None:
    if not label:
        return None
    match = ROUND_SPLIT.match(label.strip())
    return int(match.group(1)) if match else None


def _points_gd_gf(row: dict[str, Any]) -> tuple[int, int, int]:
    return (-row["points"], -(row["goals_for"] - row["goals_against"]), -row["goals_for"])


def _team_brief(team: Team | None, **extra: Any) -> dict[str, Any]:
    if team is None:
        return {"id": None, "slug": None, "name": "Data unavailable", "path": None, **extra}
    return {
        "id": team.id,
        "slug": team.slug,
        "name": team.name,
        "path": f"/team/{team.slug}",
        **extra,
    }


def compute_timeline(session: Session) -> dict[str, Any]:
    league = _top_league(session)
    if league is None:
        return {"available": False, "season": {"label": "2026/27", "kind": "7:3"}}

    # every fixture ever scheduled in this league — remaining games are counted against this, not against guesses
    all_fixtures = list(
        session.scalars(
            select(RealMatch).where(RealMatch.competition_id == league.id)
        ).all()
    )
    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    scheduled_per_team: dict[str, int] = defaultdict(int)
    for fixture in all_fixtures:
        if not fixture.home_team_id or not fixture.away_team_id:
            continue
        scheduled_per_team[fixture.home_team_id] += 1
        scheduled_per_team[fixture.away_team_id] += 1

    played = [
        fixture for fixture in all_fixtures
        if fixture.status == "completed" and fixture.home_goals is not None and fixture.away_goals is not None
    ]
    if not played:
        return {
            "available": False,
            "season": {"label": "2026/27", "kind": "7:3"},
            "competition": league.name,
            "competition_slug": league.slug,
        }

    table: dict[str, dict[str, Any]] = {}
    rounds: list[dict[str, Any]] = []

    def fresh_row(team_id: str) -> dict[str, Any]:
        return table.setdefault(
            team_id,
            {"team_id": team_id, "played": 0, "won": 0, "drawn": 0, "lost": 0,
             "goals_for": 0, "goals_against": 0, "points": 0},
        )

    by_round: dict[int, list[RealMatch]] = defaultdict(list)
    unlabelled: list[RealMatch] = []
    for fixture in played:
        round_number = _round_of(fixture.round_label)
        if round_number is None:
            unlabelled.append(fixture)
        else:
            by_round[round_number].append(fixture)

    for round_number in sorted(by_round):
        fixtures = by_round[round_number]
        fixtures.sort(key=lambda fixture: fixture.kickoff_at.isoformat() if fixture.kickoff_at else "")
        goals = sum((f.home_goals or 0) + (f.away_goals or 0) for f in fixtures)
        for fixture in fixtures:
            home_goals = fixture.home_goals or 0
            away_goals = fixture.away_goals or 0
            for team_id, on_home in ((fixture.home_team_id, True), (fixture.away_team_id, False)):
                stats = fresh_row(team_id)
                gf = home_goals if on_home else away_goals
                ga = away_goals if on_home else home_goals
                stats["played"] += 1
                stats["goals_for"] += gf
                stats["goals_against"] += ga
                if home_goals == away_goals:
                    stats["drawn"] += 1
                    stats["points"] += 1
                elif (on_home and home_goals > away_goals) or (not on_home and away_goals > home_goals):
                    stats["won"] += 1
                    stats["points"] += 3
                else:
                    stats["lost"] += 1
        rows = sorted(table.values(), key=_points_gd_gf)
        leader = rows[0]
        runner = rows[1] if len(rows) > 1 else None
        round_label = f"Matchday {round_number}"
        rounds.append(
            {
                "matchday": round_number,
                "label": round_label,
                "fixtures": len(fixtures),
                "goals": goals,
                "leader": _team_brief(
                    teams.get(leader["team_id"]),
                    points=leader["points"],
                    goal_difference=leader["goals_for"] - leader["goals_against"],
                    goals_for=leader["goals_for"],
                    played=leader["played"],
                ),
                "runner_up": _team_brief(
                    teams.get(runner["team_id"]) if runner else None,
                    points=(runner["points"] if runner else 0),
                )
                if runner
                else None,
                "gap": (leader["points"] - runner["points"]) if runner else 0,
            }
        )

    if not rounds:
        return {
            "available": False,
            "season": {"label": "2026/27", "kind": "7:3"},
            "competition": league.name,
            "competition_slug": league.slug,
        }

    # the eventual champion: how the season ends
    final_rows = sorted(table.values(), key=_points_gd_gf)
    champion = final_rows[0]
    champion_id = champion["team_id"]
    champion_team = teams.get(champion_id)
    runner_up_id = final_rows[1]["team_id"] if len(final_rows) > 1 else None

    def beats() -> dict[str, Any]:
        opening_round = rounds[0]
        avalanche = max(rounds, key=lambda r: (r["goals"], -r["matchday"]))
        # takeover: the earliest matchday from which the eventual champion never gave the lead back
        takeover_index = None
        for index in range(len(rounds)):
            if all(round_data["leader"]["id"] == champion_id for round_data in rounds[index:]):
                takeover_index = index
                break
        takeover = rounds[takeover_index] if takeover_index is not None else None
        # settled: the earliest matchday at which every rival's points + 3 * their remaining fixtures
        # fall short of the champion's points at that moment
        settled = None
        for index, round_data in enumerate(rounds):
            leader_id = round_data["leader"]["id"]
            if leader_id != champion_id:
                continue
            champ_points = round_data["leader"]["points"]
            safe = True
            for row in table_at_the_time(index):
                rival_points = row["points"]
                rival_played = row["played"]
                remaining = max(scheduled_per_team.get(row["team_id"], rival_played) - rival_played, 0)
                if row["team_id"] != champion_id and rival_points + 3 * remaining >= champ_points:
                    safe = False
                    break
            if safe:
                settled = round_data
                break
        return {
            "opening": {
                "available": True,
                "matchday": opening_round["matchday"],
                "label": opening_round["label"],
                "fixtures": opening_round["fixtures"],
                "goals": opening_round["goals"],
                "leader": opening_round["leader"],
                "eventual_champion_led": opening_round["leader"]["id"] == champion_id,
            },
            "avalanche": {
                "available": True,
                "matchday": avalanche["matchday"],
                "label": avalanche["label"],
                "goals": avalanche["goals"],
                "fixtures": avalanche["fixtures"],
            },
            "takeover": (
                {
                    "available": True,
                    "matchday": takeover["matchday"],
                    "label": takeover["label"],
                    "lead_matchdays": len(rounds) - (takeover_index if takeover_index is not None else 0),
                }
                if takeover
                else {"available": False}
            ),
            "settled": (
                {
                    "available": True,
                    "matchday": settled["matchday"],
                    "label": settled["label"],
                    "points": settled["leader"]["points"],
                    "gap": settled["gap"],
                    "decided_on_tiebreak": False,
                }
                if settled
                else {
                    "available": False,
                    # honest fallback: the champion leads the final round but never strictly cleared
                    # every ceiling — the title was sealed at the whistle, not on the points
                    "decided_on_tiebreak": bool(
                        rounds[-1]["leader"]["id"] == champion_id
                        and rounds[-1]["runner_up"] is not None
                        and rounds[-1]["runner_up"]["points"] == rounds[-1]["leader"]["points"]
                    ),
                }
            ),
        }

    # per-matchday table snapshots, kept for the settlement walk — the same arithmetic as the rounds above
    def table_at_the_time(index: int) -> list[dict[str, Any]]:
        snap: dict[str, dict[str, Any]] = {}

        def row(team_id: str) -> dict[str, Any]:
            return snap.setdefault(
                team_id,
                {"team_id": team_id, "played": 0, "goals_for": 0, "goals_against": 0, "points": 0},
            )

        for target_index in range(index + 1):
            matchday = rounds[target_index]["matchday"]
            for fixture in by_round[matchday]:
                if fixture.home_goals is None or fixture.away_goals is None:
                    continue
                for team_id, on_home in ((fixture.home_team_id, True), (fixture.away_team_id, False)):
                    stats = row(team_id)
                    gf = fixture.home_goals if on_home else fixture.away_goals
                    ga = fixture.away_goals if on_home else fixture.home_goals
                    stats["played"] += 1
                    stats["goals_for"] += gf or 0
                    stats["goals_against"] += ga or 0
                    if fixture.home_goals == fixture.away_goals:
                        stats["points"] += 1
                    elif (on_home and fixture.home_goals > fixture.away_goals) or (not on_home and fixture.away_goals > fixture.home_goals):
                        stats["points"] += 3
        return list(snap.values())

    def trajectories() -> list[dict[str, int]]:
        result: list[dict[str, int]] = []
        for index in range(len(rounds)):
            snap = table_at_the_time(index)
            champion_points = next((row["points"] for row in snap if row["team_id"] == champion_id), 0)
            runner_points = next(
                (row["points"] for row in snap if runner_up_id is not None and row["team_id"] == runner_up_id),
                0,
            )
            result.append(
                {
                    "matchday": rounds[index]["matchday"],
                    "leader_points": rounds[index]["leader"]["points"],
                    "champion_points": champion_points,
                    "runner_up_points": runner_points,
                    "gap": rounds[index]["gap"],
                }
            )
        return result

    return {
        "available": True,
        "season": {"label": "2026/27", "kind": "7:3"},
        "competition": league.name,
        "competition_slug": league.slug,
        "matchdays": max(round_data["matchday"] for round_data in rounds),
        "rounds": rounds,
        "chart": trajectories(),
        "champion": _team_brief(
            champion_team,
            points=champion["points"],
            played=champion["played"],
            won=champion["won"],
            drawn=champion["drawn"],
            lost=champion["lost"],
            goal_difference=champion["goals_for"] - champion["goals_against"],
        ),
        "beats": beats(),
    }


__all__ = ["compute_timeline"]
