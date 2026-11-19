"""The library charter: the naming rail baked into the knowledge door's static prefix.

`SYSTEM_CHARTER = SYSTEM_PROMPT + LIBRARY_CHARTER`. The charter is the byte-stable index of every
document title and section heading the library holds — the household reference the gateway can cache
across every ask. These cases pin the bake so a silent re-serialization or a stale corpus reds loudly;
past any corpus change, `scripts/regen_library_charter.py` re-bakes and these pins move with it.
"""

from __future__ import annotations

from app.services.knowledge import answer
from app.services.knowledge.library_charter import LIBRARY_CHARTER

#: The byte count printed by the bake on 2026-11-19 (1255 index lines across 158 documents).
LIBRARY_CHARTER_BYTES = 51192

#: A floor below the bake figure — guards shrinkage, never growth.
LIBRARY_CHARTER_FLOOR_BYTES = 18000

#: Per-call request bytes may never bake into a contract cache the gateway serves to other readers.
REQUEST_BYTE_FRAGMENTS = (
    "seed=",
    "locale=",
    "json",
    "fixture:",
    "player_id",
    "http",
    "/api/v1",
    "x-admin-passphrase",
    "{",
)


def test_the_charter_is_the_measured_reference_bytes() -> None:
    assert len(LIBRARY_CHARTER.encode("utf-8")) == LIBRARY_CHARTER_BYTES, (
        "the charter changed length; re-bake with scripts/regen_library_charter.py and update "
        "LIBRARY_CHARTER_BYTES in this file in the same commit"
    )


def test_the_charter_clears_the_floor() -> None:
    assert len(LIBRARY_CHARTER.encode("utf-8")) >= LIBRARY_CHARTER_FLOOR_BYTES


def test_the_charter_carries_no_request_bytes() -> None:
    lowered = LIBRARY_CHARTER.lower()
    for fragment in REQUEST_BYTE_FRAGMENTS:
        assert fragment not in lowered, f"request fragment {fragment!r} leaked into the charter"


def test_the_composed_contract_is_the_charter_then_the_prompt() -> None:
    assert answer.SYSTEM_CHARTER.startswith(answer.LIBRARY_CHARTER)
    assert answer.SYSTEM_PROMPT in answer.SYSTEM_CHARTER
    # The charter is byte 0 of the composed contract across every door that bakes it, so
    # the gateway can serve the whole charter block from a shared cache entry per machine.
    assert answer.SYSTEM_CHARTER[: len(answer.LIBRARY_CHARTER)] == answer.LIBRARY_CHARTER


def test_the_charter_has_a_narrative_envelope() -> None:
    assert LIBRARY_CHARTER.startswith("\n\nTHE LIBRARY THE PASSAGES COME FROM")
    assert "naming rail" in LIBRARY_CHARTER
    assert "citations attach to the numbered passages" in LIBRARY_CHARTER
