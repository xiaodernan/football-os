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
        assert sum(r["matches"] for r in facts["final_rounds"]) == facts["total_matches"] == 64
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
        assert sum(r["matches"] for r in facts["final_rounds"]) == facts["total_matches"]
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

    def test_2014_prints_its_own_arithmetic(self) -> None:
        result = compute_real_book("2014")
        assert result["available"] is True
        assert result["tournament"] == "2014"
        facts = result["facts"]
        assert facts["tournament"] == "2014 FIFA World Cup"
        assert facts["total_matches"] == 64
        assert facts["venues"] == 12
        assert sum(r["matches"] for r in facts["final_rounds"]) == facts["total_matches"]
        assert facts["champion"]["name"] == "Germany"
        assert facts["final"]["home"] == "Germany"
        assert facts["final"]["away"] == "Argentina"
        assert facts["final"]["score_regular"] == [0, 0]
        assert facts["final"]["score_extra_time"] == [1, 0]
        assert facts["has_penalties"] is False
        assert facts["runner_up"]["name"] == "Argentina"
        assert "Messi" in facts["runner_up"]["star"]
        assert facts["biggest_win"]["match"] == "Brazil 1-7 Germany"
        assert facts["biggest_win"]["stage"] == "Semi-finals"
        assert facts["biggest_win"]["matchday_date"] == "2014-07-08"
        assert facts["goals_scored"] == 171

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
        for tournament, goals in (("2022", 172), ("2018", 169), ("2014", 171), ("2010", 145), ("2006", 147), ("2002", 161)):
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
        final_2014 = next(row for row in compute_real_book("2014")["results"] if row["round"] == "Final")
        assert final_2014["team1"] == "Germany" and final_2014["team2"] == "Argentina"
        assert final_2014["on_field"] == [1, 0]

    def test_2010_prints_its_own_arithmetic_and_its_silence(self) -> None:
        result = compute_real_book("2010")
        assert result["available"] is True
        assert result["tournament"] == "2010"
        facts = result["facts"]
        assert facts["tournament"] == "2010 FIFA World Cup"
        assert facts["total_matches"] == 64
        assert facts["venues"] == 10
        assert sum(r["matches"] for r in facts["final_rounds"]) == facts["total_matches"]
        assert facts["champion"]["name"] == "Spain"
        assert facts["final"]["home"] == "Netherlands"
        assert facts["final"]["away"] == "Spain"
        assert facts["final"]["score_extra_time"] == [0, 1]
        assert facts["has_penalties"] is False
        assert facts["biggest_win"]["match"] == "Portugal 7-0 North Korea"
        assert facts["biggest_win"]["matchday_date"] == "2010-06-21"
        assert facts["goals_scored"] == 145
        # The snapshot transcribes fixtures and scorelines, not scorer lists.
        assert result["scorers"] == []

    def test_2006_prints_its_own_arithmetic_and_its_silence(self) -> None:
        result = compute_real_book("2006")
        assert result["available"] is True
        assert result["tournament"] == "2006"
        facts = result["facts"]
        assert facts["tournament"] == "2006 FIFA World Cup"
        assert facts["total_matches"] == 64
        assert facts["venues"] == 12
        assert sum(r["matches"] for r in facts["final_rounds"]) == facts["total_matches"]
        assert facts["champion"]["name"] == "Italy"
        assert facts["final"]["home"] == "Italy"
        assert facts["final"]["away"] == "France"
        assert facts["final"]["score_penalties"] == [5, 3]
        assert facts["has_penalties"] is True
        assert facts["biggest_win"]["match"] == "Argentina 6-0 Serbia and Montenegro"
        assert facts["biggest_win"]["matchday_date"] == "2006-06-16"
        assert facts["goals_scored"] == 147
        # The snapshot transcribes goal minutes only for nine entries in four matches; the door prints none.
        assert result["scorers"] == []

    def test_2002_prints_its_own_arithmetic_and_its_silence(self) -> None:
        result = compute_real_book("2002")
        assert result["available"] is True
        assert result["tournament"] == "2002"
        facts = result["facts"]
        assert facts["tournament"] == "2002 FIFA World Cup"
        assert facts["total_matches"] == 64
        assert facts["venues"] == 20
        assert sum(r["matches"] for r in facts["final_rounds"]) == facts["total_matches"]
        assert facts["champion"]["name"] == "Brazil"
        assert facts["final"]["home"] == "Germany"
        assert facts["final"]["away"] == "Brazil"
        assert facts["final"]["score_regular"] == [0, 2]
        assert facts["has_penalties"] is False
        assert facts["biggest_win"]["match"] == "Germany 8-0 Saudi Arabia"
        assert facts["biggest_win"]["matchday_date"] == "2002-06-01"
        assert facts["goals_scored"] == 161
        # The snapshot transcribes fixtures and scorelines, not scorer lists.
        assert result["scorers"] == []

    def test_1998_prints_its_own_arithmetic_and_its_silence(self) -> None:
        result = compute_real_book("1998")
        assert result["available"] is True
        assert result["tournament"] == "1998"
        facts = result["facts"]
        assert facts["tournament"] == "1998 FIFA World Cup"
        assert facts["total_matches"] == 64
        assert facts["venues"] == 10
        assert sum(r["matches"] for r in facts["final_rounds"]) == facts["total_matches"]
        assert facts["champion"]["name"] == "France"
        assert facts["final"]["home"] == "Brazil"
        assert facts["final"]["away"] == "France"
        assert facts["final"]["score_regular"] == [0, 3]
        assert facts["has_penalties"] is False
        assert facts["biggest_win"]["match"] == "Spain 6-1 Bulgaria"
        assert facts["biggest_win"]["matchday_date"] == "1998-06-24"
        assert facts["goals_scored"] == 171
        assert result["scorers"] == []

    def test_1994_prints_its_own_arithmetic_and_its_silence(self) -> None:
        result = compute_real_book("1994")
        assert result["available"] is True
        assert result["tournament"] == "1994"
        facts = result["facts"]
        assert facts["tournament"] == "1994 FIFA World Cup"
        assert facts["total_matches"] == 52
        assert facts["venues"] == 9
        assert sum(r["matches"] for r in facts["final_rounds"]) == facts["total_matches"]
        assert facts["champion"]["name"] == "Brazil"
        assert facts["final"]["home"] == "Brazil"
        assert facts["final"]["away"] == "Italy"
        assert facts["final"]["score_penalties"] == [3, 2]
        assert facts["has_penalties"] is True
        assert facts["biggest_win"]["match"] == "Russia 6-1 Cameroon"
        assert facts["biggest_win"]["matchday_date"] == "1994-06-28"
        assert facts["goals_scored"] == 141
        assert result["scorers"] == []

    def test_1990_prints_its_own_arithmetic_and_its_silence(self) -> None:
        result = compute_real_book("1990")
        assert result["available"] is True
        assert result["tournament"] == "1990"
        facts = result["facts"]
        assert facts["tournament"] == "1990 FIFA World Cup"
        assert facts["total_matches"] == 52
        assert facts["venues"] == 14
        assert sum(r["matches"] for r in facts["final_rounds"]) == facts["total_matches"]
        assert facts["champion"]["name"] == "West Germany"
        assert facts["final"]["home"] == "West Germany"
        assert facts["final"]["away"] == "Argentina"
        assert facts["final"]["score_regular"] == [1, 0]
        assert facts["has_penalties"] is False
        assert facts["biggest_win"]["match"] == "United States 1-5 Czechoslovakia"
        assert facts["biggest_win"]["matchday_date"] == "1990-06-10"
        assert facts["goals_scored"] == 115
        # The snapshot transcribes goal minutes only for eight entries in five matches.
        assert result["scorers"] == []

    def test_1986_prints_its_own_arithmetic_and_its_silence(self) -> None:
        result = compute_real_book("1986")
        assert result["available"] is True
        assert result["tournament"] == "1986"
        facts = result["facts"]
        assert facts["tournament"] == "1986 FIFA World Cup"
        assert facts["total_matches"] == 52
        assert facts["venues"] == 12
        assert sum(r["matches"] for r in facts["final_rounds"]) == facts["total_matches"]
        assert facts["champion"]["name"] == "Argentina"
        assert facts["final"]["home"] == "Argentina"
        assert facts["final"]["away"] == "West Germany"
        assert facts["final"]["score_regular"] == [3, 2]
        assert facts["has_penalties"] is False
        assert facts["biggest_win"]["match"] == "Soviet Union 6-0 Hungary"
        assert facts["biggest_win"]["matchday_date"] == "1986-06-02"
        assert facts["goals_scored"] == 132
        assert result["scorers"] == []

    def test_euro_2024_prints_its_own_arithmetic_computed_from_the_bytes(self) -> None:
        result = compute_real_book("euro2024")
        assert result["available"] is True
        assert result["tournament"] == "euro2024"
        facts = result["facts"]
        assert facts["tournament"] == "UEFA Euro 2024"
        assert facts["total_matches"] == 51
        assert facts["venues"] == 10
        assert sum(r["matches"] for r in facts["final_rounds"]) == facts["total_matches"]
        assert facts["champion"]["name"] == "Spain"
        assert facts["final"]["home"] == "Spain"
        assert facts["final"]["away"] == "England"
        assert facts["final"]["score_regular"] == [2, 1]
        assert facts["has_penalties"] is False
        assert facts["biggest_win"]["match"] == "Germany 5-1 Scotland"
        assert facts["biggest_win"]["matchday_date"] == "2024-06-14"
        assert facts["goals_scored"] == 117
        # The Euro 2024 file carries every goal; the snapshot counts 117 total.
        assert result["scorers"]
        assert result["scorers"][0]["goals"] == 3
        assert any(row["name"] == "Kane" and row["goals"] == 3 for row in result["scorers"])

    def test_euro_2021_prints_its_own_arithmetic_computed_from_the_bytes(self) -> None:
        result = compute_real_book("euro2021")
        assert result["available"] is True
        assert result["tournament"] == "euro2021"
        facts = result["facts"]
        assert facts["tournament"] == "UEFA Euro 2021 (the 2020 European Championship)"
        assert facts["total_matches"] == 51
        assert facts["venues"] == 11
        assert sum(r["matches"] for r in facts["final_rounds"]) == facts["total_matches"]
        assert facts["champion"]["name"] == "Italy"
        assert facts["final"]["home"] == "Italy"
        assert facts["final"]["away"] == "England"
        assert facts["final"]["score_penalties"] == [3, 2]
        assert facts["has_penalties"] is True
        assert facts["biggest_win"]["match"] == "Slovakia 0-5 Spain"
        assert facts["biggest_win"]["matchday_date"] == "2021-06-23"
        assert facts["goals_scored"] == 142
        assert result["scorers"]
        assert result["scorers"][0]["goals"] == 5
        assert any(row["name"] == "Ronaldo" and row["goals"] == 5 for row in result["scorers"])

    def test_the_champions_door_carries_worldcups_only(self) -> None:
        from app.services.world.real_book import tournaments

        assert "euro2024" not in tournaments()
        assert "euro2021" not in tournaments()
        assert set(tournaments()) == {"1934", "1938", "1950", "1954", "1958", "1962", "1966", "1970", "1974", "1978", "1982", "1986", "1990", "1994", "1998", "2002", "2006", "2010", "2014", "2018", "2022"}

    def test_the_scorers_tables_derive_from_the_committed_snapshots(self) -> None:
        scorers_2022 = {row["name"]: row for row in compute_real_book("2022")["scorers"]}
        assert scorers_2022["Kylian Mbappé"]["goals"] == 8
        assert scorers_2022["Lionel Messi"]["goals"] == 7
        assert scorers_2022["Kylian Mbappé"]["penalties"] >= 2
        assert "Mbappé" not in scorers_2022
        scorers_2018 = {row["name"]: row for row in compute_real_book("2018")["scorers"]}
        assert scorers_2018["Kane"]["goals"] == 5
        assert scorers_2018["Kane"]["penalties"] == 2
        scorers_2014 = {row["name"]: row for row in compute_real_book("2014")["scorers"]}
        # The snapshot spells him both ways; the door prints the file's own name for 2014.
        assert scorers_2014["James Rodríguez"]["goals"] == 5
        assert scorers_2014["Thomas Müller"]["goals"] == 5

    def test_an_unknown_tournament_is_refused(self) -> None:
        with pytest.raises(UnknownTournament):
            compute_real_book("0095")

    def test_the_door_answers_with_the_envelope_like_its_siblings(self, client) -> None:  # type: ignore[no-untyped-def]
        for tournament, expected in (("2022", "2022 FIFA World Cup"), ("2018", "2018 FIFA World Cup"), ("2014", "2014 FIFA World Cup")):
            response = client.get(f"{API}/world/real-book", params={"tournament": tournament})
            assert response.status_code == 200
            body = response.json()
            assert body["disclaimer"] is not None
            assert body["source"]
            assert body["facts"]["tournament"] == expected
            assert body["provenance"]["data_origin"] == "public-real"
            assert len(body["results"]) == 64
            assert body["scorers"], "the door publishes a scorers table derived from the committed snapshot"
        for tournament, expected in (("2010", "2010 FIFA World Cup"), ("2006", "2006 FIFA World Cup"), ("2002", "2002 FIFA World Cup"),
                                     ("1998", "1998 FIFA World Cup"), ("1994", "1994 FIFA World Cup"),
                                     ("1990", "1990 FIFA World Cup"), ("1986", "1986 FIFA World Cup"),
                                     ("1982", "1982 FIFA World Cup"), ("1978", "1978 FIFA World Cup"),
                                     ("1974", "1974 FIFA World Cup"), ("1970", "1970 FIFA World Cup"),
                                     ("1966", "1966 FIFA World Cup"), ("1962", "1962 FIFA World Cup"),
                                     ("1958", "1958 FIFA World Cup"), ("1954", "1954 FIFA World Cup — the Miracle of Bern"),
                                     ("1950", "1950 FIFA World Cup — the Maracanazo"), ("1938", "1938 FIFA World Cup"),
                                     ("1934", "1934 FIFA World Cup")):
            response = client.get(f"{API}/world/real-book", params={"tournament": tournament})
            assert response.status_code == 200
            body = response.json()
            assert body["disclaimer"] is not None
            assert body["source"]
            assert body["facts"]["tournament"] == expected
            assert body["provenance"]["data_origin"] == "public-real"
            counts = {"1986": 52, "1990": 52, "1994": 52, "1982": 52, "1974": 38, "1978": 38, "1970": 32,
                      "1966": 32, "1962": 32, "1958": 35, "1954": 26, "1950": 22, "1938": 18, "1934": 17}
            assert len(body["results"]) == counts.get(tournament, 64)
            scorer_cups = {"1938", "1934", "1950"}
            if tournament in scorer_cups:
                assert body["scorers"], "the door prints the scorers the committed file counts"
            else:
                assert body["scorers"] == [], "the door prints no scorers table the committed file does not carry"

    def test_the_door_rejects_a_tournament_it_does_not_carry(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/real-book", params={"tournament": "0095"})
        assert response.status_code == 422
