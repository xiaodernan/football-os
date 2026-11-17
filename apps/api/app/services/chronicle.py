"""The Chronicle — a state graph that hands the season's chapter to the voice.

Four walks, compiled in order, recursion-bounded, with the trace always on:

    START -> gather -> draft -> revise -> END

* ``gather`` is deterministic: it assembles the constitution from the world's own
  services (the gazette's edition, the full tier-1 table, the champions' 22-cup
  ledger, the streak ledger and the records door's eight keys). No model. The
  gathered bytes are the only knowledge the chapter is allowed to draw on.
* ``draft`` asks the provider for the chapter the season has earned to date.
* ``revise`` hands the draft back to the provider with the constitution in the
  same prompt and asks for one pass of tightening — every claim that survives
  printing the constitution is kept; every claim that does not is struck or
  rewritten. A failed revise keeps the draft and says so (``revision:
  "revise-failed"``), never hides a red pass.

No figure appears in the answer that did not come through ``gather``. No future
fixture, result or standings claim about a matchday that has not been played is
permitted — the constitution prints a finished matchday and nothing beyond it.

Feature names for the ledger: ``world.chronicle.draft`` and
``world.chronicle.revise``. Each press that reaches the gateway is written to the
model ledger under those names, with the gateway's own ``cache_reported`` flag
quoted verbatim or absent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.providers import LlmResult, get_llm_provider
from app.services.model_ledger import budget_exhausted, record_model_call_safely
from app.services.world.champions import compute_champions
from app.services.world.dynasties import compute_dynasties
from app.services.world.gazette import compute_gazette
from app.services.world.records import compute_records

logger = logging.getLogger("football_os.chronicle")

MAX_NODE_VISITS = 8

_SYSTEM_DRAFT = """\
You are the chronicler of one synthetic football world — the season's paper of
record, writing the chapter the league has earned to date. You see only THE
PRINTING, assembled from the world's own services: the current edition, the full
tier-1 table after the latest completed matchday, the champions' 22-cup ledger,
the streak ledger and the records keys. You know nothing else about this league.

Your task:

1. Write the opening chapter of this world — five to seven paragraphs, plain
   English, present tense. It covers: the shape of the table after the latest
   matchday, who is setting the pace and who is bleeding; the golden boot the
   seed has handed to the ledger; the cups that history here has already
   settled (only the ones THE PRINTING shows); and what the streak ledger says.
2. Name every club, player and figure exactly as THE PRINTING prints them. No
   invented clubs, players, venues, fixtures, scores, dates or figures. If it is
   not in THE PRINTING, it does not exist for this chapter.
3. The finished matchday is the edge of the world. Write nothing about any
   fixture, result or table claim for an unplayed matchday. You may say the
   season continues; you may not say who wins it.
4. No headings, no bullets, no emoji. Smooth prose, specific and dry — the
   tone of a season yearbook, not a press release.
"""

_PROMPT_DRAFT = """\
THE PRINTING — season 2026/27, edition {edition} of {total_editions}
({competition_name}, tier-1). Published {published_at}.

The edition's numbers: goals this round {goals_this_round} · draws {draws} · clean
sheets {clean_sheets} · season average goals per edition {season_average} · fixtures
played {fixture_count}.

The full table after matchday {edition}, in order:
{table_block}

The loudest fixture of the round: {loudest_fixture}
The hot hand: {hot_hand}

The cup history (2010-2022, openfootball, as The Champions door prints it):
{champions_block}
The merged scorers across 2014/2018/2022:
{merged_scorers_block}

The streak ledger (five longest win runs, five longest unbeaten runs):
{dynasties_block}

The records keys (one line each, the eight keys the records door prints):
{records_block}

Write the chapter the season has earned to date.
"""

_SYSTEM_REVISE = """\
You are the same world's copy desk. You are handed THE PRINTING and one draft
chapter. Your task is tightening, not authoring:

1. Strike every sentence that asserts a club, player, figure, fixture, score or
   date not present in THE PRINTING. Replace it with what THE PRINTING supports
   — or remove it.
2. Keep the five-to-seven paragraph shape. Keep the present tense. Keep every
   surviving claim's club name, player name and figures exactly as THE
   PRINTING prints them.
