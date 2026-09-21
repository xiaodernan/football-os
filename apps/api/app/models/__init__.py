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


# Reserved for M3 Football World (synthetic, licensed or open provenance only).
class RealPlayer(Base, TimestampMixin):
    __tablename__ = "real_players"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    position: Mapped[str] = mapped_column(String(8), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    attributes: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    derivation_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    overall: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    archetype: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(12), default="synthetic", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Team(Base, TimestampMixin):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    competition_id: Mapped[str | None] = mapped_column(ForeignKey("competitions.id", ondelete="SET NULL"), nullable=True)
    logo_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    data_origin: Mapped[str] = mapped_column(String(12), default="synthetic", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Competition(Base, TimestampMixin):
    __tablename__ = "competitions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    country: Mapped[str] = mapped_column(String(80), default="Generated World", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(12), default="synthetic", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class NewsArticle(Base, TimestampMixin):
    __tablename__ = "news_articles"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_name: Mapped[str] = mapped_column(String(120), default="synthetic-world", nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    author: Mapped[str | None] = mapped_column(String(120), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entities: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    data_origin: Mapped[str] = mapped_column(String(12), default="synthetic", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


RealPlayerTableNote = "RealPlayer/Team/Competition/NewsArticle are reserved for M3 (synthetic, licensed or open provenance only)."


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

    chunks: Mapped[list[KnowledgeChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="KnowledgeChunk.ordinal"
    )


class KnowledgeChunk(Base, TimestampMixin):
    """A retrievable slice of a document: the unit a citation points at."""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_chunk_document_ordinal"),
        Index("ix_chunk_category_ordinal", "category", "ordinal"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
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
