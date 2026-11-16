"""The Real Book — the real world's World Cup 2022, facts from CC-BY openfootball.

The synthetic world in this product is deliberately not real football. This door
is the companion: it carries a curated hand of real numbers from the real 2022
World Cup — sourced from the openfootball worldcup.json file, used with attribution.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.db import SessionLocal
from app.services.world.real_book import ATTRIBUTION, REAL_FACTS_2022, compute_real_book

API = "/api/v1"


class TestTheRealBook:
    def test_every_fact_is_internally_consistent(self) -> None:
        result = compute_real_book()
        assert result["available"] is True
        facts = result["facts"]
        assert facts["tournament"] == "2022 FIFA World Cup"
        assert facts["total_matches"] == 64
        assert facts["venues"] == 8
        # 48 + 8 + 4 + 2 + 1 + 1 = 64
        assert sum(r["matches"] for r in facts["final_rounds"]) == 64
        assert facts["champion"]["name"] == "Argentina"
        assert facts["final"]["home"] == "Argentina"
        assert facts["final"]["away"] == "France"
        assert facts["final"]["score_penalties"] == [4, 2]
        assert facts["runner_up"]["name"] == "France"
        assert "Mbappé" in facts["runner_up"]["star"]
        assert "Messi" in facts["golden_ball"]["name"]
        assert "Argentina" in facts["biggest_win"]["match"]
        assert facts["biggest_win"]["score"] == [3, 0]
        assert facts["biggest_attendance"]["match"] == "Argentina vs France"

    def test_attribution_is_required_and_complete(self) -> None:
        result = compute_real_book()
        assert result["attribution"] == ATTRIBUTION
        # The attribution names the source and the license.
        assert "openfootball" in result["attribution"]
        assert "CC-BY" in result["attribution"]
        assert "4.0" in result["attribution"]

    def test_provenance_marks_the_real_book_as_real(self) -> None:
        result = compute_real_book()
        assert result["provenance"]["data_origin"] == "public-real"
        assert result["provenance"]["is_demo_data"] is False
        assert result["provenance"]["license"] == "CC-BY 4.0"

    def test_the_door_answers_with_the_envelope_like_its_siblings(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/real-book")
        assert response.status_code == 200
        body = response.json()
        assert body["disclaimer"] is not None
        assert body["source"]
        assert body["facts"]["tournament"] == "2022 FIFA World Cup"
        assert body["provenance"]["data_origin"] == "public-real"
