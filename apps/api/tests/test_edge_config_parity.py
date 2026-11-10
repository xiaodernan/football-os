"""The edge carries two copies of the same settings; this gate keeps them one answer.

The gateway can be configured from its own `application.yml` when the config server is absent, and from
`config-repo/football-edge.yml` when it is present. A drift between the two is not a documentation
problem: the routes, the breaker's lifecycle and the rate limiter would all change behaviour depending on
whether another container happened to be up. That is two gateways wearing one name.

Both files are read here as data — no Spring context, no ports — so the gate is fast and fails at the
first divergent key. The route table is compared as id / order / uri / predicates / filters, and the
breaker and limiter blocks are compared whole.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
EDGE = ROOT / "services" / "edge" / "src" / "main" / "resources" / "application.yml"
SERVED = ROOT / "services" / "config" / "src" / "main" / "resources" / "config-repo" / "football-edge.yml"


def _doc(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path} is not a YAML mapping: {loaded!r}"
    return loaded


def _routes(path: Path) -> list[dict[str, Any]]:
    routes = _doc(path)["spring"]["cloud"]["gateway"]["server"]["webflux"]["routes"]
    assert isinstance(routes, list) and routes, f"{path} publishes no routes"
    return routes


def _shape(route: dict[str, Any]) -> tuple[Any, ...]:
    """What a route means, with the keys a reader would call its shape."""
    return (
        route["id"],
        route.get("order", 0),
        route["uri"],
        list(route.get("predicates", [])),
        list(route.get("filters", [])),
    )


def test_the_two_copies_publish_the_same_route_table() -> None:
    own = [_shape(route) for route in _routes(EDGE)]
    served = [_shape(route) for route in _routes(SERVED)]
    assert own == served, (
        "the edge's own route table and the config server's copy disagree: "
        f"{own!r} vs {served!r}. A gateway whose routes change when the config server is up is two gateways."
    )
    assert [route[0] for route in own] == ["core-api", "web"], (
        "the route order is the matching order: the API prefix must be claimed before the catch-all"
    )
    assert own[0][1] < own[1][1], "core-api must sort before web, or the catch-all would swallow the API"


def test_the_two_copies_set_the_same_breaker() -> None:
    own = _doc(EDGE)["resilience4j"]["circuitbreaker"]["configs"]["default"]
    served = _doc(SERVED)["resilience4j"]["circuitbreaker"]["configs"]["default"]
    assert own == served, (
        "the breaker behaves differently depending on whether the config server is up: "
        f"{own!r} vs {served!r}"
    )
    assert own["sliding-window-size"] == 10
    assert own["minimum-number-of-calls"] == 5, (
        "a minimum larger than the window can never be reached, so the breaker could never open"
    )
    assert own["minimum-number-of-calls"] <= own["sliding-window-size"]


def test_the_two_copies_set_the_same_limiter() -> None:
    own = _doc(EDGE)["edge"]["rate-limit"]
    served = _doc(SERVED)["edge"]["rate-limit"]
    assert own == served, (
        "the limiter behaves differently depending on whether the config server is up: "
        f"{own!r} vs {served!r}"
    )


def test_the_two_copies_agree_on_the_plane_setting_and_the_refresh_door() -> None:
    """Item 59 added a refreshable setting; it must not exist in only one of the two gateways."""
    own = _doc(EDGE)
    served = _doc(SERVED)
    assert own["edge"]["plane"] == served["edge"]["plane"], (
        "the refreshable plane setting differs between the edge's own config and the config server's copy"
    )
    own_include = own["management"]["endpoints"]["web"]["exposure"]["include"]
    served_include = served["management"]["endpoints"]["web"]["exposure"]["include"]
    assert own_include == served_include, (
        f"the actuator exposure differs between the two copies: {own_include!r} vs {served_include!r}"
    )
    assert "refresh" in own_include.split(","), (
        "without the refresh endpoint exposed, a changed setting cannot take effect without a restart"
    )


def test_the_core_route_retries_only_idempotent_transient_failures() -> None:
    """Item 60: the retry must sit inside the breaker, and must not replay real application errors."""
    for path in (EDGE, SERVED):
        route = next(row for row in _routes(path) if row["id"] == "core-api")
        filters = route["filters"]
        names = [entry["name"] for entry in filters]
        assert names == ["CircuitBreaker", "Retry"], (
            f"{path}: CircuitBreaker must be the outer filter so one caller request is one breaker "
            f"observation, however many attempts Retry makes; got {names}"
        )
        args = next(entry for entry in filters if entry["name"] == "Retry")["args"]
        assert args["retries"] == 2, f"{path}: the retry is bounded"
        assert args["series"] == [], (
            f"{path}: the stock SERVER_ERROR series would replay a 500 (a real application error) "
            f"as if it were a transient outage"
        )
        assert args["statuses"] == ["SERVICE_UNAVAILABLE", "BAD_GATEWAY"], (
            f"{path}: only the two gateway-level outage statuses are retried"
        )
        assert args["methods"] == ["GET"], f"{path}: a non-idempotent method must never be replayed"
