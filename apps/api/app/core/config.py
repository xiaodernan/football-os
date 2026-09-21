"""Application settings.

Read from environment (with optional .env) and expose typed values. No external
settings framework so the API surface of configuration stays explicit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
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
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: _env("OPENAI_MODEL", "gpt-4o-mini"))
    openai_embedding_model: str = field(default_factory=lambda: _env("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))
    embedding_provider: str = field(default_factory=lambda: _env("EMBEDDING_PROVIDER", "hash-local"))
    knowledge_dir: str = field(default_factory=lambda: _env("KNOWLEDGE_DIR", str(API_ROOT.parent.parent / "data" / "knowledge")))
    knowledge_auto_ingest: bool = field(default_factory=lambda: _env("KNOWLEDGE_AUTO_INGEST", "1") != "0")
    world_seed: int = field(default_factory=lambda: int(_env("WORLD_SEED", "3") or 3))
    world_auto_sync: bool = field(default_factory=lambda: _env("WORLD_AUTO_SYNC", "1") != "0")
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    news_api_key: str = field(default_factory=lambda: _env("NEWS_API_KEY"))
    football_data_api_key: str = field(default_factory=lambda: _env("FOOTBALL_DATA_API_KEY"))
    ai_daily_budget_usd: float = field(default_factory=lambda: float(_env("AI_DAILY_BUDGET_USD", "5.00") or 5.0))

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
        return notes


_load_dotenv()
settings = Settings()
