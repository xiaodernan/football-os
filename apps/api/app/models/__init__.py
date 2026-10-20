"""Football World entities (spec §4–§7, §10–§11, §42, §47, §59).

Portable column types only so the same models run on PostgreSQL (+pgvector later)
and the SQLite dev fallback (ADR-002).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
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
from app.core.security import new_public_id
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


def utc_today() -> date:
    """The one day the platform counts in: UTC, so a period key and a date rule cannot disagree by a timezone.

    A daily ceiling that rolls at the host's midnight and a record rule that reads a UTC date are two ceilings,
    and a page that prints both would be holding two calendars. Nothing in this app stores a local date.
    """
    return datetime.now(UTC).date()


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
    #: The program that planned this session, when one did. NULL for a session the learner planned
    #: themselves, which is most of them: the column records where a session came from, not that
    #: every session has a program behind it.
    program_id: Mapped[str | None] = mapped_column(String(40), nullable=True)

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


class UsageEvent(Base):
    """§42's Usage: one row per act, in the period that act counted toward. Never a running total.

    A stored counter is the number that goes wrong twice — once when a row is deleted underneath it, once when two
    writers increment at the same time — and it is the same mistake §40 refused for `progress` and §41 refused for
    a report's figures. The ceiling is compared against *this* table, counted at read time, and the period key is
    part of the row so yesterday's acts cannot spend today's allowance.
    """

    __tablename__ = "usage_events"
    __table_args__ = (
        # One act counts once: the same session, plan or report cannot be made to spend a ceiling twice by being
        # recorded twice, and a duplicate insert is the sound of a caller retrying rather than a second act.
        UniqueConstraint("subject_id", "feature", "period_key", "source_id", name="uq_usage_act_once"),
        Index("ix_usage_subject_feature", "subject_id", "feature", "period_key"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    #: An account or a tenant, whichever the feature is metered against. `subject_kind` says which, because the
    #: two id namespaces are different tables and a count across them would be meaningless.
    subject_id: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_kind: Mapped[str] = mapped_column(String(12), default="user", nullable=False)
    feature: Mapped[str] = mapped_column(String(60), nullable=False)
    plan: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    # `YYYY-MM` for a monthly ceiling, `YYYY-MM-DD` for a daily one — the width has to hold the longer of
    # the two, which is the whole reason this leg is run twice: SQLite stores what it is given and Postgres
    # refuses it at the column, so a too-narrow key is invisible on one engine and a DataError on the other.
    period_key: Mapped[str] = mapped_column(String(10), nullable=False)
    #: The row that made the act, so the same act is never counted twice.
    source_id: Mapped[str] = mapped_column(String(40), nullable=False)
    units: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    recorded_on: Mapped[str] = mapped_column(String(10), nullable=False)


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
        Index("ix_board_listed_publicly", "listed_publicly"),
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
    # M9's consent story: the owner's explicit, revocable yes to standing in the public
    # gallery — name, measurements and display name to visitors with no account. Default
    # False: a board is private working material until the owner says otherwise, and
    # revocation changes the gallery's predicate rather than deleting the row.
    listed_publicly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# --- Video analysis (M5, spec §14, §47, §62) ---------------------------------------------
# An uploaded clip is user content, so it is never labelled demo data; what *is* demo is the
# vision provider's output, and every detection row carries the provider, model and demo flag that
# produced it so a report cannot present pixel statistics as football insight.
class VideoAsset(Base, TimestampMixin):
    """One uploaded clip, its container facts as ffprobe reported them, and its lifecycle state.

    M5 item 3 (spec §14): a clip may be linked to the user's football identity (UserPlayer)
    or to an M6 simulation match, and may carry a revocable share token for short
    shareable clips — the same pattern §17 uses for tactical boards.
    """

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

    # M5 item 3: optional links to the user's football identity or an M6 match
    player_id: Mapped[str | None] = mapped_column(ForeignKey("user_players.id", ondelete="SET NULL"), nullable=True, index=True)
    match_id: Mapped[str | None] = mapped_column(ForeignKey("sim_matches.id", ondelete="SET NULL"), nullable=True, index=True)

    # M5 item 3: revocable share token for short shareable clips (same pattern as §17 boards)
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    shared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="private", nullable=False)


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
    sessions: Mapped[list[ClubSession]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    reports: Mapped[list[ClubReport]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    fixtures: Mapped[list[ClubFixture]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    announcements: Mapped[list[ClubAnnouncement]] = relationship(back_populates="organization", cascade="all, delete-orphan")


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


class ClubSession(Base, TimestampMixin):
    """§41's Sessions: one team's training block on one date, recorded by the coach who ran it.

    The row stores what happened — who was there, how long it lasted, how hard it felt — and not what it cost.
    `load_units` is `duration_min × rpe ÷ 60` over these columns, recomputed on every read with its formula
    printed beside it, for the same reason §40 refuses a stored `progress`: a figure derived from rows that can
    still be corrected is a figure that goes out of date in silence.

    `plan_id` and `curriculum_id` are SET NULL. Erasing a child's plan, or retiring a curriculum, must not delete
    the record that a team trained on a Tuesday — that record is the tenant's own history, not a file on the
    child, and §40's erasure right is about the second thing.
    """

    __tablename__ = "club_sessions"
    __table_args__ = (
        # Two sessions on one date is a normal thing — morning and evening — so the pair that must be unique
        # carries the slot, and a collision says which of the three coordinates is already taken.
        UniqueConstraint("organization_id", "team_id", "scheduled_on", "slot", name="uq_club_session_slot"),
        Index("ix_club_session_org_date", "organization_id", "scheduled_on"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[str] = mapped_column(ForeignKey("club_teams.id", ondelete="CASCADE"), nullable=False)
    plan_id: Mapped[str | None] = mapped_column(ForeignKey("development_plans.id", ondelete="SET NULL"), nullable=True)
    curriculum_id: Mapped[str | None] = mapped_column(ForeignKey("academy_curricula.id", ondelete="SET NULL"), nullable=True)
    coach_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # An ISO date as text, exactly as `plan_assessments.assessed_on` keeps it: the string compares in order,
    # prints as it is stored, and does not depend on a driver's notion of a date.
    scheduled_on: Mapped[str] = mapped_column(String(10), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rpe: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    focus: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # Drills are named by catalogue slug and never copied, the way a curriculum names them: the catalogue is the
    # project's, and a session that duplicated a drill could disagree with it.
    drill_slugs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # Player ids, not rows: attendance is a selection over the sheet, and the sheet is what owns the grouping.
    attendees: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    note: Mapped[str] = mapped_column(String(280), default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="sessions")


class ClubReport(Base, TimestampMixin):
    """§41's Reports: a saved *question* about a tenant, whose answers are re-summed from the rows each reader may see.

    The row stores a window and a scope — which team, which date range, which kind of reading was asked for — and
    no figure at all. Every number a report prints is summed from `club_sessions`, `guardian_consents`,
    `plan_assessments` and the sheets at read time, which is what lets the same saved report answer honestly a
    week later, to a different reader, after rows were added or erased. A stored payload would be a document that
    quietly keeps saying something the tenant no longer holds true — and to a guardian it would say more than
    their own read is allowed to see.
    """

    __tablename__ = "club_reports"
    __table_args__ = (
        # The same question, on the same window, for the same team is one report. Re-asking it updates the row
        # rather than stacking copies a reader would then have to tell apart.
        UniqueConstraint("organization_id", "kind", "team_id", "window_from", "window_to", name="uq_club_report_window"),
        Index("ix_club_report_org_kind", "organization_id", "kind"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    asked_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    #: Which reading of the tenant was asked for. §41 names Reports without a schema, so the vocabulary is this
    #: tier's own and is published by the door rather than inferred by a reader.
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("club_teams.id", ondelete="CASCADE"), nullable=True)
    window_from: Mapped[str] = mapped_column(String(10), nullable=False)
    window_to: Mapped[str] = mapped_column(String(10), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="reports")


class ClubFixture(Base, TimestampMixin):
    """§39's Matches: one fixture a tenant arranged, and a pointer to the match that answered it.

    The row is the *arrangement*: who was invited, which side this tenant's team was on, the date, the
    competition, and the eleven the tenant named. Every number about the game itself lives in `sim_matches` and
    `sim_events`, and what is kept here is the pointer that reaches them — `match_id`, the report's `digest`, the
    `model_version` that produced it and the `seed` the caller chose. A stored scoreline would disagree with a
    re-played match the moment the model is corrected, which is the mistake §40 refused for `progress` and §41
    for `load_units`.

    `opponent_name` is kept as text beside the id for the same reason `career_fixtures` keeps its opponent's: a
    world regeneration that renames or drops a club must not rewrite what two sides agreed to. The id is
    SET NULL, so the read prints the name it stored and says the club behind it is gone.
    """

    __tablename__ = "club_fixtures"
    __table_args__ = (
        # One side cannot be at home twice on a date; the same team playing the other side of a tie on the same
        # day, or two different teams of one tenant at home, are both ordinary and both stay legal.
        UniqueConstraint("organization_id", "team_id", "scheduled_on", "side", name="uq_club_fixture_day_side"),
        Index("ix_club_fixture_org_date", "organization_id", "scheduled_on"),
        Index("ix_club_fixture_team_date", "team_id", "scheduled_on"),
        Index("ix_club_fixture_match", "match_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[str] = mapped_column(ForeignKey("club_teams.id", ondelete="CASCADE"), nullable=False)
    opponent_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    opponent_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    side: Mapped[str] = mapped_column(String(5), default="home", nullable=False)
    competition: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    # An ISO date as text, exactly as `club_sessions.scheduled_on` keeps it.
    scheduled_on: Mapped[str] = mapped_column(String(10), nullable=False)
    # `scheduled` or `played`. Nothing else: an arrangement and a result are the two states this noun has, and a
    # third word would be a claim about a competition this tier does not run.
    status: Mapped[str] = mapped_column(String(12), default="scheduled", nullable=False)
    match_id: Mapped[str | None] = mapped_column(ForeignKey("sim_matches.id", ondelete="SET NULL"), nullable=True)
    match_slug: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    digest: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    model_version: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    # Player ids, not rows, and resolved at write time the way §41's attendance is: a fixture may be arranged
    # before an eleven is picked, so an empty list is allowed here where a session refuses one.
    named: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    note: Mapped[str] = mapped_column(String(280), default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="fixtures")
    # The record of who played, deleted with the arrangement it belongs to — the relationship is where the
    # CASCADE becomes visible to a reader of the model rather than only to the database.
    appearances: Mapped[list[ClubMatchAppearance]] = relationship(back_populates="fixture", cascade="all, delete-orphan")


class ClubMatchAppearance(Base, TimestampMixin):
    """One player the engine selected for one of this tenant's fixtures.

    A lineup is a *selection* — `club_fixtures.named`, the coach's words — and an appearance is a *record*: the
    eleven the engine actually shaped, from the tenant's rows, checked name by name against the stored report
    before a single row was written. The two cannot live in one column: the selection can still be edited and the
    record must not move, and `simulation.squad.replay_squads` cannot rebuild this side from above because it
    replays a *career's* overlays from move rows, which a tenant's fixture has none of.

    The name and slug are copied forward from the player row, the way `career_appearances` does, so a person
    renamed afterwards does not have their appearance re-titled; `player_id` stays the join. It is CASCADE, not
    SET NULL: a child whose record a guardian erases takes their appearance rows with them, which is §40's
    deletion right rather than a tenant's history going missing.
    """

    __tablename__ = "club_match_appearances"
    __table_args__ = (
        UniqueConstraint("fixture_id", "player_id", name="uq_club_match_appearance_player"),
        Index("ix_club_match_appearance_fixture", "fixture_id"),
        Index("ix_club_match_appearance_player", "player_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    fixture_id: Mapped[str] = mapped_column(ForeignKey("club_fixtures.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("real_players.id", ondelete="CASCADE"), nullable=False)
    player_slug: Mapped[str] = mapped_column(String(96), default="", nullable=False)
    player_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    position: Mapped[str] = mapped_column(String(24), default="", nullable=False)
    band: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    side: Mapped[str] = mapped_column(String(5), default="home", nullable=False)
    # The fixture's length, not a count of what this player did: the engine makes no substitutions, so a minute
    # column that could be edited per player would be a figure nothing produces.
    minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note: Mapped[str] = mapped_column(String(280), default="", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    fixture: Mapped[ClubFixture] = relationship(back_populates="appearances")


# --- Club OS: §39's Communication row (M8, spec §39) ----------------------------------------------
# A notice and its receipts. The decision worth reading before the columns is the missing one: there is
# no recipient list, because an audience is a predicate over `organization_members` and the people it
# selects are recomputed on every read. That is simultaneously the tier's data-minimisation rule (§40
# forbids a row about one named child, and this table has no column that could hold one) and the reason
# a revoked member leaves the denominator at once instead of haunting a stored count.
class ClubAnnouncement(Base, TimestampMixin):
    """One notice a member posts to an audience, with the role its author held when they posted it."""

    __tablename__ = "club_announcements"
    __table_args__ = (
        Index("ix_club_announcement_org_date", "organization_id", "published_on"),
        Index("ix_club_announcement_board", "organization_id", "audience", "pinned"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    # One of `announcements.AUDIENCES`, kept as text the way `role` and `status` are: the vocabulary is
    # code's, and a new audience is a new predicate rather than a migration.
    audience: Mapped[str] = mapped_column(String(24), default="members", nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(String(2000), default="", nullable=False)
    author_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # The role at publish time, deliberately a copy rather than a join: a member whose role changes
    # afterwards must not have a notice they wrote as a director re-titled under a different one.
    author_role: Mapped[str] = mapped_column(String(24), default="", nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # An ISO date as text, exactly as `club_sessions.scheduled_on` keeps it.
    published_on: Mapped[str] = mapped_column(String(10), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="announcements")
    # The receipts go with the notice: erasing a notice erases what anybody read of it, which is the
    # tenant's `announce.erase` right and not a member's history.
    reads: Mapped[list[ClubAnnouncementRead]] = relationship(back_populates="announcement", cascade="all, delete-orphan")


class ClubAnnouncementRead(Base, TimestampMixin):
    """One account's receipt for one notice: a fact, idempotent at the schema level and not only in the code path."""

    __tablename__ = "club_announcement_reads"
    __table_args__ = (
        UniqueConstraint("announcement_id", "user_id", name="uq_club_announcement_read"),
        Index("ix_club_announcement_read_user", "user_id", "read_on"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    announcement_id: Mapped[str] = mapped_column(ForeignKey("club_announcements.id", ondelete="CASCADE"), nullable=False)
    # CASCADE, not SET NULL: a receipt that names no account answers no question, and §40's deletion
    # right is that an account's records go when their account does.
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    read_on: Mapped[str] = mapped_column(String(10), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    announcement: Mapped[ClubAnnouncement] = relationship(back_populates="reads")


# --- Community: §35's publishing tier (M9, spec §35) ------------------------------------------------
# Five tables and one rule that decides all five: **a post stores a pointer, never a copy**. The figures a
# reader sees about a share — `likes`, `comments`, `reposts`, `followers` — are counted from the rows below at
# read time, so no column here could hold a stale statistic, and none could hold a figure about a child.
# The three pair-tables carry their idempotency as a unique constraint rather than as a code path, which is
# §40's consent row and §57's receipt row carried over to a community; and `community_follows` is the only row
# here that decides reach, so an unfollow withdraws a `followers` post at once and deletes nothing already read.
# Every key out of a post CASCADEs — including `author_id`, unlike §57's notice: a post is its author's own
# publication, and §40's erasure right is that an account's records go with the account.
class CommunityPost(Base, TimestampMixin):
    """One publication: the author's words, a kind, and the address of the artifact being shared."""

    __tablename__ = "community_posts"
    __table_args__ = (
        Index("ix_community_post_author_date", "author_id", "shared_on"),
        Index("ix_community_post_visibility", "visibility", "shared_on"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # One of `posts.POST_KINDS`, kept as text the way `audience` and `role` are: the vocabulary is code's, and a
    # new kind is a new pointer prefix rather than a migration.
    kind: Mapped[str] = mapped_column(String(24), default="note", nullable=False)
    body: Mapped[str] = mapped_column(String(1500), nullable=False)
    # The artifact's own path (`/tactics/boards/<slug>`, `/training/<slug>`, …), or empty for a `note`. Never a
    # copy of anything the artifact reports about itself.
    pointer: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    # One of `posts.VISIBILITIES`. A predicate, not a list: `followers` is answered by joining the follow table
    # on read, which is §57's audience-as-predicate argument with the audience being an account's followers.
    visibility: Mapped[str] = mapped_column(String(12), default="public", nullable=False)
    # An ISO date as text, exactly as `club_announcements.published_on` keeps it.
    shared_on: Mapped[str] = mapped_column(String(10), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CommunityComment(Base, TimestampMixin):
    """One reply on a post — words only, and they go with either side of the exchange."""

    __tablename__ = "community_comments"
    __table_args__ = (Index("ix_community_comment_post_date", "post_id", "commented_on"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(String(600), nullable=False)
    commented_on: Mapped[str] = mapped_column(String(10), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CommunityReaction(Base, TimestampMixin):
    """One account's one reaction to one post: pressing twice is one row because the schema says so."""

    __tablename__ = "community_reactions"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", "reaction", name="uq_community_reaction"),
        Index("ix_community_reaction_user", "user_id", "reacted_on"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # The vocabulary is `posts.REACTIONS` — one word today — and a `String` rather than an enum so that adding a
    # second feeling is a line in a tuple, not a migration with a rollback.
    reaction: Mapped[str] = mapped_column(String(16), default="like", nullable=False)
    reacted_on: Mapped[str] = mapped_column(String(10), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CommunityRepost(Base, TimestampMixin):
    """One account carrying another's post. Its existence is the whole figure `reposts` counts."""

    __tablename__ = "community_reposts"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_community_repost"),
        Index("ix_community_repost_user", "user_id", "reposted_on"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reposted_on: Mapped[str] = mapped_column(String(10), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CommunityFollow(Base, TimestampMixin):
    """One account's follow of another — the row that decides who a `followers` post reaches."""

    __tablename__ = "community_follows"
    __table_args__ = (
        UniqueConstraint("follower_id", "followee_id", name="uq_community_follow"),
        Index("ix_community_follow_followee", "followee_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    # Both sides CASCADE: a follow is a relation between two accounts and answers no question once either is
    # gone, and the tier refuses self-follows in code because a row that is its own audience would make
    # `followers` mean nobody.
    follower_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    followee_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    followed_on: Mapped[str] = mapped_column(String(10), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# --------------------------------------------------------------------------- M10's first noun: §36's creator tier
#
# Three tables and the rule §35 was built on: **a publication stores an address, never a copy**. A guide holds its
# title, its section and the author's own notes; the passages it cites stay in `knowledge_chunks`, so re-ingesting
# the corpus cannot leave a guide asserting text the document no longer carries.
#
# A citation keys on `document_id` plus the chunk's `ordinal` and stores the `text_hash` that sat at that address
# when the citation was written — because `services/knowledge/ingest.py` mints a fresh `kch_…` id for every chunk on
# each re-sync, so an id-keyed pointer dangles on the first corpus edit while (document, ordinal) keeps resolving.
# The hash is not a link, it is a witness: it is what lets a read say *this passage has moved since it was cited*.
#
# `creator_profiles` is a **state, not a role**: its existence is what makes an account a creator, and `ROLES` stays
# at seven, because a second home for that fact would have to be kept in step with the first. No column here can
# hold money — §42's `entitlements` rows are the whole of the pricing architecture in this milestone.


class CreatorProfile(Base, TimestampMixin):
    """One account's creator state. There is no `is_creator` column: this row, or its absence, is the answer."""

    __tablename__ = "creator_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_creator_profile_user"),
        UniqueConstraint("slug", name="uq_creator_profile_slug"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    headline: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    bio: Mapped[str] = mapped_column(String(1500), nullable=False, default="")
    since: Mapped[str] = mapped_column(String(10), nullable=False, default=utc_today)
    data_origin: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    is_demo_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CreatorGuide(Base, TimestampMixin):
    """A guide is a title, a section, an ordering and the author's words — and no text of what it cites."""

    __tablename__ = "creator_guides"
    __table_args__ = (
        UniqueConstraint("author_id", "slug", name="uq_creator_guide_slug"),
        Index("ix_creator_guide_author_date", "author_id", "published_on"),
        Index("ix_creator_guide_section", "section", "published_on"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    section: Mapped[str] = mapped_column(String(16), nullable=False, default="plan")
    visibility: Mapped[str] = mapped_column(String(12), nullable=False, default="public")
    published_on: Mapped[str] = mapped_column(String(10), nullable=False, default=utc_today)
    data_origin: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    is_demo_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class GuideCitation(Base, TimestampMixin):
    """One passage, cited once per guide: `citations` is a count of these rows, never a number stored beside them."""

    __tablename__ = "guide_citations"
    __table_args__ = (
        UniqueConstraint("guide_id", "document_id", "ordinal", name="uq_creator_citation"),
        Index("ix_creator_citation_document", "document_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    guide_id: Mapped[str] = mapped_column(ForeignKey("creator_guides.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="RESTRICT"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cited_text_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    note: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    data_origin: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    is_demo_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)



class CreatorProgram(Base, TimestampMixin):
    """A training program: a schedule, a dose and a progression (M10, spec §36's first kind).

    §36 lists six kinds of content a user can create, and the first is a Training Program. The
    tier's guide is a frame - a section, a title, a summary and the addresses of the passages it
    cites - and it is not a plan a learner can walk. A program is: a title, a visibility and an
    ordered list of steps, each step naming a drill from the training catalogue, the minutes it asks
    for and the author's own words. It stores no session and no completion: those are the
    learner's rows in the training tier, counted from there.
    """

    __tablename__ = "creator_programs"
    __table_args__ = (
        UniqueConstraint("author_id", "slug", name="uq_creator_program_slug"),
        Index("ix_creator_program_author_date", "author_id", "published_on"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    visibility: Mapped[str] = mapped_column(String(12), nullable=False, default="public")
    published_on: Mapped[str] = mapped_column(String(10), nullable=False, default=utc_today)
    data_origin: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    is_demo_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CreatorProgramStep(Base, TimestampMixin):
    """One step of a program: the catalogue drill, the minutes it asks for, and the author's words.

    `position` is the progression - the order the steps are walked in - and it is unique per
    program, so a program cannot hold two steps at the same place in its own schedule.
    """

    __tablename__ = "creator_program_steps"
    __table_args__ = (UniqueConstraint("program_id", "position", name="uq_creator_program_step_position"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("creator_programs.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    drill_slug: Mapped[str] = mapped_column(String(80), nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(String(300), nullable=False, default="")


class CreatorTacticalGuide(Base, TimestampMixin):
    """An editorial guide anchored to a stored tactical system (M10, spec §36's second kind).

    §36's second kind is a *Tactical Guide*: an author's reading of a shape, published beside the
    shape rather than copied out of it. The row stores the author's words, a visibility and the
    **address** of a row in `tactical_systems` - never a metric, a coordinate or a sentence about
    the shape. Every measurement a read shows is computed from the system's own dots on that read,
    so a revised catalogue cannot leave a guide quoting the old geometry.

    `system_hash` is not a figure about the system, it is a **witness**: the content address the
    system carried when the guide was written. A read compares it with the catalogue's, and a guide
    whose system has been revised since says so through `moved` while still measuring the system as
    it reads now - the same shape as `guide_citations.cited_text_hash`.

    `system_slug` is a plain pointer rather than a foreign key on purpose: `services/tactics/sync.py`
    retires catalogue rows the plan no longer authors, and a RESTRICT would make a routine catalogue
    sync fail because somebody once wrote about a system. A retired system answers as absence on
    read, in the same shape a guide that was never written earns.
    """

    __tablename__ = "creator_tactical_guides"
    __table_args__ = (
        UniqueConstraint("author_id", "slug", name="uq_creator_tactical_slug"),
        Index("ix_creator_tactical_author_date", "author_id", "published_on"),
        Index("ix_creator_tactical_system", "system_slug"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    visibility: Mapped[str] = mapped_column(String(12), nullable=False, default="public")
    system_slug: Mapped[str] = mapped_column(String(160), nullable=False)
    system_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    published_on: Mapped[str] = mapped_column(String(10), nullable=False, default=utc_today)
    data_origin: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    is_demo_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CreatorPlayerAnalysis(Base, TimestampMixin):
    """An editorial analysis anchored to a stored world player (M10, spec §36's third kind).

    §36's third kind is a *Player Analysis*: an author's reading of a footballer, published beside
    the player rather than copied out of him. The row stores the author's words, a visibility and
    the **address** of a row in `real_players` - never a rate, a total or a sentence about the
    player. Every measurement a read shows is computed from the player's own stored columns on that
    read, so a refreshed world cannot leave an analysis quoting last season's output.

    `player_hash` is not a figure about the player, it is a **witness**: the content address the
    player carried when the analysis was written. A read compares it with the world's, and an
    analysis of a player revised since says so through `moved` while still measuring the player as
    he reads now - the same shape as `guide_citations.cited_text_hash`.

    `player_slug` is a plain pointer rather than a foreign key on purpose: `services/world/sync.py`
    retires rows the world plan no longer authors, and a RESTRICT would make a routine world sync
    fail because somebody once wrote about a player. A retired player answers as absence on read,
    in the same shape an analysis that was never written earns.
    """

    __tablename__ = "creator_player_analyses"
    __table_args__ = (
        UniqueConstraint("author_id", "slug", name="uq_creator_analysis_slug"),
        Index("ix_creator_analysis_author_date", "author_id", "published_on"),
        Index("ix_creator_analysis_player", "player_slug"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    visibility: Mapped[str] = mapped_column(String(12), nullable=False, default="public")
    player_slug: Mapped[str] = mapped_column(String(160), nullable=False)
    player_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    published_on: Mapped[str] = mapped_column(String(10), nullable=False, default=utc_today)
    data_origin: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    is_demo_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CvShare(Base, TimestampMixin):
    """One public CV link (§38's share output): the token that opens it, the sections it names, and when it closed."""

    __tablename__ = "cv_shares"
    __table_args__ = (
        UniqueConstraint("share_token", name="uq_cv_share_token"),
        Index("ix_cv_share_owner_live", "user_id", "revoked_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    share_token: Mapped[str] = mapped_column(String(64), nullable=False)
    sections: Mapped[list[str]] = mapped_column(JSON, default=list)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentMemory(Base, TimestampMixin):
    """One persisted fact or context fragment for an M11 agent (spec §34 agent memory).

    Each row stores a named key/value pair scoped to a user and agent type, with optional
    session binding and TTL-based expiration. Agents read their own memories at startup
    and write new ones as they work; expired rows are pruned by a background sweep.
    """

    __tablename__ = "agent_memories"
    __table_args__ = (
        Index("ix_agent_memories_user_agent", "user_id", "agent_type"),
        Index("ix_agent_memories_expires", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_public_id("am"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RequestSpan(Base, TimestampMixin):
    """One finished span, kept so a request can be read back without a collector (M12 observability).

    OpenTelemetry was wired with an OTLP exporter, which means the spans went wherever a
    collector was listening - and nowhere at all on a host that runs none. This table is the
    backend that needs no collector: the exporter writes each finished span here, and a door
    reads a request's spans back.

    The identifiers are the trace's own: `trace_id` groups the spans of one request, `span_id`
    names one of them and `parent_span_id` names the span it hung from, so the tree is stored
    rather than rebuilt. The timings are the span's own nanosecond clock, kept as UTC datetimes
    and a duration in milliseconds, because a span that cannot say how long it took cannot say
    where the time went.
    """

    __tablename__ = "request_spans"
    __table_args__ = (
        Index("ix_request_spans_trace", "trace_id"),
        Index("ix_request_spans_start", "start_time"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_public_id("sp"))
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False)
    span_id: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_span_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="unset")
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attributes_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
