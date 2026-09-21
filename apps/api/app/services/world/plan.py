"""The generated world as a pure value: rows keyed for idempotent upsert, hashed for diffing.

Nothing in this module touches a database. `Planned.natural_key` is the identity the sync layer
matches on (a slug for public entities, a composite for stat lines), and `content_hash` covers
every visible column but never a timestamp — so "did this row change?" is answerable without
wall-clock noise, exactly like `KnowledgeDocument.content_hash` works for the corpus.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Final

WORLD_ID_PREFIXES = {
    "competition": "wcmp",
    "team": "wtem",
    "player": "wply",
    "match": "wmat",
    "stat_line": "wslt",
    "article": "wnws",
    "article_link": "wlnk",
}

# Entity type → public URL prefix (spec §80). The web tier publishes exactly these routes, so
# the API hands out paths instead of letting each client reconstruct them.
SEO_ROUTES: Final[dict[str, str]] = {
    "player": "/player",
    "team": "/team",
    "competition": "/competition",
    "match": "/match",
    "article": "/news",
    "news": "/news",
}


def web_path(entity_type: str, slug: str) -> str:
    """The canonical public URL for one world entity (spec §80).

    Single segment per entity because that is the route table the web tier publishes, and the
    API hands it out so no client has to guess how to link a player or a fixture.
    """
    return f"{SEO_ROUTES.get(entity_type, f'/{entity_type}')}/{slug}"


def world_id(kind: str, natural_key: str) -> str:
    """A stable public id derived from the natural key — reproducible, unlike `new_public_id`."""
    prefix = WORLD_ID_PREFIXES[kind]
    digest = hashlib.blake2b(f"{kind}:{natural_key}".encode(), digest_size=9).hexdigest()
    return f"{prefix}_{digest}"


def content_hash(payload: dict[str, Any]) -> str:
    """Hash of the visible columns only; dict order and key order must not matter."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Planned:
    """One row the sync layer wants to exist, with everything needed to upsert it."""

    natural_key: str
    payload: dict[str, Any]
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            object.__setattr__(self, "content_hash", content_hash(self.payload))


@dataclass
class WorldPlan:
    """A complete world build. Field order here is also the parent-first insert order."""

    seed: int
    version: str
    competitions: list[Planned] = field(default_factory=list)
    teams: list[Planned] = field(default_factory=list)
    players: list[Planned] = field(default_factory=list)
    matches: list[Planned] = field(default_factory=list)
    stat_lines: list[Planned] = field(default_factory=list)
    articles: list[Planned] = field(default_factory=list)
    article_links: list[Planned] = field(default_factory=list)

    @property
    def collections(self) -> dict[str, list[Planned]]:
        """Field order is the parent-first insert order the sync layer walks."""
        return {
            "competitions": self.competitions,
            "teams": self.teams,
            "players": self.players,
            "matches": self.matches,
            "stat_lines": self.stat_lines,
            "articles": self.articles,
            "article_links": self.article_links,
        }

    def counts(self) -> dict[str, int]:
        return {name: len(rows) for name, rows in self.collections.items()}

    def keys(self) -> dict[str, list[str]]:
        return {name: [row.natural_key for row in rows] for name, rows in self.collections.items()}

    def total_goals(self) -> int:
        return sum(int(row.payload.get("home_goals") or 0) + int(row.payload.get("away_goals") or 0) for row in self.matches)

    def stat_total(self, column: str) -> int:
        return sum(int(row.payload.get(column) or 0) for row in self.stat_lines)

    def fingerprint(self) -> str:
        """One digest over keys + per-row hashes: equal fingerprints mean identical worlds."""
        parts: list[str] = [f"seed={self.seed}", f"version={self.version}"]
        for name, rows in sorted(self.collections.items()):
            joined = ",".join(f"{row.natural_key}#{row.content_hash[:12]}" for row in sorted(rows, key=_key_order))
            parts.append(f"{name}:{joined}")
        return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _key_order(row: Planned) -> str:
    return row.natural_key


def duplicate_keys(rows: Iterable[Planned]) -> list[str]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.natural_key] = counts.get(row.natural_key, 0) + 1
    return sorted(key for key, total in counts.items() if total > 1)


__all__ = ["Planned", "SEO_ROUTES", "WorldPlan", "content_hash", "duplicate_keys", "web_path", "world_id"]
