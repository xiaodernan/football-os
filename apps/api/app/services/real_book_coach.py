"""The Real Book's coach-read — one honest press on one real World Cup, grounded in the book's own figures.

The Real Book computes everything: the fixtures, the scorers where the file printed them, the
widest margins, the Final. The coach receives the same arithmetic — the edition's name, its host,
the Final, the champion, the biggest win, the tally of goals and matches, the scorers count where
the file carries lists — and writes one short paragraph that a reader could take to heart. The
inaugural era and the interwar era are handled the same way: the coach speaks from whatever this
_edition_ carries, including knowing what the file carries and what it does not print.

Without a configured provider, the door answers `available: false` and the book's own arithmetic —
the Final, the ledger, the scorers or their honest absence — stands alone on the page.

Feature name for the ledger: `world.real_book.read`.
"""

from __future__ import annotations

from typing import Any

from app.providers import LlmResult, get_llm_provider
from app.services.model_ledger import record_model_call_safely
from app.services.verified_phrasing import phrase_verified_complete as _verified_complete
from app.services.world.real_book import compute_real_book

_SYSTEM = """\
You are the Real Book's voice on one real World Cup or European Championship. You see only this
computed snapshot of the edition — no club, player or result outside it, and never any figure you
were not handed. Your task:

1. Say one true and specific thing about this edition in a single short paragraph — anchored to a
   number you were handed; no inventions.
2. If the file carries scorer lists, you may name the top scorer; if it doesn't, do not produce a
   name.
3. Do not mix in modern context (e.g. do not discuss scripted goal averages, Twitter narratives or
   anything the reader has not asked for).
4. Plain English, one paragraph, no headings, no bullets, no emoji.
"""

_PROMPT = """\
Snapshot of this edition:
Edition: {edition}
Host: {host} · Final date: {final_date} · Final day ground was {venue}
The Final: {home} {score_regular[0]}–{score_regular[1]} {away} (full time){et_note}{pen_note}
Champion: {champion} — the note the book prints: "{champion_note}"
Runner-up: {runner_up}
Goals scored in the edition: {goals} across {matches} scored fixtures on {venues} venues.
Widest margin from the book: {biggest_win} ({stage}, {matchday_date}).
Scorers this edition carries from the file: {scorers_count} rows.

The reader just turned this page on {edition}. What does this edition own, in its own bytes?
"""

_UNSCORERED_ADDENDUM = "no scorer lists are printed for this edition — your answer must not name one."


def compute_real_book_coach_read(tournament: str = "2022") -> dict[str, Any]:
    book = compute_real_book(tournament)
    facts = book["facts"]
    final = facts["final"]
    biggest_win = facts["biggest_win"]
    scorers = book["scorers"]
    skip_scorers = bool(facts.get("skip_scorers")) or not scorers
    unplayed = facts.get("unplayed") or []
    edition_kind = facts.get("tournament", tournament)

    score_regular = final["score_regular"]
    et = facts.get("final", {}).get("score_extra_time")
    et_note = f" · after extra time {et[0]}–{et[1]}" if et and et != score_regular else ""
    pens = facts.get("final", {}).get("score_penalties")
    pen_note = f" · penalties {pens[0]}–{pens[1]}" if pens and (pens[0] or pens[1]) else ""

    prompt = _PROMPT.format(
        edition=edition_kind,
        host=facts.get("host", "—"),
        final_date=facts.get("final_date", "—"),
        score_regular=score_regular,
        home=final["home"],
        away=final["away"],
        venue=final["venue"],
        et_note=et_note,
        pen_note=pen_note,
        champion=facts["champion"]["name"],
        champion_note=facts["champion"]["note"],
        runner_up=facts["runner_up"]["name"],
        goals=facts.get("goals_scored", "—"),
        matches=facts.get("total_matches", "—"),
        venues=facts.get("venues", "—"),
        biggest_win=biggest_win["match"],
        stage=biggest_win["stage"],
        matchday_date=biggest_win["matchday_date"],
        scorers_count=len(scorers),
    )
    if skip_scorers:
        prompt += "\n" + _UNSCORERED_ADDENDUM
    if unplayed:
        prompt += f"\nOne committed fixture was {unplayed[0].get('status')}: {unplayed[0].get('team1')} v {unplayed[0].get('team2')} ({unplayed[0].get('date')}) — the book prints it as such; do not invent it as played."

    provider = get_llm_provider()
    try:
        result = _verified_complete(provider=provider, system=_SYSTEM, prompt=prompt, feature="world.real_book.read", max_tokens=360, temperature=0.3)
    except Exception as error:  # noqa: BLE001 — the provider is the risk; the door must stay up.
        failure = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        record_model_call_safely(result=failure, feature="world.real_book.read")
        return {
            "available": False,
            "edition": edition_kind,
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="world.real_book.read")
    if result.error:
        return {
            "available": False,
            "edition": edition_kind,
            "provider": result.provider,
            "model": result.model,
            "error": (result.error or "provider error")[:160],
        }
    return {
        "available": True,
        "edition": edition_kind,
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


__all__ = ["compute_real_book_coach_read"]
