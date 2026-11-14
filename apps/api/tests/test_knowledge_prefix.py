"""The house contract is byte-stable on purpose — pin it so a silent refactor reds the suite.

`SYSTEM_PROMPT` in `app.services.knowledge.answer` is the one piece of the knowledge_ask request
identical on every call. The gateway's automatic prefix cache only holds for identical leading
bytes, and on this project's gateway the report engages at a long identical prefix. The constant
is the contract, not cache bait: each clause is a rule the door needs. These cases pin the shape
without asserting a single sentence, so a deliberate rewording — re-measured or not — fails loudly
and on purpose.
"""

from __future__ import annotations

from app.services.knowledge import answer

#: The byte count of the constant at the last deliberate re-measure (2026-11-14 — probed live at
#: `wkapi.pro / gpt-6-sol`: warm repeat printed `cached_tokens = 4992` of 5171 prompt tokens).
#: If you edit the prefix, re-measure the reference bytes and update this pin with the figures — a
#: prefix cache is a byte-level contract; the test is the receipt.
SYSTEM_PROMPT_BYTES = 3645

#: A floor below the current figure — this guards against silent shrinkage, not against growth.
SYSTEM_PROMPT_FLOOR_BYTES = 3000


def test_the_system_prefix_is_the_measured_reference_bytes() -> None:
    assert len(answer.SYSTEM_PROMPT.encode("utf-8")) == SYSTEM_PROMPT_BYTES, (
        "the prefix changed length; re-measure with a live probe (see net/llm wire notes) and update "
        "SYSTEM_PROMPT_BYTES in this file in the same commit"
    )


def test_the_system_prefix_clears_the_cache_floor() -> None:
    assert len(answer.SYSTEM_PROMPT.encode("utf-8")) >= SYSTEM_PROMPT_FLOOR_BYTES


def test_the_system_prefix_carries_no_request_bytes() -> None:
    # The prefix never sees the request; a possessive leak would both bust the cache and bake one
    # reader's context into the house contract.
    lowered = answer.SYSTEM_PROMPT.lower()
    for fragment in ("seed", "locale", "slug", "json", "player:", "fixture", "-cache", "http"):
        assert fragment not in lowered, f"request fragment {fragment!r} leaked into the house contract"


def test_the_system_prefix_keeps_its_three_contracts() -> None:
    text = answer.SYSTEM_PROMPT
    assert "[1], [2]" in text, "the citation contract is gone — the Sources line is the caller's own reference rail"
    assert "Sources:" in text, "the references line contract is gone"
    assert "cannot support" in text, "the honesty floor is gone — the refusal doctrine would degrade silently"
    assert "Never invent" in text, "the invention ban is gone"
