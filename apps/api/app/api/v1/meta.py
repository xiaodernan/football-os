"""Meta endpoints: health, capabilities, provider status (spec §59)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db, has_pgvector
from app.providers import provider_status
from app.services.scouting.requirements import SCOUT_DISCLAIMER, vocabulary_problems
from app.services.scouting.search import scout_counts, scout_ready, search_problems
from app.services.simulation.challenges import CHALLENGE_DISCLAIMER, challenge_counts, challenge_ready
from app.services.simulation.service import engine_description, sim_counts, sim_ready, sim_tables_present
from app.services.tactics.sync import TACTICS_GATE, tactics_counts, tactics_ready, tactics_tables_present
from app.services.video.status import video_readiness
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
    video = video_readiness(db)
    engine = engine_description()
    return {
        "m0_foundation": True,
        "m1_player_ai_coach": True,
        "m2_rag": True,
        "m3_football_world": world_ready(db),
        "m3_world": {"tables_present": world_tables_present(db), "counts": world_counts(db), "auto_sync": settings.world_auto_sync, "seed": settings.world_seed},
        # M4 is data-derived for the same reason M3 is: 49 of the 50 authored systems is not a
        # Tactical Lab, and a flag that lied would let the UI advertise a route that 404s.
        "m4_tactical_lab": tactics_ready(db),
        "m4_tactics": {"tables_present": tactics_tables_present(db), "counts": tactics_counts(db), "gate": dict(TACTICS_GATE), "auto_sync": settings.tactics_auto_sync},
        "m5_video_analysis": video["ready"],
        "m5_video": video,
        # M6 reports the same way M3 and M4 do: the flag is whether the feature can serve, and the
        # counts beside it say how much of it has been used. A simulation is always fiction, so the
        # engine's own disclaimer travels with the flag rather than living in the UI's strings.
        "m6_simulation": sim_ready(db),
        "m6_simulation_engine": {
            "tables_present": sim_tables_present(db),
            "counts": sim_counts(db),
            "model": engine["name"],
            "model_version": engine["version"],
            "disclaimer": engine["disclaimer"],
        },
        # §21 reports like the rest: the flag is whether the catalogue is sound, the run columns exist
        # and the world is there to choose a club from — not whether anyone has started a run.
        "m6_manager_challenges": challenge_ready(db),
        "m6_challenges": {"counts": challenge_counts(db), "disclaimer": CHALLENGE_DISCLAIMER},
        # §23 reports the way §21 does: the flag is whether the vocabulary agrees with itself and the search
        # can answer every requirement kind the parser emits — not whether anyone has run a search.
        "m7_scouting": scout_ready(db),
        "m7_scout": {
            "counts": scout_counts(db),
            "problems": [*vocabulary_problems(), *search_problems(db)],
            "disclaimer": SCOUT_DISCLAIMER,
        },
        "m8_club_os": False,
        "m9_community": False,
        "locales": ["en"],
        "locales_planned": ["en", "zh", "zh-TW"],
        "demo_mode": settings.is_demo_mode,
    }
