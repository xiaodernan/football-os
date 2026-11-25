"""The fact pack must count the basket it actually ships.

The personal page reads docs/latest.json live; a hand-typed chapter count there is how the public
ribbon went stale before. This test derives the count from the baked documents on disk, so a new
chapter cannot land without the pack (and the showcase) noticing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "docs" / "latest.json"


def basket_documents() -> list[Path]:
    return [
        p for p in (ROOT / "data" / "knowledge").rglob("*.md")
        if p.name.lower() != "readme.md"
    ]


def test_the_pack_reports_the_real_basket_count() -> None:
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    assert pack["basket_chapters"] == len(basket_documents())


def test_the_pack_reports_the_real_finals_count() -> None:
    """The public ribbon once said '270 real finals' for years; derive it from the shelf instead."""
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    finals = [
        p for p in (ROOT / "data" / "knowledge" / "history").glob("*-final.md")
        if not p.name.endswith("-zh.md")
    ]
    assert pack["real_finals"] == len(finals)


def test_the_pack_is_not_a_placeholder() -> None:
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    assert re.fullmatch(r"[0-9a-f]{7,12}", pack["head"])
    assert pack["total_commits"] > 0
    assert pack["screens"] > 0
    assert pack["locales"] >= 2
    assert pack["feature_surface"]
