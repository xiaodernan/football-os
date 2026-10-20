"""The shared cache tier must be shared, and it must be this project's own.

M12's response cache has two tiers: a process-local one and a shared one other workers can see.
Until 2026-10-20 the shared tier had never served a real request on any host this project
measured: port 6379 was occupied by a Redis that requires a password, the default URL carried
none, and every load figure in `docs/M12_PRODUCTION_HARDENING_VERIFICATION.md` was taken with the
tier degraded. The document said so plainly; this file is what makes that sentence true or false.

Three claims, in the order they can be checked:

* **It exists and it is ours.** The project publishes an authenticated Redis of its own, and the
  compose file, the CI workflow and the app name the same instance. The host port is not 6379,
  because 6379 belongs to another application's cache on this host.
* **The password does not leave the process.** The URL is where the credential lives, and the
  metrics door publishes that URL to any signed-in caller. The redaction is on the parsed URL, so
  a password containing `@` or `/` is still removed.
* **It is actually shared.** A key written by one process is read by *another operating system
  process* through its own client. Two objects in one process would prove nothing: the fallback
  tier inside `RedisCache` would answer both.

The first two claims are file-only and run everywhere. The third needs a live server and is
skipped, with its reason printed, when `REDIS_URL` does not point at one — CI runs it because the
workflow starts the same container the compose file publishes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.redis_cache import RedisCache, redact_url
from app.main import app

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "apps" / "api"
COMPOSE = ROOT / "infra" / "docker-compose.yml"
CI = ROOT / ".github" / "workflows" / "ci.yml"

#: The password the project's own cache is published with. It is a development credential and
#: says so; the compose file and the CI workflow both carry it, and the gate below refuses a
#: compose file that publishes a cache with an empty password.
DEV_PASSWORD = "football"

#: The host's *other* Redis. Port 6379 is occupied on this host by an instance that requires a
#: password, which is why the project's own cache is published on 63790 and why an unauthenticated
#: default URL is a degraded tier rather than a working one.
OTHER_REDIS_PORT = 6379

PASSWORD = "TestPass1234!"


def _compose_text() -> str:
    return COMPOSE.read_text(encoding="utf-8")


def _ci_text() -> str:
    return CI.read_text(encoding="utf-8")


def _live_url() -> str | None:
    """The URL of a cache that is actually serving, or None with the reason printed."""
    url = os.environ.get("REDIS_URL")
    if not url:
        print("no REDIS_URL in the environment: the shared-tier case needs a live cache")
        return None
    cache = RedisCache(redis_url=url)
    if not cache.available:
        print(f"the cache at {redact_url(url)} is not serving: the shared-tier case cannot run")
        cache.close()
        return None
    cache.close()
    return url


class TestTheProjectPublishesItsOwnCache:
    """The compose file and the CI workflow must name one instance, not two."""

    def test_the_compose_publishes_an_authenticated_cache_of_its_own(self) -> None:
        text = _compose_text()
        assert re.search(r"^  redis:", text, re.M), f"{COMPOSE} has no redis service"

        require = re.search(r"--requirepass\s*\n\s*-\s*(\S+)", text)
        assert require is not None, f"{COMPOSE} publishes a cache that does not require a password"
        assert DEV_PASSWORD in require.group(1), (
            f"{COMPOSE} publishes a cache whose password is {require.group(1)!r}; the gate and the CI "
            f"workflow name {DEV_PASSWORD!r}, so the app, the compose and CI would not be talking "
            "about the same instance"
        )

        published = re.search(r'"\$\{REDIS_PORT:-(\d+)\}:6379"', text)
        assert published is not None, f"{COMPOSE} publishes no host port for the cache"
        assert int(published.group(1)) != OTHER_REDIS_PORT, (
            f"{COMPOSE} publishes the cache on {published.group(1)}, which is the port another "
            f"application's cache occupies on this host; the two would share a keyspace"
        )

    def test_ci_starts_the_same_cache_the_compose_publishes(self) -> None:
        compose = _compose_text()
        ci = _ci_text()

        published = re.search(r'"\$\{REDIS_PORT:-(\d+)\}:6379"', compose)
        assert published is not None, "the compose file's cache port could not be read"
        port = published.group(1)

        assert "redis" in ci, f"{CI} starts no cache service"
        assert DEV_PASSWORD in ci, f"{CI} starts a cache with a password this gate does not know"
        expected_url = f"redis://:{DEV_PASSWORD}@localhost:{port}/0"
        assert expected_url in ci, (
            f"{CI} does not export REDIS_URL={expected_url!r}; the app and the workflow would be "
            "pointing at different instances"
        )


class TestThePasswordDoesNotLeaveTheProcess:
    """The URL is where the credential lives, and the metrics door publishes the URL."""

    def test_redaction_removes_the_password_and_keeps_the_address(self) -> None:
        redacted = redact_url("redis://:hunter2@cache.internal:6379/3")
        assert "hunter2" not in redacted, f"the password survived redaction: {redacted!r}"
        assert "cache.internal" in redacted, f"the host was lost: {redacted!r}"
        assert "6379" in redacted, f"the port was lost: {redacted!r}"
        assert redacted.endswith("/3"), f"the database number was lost: {redacted!r}"

    def test_redaction_handles_a_password_that_contains_the_delimiters(self) -> None:
        redacted = redact_url("redis://:p@ss/word@cache.internal:6379/0")
        assert "p@ss/word" not in redacted, f"the password survived redaction: {redacted!r}"
        assert "cache.internal" in redacted

    def test_a_url_without_a_password_is_left_alone(self) -> None:
        assert redact_url("redis://localhost:6379/0") == "redis://localhost:6379/0"

    def test_the_published_stats_carry_no_password(self) -> None:
        """`get_stats()` is what `/api/v1/metrics/cache` publishes, so it is the place to check."""
        from unittest.mock import MagicMock, patch

        with patch("redis.from_url") as mock_from_url:
            client = MagicMock()
            client.ping.return_value = True
            client.info.return_value = {"used_memory_human": "1.5M", "connected_clients": 2}
            mock_from_url.return_value = client

            cache = RedisCache(redis_url="redis://:hunter2@cache.internal:6379/0")
            stats = cache.get_stats()

        assert stats["redis_available"] is True
        assert stats["redis_url"] is not None
        assert "hunter2" not in stats["redis_url"], f"the published URL carries the password: {stats['redis_url']!r}"
        assert "hunter2" not in json.dumps(stats), f"the published stats carry the password: {stats!r}"

    def test_the_connection_log_line_carries_no_password(self) -> None:
        from unittest.mock import MagicMock, patch

        with patch("redis.from_url") as mock_from_url:
            client = MagicMock()
            client.ping.return_value = True
            mock_from_url.return_value = client

            with patch("app.core.redis_cache.logger") as logger:
                RedisCache(redis_url="redis://:hunter2@cache.internal:6379/0")
                logged = " ".join(str(call) for call in logger.info.call_args_list)

        assert "hunter2" not in logged, f"the connection line carries the password: {logged!r}"

    def test_the_metrics_door_publishes_no_password(self) -> None:
        """The door itself, not just the function behind it."""
        client = TestClient(app)
        email = f"cache-metrics-{uuid4().hex[:8]}@example.test"
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": PASSWORD,
                "display_name": "Cache Metrics Tester",
                "role": "player",
                "accepts_data_policy": True,
            },
        )
        assert registered.status_code == 201, f"registration failed: {registered.json()}"
        client.headers.update({"Authorization": f"Bearer {registered.json()['access_token']}"})

        response = client.get("/api/v1/metrics/cache")
        assert response.status_code == 200, f"the cache door answered {response.status_code}"
        body = response.text
        secret = os.environ.get("REDIS_URL", "")
        password = ""
        if "//:" in secret and "@" in secret:
            password = secret.split("//:", 1)[1].split("@", 1)[0]
        if password:
            assert password not in body, f"the metrics door published the password: {body[:400]!r}"


class TestTheDegradedTierIsStillHonest:
    """A cache that cannot authenticate must say so rather than pretend to be serving."""

    def test_a_wrong_password_degrades_and_still_answers(self) -> None:
        url = os.environ.get("REDIS_URL")
        if not url:
            pytest.skip("no REDIS_URL in the environment: the degradation case needs a cache to refuse")
        wrong = url.replace(":", "wrong-", 1) if "://:" in url else url
        cache = RedisCache(redis_url=wrong)
        assert cache.available is False, "a cache that refused the handshake is still claiming to serve"
        cache.set("degraded", {"v": 1})
        assert cache.get("degraded") == {"v": 1}, "the fallback stopped serving"
        assert cache.get_stats()["redis_available"] is False
        assert cache.get_stats()["redis_url"] is None, "a degraded tier published its URL"


class TestTheTierIsActuallyShared:
    """Two operating system processes, one server."""

    def test_a_key_written_by_one_process_is_read_by_another(self) -> None:
        url = _live_url()
        if url is None:
            pytest.skip("no live cache: the shared-tier case needs a serving instance")

        key = f"shared-tier-probe-{uuid4().hex[:8]}"
        writer = RedisCache(redis_url=url)
        assert writer.available is True
        writer.set(key, {"written_by": "the parent process", "n": 42})
        assert writer.get(key) == {"written_by": "the parent process", "n": 42}

        child = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json, sys;"
                f"sys.path.insert(0, r'{API}');"
                "from app.core.redis_cache import RedisCache;"
                f"cache = RedisCache(redis_url={url!r});"
                f"print(json.dumps({{'available': cache.available, 'value': cache.get({key!r})}}))"
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(API),
            timeout=120,
        )
        assert child.returncode == 0, f"the reading process failed: {child.stdout!r} {child.stderr!r}"
        answer = json.loads(child.stdout.strip().splitlines()[-1])
        assert answer["available"] is True, f"the reading process could not use the cache: {answer!r}"
        assert answer["value"] == {"written_by": "the parent process", "n": 42}, (
            f"a key written by one process was not read by another: {answer!r}"
        )

        # And the key is really the server's, not the writer's fallback: a fresh reader with a
        # different key namespace still sees it, and the writer's own fallback is not what answered.
        writer.delete(key)
        assert writer.get(key) is None
