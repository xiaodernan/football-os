"""A career's run through a world cup (M13 Phase 8 item 32).

The generated world already holds a knockout cup for every season it drew: eight entrants, four
quarter-finals, two semi-finals and a final, each with a stored opponent, side and venue
(`world/builder.py`). A career never touched it — its calendar was the league's double round-robin and
nothing else — so the cup was scenery and the only income a career had was its gate, its grants and its
sales.

This module makes the cup a run the career plays. It does not invent a bracket: the world's own rows are
the draw, and the career's result *replaces the slot* the world's simulation filled. A club the world put
in the quarter-finals plays that quarter-final; win it and the semi-final the world drew for that half of
the bracket is next, with the world's other quarter-finalist on the far side; win that and the final is
the world's final, at a neutral venue. The tie is decided by the same engine a league round uses, and a
round won pays a prize into `career_budget_awards` — the table the balance arithmetic already sums, so
this is a new income, not a fifth ledger.

A tie is not a round. It does not advance `career.rounds_played`, score league points, or join the
season's double round-robin; `round_index` is the league round the tie was played after, which is where
its prize lands in the round order the timeline reads.
"""

from __future__ import annotations

import hashlib
from typing import Any, Final

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import CUP_STAGES, Career, CareerBudgetAward, CareerCupTie, CareerGateReceipt, Competition, RealMatch, Team
from app.services.simulation.career import SEED_SPACE, season_bounds
from app.services.simulation.carry_over import record_appearances
from app.services.simulation.engine import MatchInputs, simulate_match
from app.services.simulation.profile import team_profile
from app.services.simulation.service import BLOCK_MINUTES, run_simulation
from app.services.simulation.squad import squad_as_of

CUP_FORMULA: Final = (
    "a cup run is the world's own knockout bracket for the season: the quarter-final the draw gave this "
    "club, then the semi-final drawn for its half, then the final at a neutral venue; each tie is played by "
    "the same engine a league round uses with the career's own overlay and a seed from the career, the "
    "season, the cup and the stage; a tie that ends level is separated on penalties by the match digest; a "
    "home tie pays a gate into `career_gate_receipts` (only the home side takes it, and a final is the "
    "competition's), the eleven's minutes are written to `career_appearances` under the tie so they reach "
    "condition and development, a round won pays its stage's prize into `career_budget_awards` (kind "
    "`cup_prize`) and a round lost ends the run; a challenge career enters no cup, because its budget is "
    "an authored constraint"
)


#: The refusal codes this module mints, in the shape `services/club/answers.py` assembles (§40's rule: a
#: code means one status project-wide). `no_such_cup` is a 404 — the career is not in that cup — and the
#: three state refusals are 409s, beside `career_retired`, which the market already registers.
NOT_FOUND_CODES: Final[tuple[str, ...]] = ("no_such_cup",)
CONFLICT_CODES: Final[tuple[str, ...]] = ("no_cup_run", "cup_run_over", "cannot_play_cup")


class CupRefusal(RuntimeError):
    """A cup tie this career cannot play, with the code and the figures that decided it."""

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), **self.detail}


def _tie_seed(career_id: str, season: str, cup_slug: str, stage: str) -> int:
    """A tie's seed: reproducible from the career, the season, the cup and the stage alone."""
    digest = hashlib.blake2b(f"cup:{career_id}:{season}:{cup_slug}:{stage}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") % SEED_SPACE


def settle(club_goals: int, opponent_goals: int, digest: str) -> dict[str, Any]:
    """Whether the club advanced, how the tie was decided, and the sentence that says so.

    A knockout tie cannot end level. The engine models no shootout, so a drawn tie is separated by the
    match digest — even for the club, odd for the opponent — which keeps the result reproducible from the
    stored report without pretending the engine kicked the penalties.
    """
    if int(club_goals) != int(opponent_goals):
        return {"advanced": int(club_goals) > int(opponent_goals), "decided_by": "goals", "penalty_note": "", "shootout": ""}
    advanced = int(str(digest)[:8], 16) % 2 == 0
    shootout = "4-3" if advanced else "3-4"
    return {
        "advanced": advanced,
        "decided_by": "penalties",
        "penalty_note": f"level after 90; {shootout} on penalties, decided by the digest",
        "shootout": shootout,
    }


