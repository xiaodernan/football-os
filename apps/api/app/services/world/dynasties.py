"""The Dynasties — the tier-1 streak ledger, recomputed live like every world door.

One walk per request over `real_matches`: each club's completed fixtures in kickoff order,
scored W/D/L from its own point of view. Three plain answers:

  * the longest winning streaks the league has produced (top five),
  * the longest unbeaten runs (top five),
  * who is ablaze right now — the longest *current* winning streak at the latest completed matchday.

Streaks are contiguous in kickoff order (the table has exactly one tier-1 fixture per round);
a win run requires wins on the trot, unbeaten allows draws in between. No provider, no authored
claim, no stored counter — arithmetic on the rows.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RealMatch, Team
from app.services.world.almanac import _team_payload, _top_league

TOP_N = 5

__all__ = ["compute_dynasties"]


def _point_of_view(fixture: RealMatch, team_id: str) -> str:
    on_home = fixture.home_team_id == team_id
    gf = fixture.home_goals if on_home else fixture.away_goals
    ga = fixture.away_goals if on_home else fixture.home_goals
    if gf is None or ga is None:
        return "void"
    if gf > ga:
        return "W"
    if gf == ga:
        return "D"
    return "L"


def _runs(record: list[tuple[str, RealMatch]], kind: str) -> list[dict[str, Any]]:
    """All maximal runs of `W` (kind="win") or of W|D (kind="unbeaten"), with provenance."""
    matches_kind = (lambda r: r == "W") if kind == "win" else (lambda r: r != "L")
    runs: list[dict[str, Any]] = []
    cursor = 0
    while cursor < len(record):
        if not matches_kind(record[cursor][0]):
            cursor += 1
            continue
        end = cursor
        while end + 1 < len(record) and matches_kind(record[end + 1][0]):
            end += 1
        length = end - cursor + 1
        threshold = 2 if kind == "win" else 3
        if length >= threshold:
            start = record[cursor][1]
            finish = record[end][1]
            runs.append(
                {
                    "kind": kind,
                    "length": length,
                    "start_kickoff_at": start.kickoff_at.isoformat() if start.kickoff_at else None,
                    "end_kickoff_at": finish.kickoff_at.isoformat() if finish.kickoff_at else None,
                    "start_round": start.round_label,
                    "end_round": finish.round_label,
                }
            )
        cursor = end + 1
    return runs


def _streaks_for_team(fixtures: list[RealMatch], team_id: str) -> dict[str, Any]:
    record: list[tuple[str, RealMatch]] = []
    for fixture in fixtures:
        if team_id not in (fixture.home_team_id, fixture.away_team_id):
            continue
        result = _point_of_view(fixture, team_id)
        if result != "void":
            record.append((result, fixture))

    current_win_run = 0
    for result, _ in reversed(record):
        if result == "W":
            current_win_run += 1
        else:
            break

    return {
        "matches": len(record),
        "current_win_run": current_win_run,
        "win_runs": _runs(record, "win"),
        "unbeaten_runs": _runs(record, "unbeaten"),
    }


def compute_dynasties(session: Session) -> dict[str, Any]:
    league = _top_league(session)
    if league is None:
        return {"available": False, "season": {"label": "2026/27", "kind": "7:3"}}

    fixtures = list(
        session.scalars(
            select(RealMatch)
            .where(RealMatch.competition_id == league.id, RealMatch.status == "completed")
            .where(RealMatch.home_goals.is_not(None), RealMatch.away_goals.is_not(None))
            .order_by(RealMatch.kickoff_at.asc())
        ).all()
    )
    if not fixtures:
        return {
            "available": False,
            "season": {"label": "2026/27", "kind": "7:3"},
            "competition": league.name,
            "competition_slug": league.slug,
        }

    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    team_ids = {fixture.home_team_id for fixture in fixtures} | {fixture.away_team_id for fixture in fixtures}

    win_runs: list[dict[str, Any]] = []
    unbeaten_runs: list[dict[str, Any]] = []
    ablaze: dict[str, Any] = {"team": None, "current_win_run": 0, "matches": 0}

    for team_id in team_ids:
        team = teams.get(team_id)
        summary = _streaks_for_team(fixtures, team_id)
        for run in summary["win_runs"]:
            win_runs.append({**run, "team": _team_payload(team)})
        for run in summary["unbeaten_runs"]:
            unbeaten_runs.append({**run, "team": _team_payload(team)})
        if summary["current_win_run"] > ablaze["current_win_run"]:
            ablaze = {
                "team": _team_payload(team),
                "current_win_run": summary["current_win_run"],
                "matches": summary["matches"],
            }

    win_runs.sort(key=lambda run: (-run["length"], run["start_kickoff_at"] or ""))
    unbeaten_runs.sort(key=lambda run: (-run["length"], run["start_kickoff_at"] or ""))

    return {
        "available": True,
        "season": {"label": "2026/27", "kind": "7:3"},
        "competition": league.name,
        "competition_slug": league.slug,
        "judged": len(fixtures),
        "longest_win": win_runs[0] if win_runs else None,
        "longest_unbeaten": unbeaten_runs[0] if unbeaten_runs else None,
        "win_streaks": win_runs[:TOP_N],
        "unbeaten_runs": unbeaten_runs[:TOP_N],
        "ablaze": ablaze,
    }
