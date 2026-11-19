"""The Season Brief — the model is routed through the athlete's own state, not chatted at.

Coach v2 ships the deterministic engine: today's recommendation, tomorrow's drill. This
door is the complementary half: the state machine reads the athlete's *own* last 28 days,

    START -> gather -> draft -> verify -> repair -> END

and hands THAT to the language model, whose job is to author a professional's read of the
next six days — grounded line-by-line in the fingerprint, formatted as strict JSON, and
rejected wholesale the moment any rule breaks. The compiled walk runs through LangGraph's
``StateGraph`` when ``langgraph`` is importable (pinned in the image), else a bounded
hand-rolled walk; both produce the same byte-identical ``graph_trace``.

`gather` is deterministic: the caller's own player row, their 28-day session ledger
  (status mix, top drill categories by frequency, XP earned, XP gaps), their archived
  attribute deltas, and the three basket chapters nearest to the player's goal — whole
  chapters, the Deep Read discipline — all capped at ``MAX_GAMEPLAN_BYTES``. No model.
`draft` asks the provider for exactly one JSON object under one contract (three
  themes picked from the 19 catalogue categories, six day-rows with minutes in [15, 90] and
  at least three blocks each, evidence mandatory). The player's own position, archetype
  and goal are injected verbatim into the prompt, and the contract requires an echo token
  from that injection — the model cannot write a brief about an athlete it was never told about.
`verify` is deterministic: JSON parses; the schema holds; themes are unique and all
  in the whitelist; days are 1..6 in order; blocks are non-empty; focus rows all name
  one of the three themes; the echo token from the
  athlete's snapshot appears in the payload. Otherwise → `repair`.
`repair` (one pass) names the failure and asks for the artefact again. A brief that
  still violates the contract is refused, never presented as verified.

Every model call is ledgered (features ``trainings.season_brief.draft`` / ``.repair``); the
daily cap answered by ``budget_exhausted`` short-circuits the provider into an honest
refusal rather than silence.
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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import new_public_id
from app.models import (
    AttributeChange,
    CoachMessage,
    KnowledgeChunk,
    KnowledgeDocument,
    TrainingDrill,
    TrainingSession,
    UserAchievement,
    UserPlayer,
)
from app.providers import LlmResult, get_llm_provider
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.knowledge.retrieval import Filters, search
from app.services.model_ledger import budget_exhausted, record_model_call_safely
from app.services.training_catalog import CATEGORIES

# LangGraph is optional at import time; the compiled path and the fallback agree below.
# The module globals are typed as `Any` up front so mypy sees the fallback branch
# (`= None`) as a legal assignment rather than an incompatible narrowing.
_StateGraph: Any = None  # assigned at import time from langgraph, or left as the sentinel when absent
_LG_END: Any = None
try:
    from langgraph.graph import END as _LG_END_
    from langgraph.graph import StateGraph as _StateGraph_

    _StateGraph = _StateGraph_
    _LG_END = _LG_END_
except ImportError:  # pragma: no cover - the image pins langgraph; this branch exists for bare venvs
    _StateGraph = None
    _LG_END = None

logger = logging.getLogger("football_os.season_brief")

MAX_GAMEPLAN_BYTES = 120_000
#: The six day answer; contract-bound, not free-form prose.
ALLOWED_DAYS = 6
ALLOWED_BLOCKS_MIN = 3
MINUTES_MIN, MINUTES_MAX = 15, 90

_SYSTEM_DRAFT = """\
You are the Season Brief — the senior analyst inside FOOTBALL OS. You read one athlete's
actual fingerprint (their position, goal, archetype, their last 28 days of sessions, drill
categories touched, expandable attributes) and three chapters from the house library,
and you author a six-day training arc for them. You are not a chatbot; you are a coach
preparing the record that decides what happens next on the pitch.

You will be given one JSON object. You must return exactly one JSON object matching this
contract, nothing else — no markdown, no commentary, no prose outside the object:

