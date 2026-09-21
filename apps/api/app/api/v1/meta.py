"""Meta endpoints: health, capabilities, provider status (spec §59)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db, has_pgvector
from app.providers import provider_status
from app.services.world import world_counts, world_ready, world_tables_present

router = APIRouter(tags=["meta"])


@router.get("/healthz")
def healthz(db: Session = Depends(get_db)) -> dict[str, object]:
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "environment": settings.env,
        "database_dialect": db.bind.dialect.name if db.bind else "unknown",
        "pgvector": has_pgvector(db),
        "providers": provider_status(),
        "notes": settings.validate_for_boot(),
    }


@router.get("/capabilities")
def capabilities(db: Session = Depends(get_db)) -> dict[str, object]:
    """Which milestones are live — the UI uses this instead of guessing.

    M3 reports what the database actually holds rather than what the code could serve: the flag
    flips to true only once the synthetic world is present in full, because a half-written world
    must not be rendered as if it were real (spec §65, `DATA_POLICY.md`). `locales` likewise lists
    only the language the UI ships today; §81 translations are `locales_planned`.
    """
    return {
        "m0_foundation": True,
        "m1_player_ai_coach": True,
        "m2_rag": True,
        "m3_football_world": world_ready(db),
        "m3_world": {"tables_present": world_tables_present(db), "counts": world_counts(db), "auto_sync": settings.world_auto_sync, "seed": settings.world_seed},
        "m4_tactical_lab": False,
        "m5_video_analysis": False,
        "m6_simulation": False,
        "m7_scouting": False,
        "m8_club_os": False,
        "m9_community": False,
        "locales": ["en"],
        "locales_planned": ["en", "zh", "zh-TW"],
        "demo_mode": settings.is_demo_mode,
    }
