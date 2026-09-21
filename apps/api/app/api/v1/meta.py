"""Meta endpoints: health, capabilities, provider status (spec §59)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db, has_pgvector
from app.providers import provider_status

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
def capabilities() -> dict[str, object]:
    """Which milestones are live — the UI uses this instead of guessing."""
    return {
        "m0_foundation": True,
        "m1_player_ai_coach": True,
        "m2_rag": False,
        "m3_football_world": False,
        "m4_tactical_lab": False,
        "m5_video_analysis": False,
        "m6_simulation": False,
        "m7_scouting": False,
        "m8_club_os": False,
        "m9_community": False,
        "locales": ["en", "zh", "zh-TW"],
        "demo_mode": settings.is_demo_mode,
    }
