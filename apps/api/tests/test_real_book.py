"""The Real Book — the real world's World Cups, facts from CC-BY openfootball.

The synthetic world in this product is deliberately not real football. This door
is the companion: it carries real World Cup facts sourced from the openfootball
worldcup.json files, used with attribution — including the committed snapshots of
all 64 fixtures per tournament under ``app/services/world/data/``.
"""

from __future__ import annotations

import pytest

from app.services.world.real_book import ATTRIBUTION, UnknownTournament, compute_real_book, tournaments

API = "/api/v1"


class TestTheRealBook:
    def test_every_2022_fact_is_internally_consistent(self) -> None:
        result = compute_real_book()
        assert result["available"] is True
        assert result["tournament"] == "2022"
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
        assert facts["goals_scored"] == 172

    def test_2018_prints_its_own_arithmetic(self) -> None:
        result = compute_real_book("2018")
        assert result["available"] is True
        assert result["tournament"] == "2018"
        facts = result["facts"]
        assert facts["tournament"] == "2018 FIFA World Cup"
        assert facts["total_matches"] == 64
        assert facts["venues"] == 13
        assert sum(r["matches"] for r in facts["final_rounds"]) == 64
        assert facts["champion"]["name"] == "France"
        assert facts["final"]["home"] == "France"
        assert facts["final"]["away"] == "Croatia"
        assert facts["final"]["score_regular"] == [4, 2]
        assert facts["final"]["score_extra_time"] == [4, 2]
        assert facts["has_penalties"] is False
        assert facts["runner_up"]["name"] == "Croatia"
        assert "Modrić" in facts["runner_up"]["star"]
        assert facts["biggest_win"]["match"] == "Russia 5-0 Saudi Arabia"
        assert facts["biggest_win"]["stage"] == "Matchday 1"
        assert facts["biggest_win"]["matchday_date"] == "2018-06-14"
        assert facts["goals_scored"] == 169

    def test_attribution_is_required_and_complete(self) -> None:
        for tournament in tournaments():
            result = compute_real_book(tournament)
            assert result["attribution"] == ATTRIBUTION
            assert "openfootball" in result["attribution"]
            assert "CC-BY" in result["attribution"]
            assert "4.0" in result["attribution"]

    def test_provenance_marks_the_real_book_as_real(self) -> None:
        for tournament in tournaments():
            result = compute_real_book(tournament)
            assert result["provenance"]["data_origin"] == "public-real"
            assert result["provenance"]["is_demo_data"] is False
            assert result["provenance"]["license"] == "CC-BY 4.0"

    def test_the_committed_snapshots_print_all_64_fixtures_each(self) -> None:
        for tournament, goals in (("2022", 172), ("2018", 169)):
            result = compute_real_book(tournament)
            results = result["results"]
            assert len(results) == 64
            for row in results:
                assert row["team1"] and row["team2"]
                assert row["date"] and row["round"] and row["ground"]
                a, b = row["on_field"]
                assert a >= 0 and b >= 0
            assert sum(row["on_field"][0] + row["on_field"][1] for row in results) == result["facts"]["goals_scored"] == goals
        final_2022 = next(row for row in compute_real_book("2022")["results"] if row["round"] == "Final")
        assert final_2022["team1"] == "Argentina" and final_2022["team2"] == "France"
        assert final_2022["on_field"] == [3, 3]
        assert final_2022["penalties"] == [4, 2]
        final_2018 = next(row for row in compute_real_book("2018")["results"] if row["round"] == "Final")
        assert final_2018["team1"] == "France" and final_2018["team2"] == "Croatia"
        assert final_2018["on_field"] == [4, 2]
        assert final_2018["penalties"] is None

    def test_the_scorers_tables_derive_from_the_committed_snapshots(self) -> None:
        scorers_2022 = {row["name"]: row for row in compute_real_book("2022")["scorers"]}
        assert scorers_2022["Kylian Mbappé"]["goals"] == 8
        assert scorers_2022["Lionel Messi"]["goals"] == 7
        assert scorers_2022["Kylian Mbappé"]["penalties"] >= 2
        assert "Mbappé" not in scorers_2022
        scorers_2018 = {row["name"]: row for row in compute_real_book("2018")["scorers"]}
        assert scorers_2018["Kane"]["goals"] == 5
        assert scorers_2018["Kane"]["penalties"] == 2

    def test_an_unknown_tournament_is_refused(self) -> None:
        with pytest.raises(UnknownTournament):
            compute_real_book("2014")

    def test_the_door_answers_with_the_envelope_like_its_siblings(self, client) -> None:  # type: ignore[no-untyped-def]
        for tournament, expected in (("2022", "2022 FIFA World Cup"), ("2018", "2018 FIFA World Cup")):
            response = client.get(f"{API}/world/real-book", params={"tournament": tournament})
            assert response.status_code == 200
            body = response.json()
            assert body["disclaimer"] is not None
            assert body["source"]
            assert body["facts"]["tournament"] == expected
            assert body["provenance"]["data_origin"] == "public-real"
            assert len(body["results"]) == 64
            assert body["scorers"], "the door publishes a scorers table derived from the committed snapshot"

    def test_the_door_rejects_a_tournament_it_does_not_carry(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/real-book", params={"tournament": "2014"})
        assert response.status_code == 422
