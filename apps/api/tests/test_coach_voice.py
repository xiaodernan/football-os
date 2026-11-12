"""The coach's voice: what crosses the wire to the model, and what reaches the player.

Two defects motivated these cases, both found by pointing the product at a real provider rather than
at the mock (measured 2026-11-12):

* the question was not in the prompt, so "how do I scan before receiving?" was answered with a
  paragraph about the recommended rondo — the word "scan" appeared nowhere in the reply;
* the template and the model's reply were concatenated, so the reader saw the same recommendation
  twice in two voices and the answer to the question came second.

A unit test cannot prove a model answers well. It can prove the question and the measurements are
*in the prompt*, that the rules are stated, and that an absent model reply falls back rather than
leaving an empty bubble — which is what these cases do.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.services import coach_voice


def _player() -> SimpleNamespace:
    return SimpleNamespace(
        position="CM",
        age=19,
        level=3,
        preferred_foot="right",
        goal="become_box_to_box",
        archetype="engine",
        archetype_match=0.72,
        weak_foot_rating=41,
        attributes={
            "first_touch": 53,
            "ball_control": 44,
            "composure": 44,
            "passing": 51,
            "pressing": 48,
            "stamina": 57,
            "weak_foot": 41,
            # Not in VOICE_ATTRIBUTES: a full dictionary would bury the numbers the pick was scored on.
            "heading": 33,
        },
    )


def _structured() -> dict[str, object]:
    return {
        "recommendation": {
            "title": "Rondo Shapes: Press Resistance",
            "objective": "Keep possession through the press.",
            "duration_min": 18,
            "difficulty": 3,
            "coaching_points": ["Pass with the correct surface", "Move after passing"],
        }
    }


def _prompt(**overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "question": "How do I scan before receiving the ball?",
        "intent": "today",
        "player": _player(),
        "structured": _structured(),
        "reasons": ["Scored 5.95 against 23 eligible drills", "Valid for CM"],
    }
    kwargs.update(overrides)
    return json.loads(coach_voice.build_prompt(**kwargs))  # type: ignore[arg-type]


def test_the_question_crosses_the_wire() -> None:
    block = _prompt()
    assert block["QUESTION"] == "How do I scan before receiving the ball?"


def test_the_measurements_cross_the_wire() -> None:
    block = _prompt()
    facts = block["FACTS"]
    assert facts["attributes"] == {
        "first_touch": 53,
        "ball_control": 44,
        "passing": 51,
        "pressing": 48,
        "composure": 44,
        "stamina": 57,
        "weak_foot": 41,
    }
    assert "heading" not in facts["attributes"]
    assert block["PLAYER"]["archetype"] == "engine"
    assert block["SESSION"]["duration_min"] == 18
    assert block["WHY"][0].startswith("Scored 5.95")


def test_a_missing_fact_is_absent_rather_than_invented() -> None:
    player = _player()
    del player.attributes  # a player row built before the attribute tier existed
    block = _prompt(player=player)
    assert block["FACTS"]["attributes"] == {}
    assert block["FACTS"]["weak_foot_rating"] == 41


def test_the_rules_are_in_the_system_message() -> None:
    system = coach_voice.SYSTEM
    assert "Answer the player's QUESTION in your first sentence" in system
    assert "Never invent" in system
    assert "Data unavailable" in system
    # The page renders this beside the structured panel, so prose with headings would duplicate it.
    assert "No headings" in system


def test_a_model_reply_replaces_the_template_rather_than_following_it() -> None:
    template = "Today: Rondo Shapes: Press Resistance. Keep possession through the press."
    answered = "Turn your shoulders before the pass arrives, then open toward the free lane."
    assert coach_voice.compose_message(template, answered) == answered
    # Whitespace from a provider is not an answer.
    assert coach_voice.compose_message(template, "   \n ") == template
    # A demo provider, a capped turn and a failed call all land here.
    assert coach_voice.compose_message(template, "") == template


def test_the_prompt_is_one_compact_json_object() -> None:
    """The adapter sends this string verbatim, so it must parse and must not be pretty-printed."""
    raw = coach_voice.build_prompt(
        question="q",
        intent="today",
        player=_player(),
        structured=_structured(),
        reasons=["r"],
    )
    assert "\n" not in raw
    assert json.loads(raw)["INTENT"] == "today"
