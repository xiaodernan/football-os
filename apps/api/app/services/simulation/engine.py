"""The match engine (M6, spec §19).

Deterministic, block by block, and honest about what it is:

* **Same seed, same input rows, same output.** The random source is `WorldRng`, not `random.Random`,
  whose `sample`/`shuffle` internals have changed between Python releases; the digest of a finished
  simulation is therefore reproducible across processes and across both databases.
* **Every rate names its formula.** `report["model"]["factors"]` carries each expression, and each
  block records the multipliers it was played with, so a scoreline can be traced back to the two
  squads' attribute means and the metres of the two tactical systems.
* **The coefficients are authored, not fitted.** This project holds no real match data to calibrate
  against and says so on every response (`model["calibration"]`, spec §19's fictional sentence).
* **Goals are not xG.** Each chance is a Bernoulli draw on its own modelled probability, so a side can
  finish above or below its expected goals; the report prints both and lets the reader see the gap.

What it deliberately does not do: possession does not move with the scoreline, and nobody is
substituted. Both are listed in `model["what_it_does_not_model"]` rather than quietly approximated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any

from app.services.simulation.profile import SideProfile, possession_share
from app.services.world.rng import WorldRng

ENGINE_NAME = "possession-block-v1"
ENGINE_VERSION = "1.0.0"
MODEL_VERSION = f"{ENGINE_NAME}@{ENGINE_VERSION}"

# Spec §19's sentence, kept verbatim so no page can present a simulation as a forecast.
SIMULATION_DISCLAIMER = "Simulation result is fictional / model-generated and should not be interpreted as a real-world prediction."
CALIBRATION_NOTE = "coefficients authored by this project; no real match data was used to fit them, and the engine claims no accuracy against real football"

# The chosen constants, together in one place so the whole model is readable at a glance.
COEFFICIENTS: dict[str, float] = {
    "shot_rate_per_ball_minute": 0.22,
    "passes_per_ball_minute": 7.5,
    "press_attempts_per_opp_ball_minute": 0.26,
    "press_conversion_base": 0.14,
    "press_conversion_slope": 0.22,
    "high_turnover_share": 0.30,
    "press_shot_share": 0.42,
    "transition_share": 0.35,
    "transition_shot_share": 0.25,
    "fouls_per_ball_minute": 0.095,
    "yellow_per_foul_base": 0.055,
    "yellow_per_foul_press_slope": 0.045,
    "red_per_foul": 0.004,
    "injury_rate_per_minute": 0.0014,
    "xg_big_chance": 0.30,
    "xg_normal_chance": 0.10,
    "xg_long_range": 0.035,
    "xg_transition_bonus": 1.15,
    "on_target_base": 0.40,
    "on_target_xg_slope": 0.35,
    "corner_per_off_target": 0.35,
    "late_match_shot_drift": 0.12,
    "late_match_xg_drift": 0.15,
    "fatigue_slope": 0.18,
    "man_down_attack": 0.88,
    "man_down_concede": 1.12,
    "substitution_fresh_legs_bonus": 0.05,
}

# A shot is one of three kinds, each with its own modelled quality before the two squads adjust it.
CHANCE_WEIGHTS: dict[str, float] = {"big_chance": 0.14, "normal_chance": 0.62, "long_range": 0.24}
CHANCE_XG: dict[str, float] = {
    "big_chance": COEFFICIENTS["xg_big_chance"],
    "normal_chance": COEFFICIENTS["xg_normal_chance"],
    "long_range": COEFFICIENTS["xg_long_range"],
}

# Who finishes a chance: forwards mostly, occasionally a midfielder, rarely a defender, never a keeper.
BAND_SCORING_WEIGHT: dict[str, float] = {"attack": 3.0, "midfield": 2.0, "defence": 1.0, "keeper": 0.02}

FACTOR_EXPRESSIONS: tuple[dict[str, str], ...] = (
    {
        "key": "possession_share",
        "expression": "0.5 + 0.5·tanh(Δ / 18), clipped to 0.24–0.76; Δ = 26·(midfield_home − midfield_away) + 6·(press_resistance_home − press_resistance_away)",
        "reads": "the two midfield indices and the spacing/line_separation metres of each shape",
    },
    {
        "key": "shot_volume",
        "expression": "(0.55 + attack) × stretch(own depth, width) × opening(opp line_separation, space_behind) × fatigue × (1 + 0.12·t) × man-down",
        "reads": "own forwards' attributes, own shape's metres in possession, the opponent's metres out of it, minute of the match",
    },
    {
        "key": "shot_rate",
        "expression": "Poisson(0.22 × ball_minutes × shot_volume), capped at 40 attempts a block",
        "reads": "share of the block's minutes spent in possession, then the volume factor above",
    },
    {
        "key": "chance_quality",
        "expression": "(0.70 + 0.60·attack) × (1 − 0.25·opp defence) × (1 − 0.15·opp keeper) × (1 + 0.15·t), clipped to 0.05–0.90",
        "reads": "the same indices, from the finishing side rather than the volume side",
    },
    {
        "key": "expected_goals",
        "expression": "chance-class xG (0.30 big / 0.10 normal / 0.035 long-range) × chance_quality × 1.15 if it came from a turnover, clipped to 0.005–0.60; a goal is one Bernoulli draw on that number",
        "reads": "how the chance arrived, and the two squads' finishing and resisting indices",
    },
    {
        "key": "press_conversion",
        "expression": "0.14 + 0.22·press − 0.10·(opp midfield − 0.5), clipped to 0.05–0.55, drawn per press attempt",
        "reads": "own pressing attributes and the opponent's midfield index",
    },
    {
        "key": "fatigue",
        "expression": "1 − 0.18·t × (0.5 + 0.5·(1 − form))",
        "reads": "minute as a share of the match, and the selected eleven's stored form: a lower-form side fades further",
    },
    {
        "key": "pass_accuracy",
        "expression": "0.60 + 0.28·midfield − 0.12·opp press, clipped to 0.48–0.93, drawn per attempt as independent Bernoulli trials",
        "reads": "own midfield index and the opponent's press index",
    },
    {
        "key": "set_pieces",
        "expression": "a shot off target becomes a corner conceded with probability 0.35; no set-piece goal model",
        "reads": "stated so the absence is visible rather than guessed at",
    },
    {
        "key": "substitution_fresh_legs",
        "expression": "midfield and attack × (1 + 0.05) from the block at minute round(0.6·minutes); the shape and possession share are unchanged",
        "reads": "the authored fresh-legs bonus, applied once per side after the fixed minute",
    },
)


@dataclass(frozen=True)
class MatchInputs:
    """What a simulation needs before a minute is played. Reads nothing: the caller supplies it."""

    home: SideProfile
    away: SideProfile
    seed: int
    minutes: int = 90
    block_minutes: int = 6
    substitutions: int = 0

    @property
    def blocks(self) -> int:
        return max(1, round(self.minutes / self.block_minutes))


@dataclass
class _Side:
    """One side's running totals, tagged with which half of the scoreline it owns."""

    key: str
    profile: SideProfile
    possession: float
    shots: int = 0
    shots_on_target: int = 0
    goals: int = 0
    xg: float = 0.0
    passes: int = 0
    pass_completions: int = 0
    press_attempts: int = 0
    turnovers_won: int = 0
    high_turnovers: int = 0
    transitions: int = 0
    big_chances: int = 0
    fouls: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    injuries: int = 0
    corners_conceded: int = 0

    @property
    def sent_off(self) -> bool:
        return self.red_cards > 0

    def to_dict(self) -> dict[str, Any]:
        attempted = max(1, self.passes)
        return {
            "side": self.key,
            "team_id": self.profile.team_id,
            "name": self.profile.name,
            "short_name": self.profile.short_name,
            "formation": self.profile.formation,
            "system_slug": self.profile.system_slug,
            "system_name": self.profile.system_name,
            # Which squad this side was built from. Empty for a club playing its own stored rows; a
            # career's round names the overlay here, so a signed player in the eleven is explained by
            # the report itself rather than leaving a reader to notice he is not on the club's page.
            "squad_label": self.profile.squad_label,
            "goals": self.goals,
            "possession_pct": round(self.possession * 100, 1),
            "shots": self.shots,
            "shots_on_target": self.shots_on_target,
            "big_chances": self.big_chances,
            "expected_goals": round(self.xg, 3),
            "passes": self.passes,
            "pass_completions": self.pass_completions,
            "pass_accuracy_pct": round(100 * self.pass_completions / attempted, 1),
            "press_attempts": self.press_attempts,
            "turnovers_won": self.turnovers_won,
            "high_turnovers_won": self.high_turnovers,
            "transitions": self.transitions,
            "corners_conceded": self.corners_conceded,
            "fouls": self.fouls,
            "yellow_cards": self.yellow_cards,
            "red_cards": self.red_cards,
            "injuries": self.injuries,
            # The eleven is printed so a named scorer can be checked against it by anyone reading the
            # report — the engine should not be able to credit a player who was never selected.
            "lineup": [{"player": player, "position": position, "band": band} for player, position, band in self.profile.lineup],
            "indices": {
                "attack": round(self.profile.attack, 3),
                "midfield": round(self.profile.midfield, 3),
                "defence": round(self.profile.defence, 3),
                "keeper": round(self.profile.keeper, 3),
                "press": round(self.profile.press, 3),
                "form": round(self.profile.form, 3),
            },
            # The measurements travel beside the side, so a reader can check an index against the metres
            # and the squad attributes it was computed from instead of taking it on trust.
            "inputs": {
                "tactics": {key: round(value, 2) for key, value in self.profile.tactics.items()},
                "factors": [metric.to_dict() for metric in self.profile.factors],
            },
        }


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _binomial(rng: WorldRng, trials: int, probability: float) -> int:
    """Successes in `trials` independent draws, done one at a time so the seed controls every one."""
    if trials <= 0 or probability <= 0.0:
        return 0
    clipped = min(1.0, probability)
    return sum(1 for _ in range(trials) if rng.random() < clipped)


