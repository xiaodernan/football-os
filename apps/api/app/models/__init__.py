"""Football World entities (spec §4–§7, §10–§11, §42, §47, §59).

Portable column types only so the same models run on PostgreSQL (+pgvector later)
and the SQLite dev fallback (ADR-002).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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
