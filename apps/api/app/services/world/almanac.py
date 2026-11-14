"""The world's own almanac — the season, summed.

The world already holds every column the almanac reads: `real_players` for the raw figures
(appearances, goals, assists, rating, clean sheets, weighted cards, age), and `real_matches`
for the table the championship is lifted over. **The door never invents a figure and never
authors a sentence.** It returns rows and keys; the web page prints the language.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Competition, RealMatch, RealPlayer, Team

STAT_MIN_APPEARANCES: int = 15
STAT_MIN_MINUTES: int = 900
CARD_WEIGHT: int = 3  # one red is three yellows — the almanac's discipline column
PORTRAIT_LABEL_GOALS = "goals"
PORTRAIT_LABEL_ASSISTS = "assists"
PORTRAIT_LABEL_CLEAN_SHEETS = "clean_sheets"
PORTRAIT_LABEL_INVOLVEMENT = "involvement"
PORTRAIT_LABEL_RATING = "rating"
PORTRAIT_LABEL_WEIGHTED_CARDS = "weighted_cards"

AwardKey = str  # the catalogue maps each key to its own name+hint — any unknown key renders 404


def _player_payload(player: RealPlayer, stat: Any) -> dict[str, Any]:
    return {
        "slug": player.slug,
        "id": player.id,
        "name": player.name,
        "position": player.position,
        "overall": player.overall,
        "age": player.age,
        "nation": player.nation,
        "path": f"/player/{player.slug}",
        "stat": float(stat) if stat is not None else None,
        "stat_label": stat if isinstance(stat, str) else None,
        "data_origin": "synthetic",
        "is_demo_data": True,
    }


def _team_payload(team: Team | None, **extra: Any) -> dict[str, Any]:
    if team is None:
        return {"name": "Data unavailable", "slug": None, "path": None, **extra}
    return {
        "id": team.id,
        "slug": team.slug,
        "name": team.name,
        "path": f"/team/{team.slug}",
        **extra,
    }


def _award(
    key: AwardKey,
    winner: RealPlayer | None,
    win_stat: Any,
    runner_ups: list[tuple[RealPlayer, Any]],
) -> dict[str, Any]:
    return {
        "key": key,
        "winner": _player_payload(winner, win_stat) if winner is not None else None,
        "runner_ups": [_player_payload(player, stat) for player, stat in runner_ups],
    }


def _top_league(session: Session) -> Competition | None:
    """The same league the whole almanac speaks for — the top tier, name-broken ties.

    The world's pyramid has a tier-1 league and at least one tier-2; the almanac honours one
    competition, never two, so the manager figure and the title race cannot drift apart.
    """
    return session.scalar(
        select(Competition)
        .where(Competition.kind == "league")
        .order_by(Competition.tier.asc(), Competition.name.asc())
        .limit(1)
    )


def _compute_league_table(session: Session) -> dict[str, Any]:
    """Recompute the league table from completed league fixtures, same way `world.py` does."""
    league = _top_league(session)
    if league is None:
        return {"available": False}

    fixtures = list(
        session.scalars(
            select(RealMatch)
            .where(RealMatch.competition_id == league.id, RealMatch.status == "completed")
            .order_by(RealMatch.kickoff_at.asc())
        ).all()
    )
    table: dict[str, dict[str, int]] = {}
    for fixture in fixtures:
        if fixture.home_goals is None or fixture.away_goals is None:
            continue
        for team_id, on_home in ((fixture.home_team_id, True), (fixture.away_team_id, False)):
            stats = table.setdefault(
                team_id,
                {"played": 0, "won": 0, "drawn": 0, "lost": 0, "goals_for": 0, "goals_against": 0, "points": 0},
            )
            gf = fixture.home_goals if on_home else fixture.away_goals
            ga = fixture.away_goals if on_home else fixture.home_goals
            stats["played"] += 1
            stats["goals_for"] += gf or 0
            stats["goals_against"] += ga or 0
            if fixture.home_goals == fixture.away_goals:
                stats["drawn"] += 1
                stats["points"] += 1
            elif (on_home and fixture.home_goals > fixture.away_goals) or (not on_home and fixture.away_goals > fixture.home_goals):
                stats["won"] += 1
                stats["points"] += 3
            else:
                stats["lost"] += 1
    return {
        "available": True,
        "competition": league.name,
        "competition_slug": league.slug,
        "table": table,
    }


def _title_race(session: Session) -> dict[str, Any]:
    computed = _compute_league_table(session)
    if not computed["available"]:
        return {"available": False}
    rows = sorted(
        computed["table"].items(),
        key=lambda kv: (-kv[1]["points"], -(kv[1]["goals_for"] - kv[1]["goals_against"]), -kv[1]["goals_for"]),
    )
    if len(rows) < 2:
        return {"available": False}
    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    champ_id, champ = rows[0]
    runner_id, runner = rows[1]
    champ_team = teams.get(champ_id)
    runner_team = teams.get(runner_id)
    return {
        "available": True,
        "competition": computed["competition"],
        "competition_slug": computed["competition_slug"],
        "champion": {
            "id": champ_id,
            "slug": getattr(champ_team, "slug", ""),
            "name": getattr(champ_team, "name", "Data unavailable"),
            "path": f"/team/{getattr(champ_team, 'slug', '')}" if champ_team is not None else None,
            "played": champ["played"],
            "won": champ["won"],
            "drawn": champ["drawn"],
            "lost": champ["lost"],
            "goals_for": champ["goals_for"],
            "goals_against": champ["goals_against"],
            "points": champ["points"],
            "goal_difference": champ["goals_for"] - champ["goals_against"],
        },
        "runner_up": {
            "id": runner_id,
            "slug": getattr(runner_team, "slug", ""),
            "name": getattr(runner_team, "name", "Data unavailable"),
            "path": f"/team/{getattr(runner_team, 'slug', '')}" if runner_team is not None else None,
            "played": runner["played"],
            "won": runner["won"],
            "drawn": runner["drawn"],
            "lost": runner["lost"],
            "goals_for": runner["goals_for"],
            "goals_against": runner["goals_against"],
            "points": runner["points"],
            "goal_difference": runner["goals_for"] - runner["goals_against"],
        },
        "margin": champ["points"] - runner["points"],
        "gd_margin": (champ["goals_for"] - champ["goals_against"]) - (runner["goals_for"] - runner["goals_against"]),
    }


def compute_almanac(session: Session) -> dict[str, Any]:
    """The whole almanac, computed from the world's own stored rows."""
    players = list(
        session.scalars(
            select(RealPlayer).order_by(RealPlayer.goals.desc(), RealPlayer.assists.desc(), RealPlayer.overall.desc())
        ).all()
    )
    if not players:
        return {"awards": [], "best_manager": None, "season": {"label": "2026", "kind": "7:3"}}

    golden_boot_pool = sorted(players, key=lambda p: (p.goals, p.assists, p.overall), reverse=True)[:4]
    golden_boot, *golden_boot_rest = golden_boot_pool

    playmaker_pool = sorted(players, key=lambda p: (p.assists, p.goals, p.overall), reverse=True)[:4]
    playmaker, *playmaker_rest = playmaker_pool

    complete_pool = sorted(players, key=lambda p: ((p.goals + p.assists), p.goals, p.assists), reverse=True)[:4]
    complete_leader, *complete_rest = complete_pool

    glove_pool = sorted(players, key=lambda p: (p.clean_sheets, p.overall), reverse=True)[:4]
    glove_winner, *glove_rest = glove_pool

    poty_pool = [p for p in players if p.appearances >= STAT_MIN_APPEARANCES]
    player_season_pool = sorted(poty_pool, key=lambda p: (p.rating, p.minutes), reverse=True)[:4]
    if player_season_pool:
        season_winner, *season_rest = player_season_pool
        poty_award = _award(
            "player_of_season",
            season_winner,
            season_winner.rating,
            [(p, p.rating) for p in season_rest],
        )
    else:
        poty_award = _award("player_of_season", None, None, [])

    enforcer_pool = sorted(players, key=lambda p: (p.yellow_cards + CARD_WEIGHT * p.red_cards, p.yellow_cards), reverse=True)[:4]
    enforcer_winner, *enforcer_rest = enforcer_pool

    young_pool = [p for p in players if p.age <= 23]
    if young_pool:
        breakthrough_pool = sorted(young_pool, key=lambda p: ((p.goals + p.assists), p.minutes), reverse=True)[:4]
        breakthrough_winner, *breakthrough_rest = breakthrough_pool
    else:
        breakthrough_winner, breakthrough_rest = None, []

    league_competition = _top_league(session)
    best_manager: dict[str, Any] | None = None
    if league_competition is not None:
        fixtures = list(
            session.scalars(
                select(RealMatch).where(
                    RealMatch.competition_id == league_competition.id,
                    RealMatch.status == "completed",
                )
            ).all()
        )
        teams = {team.id: team for team in session.scalars(select(Team)).all()}
        table: dict[str, dict[str, Any]] = {}

        def side(team_id: str) -> dict[str, Any]:
            return table.setdefault(
                team_id,
                {
                    "team_id": team_id,
                    "played": 0,
                    "won": 0,
                    "drawn": 0,
                    "lost": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "points": 0,
                },
            )

        for fixture in fixtures:
            if fixture.home_goals is None or fixture.away_goals is None:
                continue
            home, away = side(fixture.home_team_id), side(fixture.away_team_id)
            home["played"] += 1
            away["played"] += 1
            home["goals_for"] += fixture.home_goals
            home["goals_against"] += fixture.away_goals
            away["goals_for"] += fixture.away_goals
            away["goals_against"] += fixture.home_goals
            if fixture.home_goals == fixture.away_goals:
                home["drawn"] += 1
                away["drawn"] += 1
                home["points"] += 1
                away["points"] += 1
            elif fixture.home_goals > fixture.away_goals:
                home["won"] += 1
                away["lost"] += 1
                home["points"] += 3
            else:
                away["won"] += 1
                home["lost"] += 1
                away["points"] += 3

        rows = sorted(
            table.values(),
            key=lambda row: (-row["points"], -(row["goals_for"] - row["goals_against"]), -row["goals_for"]),
        )
        if rows:
            top = rows[0]
            best_manager = {
                "team": _team_payload(teams.get(top["team_id"])),
                "competition_id": league_competition.id,
                "competition_name": league_competition.name,
                "competition_slug": league_competition.slug,
                "played": top["played"],
                "won": top["won"],
                "drawn": top["drawn"],
                "lost": top["lost"],
                "goals_for": top["goals_for"],
                "goals_against": top["goals_against"],
                "points": top["points"],
                "data_origin": "synthetic",
            }

    return {
        "season": {"label": "2026/27", "kind": "7:3"},
        "awards": [
            _award("golden_boot", golden_boot, golden_boot.goals, [(p, p.goals) for p in golden_boot_rest]),
            _award("playmaker_crown", playmaker, playmaker.assists, [(p, p.assists) for p in playmaker_rest]),
            _award(
                "complete_forward",
                complete_leader,
                complete_leader.goals + complete_leader.assists,
                [(p, p.goals + p.assists) for p in complete_rest],
            ),
            _award(
                "golden_glove",
                glove_winner,
                glove_winner.clean_sheets,
                [(p, p.clean_sheets) for p in glove_rest],
            ),
            poty_award,
            _award(
                "the_enforcer",
                enforcer_winner,
                enforcer_winner.yellow_cards + CARD_WEIGHT * enforcer_winner.red_cards,
                [(p, p.yellow_cards + CARD_WEIGHT * p.red_cards) for p in enforcer_rest],
            ),
            _award(
                "breakthrough",
                breakthrough_winner,
                (breakthrough_winner.goals + breakthrough_winner.assists) if breakthrough_winner else None,
                [(p, p.goals + p.assists) for p in breakthrough_rest] if breakthrough_rest else [],
            ),
        ],
        "best_manager": best_manager,
        "portrait": {
            "golden_boot": _player_payload(golden_boot, golden_boot.goals),
            "playmaker": _player_payload(playmaker, playmaker.assists),
        },
        "title_race": _title_race(session),
    }


__all__ = [
    "STAT_MIN_APPEARANCES",
    "STAT_MIN_MINUTES",
    "CARD_WEIGHT",
    "compute_almanac",
]
