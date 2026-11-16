"""The Upset Register — the tier-1 underdog's arithmetic, written down.

Every completed tier-1 fixture is scored by the combined `overall` of each squad's eleven
strongest. The favorite is the side with the higher rating; the underdog is the other one.
Three plain answers come out of the same walk — no provider, no prediction, no authored
miracle, only what the rows say:

  * the largest rating gaps the underdog closed to win (the five biggest upsets),
  * the fortress draws — a gap of eight or more that still ended level,
  * the season's tally: how many upsets, how many fortresses, the mean gap that fell.

A rating is not fate. The register celebrates the result, and prints the gap it overcame,
so a reader can see for themselves how far the seed fell short of its own arithmetic.

This door shares the strength rule with the Noise Dossier on purpose: the same eleven,
the same average, so the two registers can be read side by side. What they disagree on is
the question — noise scores the caller, the register honours the dog.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Competition, RealMatch, Team
from app.services.world.almanac import _team_payload, _top_league
from app.services.world.noise import _actual, _team_strength

FORTRESS_GAP = 8.0
TOP_N = 5

__all__ = ["compute_upsets"]


def _completed_fixtures(session: Session, league: Competition) -> list[RealMatch]:
    return list(
        session.scalars(
            select(RealMatch)
            .where(RealMatch.competition_id == league.id, RealMatch.status == "completed")
            .where(RealMatch.home_goals.is_not(None), RealMatch.away_goals.is_not(None))
            .order_by(RealMatch.kickoff_at.asc())
        ).all()
    )


def _fixture_row(
    fixture: RealMatch,
    teams: dict[str, Team],
    rating_gap: float,
    favorite: str,
    kind: str,
) -> dict[str, Any]:
    return {
        "slug": fixture.slug,
        "path": f"/match/{fixture.slug}",
        "kickoff_at": fixture.kickoff_at.isoformat() if fixture.kickoff_at else None,
        "round_label": fixture.round_label,
        "home": _team_payload(teams.get(fixture.home_team_id)),
        "away": _team_payload(teams.get(fixture.away_team_id)),
        "home_goals": fixture.home_goals,
        "away_goals": fixture.away_goals,
        "favorite": favorite,
        "rating_gap": round(rating_gap, 2),
        "kind": kind,
    }


def compute_upsets(session: Session) -> dict[str, Any]:
    league = _top_league(session)
    if league is None:
        return {"available": False, "season": {"label": "2026/27", "kind": "7:3"}}

    fixtures = _completed_fixtures(session, league)
    if not fixtures:
        return {
            "available": False,
            "season": {"label": "2026/27", "kind": "7:3"},
            "competition": league.name,
            "competition_slug": league.slug,
        }

    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    strength_cache: dict[str, float | None] = {}
    for team_id in {f.home_team_id for f in fixtures} | {f.away_team_id for f in fixtures}:
        strength_cache[team_id] = _team_strength(session, team_id)

    judged = 0
    rows: list[dict[str, Any]] = []
    for fixture in fixtures:
        home_s = strength_cache.get(fixture.home_team_id)
        away_s = strength_cache.get(fixture.away_team_id)
        if home_s is None or away_s is None or abs(home_s - away_s) < 0.01:
            continue
        judged += 1
        favorite = "home" if home_s > away_s else "away"
        actual = _actual(fixture.home_goals or 0, fixture.away_goals or 0)
        gap = abs(home_s - away_s)
        if actual != "draw" and actual != favorite:
            rows.append(_fixture_row(fixture, teams, gap, favorite, "upset"))
        elif actual == "draw" and gap >= FORTRESS_GAP:
            rows.append(_fixture_row(fixture, teams, gap, favorite, "fortress"))

    upsets = [row for row in rows if row["kind"] == "upset"]
    fortresses = [row for row in rows if row["kind"] == "fortress"]
    upsets.sort(key=lambda row: (-row["rating_gap"], -abs((row["home_goals"] or 0) - (row["away_goals"] or 0))))
    fortresses.sort(key=lambda row: -row["rating_gap"])
    recent_upsets = sorted(upsets, key=lambda row: row["kickoff_at"] or "", reverse=True)[:TOP_N]

    mean_gap = round(sum(row["rating_gap"] for row in upsets) / len(upsets), 2) if upsets else 0.0
    return {
        "available": True,
        "season": {"label": "2026/27", "kind": "7:3"},
        "competition": league.name,
        "competition_slug": league.slug,
        "judged": judged,
        "upset_count": len(upsets),
        "fortress_count": len(fortresses),
        "mean_upset_gap": mean_gap,
        "upset_rate_pct": round(100 * len(upsets) / judged, 2) if judged else 0.0,
        "fortress_gap": FORTRESS_GAP,
        "biggest_upset": upsets[0] if upsets else None,
        "fortress": fortresses[0] if fortresses else None,
        "upsets": upsets[:TOP_N],
        "fortresses": fortresses[:TOP_N],
        "recent_upsets": recent_upsets,
    }