def _stage_rows(session: Session, cup_id: str, season: str) -> dict[str, list[RealMatch]]:
    """The world's bracket rows for one cup and season, quarter-finals first, each stage in draw order."""
    rows = list(
        session.scalars(
            select(RealMatch)
            .where(RealMatch.competition_id == cup_id, RealMatch.season == season)
            .order_by(RealMatch.kickoff_at, RealMatch.slug)
        ).all()
    )
    grouped: dict[str, list[RealMatch]] = {stage: [] for stage in CUP_STAGES}
    for row in rows:
        label = str(row.round_label or "")
        for stage in CUP_STAGES:
            if label == stage or label.startswith(f"{stage} "):
                grouped[stage].append(row)
                break
    for stage in CUP_STAGES:
        # Draw order, not kickoff order: the world jitters each matchday by a few days, and a bracket
        # whose quarter-finals swapped places would hand a career the wrong half of the draw.
        grouped[stage].sort(key=lambda row: _draw_order(row))
    return grouped


def _draw_order(row: RealMatch) -> tuple[int, str]:
    """`Quarter-final 3` sorts as 3, and the unnumbered `Final` as 0."""
    label = str(row.round_label or "")
    tail = label.rsplit(" ", 1)[-1]
    return (int(tail) if tail.isdigit() else 0, label)


def _winner(row: RealMatch) -> str | None:
    """The club the world's own simulation sent through: the higher score, home on a draw."""
    if row.home_goals is None or row.away_goals is None:
        return None
    return str(row.home_team_id if int(row.home_goals) >= int(row.away_goals) else row.away_team_id)


def _side_in(row: RealMatch, team_id: str) -> str | None:
    if str(row.home_team_id) == team_id:
        return "home"
    if str(row.away_team_id) == team_id:
        return "away"
    return None


def _drawn_seed(text: str) -> int:
    """A drawn tie's seed: reproducible from the row it resolves, so asking twice names the same club."""
    digest = hashlib.blake2b(f"drawn:{text}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") % SEED_SPACE


def _drawn_match(session: Session, home_id: str, away_id: str, *, seed: int) -> tuple[str, str]:
    """Who wins a tie nobody has played, and the sentence that says how it was decided.

    The world stores next season's cup only as far as its quarter-finals: a bracket cannot be drawn past
    the round whose participants exist. When a career's route first needs a tie the world has not played,
    the engine plays it here from the two clubs' stored profiles and a seed derived from the row. It is a
    pure call — no `sim_matches` row is written for a match nobody watched — so the answer is stable.
    """
    report = simulate_match(
        MatchInputs(
            home=team_profile(session, home_id),
            away=team_profile(session, away_id),
            seed=seed,
            minutes=90,
            block_minutes=BLOCK_MINUTES,
            substitutions=0,
            tactical_shift_minute=0,
            home_momentum=0.0,
            away_momentum=0.0,
        )
    )
    home_goals = int(report["score"]["home"])
    away_goals = int(report["score"]["away"])
    if home_goals != away_goals:
        winner = home_id if home_goals > away_goals else away_id
        return winner, f"engine {home_goals}-{away_goals} (seed {seed})"
    advanced_home = int(str(report["digest"])[:8], 16) % 2 == 0
    return (
        home_id if advanced_home else away_id,
        f"engine level after 90, penalties to the {'home' if advanced_home else 'away'} side (seed {seed})",
    )


def _drawn_winner(session: Session, row: RealMatch) -> tuple[str, str]:
    """Who the world sends through one drawn tie: its stored result, or the engine's reading of the draw."""
    stored = _winner(row)
    if stored is not None:
        return stored, f"the world's stored {row.round_label} result"
    return _drawn_match(session, str(row.home_team_id), str(row.away_team_id), seed=_drawn_seed(str(row.slug)))


