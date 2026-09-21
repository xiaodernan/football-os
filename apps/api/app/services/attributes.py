"""Attribute model, baselines and archetype derivation (spec §5–§6, §27).

All derivations are deterministic functions of stored inputs so any number shown in
the UI can be explained by the reasons returned here (spec §8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import ALL_ATTRIBUTES, ATTRIBUTES

# Archetype catalogue — original definitions, each with core attributes, zones, strengths,
# weaknesses, recommended drill categories and a progression tree (spec §6).
ARCHETYPES: dict[str, dict[str, Any]] = {
    "Deep-Lying Playmaker": {
        "positions": ["CDM", "CM"],
        "core": {"vision": 3, "passing": 3, "long_passing": 2, "decision_making": 3, "composure": 2, "scanning": 2},
        "zones": ["deep_central", "left_half_space"],
        "strengths": ["tempo control", "breaking first line", "positional discipline"],
        "weaknesses": ["recovery speed", "final-third threat"],
        "drill_categories": ["passing", "receiving", "scanning", "decision_making"],
        "progression_tree": ["Box-to-Box", "Advanced Playmaker"],
    },
    "Box-to-Box": {
        "positions": ["CM", "CDM"],
        "core": {"stamina": 3, "pressing": 3, "passing": 2, "transition": 3, "acceleration": 2, "defensive_awareness": 2},
        "zones": ["central_corridor"],
        "strengths": ["double pivot coverage", "transition carries", "press resistance"],
        "weaknesses": ["defensive positioning when tired", "creative risk"],
        "drill_categories": ["passing", "pressing", "transition", "fitness"],
        "progression_tree": ["Ball-Winning Midfielder", "Advanced Playmaker"],
    },
    "Ball-Winning Midfielder": {
        "positions": ["CDM", "CM"],
        "core": {"tackling": 3, "anticipation": 3, "strength": 2, "positioning": 3, "pressing": 2, "stamina": 2},
        "zones": ["deep_central", "central_corridor"],
        "strengths": ["recoveries", "screening the back line", "duel win rate"],
        "weaknesses": ["progressive passing range", "ball carrying under pressure"],
        "drill_categories": ["defending", "pressing", "first_touch"],
        "progression_tree": ["Deep-Lying Playmaker", "Box-to-Box"],
    },
    "Advanced Playmaker": {
        "positions": ["CAM", "CM"],
        "core": {"vision": 3, "first_touch": 3, "dribbling": 2, "decision_making": 3, "composure": 2, "off_ball_movement": 2},
        "zones": ["right_half_space", "left_half_space", "central_corridor"],
        "strengths": ["line-breaking passes", "receiving between lines", "chance creation"],
        "weaknesses": ["defensive contribution", "endurance across 90'"],
        "drill_categories": ["receiving", "dribbling", "decision_making", "passing"],
        "progression_tree": ["Deep-Lying Playmaker"],
    },
    "Inverted Winger": {
        "positions": ["LW", "RW"],
        "core": {"dribbling": 3, "finishing": 2, "ball_control": 3, "acceleration": 2, "off_ball_movement": 2, "vision": 2},
        "zones": ["inside_channel", "final_third_central"],
        "strengths": ["1v1 isolation", "far-post runs", "cutting inside onto strong foot"],
        "weaknesses": ["crossing consistency", "defensive tracking"],
        "drill_categories": ["1v1", "finishing", "dribbling", "ball_mastery"],
        "progression_tree": ["Complete Forward", "Pressing Forward"],
    },
    "Wide Playmaker": {
        "positions": ["LM", "RM", "LB", "RB"],
        "core": {"crossing": 3, "passing": 3, "long_passing": 2, "stamina": 2, "space_occupation": 2, "first_touch": 2},
        "zones": ["wide_channel"],
        "strengths": ["width provision", "delivery volume", "overlap timing"],
        "weaknesses": ["aerial duels", "central composure"],
        "drill_categories": ["crossing", "passing", "fitness"],
        "progression_tree": ["Inverted Winger", "Inverted Fullback"],
    },
    "Pressing Forward": {
        "positions": ["ST", "CF", "LW", "RW"],
        "core": {"pressing": 3, "transition": 3, "acceleration": 3, "finishing": 2, "stamina": 2, "anticipation": 2},
        "zones": ["high_central", "wide_channel"],
        "strengths": ["counter-press triggers", "turnovers high up", "pressing stamina"],
        "weaknesses": ["hold-up play", "long passing lanes"],
        "drill_categories": ["pressing", "transition", "finishing"],
        "progression_tree": ["Complete Forward", "Target Forward"],
    },
    "Target Forward": {
        "positions": ["ST", "CF"],
        "core": {"heading": 3, "strength": 3, "finishing": 2, "positioning": 2, "composure": 2, "first_touch": 2},
        "zones": ["high_central", "six_yard"],
        "strengths": ["aerial threat", "hold-up", "set-piece presence"],
        "weaknesses": ["wide link-up", "press resistance in space"],
        "drill_categories": ["first_touch", "finishing", "set_pieces"],
        "progression_tree": ["Complete Forward"],
    },
    "Complete Forward": {
        "positions": ["ST", "CF", "LW", "RW"],
        "core": {"finishing": 3, "dribbling": 2, "first_touch": 3, "composure": 3, "off_ball_movement": 2, "strength": 2},
        "zones": ["high_central", "inside_channel", "half_spaces"],
        "strengths": ["scoring variety", "self-creation", "clutch composure"],
        "weaknesses": ["defensive discipline", "sustained pressing"],
        "drill_categories": ["finishing", "ball_mastery", "1v1", "decision_making"],
        "progression_tree": [],
    },
    "Progressive Centre Back": {
        "positions": ["CB"],
        "core": {"long_passing": 3, "build_up": 3, "tackling": 2, "positioning": 3, "composure": 2, "strength": 2},
        "zones": ["deep_central"],
        "strengths": ["line-breaking passes", "carrying into midfield", "defensive organisation"],
        "weaknesses": ["recovery pace in wide areas", "1v1 on the last line"],
        "drill_categories": ["passing", "first_touch", "defending"],
        "progression_tree": ["Ball-Winning Midfielder"],
    },
    "Inverted Fullback": {
        "positions": ["LB", "RB"],
        "core": {"passing": 3, "positioning": 3, "decision_making": 2, "first_touch": 3, "pressing": 2, "stamina": 2},
        "zones": ["deep_central", "half_spaces"],
        "strengths": ["numerical superiority in build-up", "intercepting transitions", "central coverage"],
        "weaknesses": ["crossing volume", "1v1 defending out wide"],
        "drill_categories": ["receiving", "passing", "positioning", "defending"],
        "progression_tree": ["Deep-Lying Playmaker"],
    },
    "Sweeper Keeper": {
        "positions": ["GK"],
        "core": {"passing": 3, "decision_making": 2, "positioning": 3, "composure": 3, "anticipation": 2, "long_passing": 2},
        "zones": ["defensive_third"],
        "strengths": ["sweeping behind the line", "build-up outlet", "distribution quality"],
        "weaknesses": ["aerial claim safety", "aggressive rushing"],
        "drill_categories": ["goalkeeping", "passing", "decision_making"],
        "progression_tree": [],
    },
}

POSITION_BASELINE: dict[str, dict[str, int]] = {
    "GK": {"positioning": 8, "anticipation": 8, "composure": 7, "decision_making": 7, "passing": 6, "strength": 6, "heading": 5, "dribbling": 2, "finishing": 2},
    "CB": {"positioning": 8, "tackling": 8, "heading": 8, "defensive_awareness": 8, "strength": 7, "composure": 6, "passing": 6, "dribbling": 4, "finishing": 4},
    "LB": {"stamina": 8, "positioning": 7, "crossing": 7, "defensive_awareness": 7, "tackling": 7, "acceleration": 7, "passing": 6, "strength": 5},
    "RB": {"stamina": 8, "positioning": 7, "crossing": 7, "defensive_awareness": 7, "tackling": 7, "acceleration": 7, "passing": 6, "strength": 5},
    "CDM": {"positioning": 8, "passing": 8, "defensive_awareness": 8, "tackling": 7, "vision": 7, "decision_making": 7, "pressing": 7, "stamina": 7},
    "CM": {"passing": 8, "vision": 8, "first_touch": 8, "decision_making": 7, "scanning": 7, "stamina": 7, "pressing": 6, "tackling": 6},
    "CAM": {"first_touch": 9, "dribbling": 8, "vision": 8, "passing": 8, "composure": 7, "off_ball_movement": 7, "finishing": 6, "pressing": 4},
    "LM": {"dribbling": 8, "crossing": 8, "acceleration": 8, "stamina": 8, "first_touch": 7, "passing": 6, "defensive_awareness": 4},
    "RM": {"dribbling": 8, "crossing": 8, "acceleration": 8, "stamina": 8, "first_touch": 7, "passing": 6, "defensive_awareness": 4},
    "LW": {"dribbling": 9, "acceleration": 9, "first_touch": 8, "finishing": 7, "off_ball_movement": 7, "stamina": 7, "passing": 6},
    "RW": {"dribbling": 9, "acceleration": 9, "first_touch": 8, "finishing": 7, "off_ball_movement": 7, "stamina": 7, "passing": 6},
    "ST": {"finishing": 9, "composure": 8, "off_ball_movement": 8, "positioning": 7, "first_touch": 7, "heading": 6, "strength": 6, "pressing": 5},
    "CF": {"finishing": 8, "first_touch": 8, "dribbling": 7, "vision": 7, "off_ball_movement": 8, "composure": 7, "pressing": 6},
}

LEVEL_OFFSET = {"beginner": -14, "intermediate": -6, "advanced": 0, "elite": 6}

# Weighting used for the single "overall" number shown on the card. Position-specific so a
# keeper and a striker are not judged on the same axis (spec §27 warns against one global score).
OVERALL_WEIGHTS: dict[str, tuple[str, ...]] = {
    "GK": ("positioning", "anticipation", "composure", "decision_making", "passing", "strength"),
    "CB": ("positioning", "tackling", "heading", "defensive_awareness", "strength", "passing"),
    "LB": ("defensive_awareness", "tackling", "crossing", "stamina", "acceleration", "passing"),
    "RB": ("defensive_awareness", "tackling", "crossing", "stamina", "acceleration", "passing"),
    "CDM": ("positioning", "defensive_awareness", "passing", "tackling", "vision", "pressing"),
    "CM": ("passing", "first_touch", "vision", "decision_making", "pressing", "stamina"),
    "CAM": ("first_touch", "passing", "vision", "dribbling", "composure", "off_ball_movement"),
    "LM": ("crossing", "dribbling", "first_touch", "acceleration", "stamina", "passing"),
    "RM": ("crossing", "dribbling", "first_touch", "acceleration", "stamina", "passing"),
    "LW": ("dribbling", "first_touch", "acceleration", "finishing", "off_ball_movement", "passing"),
    "RW": ("dribbling", "first_touch", "acceleration", "finishing", "off_ball_movement", "passing"),
    "ST": ("finishing", "composure", "off_ball_movement", "first_touch", "positioning", "heading"),
    "CF": ("finishing", "first_touch", "vision", "off_ball_movement", "dribbling", "composure"),
}


@dataclass
class Baseline:
    attributes: dict[str, int]
    overall: int
    potential: int
    reasons: list[str]


def _clamp(value: float, low: int = 1, high: int = 99) -> int:
    return int(max(low, min(high, round(value))))


def derive_baseline(*, position: str, age: int, level: str, preferred_foot: str, height_cm: int | None = None) -> Baseline:
    """Position profile ± level offset ± age curve. Deterministic and explainable."""
    if position not in POSITION_BASELINE:
        raise ValueError(f"unknown position {position}")
    base = POSITION_BASELINE[position]
    offset = LEVEL_OFFSET.get(level, 0)
    reasons = [
        f"Position {position} sets the attribute profile (highest baselines: {', '.join(sorted(base, key=lambda k: -base[k])[:3])})",
        f"Level '{level}' applies a {offset:+d} offset to every attribute",
    ]
    # Physical curve: peak 24-28, decline after 31, lower before 18.
    if age < 18:
        phys_mod, phys_note = -4, "Age under 18 caps physical attributes for safe loading"
    elif age <= 20:
        phys_mod, phys_note = -1, "Age 17-20: physical attributes still developing"
    elif age <= 29:
        phys_mod, phys_note = 2, "Age 21-29 is the physical peak window"
    elif age <= 33:
        phys_mod, phys_note = -1, "Age 30-33: slight physical decline, experience compensated"
    else:
        phys_mod, phys_note = -4, "Age 34+: physical decline, mental/tactical attributes compensated"
    reasons.append(phys_note)
    mental_mod = 0
    if age >= 27:
        mental_mod = 2
        reasons.append("Age 27+ adds experience to mental and tactical attributes")

    attributes: dict[str, int] = {}
    for group, names in ATTRIBUTES.items():
        for name in names:
            value = 35 + (base.get(name, 5) * 3) + offset
            if group == "physical":
                value += phys_mod
            if group in ("mental", "tactical"):
                value += mental_mod
            if height_cm:
                if name in ("heading", "strength"):
                    value += max(-3, min(5, round((height_cm - 178) / 8)))
                if name in ("agility", "acceleration", "balance"):
                    value -= max(-2, min(4, round((height_cm - 178) / 12)))
            if name == "finishing" and preferred_foot == "both":
                value += 1
            attributes[name] = _clamp(value, 20, 90)

    overall = compute_overall(position, attributes)
    growth_headroom = max(0, 90 - overall)
    potential = _clamp(overall + int(growth_headroom * (0.35 if age <= 21 else 0.2 if age <= 27 else 0.1)), overall, 99)
    reasons.append(f"Potential weighted by age band ({'high' if age <= 21 else 'moderate' if age <= 27 else 'limited'})")
    return Baseline(attributes=attributes, overall=overall, potential=potential, reasons=reasons)


def compute_overall(position: str, attributes: dict[str, int]) -> int:
    keys = OVERALL_WEIGHTS.get(position, ALL_ATTRIBUTES[:6])
    values = [attributes.get(k, 40) for k in keys]
    return _clamp(sum(values) / len(values)) if values else 40


def derive_archetype(position: str, attributes: dict[str, int]) -> tuple[str, float, list[str]]:
    """Score every archetype valid for the position; return name, match %, reasons."""
    scored: list[tuple[str, float, list[str]]] = []
    for name, spec in ARCHETYPES.items():
        if position not in spec["positions"]:
            continue
        core: dict[str, int] = spec["core"]
        total_weight = sum(core.values()) or 1
        weighted = sum(attributes.get(attr, 40) * weight for attr, weight in core.items())
        average = weighted / total_weight
        match = max(0.0, min(1.0, (average - 35) / 55))
        reasons = [
            f"Core attributes for {name}: " + ", ".join(f"{a} {attributes.get(a, 40)}" for a in core),
            f"Weighted core value {average:.1f} maps to {match * 100:.0f}% archetype fit",
        ]
        scored.append((name, round(match, 3), reasons))
    if not scored:
        return "Developing Player", 0.0, [f"No archetype mapped for position {position}; general development recommended"]
    scored.sort(key=lambda item: (-item[1], item[0]))
    name, match, reasons = scored[0]
    spec = ARCHETYPES[name]
    reasons = [
        f"Selected from {len(scored)} archetypes valid for {position}",
        *reasons,
        f"Strengths of this profile: {', '.join(spec['strengths'])}",
        f"Development trade-offs: {', '.join(spec['weaknesses'])}",
    ]
    runner_up = scored[1][0] if len(scored) > 1 else None
    if runner_up:
        reasons.append(f"Next best fit: {runner_up} ({scored[1][1] * 100:.0f}%) — progression tree allows switching later")
    return name, match, reasons


def attribute_gaps(attributes: dict[str, int], focus: tuple[str, ...]) -> list[tuple[str, int]]:
    """Weakest first, restricted to the attributes that matter for the current goal."""
    relevant = [a for a in focus if a in attributes] or list(attributes)
    return sorted(((a, attributes[a]) for a in relevant), key=lambda item: item[1])