def _named_player(rng: WorldRng, side: _Side) -> tuple[str, str, str]:
    """A fictional player from this side's own eleven, weighted by band. Returns (name, position, band)."""
    slots = list(side.profile.lineup)
    if not slots:
        return (side.profile.short_name, "", "")
    weights = [BAND_SCORING_WEIGHT.get(band, 1.0) for _name, _position, band in slots]
    # The draw is over the eleven's own tuples, not their names: a squad with two identical surnames
    # still gets one draw per slot, and the lineup order keeps the seed in charge of which it is.
    return rng.weighted(slots, weights)


def _chance_weights(side: _Side, opponent: _Side) -> list[float]:
    """How a chance arrives shifts with the shapes: a stretched attack gets more big chances, a low
    block forces more long-range attempts."""
    own = side.profile.tactics
    opp = opponent.profile.tactics
    stretch = own.get("depth", 30.0) / 60.0 if own else 0.0
    compact = 1.0 - _clamp(opp.get("line_separation", 16.0) / 32.0, 0.0, 1.0) if opp else 0.0
    return [
        CHANCE_WEIGHTS["big_chance"] + 0.05 * stretch + 0.05 * compact,
        CHANCE_WEIGHTS["normal_chance"],
        CHANCE_WEIGHTS["long_range"] + 0.10 * compact,
    ]