def _drawn_half_winner(
    session: Session, cup: Competition, season: str, rows: dict[str, list[RealMatch]], half: int
) -> tuple[str, str]:
    """Who the other half of a drawn bracket sends to the final, with the route that produced him."""
    pair = rows[CUP_STAGES[0]][2 * half : 2 * half + 2]
    first, first_note = _drawn_winner(session, pair[0])
    second, second_note = _drawn_winner(session, pair[1])
    winner, note = _drawn_match(
        session, first, second, seed=_drawn_seed(f"{cup.slug}:{season}:Semi-final {half + 1}")
    )
    return winner, f"{first_note}; {second_note}; semi {note}"


def _slot(session: Session, cup: Competition, season: str, stage_index: int, club_id: str) -> dict[str, Any] | None:
    """Who this club meets at `stage_index`, on which side, and why — read from the world's bracket.

    The club's quarter-final is the row the draw put it in. Every later stage is the row the world drew for
    the club's half; when the world's own simulation did not send the club through, the club takes the slot
    of the club it beat, so the opponent and the side are still the world's and not an invention. `None`
    when the bracket cannot answer — a season the world drew no cup for, or a stage the rows are missing.
    """
    if stage_index < 1 or stage_index > len(CUP_STAGES):
        return None
    rows = _stage_rows(session, str(cup.id), season)
    quarters = rows[CUP_STAGES[0]]
    entered = next((row for row in quarters if _side_in(row, club_id)), None)
    if entered is None:
        return None
    quarter_index = quarters.index(entered)
    if stage_index == 1:
        away = str(entered.away_team_id) if str(entered.home_team_id) == club_id else str(entered.home_team_id)
        side = _side_in(entered, club_id) or "home"
        return {
            "stage": CUP_STAGES[0],
            "stage_index": 1,
            "opponent_team_id": away,
            "side": side,
            "world_match_id": entered.id,
            "world_match_slug": entered.slug,
            "basis": f"the {entered.round_label} the world drew for this club in the {cup.name}",
        }
    # The club's route through the bracket: half = which semi-final, and the club it replaced at each step.
    replaced = _winner(entered) or club_id
    half = quarter_index // 2
    stages = rows[CUP_STAGES[1]]
    if stages:
        semi = stages[half] if half < len(stages) else None
        if semi is not None:
            if stage_index == 2:
                other = str(semi.away_team_id) if str(semi.home_team_id) == str(replaced) else str(semi.home_team_id)
                side = _side_in(semi, str(replaced)) or _side_in(semi, club_id) or "home"
                return {
                    "stage": CUP_STAGES[1],
                    "stage_index": 2,
                    "opponent_team_id": other,
                    "side": side,
                    "world_match_id": semi.id,
                    "world_match_slug": semi.slug,
                    "basis": f"the {semi.round_label} the world drew for the half this club's quarter-final feeds",
                }
            replaced = _winner(semi) or str(replaced)
    if stage_index == 2:
        # A season drawn only to its quarter-finals (the world's next season): the semi-final's other
        # participant is the winner of the adjacent quarter-final, which nobody has played yet. The
        # engine resolves that tie from the stored draw, and the bracket rule "the first quarter-final of
        # a half hosts the semi" decides the side.
        opponent, note = _drawn_winner(session, quarters[2 * half + (1 - quarter_index % 2)])
        return {
            "stage": CUP_STAGES[1],
            "stage_index": 2,
            "opponent_team_id": opponent,
            "side": "home" if quarter_index % 2 == 0 else "away",
            "world_match_id": None,
            "world_match_slug": "",
            "basis": (
                f"the Semi-final is not a drawn row yet: Quarter-final {2 * half + 1} meets Quarter-final "
                f"{2 * half + 2}, and the adjacent tie decides this opponent ({note})"
            ),
        }
    final = rows[CUP_STAGES[2]][0] if rows[CUP_STAGES[2]] else None
    if final is None:
        opponent, note = _drawn_half_winner(session, cup, season, rows, 1 - half)
        return {
            "stage": CUP_STAGES[2],
            "stage_index": 3,
            "opponent_team_id": opponent,
            "side": "home" if half == 0 else "away",
            "world_match_id": None,
            "world_match_slug": "",
            "basis": (
                f"the Final is not a drawn row yet: the other half of the bracket decides this opponent "
                f"({note})"
            ),
        }
    other = str(final.away_team_id) if str(final.home_team_id) == str(replaced) else str(final.home_team_id)
    side = _side_in(final, str(replaced)) or _side_in(final, club_id) or "home"
    return {
        "stage": CUP_STAGES[2],
        "stage_index": 3,
        "opponent_team_id": other,
        "side": side,
        "world_match_id": final.id,
        "world_match_slug": final.slug,
        "basis": f"the {final.round_label} the world drew, played at a neutral venue",
    }

