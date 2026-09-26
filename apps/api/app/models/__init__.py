"""Football World entities (spec §4–§7, §10–§11, §42, §47, §59).

Portable column types only so the same models run on PostgreSQL (+pgvector later)
and the SQLite dev fallback (ADR-002).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.vector_type import EMBEDDING_DIM, EmbeddingVector

ATTRIBUTES: dict[str, tuple[str, ...]] = {
    "technical": ("ball_control", "first_touch", "passing", "long_passing", "dribbling", "finishing", "crossing", "heading", "tackling"),
    "physical": ("acceleration", "speed", "agility", "balance", "stamina", "strength"),
    "mental": ("vision", "decision_making", "positioning", "scanning", "composure", "anticipation"),
    "tactical": ("pressing", "build_up", "off_ball_movement", "defensive_awareness", "space_occupation", "transition"),
}
ALL_ATTRIBUTES: tuple[str, ...] = tuple(v for group in ATTRIBUTES.values() for v in group)

POSITIONS = ("GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "ST", "CF")
PREFERRED_FEET = ("left", "right", "both")
LEVELS = ("beginner", "intermediate", "advanced", "elite")
GOALS = (
    "improve_first_touch",
    "improve_passing",
    "improve_dribbling",
    "improve_finishing",
    "improve_defending",
    "improve_pressing",
    "improve_weak_foot",
    "improve_fitness",
    "improve_vision",
    "become_box_to_box",
    "become_playmaker",
    "become_inverted_winger",
)
SESSION_STATUSES = ("planned", "in_progress", "completed", "skipped")
JOB_STATUSES = ("QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "RETRYING")
DATA_ORIGINS = ("synthetic", "licensed", "open", "user", "project-authored")


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class User(TimestampMixin, Base):
    """Account + role. RBAC roles per spec §2; organisation reserved for B2B §41."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(400), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="player", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_minor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parental_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    organization_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    plan: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    locale: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_anchor_date: Mapped[str | None] = mapped_column(String(10), nullable=True)

    players: Mapped[list[UserPlayer]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[list[TrainingSession]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserPlayer(TimestampMixin, Base):
    """The user's own football identity — strictly separate from RealPlayer (spec §7)."""

    __tablename__ = "user_players"
    __table_args__ = (Index("ix_user_players_user", "user_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    position: Mapped[str] = mapped_column(String(8), nullable=False)
    secondary_positions: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_foot: Mapped[str] = mapped_column(String(8), default="right", nullable=False)
    weak_foot_rating: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[str] = mapped_column(String(20), default="beginner", nullable=False)
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goal: Mapped[str] = mapped_column(String(40), default="improve_first_touch", nullable=False)
    attributes: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    derivation_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    overall: Mapped[int] = mapped_column(Integer, default=40, nullable=False)
    potential: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    form: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    archetype: Mapped[str] = mapped_column(String(60), default="Developing Player", nullable=False)
    archetype_match: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    style: Mapped[str] = mapped_column(String(60), default="unknown", nullable=False)
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    visibility: Mapped[str] = mapped_column(String(12), default="private", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(12), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="players")


class TrainingDrill(Base, TimestampMixin):
    """Training Academy catalogue item — full field set from spec §10."""

    __tablename__ = "training_drills"
    __table_args__ = (UniqueConstraint("slug", name="uq_drill_slug"), Index("ix_drill_category", "category"))

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    equipment: Mapped[list[str]] = mapped_column(JSON, default=list)
    needs_pitch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    setup: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[list[str]] = mapped_column(JSON, default=list)
    coaching_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    common_mistakes: Mapped[list[str]] = mapped_column(JSON, default=list)
    progressions: Mapped[list[str]] = mapped_column(JSON, default=list)
    regression: Mapped[str] = mapped_column(Text, default="", nullable=False)
    test_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    test_target: Mapped[str] = mapped_column(Text, default="", nullable=False)
    target_attributes: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    positions: Mapped[list[str]] = mapped_column(JSON, default=list)
    min_age_safe: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    xp_base: Mapped[int] = mapped_column(Integer, default=40, nullable=False)
    video_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    data_origin: Mapped[str] = mapped_column(String(12), default="synthetic", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TrainingSession(Base, TimestampMixin):
    """A planned or completed training instance for one UserPlayer."""

    __tablename__ = "training_sessions"
    __table_args__ = (Index("ix_sessions_user_date", "user_id", "planned_date"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("user_players.id", ondelete="CASCADE"), nullable=False)
    drill_id: Mapped[str] = mapped_column(ForeignKey("training_drills.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="planned", nullable=False)
    planned_date: Mapped[str] = mapped_column(String(10), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    focus_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    difficulty_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    self_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    demo_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    recommendation_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)

    user: Mapped[User] = relationship(back_populates="sessions")
    drill: Mapped[TrainingDrill] = relationship()


class XpEvent(Base):
    """Every point awarded is explainable: formula + reason + evidence (spec §8)."""

    __tablename__ = "xp_events"
    __table_args__ = (Index("ix_xp_user_created", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("user_players.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(160), nullable=False)
    formula: Mapped[str] = mapped_column(String(240), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), default="training_session", nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AttributeChange(Base):
    __tablename__ = "attribute_changes"
    __table_args__ = (Index("ix_attr_player_created", "player_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("user_players.id", ondelete="CASCADE"), nullable=False)
    attribute: Mapped[str] = mapped_column(String(40), nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    before: Mapped[int] = mapped_column(Integer, nullable=False)
    after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CoachMessage(Base):
    """AI Coach conversation + long-term coach memory (spec §9, §34)."""

    __tablename__ = "coach_messages"
    __table_args__ = (Index("ix_coach_user_created", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    role: Mapped[str] = mapped_column(String(12), default="coach", nullable=False)
    kind: Mapped[str] = mapped_column(String(40), default="chat", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(30), default="mock", nullable=False)
    model: Mapped[str] = mapped_column(String(60), default="rule-engine-demo", nullable=False)
    demo_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TrainingPlan(Base, TimestampMixin):
    __tablename__ = "training_plans"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("user_players.id", ondelete="CASCADE"), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    goal: Mapped[str] = mapped_column(String(40), nullable=False)
    days: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    demo_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list)


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    criterion: Mapped[str] = mapped_column(String(60), nullable=False)


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    achievement_id: Mapped[str] = mapped_column(ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Job(Base):
    """Async job state machine (spec §47, ADR-006)."""

    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class ModelCall(Base):
    """Provider/token/cost ledger (spec §46, §59, §76)."""

    __tablename__ = "model_calls"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    feature: Mapped[str] = mapped_column(String(60), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    actual_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    demo_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Entitlement(Base):
    """Feature/plan/limit matrix as data — no payment vendor needed (spec §42)."""

    __tablename__ = "entitlements"
    __table_args__ = (UniqueConstraint("feature", "plan", name="uq_feature_plan"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    feature: Mapped[str] = mapped_column(String(60), nullable=False)
    plan: Mapped[str] = mapped_column(String(20), nullable=False)
    limit_value: Mapped[int] = mapped_column(Integer, nullable=False)
    period: Mapped[str] = mapped_column(String(20), default="day", nullable=False)


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(60), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# --- Football World (M3) ---------------------------------------------------------------
# Everything below is generated by `app.services.world` from a fixed seed: fictional
# identities, no real person/club/competition/match, and every row keeps its provenance
# (`data_origin='synthetic'`, `is_demo_data=True`) so no surface can present it as fact.
class Competition(Base, TimestampMixin):
    """League or cup inside the generated world (spec §4 'Competition', §65)."""

    __tablename__ = "competitions"
    __table_args__ = (Index("ix_competition_kind", "kind"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    country: Mapped[str] = mapped_column(String(80), default="Generated World", nullable=False)
    kind: Mapped[str] = mapped_column(String(12), default="league", nullable=False)
    tier: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    region: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    season: Mapped[str] = mapped_column(String(12), default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(12), default="synthetic", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    teams: Mapped[list[Team]] = relationship(back_populates="competition")


class Team(Base, TimestampMixin):
    """A fictional club: identity, ground, bench and the competition it is registered in (spec §4)."""

    __tablename__ = "teams"
    __table_args__ = (Index("ix_team_competition", "competition_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    competition_id: Mapped[str | None] = mapped_column(ForeignKey("competitions.id", ondelete="CASCADE"), nullable=True)
    logo_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    short_name: Mapped[str] = mapped_column(String(24), default="", nullable=False)
    city: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    stadium: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    manager_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    formation: Mapped[str] = mapped_column(String(8), default="4-4-2", nullable=False)
    brand_color: Mapped[str] = mapped_column(String(9), default="#1f6f5c", nullable=False)
    nation: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    season: Mapped[str] = mapped_column(String(12), default="", nullable=False)
    squad_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overall: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(12), default="synthetic", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    competition: Mapped[Competition | None] = relationship(back_populates="teams")
    players: Mapped[list[RealPlayer]] = relationship(back_populates="team")


class RealPlayer(Base, TimestampMixin):
    """A generated footballer in the synthetic world — strictly separate from `UserPlayer` (spec §7)."""

    __tablename__ = "real_players"
    __table_args__ = (
        Index("ix_real_player_team", "team_id"),
        Index("ix_real_player_position_overall", "position", "overall"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    position: Mapped[str] = mapped_column(String(8), nullable=False)
    secondary_positions: Mapped[list[str]] = mapped_column(JSON, default=list)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    preferred_foot: Mapped[str] = mapped_column(String(8), default="right", nullable=False)
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nation: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)
    season: Mapped[str] = mapped_column(String(12), default="", nullable=False)
    attributes: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    derivation_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    overall: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    potential: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    archetype: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    archetype_match: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    appearances: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    starts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    goals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assists: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clean_sheets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    yellow_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    red_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    form: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(12), default="synthetic", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    team: Mapped[Team | None] = relationship(back_populates="players")


class RealMatch(Base, TimestampMixin):
    """A fixture in the generated world. `status='scheduled'` rows carry no score or stat lines."""

    __tablename__ = "real_matches"
    __table_args__ = (
        Index("ix_match_competition_season", "competition_id", "season"),
        Index("ix_match_kickoff", "kickoff_at"),
        Index("ix_match_home_team", "home_team_id"),
        Index("ix_match_away_team", "away_team_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    season: Mapped[str] = mapped_column(String(12), nullable=False)
    competition_id: Mapped[str | None] = mapped_column(ForeignKey("competitions.id", ondelete="CASCADE"), nullable=True)
    home_team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    away_team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    round_label: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    kickoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    venue_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    venue_city: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="scheduled", nullable=False)
    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    haystack: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(12), default="synthetic", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    competition: Mapped[Competition | None] = relationship()
    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id])
    stat_lines: Mapped[list[RealPlayerMatchStat]] = relationship(back_populates="match", cascade="all, delete-orphan", order_by="RealPlayerMatchStat.minute_rank")


class RealPlayerMatchStat(TimestampMixin, Base):
    """One player's generated stat line for one match — the source every season total rolls up from."""

    __tablename__ = "real_player_match_stats"
    __table_args__ = (
        UniqueConstraint("match_id", "player_id", name="uq_match_stat_line"),
        UniqueConstraint("natural_key", name="uq_match_stat_natural_key"),
        Index("ix_stat_line_player", "player_id"),
        Index("ix_stat_line_match", "match_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    natural_key: Mapped[str] = mapped_column(String(200), nullable=False)
    match_id: Mapped[str] = mapped_column(ForeignKey("real_matches.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("real_players.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(12), default="starter", nullable=False)
    position: Mapped[str] = mapped_column(String(8), default="", nullable=False)
    minute_rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    goals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assists: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shots: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shots_on_target: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passes_accurate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    key_passes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tackles: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    interceptions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duels_won: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    saves: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fouls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    yellow_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    red_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(12), default="synthetic", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    match: Mapped[RealMatch] = relationship(back_populates="stat_lines")
    player: Mapped[RealPlayer] = relationship()
    team: Mapped[Team] = relationship()


class RealTrainingSession(TimestampMixin, Base):
    """A training session inside the generated world (spec §65 gate: 100 of them).

    Kept apart from ``TrainingSession`` on purpose: that table is a real person's own log, with
    export and erasure semantics attached, while these rows are demo history belonging to synthetic
    players. The catalogue is referenced by ``drill_slug`` rather than a FK because the world plan is
    built in memory from ``training_catalog.DRILLS`` and must not depend on the catalogue already
    having been synced — a test asserts every slug resolves.
    """

    __tablename__ = "real_training_sessions"
    __table_args__ = (
        UniqueConstraint("natural_key", name="uq_world_training_natural_key"),
        Index("ix_world_training_player_date", "player_id", "session_date"),
        Index("ix_world_training_team", "team_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    natural_key: Mapped[str] = mapped_column(String(200), nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("real_players.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    player_slug: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    player_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    position: Mapped[str] = mapped_column(String(8), default="", nullable=False)
    season: Mapped[str] = mapped_column(String(12), default="", nullable=False)
    session_date: Mapped[str] = mapped_column(String(10), nullable=False)
    drill_slug: Mapped[str] = mapped_column(String(140), nullable=False)
    drill_title: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rpe: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    load_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="completed", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(12), default="synthetic", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    player: Mapped[RealPlayer] = relationship()
    team: Mapped[Team] = relationship()


class NewsArticle(Base, TimestampMixin):
    """A generated news item: template prose over generated rows, never a real-world claim (spec §25)."""

    __tablename__ = "news_articles"
    __table_args__ = (Index("ix_news_category_published", "category", "published_at"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    claim_class: Mapped[str] = mapped_column(String(16), default="fact", nullable=False)
    season: Mapped[str] = mapped_column(String(12), default="", nullable=False)
    source_name: Mapped[str] = mapped_column(String(120), default="synthetic-world", nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    author: Mapped[str | None] = mapped_column(String(120), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entities: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    haystack: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(12), default="synthetic", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    links: Mapped[list[NewsArticleLink]] = relationship(back_populates="article", cascade="all, delete-orphan")


class NewsArticleLink(Base):
    """Typed entity edge from an article to a world entity — the §4 'entities must relate' rule."""

    __tablename__ = "news_article_links"
    __table_args__ = (
        UniqueConstraint("article_id", "entity_type", "entity_slug", name="uq_news_article_link"),
        Index("ix_news_link_entity", "entity_type", "entity_slug"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    article_id: Mapped[str] = mapped_column(ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_slug: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data_origin: Mapped[str] = mapped_column(String(12), default="synthetic", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    article: Mapped[NewsArticle] = relationship(back_populates="links")


class KnowledgeDocument(Base, TimestampMixin):
    """One ingested knowledge source (spec §28-§29).

    `data_origin='project-authored'` marks content this project wrote itself: it is real
    editorial content, not DEMO DATA, and it is not a licensed third-party feed.
    """

    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    applies_to: Mapped[list[str]] = mapped_column(JSON, default=list)
    difficulty: Mapped[str] = mapped_column(String(20), default="intermediate", nullable=False)
    source_label: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    editorial_confidence: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    last_reviewed: Mapped[str] = mapped_column(String(10), default="", nullable=False)
    source_path: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="project-authored", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chunks: Mapped[list[KnowledgeChunk]] = relationship(back_populates="document", cascade="all, delete-orphan", order_by="KnowledgeChunk.ordinal")


class KnowledgeChunk(Base, TimestampMixin):
    """A retrievable slice of a document: the unit a citation points at."""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_chunk_document_ordinal"),
        Index("ix_chunk_category_ordinal", "category", "ordinal"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    haystack: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    applies_to: Mapped[list[str]] = mapped_column(JSON, default=list)
    difficulty: Mapped[str] = mapped_column(String(20), default="intermediate", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    terms: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    embedding: Mapped[list[float]] = mapped_column(EmbeddingVector(EMBEDDING_DIM), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")


class KnowledgeQuery(Base):
    """What was asked, what was retrieved and whether it was answered — the RAG audit trail."""

    __tablename__ = "knowledge_queries"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(12), default="hybrid", nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    hit_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    hit_scores: Mapped[list[float]] = mapped_column(JSON, default=list)
    answered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    retrieval_backend: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


WORLD_DISCLAIMER = (
    "Football World rows are synthetic demo data: every club, player, fixture, statistic and article in these "
    "tables is generated locally from a fixed seed. They describe no real person, club, competition or match, "
    "and no figure here is a measurement of the real world."
)


TACTICS_DISCLAIMER = (
    "Tactical systems are project-authored coaching structures. The coordinates are written by this repository and "
    "every width, spacing and separation figure is measured from them; nothing here records how a real team played, "
    "and there is no tracking data or provider call behind any number."
)


# --- Tactical Lab (M4) -------------------------------------------------------------------
# Written only by `app.services.tactics.sync`. These rows are project-authored rather than
# synthetic demo data: the shapes are a design artefact of this repository, so `is_demo_data`
# is False and `data_origin` says "project-authored" — the same distinction the M2 knowledge
# corpus draws. The measured numbers live in `board` because they are the *output* of the plan,
# stored verbatim so the API serves exactly what was computed; everything a browse path filters
# or orders by is a real column.
class TacticalSystem(Base, TimestampMixin):
    """One of the 50 tactical systems: a shape, a temperament, and what the geometry measures (spec §11–§13, §65)."""

    __tablename__ = "tactical_systems"
    __table_args__ = (
        Index("ix_tactics_formation", "formation"),
        Index("ix_tactics_temperament", "temperament_key"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    formation: Mapped[str] = mapped_column(String(20), nullable=False)
    temperament_key: Mapped[str] = mapped_column(String(40), nullable=False)
    press_line_y: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    block_depth: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    defensive_narrowing: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    board: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="project-authored", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# --- User tactics boards (M4, spec §13 "Tactical Board", §21 sharing) --------------------
# A board a person arranged, as opposed to the 50 the project authored. Coordinates are the user's
# own and are validated on write (eleven slots, known roles, on the grass) rather than trusted: the
# metrics a shared board displays are recomputed from them, so a saved position cannot end up
# inconsistent with the numbers printed beside it.
class TacticBoard(Base, TimestampMixin):
    """A draggable eleven-player board owned by an account, shareable by unguessable token."""

    __tablename__ = "tactic_boards"
    __table_args__ = (
        Index("ix_board_owner", "owner_id"),
        Index("ix_board_visibility", "visibility"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    origin_system: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phase_in: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    phase_out: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    visibility: Mapped[str] = mapped_column(String(12), default="private", nullable=False)
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    shared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# --- Video analysis (M5, spec §14, §47, §62) ---------------------------------------------
# An uploaded clip is user content, so it is never labelled demo data; what *is* demo is the
# vision provider's output, and every detection row carries the provider, model and demo flag that
# produced it so a report cannot present pixel statistics as football insight.
class VideoAsset(Base, TimestampMixin):
    """One uploaded clip, its container facts as ffprobe reported them, and its lifecycle state."""

    __tablename__ = "video_assets"
    __table_args__ = (
        Index("ix_video_owner_created", "owner_id", "created_at"),
        Index("ix_video_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    filename: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False)
    content_type: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="uploaded", nullable=False)
    duration_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fps: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    codec: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    bitrate_kbps: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    frame_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    frame_interval_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    media: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class VideoDetection(Base):
    """One measured event on a clip: where the non-pitch pixels were, and the number that said so."""

    __tablename__ = "video_detections"
    __table_args__ = (Index("ix_detection_asset_time", "asset_id", "t_s"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("video_assets.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40), default="movement", nullable=False)
    t_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    x: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    y: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    why: Mapped[str] = mapped_column(Text, default="", nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    model: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    demo_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# --- Football simulation (M6, spec §19, §20) ---------------------------------------------
# A simulation is derived from the synthetic world's rows, so it is demo data by definition and is
# stored that way on every row rather than only in the response body. `report` is the whole engine
# output — scoreline, per-block ledger, events, and the formula strings behind each rate — and
# `digest` is the hash the engine takes over it, so a saved match can be re-derived and compared
# instead of trusted. The two team ids are nullable with SET NULL: the world may be regenerated or a
# club removed, and the match record must survive that with its own copy of the names.
class SimulationMatch(Base, TimestampMixin):
    """One played match: the inputs that were chosen, the report the engine produced, its digest."""

    __tablename__ = "sim_matches"
    __table_args__ = (
        Index("ix_sim_owner_created", "owner_id", "created_at"),
        Index("ix_sim_fixture", "home_team_id", "away_team_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    model_version: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    seed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    block_minutes: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    home_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    away_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    home_system: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    away_system: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    home_goals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    away_goals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    winner_side: Mapped[str] = mapped_column(String(8), default="draw", nullable=False)
    digest: Mapped[str] = mapped_column(String(16), default="", nullable=False, index=True)
    report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    data_origin: Mapped[str] = mapped_column(String(20), default="simulation", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # The engine's event list as rows (ROADMAP item 4): written in the same transaction as the report, so
    # a match and its timeline appear together or not at all.
    events: Mapped[list[SimulationEvent]] = relationship(back_populates="match", cascade="all, delete-orphan", order_by="SimulationEvent.ordinal")


# --- Career Mode (M6, spec §20) -------------------------------------------------------------------
# A career is the container a season is played in: one account's fictional manager, one club borrowed
# from the synthetic world, a fixture list produced by rotating that competition's clubs, and every
# fixture decided by `possession-block-v1`. The rows below store the *inputs and the outcome of each
# round*; the record, the mini-table and the objective verdicts are summed from them on each read, so
# a career page and a fixture list cannot drift apart — the same rule a single `sim_matches` row
# follows for one match.
CAREER_STATUSES: Final[tuple[str, ...]] = ("active", "retired")
CAREER_PHLOSOPHIES: Final[tuple[str, ...]] = ("possession", "direct", "pressing", "counter", "balanced")
# A career may be played under an authored scenario (spec §21). The scenario's name and its round
# window are the only two things stored: the goal, the reward and the verdict are recomputed from the
# run's own fixtures, so a challenge cannot be edited into having been won.
CHALLENGE_WINDOW_OPEN: Final[int] = 0
OBJECTIVE_KINDS: Final[tuple[str, ...]] = ("wins", "points", "goal_difference", "unbeaten")
OBJECTIVE_FORMULA: Final[dict[str, str]] = {
    "wins": "count of career_fixtures where outcome = W",
    "points": "sum of career_fixtures.points (win 3, draw 1, loss 0)",
    "goal_difference": "sum(club_goals) - sum(opponent_goals)",
    "unbeaten": "longest run of career_fixtures with outcome in (W, D)",
}


class Career(Base, TimestampMixin):
    """One user's managerial career: the club, the stated intent, and the objectives to judge it by."""

    __tablename__ = "careers"
    __table_args__ = (Index("ix_career_owner_created", "owner_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    manager_name: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    club_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    club_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    club_short: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    competition_id: Mapped[str | None] = mapped_column(ForeignKey("competitions.id", ondelete="SET NULL"), nullable=True)
    competition_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    season: Mapped[str] = mapped_column(String(12), default="", nullable=False)
    philosophy: Mapped[str] = mapped_column(String(20), default="balanced", nullable=False)
    system_slug: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    budget: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    budget_units: Mapped[str] = mapped_column(String(40), default="career credits", nullable=False)
    objectives: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    rounds_played: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="active", nullable=False)
    # Set when the career was opened from a live challenge (spec §21). Empty for an open career, which
    # has no window and can be played for as long as its manager likes.
    challenge_slug: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    challenge_window: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="simulation", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    owner: Mapped[User] = relationship()
    club: Mapped[Team | None] = relationship()
    fixtures: Mapped[list[CareerFixture]] = relationship(back_populates="career", cascade="all, delete-orphan", order_by="CareerFixture.round_index")
    listings: Mapped[list[TransferListing]] = relationship(back_populates="career", cascade="all, delete-orphan", order_by="TransferListing.listed_round")
    moves: Mapped[list[CareerSquadMove]] = relationship(back_populates="career", cascade="all, delete-orphan", order_by="CareerSquadMove.round_index")
    wage_charges: Mapped[list[CareerWageCharge]] = relationship(back_populates="career", cascade="all, delete-orphan", order_by="CareerWageCharge.round_index")
    appearances: Mapped[list[CareerAppearance]] = relationship(back_populates="career", cascade="all, delete-orphan", order_by="CareerAppearance.round_index")


class CareerFixture(Base, TimestampMixin):
    """One round: which club was met, on which side, and the stored match that decided it."""

    __tablename__ = "career_fixtures"
    __table_args__ = (
        UniqueConstraint("career_id", "round_index", name="uq_career_round"),
        Index("ix_career_fixture_match", "match_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    career_id: Mapped[str] = mapped_column(ForeignKey("careers.id", ondelete="CASCADE"), nullable=False)
    round_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    match_id: Mapped[str | None] = mapped_column(ForeignKey("sim_matches.id", ondelete="SET NULL"), nullable=True)
    match_slug: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    digest: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    model_version: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    seed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    side: Mapped[str] = mapped_column(String(5), default="home", nullable=False)
    opponent_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    opponent_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    opponent_short: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    venue_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    club_goals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    opponent_goals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    outcome: Mapped[str] = mapped_column(String(4), default="D", nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="simulation", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    career: Mapped[Career] = relationship(back_populates="fixtures")
    match: Mapped[SimulationMatch | None] = relationship()


# --- Transfer market (M6, spec §22) -----------------------------------------------------------------
# The market is what turns a career's budget from a stated number into an arithmetic: every fee that
# leaves or arrives is a row below, and `budget_remaining` is summed from those rows on each read, the
# same way the career's points are. Two tables, because the two things have different lifetimes — a
# *listing* is an offer the market made at a moment (its fee and its clause must not drift when the
# player's stored attributes do), and a *move* is something the career actually did.
MARKET_SIDES: Final[tuple[str, ...]] = ("in", "out")
LISTING_STATUSES: Final[tuple[str, ...]] = ("open", "signed", "withdrawn")
MOVE_KINDS: Final[tuple[str, ...]] = ("buy", "loan", "sell", "release")
MOVE_EFFECT: Final[dict[str, str]] = {
    "buy": "the player joins this career's club and stays",
    "loan": "the player joins until loan_until_round, then stops being available",
    "sell": "the player leaves this career's club and the fee arrives",
    "release": "the player leaves this career's club for nothing",
}
# A wage row is the one ledger entry with no player attached to it, so its sentence names the round.
WAGE_EFFECT: Final = "the wages this career agreed are paid: every deal it holds costs its weekly wage for the round it was held"
# Stored so the number on a page and the rows behind it can be checked against each other by anyone.
BUDGET_FORMULA: Final = "career.budget + sum(moves.fee where kind = sell) - sum(moves.fee where kind in (buy, loan)) - sum(wage_charges.fee)"


class TransferListing(Base, TimestampMixin):
    """One player the market offered a career, at the price the valuation printed when it was listed."""

    __tablename__ = "transfer_listings"
    __table_args__ = (
        UniqueConstraint("career_id", "player_id", name="uq_listing_career_player"),
        Index("ix_listing_career_status", "career_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    career_id: Mapped[str] = mapped_column(ForeignKey("careers.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("real_players.id", ondelete="CASCADE"), nullable=False)
    # The name, club and price as they read at listing time. The player row can be regenerated underneath
    # a career; the offer that was made — and refused — stays what it was.
    player_slug: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    player_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    position: Mapped[str] = mapped_column(String(8), default="", nullable=False)
    age: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overall: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    potential: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    from_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    from_team_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    asking_fee: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # What the seller asks *now*. It starts equal to `asking_fee` and can only come down through
    # negotiation, never below the floor that formula allows; keeping the listing-time price beside it
    # is what lets a reader check that the haggling stopped where the printed rule said it would.
    current_price: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    release_clause: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    contract_years: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    weekly_wage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tactical_fit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    needed_band: Mapped[str] = mapped_column(String(12), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="open", nullable=False)
    listed_round: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    negotiations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_offer: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="simulation", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    career: Mapped[Career] = relationship(back_populates="listings")


class CareerSquadMove(Base, TimestampMixin):
    """One thing a career did to its squad, and the budget arithmetic it left behind.

    `round_index` is the round the move was made before, which is what makes a stored match
    re-derivable: the eleven the engine played in round 4 is the club's squad as of the moves made
    before round 4, not as of today.
    """

    __tablename__ = "career_squad_moves"
    __table_args__ = (
        Index("ix_squad_move_career_round", "career_id", "round_index"),
        Index("ix_squad_move_player", "player_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    career_id: Mapped[str] = mapped_column(ForeignKey("careers.id", ondelete="CASCADE"), nullable=False)
    round_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    kind: Mapped[str] = mapped_column(String(8), default="buy", nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("real_players.id", ondelete="CASCADE"), nullable=False)
    player_slug: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    player_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    position: Mapped[str] = mapped_column(String(8), default="", nullable=False)
    fee: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fee_units: Mapped[str] = mapped_column(String(40), default="career credits", nullable=False)
    contract_years: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    weekly_wage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    loan_until_round: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    listing_id: Mapped[str | None] = mapped_column(ForeignKey("transfer_listings.id", ondelete="SET NULL"), nullable=True)
    counterparty_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    counterparty_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    # The balance the move produced, stored beside it so a reader can add the column up and get the
    # same running total the next row reports.
    budget_after: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="simulation", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    career: Mapped[Career] = relationship(back_populates="moves")


class CareerWageCharge(Base, TimestampMixin):
    """What one played round cost a career in wages (spec §22).

    Its own table rather than another `career_squad_moves` kind because a wage is money that moves with
    no player attached to it: that table's `player_id` is a foreign key a charge has no honest value
    for, and the eleven is composed out of those rows. The ledger a reader adds up is both tables in
    round order, which is why the running `budget_after` is stored on each row of both.

    One row per round, written when the round is played, with the players it was charged for spelled out
    in `detail` so the figure can be checked against the deals without running the code again.
    """

    __tablename__ = "career_wage_charges"
    __table_args__ = (Index("ix_wage_charge_career_round", "career_id", "round_index"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    career_id: Mapped[str] = mapped_column(ForeignKey("careers.id", ondelete="CASCADE"), nullable=False)
    round_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fee: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fee_units: Mapped[str] = mapped_column(String(40), default="career credits", nullable=False)
    players: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    budget_after: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="simulation", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    career: Mapped[Career] = relationship(back_populates="wage_charges")


APPEARANCE_NOTE: Final = (
    "one row per player the engine selected for a career's side in one round. The engine models no "
    "substitutions, so a selected player plays the whole fixture and `minutes` is the match length it was "
    "played at — the row states what was picked, not what was observed."
)


class CareerAppearance(Base, TimestampMixin):
    """One player's place in one career round: the trace a played round leaves behind (spec §20).

    This is what makes a career carry over rather than reset. `career_fixtures` records the score of a
    round and `career_squad_moves` records who the career bought, but neither says who actually played —
    so without these rows the eleven in round 9 is built from exactly the same inputs as the eleven in
    round 1, and no amount of minutes or training could reach the engine.

    Minutes are stored rather than re-read out of `sim_matches.report`, because the match report is the
    engine's output and can be deleted by its owner: the load a round put on a squad is a fact about the
    career, not about a report that happens to still be on file.

    `player_id` follows `career_squad_moves` in being a real foreign key with a cascade — if the world is
    regenerated and a player's row goes, the trace of him goes with it rather than pointing at nobody.
    """

    __tablename__ = "career_appearances"
    __table_args__ = (
        UniqueConstraint("career_id", "round_index", "player_id", name="uq_career_appearance_round_player"),
        Index("ix_appearance_career_round", "career_id", "round_index"),
        Index("ix_appearance_player", "player_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    career_id: Mapped[str] = mapped_column(ForeignKey("careers.id", ondelete="CASCADE"), nullable=False)
    round_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("real_players.id", ondelete="CASCADE"), nullable=False)
    player_slug: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    player_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    position: Mapped[str] = mapped_column(String(8), default="", nullable=False)
    band: Mapped[str] = mapped_column(String(10), default="", nullable=False)
    side: Mapped[str] = mapped_column(String(5), default="home", nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minutes_units: Mapped[str] = mapped_column(String(40), default="match minutes", nullable=False)
    opponent_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="simulation", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    career: Mapped[Career] = relationship(back_populates="appearances")


# --- The stored timeline (M6, ROADMAP item 4) -------------------------------------------------------
# `sim_matches.report` already carries the engine's event list, so this table is not the only copy of
# the timeline — it is the copy that can be *asked a question of*. A report is one JSON blob per match:
# reading "who scored most in this career" or "how many sendings-off in this competition" out of it
# means loading every report in the world. These rows answer both with one query, and they are what a
# later module (a scout, a scoring chart, a disciplinary balance) will be built on.
#
# `ordinal` is the event's position in the report's own list, and `(match_id, ordinal)` is unique
# because the pair is the whole identity of an event: the report is sorted by minute with ties broken
# by the order the engine appended them, so two events in the same minute are only distinguishable by
# which of them came first. That is also why the timeline check compares rows against the report field
# by field rather than by count — a rewritten report that kept its length would pass a `len` test.
EVENT_SIDES: Final[tuple[str, ...]] = ("home", "away")
EVENT_TYPES: Final[tuple[str, ...]] = ("goal", "shot_saved", "shot_off_target", "yellow_card", "red_card", "injury")
# How an event's player was matched to a row. The engine names a scorer out of the side's eleven and
# the report prints names only — `lineup` is inside a stored match's digest, so it cannot be changed to
# carry ids — and the identity is recovered by looking the name back up in the same eleven. A squad
# with two players of one name is therefore `ambiguous` and keeps no id: guessing between them would
# put a real row's record down for the wrong person.
EVENT_ATTRIBUTION: Final[dict[str, str]] = {
    "identified": "the name the engine printed matches exactly one player in that side's selected eleven",
    "ambiguous": "two or more of that side's selected eleven share the name, so no player row is claimed",
    "unnamed": "the event names the side rather than a player, which is what the engine prints with no lineup",
}


class SimulationEvent(Base, TimestampMixin):
    """One engine event as its own row: the minute, what happened, and who the report named."""

    __tablename__ = "sim_events"
    __table_args__ = (
        Index("ix_sim_event_match", "match_id"),
        UniqueConstraint("match_id", "ordinal", name="uq_sim_event_position"),
        Index("ix_sim_event_player_type", "player_id", "event_type"),
        Index("ix_sim_event_type_minute", "event_type", "minute"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("sim_matches.id", ondelete="CASCADE"), nullable=False)
    match_slug: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minute: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), default="", nullable=False)
    side: Mapped[str] = mapped_column(String(5), default="home", nullable=False)
    team: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    player_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    player_id: Mapped[str | None] = mapped_column(ForeignKey("real_players.id", ondelete="SET NULL"), nullable=True)
    player_slug: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    position: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    chance: Mapped[str] = mapped_column(String(24), default="", nullable=False)
    expected_goals: Mapped[float | None] = mapped_column(Float, nullable=True)
    score: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    attribution: Mapped[str] = mapped_column(String(12), default="unnamed", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="simulation", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    match: Mapped[SimulationMatch] = relationship(back_populates="events")


# --- Scouting shortlists (M7, spec §23's "建立 shortlist") ---------------------------------------
# A shortlist stores membership and the manager's own words, never a figure. §22's market listings do
# snapshot prices, and rightly: a listing is the record of an offer that was made, so the number has to
# stay what it was when it was refused. A shortlist is the opposite kind of object — a live question about
# who to watch — so a rating copied in at add-time would keep answering after the row behind it had moved.
# Every figure a shortlist prints is read off the stored players again on the request that shows it.
class ScoutShortlist(Base, TimestampMixin):
    """One named list of players a manager is following, plus the sentence and role it was built against."""

    __tablename__ = "scout_shortlists"
    __table_args__ = (
        Index("ix_shortlist_owner", "owner_id"),
        UniqueConstraint("owner_id", "name", name="uq_shortlist_owner_name"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # The career whose squad need the list is read against, if one was named. Only the link is stored: the
    # need band, the fit figures and §24's team fit are recomputed from the career's own round on every read.
    career_id: Mapped[str | None] = mapped_column(ForeignKey("careers.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    query: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    items: Mapped[list[ScoutShortlistItem]] = relationship(back_populates="shortlist", cascade="all, delete-orphan", order_by="ScoutShortlistItem.position")


class ScoutShortlistItem(Base, TimestampMixin):
    """One player on one list. The only number here is `position`, which is a fact about the list, not the player."""

    __tablename__ = "scout_shortlist_items"
    __table_args__ = (
        UniqueConstraint("shortlist_id", "player_id", name="uq_shortlist_player"),
        Index("ix_shortlist_item_order", "shortlist_id", "position"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    shortlist_id: Mapped[str] = mapped_column(ForeignKey("scout_shortlists.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("real_players.id", ondelete="CASCADE"), nullable=False)
    note: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    shortlist: Mapped[ScoutShortlist] = relationship(back_populates="items")


# --- Club OS: organisations, members, teams (M8, spec §39 and §41) ---------------------------------
# The B2B spine. Two decisions are built into these four tables and are worth stating where the schema is,
# because they are the opposite of what a first pass would do.
#
# First, membership is a row and not a column. `users.organization_id` has existed since the initial
# migration and stays exactly that: a single id, and a constraint that says a scout works for one academy.
# §41 lists Coach and Scout among the tenant kinds, and the same person coaching a club team and scouting
# for an academy is the ordinary case, so `organization_members` is the source of truth. The old column is
# left in place rather than dropped, and the tier's own gate reports any user it points at who is not a
# member — so it can go stale, but it cannot go unnoticed.
#
# Second, a role is a string on a membership row and the permission set it grants lives in code, published
# by the API. Storing permissions per row would let one member's rights drift away from their role with no
# record of who changed what; the matrix in `services/club/access.py` is printed instead, so a member can
# be told which of their rights come from where.
class Organization(Base, TimestampMixin):
    """One tenant: an academy, an amateur club, a school, or an independent scout's desk."""

    __tablename__ = "organizations"
    __table_args__ = (Index("ix_organization_kind", "kind"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(96), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    # `kind` is what §41 asks for, and it is a free label rather than an enum in the database: the difference
    # between an academy and a school changes which reports a parent may see, not which rows exist.
    kind: Mapped[str] = mapped_column(String(32), default="club", nullable=False)
    country: Mapped[str] = mapped_column(String(2), default="", nullable=False)
    # What a report's visibility defaults to when an author does not choose. The column holds the default,
    # not a permission: an explicit choice on a report still overrides it.
    visibility_default: Mapped[str] = mapped_column(String(16), default="members", nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    members: Mapped[list[OrganizationMember]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    # An organisation's teams go with it: a tenant is deleted, its team sheets and its squad rows with it.
    teams: Mapped[list[ClubTeam]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    # §40's academy rows hang off the same spine, and the ORM is told so rather than left to the database's
    # cascade: a tenant's curriculum, its development plans and the consents recorded inside it are deleted by
    # the code that deletes the tenant, on every engine, whether or not that engine enforces foreign keys.
    curricula: Mapped[list[AcademyCurriculum]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    plans: Mapped[list[DevelopmentPlan]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    consents: Mapped[list[GuardianConsent]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class OrganizationMember(Base, TimestampMixin):
    """One person's standing in one organisation, and the role that standing is read through."""

    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_member"),
        Index("ix_organization_member_user", "user_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(24), default="member", nullable=False)
    # `invited` exists so a membership can be offered before it is accepted, and `revoked` so a departure
    # leaves a row behind: deleting a member would erase the record of who could see what while they were in.
    status: Mapped[str] = mapped_column(String(12), default="active", nullable=False)
    invited_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="members")


class ClubTeam(Base, TimestampMixin):
    """One of an organisation's own teams. It is not the fictional world's club, and does not borrow its rows."""

    __tablename__ = "club_teams"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_club_team_name"),
        Index("ix_club_team_organization", "organization_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # An age band is the whole point of an academy's team list, and it is what §40's data-minimisation rules
    # later key off: a squad with anyone under 18 in it is handled as a minors' squad by the reporting tier.
    age_group: Mapped[str] = mapped_column(String(24), default="open", nullable=False)
    stage: Mapped[str] = mapped_column(String(16), default="youth", nullable=False)
    world_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="teams")
    squad: Mapped[list[ClubTeamMember]] = relationship(back_populates="team", cascade="all, delete-orphan")


class ClubTeamMember(Base, TimestampMixin):
    """A stored player on an organisation's team sheet: membership, and a note of the coach's own words."""

    __tablename__ = "club_team_members"
    __table_args__ = (
        UniqueConstraint("team_id", "player_id", name="uq_club_team_player"),
        Index("ix_club_team_member_player", "player_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("club_teams.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("real_players.id", ondelete="CASCADE"), nullable=False)
    note: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    team: Mapped[ClubTeam] = relationship(back_populates="squad")


# --- Youth academy (M8, spec §40) ---------------------------------------------------------
#
# §40 asks for seven things — Player Development, Individual Development Plan, Training Curriculum, Assessment,
# Coach Feedback, Video Evidence, Progress — and for six rules about minors: parental consent, privacy, data
# minimisation, access controls, deletion, age-appropriate design. The shape below is those rules as columns.
#
# **Minimisation is a table, not a promise.** Every column here is named in the published allowlist
# (`services/club/academy.py`'s `STORED_FIELDS`), and there is no column for an address, a telephone number, an
# email, a birthday, a location, a medical note or a school: the tier cannot store what it has nowhere to put.
# The request bodies are `extra="forbid"`, so a caller offering one of those is refused before the service reads
# the payload, and the answer names the field it rejected and the fields it accepts.
#
# **A minor's plan needs a consent row, and the consent row is the access control too.** `guardian_consents`
# links one account to one player inside one tenant and carries the scopes the guardian agreed to. It is
# self-declared — nothing in this project can verify guardianship — and `limitations()` says so rather than
# implying a check that does not exist. A plan for a player under 18 cannot be opened without a granted row, and
# the same row is what lets that guardian read *that child's* plan and no other.
#
# **An assessment keeps its own numbers; progress is arithmetic over those rows.** `overall_observed` and
# `ratings` are a measurement taken on the day, copied from the world's row at that moment, because an
# assessment's whole purpose is to be the record of what was seen then. Progress is therefore never stored: it
# is the difference between the first and last assessment of a plan, recomputed on every read with its formula
# printed beside it.
#
# **`player_id` cascades from `real_players`.** A plan points at the generated world's row for that person, the
# same row a team sheet points at, so a rating cannot go stale on a plan any more than on a sheet. The cost is
# stated in `limitations()`: regenerating the world deletes those rows, and every plan of every tenant goes with
# them. A copy would have survived; a copy would also have disagreed with the player it claimed to describe.
class AcademyCurriculum(Base, TimestampMixin):
    """§40's Training Curriculum: what one age band of one tenant trains, and how much of a week it takes."""

    __tablename__ = "academy_curricula"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_academy_curriculum_name"),
        Index("ix_academy_curriculum_org", "organization_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    age_group: Mapped[str] = mapped_column(String(24), default="open", nullable=False)
    weekly_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Phases are ordered and few: `[{label, focus, minutes}]`. Drills are named by their catalogue slug and never
    # copied, so a curriculum points at the project-authored catalogue the way a sheet points at a player.
    phases: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="curricula")


class DevelopmentPlan(Base, TimestampMixin):
    """§40's Individual Development Plan: one player, one tenant, the focus they agreed to work on."""

    __tablename__ = "development_plans"
    __table_args__ = (
        Index("ix_development_plan_org", "organization_id"),
        Index("ix_development_plan_player", "player_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    curriculum_id: Mapped[str | None] = mapped_column(ForeignKey("academy_curricula.id", ondelete="SET NULL"), nullable=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("club_teams.id", ondelete="SET NULL"), nullable=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("real_players.id", ondelete="CASCADE"), nullable=False)
    author_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="active", nullable=False)
    focus: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    goals: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    review_weeks: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    # The age the plan was opened at, and whether that age made the player a minor. `real_players` carries an
    # integer age for a season, so a plan written in spring must still be able to say which rule applied to it
    # when it was written — the live age is read too, and the two are printed side by side when they disagree.
    age_at_open: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minor_at_open: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="plans")
    assessments: Mapped[list[PlanAssessment]] = relationship(back_populates="plan", cascade="all, delete-orphan")
    feedback: Mapped[list[CoachFeedback]] = relationship(back_populates="plan", cascade="all, delete-orphan")
    evidence: Mapped[list[PlanVideoEvidence]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class PlanAssessment(Base, TimestampMixin):
    """§40's Assessment: the five development axes rated on a day, and what the coach saw then."""

    __tablename__ = "plan_assessments"
    __table_args__ = (Index("ix_plan_assessment_plan", "plan_id", "assessed_on"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("development_plans.id", ondelete="CASCADE"), nullable=False)
    assessor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # An ISO `YYYY-MM-DD` string rather than a DATE column: the tests run on two engines, a review date is
    # ordered and compared as text at day resolution, and nothing here needs date arithmetic in SQL.
    assessed_on: Mapped[str] = mapped_column(String(10), nullable=False)
    ratings: Mapped[dict[str, int]] = mapped_column(JSON, default=dict, nullable=False)
    strengths: Mapped[str] = mapped_column(Text, default="", nullable=False)
    areas: Mapped[str] = mapped_column(Text, default="", nullable=False)
    overall_observed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_focus: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    plan: Mapped[DevelopmentPlan] = relationship(back_populates="assessments")


class CoachFeedback(Base, TimestampMixin):
    """§40's Coach Feedback: one sentence the coach wrote to one player, and whether the guardian may read it."""

    __tablename__ = "coach_feedback"
    __table_args__ = (Index("ix_coach_feedback_plan", "plan_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("development_plans.id", ondelete="CASCADE"), nullable=False)
    coach_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # Default true, and only for a plan that was already gated on a consent row: feedback is the least sensitive
    # of §40's artefacts and a guardian who consented to the plan expects to see what they are being told.
    shared_with_guardian: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    plan: Mapped[DevelopmentPlan] = relationship(back_populates="feedback")


class PlanVideoEvidence(Base, TimestampMixin):
    """§40's Video Evidence: a window of a clip that was uploaded to M5, cited by an assessment."""

    __tablename__ = "plan_video_evidence"
    __table_args__ = (Index("ix_plan_evidence_plan", "plan_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("development_plans.id", ondelete="CASCADE"), nullable=False)
    assessment_id: Mapped[str | None] = mapped_column(ForeignKey("plan_assessments.id", ondelete="SET NULL"), nullable=True)
    # SET NULL, and deliberately so: a clip is a person's upload and may be deleted while a tenant still cites
    # it. The citation then survives with its own measured window and reports `clip_present=False`, which is a
    # truthful record of what was seen; a cascade would have quietly rewritten the assessment's history.
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("video_assets.id", ondelete="SET NULL"), nullable=True)
    label: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    t_start: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    t_end: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    plan: Mapped[DevelopmentPlan] = relationship(back_populates="evidence")


class GuardianConsent(Base, TimestampMixin):
    """§40's parental consent, and the only foothold a parent has: one account, one child, one tenant, one scope set."""

    __tablename__ = "guardian_consents"
    __table_args__ = (
        UniqueConstraint("organization_id", "guardian_user_id", "player_id", name="uq_guardian_consent"),
        Index("ix_guardian_consent_player", "player_id", "state"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    guardian_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("real_players.id", ondelete="CASCADE"), nullable=False)
    # `withdrawn` keeps the row: a consent that was in force for a season was in force, and the record of what
    # was seen under it is the reason a tenant can answer for it afterwards. Withdrawal stops new reads.
    state: Mapped[str] = mapped_column(String(12), default="granted", nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="consents")