def _volume_and_quality(side: _Side, opponent: _Side, progress: float) -> tuple[float, float, dict[str, float]]:
    """The block's two multipliers, and the numbers inside them for the block row to carry."""
    tactics = side.profile.tactics
    opp_tactics = opponent.profile.tactics

    attack_term = 0.55 + side.profile.attack
    stretch = 1.0 + (((tactics.get("depth", 30.0) - 30.0) / 120.0 + (tactics.get("width", 40.0) - 40.0) / 160.0) if tactics else 0.0)
    opponent_opening = 1.0 + (((opp_tactics.get("line_separation", 16.0) - 16.0) / 60.0 + (opp_tactics.get("space_behind", 12.0) - 12.0) / 80.0) if opp_tactics else 0.0)
    fatigue = 1.0 - COEFFICIENTS["fatigue_slope"] * progress * (0.5 + 0.5 * (1.0 - side.profile.form))
    late_space = 1.0 + COEFFICIENTS["late_match_shot_drift"] * progress
    man_down_attack = COEFFICIENTS["man_down_attack"] if side.sent_off else 1.0
    man_down_concede = COEFFICIENTS["man_down_concede"] if opponent.sent_off else 1.0

    volume = attack_term * stretch * opponent_opening * fatigue * late_space * man_down_attack * man_down_concede
    finish = 0.70 + 0.60 * side.profile.attack
    resists = (1.0 - 0.25 * opponent.profile.defence) * (1.0 - 0.15 * opponent.profile.keeper)
    late_quality = 1.0 + COEFFICIENTS["late_match_xg_drift"] * progress
    quality = _clamp(finish * resists * late_quality * man_down_attack, 0.05, 0.90)

    terms = {
        "attack_term": round(attack_term, 3),
        "stretch": round(stretch, 3),
        "opponent_opening": round(opponent_opening, 3),
        "fatigue": round(fatigue, 3),
        "late_space": round(late_space, 3),
        "man_down_attack": round(man_down_attack, 3),
        "man_down_concede": round(man_down_concede, 3),
    }
    return volume, quality, terms


