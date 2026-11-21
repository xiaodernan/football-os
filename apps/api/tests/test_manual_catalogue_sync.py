"""The in-app manual's generated spec must never describe a door the six-locale catalogue lacks."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.services.manual_spec import MANUAL_CONTEXT, MANUAL_SPEC_BYTES

ROOT = Path(__file__).resolve().parents[3]
EN = ROOT / "apps" / "web" / "messages" / "en.json"


def _catalogue() -> dict:
    return json.loads(EN.read_text(encoding="utf-8"))


def test_byte_pin_matches_the_context():
    assert len(MANUAL_CONTEXT.encode("utf-8")) == MANUAL_SPEC_BYTES


def test_the_manual_tours_only_catalogued_doors():
    manual = _catalogue()["manual"]
    # Every tourN pair the spec generator walks must exist in the catalogue.
    numbered = sorted(
        {int(re.search(r"\d+", k).group()) for k in manual if re.fullmatch(r"tour\d+[td]", k)}
    )
    # The generated spec's tour section has exactly that many entries.
    tour_block = MANUAL_CONTEXT.split("## The doors tour\n", 1)[1].split("\n\n## ", 1)[0]
    rendered = [line for line in tour_block.splitlines() if line.startswith("- **")]
    assert len(rendered) == len(numbered), (
        f"the manual spec renders {len(rendered)} tour doors but the catalogue has {len(numbered)}"
    )


def test_no_orphan_feature_is_described_as_a_tour_door():
    # regression: season-brief and opponent-brief are API-only doors (POST endpoints) and are NOT
    # clickable catalogue doors. They must not reappear in the tour as if a reader could tap them.
    tour_block = MANUAL_CONTEXT.split("## The doors tour\n", 1)[1].split("\n\n## ", 1)[0].lower()
    for orphan in ("season brief", "opposition analyst", "opponent brief"):
        assert orphan not in tour_block, f"{orphan} is not a catalogue tour door"
    # The features themselves are real and must not be denied — only their presence in the tour.
    assert Path(ROOT / "apps/api/app/services/season_brief.py").exists()
    assert Path(ROOT / "apps/api/app/services/opponent_analyst.py").exists()
