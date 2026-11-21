"""The seeded demo cohort: realistic user behaviour, deterministic and labelled synthetic."""

from __future__ import annotations

import random
from collections import Counter

from app.services import behavior_seed as bs


def test_the_cohort_is_deterministic():
    a = bs._generate(random.Random(bs.SEED), 7)
    b = bs._generate(random.Random(bs.SEED), 7)
    assert a == b, "the same seed must replay the same cohort — the admin must not see churn"


def test_different_seeds_produce_different_worlds():
    a = bs._generate(random.Random(1), 7)
    b = bs._generate(random.Random(2), 7)
    assert a != b, "a different seed must re-roll the world"


def test_every_row_walks_a_real_product_path():
    rows = bs._generate(random.Random(bs.SEED), 14)
    known = {path for path, _ in bs.ENTRY_WEIGHTS}
    for target_list in bs.TRANSITIONS.values():
        known |= {path for path, _ in target_list}
    bad = [r[2] for r in rows if r[2] not in known]
    assert not bad, f"simulated users landed on non-product paths: {set(bad)}"


def test_bounce_means_leaving_before_six_seconds():
    rows = bs._generate(random.Random(bs.SEED), 14)
    # the beacon defines bounce as dwell < 6000 ms; a bounced row must satisfy it
    assert all(r[4] is False or r[3] < 6000 for r in rows)
    # and there must be both patient and impatient readers — otherwise the simulation is flat
    bounced = sum(1 for r in rows if r[4])
    assert 0 < bounced < len(rows), "the cohort must contain both bouncers and stayers"


def test_sessions_have_a_plausible_depth():
    rows = bs._generate(random.Random(bs.SEED), 14)
    by_ref: dict[str, list] = {}
    for ref, _, path, dwell, bounced in rows:
        by_ref.setdefault(ref, []).append((path, dwell, bounced))
    depths = Counter(len(v) for v in by_ref.values())
    # every session has 1..6 events (the generator's cap); most have more than one
    assert all(1 <= len(v) <= 6 for v in by_ref.values())
    assert sum(n for depth, n in depths.items() if depth > 1) > 0


def test_timestamps_increase_within_a_session():
    rows = bs._generate(random.Random(bs.SEED), 14)
    by_ref: dict[str, list] = {}
    for ref, stamp, _, _, _ in rows:
        by_ref.setdefault(ref, []).append(stamp)
    for stamps in by_ref.values():
        assert stamps == sorted(stamps), "a session's clicks must move forward in time"


def test_entry_weights_favour_the_front_door():
    rows = bs._generate(random.Random(bs.SEED), 30)
    entries: dict[str, int] = {}
    seen: set[str] = set()
    for ref, _, path, _, _ in rows:
        if ref not in seen:
            seen.add(ref)
            entries[path] = entries.get(path, 0) + 1
    assert entries.get("/", 0) > 0
    # the front door is the single most common entry in the weight table
    assert bs.ENTRY_WEIGHTS[0][0] == "/"
