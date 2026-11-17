"""The Champions' coach-read — one honest paragraph on the three world-cup editions this product carries.

The Champions door prints the three World Cups the Real Book holds (2014 Brazil, 2018 Russia,
2022 Qatar) side by side from the committed openfootball snapshots (CC-BY 4.0), with the three
finals, the merged top scorers and the per-tournament arithmetic. The model receives exactly
those rows and speaks one short paragraph on the three champions. It never invents a nation,
scorer, final or figure beyond the committed snapshots; no claim is made beyond these three
tournaments.

Without a configured provider the door answers `available: false` and the champions stand alone on
the page.

Feature name for the ledger: `world.champions.read`.
"""

from __future__ import annotations

from typing import Any

from app.providers import LlmResult, get_llm_provider
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.model_ledger import record_model_call_safely
from app.services.world.champions import compute_champions

_SYSTEM = """\
You are the voice of The Champions — the 22 World Cups this product carries from the committed
openfootball snapshots (CC-BY 4.0). You see exactly the rows the door prints: every one of the
22 champions (year · champion def. runner-up · the final's score columns), the three most
recent detailed (date, venue, golden ball, biggest win), the merged scorers ledger across
2014/2018/2022, and the totals. You know nothing else about football. Your task:

1. Speak one short paragraph on the champions — the through-line (which nations repeat, who
   lifted twice and more), how the three most recent finals were decided, and which scorers
   carried the three most recent tournaments.
2. Name every nation, player, final, score and figure exactly as the rows print them. No
   inventing nations, finals, venues, scorers or figures beyond the committed snapshots. The
   score columns carry no home/away label; neither column is attributable to a side.
3. These 22 tournaments from the committed files are all you know; the paragraph makes no
   claim about any other tournament, and the count is a count.
4. Plain English, one paragraph, no headings, no bullets, no emoji.
"""

_PROMPT = """\
Season 2026/27 — what The Champions printed for the 22 World Cups this product carries (openfootball snapshots, CC-BY 4.0):

Tournaments: {entries_count} · Matches: {total_matches} · Goals on field: {total_goals}

Every champion (year · champion def. runner-up · final score (as the snapshot's own columns print, no side labelled)):
{all_finals_block}

The three most recent in detail:
2014 Brazil World Cup — champion {c2014_champion} def. {c2014_runner_up}
  Final at {c2014_venue} on {c2014_date}: {c2014_final} · {c2014_matches} matches · {c2014_goals} goals ({c2014_goals_per_match}/game)
  Golden ball: {c2014_golden_ball} · biggest win: {c2014_biggest_win}
2018 Russia World Cup — champion {c2018_champion} def. {c2018_runner_up}
  Final at {c2018_venue} on {c2018_date}: {c2018_final} · {c2018_matches} matches · {c2018_goals} goals ({c2018_goals_per_match}/game)
  Golden ball: {c2018_golden_ball} · biggest win: {c2018_biggest_win}
2022 Qatar World Cup — champion {c2022_champion} def. {c2022_runner_up}
  Final at {c2022_venue} on {c2022_date}: {c2022_final} · {c2022_matches} matches · {c2022_goals} goals ({c2022_goals_per_match}/game)
  Golden ball: {c2022_golden_ball} · biggest win: {c2022_biggest_win}

Merged top scorers across the three most recent cups (goals 2014 / 2018 / 2022 → total):
{merged_scorers_block}

{joint_note}

The reader wants one honest paragraph on the champions this door carries.
"""


def _final_block(entry: dict[str, Any]) -> str:
    final = entry.get("final") or {}
    score = final.get("score_regular", ["?", "?"])
    et = final.get("score_extra_time")
    pens = final.get("score_penalties")
    bits = [f"{score[0]}–{score[1]}"]
    if et:
        bits.append(f"aet {et[0]}–{et[1]}")
    if pens and any(p for p in pens):
        bits.append(f"pens {pens[0]}–{pens[1]}")
    return " · ".join(bits)


def _scorers_block(rows: list[dict[str, Any]] | None, limit: int = 8) -> str:
    if not rows:
        return "  (no scorer rows carried in the committed snapshots)"
    lines = []
    for row in rows[:limit]:
        lines.append(
            f"  {row.get('name', '?')} — {row.get('goals_2014', 0)} / {row.get('goals_2018', 0)} / {row.get('goals_2022', 0)} → {row.get('total', 0)}"
        )
    return "\n".join(lines)


