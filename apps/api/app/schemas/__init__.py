"""Request/response DTOs (spec §74: typed, validated, versioned)."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.models import GOALS, LEVELS, POSITIONS, PREFERRED_FEET
from app.services.attributes import ALL_ATTRIBUTES

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def _check_email(value: str) -> str:
    if not EMAIL_RE.match(value):
        raise ValueError("Enter a valid email address")
    return value.lower().strip()


class RegisterIn(BaseModel):
    email: str = Field(min_length=6, max_length=320)
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(min_length=2, max_length=60)
    role: Literal["fan", "player", "coach", "manager", "scout", "academy"] = "player"
    accepts_data_policy: bool

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return _check_email(value)

    @field_validator("accepts_data_policy")
    @classmethod
    def _must_accept(cls, value: bool) -> bool:
        if not value:
            raise ValueError("The data policy must be accepted to create an account")
        return value


class LoginIn(BaseModel):
    email: str = Field(min_length=6, max_length=320)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return _check_email(value)


class TokenPair(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    demo_mode: bool


class UserOut(BaseModel):
    id: str
    email: str = Field(min_length=6, max_length=320)
    display_name: str
    role: str
    plan: str
    locale: str
    streak_days: int
    model_config = {"from_attributes": True}


class PlayerIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    position: str
    age: int = Field(ge=8, le=45)
    level: str
    preferred_foot: str
    goal: str
    height_cm: int | None = Field(default=None, ge=120, le=215)
    self_rated_attributes: dict[str, int] | None = None

    @field_validator("position")
    @classmethod
    def _position(cls, value: str) -> str:
        if value not in POSITIONS:
            raise ValueError(f"position must be one of {', '.join(POSITIONS)}")
        return value

    @field_validator("level")
    @classmethod
    def _level(cls, value: str) -> str:
        if value not in LEVELS:
            raise ValueError(f"level must be one of {', '.join(LEVELS)}")
        return value

    @field_validator("preferred_foot")
    @classmethod
    def _foot(cls, value: str) -> str:
        if value not in PREFERRED_FEET:
            raise ValueError("preferred_foot must be left, right or both")
        return value

    @field_validator("goal")
    @classmethod
    def _goal(cls, value: str) -> str:
        if value not in GOALS:
            raise ValueError(f"goal must be one of {', '.join(GOALS)}")
        return value

    @field_validator("self_rated_attributes")
    @classmethod
    def _attrs(cls, value: dict[str, int] | None) -> dict[str, int] | None:
        if value is None:
            return None
        if len(value) > len(ALL_ATTRIBUTES):
            raise ValueError("Too many attributes submitted")
        for key, rating in value.items():
            if key not in ALL_ATTRIBUTES:
                raise ValueError(f"Unknown attribute {key}")
            if not 1 <= rating <= 99:
                raise ValueError(f"{key} must be between 1 and 99")
        return value


class PlayerOut(BaseModel):
    id: str
    name: str
    position: str
    age: int
    level: str
    preferred_foot: str
    goal: str
    height_cm: int | None
    overall: int
    potential: int
    form: float
    archetype: str
    archetype_match: float
    xp: int
    level_number: int
    attributes: dict[str, int]
    visibility: str
    is_demo_data: bool
    derivation_reasons: list[str] = []

    model_config = {"from_attributes": True}


class DrillOut(BaseModel):
    id: str
    slug: str
    title: str
    category: str
    objective: str
    difficulty: int
    duration_min: int
    equipment: list[str]
    setup: str
    instructions: list[str]
    coaching_points: list[str]
    common_mistakes: list[str]
    progressions: list[str]
    regression: str
    test_prompt: str
    test_target: str
    target_attributes: dict[str, int]
    positions: list[str]
    xp_base: int
    is_demo_data: bool = True

    model_config = {"from_attributes": True}


class PlanSessionIn(BaseModel):
    drill_id: str
    available_minutes: int = Field(default=25, ge=5, le=180)
    equipment: list[str] = Field(default_factory=list, max_length=12)
    has_pitch: bool = True


class CompleteIn(BaseModel):
    execution: int = Field(ge=1, le=5)
    focus: int = Field(default=3, ge=1, le=5)
    difficulty_experience: int = Field(default=3, ge=1, le=5)
    self_notes: str | None = Field(default=None, max_length=1200)


class CoachAskIn(BaseModel):
    question: str = Field(min_length=3, max_length=800)
    available_minutes: int | None = Field(default=None, ge=5, le=180)
    has_pitch: bool = True
    equipment: list[str] = Field(default_factory=list, max_length=12)


class PlanIn(BaseModel):
    horizon_days: int = Field(default=7, ge=1, le=90)
    available_minutes: int = Field(default=25, ge=5, le=180)
    days_per_week: int = Field(default=4, ge=1, le=7)
    has_pitch: bool = True


class AiEnvelope(BaseModel):
    demo_mode: bool
    provider: str
    model: str
    confidence: float
    reasons: list[str]
    sources: list[dict[str, Any]] = []
    generated_at: str
    disclaimer: str


KNOWLEDGE_POSITIONS = ("goalkeeper", "defender", "midfielder", "forward", "all")
KNOWLEDGE_DIFFICULTIES = ("beginner", "intermediate", "advanced")


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip().lower()
    return stripped or None


class KnowledgeFilterIn(BaseModel):
    """Metadata filters shared by /search and /ask (spec §29 'Metadata Filter')."""

    mode: Literal["semantic", "keyword", "hybrid"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=20)
    category: str | None = Field(default=None, max_length=40)
    position: str | None = Field(default=None, max_length=20)
    difficulty: str | None = Field(default=None, max_length=20)
    tag: str | None = Field(default=None, max_length=40)
    document_slug: str | None = Field(default=None, max_length=120)

    @field_validator("category", "position", "difficulty", "tag", "document_slug", mode="after")
    @classmethod
    def _normalise(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @field_validator("position")
    @classmethod
    def _position_known(cls, value: str | None) -> str | None:
        if value and value not in KNOWLEDGE_POSITIONS:
            raise ValueError(f"position must be one of: {', '.join(KNOWLEDGE_POSITIONS)}")
        return value

    @field_validator("difficulty")
    @classmethod
    def _difficulty_known(cls, value: str | None) -> str | None:
        if value and value not in KNOWLEDGE_DIFFICULTIES:
            raise ValueError(f"difficulty must be one of: {', '.join(KNOWLEDGE_DIFFICULTIES)}")
        return value


class KnowledgeSearchIn(KnowledgeFilterIn):
    query: str = Field(min_length=2, max_length=400)


class KnowledgeAskIn(KnowledgeFilterIn):
    question: str = Field(min_length=3, max_length=500)


class KnowledgeIngestIn(BaseModel):
    root: str | None = Field(default=None, max_length=400)
    force: bool = False
