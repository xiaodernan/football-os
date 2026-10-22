"""`/metrics/system`'s headline rows were the AI ledger wearing a system badge.

`request_count` was `COUNT(ModelCall.id)` and `error_count` the failed subset of the same table, so the two
figures an operator looks at first measured how much AI the product bought. A door answering 404 all day,
a rate limiter firing, a worker wedging, none of it moved either number — and `/metrics/providers` already
answered the question they actually answered, better than they did.

These cases drive the row that replaced them: counts of what this process served, and a bounded sample of
what callers waited, on the same nearest-rank arithmetic the latency profile uses so the two cannot drift.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.request_metrics import SAMPLE_SIZE, record, reset, snapshot


class TestArithmetic:
    """What the sample is asked to answer, answered from the durations it was given."""

    def test_it_counts_and_averages_what_it_recorded(self) -> None:
        reset()
        for duration in (10.0, 20.0, 30.0, 40.0):
            record(200, duration)

        figure = snapshot()

        assert figure["request_count"] == 4
        assert figure["error_count"] == 0
        assert figure["avg_latency_ms"] == 25.0
        assert figure["p95_latency_ms"] == 40.0

    def test_a_server_error_is_an_error_and_anything_below_it_is_not(self) -> None:
        reset()
        record(404, 5.0)
        record(429, 5.0)
        record(200, 5.0)

        assert snapshot()["error_count"] == 0

        record(500, 5.0)
        record(503, 5.0)

        assert snapshot()["error_count"] == 2

    def test_the_sample_is_bounded_and_says_so(self) -> None:
        reset()
        for _index in range(SAMPLE_SIZE + 25):
            record(200, float(_index))

        figure = snapshot()

        assert figure["request_sample_size"] == SAMPLE_SIZE
        assert figure["request_sample_is_newest"] is True

        reset()
        record(200, 3.0)

        assert snapshot()["request_sample_is_newest"] is False


class TestTheDoor:
    """The rows as the door reports them, through the real middleware that does the recording."""

    def test_it_reports_the_requests_this_process_has_served(self, admin_client: TestClient) -> None:
        before = snapshot()["request_count"]

        # Two calls that buy no AI at all, so the arithmetic this replaced could not have moved.
        assert admin_client.get("/api/v1/healthz").status_code == 200
        assert admin_client.get("/api/v1/healthz").status_code == 200
        assert snapshot()["request_count"] - before == 2

        # The door reports what this process served. Its own request is recorded after the route has
        # answered — the response cannot carry a figure about a request that has not finished — so the
        # row it reads is the count as of the request that arrived just before it.
        assert admin_client.get("/api/v1/metrics/system").json()["request_count"] == before + 2

    def test_a_500_is_counted_even_though_the_middleware_that_serves_it_never_finishes(self) -> None:
        """The crash answer is produced outside every user middleware, so the count needs the second path."""
        from app.main import create_app

        boom = create_app()

        @boom.get("/__probe_boom")
        def _boom() -> None:
            raise RuntimeError("deliberate probe failure")

        before = snapshot()["error_count"]
        with TestClient(boom, raise_server_exceptions=False) as crash:
            assert crash.get("/__probe_boom").status_code == 500

        assert snapshot()["error_count"] == before + 1
