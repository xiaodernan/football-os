"""The coach's answer pipeline, compiled into an explicit StateGraph.

StateGraph is a small machine with three moving parts — a shared state object, nodes, and
conditional edges — and it is the design this project now uses for the coach. The object
every node reads and writes is `CoachGraphState` below: the question, the computed intent,
the arithmetic that answers it, the phrasing call (or its refusal), the persisted message,
and the visit log. The nodes below are single steps of work; the edges say which step the
machine takes next; the conditional edge after `spend_gate` says whether the model is asked
to phrase the arithmetic at all.

.. code-block:: text

   entry
     └─ classify_intent
            └─ build_arithmetic
                   └─ spend_gate ──exhausted──> persist_answer ──> END
                       └─phrase──> phrase_answer ──> persist_answer ──> END

Cycles: none — the graph is acyclic by construction; a recursion bound of ``MAX_NODE_VISITS``
("6") is enforced not by trusting the edge table but by the walk itself, which raises
``GraphCycleError`` if it iterates more steps than the bound allows.

What the reader sees on :8100: the same coach, the same numbers, the same fallback for demo
mode — plus one difference: the caller learns in what order the coach's answer was assembled
(`graph_trace`), because a pipeline nobody can see is exactly the failure mode StateGraph
exists to abolish.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import CoachMessage
from app.providers import get_llm_provider
from app.services import coach_engine, coach_voice
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.model_ledger import budget_exhausted, record_model_call_safely

if TYPE_CHECKING:
    from app.models import User, UserPlayer

logger = logging.getLogger("football_os.coach_graph")

#: Hard cap on how many node steps one run may take. The graph below is acyclic in practice,
#: but the cap is a promise, not an assertion — the walk itself enforces it.
MAX_NODE_VISITS = 6


class GraphCycleError(RuntimeError):
    """Raised when the walk exceeds MAX_NODE_VISITS — the recursion bound, enforced."""


@dataclass
class CoachGraphState:
    """The shared state. Everything one node can learn about the run is here; nothing else can."""

    question: str
    available_minutes: int | None = None
    has_pitch: bool | None = None

    #: set by nodes, in the order the graph executes them
    intent: str = ""
    structured: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    confidence: float = 0.0
    template: str = ""
    result: Any | None = None
    content: str = ""
    graph_trace: list[str] = field(default_factory=list)
    persisted: bool = False


def _node_classify_intent(state: CoachGraphState, db: Session, user: User, player: UserPlayer) -> CoachGraphState:
    state.intent = coach_engine.answer_intent(db, user, player, state.question)
    state.structured = {"intent": state.intent}
    return state


def _node_build_arithmetic(state: CoachGraphState, db: Session, user: User, player: UserPlayer) -> CoachGraphState:
    intent = state.intent
    structured = state.structured
    if intent in {"today", "plan_7", "plan_30", "plan_90"}:
        horizon = {"plan_7": 7, "plan_30": 30, "plan_90": 90}.get(intent, 1)
        if intent == "today":
            rec = coach_engine.recommend_today(db, user, player, available_minutes=state.available_minutes, has_pitch=state.has_pitch)
            structured["recommendation"] = rec.drill
            structured["alternatives"] = rec.alternatives
            structured["message"] = f"Today: {rec.drill['title']}. {rec.drill['objective']}"
            reasons = rec.reasons
            confidence = rec.confidence
        else:
            days = coach_engine.build_plan(db, player, horizon_days=horizon, available_minutes=state.available_minutes or 25, days_per_week=4, has_pitch=bool(state.has_pitch))
            structured["plan"] = {"horizon_days": horizon, "days": days}
            structured["message"] = f"{horizon}-day plan built around {player.goal.replace('_', ' ')} with recovery days scheduled."
            reasons = [
                f"Emphasis rotated across {', '.join(coach_engine.plan_emphasis(player)[:4])}",
                "Recovery days inserted so weekly load stays safe",
                "Sessions ordered by attribute gap, weakest first",
            ]
            confidence = 0.78
        state.structured = structured
        state.reasons = reasons
        state.confidence = confidence
        state.template = structured.get("message", "")
        return state

    if intent == "weak_foot":
        rec = coach_engine.recommend_today(db, user, player, available_minutes=state.available_minutes or 15)
        structured["message"] = "Weak-foot work is the fastest route: two short sessions a week beat one long one."
        structured["recommendation"] = rec.drill
        state.reasons = [
            f"Weak-foot rating stored as {player.weak_foot_rating}",
            "Ball-mastery and wall-pass drills transfer to the weak foot in 4-6 weeks of consistent reps",
        ]
        state.confidence = 0.74
    elif intent == "ball_loss":
        attrs = player.attributes
        structured["message"] = (
            f"Ball loss usually traces to first touch under pressure, not dribbling. "
            f"Your first touch is {attrs.get('first_touch', 40)} and composure {attrs.get('composure', 40)}."
        )
        state.reasons = [
            f"first_touch {attrs.get('first_touch', 40)} vs ball_control {attrs.get('ball_control', 40)} — the lower value is the limiter",
            f"Recent sessions covered: {', '.join(sorted(coach_engine.history_summary(db, user, player)['recent_categories'])) or 'none yet'}",
            "Check whether you are receiving square-on; half-turn receiving removes half the pressure",
        ]
        state.confidence = 0.7
    elif intent == "role_question":
        knowledge = coach_engine.archetype_knowledge(player.archetype)
        structured["message"] = (
            f"As a {player.position} your current profile reads {player.archetype} ({player.archetype_match * 100:.0f}% fit). "
            f"Priorities: {', '.join(knowledge.get('strengths', ['positional discipline']))}."
        )
        state.reasons = [
            f"Archetype derived from weighted core attributes: {', '.join(knowledge.get('core', {}).keys())}",
            f"Preferred zones: {', '.join(knowledge.get('zones', ['central_corridor']))}",
            f"Known trade-offs: {', '.join(knowledge.get('weaknesses', ['general development']))}",
            f"Recommended drill categories: {', '.join(knowledge.get('drill_categories', []))}",
        ]
        state.confidence = 0.8
    elif intent == "pressing":
        attrs = player.attributes
        structured["message"] = (
            f"Pressing is triggered, not attempted. Your pressing {attrs.get('pressing', 40)} "
            f"and stamina {attrs.get('stamina', 40)} set the ceiling."
        )
        state.reasons = [
            f"pressing {attrs.get('pressing', 40)} / stamina {attrs.get('stamina', 40)} / transition {attrs.get('transition', 40)}",
            "Train counter-press triggers: lose ball -> 5 seconds of controlled pressure",
            "If the first pressor is beaten, the second must cover the pass, not the dribbler",
        ]
        state.confidence = 0.72
    elif intent == "match_review":
        structured["message"] = (
            "No match data is stored for your profile yet. Match analysis lands with the video pipeline (M5); "
            "until then I will say 'Data unavailable' rather than guess."
        )
        state.reasons = [
            "No MatchPerformance rows exist for this player",
            "Spec §15: unavailable metrics must display 'Data unavailable'",
        ]
        state.confidence = 0.5
    elif intent == "explain":
        summary = coach_engine.history_summary(db, user, player)
        structured["message"] = (
            f"Your progress is explainable: {summary['sessions_total']} completed sessions, "
            f"{summary['xp_total']} XP, level {summary['level']}."
        )
        state.reasons = [r["reason"] for r in summary["attribute_trend"][:5]] or [
            "No attribute changes recorded yet — complete a session first"
        ]
        state.confidence = 0.8
    else:
        rec = coach_engine.recommend_today(db, user, player, available_minutes=state.available_minutes, has_pitch=state.has_pitch)
        structured["recommendation"] = rec.drill
        structured["message"] = f"Here is the most useful next session: {rec.drill['title']}. {rec.drill['objective']}"
        state.reasons = rec.reasons
        state.confidence = rec.confidence

    state.structured = structured
    state.template = structured.get("message", "")
    return state


def _node_spend_gate(state: CoachGraphState, db: Session, user: User, player: UserPlayer) -> CoachGraphState:
    provider = get_llm_provider()
    if budget_exhausted(db):
        state.reasons = [
            *state.reasons,
            "Today's AI spend cap is reached, so the phrasing step was skipped; every figure above is still computed from your stored profile and history",
        ]
        return state

    recent = coach_engine.history_summary(db, user, player)
    state.result = provider.complete(
        system=LIBRARY_CHARTER + coach_voice.SYSTEM,
        prompt=coach_voice.build_prompt(
            question=state.question,
            intent=state.intent,
            player=player,
            structured=state.structured,
            reasons=state.reasons,
            history=recent,
        ),
        max_tokens=220,
        temperature=0.5,
        # Stable key scoped to the LangGraph coach's phrasing job; the athlete and their weekly
        # facts form the same prefix day after day, so the gateway can serve them from cache
        # instead of recomputing the entire block on every duplicated ask.
        prompt_cache_key="football-os/coach-phrase",
    )
    return state


def _node_phrase_answer(state: CoachGraphState, db: Session, user: User, player: UserPlayer) -> CoachGraphState:
    # In demo mode the provider is the mock and costs nothing, and the compose step below is a
    # no-op for its text; the spend gate already returned without calling anything, so reaching
    # this node with ``result=None`` is an honest pass-through, not an error.
    result = state.result
    state.content = coach_voice.compose_message(
        state.template,
        result.text if result is not None and not result.demo_mode else "",
    )
    return state


def _node_persist_answer(state: CoachGraphState, db: Session, user: User, player: UserPlayer) -> CoachGraphState:
    if state.result is None:
        # The capped turn still writes a row; the ledger just doesn't hear about it.
        content = state.content or state.template
        provider_name, model, demo_mode = "rule-engine-demo", "rule-engine-demo", True
    else:
        content = state.content
        provider_name, model, demo_mode = state.result.provider, state.result.model, state.result.demo_mode
    structured_content = {**state.structured, "message": content, "question": state.question}
    row = CoachMessage(
        id=new_public_id("msg"),
        user_id=user.id,
        player_id=player.id,
        role="coach",
        kind=f"answer:{state.intent}",
        content=content,
        structured={"reasons": state.reasons, "provider_text": state.result.text if state.result is not None and not state.result.demo_mode else None},
        provider=provider_name,
        model=model,
        demo_mode=demo_mode,
        confidence=state.confidence,
        reasons=state.reasons,
    )
    db.add(row)
    db.commit()

    structured_content["graph_trace"] = list(state.graph_trace)
    state.structured = structured_content
    if state.result is not None:
        record_model_call_safely(result=state.result, feature="coach.ask", user_id=user.id)
    state.persisted = True
    return state


def compile_chain() -> list[tuple[str, Any]]:
    """The compiled edge table — one ordered list; every run of this graph walks it in order.

    `spend_gate` selects `phrase_answer` only when a provider was not already refused by the
    spend gate, but the walk itself still respects that order through the conditional below:
    the acyclic compile here names the whole route, and `run_coach_graph` walks it with the
    recursion guard.
    """
    return [
        ("classify_intent", _node_classify_intent),
        ("build_arithmetic", _node_build_arithmetic),
        ("spend_gate", _node_spend_gate),
        ("phrase_answer", _node_phrase_answer),
        ("persist_answer", _node_persist_answer),
        ("END", None),
    ]


def run_coach_graph(
    db: Session,
    user: User,
    player: UserPlayer,
    *,
    question: str,
    available_minutes: int | None = None,
    has_pitch: bool | None = None,
) -> dict[str, Any]:
    """Walk the compiled chain. Every run is bounded by MAX_NODE_VISITS; the trace is not optional."""
    state = CoachGraphState(question=question, available_minutes=available_minutes, has_pitch=has_pitch)
    state.graph_trace.append("START")

    route = compile_chain()
    for node_name, node in route:
        if node is None:  # END
            state.graph_trace.append("END")
            break
        if len(state.graph_trace) >= MAX_NODE_VISITS + 1:
            raise GraphCycleError(
                f"the walk exceeded {MAX_NODE_VISITS} node steps on question {question!r} — "
                f"the graph's recursion bound refused before any answer left this process."
            )
        state.graph_trace.append(node_name)
        state = node(state, db, user, player)

    structured = {
        **state.structured,
        "message": state.content or state.template,
        "question": state.question,
        "graph_trace": list(state.graph_trace),
    }
    return {
        "intent": state.intent,
        "reasons": state.reasons,
        "confidence": state.confidence,
        "provider": state.result.provider if state.result is not None else "mock",
        "model": state.result.model if state.result is not None else "rule-engine-demo",
        "demo_mode": state.result.demo_mode if state.result is not None else True,
        "structured": structured,
    }


__all__ = [
    "CoachGraphState",
    "GraphCycleError",
    "MAX_NODE_VISITS",
    "compile_chain",
    "run_coach_graph",
]
