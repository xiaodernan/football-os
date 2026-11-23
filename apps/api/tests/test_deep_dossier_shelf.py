"""The deep-dossier chapter shelf must resolve in a checkout *and* in the API image.

A previous build used `parents[5]`, which exists in the source tree but not in the container's
`/app/app/services/world/` layout; importing the module raised `IndexError` and the smoke container
never bound :8100. The shelf is now discovered by probing candidates, with an explicit mount as the
first choice.
"""

from __future__ import annotations

from pathlib import Path

from app.services.world import deep_dossier as dd


def test_the_shelf_resolves_without_raising() -> None:
    assert isinstance(dd.HISTORY_DIR, Path)
    assert dd.HISTORY_DIR.name == "history"


def test_an_explicit_mount_wins(monkeypatch: object, tmp_path: Path) -> None:
    shelf = tmp_path / "history"
    shelf.mkdir()
    monkeypatch.setenv("FOOTBALL_KNOWLEDGE_DIR", str(tmp_path))  # type: ignore[attr-defined]
    assert dd._resolve_history_dir() == shelf


def test_a_missing_mount_falls_through_to_the_checkout() -> None:
    assert dd.HISTORY_DIR.is_dir()  # the repository always carries the verified chapters