{
  "headline": "<= 150 chars. One sentence the athlete can act on today.",
  "themes": ["exactly 3 strings, all from the catalogue list you are given"],
  "arc": [
    {"day": 1, "focus": "one of the themes", "minutes": 30, "blocks": ["drill a", "drill b", "drill c"]},
    ... six objects day 1..6, each minutes between 15 and 90, each at least 3 blocks ...
  ],
  "one_more": "the single lever that comes after the arc closes, <= 110 chars.",
  "evidence": ["strings naming numbers you were given, e.g. 'sessions=12' or 'archetype=Box-to-Box' — at least 3, every one traceable to the JSON you received"],
  "echo": "one token you can ONLY know if you read the JSON you were given (the position code, the goal string, or the archetype)"
}

Rules you never break:

1. `themes` must be exactly three distinct strings chosen from the catalogue whitelist you receive. Invented categories are refused.
2. Every block must name a concrete football action (a drill, a constraint, a game shape), never a vibe word like "intensity" or "focus".
3. Minutes are whole numbers within 15..90. `arc` is six entries, day 1 through 6.
4. `echo` MUST contain the position code or the goal token from the JSON you were given.
5. `evidence` must carry at least three traceable references to numbers, strings or labels from the JSON you received.
6. Chapters are the why; the fingerprint is the who. Cite a chapter idea in `one_more` or `headline` if it helps the athlete, without naming files.
7. Answer in the athlete's data language (default English). No greetings, no headings, no caveats — the object IS the product.
"""

_SYSTEM_REPAIR = """\
You are the same Season Brief, called back because the previous JSON violated its contract.
Below you receive the failure named by the verifier and the draft you wrote. Return exactly
one JSON object under the same contract, fixing only what the verifier named — do not invent
content beyond the JSON snapshot you were given.
"""

_SYSTEM_DRAFT_CHARTER = LIBRARY_CHARTER + _SYSTEM_DRAFT
_SYSTEM_REPAIR_CHARTER = LIBRARY_CHARTER + _SYSTEM_REPAIR


@dataclass
class SeasonBriefState:
    goal_token: str = ""
    position_token: str = ""
    player_id: str = ""
    locale: str = "en"
    available: bool = True
    error: str | None = None
    snapshot: dict[str, Any] = field(default_factory=dict)
    chapter_packets: list[dict[str, Any]] = field(default_factory=list)
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


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rsplit("\n", 1)[0]


def _load_chapter_packets(db: Session, question: str, *, locale: str, top_k: int = 3) -> list[dict[str, Any]]:
    found = search(db, question, filters=Filters(locale=locale or "en"), mode="hybrid", top_k=top_k * 2)
    seen: set[str] = set()
    packets: list[dict[str, Any]] = []
    for hit in found.hits:
        slug = getattr(hit, "document_slug", None) or ""
        if not slug or slug in seen or len(packets) >= top_k:
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
        budget = max(10_000, MAX_GAMEPLAN_BYTES // top_k)
        body = _clip(body, budget)
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
    return packets


def _node_gather(state: SeasonBriefState, db: Session, *, user_id: str) -> SeasonBriefState:
    started = time.perf_counter()
    player = db.scalar(
        select(UserPlayer).where(UserPlayer.user_id == user_id).order_by(UserPlayer.created_at)
    )
    if player is None:
        state.available = False
        state.error = "create your player profile first (POST /api/v1/players)"
        state.timings_ms["gather"] = int((time.perf_counter() - started) * 1000)
        return state

    state.player_id = player.id
    state.position_token = str(player.position or "")
    state.goal_token = str(player.goal or "")

    since = datetime.now(UTC) - timedelta(days=28)
    sessions = db.scalars(
        select(TrainingSession).where(TrainingSession.player_id == player.id, TrainingSession.created_at >= since)
    ).all()
    completed = [s for s in sessions if s.status == "completed"]
    planned = [s for s in sessions if s.status == "planned"]
    xp_28d = sum(int(s.xp_awarded or 0) for s in completed)

    drill_ids = {s.drill_id for s in sessions}
    drills_by_id = {d.id: d for d in db.scalars(select(TrainingDrill).where(TrainingDrill.id.in_(list(drill_ids)))).all()} if drill_ids else {}
    category_counts: dict[str, int] = {}
    for s in sessions:
        drill = drills_by_id.get(s.drill_id)
        if drill and drill.category:
            category_counts[drill.category] = category_counts.get(drill.category, 0) + 1
    top_categories = sorted(category_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:4]

    attribute_deltas = db.scalars(
        select(AttributeChange).where(AttributeChange.player_id == player.id, AttributeChange.created_at >= since)
    ).all()
    delta_by_attribute: dict[str, int] = {}
    for change in attribute_deltas:
        delta_by_attribute[change.attribute] = delta_by_attribute.get(change.attribute, 0) + int(change.delta)
    top_deltas = sorted(delta_by_attribute.items(), key=lambda kv: (-abs(kv[1]), kv[0]))[:4]

    achievements = int(db.scalar(select(func.count(UserAchievement.id)).where(UserAchievement.user_id == user_id)) or 0)

    goal_text = player.goal or "football development"
    question = f"{goal_text} {player.position} {player.archetype}".strip()
    packets = _load_chapter_packets(db, question, locale=state.locale, top_k=3)

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
        "form": round(float(player.form), 3),
        "sessions_28d": len(sessions),
        "completed_28d": len(completed),
        "planned_pending_28d": len(planned),
        "xp_28d": int(xp_28d),
        "top_categories_28d": dict(top_categories),
        "attribute_deltas_28d": dict(top_deltas),
        "achievements_total": int(achievements),
        "available_minutes_per_session": [15, 30, 45, 60],
    }
    state.chapter_packets = packets
    state.context_bytes = sum(int(pkt["bytes"]) for pkt in state.chapter_packets)
    state.timings_ms["gather"] = int((time.perf_counter() - started) * 1000)
    logger.info(
        "season_brief.gather sessions=%d completed=%d packets=%d bytes=%d",
        len(sessions),
        len(completed),
        len(packets),
        state.context_bytes,
    )
    return state


def _prompt_payload(state: SeasonBriefState) -> str:
    return json.dumps(
        {
            "intent": "season_brief",
            "snapshot": state.snapshot,
            "whitelist": list(CATEGORIES),
            "chapters": [
                {"ref": pkt["ref"], "title": pkt["title"], "body": pkt["body"]}
                for pkt in state.chapter_packets
            ],
        },
        ensure_ascii=False,
    )


def _node_draft(state: SeasonBriefState, db: Session) -> SeasonBriefState:
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
            max_tokens=900,
            temperature=0.3,
            prompt_cache_key="trainings.season_brief.draft",
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
    record_model_call_safely(result=result, feature="trainings.season_brief.draft")
    state.provider = result.provider
    state.model = result.model
    state.demo_mode = bool(result.demo_mode)
    state.input_tokens += result.input_tokens or 0
    state.output_tokens += result.output_tokens or 0
    state.cached_input_tokens += result.cached_input_tokens or 0
    state.cache_reported = state.cache_reported or bool(result.cache_reported)
    if result.error:
        state.available = False
        return state
    state.draft = (result.text or "").strip()
    state.payload = _parse_json_object(state.draft) or {}
    return state


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
        # Tolerate one enclosing pair of prose around the object rather than reroute to repair
        # for a wrapper the model adds despite the contract.
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _node_verify(state: SeasonBriefState, db: Session) -> SeasonBriefState:  # noqa: ARG001
    if not state.available:
        return state
    failures = _contract_failures(state.payload, state.snapshot)
    state.verify_failures = failures
    state.verify_ok = not failures
    logger.info("season_brief.verify ok=%s failures=%s", state.verify_ok, failures)
    return state


def _contract_failures(payload: dict[str, Any], snapshot: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    headline = payload.get("headline")
    if not isinstance(headline, str) or not headline.strip():
        failures.append("headline missing or empty")
    elif len(headline) > 200:
        failures.append(f"headline too long ({len(headline)} chars)")

    themes = payload.get("themes")
    if not isinstance(themes, list) or len(themes) != 3:
        failures.append("themes must be exactly three strings")
    else:
        whitelist = set(CATEGORIES)
        cleaned_themes = [str(t).lower().strip() for t in themes]
        if len(set(cleaned_themes)) != 3:
            failures.append("themes must be distinct")
        else:
            outside = [t for t in cleaned_themes if t not in whitelist]
            if outside:
                failures.append(f"themes outside the catalogue whitelist: {outside}")

    arc = payload.get("arc")
    themes_lower = _themes_lower(themes)
    if not isinstance(arc, list) or len(arc) != ALLOWED_DAYS:
        failures.append(f"arc must have exactly {ALLOWED_DAYS} day-objects")
    else:
        for index, entry in enumerate(arc):
            if not isinstance(entry, dict):
                failures.append(f"arc[{index}] is not an object")
                continue
            day = entry.get("day")
            minutes = entry.get("minutes")
            blocks = entry.get("blocks")
            focus = entry.get("focus")
            if day != index + 1:
                failures.append(f"arc[{index}].day must be {index + 1}")
            if not isinstance(minutes, int | float) or isinstance(minutes, bool) or not (MINUTES_MIN <= int(minutes) <= MINUTES_MAX):
                failures.append(f"arc[{index}].minutes must be in {MINUTES_MIN}..{MINUTES_MAX}")
            if not isinstance(focus, str) or not focus.strip():
                failures.append(f"arc[{index}].focus missing")
            elif themes_lower and focus.lower().strip() not in themes_lower:
                failures.append(f"arc[{index}].focus must be one of the three themes")
            if not isinstance(blocks, list) or len(blocks) < ALLOWED_BLOCKS_MIN:
                failures.append(f"arc[{index}].blocks must name at least {ALLOWED_BLOCKS_MIN} actions")
            elif any(not isinstance(b, str) or not str(b).strip() for b in blocks):
                failures.append(f"arc[{index}].blocks contains an empty action")

    one_more = payload.get("one_more")
    if not isinstance(one_more, str) or not one_more.strip():
        failures.append("one_more missing")
    elif len(one_more) > 160:
        failures.append(f"one_more too long ({len(one_more)} chars)")

    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 3:
        failures.append("evidence must name at least three traceable references")
    elif any(not isinstance(item, str) or not item.strip() for item in evidence):
        failures.append("evidence contains an empty reference")

    echo = payload.get("echo")
    if not isinstance(echo, str) or not echo.strip():
        failures.append("echo missing — the brief never named the athlete it reads")
    else:
        haystack = json.dumps(snapshot, ensure_ascii=False).lower()
        if echo.lower().strip() not in haystack:
            failures.append(f"echo {echo!r} does not appear in the athlete's own snapshot")

    return failures


def _themes_lower(themes: Any) -> set[str]:
    if not isinstance(themes, list):
        return set()
    return {str(item).lower().strip() for item in themes}


def _node_repair(state: SeasonBriefState, db: Session) -> SeasonBriefState:
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
                    "intent": "season_brief_repair",
                    "failure": state.verify_failures,
                    "draft": state.draft,
                    "snapshot": state.snapshot,
                    "whitelist": list(CATEGORIES),
                    "chapters": [
                        {"ref": pkt["ref"], "title": pkt["title"], "body": pkt["body"][:6000]}
                        for pkt in state.chapter_packets
                    ],
                },
                ensure_ascii=False,
            ),
            max_tokens=900,
            temperature=0.2,
            prompt_cache_key="trainings.season_brief.repair",
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
    record_model_call_safely(result=result, feature="trainings.season_brief.repair")
    state.input_tokens += result.input_tokens or 0
    state.output_tokens += result.output_tokens or 0
    state.cached_input_tokens += result.cached_input_tokens or 0
    state.cache_reported = state.cache_reported or bool(result.cache_reported)
    if result.error and not (result.text or "").strip():
        return state
    state.payload = _parse_json_object((result.text or "").strip()) or {}
    state.draft = (result.text or "").strip()
    failures = _contract_failures(state.payload, state.snapshot)
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
    """Build the StateGraph for one run — the four doors, in one chain."""
    if _StateGraph is None:
        return None

    def _wrap(name: str, fn: Any) -> Any:
        def node(state: SeasonBriefState) -> SeasonBriefState:
            state.graph_trace.append(name)
            return fn(state)

        node.__name__ = name
        return node

    builder = _StateGraph(SeasonBriefState)
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


def _walk_graph(db: Session, state: SeasonBriefState, user_id: str) -> SeasonBriefState:
    graph = _compile_langgraph(db, user_id)
    if graph is None:
        return _walk_legacy(db, state, user_id=user_id)
    out = graph.invoke(state)
    if isinstance(out, dict):
        state = SeasonBriefState(**out)
    if "START" not in state.graph_trace:
        state.graph_trace = ["START", *state.graph_trace]
    if "END" not in state.graph_trace:
        state.graph_trace = [*state.graph_trace, "END"]
    return state


def _walk_legacy(db: Session, state: SeasonBriefState, *, user_id: str) -> SeasonBriefState:
    """The bounded hand-rolled walk — the fallback for environments without langgraph."""
    nodes: list[tuple[str, Any]] = [
        ("gather", lambda: _node_gather(state, db, user_id=user_id)),
        ("draft", lambda: _node_draft(state, db)),
        ("verify", lambda: _node_verify(state, db)),
        ("repair", lambda: _node_repair(state, db)),
    ]
    state.graph_trace.append("START")
    for name, node in nodes:
        if len(state.graph_trace) >= 9:
            state.available = False
            state.error = "graph exceeded 8 node visits"
            break
        state.graph_trace.append(name)
        state = node()
    state.graph_trace.append("END")
    return state


def compute_season_brief(db: Session, *, user_id: str, locale: str = "en") -> dict[str, Any]:
    state = SeasonBriefState(locale=locale if locale else "en")
    started = time.perf_counter()
    state = _walk_graph(db, state, user_id)

    verify = {"ok": state.verify_ok, "repair_passes": state.repair_passes, "failures": state.verify_failures}
    elapsed = int((time.perf_counter() - started) * 1000)

    if not state.available or not state.verify_ok:
        payload: dict[str, Any] = {
            "answered": False,
            "headline": None,
            "themes": [],
            "arc": [],
            "one_more": None,
            "evidence": [],
            "graph_trace": state.graph_trace,
            "verify": verify,
            "provider": state.provider,
            "model": state.model,
            "demo_mode": state.demo_mode,
            "error": state.error or "the draft refused the contract — treat every byte as unverified",
        }
        _persist(db, user_id=user_id, state=state, payload=payload, headline="", answered=False)
        _record_timings(state, elapsed)
        return payload

    headline = str(state.payload.get("headline", "")).strip()
    arc = state.payload.get("arc") or []
    themes = [str(t).lower().strip() for t in (state.payload.get("themes") or [])]
    payload = {
        "answered": True,
        "headline": headline,
        "themes": themes,
        "arc": arc,
        "one_more": str(state.payload.get("one_more", "")).strip(),
        "evidence": [str(item).strip() for item in (state.payload.get("evidence") or [])][:6],
        "chapters_used": [
            {"ref": pkt["ref"], "slug": pkt["slug"], "title": pkt["title"], "score": pkt["score"]}
            for pkt in state.chapter_packets
        ],
        "graph_trace": state.graph_trace,
        "verify": verify,
        "provider": state.provider,
        "model": state.model,
        "demo_mode": state.demo_mode,
        "player_id": state.player_id,
        "snapshot_sessions_28d": (state.snapshot or {}).get("sessions_28d"),
    }
    _persist(db, user_id=user_id, state=state, payload=payload, headline=headline, answered=True)
    _record_timings(state, elapsed)
    return payload


def _persist(db: Session, *, user_id: str, state: SeasonBriefState, payload: dict[str, Any], headline: str, answered: bool) -> None:
    try:
        db.add(
            CoachMessage(
                id=new_public_id("msg"),
                user_id=user_id,
                player_id=state.player_id or None,
                role="coach",
                kind="season_brief",
                content=headline or (state.error or "the brief refused the contract"),
                structured={
                    "answered": answered,
                    "verify": {"ok": state.verify_ok, "repair_passes": state.repair_passes, "failures": state.verify_failures},
                    "provider": state.provider,
                    "model": state.model,
                    "payload": payload,
                },
                reasons=[
                    "the brief is the model's reading of the athlete's 28-day fingerprint, not a template",
                    f"verify: {'all contract rules hold' if state.verify_ok else 'refused at the gate'}",
                    f"chapters loaded: {[pkt['slug'] for pkt in state.chapter_packets]}",
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
        logger.exception("season_brief.persist_failed")


def _record_timings(state: SeasonBriefState, elapsed: int) -> None:
    state.timings_ms["total"] = elapsed
    logger.info(
        "season_brief.done total_ms=%d cached=%s", elapsed, state.cached_input_tokens
    )