3. If the draft invents an unplayed matchday fixture, result or table claim,
   delete it outright.
4. Plain English, no headings, no bullets, no emoji. Return the revised
   chapter in full and nothing else.
"""

_PROMPT_REVISE = """\
THE PRINTING:
{constitution_block}

THE DRAFT CHAPTER:
{draft}

Return the revised chapter in full and nothing else.
"""


@dataclass
class ChronicleState:
    constitution: str = ""
    draft: str = ""
    answer: str = ""
    revision: str = "not-run"
    available: bool = False
    provider: str = "unknown"
    model: str = "unknown"
    demo_mode: bool = True
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cache_reported: bool = False
    latency_ms: float = 0.0
    graph_trace: list[str] = field(default_factory=list)
    edition: str = "2026/27"
    total_editions: int | None = None


def _table_block(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "  (table unavailable)"
    lines: list[str] = []
    for row in rows:
        team = (row.get("team") or {}).get("name", "?")
        lines.append(
            f"  {row.get('position'):>2}. {team} · P {row.get('played')} · "
            f"{row.get('won')}-{row.get('drawn')}-{row.get('lost')} · "
            f"GF {row.get('goals_for')} GA {row.get('goals_against')} · "
            f"GD {row.get('goal_difference', 0)} · {row.get('points')} pts"
        )
    return "\n".join(lines)


def _champions_block(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "  (cup ledger unavailable)"
    lines: list[str] = []
    for entry in entries:
        champion = entry.get("champion") or {}
        runner_up = entry.get("runner_up") or {}
        final = entry.get("final") or {}
        regular = final.get("score_regular") or [None, None]
        et_flag = " (a.e.t.)" if entry.get("has_penalties") and final.get("score_penalties") != [0, 0] else ""
        lines.append(
            f"  {entry.get('tournament')} — {champion.get('name', '?')} def. {runner_up.get('name', '?')} "
            f"{regular[0]}–{regular[1]}{et_flag} · {entry.get('goals_scored', '?')} goals · "
            f"{entry.get('goals_per_match', '?')}/match · host {entry.get('host', '?')}"
        )
    return "\n".join(lines)


def _merged_scorers_block(merged: list[dict[str, Any]]) -> str:
    if not merged:
        return "  (scorers ledger unavailable)"
    lines = [f"  {row.get('name')} — {row.get('goals_2014')}/{row.get('goals_2018')}/{row.get('goals_2022')} · total {row.get('total')}" for row in merged[:6]]
    return "\n".join(lines) if lines else "  (scorers ledger unavailable)"


def _fixture_block(row: dict[str, Any] | None) -> str:
    if not row:
        return "(none)"
    home = (row.get("home") or {}).get("name", "?")
    away = (row.get("away") or {}).get("name", "?")
    return f"{home} {row.get('home_goals', '?')}–{row.get('away_goals', '?')} {away} · {row.get('venue', '?')}"


def _hot_hand_block(row: dict[str, Any] | None) -> str:
    if not row:
        return "(nobody scored)"
    team = (row.get("team") or {}).get("name", "?")
    return f"{team} · {row.get('goals', 0)} goal(s) this round"


def _dynasties_block(dynasty: dict[str, Any]) -> str:
    if not dynasty.get("available"):
        return "  (streak ledger unavailable)"
    lines: list[str] = []
    for run in (dynasty.get("win_streaks") or [])[:5]:
        team = (run.get("team") or {}).get("name", "?")
        lines.append(f"  win · {team} · {run.get('length')} in a row · MD {run.get('start_round')}–{run.get('end_round')}")
    for run in (dynasty.get("unbeaten_runs") or [])[:5]:
        team = (run.get("team") or {}).get("name", "?")
        lines.append(f"  unbeaten · {team} · {run.get('length')} in a row · MD {run.get('start_round')}–{run.get('end_round')}")
    ablaze = dynasty.get("ablaze") or {}
    ablaze_team = (ablaze.get("team") or {}).get("name", "?")
    lines.append(f"  ablaze · {ablaze_team} · {ablaze.get('current_win_run', 0)} wins from {ablaze.get('matches', '?')} played")
    return "\n".join(lines)


_SCALAR_KEYS = ("goals", "assists", "rating", "saves", "clean_sheets", "played", "minutes", "goal_difference", "points")


def _records_block(records: list[dict[str, Any]]) -> str:
    if not records:
        return "  (records ledger unavailable)"
    lines: list[str] = []
    for row in records:
        key = row.get("key", "?")
        if not row.get("available"):
            lines.append(f"  {key} — unavailable")
            continue
        holder = row.get("player") or row.get("team") or row.get("match") or {}
        name = holder.get("name") if isinstance(holder, dict) else str(holder)
        figure = next((f"{k}={row[k]}" for k in _SCALAR_KEYS if isinstance(row.get(k), int | float) and row.get(k)), "")
        lines.append(f"  {key} — {name or '?'}{(' · ' + figure) if figure else ''}")
    return "\n".join(lines)


def _node_gather(state: ChronicleState, db: Session) -> ChronicleState:
    edition = compute_gazette(db)
    if not edition.get("available"):
        state.available = False
        state.error = "the gazette could not be computed — the chapter has no printed matchday"
        return state

    champions = compute_champions() if callable(compute_champions) else {"available": False}
    champion_entries = champions.get("entries", []) if champions.get("available", False) else []
    merged = champions.get("merged_scorers", []) if champions.get("available", False) else []

    dynasty = compute_dynasties(db)
    records_payload = compute_records(db)
    records = records_payload.get("records", []) if isinstance(records_payload, dict) else []

    number = edition.get("number") or {}
    goals_this_round = number.get("goals_this_round")
    draws = number.get("draws")
    clean_sheets = number.get("clean_sheets")
    season_average = number.get("season_average_goals")
    fixture_count = number.get("fixtures")

    table_after = edition.get("table_after") or []
    constitution = _PROMPT_DRAFT.format(
        edition=edition.get("edition", "?"),
        total_editions=edition.get("total_editions", "?"),
        competition_name=(edition.get("competition") or {}).get("name", "?"),
        published_at=edition.get("published_at", "?"),
        goals_this_round=goals_this_round,
        draws=draws,
        clean_sheets=clean_sheets,
        season_average=season_average,
        fixture_count=fixture_count,
        table_block=_table_block(table_after),
        loudest_fixture=_fixture_block(edition.get("lead")),
        hot_hand=_hot_hand_block(edition.get("hot_hand")),
        champions_block=_champions_block(champion_entries),
        merged_scorers_block=_merged_scorers_block(merged),
        dynasties_block=_dynasties_block(dynasty),
        records_block=_records_block(records),
    )

    state.constitution = constitution
    state.edition = str(edition.get("season", {}).get("label", "2026/27"))
    state.total_editions = edition.get("total_editions")
    state.available = True
    return state


def _node_draft(state: ChronicleState, db: Session) -> ChronicleState:
    if not state.available:
        return state
    if budget_exhausted(db):
        state.provider = "rule-engine-demo"
        state.model = "rule-engine-demo"
        state.revision = "skipped:budget"
        state.answer = _demo_chapter(state)
        return state

    provider = get_llm_provider()
    try:
        result = provider.complete(
            system=_SYSTEM_DRAFT,
            prompt=state.constitution,
            max_tokens=1100,
            temperature=0.55,
            prompt_cache_key="world.chronicle.draft",
        )
    except Exception as error:  # noqa: BLE001 — the provider gateway itself is the risk; the door must stay up.
        failure = LlmResult(text="", provider=getattr(provider, "name", "unknown"), model="unreachable", demo_mode=True, error=str(error)[:300], latency_ms=0)
        record_model_call_safely(result=failure, feature="world.chronicle.draft")
        state.available = False
        state.provider = failure.provider
        state.model = failure.model
        state.latency_ms = 0.0
        state.error = (failure.error or "unreachable gateway")[:160]
        state.revision = "revise-skipped:draft-failed"
        return state

    record_model_call_safely(result=result, feature="world.chronicle.draft")
    state.input_tokens += result.input_tokens or 0
    state.output_tokens += result.output_tokens or 0
    state.cached_input_tokens += result.cached_input_tokens or 0
    state.cache_reported = state.cache_reported or bool(result.cache_reported)
    state.latency_ms += result.latency_ms or 0.0
    state.provider = result.provider
    state.model = result.model
    state.demo_mode = bool(result.demo_mode)

    if result.error:
        state.available = False
        state.error = (result.error or "provider error")[:160]
        state.revision = "revise-skipped:draft-failed"
        return state

    state.draft = result.text or ""
    state.answer = state.draft
    return state


def _node_revise(state: ChronicleState, db: Session) -> ChronicleState:
    if not state.available or budget_exhausted(db) or not state.draft:
        if state.revision == "not-run":
            state.revision = "revise-skipped"
        return state

    provider = get_llm_provider()
    prompt = _PROMPT_REVISE.format(
        constitution_block=state.constitution,
        draft=state.draft,
    )
    try:
        result = provider.complete(
            system=_SYSTEM_REVISE,
            prompt=prompt,
            max_tokens=1000,
            temperature=0.2,
            prompt_cache_key="world.chronicle.revise",
        )
    except Exception as error:  # noqa: BLE001
        failure = LlmResult(text="", provider=getattr(provider, "name", "unknown"), model="unreachable", demo_mode=True, error=str(error)[:300], latency_ms=0)
        record_model_call_safely(result=failure, feature="world.chronicle.revise")
        state.revision = "revise-failed"
        return state

    record_model_call_safely(result=result, feature="world.chronicle.revise")
    state.input_tokens += result.input_tokens or 0
    state.output_tokens += result.output_tokens or 0
    state.cached_input_tokens += result.cached_input_tokens or 0
    state.cache_reported = state.cache_reported or bool(result.cache_reported)
    state.latency_ms += result.latency_ms or 0.0

    if result.error or not (result.text or "").strip():
        state.revision = "revise-failed"
        return state

    state.answer = result.text.strip()
    state.revision = "applied"
    return state


def compile_chain() -> list[tuple[str, Any]]:
    """The compiled edge table — one ordered list, walked in order."""
    return [
        ("gather", _node_gather),
        ("draft", _node_draft),
        ("revise", _node_revise),
        ("END", None),
    ]


def _demo_chapter(state: ChronicleState) -> str:  # noqa: ARG001 — the signature matches the graph nodes' shape.
    lines = [
        "The matchday ledger is written, the table is settled for now, and the "
        "chapter waits for a voice this turn does not have.",
        "",
        "What is printed stands: the table after the latest completed matchday, the cup "
        "ledger of the 22 editions, the streak ledger the season has drawn. What is not "
        "printed is continued beyond this edition; nothing here outruns the world the seed "
        "draws.",
    ]
    return "\n".join(lines)


def compute_chronicle(db: Session) -> dict[str, Any]:
    state = ChronicleState()
    state.graph_trace.append("START")
    route = compile_chain()
    for node_name, node in route:
        if node is None:  # END
            state.graph_trace.append("END")
            break
        if len(state.graph_trace) >= MAX_NODE_VISITS + 1:
            state.available = False
            state.error = f"graph exceeded {MAX_NODE_VISITS} node visits"
            state.revision = "graph-cycle-refused"
            break
        state.graph_trace.append(node_name)
        state = node(state, db)

    payload: dict[str, Any] = {
        "edition": state.edition,
        "total_editions": state.total_editions,
        "graph_trace": state.graph_trace,
        "provider": state.provider,
        "model": state.model,
        "demo_mode": state.demo_mode or state.provider == "rule-engine-demo",
        "revision": state.revision,
        "input_tokens": state.input_tokens,
        "cached_input_tokens": state.cached_input_tokens,
        "cache_reported": state.cache_reported,
        "output_tokens": state.output_tokens,
        "latency_ms": round(state.latency_ms, 1),
        "constitution_chars": len(state.constitution),
    }
    if state.available:
        payload.update({"available": True, "answer": state.answer})
    else:
        payload.update({"available": False, "error": state.error or "the chronicle could not be composed"})
    return payload


__all__ = ["MAX_NODE_VISITS", "compute_chronicle", "compile_chain"]
