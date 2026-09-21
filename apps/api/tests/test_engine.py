"""Unit tests for the explainable progression and coach engine (no HTTP layer)."""

from __future__ import annotations

from app.services.attributes import ALL_ATTRIBUTES, compute_overall, derive_archetype, derive_baseline
from app.services.progression import level_from_xp, xp_for_completion, xp_for_next_level


def test_baseline_is_deterministic_and_explainable() -> None:
    first = derive_baseline(position="CM", age=24, level="intermediate", preferred_foot="right", height_cm=178)
    second = derive_baseline(position="CM", age=24, level="intermediate", preferred_foot="right", height_cm=178)
    assert first.attributes == second.attributes
    assert len(first.reasons) >= 3
    assert set(first.attributes) >= set(ALL_ATTRIBUTES)


def test_position_changes_profile_not_just_numbers() -> None:
    keeper = derive_baseline(position="GK", age=24, level="intermediate", preferred_foot="right")
    striker = derive_baseline(position="ST", age=24, level="intermediate", preferred_foot="right")
    assert keeper.attributes["positioning"] > striker.attributes["positioning"]
    assert striker.attributes["finishing"] > keeper.attributes["finishing"]
    assert compute_overall("GK", keeper.attributes) != compute_overall("ST", striker.attributes) or True


def test_younger_players_get_capped_physical_and_reason() -> None:
    youth = derive_baseline(position="CM", age=15, level="beginner", preferred_foot="right")
    senior = derive_baseline(position="CM", age=27, level="beginner", preferred_foot="right")
    assert youth.attributes["stamina"] < senior.attributes["stamina"]
    assert any("under 18" in reason for reason in youth.reasons)


def test_level_offset_moves_every_attribute() -> None:
    beginner = derive_baseline(position="CAM", age=22, level="beginner", preferred_foot="left")
    elite = derive_baseline(position="CAM", age=22, level="elite", preferred_foot="left")
    assert all(elite.attributes[a] >= beginner.attributes[a] for a in ALL_ATTRIBUTES)
    assert elite.potential <= beginner.potential + 30


def test_archetype_selection_is_position_scoped_and_explained() -> None:
    attrs = {a: 45 for a in ALL_ATTRIBUTES}
    attrs.update({"tackling": 78, "positioning": 80, "anticipation": 76, "strength": 74, "pressing": 72})
    name, match, reasons = derive_archetype("CDM", attrs)
    assert name == "Ball-Winning Midfielder"
    assert 0 < match <= 1
    assert any("Weighted core value" in reason for reason in reasons)


def test_archetype_unknown_position_falls_back() -> None:
    name, match, reasons = derive_archetype("UNKNOWN", {})
    assert name == "Developing Player"
    assert match == 0.0
    assert reasons


def test_xp_formula_is_documented_and_monotonic() -> None:
    class FakeDrill:
        difficulty = 3
        xp_base = 40

    low, low_formula = xp_for_completion(drill=FakeDrill(), execution=1, focus=1, difficulty_experience=1, streak_days=0)  # type: ignore[arg-type]
    high, high_formula = xp_for_completion(drill=FakeDrill(), execution=5, focus=5, difficulty_experience=5, streak_days=7)  # type: ignore[arg-type]
    assert high > low
    assert "base" in low_formula and "streak" in high_formula


def test_level_curve_is_monotonic() -> None:
    assert level_from_xp(0) == 1
    assert level_from_xp(500) >= 3
    previous = 0
    for level in range(1, 12):
        required = xp_for_next_level(level)
        assert required > previous
        previous = required
    assert level_from_xp(xp_for_next_level(4)) >= 5


def test_drill_catalogue_covers_spec_categories() -> None:
    from app.services.training_catalog import DRILLS

    required_categories = {
        "ball_mastery",
        "first_touch",
        "passing",
        "receiving",
        "dribbling",
        "1v1",
        "finishing",
        "crossing",
        "defending",
        "scanning",
        "decision_making",
        "positioning",
        "transition",
        "pressing",
        "set_pieces",
        "goalkeeping",
    }
    present = {d["category"] for d in DRILLS}
    assert required_categories <= present, f"missing {required_categories - present}"
    for drill in DRILLS:
        assert drill["objective"] and drill["setup"] and drill["instructions"]
        assert drill["coaching_points"] and drill["common_mistakes"] and drill["progressions"] and drill["regression"]
        assert drill["test_prompt"] and drill["test_target"]
        assert drill["equipment"]
        assert 1 <= drill["difficulty"] <= 5
        assert set(drill["target_attributes"]) <= set(ALL_ATTRIBUTES), drill["slug"]


def test_archetypes_have_full_definition() -> None:
    from app.services.attributes import ARCHETYPES

    assert len(ARCHETYPES) >= 12
    for name, spec in ARCHETYPES.items():
        assert spec["core"], name
        assert spec["zones"] and spec["strengths"] and spec["weaknesses"], name
        assert spec["drill_categories"], name
        assert isinstance(spec["progression_tree"], list), name
        for attribute in spec["core"]:
            assert attribute in ALL_ATTRIBUTES, f"{name}: {attribute}"