def _golden_ball_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name", "?"))
    return str(value) if value else "?"


def _cup_fields(entry: dict[str, Any]) -> dict[str, str]:
    year = str(entry.get("tournament", ""))
    out = {
        f"c{year}_champion": str(entry.get("champion", "?")),
        f"c{year}_runner_up": str(entry.get("runner_up", "?")),
        f"c{year}_final": _final_block(entry),
        f"c{year}_matches": str(entry.get("total_matches", "?")),
        f"c{year}_goals": str(entry.get("goals_scored", "?")),
        f"c{year}_goals_per_match": str(entry.get("goals_per_match", "?")),
        f"c{year}_venue": str((entry.get("final") or {}).get("venue", "?")),
        f"c{year}_date": str((entry.get("final") or {}).get("matchday_date", "?")),
        f"c{year}_golden_ball": _golden_ball_name(entry.get("golden_ball")),
    }
    biggest = entry.get("biggest_win") or {}
    out[f"c{year}_biggest_win"] = str(biggest.get("match", "?"))
    return out


def _all_finals_block(entries: list[dict[str, Any]]) -> str:
    lines = []
    for entry in entries:
        year = entry.get("tournament", "?")
        champion = entry.get("champion", "?")
        runner_up = entry.get("runner_up", "?")
        final = entry.get("final") or {}
        score = final.get("score_regular", ["?", "?"])
        et = final.get("score_extra_time")
        pens = final.get("score_penalties")
        bits = [f"{score[0]}–{score[1]}"]
        if et:
            bits.append(f"aet {et[0]}–{et[1]}")
        if pens and any(p for p in pens):
            bits.append(f"pens {pens[0]}–{pens[1]}")
        lines.append(f"  {year} · {champion} def. {runner_up} · {' · '.join(bits)}")
    return "\n".join(lines)


def compute_champions_coach_read() -> dict[str, Any]:
    try:
        champions = compute_champions()
    except Exception as error:  # noqa: BLE001 — the door must answer, not 500
        record_model_call_safely(
            result=LlmResult(
                text="",
                provider="unknown",
                model="champions-coach-read",
                demo_mode=True,
                error=str(error)[:300],
                latency_ms=0,
            ),
            feature="world.champions.read",
        )
        return {"available": False, "edition": "2026/27", "provider": "unknown", "error": "champions recompute failed"}

    if not champions.get("available"):
        return {
            "available": False,
            "edition": "2026/27",
            "provider": "unknown",
            "error": champions.get("reason", "the champions could not be computed"),
        }

    entries = champions.get("entries", [])
    cup_fields: dict[str, str] = {}
    for entry in entries:
        cup_fields.update(_cup_fields(entry))
    total_matches = sum(int(entry.get("total_matches", 0) or 0) for entry in entries)
    total_goals = sum(int(entry.get("goals_scored", 0) or 0) for entry in entries)
    prompt = _PROMPT.format(
        merged_scorers_block=_scorers_block(champions.get("merged_scorers")),
        joint_note=champions.get("joint_top_scorers_note", ""),
        entries_count=len(entries),
        total_matches=total_matches,
        total_goals=total_goals,
        all_finals_block=_all_finals_block(entries),
        **cup_fields,
    )

    provider = get_llm_provider()
    try:
        result = provider.complete(system=LIBRARY_CHARTER + _SYSTEM, prompt=prompt, max_tokens=320, temperature=0.3, prompt_cache_key="world.champions.read")
    except Exception as error:  # noqa: BLE001
        failure = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        record_model_call_safely(result=failure, feature="world.champions.read")
        return {
            "available": False,
            "edition": "2026/27",
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="world.champions.read")
    if result.error:
        return {
            "available": False,
            "edition": "2026/27",
            "provider": result.provider,
            "model": result.model,
            "error": (result.error or "provider error")[:160],
        }
    return {
        "available": True,
        "edition": "2026/27",
        "provider": result.provider,
        "model": result.model,
        "demo_mode": result.demo_mode,
        "input_tokens": result.input_tokens,
        "cached_input_tokens": result.cached_input_tokens,
        "cache_reported": result.cache_reported,
        "output_tokens": result.output_tokens,
        "latency_ms": result.latency_ms,
        "answer": result.text,
    }


__all__ = ["compute_champions_coach_read"]
