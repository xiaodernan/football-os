"""Shared types for the knowledge graph projection (spec §30).

These types are used by both the projection logic (project.py) and the graph_join
module, avoiding a circular import between project.py and graph_join.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Node:
    """One addressable thing: what it is, where its page is, and what it is made of."""

    kind: str
    id: str
    slug: str
    label: str
    path: str
    data_origin: str
    is_demo_data: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "slug": self.slug,
            "label": self.label,
            "path": self.path,
            "data_origin": self.data_origin,
            "is_demo_data": self.is_demo_data,
        }


@dataclass(frozen=True)
class Link:
    """One traversed edge: the verb read from the node it was reached from, and the row that proved it."""

    verb: str
    direction: str
    other: Node
    facts: dict[str, Any]
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "verb": self.verb,
            "direction": self.direction,
            "other": self.other.as_dict(),
            "facts": dict(self.facts),
            "evidence": dict(self.evidence),
        }


class GraphRefusal(ValueError):
    """A question this tier will not answer. The code decides the status; see `answers.py`."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.details}