def _ties_of(session: Session, career: Career, *, season_index: int, cup_slug: str) -> list[CareerCupTie]:
    return list(
        session.scalars(
            select(CareerCupTie)
            .where(
                CareerCupTie.career_id == career.id,
                CareerCupTie.season_index == int(season_index),
                CareerCupTie.cup_slug == cup_slug,
            )
            .order_by(CareerCupTie.stage_index)
        ).all()
    )


def _prizes(session: Session, career: Career, *, season_index: int) -> dict[str, Any]:
    """Every cup prize this career has been paid in the season, keyed by the award's own stage string."""
    rows = list(
        session.scalars(
            select(CareerBudgetAward).where(
                CareerBudgetAward.career_id == career.id,
                CareerBudgetAward.season_index == int(season_index),
                CareerBudgetAward.kind == "cup_prize",
            )
        ).all()
    )
    return {str(row.stage): row for row in rows}


def cup_tie_row(tie: CareerCupTie, *, prize: Any | None = None, gate: Any | None = None) -> dict[str, Any]:
    """One played tie as the page and the wire read it: the score, how it was settled and what it paid."""
    return {
        "id": tie.id,
        "season_index": int(tie.season_index),
        "season": tie.season,
        "cup_slug": tie.cup_slug,
        "cup_name": tie.cup_name,
        "stage": tie.stage,
        "stage_index": int(tie.stage_index),
        "round_index": int(tie.round_index),
        "side": tie.side,
        "opponent_team_id": tie.opponent_team_id,
        "opponent_name": tie.opponent_name,
        "opponent_short": tie.opponent_short,
        "venue_name": tie.venue_name,
        "club_goals": int(tie.club_goals),
        "opponent_goals": int(tie.opponent_goals),
        "outcome": tie.outcome,
        "decided_by": tie.decided_by,
        "penalty_note": tie.penalty_note,
        "score": f"{int(tie.club_goals)}-{int(tie.opponent_goals)}",
        "digest": tie.digest,
        "seed": int(tie.seed),
        "model_version": tie.model_version,
        "match_slug": tie.match_slug,
        "match_path": f"/simulate/{tie.match_slug}" if tie.match_slug else None,
        "world_match_id": tie.world_match_id,
        "basis": tie.basis,
        "prize": (
            {
                "amount": int(prize.amount),
                "units": prize.amount_units,
                "budget_after": int(prize.budget_after),
                "basis": prize.basis,
            }
            if prize is not None
            else None
        ),
        "gate": (
            {
                "amount": int(gate.amount),
                "units": gate.amount_units,
                "attendance": int(gate.attendance),
                "ticket_price": int(gate.ticket_price),
                "budget_after": int(gate.budget_after),
                "basis": gate.basis,
            }
            if gate is not None
            else None
        ),
        "created_at": tie.created_at.isoformat() if tie.created_at else None,
    }


