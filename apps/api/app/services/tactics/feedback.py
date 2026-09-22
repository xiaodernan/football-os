"""Tactical feedback: an analysis assembled from measurement plus passages this project wrote (spec §13, §29; `AI_POLICY.md` §1/§3).

Two hard rules, both inherited from the M2 knowledge surface:

1. **A point is made only if a stored principle supports it.** Each topic is a question put to the
   knowledge corpus through the same hybrid retrieval the library uses; if retrieval does not reach
   its answerability gates, the topic is reported as *not grounded* rather than filled with plausible
   coaching prose. The refusals are part of the payload, so a reader can see what this system could
   not say.
2. **The numbers come from the geometry.** Every value quoted in a statement is read back out of the
   measured payload with its formula, so the sentence "the block sits 10.0 m from its own goal" is
   checkable against the same table the page prints.

With no provider key configured this is extractive assembly, and `method` says exactly that; it is
never presented as a model's opinion, and no AI output here writes to a stored row.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import TACTICS_DISCLAIMER
from app.services.knowledge.retrieval import MIN_USEFUL_SCORE, Hit, search

FIT_TOLERANCE: Final = 4
FIT_SHORTFALL: Final = 12


@dataclass(frozen=True)
class Topic:
    """One question the analysis asks, the measurement it is about, and how the answer is phrased."""

    key: str
    label: str
    query: str
    metric: str
    phase: str
    frame: str


TOPICS: Final[tuple[Topic, ...]] = (
    Topic(
        key="pressing",
        label="Pressing line",
        query="what makes a high press worth the risk, and what triggers it",
        metric="space_behind",
        phase="out",
        frame="Defends with the back line {value:.1f} m from its own goal: the press is only worth it if the trigger is taught, because that is the space a ball in behind has to travel.",
    ),
    Topic(
        key="compactness",
        label="Block compactness",
        query="defending in a compact block distance between the lines",
        metric="spacing",
        phase="out",
        frame="Mean {value:.1f} m to the nearest team-mate while out of possession, which is the distance a combination has to cross to break the block.",
    ),
    Topic(
        key="build-up",
        label="Build-up under pressure",
        query="building up against a press, the first pass and the rest defence",
        metric="isolation",
        phase="in",
        frame="The most isolated player in possession is {value:.1f} m from support — the exact yardstick for whether a press can be played through.",
    ),
    Topic(
        key="width",
        label="Width in attack",
        query="using width in attack to stretch a compact block",
        metric="width",
        phase="in",
        frame="Attacking shape spans {value:.1f} m of the 68 m width, so the opponent's block is asked to shift that far before the ball is switched.",
    ),
    Topic(
        key="lines",
        label="Distance between the lines",
        query="space between the lines of a team and the counter-attack it allows",
        metric="line_separation",
        phase="in",
        frame="{value:.1f} m separates this team's lines in possession, which is the channel a counter is played into on a turnover.",
    ),
    Topic(
        key="height",
        label="How high the team sits",
        query="squad height and territory held in possession",
        metric="balance",
        phase="in",
        frame="The team's mass sits {value:.1f} m from its own goal, so most tackles and turnovers happen in the opponent's half.",
    ),
)


@dataclass
class FeedbackResult:
    """The cited analysis of one system: what is grounded, and what this build refused to say."""

    system: dict[str, Any]
    points: list[dict[str, Any]] = field(default_factory=list)
    ungrounded: list[dict[str, Any]] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    retrieval_backend: str = ""
    scanned_chunks: int = 0

    @property
    def demo_mode(self) -> bool:
        return settings.is_demo_mode

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "points": self.points,
            "ungrounded": self.ungrounded,
            "reasons": self.reasons,
            "citations": [point["citation"] for point in self.points],
            "retrieval_backend": self.retrieval_backend,
            "scanned_chunks": self.scanned_chunks,
            "demo_mode": self.demo_mode,
            "provider": "none (no AI key configured)" if self.demo_mode else "configured provider",
            "model": "extractive assembly over measured rows + knowledge corpus",
            "method": (
                "Each topic is a query against the project-authored knowledge corpus through the same hybrid "
                "retrieval as /knowledge. A topic whose retrieval fails the answerability gates is reported in "
                "`ungrounded` with its measured numbers instead of being written as prose."
            ),
            "data_origin": "project-authored",
            "is_demo_data": False,
            "disclaimer": TACTICS_DISCLAIMER,
        }


def _best_hit(hits: list[Hit]) -> Hit | None:
    return next((hit for hit in hits if hit.score >= MIN_USEFUL_SCORE), None)


def build_feedback(db: Session, payload: Mapping[str, Any]) -> FeedbackResult:
    """Analyse one stored system: measured statements, each anchored to a cited passage."""
    board = dict(payload.get("board") or {})
    metrics = {
        "in": {str(row["key"]): row for row in board.get("metrics_in") or []},
        "out": {str(row["key"]): row for row in board.get("metrics_out") or []},
    }
    result = FeedbackResult(
        system={
            "slug": payload.get("slug"),
            "name": payload.get("name"),
            "formation": payload.get("formation"),
            "temperament_key": payload.get("temperament_key"),
            "idea": board.get("idea"),
            "strengths": board.get("strengths") or [],
            "risks": board.get("risks") or [],
        }
    )
    backend = ""
    scanned = 0

    for topic in TOPICS:
        row = metrics[topic.phase].get(topic.metric)
        if row is None:
            result.ungrounded.append({"topic": topic.key, "label": topic.label, "reason": "the measurement is missing"})
            continue
        value = float(row["value"])
        search_result = search(db, topic.query, top_k=3)
        backend = backend or search_result.backend
        scanned += search_result.scanned
        hit = _best_hit(search_result.hits) if search_result.answerable else None
        if hit is None:
            result.ungrounded.append(
                {
                    "topic": topic.key,
                    "label": topic.label,
                    "value": value,
                    "unit": row["unit"],
                    "reason": search_result.reasons[-1] if search_result.reasons else "no passage reached the answerability gates",
                    "answerability": {
                        "answerable": search_result.answerable,
                        "coverage": round(search_result.discriminative_coverage, 3),
                        "top_score": round(search_result.top_score, 4),
                    },
                }
            )
            continue
        result.points.append(
            {
                "topic": topic.key,
                "label": topic.label,
                "statement": topic.frame.format(value=value),
                "metric": {
                    "key": topic.metric,
                    "value": value,
                    "unit": row["unit"],
                    "formula": row["formula"],
                    "phase": topic.phase,
                },
                "citation": hit.citation(),
                "score": round(hit.score, 4),
            }
        )
        result.reasons.append(f"{topic.label}: cited {hit.document_slug}#{hit.ordinal} at score {hit.score:.3f}")

    if not result.points:
        result.reasons.append("no topic reached the corpus's answerability gates, so no statement was made")
    result.retrieval_backend = backend or "none"
    result.scanned_chunks = scanned
    return result


def fit_rows(demands: Mapping[str, int], attributes: Mapping[str, int]) -> dict[str, Any]:
    """Compare a player's six tactical attributes with what a system's roles demand.

    Arithmetic, not adjectives: the verdict for each attribute is a threshold on a published
    difference, and the sum is the mean of those differences — so the same two rows always produce
    the same fit, and a reader can recompute it.
    """
    rows: list[dict[str, Any]] = []
    for attribute, demand in sorted(demands.items()):
        have = int(attributes.get(attribute, 0) or 0)
        gap = have - demand
        verdict = "short" if gap <= -FIT_SHORTFALL else "exceeds" if gap >= FIT_TOLERANCE else "matches"
        rows.append(
            {
                "attribute": attribute,
                "demanded": demand,
                "have": have,
                "gap": gap,
                "verdict": verdict,
                "rule": f"short at ≤ -{FIT_SHORTFALL}, exceeds at ≥ +{FIT_TOLERANCE}, otherwise matches",
            }
        )
    covered = len(rows)
    mean_gap = round(sum(row["gap"] for row in rows) / covered, 2) if covered else 0.0
    shortfalls = [row["attribute"] for row in rows if row["verdict"] == "short"]
    return {
        "rows": rows,
        "mean_gap": mean_gap,
        "covered_attributes": covered,
        "shortfalls": shortfalls,
        "verdict": ("fits the demands of this shape" if not shortfalls else f"short in {len(shortfalls)} of {covered} tactical demands: {', '.join(shortfalls)}"),
        "formula": "gap = attribute - demand per attribute; mean_gap is the arithmetic mean of those gaps",
    }