def _take_shot(
    rng: WorldRng,
    side: _Side,
    opponent: _Side,
    minute: int,
    events: list[dict[str, Any]],
    chance: str,
    quality: float,
    *,
    from_press: bool = False,
) -> None:
    """One attempt: modelled quality, an on-target draw, then a Bernoulli goal draw on the same number.

    The scoreline a goal reports is filled in afterwards, once every event has a minute attached, so
    this function needs only the two sides' own ledgers.
    """
    base = CHANCE_XG.get(chance, COEFFICIENTS["xg_normal_chance"])
    xg = _clamp(base * quality * (COEFFICIENTS["xg_transition_bonus"] if from_press else 1.0), 0.005, 0.60)
    side.xg += xg
    side.shots += 1
    if chance == "big_chance":
        side.big_chances += 1
    on_target = rng.random() < _clamp(
        COEFFICIENTS["on_target_base"] + COEFFICIENTS["on_target_xg_slope"] * (xg / 0.30),
        0.20,
        0.90,
    )
    scorer, position, _band = _named_player(rng, side)
    if on_target:
        side.shots_on_target += 1
    elif rng.random() < COEFFICIENTS["corner_per_off_target"]:
        opponent.corners_conceded += 1
    if on_target and rng.random() < xg:
        side.goals += 1
        events.append(
            {
                "minute": minute,
                "type": "goal",
                "side": side.key,
                "team": side.profile.short_name,
                "player": scorer,
                "position": position,
                "chance": chance,
                "expected_goals": round(xg, 3),
                "detail": f"Goal for {side.profile.name}: {chance.replace('_', ' ')} from {scorer}" + (f" ({position})" if position else ""),
            }
        )
    elif on_target:
        events.append(
            {
                "minute": minute,
                "type": "shot_saved",
                "side": side.key,
                "team": side.profile.short_name,
                "player": scorer,
                "position": position,
                "chance": chance,
                "expected_goals": round(xg, 3),
                "detail": f"Save from the {opponent.profile.short_name} keeper — {chance.replace('_', ' ')} by {scorer}",
            }
        )
    else:
        events.append(
            {
                "minute": minute,
                "type": "shot_off_target",
                "side": side.key,
                "team": side.profile.short_name,
                "player": scorer,
                "position": position,
                "chance": chance,
                "expected_goals": round(xg, 3),
                "detail": f"{scorer} sends the {chance.replace('_', ' ')} wide or blocked",
            }
        )