def _run(
    session: Session,
    career: Career,
    cup: Competition,
    *,
    season: str,
    season_index: int,
    club: Team | None,
    prizes: dict[str, Any],
    gates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One cup's run for this career: what it has played, what is next, and what it has paid."""
    gates = gates or {}
    ties = _ties_of(session, career, season_index=season_index, cup_slug=str(cup.slug))
    status = "live"
    for tie in ties:
        if str(tie.outcome) != "W":
            status = "eliminated"
    stage_index = int(ties[-1].stage_index) + 1 if ties else 1
    if status == "live" and len(ties) >= len(CUP_STAGES):
        status = "won" if all(str(tie.outcome) == "W" for tie in ties) else "eliminated"
    reason = None
    slot: dict[str, Any] | None = None
    if status == "live" and career.club_id:
        slot = _slot(session, cup, season, stage_index, str(career.club_id))
        if slot is None:
            status = "unavailable"
            reason = f"the world's {season} bracket for the {cup.name} has no {CUP_STAGES[min(stage_index, len(CUP_STAGES)) - 1]} row this club could reach"
        else:
            opponent = session.get(Team, slot["opponent_team_id"]) if slot.get("opponent_team_id") else None
            if slot["stage"] == "Final":
                venue_name, venue_club = "Neutral venue", ""
            elif slot["side"] == "home":
                venue_name, venue_club = (club.stadium if club is not None else ""), career.club_name
            else:
                venue_name, venue_club = (opponent.stadium if opponent is not None else ""), (opponent.name if opponent is not None else "")
            slot = {
                **slot,
                "round_index": int(career.rounds_played) + 1,
                "opponent_name": opponent.name if opponent is not None else "",
                "opponent_short": opponent.short_name if opponent is not None else "",
                "venue_name": venue_name,
                "venue_club": venue_club,
                "seed": _tie_seed(str(career.id), season, str(cup.slug), str(slot["stage"])),
            }
    rows = [
        cup_tie_row(tie, prize=prizes.get(f"{tie.cup_slug}:{tie.stage}"), gate=gates.get(str(tie.id))) for tie in ties
    ]
    won = sum(1 for tie in ties if str(tie.outcome) == "W")
    return {
        "cup_id": cup.id,
        "cup_slug": cup.slug,
        "cup_name": cup.name,
        "region": cup.region,
        "season": season,
        "season_index": int(season_index),
        "stage": {"index": stage_index, "label": CUP_STAGES[min(stage_index, len(CUP_STAGES)) - 1], "of": len(CUP_STAGES)},
        "status": status,
        "reason": reason,
        "next": slot,
        "ties": rows,
        "record": {
            "played": len(ties),
            "won": won,
            "lost": len(ties) - won,
            "goals_for": sum(int(tie.club_goals) for tie in ties),
            "goals_against": sum(int(tie.opponent_goals) for tie in ties),
        },
        "prizes": {
            "total": sum(int(row["prize"]["amount"]) for row in rows if row["prize"] is not None),
            "rows": sum(1 for row in rows if row["prize"] is not None),
        },
        "gates": {
            "total": sum(int(row["gate"]["amount"]) for row in rows if row["gate"] is not None),
            "rows": sum(1 for row in rows if row["gate"] is not None),
        },
        "formula": CUP_FORMULA,
    }


def cup_view(session: Session, career: Career, *, bounds: dict[str, Any] | None = None) -> dict[str, Any]:
    """Every cup the world entered this career in this season, with the run each one is on.

    The bracket is the world's, so the block reports what the world drew rather than what the career
    might prefer: a club the draw left out has no run, a season the world drew no cup for has none
    either, and a challenge career has none at all because its budget is an authored number a prize
    would silently raise. Each of those answers carries the sentence that says so.
    """
    if career.challenge_slug:
        return {
            "available": False,
            "reason": "a challenge career's budget is an authored constraint printed when the run starts, so it enters no cup",
            "season": career.season,
            "runs": [],
            "totals": {"runs": 0, "ties": 0, "won": 0, "prizes": 0, "gates": 0},
            "formula": CUP_FORMULA,
        }
    if not career.club_id:
        return {
            "available": False,
            "reason": "this career has no club, so it has no cup to enter",
            "season": career.season,
            "runs": [],
            "totals": {"runs": 0, "ties": 0, "won": 0, "prizes": 0, "gates": 0},
            "formula": CUP_FORMULA,
        }
    bounds = bounds if bounds is not None else season_bounds(session, career)
    season = str(bounds.get("season") or career.season)
    season_index = int(bounds["index"])
    club = session.get(Team, career.club_id)
    drawn = list(
        session.scalars(
            select(RealMatch.competition_id)
            .where(
                RealMatch.season == season,
                or_(RealMatch.home_team_id == career.club_id, RealMatch.away_team_id == career.club_id),
            )
            .distinct()
        ).all()
    )
    cups: list[Competition] = []
    if drawn:
        cups = list(
            session.scalars(
                select(Competition).where(Competition.id.in_(sorted({str(row) for row in drawn if row})), Competition.kind == "cup").order_by(Competition.slug)
            ).all()
        )
    prizes = _prizes(session, career, season_index=season_index)
    gate_rows = list(
        session.scalars(
            select(CareerGateReceipt).where(
                CareerGateReceipt.career_id == career.id, CareerGateReceipt.tie_id.is_not(None)
            )
        ).all()
    )
    gates = {str(row.tie_id): row for row in gate_rows}
    runs = [
        _run(session, career, cup, season=season, season_index=season_index, club=club, prizes=prizes, gates=gates)
        for cup in cups
    ]
    return {
        "available": bool(runs),
        "reason": None if runs else f"the world's {season} season drew no cup bracket this club entered",
        "season": season,
        "season_index": season_index,
        "runs": runs,
        "totals": {
            "runs": len(runs),
            "ties": sum(run["record"]["played"] for run in runs),
            "won": sum(run["record"]["won"] for run in runs),
            "prizes": sum(run["prizes"]["total"] for run in runs),
            "gates": sum(run["gates"]["total"] for run in runs),
        },
        "formula": CUP_FORMULA,
    }


def play_cup_tie(session: Session, career: Career, *, cup: str | None = None) -> tuple[CareerCupTie, Any]:
    """Play the next tie of one live cup run, store it, and pay the prize if it was won.

    The only path that plays a tie, so the rules live here: a retired career plays nothing, a run that is
    over refuses rather than inventing a quarter-final, and the tie is decided by the same engine a league
    round uses — with the career's own overlay, so a signing reaches the cup as well as the league. A tie
    that ends level is separated on penalties by the match digest, which keeps the result reproducible
    without pretending the engine models a shootout.
    """
    if career.status != "active":
        raise CupRefusal("career_retired", "this career is retired; take charge again before playing a cup tie")
    view = cup_view(session, career)
    if not view["available"]:
        raise CupRefusal("no_cup_run", str(view["reason"]))
    runs = view["runs"]
    if cup:
        wanted = cup.strip()
        runs = [run for run in runs if wanted in (run["cup_slug"], run["cup_id"])]
        if not runs:
            raise CupRefusal("no_such_cup", f"this career is not entered in {cup!r} this season")
    live = [run for run in runs if run["status"] == "live" and run.get("next")]
    if not live:
        ended = runs[0] if runs else None
        raise CupRefusal(
            "cup_run_over",
            "this season's cup run is over"
            if ended is not None and ended["status"] == "won"
            else "this season's cup run has ended",
            runs=[{"cup_slug": run["cup_slug"], "status": run["status"], "played": run["record"]["played"]} for run in runs],
        )
    run = live[0]
    slot = run["next"]
    club_id = str(career.club_id)
    opponent_id = str(slot["opponent_team_id"])
    home_id, away_id = (club_id, opponent_id) if slot["side"] == "home" else (opponent_id, club_id)
    overlay = squad_as_of(session, career, int(career.rounds_played) + 1)
    match = run_simulation(
        session,
        owner_id=career.owner_id,
        home_team_id=home_id,
        away_team_id=away_id,
        home_system=(career.system_slug or None) if slot["side"] == "home" else None,
        away_system=None if slot["side"] == "home" else (career.system_slug or None),
        seed=int(slot["seed"]),
        minutes=90,
        home_squad=overlay if home_id == club_id else None,
        away_squad=overlay if away_id == club_id else None,
    )
    club_goals = int(match.home_goals) if slot["side"] == "home" else int(match.away_goals)
    opponent_goals = int(match.away_goals) if slot["side"] == "home" else int(match.home_goals)
    ended = settle(club_goals, opponent_goals, str(match.digest))
    advanced = bool(ended["advanced"])
    club = session.get(Team, club_id)
    opponent = session.get(Team, opponent_id)
    if str(slot["stage"]) == "Final":
        venue_name = "Neutral venue"
    elif slot["side"] == "home":
        venue_name = club.stadium if club is not None else ""
    else:
        venue_name = opponent.stadium if opponent is not None else ""
    tie = CareerCupTie(
        id=new_public_id("ctie"),
        career_id=career.id,
        season_index=int(run["season_index"]),
        season=str(run["season"]),
        cup_id=str(run["cup_id"]),
        cup_slug=str(run["cup_slug"]),
        cup_name=str(run["cup_name"]),
        stage=str(slot["stage"]),
        stage_index=int(slot["stage_index"]),
        round_index=int(career.rounds_played),
        match_id=match.id,
        match_slug=match.slug,
        digest=match.digest,
        model_version=match.model_version,
        seed=int(match.seed),
        side=str(slot["side"]),
        opponent_team_id=opponent_id,
        opponent_name=opponent.name if opponent is not None else str(slot.get("opponent_name") or ""),
        opponent_short=opponent.short_name if opponent is not None else str(slot.get("opponent_short") or ""),
        venue_name=venue_name,
        club_goals=club_goals,
        opponent_goals=opponent_goals,
        outcome="W" if advanced else "L",
        decided_by=str(ended["decided_by"]),
        penalty_note=str(ended["penalty_note"]),
        world_match_id=slot.get("world_match_id"),
        basis=f"{slot['basis']}; {run['cup_name']} {slot['stage']}, {slot['side']} against {opponent.name if opponent is not None else ''}".strip(),
        data_origin="simulation",
        is_demo_data=True,
    )
    session.add(tie)
    session.commit()
    session.refresh(tie)
    # The tie leaves the same two traces a league round does: the eleven that played it (M13 item 34, so
    # its minutes reach condition and the development curve) and, for a home tie, the gate it earned. The
    # gate is written before the prize so the prize's stored `budget_after` includes it, which is the order
    # the timeline reads.
    _trace_tie(session, career, tie=tie, match=match, overlay=overlay)
    from app.services.simulation.market import pay_cup_gate, pay_cup_prize, pay_upkeep

    pay_cup_gate(session, career, tie=tie)
    # A home tie opens the ground too, so it pays the same running cost immediately after its gate and
    # before its prize. A final at a neutral venue and an away tie pay neither.
    pay_upkeep(session, career, tie=tie)
    if advanced:
        pay_cup_prize(session, career, tie=tie)
    return tie, match


def _trace_tie(session: Session, career: Career, *, tie: CareerCupTie, match: Any, overlay: Any) -> None:
    """Write one appearance row per player this tie selected, keyed by the tie (M13 Phase 9 item 34).

    The eleven is rebuilt from the same rows the engine played with and checked against the names in the
    stored report, exactly as a league round is. A cup minute is a minute of load: `carry_over` sums these
    rows into the condition the next round reads, and `development_view` sums them into the curve. No
    `career_developments` row is written for a tie — that table is keyed by league round, and the tie's
    minutes reach the curve at the next round's write, when they are part of the cumulative total.
    """
    side = "home" if str(match.home_team_id) == str(career.club_id) else "away"
    profile = team_profile(session, career.club_id or "", system_slug=career.system_slug or None, squad=overlay)
    recorded = [
        str(row.get("player", ""))
        for row in list(match.report.get("sides", {}).get(side, {}).get("lineup", []))
        if isinstance(row, dict)
    ]
    selected = [name for _player_id, _slug, name, _position, _band in profile.selected]
    if recorded and recorded != selected:
        return
    record_appearances(
        session,
        career,
        round_index=int(tie.round_index),
        lineup=list(profile.selected),
        side=side,
        minutes=int(match.minutes),
        opponent_name=str(tie.opponent_name),
        tie_id=str(tie.id),
        context=f"the {tie.cup_name} {tie.stage}",
    )
