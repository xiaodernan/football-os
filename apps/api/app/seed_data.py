"""Seed helpers shared by the CLI and the tests."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, new_public_id
from app.models import User, UserPlayer, utc_today
from app.services.attributes import derive_archetype, derive_baseline
from app.services.progression import refresh_derived_state
from app.services.training_catalog import sync_catalog


def seed_catalogue(db: Session) -> int:
    return sync_catalog(db)


def ensure_demo_account(db: Session, *, email: str, password: str) -> UserPlayer:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        user = User(
            id=new_public_id("usr"),
            email=email.lower(),
            password_hash=hash_password(password),
            display_name="Demo Analyst",
            role="player",
        )
        db.add(user)
        db.commit()
    existing = db.scalar(select(UserPlayer).where(UserPlayer.user_id == user.id))
    if existing is not None:
        return existing
    baseline = derive_baseline(position="CM", age=24, level="intermediate", preferred_foot="right", height_cm=178)
    attributes = dict(baseline.attributes)
    archetype, match, arch_reasons = derive_archetype("CM", attributes)
    reasons = ["DEMO PLAYER — generated from the synthetic baseline, not a real athlete", *baseline.reasons, *arch_reasons]
    player = UserPlayer(
        id=new_public_id("ply"),
        user_id=user.id,
        name="Demo Midfielder",
        position="CM",
        age=24,
        level="intermediate",
        preferred_foot="right",
        height_cm=178,
        goal="become_box_to_box",
        attributes=attributes,
        derivation_reasons=reasons,
        archetype=archetype,
        archetype_match=match,
        is_demo_data=True,
        data_origin="synthetic",
        xp=0,
    )
    refresh_derived_state(player)
    db.add(player)
    db.commit()
    return player


def today_str() -> str:
    return utc_today().isoformat()
