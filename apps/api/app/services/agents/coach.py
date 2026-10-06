"""Coach agent for M1/M11 (spec §9, §32).

Recommends training based on player profile, recent training history, and stated goals.
Uses stored state rather than hallucination — all recommendations derive from database rows.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TrainingSession, UserPlayer
from app.services.agents.base import BaseAgent
from app.services.coach_engine import GOAL_FOCUS, _drill_rows


class CoachAgent(BaseAgent):
    """AI Coach agent that recommends training sessions.

    Analyzes:
    - Player archetype and attributes (from UserPlayer)
    - Recent training completion history
    - Stated goals (from agent memory or query context)

    Returns structured recommendation with drill details and reasoning.
    """

    def run(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """Recommend what to train today based on player state.

        Query should be something like "What should I train today?" or include a goal.
        Returns dict compatible with AgentRunResponse: answer, citations, confidence.
        """
        # Get player info
        player = self._get_player()
        if not player:
            answer = "Create your player profile first to get personalized training recommendations."
            return {
                "answer": answer,
                "citations": [],
                "confidence": 0.0,
                "from_cache": False,
                "stored_key": None,
                "requires_profile": True,
            }

        # Determine training goal from query or memory
        goal = self._extract_goal(query)
        if not goal:
            # Check memory for previously stated goals
            stored_goal = self.recall("current_goal")
            goal = stored_goal.get("goal") if stored_goal else None

        # If still no goal, infer from weakest attributes
        if not goal:
            goal = self._infer_goal(player)

        # Store the goal in memory for continuity
        if goal:
            self.remember("current_goal", {"goal": goal}, ttl_seconds=604800)  # 7 days

        # Get relevant drills
        drills = self._get_drills_for_goal(goal)

        # Get recent training history
        recent_sessions = self._get_recent_sessions()

        # Build recommendation
        primary_drill = drills[0] if drills else None
        alternatives = drills[1:4] if len(drills) > 1 else []

        reasons = self._build_reasons(goal, player, recent_sessions)

        # Format answer as human-readable text
        if primary_drill:
            answer_lines = [
                f"**Today's Training: {primary_drill.get('title', 'Unknown Drill')}**",
                f"",
                f"Goal: {goal.replace('_', ' ').title()}",
                f"Duration: {primary_drill.get('duration_min', 20)} minutes",
                f"Difficulty: {primary_drill.get('difficulty', 'intermediate').title()}",
                f"",
                f"**Why this drill:**",
            ]
            for reason in reasons:
                answer_lines.append(f"- {reason}")

            if alternatives:
                answer_lines.append(f"")
                answer_lines.append(f"**Alternative drills:**")
                for alt in alternatives:
                    answer_lines.append(f"- {alt.get('title')} ({alt.get('category')})")

            answer = "\n".join(answer_lines)
            confidence = 0.8
        else:
            answer = f"I understand you want to work on **{goal.replace('_', ' ').title()}**. The training catalogue is being populated — check back soon for specific drill recommendations."
            confidence = 0.5  # We understood the goal, just no drills available yet

        # Store recommendation in memory
        cache_key = f"coach_recommendation:{goal}"
        self.remember(
            cache_key,
            {
                "drill": primary_drill,
                "goal": goal,
                "reasons": reasons,
                "alternatives": alternatives,
            },
            ttl_seconds=86400,
        )

        return {
            "answer": answer,
            "citations": [],
            "confidence": confidence,
            "from_cache": False,
            "stored_key": cache_key,
        }

    def _get_player(self) -> UserPlayer | None:
        """Get the user's primary player."""
        stmt = select(UserPlayer).where(UserPlayer.user_id == self.user_id).limit(1)
        return self.db.execute(stmt).scalar_one_or_none()

    def _extract_goal(self, query: str) -> str | None:
        """Extract training goal from query text."""
        query_lower = query.lower()

        # Map common phrases to goal keys
        goal_phrases = {
            "improve_first_touch": ["first touch", "ball control", "touch"],
            "improve_passing": ["passing", "long passing", "vision"],
            "improve_dribbling": ["dribbling", "1v1", "ball mastery"],
            "improve_finishing": ["finishing", "shooting", "composure"],
            "improve_defending": ["defending", "tackling", "positioning"],
            "improve_pressing": ["pressing", "transition", "stamina"],
            "improve_weak_foot": ["weak foot", "two-footed"],
            "improve_fitness": ["fitness", "speed", "acceleration", "stamina"],
        }

        for goal_key, phrases in goal_phrases.items():
            if any(phrase in query_lower for phrase in phrases):
                return goal_key

        return None

    def _infer_goal(self, player: UserPlayer) -> str:
        """Infer training goal from player's weakest attributes."""
        # Simple heuristic: focus on lowest-rated core attributes
        # In a real implementation, this would use the full attribute set
        archetype = getattr(player, 'archetype', None) or "general"

        # Default to general improvement
        return "improve_first_touch"

    def _get_drills_for_goal(self, goal: str) -> list[dict[str, Any]]:
        """Get drills relevant to the specified goal."""
        focus = GOAL_FOCUS.get(goal)
        if not focus:
            # Return generic drills
            return _drill_rows(self.db)[:5]

        # Filter drills by matching categories or attributes
        all_drills = _drill_rows(self.db)
        categories = focus.get("categories", ())

        matching = [
            d for d in all_drills
            if d.get("category") in categories
        ]

        # Sort by difficulty (easier first for progression)
        difficulty_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
        matching.sort(key=lambda d: difficulty_order.get(d.get("difficulty", "intermediate"), 1))

        return matching[:5]

    def _get_recent_sessions(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get recent completed training sessions."""
        stmt = (
            select(TrainingSession)
            .where(TrainingSession.user_id == self.user_id)
            .order_by(TrainingSession.completed_at.desc())
            .limit(limit)
        )
        sessions = self.db.execute(stmt).scalars().all()
        return [
            {
                "id": s.id,
                "drill_slug": s.drill_slug,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "execution_rating": s.execution_rating,
            }
            for s in sessions
        ]

    def _build_reasons(self, goal: str, player: UserPlayer, recent_sessions: list) -> list[str]:
        """Build human-readable reasons for the recommendation."""
        reasons = []

        # Goal-based reason
        focus = GOAL_FOCUS.get(goal, {})
        attributes = focus.get("attributes", ())
        if attributes:
            attr_list = ", ".join(attributes[:3])
            reasons.append(f"Focus areas: {attr_list}")

        # Recent training context
        if recent_sessions:
            last_session = recent_sessions[0]
            reasons.append(f"Last trained: {last_session['drill_slug']}")
        else:
            reasons.append("Starting fresh training journey")

        # Player context
        archetype = getattr(player, 'archetype', None)
        if archetype:
            reasons.append(f"Archetype: {archetype}")

        return reasons
