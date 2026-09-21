"""Football World (M3, spec §4-§7, §25, §56, §65): a seeded, synthetic world the app can browse.

Three layers, kept apart on purpose:

* `builder.plan_world()` — pure arithmetic and string assembly, no database, no wall clock.
  The same seed always yields the same rows, so a re-run is provably a no-op.
* `sync.sync_world()` — diffs that plan against the tables and upserts by natural key.
* `search.search_world()` — one typed, ranked result set across every entity, each row
  carrying the canonical web path the SEO layer links to (spec §80).

Provenance is structural, not a comment: `data_origin='synthetic'`, `is_demo_data=True` and a
content hash sit on every row, and `DATA_POLICY.md` §1 requires those flags on any surface that
renders them.
"""

from __future__ import annotations

from app.services.world.builder import WorldSizes, plan_world
from app.services.world.search import SearchHit, search_world, web_path
from app.services.world.sync import (
    WorldSyncReport,
    sync_world,
    world_counts,
    world_ready,
    world_tables_present,
)

__all__ = [
    "SearchHit",
    "WorldSizes",
    "WorldSyncReport",
    "plan_world",
    "search_world",
    "web_path",
    "sync_world",
    "world_counts",
    "world_ready",
    "world_tables_present",
]
