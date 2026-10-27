"""What a played round leaves behind, and what the next round reads from it (spec §20).

Career Mode decided every round with the same inputs: the club's stored squad rows and each player's
stored `form`, which the world generator wrote once and nothing updates. So a career that had played
eight matches fielded a side exactly as fresh as one that had played none, and the 100 training sessions
in `real_training_sessions` — each with a `load_units` figure on it — reached nothing but a player's
page. §20 asks for squad and training status to carry over between matches; this module is the whole of
what this build can honestly mean by that.

Three rules:

1. **The trace is a row, not a re-derivation.** `career_appearances` records who was selected for the
   career's side in each round and at how many minutes, written when the round is played. A load that had
   to be recomputed out of `sim_matches.report` would disappear the moment its owner deleted the match.
2. **Load is a window with a decay, and the arithmetic is published.** Each previous round counts at
   half the weight of the one before it, so the figure is dominated by the last fixture — which is what
   "carry over between matches" is about — without forgetting the two before it.
3. **Training is a reserve, not a bonus track.** A player with sessions on file gives back part of the
   load his minutes put on him, and the most that can be given back is a stated fraction. A player with
   no training record is not punished below what his minutes alone do.

Where it reaches the engine: `profile.team_profile` folds each selected player's condition into the side's
form index, and the engine's fatigue term already reads that index — "a lower-form side fades further".
So a tired side is not given a new multiplier; it is measured as what the model already says a lower form
is. With no appearances on file the map is empty and the numbers are bit-for-bit what they were before
this module existed, which is why stored matches from other pages still replay to their own digests.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import Career, CareerAppearance, RealTrainingSession

# How far back a round looks, and how much each earlier round still costs.
RECENT_ROUNDS: Final = 3
DECAY: Final = 0.5

# A window held at full match minutes in every round takes condition down by this much; training gives
# back at most this much, and its reserve is complete at this many load units on file. The two bounds
# below bind at different points of that arithmetic: an untrained starter with a full window sits at
# 0.55 raw and the floor lifts him to 0.60, while the same starter with a complete reserve is at 0.70,
# inside both.
FATIGUE_DEPTH: Final = 0.45
TRAINING_RESERVE: Final = 0.15
TRAINING_RESERVE_LOAD: Final = 1200
CONDITION_FLOOR: Final = 0.60
CONDITION_CEILING: Final = 1.00

# The load a player can carry is measured against the most the window itself can hold — a full match in
# each of the three rounds, decayed — so a saturated starter reads as 1.0 of the scale rather than as
# 1.75 of a single match, and the depth and the reserve stay comparable to each other.
FULL_MATCH_MINUTES: Final = 90.0
WINDOW_LOAD: Final = FULL_MATCH_MINUTES * sum(DECAY**index for index in range(RECENT_ROUNDS))
FORM_WEIGHT: Final = "0.5 + 0.5·condition"

LOAD_FORMULA: Final = (
    f"load_units = Σ over the {RECENT_ROUNDS} rounds before this one of minutes played × {DECAY}^(rounds since); "
    f"a round's minutes are the match length it was played at, because the engine selects an eleven and models no substitutions"
)

RESERVE_FORMULA: Final = f"training_reserve = {TRAINING_RESERVE} × min(1, Σ load_units of this player's sessions in real_training_sessions ÷ {TRAINING_RESERVE_LOAD})"

CONDITION_FORMULA: Final = (
    f"condition = 1 − {FATIGUE_DEPTH}·(load_units ÷ {WINDOW_LOAD:g}) + training_reserve, clipped to "
    f"{CONDITION_FLOOR:.2f}–{CONDITION_CEILING:.2f}, where {WINDOW_LOAD:g} is a full match in each of the "
    f"{RECENT_ROUNDS} rounds at {DECAY} decay; a player the world holds no session for has a training_reserve of 0, "
    "which is his minutes alone rather than a penalty"
)

FORM_FORMULA: Final = (
    f"form = mean over the selected eleven of (stored form − 0.8) ÷ 0.4 × ({FORM_WEIGHT}), where {FORM_WEIGHT} is 1 for a "
    "player with no trace, so an untouched club's side is the stored-form mean exactly as it was before this rule existed"
)

CARRY_DISCLAIMER: Final = (
    "Condition is arithmetic over rows this platform wrote for a fictional squad: minutes the engine's own "
    "selection produced and training loads the world generator authored. It is not a measure of any real "
    "player's fitness, and no sports science was fitted to real data here."
)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def appearances_as_of(session: Session, career_id: str, round_index: int) -> list[CareerAppearance]:
    """The rounds before `round_index` that this career left a trace for, oldest first.

    Strictly before: the round being played is not yet played, so it cannot be tired by itself.
    """
    return list(
        session.scalars(
            select(CareerAppearance).where(CareerAppearance.career_id == career_id, CareerAppearance.round_index < round_index).order_by(CareerAppearance.round_index, CareerAppearance.player_name)
        ).all()
    )


def appearances_of_round(session: Session, career_id: str, round_index: int) -> list[CareerAppearance]:
    return list(session.scalars(select(CareerAppearance).where(CareerAppearance.career_id == career_id, CareerAppearance.round_index == round_index).order_by(CareerAppearance.player_name)).all())


def load_windows(rows: list[CareerAppearance], *, round_index: int) -> dict[str, dict[str, float]]:
    """player id → the decayed minutes it carries into `round_index`, with the rounds that made it up.

    A round further back counts half as much, so the window is dominated by the last fixture without
    forgetting the two before it. Rounds outside the window are dropped rather than folded into a
    lifetime total: a season of football does not tire a player linearly, and nothing here claims to
    model recovery beyond that one stated rule.
    """
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        since = int(round_index) - int(row.round_index)
        if since <= 0 or since > RECENT_ROUNDS:
            continue
        entry = out.setdefault(row.player_id, {"load": 0.0, "rounds": 0.0, "minutes": 0.0})
        weight = DECAY ** (since - 1)
        entry["load"] = round(entry["load"] + int(row.minutes) * weight, 3)
        entry["rounds"] += 1
        entry["minutes"] += int(row.minutes)
    return out


def training_loads(session: Session, player_ids: list[str]) -> dict[str, int]:
    """Σ `load_units` the world holds for each player. A player with no sessions is absent, not zero-filled.

    The count matters as much as the sum: the view prints how many of a traced eleven had any training
    record at all, because a rule that reads a table most players are not in is worth being exact about.
    """
    wanted = [pid for pid in player_ids if pid]
    if not wanted:
        return {}
    rows = session.execute(select(RealTrainingSession.player_id, RealTrainingSession.load_units).where(RealTrainingSession.player_id.in_(wanted))).all()
    totals: dict[str, int] = {}
    for player_id, units in rows:
        totals[str(player_id)] = totals.get(str(player_id), 0) + int(units or 0)
    return totals


def condition_of(load: float, training: int) -> float:
    """One player's condition going into a round: his carried load, minus what his training record gives back."""
    fatigue = FATIGUE_DEPTH * (load / WINDOW_LOAD)
    reserve = TRAINING_RESERVE * min(1.0, training / TRAINING_RESERVE_LOAD)
    return round(_clamp(CONDITION_CEILING - fatigue + reserve, CONDITION_FLOOR, CONDITION_CEILING), 4)


