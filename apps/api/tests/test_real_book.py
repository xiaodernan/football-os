"""The Real Book — the real world's World Cup 2022, facts from CC-BY openfootball.

The synthetic world in this product is deliberately not real football. This door
is the companion: it carries real 2022 World Cup facts sourced from the openfootball
worldcup.json file, used with attribution — including the committed snapshot of all
64 fixtures under ``app/services/world/data/``.
"""

from __future__ import annotations

from app.services.world.real_book import ATTRIBUTION, compute_real_book

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
        assert facts["biggest_attendance"]["match"] == "Argentina vs France"
        # The snapshot's own arithmetic: Spain 7-0 Costa Rica is the widest margin.
        assert facts["biggest_win"]["match"] == "Spain 7-0 Costa Rica"
        assert facts["biggest_win"]["score"] == [7, 0]
        assert facts["biggest_win"]["matchday_date"] == "2022-11-23"
        assert facts["goals_scored"] == 172

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

    def test_the_committed_snapshot_prints_all_64_fixtures(self) -> None:
        result = compute_real_book()
        results = result["results"]
        assert len(results) == 64
        for row in results:
            assert row["team1"] and row["team2"]
            assert row["date"] and row["round"] and row["ground"]
            assert 2022 == int(row["date"][:4])
            a, b = row["on_field"]
            assert a >= 0 and b >= 0
        # the on-field goal total recomputed from the rows is the published figure
        assert sum(row["on_field"][0] + row["on_field"][1] for row in results) == result["facts"]["goals_scored"] == 172
        # the final is in the list, with the penalties shootout captured
        final = next(row for row in results if row["round"] == "Final")
        assert final["team1"] == "Argentina" and final["team2"] == "France"
        assert final["on_field"] == [3, 3]
        assert final["penalties"] == [4, 2]

    def test_the_scorers_table_merges_the_two_mbappe_spellings(self) -> None:
        result = compute_real_book()
        scorers = {row["name"]: row for row in result["scorers"]}
        assert scorers["Kylian Mbappé"]["goals"] == 8
        assert scorers["Lionel Messi"]["goals"] == 7
        assert scorers["Kylian Mbappé"]["penalties"] >= 2
        # no duplicate-spelling entries leak into the table
        assert "Mbappé" not in scorers

    def test_the_door_answers_with_the_envelope_like_its_siblings(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/real-book")
        assert response.status_code == 200
        body = response.json()
        assert body["disclaimer"] is not None
        assert body["source"]
        assert body["facts"]["tournament"] == "2022 FIFA World Cup"
        assert body["provenance"]["data_origin"] == "public-real"
        assert len(body["results"]) == 64
        assert body["scorers"], "the door publishes a scorers table derived from the committed snapshot"
