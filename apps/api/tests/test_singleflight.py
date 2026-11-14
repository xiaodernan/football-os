"""The world-search lane: one leader, many followers, no duplicate scan.

`Singleflight.call` is the in-process half of the answer to "what if K identical readers
arrive before the 60-second response cache opens a lane of its own". These cases pin the four
properties the design promises, then the doorwiring itself: that a K-thread burst on
`unified_search` with a cold cache executes `search_world` exactly once.
"""

from __future__ import annotations

import threading

from starlette.requests import Request

from app.core.singleflight import Singleflight

APP_PATH = "/api/v1/world/search"


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": APP_PATH,
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("testserver", 80),
        }
    )


class TestTheLane:
    def test_k_followers_share_one_call(self) -> None:
        flight = Singleflight("t")
        started = threading.Event()
        release = threading.Event()
        executions = 0

        def slow() -> str:
            nonlocal executions
            executions += 1
            started.set()
            release.wait(5)
            return "the-answer"

        results: list[str] = []
        errors: list[BaseException] = []

        def follower() -> None:
            try:
                results.append(flight.call("k", slow))
            except BaseException as exc:  # pragma: no cover - failure path proven separately
                errors.append(exc)

        leader = threading.Thread(target=follower)
        leader.start()
        assert started.wait(5), "the leader should be inside the call"
        threads = [threading.Thread(target=follower) for _ in range(11)]
        for thread in threads:
            thread.start()
        release.set()
        leader.join(5)
        for thread in threads:
            thread.join(5)
        assert errors == []
        assert executions == 1
        assert results.count("the-answer") == 12
        assert flight.stats() == {"leaders": 1, "joins": 11}

    def test_the_lane_empties_after_a_call(self) -> None:
        flight = Singleflight("t")
        assert flight.call("k", lambda: 1) == 1
        assert flight.inflight_size() == 0

    def test_a_call_after_completion_gets_a_fresh_lane(self) -> None:
        flight = Singleflight("t")
        executions = []

        def produce() -> int:
            executions.append(1)
            return len(executions)

        flight.call("k", produce)
        flight.call("k", produce)
        assert executions == [1, 1]
        assert flight.stats()["joins"] == 0

    def test_a_leader_exception_reaches_every_follower(self) -> None:
        flight = Singleflight("t")
        boom = RuntimeError("the world refused")

        def broken() -> None:
            raise boom

        try:
            flight.call("k", broken)
        except RuntimeError as exc:
            assert exc is boom
        else:  # pragma: no cover
            raise AssertionError("leader must raise")

    def test_each_follower_reraises_the_leaders_exception(self) -> None:
        flight = Singleflight("t")
        started = threading.Event()
        release = threading.Event()

        def broken() -> None:
            started.set()
            release.wait(5)
            raise ValueError("shared failure")

        leader_boom: list[BaseException] = []

        def leader() -> None:
            try:
                flight.call("k", broken)
            except BaseException as exc:
                leader_boom.append(exc)

        thread = threading.Thread(target=leader)
        thread.start()
        assert started.wait(5)
        # follower must attach before the leader fails
        follower_boom: list[BaseException] = []

        def follower() -> None:
            try:
                flight.call("k", broken)
            except BaseException as exc:
                follower_boom.append(exc)

        second = threading.Thread(target=follower)
        second.start()
        release.set()
        thread.join(5)
        second.join(5)
        assert len(leader_boom) == 1
        assert len(follower_boom) == 1
        assert isinstance(follower_boom[0], ValueError)
        assert flight.stats() == {"leaders": 1, "joins": 1}


def test_the_door_coalesces_a_cold_cache_burst(monkeypatch) -> None:
    """The wiring, not just the class: a burst through `unified_search` runs `search_world` once."""
    from app.api.v1 import world as world_module

    executions = []
    release = threading.Event()
    started = threading.Event()

    class FakeHit:
        def __init__(self) -> None:
            self.type = "team"

        def to_dict(self):
            return {"type": "team", "slug": "viremont", "id": "w-tm-viremont"}


    def fake_search_world(db, query, *, types=None, limit=20):
        executions.append(query)
        started.set()
        release.wait(5)
        return [FakeHit()]

    monkeypatch.setattr(world_module, "search_world", fake_search_world)

    errors: list[BaseException] = []

    def hit_door(results: list) -> None:
        try:
            results.append(
                world_module.unified_search(
                    _request(),
                    q="viremont",
                    types=None,
                    limit_rows=20,
                    db=None,  # the fake never touches a session
                )
            )
        except BaseException as exc:
            errors.append(exc)

    results: list = []
    leader = threading.Thread(target=lambda: hit_door(results))
    leader.start()
    assert started.wait(5)
    followers = [threading.Thread(target=lambda: hit_door(results)) for _ in range(6)]
    for follower in followers:
        follower.start()
    release.set()
    leader.join(5)
    for follower in followers:
        follower.join(5)
    assert errors == [], [repr(e) for e in errors]
    assert executions == ["viremont"]
    assert len(results) == 7
    assert all(body["results"] and body["results"][0]["slug"] == "viremont" for body in results)
    world_module.world_search_flight.reset_stats()