def condition_map(
    session: Session,
    career_id: str,
    *,
    round_index: int,
    appearances: list[CareerAppearance] | None = None,
    training: dict[str, int] | None = None,
) -> dict[str, float]:
    """player id → condition for everyone this career has played in its last rounds.

    Only players with a trace appear: a side drawn from untouched rows must keep the stored-form mean
    exactly, which is what lets a match stored before this rule still replay to its own digest.
    `appearances`/`training` let a caller that already fetched them (the career view) hand them in; the
    round window is derived from that one list by filtering to rounds before `round_index`.
    """
    if appearances is not None:
        rows = [row for row in appearances if int(row.round_index) < int(round_index)]
    else:
        rows = appearances_as_of(session, career_id, round_index)
    windows = load_windows(rows, round_index=round_index)
    if not windows:
        return {}
    training = training if training is not None else training_loads(session, list(windows))
    return {player_id: condition_of(entry["load"], training.get(player_id, 0)) for player_id, entry in windows.items()}


def record_appearances(
    session: Session,
    career: Career,
    *,
    round_index: int,
    lineup: list[tuple[str, str, str, str, str]],
    side: str,
    minutes: int,
    opponent_name: str,
) -> list[CareerAppearance]:
    """Write one trace per selected player. Idempotent per round, so a re-played round cannot double up.

    `lineup` is (player id, slug, name, position, band) in the order the side was selected. The caller
    rebuilds it from the same rows the engine played and checks it against the match report before
    calling — a trace written from a reconstructed eleven that does not match the eleven that played would
    be a claim about a match this platform cannot support.
    """
    already = appearances_of_round(session, career.id, round_index)
    if already:
        return already
    rows: list[CareerAppearance] = []
    for player_id, slug, name, position, band in lineup:
        rows.append(
            CareerAppearance(
                id=new_public_id("cap"),
                career_id=career.id,
                round_index=round_index,
                player_id=player_id,
                player_slug=slug,
                player_name=name,
                position=position,
                band=band,
                side=side,
                minutes=minutes,
                opponent_name=opponent_name,
                note=f"selected by the engine for round {round_index} and played the fixture's full {minutes} minutes as modelled",
                data_origin="simulation",
                is_demo_data=True,
            )
        )
    session.add_all(rows)
    session.commit()
    return rows