def _record(events: list[dict[str, Any]], side: _Side, minute: int, kind: str, player: str, position: str, detail: str) -> None:
    events.append(
        {
            "minute": minute,
            "type": kind,
            "side": side.key,
            "team": side.profile.short_name,
            "player": player,
            "position": position,
            "detail": detail,
        }
    )


def _apply_running_score(events: list[dict[str, Any]]) -> None:
    """Order the match by minute, then stamp each goal with the scoreline as it stood when it went in."""
    order = {id(event): index for index, event in enumerate(events)}
    events.sort(key=lambda event: (event["minute"], order[id(event)]))
    running = {"home": 0, "away": 0}
    for event in events:
        if event["type"] != "goal":
            continue
        running[event["side"]] += 1
        event["score"] = f"{running['home']}-{running['away']}"


def _winner(home_goals: int, away_goals: int, home: SideProfile, away: SideProfile) -> dict[str, Any]:
    if home_goals == away_goals:
        return {"side": "draw", "name": "Draw"}
    if home_goals > away_goals:
        return {"side": "home", "name": home.name, "team_id": home.team_id}
    return {"side": "away", "name": away.name, "team_id": away.team_id}


def _digest(report: dict[str, Any]) -> str:
    """A hash over the numbers a reader can check the scoreline against. Taken before `digest` exists."""
    payload = json.dumps(report, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _apply_substitution(side: _Side, minute: int, events: list[dict[str, Any]], log: list[dict[str, Any]]) -> None:
    """Model a substitution as fresh legs: a bounded boost to the side's midfield and attack indices from a
    fixed minute. It does NOT name a player or change the shape — the engine still cannot credit a player it
    never selected, so the effect is an energy number, not a personnel change.

    The bonus is deterministic (no random draw), so a substitution leaves the seed in charge of every other
    number in the match; it only shifts the indices the rest of the match reads.
    """
    bonus = COEFFICIENTS["substitution_fresh_legs_bonus"]
    side.profile = replace(
        side.profile,
        attack=_clamp(side.profile.attack * (1.0 + bonus), 0.0, 1.0),
        midfield=_clamp(side.profile.midfield * (1.0 + bonus), 0.0, 1.0),
    )
    detail = (
        f"Substitution for {side.profile.name}: fresh legs bring a modelled {bonus * 100:.0f}% boost to "
        f"midfield and attack from here. The engine does not name the player or change the shape."
    )
    _record(events, side, minute, "substitution", "", "", detail)
    log.append({"minute": minute, "side": side.key, "team": side.profile.short_name, "detail": detail})


def simulate_match(inputs: MatchInputs) -> dict[str, Any]:
    """Play a match from two profiles. The database has already been read; this is pure arithmetic."""
    home_profile, away_profile = inputs.home, inputs.away
    share = possession_share(home_profile, away_profile, home_profile.tactics, away_profile.tactics)
    home = _Side(key="home", profile=home_profile, possession=share)
    away = _Side(key="away", profile=away_profile, possession=1.0 - share)
    pairs = (home, away), (away, home)

    rng = WorldRng(inputs.seed).fork(f"{MODEL_VERSION}:{home_profile.team_id}v{away_profile.team_id}:{inputs.seed}")
    events: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    # A substitution is modelled as fresh legs: a bounded boost to a side's midfield and attack from a
    # fixed minute. The default (substitutions=0) applies nothing, so the selected eleven plays on and the
    # digest is unchanged; this is the only branch that distinguishes the two paths.
    sub_minute = max(1, round(inputs.minutes * 0.6))
    sub_applied: dict[str, bool] = {"home": False, "away": False}
    substitutions_log: list[dict[str, Any]] = []

    for index in range(inputs.blocks):
        start = index * inputs.block_minutes + 1
        end = min(inputs.minutes, (index + 1) * inputs.block_minutes)
        span = end - start + 1
        progress = end / max(1, inputs.minutes)
        opening = {side.key: (side.goals, side.xg, side.shots) for side in (home, away)}
        block_terms: dict[str, dict[str, float]] = {}

        for side, opponent in pairs:
            if inputs.substitutions > 0 and not sub_applied[side.key] and start >= sub_minute:
                _apply_substitution(side, sub_minute, events, substitutions_log)
                sub_applied[side.key] = True
            ball_minutes = span * side.possession
            opp_ball_minutes = span * opponent.possession
            volume, quality, terms = _volume_and_quality(side, opponent, progress)
            block_terms[side.key] = {**terms, "volume": round(volume, 3), "chance_quality": round(quality, 3)}

            attempts = round(COEFFICIENTS["passes_per_ball_minute"] * ball_minutes * (0.6 + side.profile.midfield))
            accuracy = _clamp(0.60 + 0.28 * side.profile.midfield - 0.12 * opponent.profile.press, 0.48, 0.93)
            side.passes += attempts
            side.pass_completions += _binomial(rng, attempts, accuracy)

            press_attempts = rng.poisson(
                COEFFICIENTS["press_attempts_per_opp_ball_minute"] * opp_ball_minutes * (0.5 + side.profile.press),
                cap=80,
            )
            conversion = _clamp(
                COEFFICIENTS["press_conversion_base"] + COEFFICIENTS["press_conversion_slope"] * side.profile.press - 0.10 * (opponent.profile.midfield - 0.5),
                0.05,
                0.55,
            )
            won = _binomial(rng, press_attempts, conversion)
            high = _binomial(rng, won, COEFFICIENTS["high_turnover_share"])
            side.press_attempts += press_attempts
            side.turnovers_won += won
            side.high_turnovers += high

            for _ in range(_binomial(rng, high, COEFFICIENTS["press_shot_share"])):
                _take_shot(rng, side, opponent, rng.randint(start, end), events, "big_chance", quality, from_press=True)

            transitions = _binomial(rng, won - high, COEFFICIENTS["transition_share"])
            side.transitions += transitions
            for _ in range(_binomial(rng, transitions, COEFFICIENTS["transition_shot_share"])):
                _take_shot(rng, side, opponent, rng.randint(start, end), events, "normal_chance", quality, from_press=True)

            shot_count = rng.poisson(COEFFICIENTS["shot_rate_per_ball_minute"] * ball_minutes * volume, cap=40)
            for _ in range(shot_count):
                chance = rng.weighted(list(CHANCE_WEIGHTS), _chance_weights(side, opponent))
                _take_shot(rng, side, opponent, rng.randint(start, end), events, chance, quality)

            fouls = rng.poisson(
                COEFFICIENTS["fouls_per_ball_minute"] * ball_minutes * (0.8 + 0.5 * opponent.profile.press),
                cap=30,
            )
            side.fouls += fouls
            yellows = _binomial(
                rng,
                fouls,
                COEFFICIENTS["yellow_per_foul_base"] + COEFFICIENTS["yellow_per_foul_press_slope"] * opponent.profile.press,
            )
            reds = _binomial(rng, fouls, COEFFICIENTS["red_per_foul"])
            for _ in range(yellows):
                side.yellow_cards += 1
                player, position, _band = _named_player(rng, side)
                _record(
                    events,
                    side,
                    rng.randint(start, end),
                    "yellow_card",
                    player,
                    position,
                    f"Yellow card for {player}" + (f" ({position})" if position else "") + f" — a tactical foul against {opponent.profile.short_name}",
                )
            for _ in range(reds):
                side.red_cards += 1
                player, position, _band = _named_player(rng, side)
                _record(
                    events,
                    side,
                    rng.randint(start, end),
                    "red_card",
                    player,
                    position,
                    f"Red card for {player}" + (f" ({position})" if position else "") + f" — {side.profile.short_name} are a man down for the rest of the match as modelled",
                )

            injuries = rng.poisson(COEFFICIENTS["injury_rate_per_minute"] * span * (0.8 + 0.6 * progress), cap=3)
            for _ in range(injuries):
                side.injuries += 1
                player, position, band = _named_player(rng, side)
                _record(
                    events,
                    side,
                    rng.randint(start, end),
                    "injury",
                    player,
                    position,
                    f"{player} goes off injured" + (f" ({position})" if position else "") + " — the model raises fatigue from here, it does not name a diagnosis" + ("" if band else ""),
                )

        rows: dict[str, Any] = {}
        for side in (home, away):
            goals_before, xg_before, shots_before = opening[side.key]
            rows[side.key] = {
                "goals": side.goals - goals_before,
                "expected_goals": round(side.xg - xg_before, 3),
                "shots": side.shots - shots_before,
                "possession_pct": round(side.possession * 100, 1),
                "cumulative": f"{home.goals}-{away.goals}",
                **block_terms[side.key],
            }
        blocks.append({"minute_from": start, "minute_to": end, "home": rows["home"], "away": rows["away"]})

    _apply_running_score(events)

    report: dict[str, Any] = {
        "status": "completed",
        "substitutions": substitutions_log,
        "model": {
            "name": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "model_version": MODEL_VERSION,
            "seed": inputs.seed,
            "minutes": inputs.minutes,
            "block_minutes": inputs.block_minutes,
            "blocks": inputs.blocks,
            "calibration": CALIBRATION_NOTE,
            "coefficients": COEFFICIENTS,
            "factors": list(FACTOR_EXPRESSIONS),
            "what_it_does_not_model": [
                "substituted players are not named and the shape does not change — a substitution is a fresh-legs bonus to midfield and attack from a fixed minute",
                "possession shifting with the scoreline",
                "set-piece routines beyond a corner count against",
                "goalkeeping as its own attribute — this world's player model has none",
                "weather, referee identity, crowd, travel",
                "anything about a real match: no fixture here is a forecast",
            ],
        },
        "score": {"home": home.goals, "away": away.goals, "winner": _winner(home.goals, away.goals, home_profile, away_profile)},
        "sides": {"home": home.to_dict(), "away": away.to_dict()},
        "totals": {
            "shots": home.shots + away.shots,
            "shots_on_target": home.shots_on_target + away.shots_on_target,
            "expected_goals": round(home.xg + away.xg, 3),
            "passes": home.passes + away.passes,
            "pass_completions": home.pass_completions + away.pass_completions,
            "press_attempts": home.press_attempts + away.press_attempts,
            "turnovers_won": home.turnovers_won + away.turnovers_won,
            "corners": home.corners_conceded + away.corners_conceded,
            "cards": home.yellow_cards + away.yellow_cards + 2 * (home.red_cards + away.red_cards),
            "events": len(events),
            "goal_events": sum(1 for event in events if event["type"] == "goal"),
        },
        "possession_share": {
            "home": round(share, 3),
            "away": round(1.0 - share, 3),
            "formula": "0.5 + 0.5·tanh(Δ/18), clipped to 0.24–0.76 — see model.factors[key=possession_share]",
        },
        "events": events,
        "blocks": blocks,
        "provenance": {
            "data_origin": "simulation",
            "is_demo_data": True,
            "disclaimer": SIMULATION_DISCLAIMER,
            "inputs_are_from": ["teams", "real_players", "tactical_systems"],
        },
    }
    report["digest"] = _digest(report)
    return report


__all__ = [
    "CALIBRATION_NOTE",
    "ENGINE_NAME",
    "ENGINE_VERSION",
    "MODEL_VERSION",
    "SIMULATION_DISCLAIMER",
    "MatchInputs",
    "simulate_match",
]
