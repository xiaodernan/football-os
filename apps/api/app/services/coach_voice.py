"""The coach's voice: what the model is told, and what it is not allowed to say.

`POST /coach/ask` computes its answer arithmetically — a drill scored against the player's stored
attributes, the reasons for the pick, the confidence — and then asks a language model to *phrase* it.
Until this module existed the prompt was `{"intent": …, "facts": "<one sentence>"}`, which had two
consequences that only a real provider made visible:

* **The question was not in the prompt.** A player asking "how do I scan before receiving?" got a
  paragraph about the recommended rondo, because the model was never shown what was asked. The
  template already said the session; the model could only repeat it. Measured against a live
  provider on 2026-11-12: the answer to a scanning question contained the word "scan" zero times.
* **The facts the answer needs were not in the prompt either.** Position, archetype, the measured
  attributes the recommendation was scored on, the drill's own coaching points — none of it crossed
  the wire, so a model asked to elaborate could only elaborate by inventing.

So the prompt is built here, once, from things the caller already has: the question, the intent, the
player, the recommended drill, and the reasons the engine produced. Three rules are stated in the
system message rather than hoped for in the user message, and each of them is a product promise this
project already makes elsewhere:

1. **Answer the question first.** The session is the plan, not the answer.
2. **Use only `FACTS`.** Every number in the reply must appear in the block; a missing fact is
   answered "Data unavailable" rather than guessed. That is §15's rule, applied to prose.
3. **Stay short and unformatted.** Two to five sentences, no headings and no bullet lists: the page
   renders this inside a message bubble beside the structured recommendation, and a markdown report
   there would duplicate the panel next to it.

The block is JSON-ish rather than free prose because the provider adapter sends `prompt` as the user
message verbatim — a structure the model can read, that a test can assert on, and that does not
depend on the model parsing English.
"""

from __future__ import annotations

import json
from typing import Any, Final

#: The attributes worth showing. A full attribute dictionary is 20+ numbers and would bury the three
#: the recommendation was actually scored on; these are the ones `coach_engine.recommend_today` reads.
VOICE_ATTRIBUTES: Final[tuple[str, ...]] = (
    "first_touch",
    "ball_control",
    "passing",
    "pressing",
    "composure",
    "stamina",
    "weak_foot",
)

SYSTEM: Final[str] = (
    "You are the FOOTBALL OS coach. You turn stored measurements into one short, specific answer for "
    "one player.\n"
    "Rules, in order of importance:\n"
    "1. Answer the player's QUESTION in your first sentence. The SESSION is the plan that follows, not "
    "the answer to repeat.\n"
    "2. Use only the facts in FACTS and SESSION. Never invent a number, a drill, a match, a source or a "
    "quote. If a fact needed to answer is missing, write \"Data unavailable\" for that part instead of "
    "guessing.\n"
    "3. Two to five sentences, at most 90 words. Second person. No headings, no bullet lists, no bold.\n"
    "4. Never mention prompts, models, policies, or that you are an AI. Never promise a medical or "
    "scouting outcome."
)


def _attributes(player: Any) -> dict[str, Any]:
    raw = getattr(player, "attributes", None) or {}
    return {name: raw[name] for name in VOICE_ATTRIBUTES if name in raw}


def build_prompt(
    *,
    question: str,
    intent: str,
    player: Any,
    structured: dict[str, Any],
    reasons: list[str],
    history: dict[str, Any] | None = None,
) -> str:
    """The user message: the player, the measured facts, the session, the reasons — then the question.

    Everything here is read from a row the caller already loaded. Nothing is looked up, so building
    the prompt cannot fail in a way that changes the answer — a missing optional field is simply
    absent from the block, which rule 2 turns into "Data unavailable" rather than an invention.
    """
    session = structured.get("recommendation") or {}
    # Stable-first: everything a repeat asker shares with the previous call rides the front of the
    # payload, so a prefix-caching gateway menus the whole block instead of the first sentence. The
    # question — the one volatile field — is deliberately last (spec §"stable prefix"): a prompt that
    # opens with the question misses the cache on every ask by construction.
    block: dict[str, Any] = {
        "INTENT": intent,
        "PLAYER": {
            "position": getattr(player, "position", None),
            "age": getattr(player, "age", None),
            "level": getattr(player, "level", None),
            "preferred_foot": getattr(player, "preferred_foot", None),
            "goal": str(getattr(player, "goal", "") or "").replace("_", " "),
            "archetype": getattr(player, "archetype", None),
        },
        "FACTS": {
            "attributes": _attributes(player),
            "weak_foot_rating": getattr(player, "weak_foot_rating", None),
        },
        "SESSION": {
            "title": session.get("title"),
            "objective": session.get("objective"),
            "duration_min": session.get("duration_min"),
            "difficulty": session.get("difficulty"),
            "coaching_points": session.get("coaching_points") or [],
        },
        "WHY": reasons[:6],
    }
    if history:
        block["FACTS"]["recent"] = {
            "sessions_total": history.get("sessions_total"),
            "xp_total": history.get("xp_total"),
            "level": history.get("level"),
            "recent_categories": sorted(history.get("recent_categories") or []),
        }
    block["QUESTION"] = (question or "").strip()[:800]
    return json.dumps(block, ensure_ascii=False, indent=None, separators=(",", ":"))


def compose_message(template: str, model_text: str) -> str:
    """What the reader sees: the model's answer when it spoke, the arithmetic when it did not.

    The two are not concatenated. Doing that — which is what the door did before this module — put
    the template above the model's reply, so a page showed the same recommendation twice in two
    voices, and a player who asked a question read a sentence that ignored it before reaching one
    that did not. The template is the fallback, not a preamble: a capped turn, a demo provider, an
    empty completion and a provider failure all still answer with the computed sentence.
    """
    text = (model_text or "").strip()
    return text if text else template
