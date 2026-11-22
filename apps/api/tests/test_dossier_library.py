"""The shelf: a generated chapter that does not vanish with the tab.

`deep_dossier` answers a question; `dossier_library` keeps the answer. These cases pin the two
promises that make a shelf trustworthy — the same commission is never paid for twice, and the
second reader of a chapter gets the row the first reader wrote rather than a duplicate.

The gateway is never called here: `compute_deep_dossier` is replaced with a fixed chapter, so
the cases measure the shelf's own contract (dedupe, slug, counters) and not the model's prose.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.services.world import dossier_library


def _chapter(focus: str = "finals", **_: Any) -> dict[str, Any]:
    return {
        "available": True,
        "focus": focus,
        "chapter": "Real Madrid beat Stade de Reims 4–3 in 1956.\n\nDi Stéfano scored 14 that season.",
        "source_count": 46,
        "estimated_input_tokens": 88_397,
        "input_tokens": 131_386,
        "cached_input_tokens": 118_245,
        "verified": True,
    }


@pytest.fixture(autouse=True)
def _no_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dossier_library, "compute_deep_dossier", _chapter)


def test_signature_is_case_and_whitespace_insensitive() -> None:
    a = dossier_library.volume_signature("  European   Cup Finals ", "deep", 42, "en")
    b = dossier_library.volume_signature("european cup finals", "deep", 42, "en")
    assert a == b
    assert a != dossier_library.volume_signature("european cup finals", "epic", 42, "en")
    assert a != dossier_library.volume_signature("european cup finals", "deep", 7, "en")


def test_slug_is_readable_and_carries_the_signature_suffix() -> None:
    signature = dossier_library.volume_signature("European Cup finals", "deep", 42, "en")
    slug = dossier_library.volume_slug("European Cup finals", signature)
    assert slug == f"european-cup-finals-{signature[:8]}"


def test_the_same_commission_is_paid_for_once(client: Any) -> None:
    focus = f"European Cup finals {uuid.uuid4().hex[:6]}"
    first = client.post("/api/v1/world/deep-dossier/volumes", json={"focus": focus, "depth": "deep", "seed": 42})
    second = client.post("/api/v1/world/deep-dossier/volumes", json={"focus": focus.upper(), "depth": "deep", "seed": 42})

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert first.json()["slug"] == second.json()["slug"]
    assert first.json()["cached_input_tokens"] == 118_245
    assert first.json()["path"].startswith("/world/dossier-library/")


def test_the_shelf_lists_what_was_bound_and_a_detail_read_counts_a_view(client: Any) -> None:
    focus = f"The 1960 final {uuid.uuid4().hex[:6]}"
    bound = client.post("/api/v1/world/deep-dossier/volumes", json={"focus": focus, "depth": "standard", "seed": 9})
    assert bound.status_code == 201, bound.text
    slug = bound.json()["slug"]

    shelf = client.get("/api/v1/world/deep-dossier/volumes", params={"limit": 60})
    assert shelf.status_code == 200
    assert shelf.json()["total"] >= 1
    assert slug in {row["slug"] for row in shelf.json()["volumes"]}

    detail = client.get(f"/api/v1/world/deep-dossier/volumes/{slug}")
    again = client.get(f"/api/v1/world/deep-dossier/volumes/{slug}", params={"count_view": "false"})
    assert detail.status_code == 200
    assert again.json()["view_count"] == detail.json()["view_count"] == 1
    assert "Stade de Reims" in detail.json()["chapter"]


def test_a_missing_volume_is_404(client: Any) -> None:
    response = client.get("/api/v1/world/deep-dossier/volumes/no-such-volume")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"


def test_unknown_depth_and_empty_focus_are_refused(client: Any) -> None:
    assert client.post("/api/v1/world/deep-dossier/volumes", json={"focus": "x", "depth": "infinite"}).status_code == 422
    assert client.post("/api/v1/world/deep-dossier/volumes", json={"focus": ""}).status_code == 422
