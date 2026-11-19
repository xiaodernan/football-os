"""The Opposition Analyst — the blueprint is written before a ball is kicked.

A coach names the opponent's shape and their own shape; the machine reads the athlete's own
fingerprint and the basket's tactics chapters, and authors a four-phase plan under a strict
contract. It refuses what it cannot verify — never a plan about a team it was never told about.

    START -> gather -> draft -> verify -> repair -> END

\* ``gather`` (deterministic): the caller's own 28-day training ledger (status mix, top drill
  categories, XP earned) joined with the player's position/archetype/goal, plus the three basket
  chapters nearest to `{opponent_shape} {own_shape} {levers}` under `category=tactics`, whole text.
\* ``draft`` (the model, under contract): four phases (each {name, trigger, action}), ≥4 concrete
  blocks, ≥2 counter-arguments the opponent can reach for, evidence mandatory, and an ``echo`` token
  drawn from the opponent_shape string itself.
\* ``verify`` (deterministic): schema, counts, echo-in-input; one bounded ``repair`` names the failure.
\* ``repair`` paints the failure verbatim; a brief still violating the contract is refused.

Every model call is ledgered (`tactics.opponent_analyst.draft` / `.repair`); the gate is the same
LangGraph compiled walk as the Season Brief, byte-identical `graph_trace` bookends.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import new_public_id
from app.models import (
    CoachMessage,
    KnowledgeChunk,
    KnowledgeDocument,
    TrainingDrill,
    TrainingSession,
    UserPlayer,
)
from app.providers import LlmResult, get_llm_provider
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.knowledge.retrieval import Filters, search
from app.services.model_ledger import budget_exhausted, record_model_call_safely

_StateGraph: Any = None
_LG_END: Any = None
try:
    from langgraph.graph import END as _LG_END_
    from langgraph.graph import StateGraph as _StateGraph_

    _StateGraph = _StateGraph_
    _LG_END = _LG_END_
except ImportError:  # pragma: no cover - the image pins langgraph; this branch is for bare venvs
    _StateGraph = None
    _LG_END = None

logger = logging.getLogger("football_os.opponent_analyst")

MAX_PACKET_BYTES = 120_000

_SYSTEM_DRAFT = """\
You are the Opposition Analyst inside FOOTBALL OS. You read one athlete's fingerprint, three
whole tactics chapters from the house library, the opponent's shape and the coach's own shape,
and you author a four-phase plan for the match. You are not a commentator — you are the analyst
the team room listens to before a ball is kicked.

You receive one JSON object and MUST return exactly one JSON object under this contract,
nothing else — no markdown, no preamble, no commentary outside the object:

{
  "headline": "one actionable sentence, <= 150 chars",
  "phases": [
    {"name": "phase name", "trigger": "the event that starts the phase", "action": "the concrete football action"},
    ... exactly four phases ...
  ],
  "blocks": ["at least 4 concrete football actions; no vibe words like 'intensity', 'focus', 'dynamics'"],
  "counters": ["at least 2 things the opponent will try to do to us"],
  "one_more": "the single next step after this plan closes, <= 110 chars",
  "evidence": ["at least 3 references traceable to the inputs (shapes, positions, numbers, chapter names)"],
  "echo": "a token you can ONLY know if you read the opponent_shape string you were given"
}

Rules:

1. `phases` must be exactly four. Each phase's `action` is a football action, not an emotion.
2. `blocks` and `counters` are actions, not adjectives. Name the drill, the zone, the pass lane, the trigger.
3. `echo` MUST contain a single distinctive TOKEN taken verbatim from the opponent_shape string (a number, formation code or word). Do not paraphrase it.
4. `evidence` must carry at least three traceable references to things in the JSON you received.
5. Chapters are the why; the fingerprint is who you are for. Answer in the caller's data language (default English).
6. No greetings, no hedging, no meta-commentary — the object IS the product.
"""

_SYSTEM_REPAIR = """\
You are the same Opposition Analyst, called back because the previous JSON violated its contract.
Below you receive the failure the verifier names and the draft you wrote. Return exactly one JSON
object under the same contract, fixing what the verifier names — invent nothing beyond the JSON
snapshot you were given.
"""

_SYSTEM_DRAFT_CHARTER = LIBRARY_CHARTER + _SYSTEM_DRAFT
_SYSTEM_REPAIR_CHARTER = LIBRARY_CHARTER + _SYSTEM_REPAIR


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rsplit("\n", 1)[0]


def _string_field(value: Any, name: str, *, max_length: int) -> str:
    out = str(value or "").strip()
    if not out:
        raise ValueError(f"{name} missing")
    if len(out) > max_length:
        raise ValueError(f"{name} must be at most {max_length} chars")
    return out


@dataclass
class OpponentAnalystState:
    opponent_shape: str = ""
    own_shape: str = ""
    levers: str = ""
    locale: str = "en"
    available: bool = True
    error: str | None = None
    player_id: str | None = None
    snapshot: dict[str, Any] = field(default_factory=dict)
    packets: list[dict[str, Any]] = field(default_factory=list)
    draft: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    verify_ok: bool = False
    verify_failures: list[str] = field(default_factory=list)
    repair_passes: int = 0
    provider: str = "unknown"
    model: str = "unknown"
    demo_mode: bool = True
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cache_reported: bool = False
    context_bytes: int = 0
    timings_ms: dict[str, int] = field(default_factory=dict)
    graph_trace: list[str] = field(default_factory=list)


def _node_gather(state: OpponentAnalystState, db: Session, *, user_id: str) -> OpponentAnalystState:
    started = time.perf_counter()
    player = db.scalar(select(UserPlayer).where(UserPlayer.user_id == user_id).order_by(UserPlayer.created_at))
    if player is None:
        state.available = False
        state.error = "create your player profile first (POST /api/v1/players)"
        state.timings_ms["gather"] = int((time.perf_counter() - started) * 1000)
        return state

    state.player_id = player.id
    since = datetime.now(UTC) - timedelta(days=28)
    sessions = db.scalars(
        select(TrainingSession).where(TrainingSession.player_id == player.id, TrainingSession.created_at >= since)
    ).all()
    completed = [s for s in sessions if s.status == "completed"]
    xp_28d = sum(int(s.xp_awarded or 0) for s in completed)

    drill_ids = {s.drill_id for s in sessions}
    drills_by_id = {d.id: d for d in db.scalars(select(TrainingDrill).where(TrainingDrill.id.in_(list(drill_ids)))).all()} if drill_ids else {}
    category_counts: dict[str, int] = {}
    for s in sessions:
        drill = drills_by_id.get(s.drill_id)
        if drill and drill.category:
            category_counts[drill.category] = category_counts.get(drill.category, 0) + 1

    query = f"{state.opponent_shape} {state.own_shape} {state.levers}".strip()
    found = search(db, query, filters=Filters(category="tactics", locale=state.locale or "en"), mode="hybrid", top_k=6)
    packets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in found.hits:
        slug = hit.document_slug
        if not slug or slug in seen or len(packets) >= 3:
            continue
        seen.add(slug)
        document = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.slug == slug))
        body = ""
        if document is not None:
            candidate = Path(settings.knowledge_dir) / document.source_path if document.source_path else None
            if candidate and candidate.is_file():
                try:
                    raw = candidate.read_text(encoding="utf-8")
                except OSError:
                    raw = ""
                front = re.match(r"\A---\n.*?\n---\n", raw, flags=re.DOTALL)
                body = raw[front.end():] if front else raw
            if not body.strip():
                chunks = db.scalars(
                    select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id).order_by(KnowledgeChunk.ordinal)
                ).all()
                body = "\n\n".join(chunk.text for chunk in chunks)
        if not body.strip():
            continue
        body = _clip(body, max(10_000, MAX_PACKET_BYTES // 3))
        packets.append(
            {
                "ref": len(packets) + 1,
                "slug": slug,
                "title": getattr(hit, "title", slug) or slug,
                "score": round(getattr(hit, "score", 0.0), 4),
                "bytes": len(body),
                "body": body,
            }
        )

    if not packets:
        state.available = False
        state.error = "the basket holds no tactics chapter near this shape pair — the library cannot ground a plan it does not hold"
        state.timings_ms["gather"] = int((time.perf_counter() - started) * 1000)
        return state

    state.snapshot = {
        "position": str(player.position),
        "secondary_positions": [str(p) for p in (player.secondary_positions or [])][:4],
        "preferred_foot": str(player.preferred_foot),
        "weak_foot_rating": int(player.weak_foot_rating),
        "age": int(player.age),
        "level": str(player.level),
        "goal": str(player.goal),
        "archetype": str(player.archetype),
        "overall": int(player.overall),
        "potential": int(player.potential),
        "xp": int(player.xp),
        "level_number": int(player.level_number),
        "sessions_28d": len(sessions),
        "completed_28d": len(completed),
        "xp_28d": int(xp_28d),
        "top_categories_28d": dict(sorted(category_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:4]),
        "opponent_shape": state.opponent_shape,
        "own_shape": state.own_shape,
        "levers": state.levers,
    }
    state.packets = packets
    state.context_bytes = sum(int(pkt["bytes"]) for pkt in packets)
    state.timings_ms["gather"] = int((time.perf_counter() - started) * 1000)
    logger.info("opponent_analyst.gather packets=%d bytes=%d", len(packets), state.context_bytes)
    return state


def _prompt_payload(state: OpponentAnalystState) -> str:
    return json.dumps(
        {
            "intent": "opponent_analyst",
            "snapshot": state.snapshot,
            "chapters": [
                {"ref": pkt["ref"], "title": pkt["title"], "body": pkt["body"]} for pkt in state.packets
            ],
        },
        ensure_ascii=False,
    )


def _parse_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"\A```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*\Z", "", cleaned)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _node_draft(state: OpponentAnalystState, db: Session) -> OpponentAnalystState:
    if not state.available:
        return state
    if budget_exhausted(db):
        state.provider = "rule-engine-demo"
        state.model = "rule-engine-demo"
        state.error = "the daily model cap is reached; the brief waits for the cap to reset"
        state.available = False
        return state
    provider = get_llm_provider()
    try:
        result = provider.complete(
            system=_SYSTEM_DRAFT_CHARTER,
            prompt=_prompt_payload(state),
            max_tokens=1100,
            temperature=0.3,
            prompt_cache_key="tactics.opponent_analyst.draft",
        )
    except Exception as error:  # noqa: BLE001 — the gateway is the risk; the door must stay up.
        result = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        state.error = (result.error or "unreachable gateway")[:160]
    record_model_call_safely(result=result, feature="tactics.opponent_analyst.draft")
    state.input_tokens += result.input_tokens or 0
    state.output_tokens += result.output_tokens or 0
    state.cached_input_tokens += result.cached_input_tokens or 0
    state.cache_reported = state.cache_reported or bool(result.cache_reported)
    state.provider = result.provider
    state.model = result.model
    state.demo_mode = bool(result.demo_mode)
    if result.error:
        state.available = False
        return state
    state.draft = (result.text or "").strip()
    state.payload = _parse_json_object(state.draft) or {}
    return state


def _contract_failures(payload: dict[str, Any], opponent_shape: str) -> list[str]:
    failures = []
    headline = payload.get("headline")
    if not isinstance(headline, str) or not headline.strip():
        failures.append("headline missing or empty")
    elif len(headline) > 200:
        failures.append(f"headline too long ({len(headline)} chars)")

    phases = payload.get("phases")
    if not isinstance(phases, list) or len(phases) != 4:
        failures.append("phases must be exactly four objects")
    else:
        for index, phase in enumerate(phases):
            if not isinstance(phase, dict):
                failures.append(f"phases[{index}] is not an object")
                continue
            for key in ("name", "trigger", "action"):
                value = phase.get(key)
                if not isinstance(value, str) or not value.strip():
                    failures.append(f"phases[{index}].{key} missing")

    blocks = payload.get("blocks")
    if not isinstance(blocks, list) or len(blocks) < 4:
        failures.append("blocks must name at least four concrete actions")
    elif any(not isinstance(item, str) or not item.strip() for item in blocks):
        failures.append("blocks contain an empty action")

    counters = payload.get("counters")
    if not isinstance(counters, list) or len(counters) < 2:
        failures.append("counters must name at least two opponent actions")
    elif any(not isinstance(item, str) or not item.strip() for item in counters):
        failures.append("counters contain an empty item")

    one_more = payload.get("one_more")
    if not isinstance(one_more, str) or not one_more.strip():
        failures.append("one_more missing")
    elif len(one_more) > 160:
        failures.append(f"one_more too long ({len(one_more)} chars)")

    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 3:
        failures.append("evidence must carry at least three traceable references")
    elif any(not isinstance(item, str) or not item.strip() for item in evidence):
        failures.append("evidence contains an empty reference")

    echo = payload.get("echo")
    if not isinstance(echo, str) or not echo.strip():
        failures.append("echo missing — the plan never named the opponent it plans against")
    elif echo.lower().strip() not in opponent_shape.lower():
        failures.append(f"echo {echo!r} does not appear in the opponent_shape string")

    return failures


def _node_verify(state: OpponentAnalystState, db: Session) -> OpponentAnalystState:  # noqa: ARG001
    if not state.available:
        return state
    failures = _contract_failures(state.payload, state.opponent_shape)
    state.verify_failures = failures
    state.verify_ok = not failures
    logger.info("opponent_analyst.verify ok=%s failures=%s", state.verify_ok, failures)
    return state


def _node_repair(state: OpponentAnalystState, db: Session) -> OpponentAnalystState:
    if not state.available or state.verify_ok or state.repair_passes >= 1:
        return state
    state.repair_passes = 1
    if budget_exhausted(db):
        return state
    provider = get_llm_provider()
    try:
        result = provider.complete(
            system=_SYSTEM_REPAIR_CHARTER,
            prompt=json.dumps(
                {
                    "intent": "opponent_analyst_repair",
                    "failure": state.verify_failures,
                    "draft": state.draft,
                    "snapshot": state.snapshot,
                    "chapters": [
                        {"ref": pkt["ref"], "title": pkt["title"], "body": pkt["body"][:6000]}
                        for pkt in state.packets
                    ],
                },
                ensure_ascii=False,
            ),
            max_tokens=1100,
            temperature=0.2,
            prompt_cache_key="tactics.opponent_analyst.repair",
        )
    except Exception as error:  # noqa: BLE001
        result = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
    record_model_call_safely(result=result, feature="tactics.opponent_analyst.repair")
    state.input_tokens += result.input_tokens or 0
    state.output_tokens += result.output_tokens or 0
    state.cached_input_tokens += result.cached_input_tokens or 0
    state.cache_reported = state.cache_reported or bool(result.cache_reported)
    if result.error and not (result.text or "").strip():
        return state
    state.draft = (result.text or "").strip()
    state.payload = _parse_json_object(state.draft) or {}
    failures = _contract_failures(state.payload, state.opponent_shape)
    state.verify_failures = failures
    state.verify_ok = not failures
    return state


def compile_chain() -> list[tuple[str, Any]]:
    """The compiled edge table — documentation for the walk, and the ordering the fallback replays."""
    return [
        ("gather", "_node_gather(state, db, user_id=user_id)"),
        ("draft", "_node_draft(state, db)"),
        ("verify", "_node_verify(state, db)"),
        ("repair", "_node_repair(state, db)"),
        ("END", None),
    ]


def _compile_langgraph(db: Session, user_id: str) -> Any | None:
    if _StateGraph is None:
        return None

    def _wrap(name: str, fn: Any) -> Any:
        def node(state: OpponentAnalystState) -> OpponentAnalystState:
            state.graph_trace.append(name)
            return fn(state)

        node.__name__ = name
        return node

    builder = _StateGraph(OpponentAnalystState)
    builder.add_node("gather", _wrap("gather", lambda state: _node_gather(state, db, user_id=user_id)))
    builder.add_node("draft", _wrap("draft", lambda state: _node_draft(state, db)))
    builder.add_node("verify", _wrap("verify", lambda state: _node_verify(state, db)))
    builder.add_node("repair", _wrap("repair", lambda state: _node_repair(state, db)))
    builder.set_entry_point("gather")
    builder.add_edge("gather", "draft")
    builder.add_edge("draft", "verify")
    builder.add_edge("verify", "repair")
    builder.add_edge("repair", _LG_END)
    return builder.compile()


def _walk_graph(db: Session, state: OpponentAnalystState, user_id: str) -> OpponentAnalystState:
    graph = _compile_langgraph(db, user_id)
    if graph is None:
        return _walk_legacy(db, state, user_id=user_id)
    out = graph.invoke(state)
    if isinstance(out, dict):
        state = OpponentAnalystState(**out)
    if "START" not in state.graph_trace:
        state.graph_trace = ["START", *state.graph_trace]
    if "END" not in state.graph_trace:
        state.graph_trace = [*state.graph_trace, "END"]
    return state


def _walk_legacy(db: Session, state: OpponentAnalystState, *, user_id: str) -> OpponentAnalystState:
    state.graph_trace.append("START")
    nodes = [
        ("gather", lambda: _node_gather(state, db, user_id=user_id)),
        ("draft", lambda: _node_draft(state, db)),
        ("verify", lambda: _node_verify(state, db)),
        ("repair", lambda: _node_repair(state, db)),
    ]
    # The legacy fallback uses Python cell closure: each lambda reuses `state`, whose binding is
    # mutated at the point the lambda is called, which is why the order above is the whole answer.
    for name, node in nodes:
        if len(state.graph_trace) >= 9:
            state.available = False
            state.error = "graph exceeded 8 node visits"
            break
        state.graph_trace.append(name)
        state = node()
    state.graph_trace.append("END")
    return state


def compute_opponent_brief(
    db: Session,
    *,
    opponent_shape: str,
    own_shape: str,
    levers: str = "",
    locale: str = "en",
    user_id: str,
) -> dict[str, Any]:
    opponent_shape = str(opponent_shape).strip()
    own_shape = str(own_shape).strip()
    levers = str(levers or "").strip()
    if not opponent_shape or len(opponent_shape) > 200:
        raise ValueError("opponent_shape must be 1..200 chars")
    if not own_shape or len(own_shape) > 200:
        raise ValueError("own_shape must be 1..200 chars")
    if len(levers) > 280:
        raise ValueError("levers must be at most 280 chars")

    state = OpponentAnalystState(opponent_shape=opponent_shape, own_shape=own_shape, levers=levers, locale=locale or "en")
    started = time.perf_counter()
    state = _walk_graph(db, state, user_id)
    _elapsed = int((time.perf_counter() - started) * 1000)
    logger.info("opponent_analyst.done total_ms=%d cached=%s", _elapsed, state.cached_input_tokens)
    verify = {"ok": state.verify_ok, "repair_passes": state.repair_passes, "failures": state.verify_failures}

    if not state.available or not state.verify_ok:
        payload: dict[str, Any] = {
            "answered": False,
            "headline": None,
            "phases": [],
            "blocks": [],
            "counters": [],
            "one_more": None,
            "evidence": [],
            "graph_trace": state.graph_trace,
            "verify": verify,
            "provider": state.provider,
            "model": state.model,
            "demo_mode": state.demo_mode,
            "error": state.error or "the plan refused the contract — treat every byte as unverified",
            "context_bytes": state.context_bytes,
        }
        _persist(db, user_id=user_id, state=state, payload=payload, answered=False, headline="")
        return payload

    headline = str(state.payload.get("headline", "")).strip()
    payload: dict[str, Any] = {
        "answered": True,
        "headline": headline,
        "phases": [
            {"name": str(p.get("name", "")).strip(), "trigger": str(p.get("trigger", "")).strip(), "action": str(p.get("action", "")).strip()}
            for p in (state.payload.get("phases") or [])
        ],
        "blocks": [str(b).strip() for b in (state.payload.get("blocks") or [])],
        "counters": [str(c).strip() for c in (state.payload.get("counters") or [])],
        "one_more": str(state.payload.get("one_more", "")).strip(),
        "evidence": [str(item).strip() for item in (state.payload.get("evidence") or [])][:6],
        "chapters_used": [
            {"ref": pkt["ref"], "slug": pkt["slug"], "title": pkt["title"], "score": pkt["score"]}
            for pkt in state.packets
        ],
        "graph_trace": state.graph_trace,
        "verify": verify,
        "provider": state.provider,
        "model": state.model,
        "demo_mode": state.demo_mode,
        "player_id": state.player_id,
        "snapshot_sessions_28d": (state.snapshot or {}).get("sessions_28d"),
        "context_bytes": state.context_bytes,
    }
    _persist(db, user_id=user_id, state=state, payload=payload, answered=True, headline=headline)
    return payload


def _persist(
    db: Session,
    *,
    user_id: str,
    state: OpponentAnalystState,
    payload: dict[str, Any],
    answered: bool,
    headline: str,
) -> None:
    try:
        db.add(
            CoachMessage(
                id=new_public_id("msg"),
                user_id=user_id,
                player_id=state.player_id or None,
                role="coach",
                kind="opponent_brief",
                content=headline or (state.error or "the plan refused the contract"),
                structured={
                    "answered": answered,
                    "verify": {"ok": state.verify_ok, "repair_passes": state.repair_passes, "failures": state.verify_failures},
                    "provider": state.provider,
                    "model": state.model,
                    "payload": payload,
                },
                reasons=[
                    "the four-phase plan is the model's reading of the shape pair, not a template",
                    f"verify: {'all contract rules hold' if state.verify_ok else 'refused at the gate'}",
                    f"chapters loaded: {[pkt['slug'] for pkt in state.packets]}",
                ],
                confidence=0.72 if answered else 0.0,
                provider=state.provider,
                model=state.model,
                demo_mode=bool(state.demo_mode),
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001 — persistence never sinks the door's answer
        db.rollback()
        logger.exception("opponent_analyst.persist_failed")