def _row(appearance: CareerAppearance) -> dict[str, Any]:
    return {
        "round_index": appearance.round_index,
        "player_name": appearance.player_name,
        "player_path": f"/player/{appearance.player_slug}" if appearance.player_slug else None,
        "position": appearance.position,
        "band": appearance.band,
        "side": appearance.side,
        "minutes": appearance.minutes,
        "minutes_units": appearance.minutes_units,
        "opponent_name": appearance.opponent_name,
        "note": appearance.note,
    }


def carry_over_view(
    session: Session,
    career: Career,
    *,
    next_round: int,
    appearances: list[CareerAppearance] | None = None,
    training: dict[str, int] | None = None,
) -> dict[str, Any]:
    """What this career's played rounds have left on its players, and what round `next_round` reads.

    Everything here is summed from `career_appearances` and `real_training_sessions` on the request, in
    the same discipline as the record and the budget: the figures a page prints are the figures these
    rows give, with the expression beside them. `appearances`/`training` let a caller that already fetched
    them (the career view, for `development_view` too) hand them in rather than read the tables again; the
    round window is derived from the one appearance list, so the table is read once.
    """
    all_rows = appearances if appearances is not None else list(session.scalars(select(CareerAppearance).where(CareerAppearance.career_id == career.id).order_by(CareerAppearance.round_index)).all())
    history = [row for row in all_rows if int(row.round_index) < int(next_round)]
    windows = load_windows(history, round_index=next_round)
    training = training if training is not None else training_loads(session, list(windows))
    conditions = {player_id: condition_of(entry["load"], training.get(player_id, 0)) for player_id, entry in windows.items()}
    last_round = max((row.round_index for row in all_rows), default=0)
    traced = {row.round_index for row in all_rows}
    # A round the career played but left no rows for is a hole in the ledger, not a rest: the engine could
    # not attribute its eleven. Saying so beats printing a condition figure built on the rounds that were.
    untraced = [round_number for round_number in range(1, int(career.rounds_played) + 1) if round_number not in traced]
    played_last = [row for row in all_rows if row.round_index == last_round]
    mean_last = round(sum(conditions.get(row.player_id, CONDITION_CEILING) for row in played_last) / len(played_last), 4) if played_last else CONDITION_CEILING
    ranked = sorted(windows.items(), key=lambda item: (-item[1]["load"], item[0]))
    by_id = {row.player_id: row for row in history}
    return {
        "rounds_played": int(career.rounds_played),
        "rounds_traced": len(traced),
        "untraced_rounds": untraced,
        "appearances": len(all_rows),
        "players_traced": len({row.player_id for row in all_rows}),
        "last_traced_round": last_round,
        "next_round": next_round,
        "window_rounds": RECENT_ROUNDS,
        "decay_per_round": DECAY,
        "carrying_load": len(windows),
        "mean_condition_of_last_xi": mean_last,
        "condition_floor": CONDITION_FLOOR,
        "training_records_found": sum(1 for player_id in windows if player_id in training),
        "most_loaded": [
            {
                "player_id": player_id,
                "player_name": by_id[player_id].player_name if player_id in by_id else player_id,
                "position": by_id[player_id].position if player_id in by_id else "",
                "minutes_recent": by_id[player_id].minutes if player_id in by_id else 0,
                "rounds_in_window": entry["rounds"],
                "load_units": entry["load"],
                "training_load_units": training.get(player_id, 0),
                "condition": conditions[player_id],
            }
            for player_id, entry in ranked[:11]
        ],
        "rows": [_row(row) for row in all_rows[-30:]],
        "load_formula": LOAD_FORMULA,
        "reserve_formula": RESERVE_FORMULA,
        "condition_formula": CONDITION_FORMULA,
        "form_formula": FORM_FORMULA,
        "note": (
            "the condition the next round reads is this career's own history; a club with no played round here has no trace, "
            "and its side is the stored-form mean exactly as it has always been"
            + (
                f"; {len(untraced)} played round(s) left no trace at all ({', '.join(str(number) for number in untraced)}), so the load carried into the next round is measured without them"
                if untraced
                else ""
            )
        ),
        "disclaimer": CARRY_DISCLAIMER,
        "data_origin": "simulation",
        "is_demo_data": True,
    }


__all__ = [
    "CONDITION_FORMULA",
    "CARRY_DISCLAIMER",
    "DECAY",
    "FORM_FORMULA",
    "FULL_MATCH_MINUTES",
    "LOAD_FORMULA",
    "RECENT_ROUNDS",
    "RESERVE_FORMULA",
    "appearances_as_of",
    "appearances_of_round",
    "carry_over_view",
    "condition_map",
    "condition_of",
    "load_windows",
    "record_appearances",
    "training_loads",
]
