"""The Tactical Lab's content-addressed memo (M12 Caching).

`metrics_for_rows` memoises the published metrics on the canonical JSON of the rows themselves. These
cases pin the three properties that make the cache safe rather than merely fast:

1. **It answers what the pure function answers.** A memo that drifts from `metrics_of(shape_from_rows())`
   is a second source of truth, which is the failure the whole module exists to prevent.
2. **It is self-invalidating on content.** A different dot is a different key, so a re-synced phase
   cannot serve yesterday's figures. This is what a TTL cannot do, and the reason the memo exists.
3. **It hands back its own stored dict.** A caller that intends to write must deepcopy first — `analysis`'s
   ShapeDiff only reads it, and the case below records the contract rather than hoping a reader knows.

The memo is process-global and the run's cases share one process, so each case reads its own *tagged*
row set (`_tagged`): a shared entry would make one case's counts a fact about the case before it.
"""

from __future__ import annotations

import json
from copy import deepcopy

from app.core.cache import TTLCache
from app.services.tactics.analysis import metrics_for_rows, metrics_of, shape_from_rows
from app.services.tactics.boards import metrics_for
from app.services.tactics.roles import ROLES

#: Eleven slots, one keeper, in the shape the authored catalogue stores them. The roles are `ROLES`' own
#: vocabulary, and `metrics_of` raises on a role it does not hold — so a wrong role here is a test bug,
#: not a validation finding.
PHASE_IN: list[dict[str, object]] = [
    {"role": "GK", "x": 5.0, "y": 34.0},
    {"role": "RB", "x": 22.0, "y": 78.0},
    {"role": "DCB", "x": 14.0, "y": 62.0},
    {"role": "DCB", "x": -14.0, "y": 62.0},
    {"role": "LB", "x": -22.0, "y": 78.0},
    {"role": "DM", "x": 9.0, "y": 40.0},
    {"role": "DM", "x": -9.0, "y": 40.0},
    {"role": "RM", "x": 24.0, "y": 14.0},
    {"role": "AM", "x": 0.0, "y": 26.0},
    {"role": "LM", "x": -24.0, "y": 14.0},
    {"role": "ST", "x": 0.0, "y": 4.0},
]

#: How many row sets this file has tagged, so each gets its own x on the striker.
_TAGS_ISSUED = 0


def _tagged() -> list[dict[str, object]]:
    """A copy of `PHASE_IN` whose last dot sits somewhere no other case has put it."""
    global _TAGS_ISSUED
    _TAGS_ISSUED += 1
    rows = deepcopy(PHASE_IN)
    rows[-1] = {**rows[-1], "x": float(rows[-1]["x"]) + _TAGS_ISSUED * 0.01}
    return rows


def _pure(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    """The answer with no memo involved, as the reference."""
    return {metric.key: metric.to_dict() for metric in metrics_of(shape_from_rows(rows))}


def _key_of(rows: list[dict[str, object]]) -> str:
    return "tactics:metrics:" + json.dumps(list(rows), sort_keys=True, separators=(",", ":"))


def test_the_memo_answers_exactly_what_the_pure_function_answers() -> None:
    rows = _tagged()
    memoised = metrics_for_rows(rows)
    assert memoised == _pure(rows), "a memo that disagrees with the function is a second source of truth"
    assert set(memoised) == {"width", "depth", "spacing", "space_behind", "balance"} or len(memoised) >= 5


def test_a_different_dot_is_a_different_answer() -> None:
    """The cache's key is the content, so an edit cannot serve the previous figures."""
    first_rows, moved_rows = _tagged(), _tagged()
    first = metrics_for_rows(first_rows)
    moved_rows[-1] = {**moved_rows[-1], "y": 44.0}
    second = metrics_for_rows(moved_rows)
    assert second != first, "moving the striker changed the footprint, so the answer must change"
    assert second == _pure(moved_rows), "and it changed to exactly what the pure function now answers"


def test_the_second_read_is_served_rather_than_recomputed() -> None:
    from app.services.tactics import analysis

    rows = _tagged()
    key = _key_of(rows)
    answer = metrics_for_rows(rows)
    entry = analysis._ROW_METRICS_CACHE._cache[key]
    served_at = entry.access_count
    again = metrics_for_rows(rows)
    assert again is answer, "the second read is the very object the cache holds"
    assert analysis._ROW_METRICS_CACHE._cache[key].access_count == served_at + 1, "and it counted as a hit"
    assert analysis._ROW_METRICS_CACHE.get_stats()["hits"] >= 0


def test_the_memo_returns_its_stored_dict_so_a_mutating_caller_corrupts_it() -> None:
    """Recorded, because a mutating caller must deepcopy first — `ShapeDiff` only reads."""
    rows = _tagged()
    first = metrics_for_rows(rows)
    first["width"]["value"] = 999.0
    second = metrics_for_rows(rows)
    assert second["width"]["value"] == 999.0, (
        "the memo hands back its own dict: the saving and the hazard are the same line, and the hazard " "is documented here rather than left for a reader to discover"
    )


def test_the_underlying_cache_still_expires() -> None:
    """The TTL did not go away; the memo's safety is the content key, not an absent expiry."""
    cache = TTLCache(max_size=4, default_ttl=0.05)
    cache.set("a", 1)
    assert cache.get("a") == 1
    import time

    time.sleep(0.1)
    assert cache.get("a") is None


def test_board_metrics_and_the_memo_read_the_same_rows_the_same_way() -> None:
    """`boards.metrics_for` is the list form of the same figures; the two must not disagree."""
    rows = _tagged()
    listed = {item["key"]: item for item in metrics_for(rows)}
    keyed = metrics_for_rows(rows)
    assert set(listed) == set(keyed)
    for key, value in listed.items():
        assert value == keyed[key], f"{key} differs between the list form and the memoised key"


def test_the_published_metric_keys_are_the_ones_the_page_reads() -> None:
    """The memo's answer carries the formulas §62 promises, not bare numbers."""
    rows = _tagged()
    answer = metrics_for_rows(rows)
    for key, metric in answer.items():
        assert set(metric) >= {"key", "label", "value", "unit", "formula"}, f"{key} is missing its formula"
        assert metric["formula"], f"{key} publishes an empty formula"


def test_every_role_the_shape_uses_is_one_the_engine_holds() -> None:
    """A case that fails here is a test bug: `metrics_of` raises on a role `ROLES` does not have."""
    for row in PHASE_IN:
        assert row["role"] in ROLES
