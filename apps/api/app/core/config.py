"""Application settings.

Read from environment (with optional .env) and expose typed values. No external
settings framework so the API surface of configuration stays explicit.
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    # A test run sets this before importing any app module. Without it, `setdefault` below re-reads a
    # developer's `.env` after `tests/conftest.py` has cleared the provider keys, and the suite's
    # verdict silently depends on whether that developer happens to have a real key configured:
    # `test_health_reports_demo_mode` passed on CI and failed on a laptop with one. A gate that reads
    # the environment it is testing is not a gate.
    if os.environ.get("FOOTBALL_OS_SKIP_DOTENV") == "1":
        return
    env_file = API_ROOT / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _demo_mode() -> bool:
    return not (_env("OPENAI_API_KEY") or _env("ANTHROPIC_API_KEY"))


@dataclass(frozen=True)
class Settings:
    env: str = field(default_factory=lambda: _env("ENV", "development"))
    app_secret: str = field(default_factory=lambda: _env("APP_SECRET", "dev-only-insecure-secret"))
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", f"sqlite:///{(API_ROOT / 'football_os.db').as_posix()}"))
    cors_origins: tuple[str, ...] = field(default_factory=lambda: tuple(o for o in _env("CORS_ORIGINS", "http://localhost:3000").split(",") if o))
    access_token_ttl_minutes: int = field(default_factory=lambda: int(_env("ACCESS_TOKEN_TTL_MINUTES", "15") or 15))
    refresh_token_ttl_days: int = field(default_factory=lambda: int(_env("REFRESH_TOKEN_TTL_DAYS", "30") or 30))
    # How long a rotated-out refresh token may still be presented, so parallel proxied requests
    # from one browser cannot sign each other out. Past it, presenting one kills every session.
    refresh_reuse_grace_seconds: int = field(default_factory=lambda: int(_env("REFRESH_REUSE_GRACE_SECONDS", "60") or 60))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: _env("OPENAI_MODEL", "gpt-4o-mini"))
    openai_base_url: str = field(default_factory=lambda: _env("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    openai_user_agent: str | None = field(default_factory=lambda: _env("OPENAI_USER_AGENT"))
    openai_embedding_model: str = field(default_factory=lambda: _env("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))
    embedding_provider: str = field(default_factory=lambda: _env("EMBEDDING_PROVIDER", "hash-local"))
    knowledge_dir: str = field(default_factory=lambda: _env("KNOWLEDGE_DIR", str(API_ROOT.parent.parent / "data" / "knowledge")))
    knowledge_auto_ingest: bool = field(default_factory=lambda: _env("KNOWLEDGE_AUTO_INGEST", "1") != "0")
    world_seed: int = field(default_factory=lambda: int(_env("WORLD_SEED", "3") or 3))
    world_auto_sync: bool = field(default_factory=lambda: _env("WORLD_AUTO_SYNC", "1") != "0")
    tactics_auto_sync: bool = field(default_factory=lambda: _env("TACTICS_AUTO_SYNC", "1") != "0")
    # M5 video: where uploads land on disk, and what may be uploaded at all (spec §5 upload
    # allow-list). The type list is checked against the file's own bytes, not its name.
    storage_dir: str = field(default_factory=lambda: _env("STORAGE_DIR", "var/storage"))
    video_max_bytes: int = field(default_factory=lambda: int(_env("VIDEO_MAX_BYTES", str(64 * 1024 * 1024))))
    video_allowed_types: tuple[str, ...] = ("video/mp4", "video/quicktime", "video/webm")
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    news_api_key: str = field(default_factory=lambda: _env("NEWS_API_KEY"))
    football_data_api_key: str = field(default_factory=lambda: _env("FOOTBALL_DATA_API_KEY"))
    ai_daily_budget_usd: float = field(default_factory=lambda: float(_env("AI_DAILY_BUDGET_USD", "5.00") or 5.0))
    # A published monthly ceiling, distinct from the daily budget: 0 means "no ceiling configured",
    # and the advisor says so rather than inventing one. Set AI_MONTHLY_CEILING_USD to publish one.
    ai_monthly_ceiling_usd: float = field(default_factory=lambda: float(_env("AI_MONTHLY_CEILING_USD", "0") or 0.0))
    # M13 item 21's out-of-band channel: a signed POST to this URL when the monthly ceiling is projected over
    # or exceeded. Empty means none is configured, and an alert is recorded in `ops_alerts` without leaving the
    # platform (a webhook configured later delivers the undelivered rows on the next sweep).
    ops_alert_webhook_url: str = field(default_factory=lambda: _env("OPS_ALERT_WEBHOOK_URL"))
    # M12 observability: keep every finished span in the database, so a request can be read back
    # without a collector. Off by default because it writes a row per span; a deployment turns it on
    # (or points OpenTelemetry at a collector and leaves this off).
    trace_store_enabled: bool = field(default_factory=lambda: _env("TRACE_STORE_ENABLED", "0") != "0")
    # Phase 11 service plane: where this process announces itself. Empty means the registry is not
    # used at all — no connection, no heartbeat, no log line. A deployment sets EUREKA_URL and the
    # edge can then route `lb://football-core` instead of a hand-written address.
    eureka_url: str = field(default_factory=lambda: _env("EUREKA_URL"))
    service_name: str = field(default_factory=lambda: _env("SERVICE_NAME", "FOOTBALL-CORE"))
    service_host: str = field(default_factory=lambda: _env("SERVICE_HOST", socket.gethostname()))
    # The port this process serves on. Uvicorn is started with a port, not with this variable, so a
    # deployment that changes one sets both; the default matches the documented dev command.
    service_port: int = field(default_factory=lambda: int(_env("SERVICE_PORT", "8000") or 8000))
    # M15 rate limiting. On everywhere but the test environment, where the suite issues thousands of
    # requests from one identity on purpose and a budget would be a test that fails for being fast.
    # The store is the cache tier's unless a deployment points the limiter at its own instance —
    # they are different workloads (an evictable cache and a stateful counter) and a host may want
    # them apart. The fallback is written here rather than left to `get_limiter`'s own default,
    # because both callers pass this field explicitly and an empty string is a value, not an absence:
    # `get_limiter("")` builds a process-only tier and never consults the environment.
    rate_limit_enabled: bool = field(default_factory=lambda: _env("RATE_LIMIT_ENABLED", "0" if _env("ENV", "development") == "test" else "1") != "0")
    rate_limit_redis_url: str = field(default_factory=lambda: _env("RATE_LIMIT_REDIS_URL") or _env("REDIS_URL"))
    # Only a peer inside one of these networks may name the caller in `X-Forwarded-For`. The default
    # is the loopback pair, which is where this project's own edge and web tier run; a deployment
    # behind another proxy adds that proxy's network, and a deployment behind none leaves it empty.
    rate_limit_trusted_proxies: tuple[str, ...] = field(default_factory=lambda: tuple(p for p in _env("RATE_LIMIT_TRUSTED_PROXIES", "127.0.0.1/32,::1/128").split(",") if p))

    @property
    def is_demo_mode(self) -> bool:
        return _demo_mode()

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"prod", "production"}

    def validate_for_boot(self) -> list[str]:
        """Return human-readable capability/warning notes surfaced via /healthz."""
        notes: list[str] = []
        if self.is_production and self.app_secret == "dev-only-insecure-secret":
            raise RuntimeError("APP_SECRET must be set in production")
        if self.database_url.startswith("sqlite"):
            notes.append("sqlite-fallback: pgvector features require PostgreSQL")
        if self.is_demo_mode:
            notes.append("DEMO MODE: no AI provider key configured, outputs are template-reasoned and labelled")
        if not self.world_auto_sync:
            notes.append("world-auto-sync-disabled: /api/v1/world serves whatever is already in the database")
        if not self.tactics_auto_sync:
            notes.append("tactics-auto-sync-disabled: /api/v1/tactics serves whatever is already in the database")
        return notes


_load_dotenv()
settings = Settings()
