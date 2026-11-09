"""The core's optional announcement to a registry.

The Python process is canonical: it computes every figure and publishes every sentence about a club,
a player or a season. A registry does not change that — it only lets the edge find the core by name
instead of by an address someone typed into a file.

The whole module is off unless `EUREKA_URL` is set. That is deliberate: a developer running one
process gets no background traffic, no failed connections and no log noise, and the tests that never
set the variable prove it. When it is set, the process registers once, renews its lease on an
interval, and withdraws on shutdown. No failure in here may reach startup or shutdown — a registry
that is down is a degraded platform, not a core that refuses to boot — so every call is best-effort
and says so in the log.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

DEFAULT_APP_NAME = "FOOTBALL-CORE"
DEFAULT_RENEWAL_SECONDS = 10.0
DEFAULT_LEASE_SECONDS = 30
REQUEST_TIMEOUT_SECONDS = 3.0


def instance_id(app: str, host: str, port: int) -> str:
    """Eureka's own convention: the host, the app in lower case, and the port."""
    return f"{host}:{app.lower()}:{port}"


def instance_payload(
    *,
    app: str,
    host: str,
    port: int,
    ip: str,
    renewal_seconds: float,
    lease_seconds: int,
) -> dict[str, Any]:
    """The registration document, in the shape the real registry reads.

    `vipAddress` is lower case because that is the name a client asks for (`lb://football-core`),
    and Eureka indexes VIPs by that spelling. The URLs point at the health door on the same port,
    so a registry page answers "is it alive" with the product's own answer rather than a guess.
    """
    base = f"http://{host}:{port}"
    return {
        "instance": {
            "instanceId": instance_id(app, host, port),
            "hostName": host,
            "app": app.upper(),
            "ipAddr": ip,
            "vipAddress": app.lower(),
            "secureVipAddress": app.lower(),
            "status": "UP",
            "port": {"$": port, "@enabled": "true"},
            "securePort": {"$": port, "@enabled": "false"},
            "homePageUrl": f"{base}/",
            "statusPageUrl": f"{base}/api/v1/healthz",
            "healthCheckUrl": f"{base}/api/v1/healthz",
            "dataCenterInfo": {
                "@class": "com.netflix.appinfo.InstanceInfo$DefaultDataCenterInfo",
                "name": "MyOwn",
            },
            "leaseInfo": {
                "renewalIntervalInSecs": max(1, round(renewal_seconds)),
                "durationInSecs": lease_seconds,
            },
            "metadata": {"product": "football-os", "canonical": "true"},
        }
    }


def _resolve_ip(host: str) -> str:
    try:
        return socket.gethostbyname(host)
    except OSError:
        return "127.0.0.1"


@dataclass(frozen=True)
class DiscoverySettings:
    """What the registrar needs, built from `Settings` in one place."""

    registry_url: str
    app: str = DEFAULT_APP_NAME
    host: str = ""
    port: int = 8000
    renewal_seconds: float = DEFAULT_RENEWAL_SECONDS
    lease_seconds: int = DEFAULT_LEASE_SECONDS


class EurekaRegistrar:
    """Registers this process, renews the lease, and withdraws — best-effort throughout.

    `renewal_seconds` is a float only so a test can drive the loop in milliseconds; the registration
    document rounds it to the whole seconds Eureka expects.
    """

    def __init__(
        self,
        registry_url: str,
        *,
        app: str = DEFAULT_APP_NAME,
        host: str = "",
        port: int = 8000,
        renewal_seconds: float = DEFAULT_RENEWAL_SECONDS,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> None:
        self._registry_url = registry_url.strip()
        self._app = app.strip() or DEFAULT_APP_NAME
        self._host = host.strip() or socket.gethostname()
        self._port = port
        self._renewal_seconds = renewal_seconds
        self._lease_seconds = lease_seconds
        self._ip = _resolve_ip(self._host)
        self._client: httpx.AsyncClient | None = None
        self._renewal: asyncio.Task[None] | None = None

    @classmethod
    def from_settings(cls, settings: DiscoverySettings) -> EurekaRegistrar:
        return cls(
            settings.registry_url,
            app=settings.app,
            host=settings.host,
            port=settings.port,
            renewal_seconds=settings.renewal_seconds,
            lease_seconds=settings.lease_seconds,
        )

    @property
    def enabled(self) -> bool:
        return bool(self._registry_url)

    @property
    def running(self) -> bool:
        return self._renewal is not None

    @property
    def app_path(self) -> str:
        return f"apps/{quote(self._app.upper(), safe='')}"

    @property
    def instance_path(self) -> str:
        return f"{self.app_path}/{quote(instance_id(self._app, self._host, self._port), safe='')}"

    @property
    def payload(self) -> dict[str, Any]:
        return instance_payload(
            app=self._app,
            host=self._host,
            port=self._port,
            ip=self._ip,
            renewal_seconds=self._renewal_seconds,
            lease_seconds=self._lease_seconds,
        )

    async def start(self) -> None:
        """Announce once, then renew in the background. Never raises."""
        if not self.enabled or self._client is not None:
            return
        # The trailing slash is load-bearing: paths below are relative, and joining a leading-slash
        # path against a base URL would drop the `/eureka/` context the registry is served under.
        try:
            self._client = httpx.AsyncClient(
                base_url=self._registry_url.rstrip("/") + "/",
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except (httpx.InvalidURL, ValueError) as exc:
            # A typo in a deployment's environment is a degraded platform, not a refused boot.
            logger.error("eureka registration disabled, invalid registry url: %s", exc)
            return
        await self._register()
        self._renewal = asyncio.create_task(self._renew_forever(), name="eureka-lease-renewal")
        logger.info("eureka registration started app=%s instance=%s", self._app, instance_id(self._app, self._host, self._port))

    async def stop(self) -> None:
        """Withdraw the instance and release the client. Never raises."""
        if self._renewal is not None:
            self._renewal.cancel()
            try:
                await self._renewal
            except asyncio.CancelledError:
                pass
            self._renewal = None
        if self._client is None:
            return
        await self._request("DELETE", self.instance_path)
        await self._client.aclose()
        self._client = None
        logger.info("eureka registration withdrawn app=%s", self._app)

    async def _register(self) -> None:
        response = await self._request("POST", self.app_path, json=self.payload)
        if response is not None and response.status_code >= 300:
            logger.warning("eureka registration refused status=%s body=%s", response.status_code, response.text[:200])

    async def _renew_forever(self) -> None:
        while True:
            await asyncio.sleep(self._renewal_seconds)
            response = await self._request("PUT", self.instance_path)
            if response is not None and response.status_code == 404:
                # The registry has never heard of this instance — evicted, or restarted under us.
                # Re-announcing is cheaper and safer than waiting for a lease that no longer exists.
                logger.warning("eureka lease unknown, re-registering instance=%s", instance_id(self._app, self._host, self._port))
                await self._register()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response | None:
        if self._client is None:
            return None
        try:
            return await self._client.request(method, path, **kwargs)
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("eureka %s %s failed: %s", method, path, exc)
            return None
