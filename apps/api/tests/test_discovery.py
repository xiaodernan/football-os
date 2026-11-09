"""The core's optional announcement to the registry, driven against a real HTTP server.

The module under test is the one place where the canonical process talks to infrastructure it does
not own, so the tests read what a registry actually receives rather than what the code intended to
send. A `ThreadingHTTPServer` stands in for Eureka: it records every method, path and JSON body and
answers with the status codes the real registry uses (204 for a registration, 200 for a renewal, 404
for a lease it has never seen). Nothing here sleeps longer than a heartbeat interval scaled down to
milliseconds — `renewal_seconds` is a float for exactly this reason.

The first case is the one that matters most in daily work: with no `EUREKA_URL`, the process makes
no call at all. A registry integration that quietly phones home from every developer's laptop would
be worse than no integration.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from app.core.discovery import EurekaRegistrar, instance_id, instance_payload


class FakeRegistry:
    """Records requests and answers the way Eureka does, including one unknown lease on demand."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self.put_statuses: list[int] = []
        self._lock = threading.Lock()

    def record(self, method: str, path: str, payload: dict[str, Any] | None) -> None:
        with self._lock:
            self.calls.append((method, path, payload))

    def methods(self) -> list[str]:
        with self._lock:
            return [method for method, _, _ in self.calls]

    def first(self, method: str) -> tuple[str, dict[str, Any] | None]:
        with self._lock:
            for seen, path, payload in self.calls:
                if seen == method:
                    return path, payload
        raise AssertionError(f"no {method} was recorded")


def serve(registry: FakeRegistry) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

        def _payload(self) -> dict[str, Any] | None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            return json.loads(raw) if raw else None

        def _answer(self, status: int) -> None:
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self) -> None:
            registry.record("POST", self.path, self._payload())
            self._answer(204)

        def do_PUT(self) -> None:
            registry.record("PUT", self.path, self._payload())
            self._answer(registry.put_statuses.pop(0) if registry.put_statuses else 200)

        def do_DELETE(self) -> None:
            registry.record("DELETE", self.path, self._payload())
            self._answer(200)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


async def wait_for(registry: FakeRegistry, method: str, count: int, timeout: float = 10.0) -> None:
    """Wait for `count` calls of a method, not for a wall-clock guess.

    The first connection to a freshly started local server costs more than a lease interval on
    Windows, so a fixed sleep would be a race. This waits for the fact under test instead.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    while registry.methods().count(method) < count:
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"{method} x{count} never arrived; saw {registry.methods()}")
        await asyncio.sleep(0.02)


def test_no_registry_url_means_no_traffic_at_all() -> None:
    registrar = EurekaRegistrar("")

    async def scenario() -> None:
        await registrar.start()
        await asyncio.sleep(0.05)
        assert registrar.running is False
        await registrar.stop()

    asyncio.run(scenario())
    assert registrar.enabled is False


def test_a_malformed_registry_url_does_not_refuse_the_boot() -> None:
    registrar = EurekaRegistrar("not a url")

    async def scenario() -> None:
        await registrar.start()
        await registrar.stop()

    asyncio.run(scenario())
    assert registrar.running is False


def test_the_registration_document_is_the_shape_eureka_reads() -> None:
    payload = instance_payload(
        app="FOOTBALL-CORE",
        host="core-1",
        port=8100,
        ip="10.0.0.5",
        renewal_seconds=10,
        lease_seconds=30,
    )["instance"]

    assert payload["app"] == "FOOTBALL-CORE"
    assert payload["instanceId"] == "core-1:football-core:8100"
    # Lower case because that is the name the edge asks for: lb://football-core.
    assert payload["vipAddress"] == "football-core"
    assert payload["status"] == "UP"
    assert payload["port"] == {"$": 8100, "@enabled": "true"}
    assert payload["securePort"] == {"$": 8100, "@enabled": "false"}
    assert payload["leaseInfo"] == {"renewalIntervalInSecs": 10, "durationInSecs": 30}
    assert payload["healthCheckUrl"] == "http://core-1:8100/api/v1/healthz"
    assert payload["dataCenterInfo"]["name"] == "MyOwn"
    assert instance_id("football-core", "core-1", 8100) == "core-1:football-core:8100"


def test_the_process_registers_renews_and_withdraws() -> None:
    registry = FakeRegistry()
    server = serve(registry)
    port = server.server_address[1]
    registrar = EurekaRegistrar(
        f"http://127.0.0.1:{port}/eureka/",
        app="FOOTBALL-CORE",
        host="127.0.0.1",
        port=8100,
        renewal_seconds=0.05,
        lease_seconds=30,
    )

    async def scenario() -> None:
        await registrar.start()
        await wait_for(registry, "PUT", 2)
        await registrar.stop()

    try:
        asyncio.run(scenario())
    finally:
        server.shutdown()
        server.server_close()

    methods = registry.methods()
    assert methods[0] == "POST"
    assert "PUT" in methods
    assert methods[-1] == "DELETE"

    register_path, register_body = registry.first("POST")
    assert register_path == "/eureka/apps/FOOTBALL-CORE"
    assert register_body is not None
    assert register_body["instance"]["port"]["$"] == 8100
    assert register_body["instance"]["leaseInfo"]["renewalIntervalInSecs"] == 1

    renew_path, _ = registry.first("PUT")
    assert renew_path == f"/eureka/apps/FOOTBALL-CORE/{instance_id('FOOTBALL-CORE', '127.0.0.1', 8100).replace(':', '%3A')}"
    assert registry.first("DELETE")[0] == renew_path


def test_an_evicted_lease_is_re_announced() -> None:
    registry = FakeRegistry()
    registry.put_statuses = [404]
    server = serve(registry)
    port = server.server_address[1]
    registrar = EurekaRegistrar(
        f"http://127.0.0.1:{port}/eureka/",
        app="FOOTBALL-CORE",
        host="127.0.0.1",
        port=8100,
        renewal_seconds=0.05,
    )

    async def scenario() -> None:
        await registrar.start()
        await wait_for(registry, "POST", 2)
        await wait_for(registry, "PUT", 2)
        await registrar.stop()

    try:
        asyncio.run(scenario())
    finally:
        server.shutdown()
        server.server_close()

    methods = registry.methods()
    assert methods.count("POST") >= 2, "a 404 lease must produce a second registration"
    assert methods.count("PUT") >= 2, "renewals continue after the re-registration"


def test_a_registry_that_is_down_never_propagates() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]
    registrar = EurekaRegistrar(f"http://127.0.0.1:{closed_port}/eureka/", host="127.0.0.1", port=8100, renewal_seconds=0.05)

    async def scenario() -> None:
        await registrar.start()
        await asyncio.sleep(0.15)
        await registrar.stop()

    asyncio.run(scenario())
    assert registrar.running is False
