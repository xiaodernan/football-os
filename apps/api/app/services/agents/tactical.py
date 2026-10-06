"""Tactical agent for M11 (spec §32).

Analyzes tactical systems, formations, and space patterns to answer questions about
team shape, pressing, width, and positional roles. Queries the tactical_systems table
and synthesizes recommendations based on measured geometry.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TacticalSystem
from app.services.agents.base import BaseAgent


class TacticalAgent(BaseAgent):
    """Football tactics agent that analyzes formations and space patterns.

    Uses stored tactical systems (§16-§18) to compare formations, identify weak zones,
    and recommend adjustments. Persists analysis in agent memory for follow-up questions.
    """

    def run(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """Analyze a tactical question and return structured guidance.

        Returns a dict with keys: answer, citations, confidence, from_cache, stored_key.
        """
        # Check if we've answered this before
        cache_key = f"tactical:{query.lower().strip()}"
        cached = self.recall(cache_key)
        if cached:
            return {
                "answer": cached.get("answer", ""),
                "citations": cached.get("citations", []),
                "confidence": cached.get("confidence", 0.0),
                "from_cache": True,
                "stored_key": cache_key,
            }

        # Analyze the query
        analysis = self._analyze(query)

        # Store in memory (TTL: 7 days - tactical context is shorter-lived than research)
        self.remember(
            cache_key,
            {
                "answer": analysis["answer"],
                "citations": analysis["citations"],
                "confidence": analysis["confidence"],
                "query": query,
            },
            ttl_seconds=604800,
        )

        return {
            "answer": analysis["answer"],
            "citations": analysis["citations"],
            "confidence": analysis["confidence"],
            "from_cache": False,
            "stored_key": cache_key,
        }

    def _analyze(self, query: str) -> dict[str, Any]:
        """Perform tactical analysis based on query keywords."""
        query_lower = query.lower()

        # Extract formation mentions
        formation = self._extract_formation(query_lower)
        topic = self._extract_topic(query_lower)

        if not formation and not topic:
            return {
                "answer": "I can analyze tactical systems, formations, and space patterns. Try asking about specific formations (e.g., '4-3-3', '3-5-2') or tactical concepts like 'pressing', 'width', 'defensive line', or 'space occupation'.",
                "citations": [],
                "confidence": 0.0,
            }

        # Query tactical systems
        systems = self._get_systems(formation, topic)

        if not systems:
            answer = f"I don't have data on {'the ' + formation + ' formation' if formation else 'that tactical concept'} in the current catalogue. The tactical database is being expanded."
            return {"answer": answer, "citations": [], "confidence": 0.3}

        # Build analysis
        if formation and topic:
            answer = self._compare_systems(systems, formation, topic)
        elif formation:
            answer = self._describe_formation(systems, formation)
        else:
            answer = self._explain_concept(systems, topic)

        confidence = 0.85 if len(systems) >= 3 else 0.7
        citations = [{"type": "tactical_system", "count": len(systems)}]

        return {"answer": answer, "citations": citations, "confidence": confidence}

    def _extract_formation(self, query: str) -> str | None:
        """Extract formation pattern from query."""
        import re

        # Match common formations: 4-3-3, 3-5-2, 4-4-2, etc.
        match = re.search(r"\d-\d-\d(?:-\d)?", query)
        if match:
            return match.group(0)
        return None

    def _extract_topic(self, query: str) -> str | None:
        """Extract tactical topic from query."""
        topics = [
            "pressing",
            "width",
            "depth",
            "defensive line",
            "space",
            "transition",
            "build-up",
            "counter-attack",
            "possession",
            "compact",
            "narrow",
            "balance",
        ]
        for topic in topics:
            if topic in query:
                return topic
        return None

    def _get_systems(self, formation: str | None, topic: str | None) -> list[dict[str, Any]]:
        """Query tactical systems matching criteria."""
        stmt = select(TacticalSystem)

        if formation:
            stmt = stmt.where(TacticalSystem.formation == formation)

        rows = self.db.scalars(stmt).all()

        result = []
        for row in rows:
            result.append(
                {
                    "name": row.name,
                    "formation": row.formation,
                    "temperament": row.temperament_key,
                    "press_line_y": row.press_line_y,
                    "block_depth": row.block_depth,
                    "narrowing": row.defensive_narrowing,
                    "board": row.board,
                }
            )

        return result

    def _describe_formation(self, systems: list[dict], formation: str) -> str:
        """Describe characteristics of a specific formation."""
        count = len(systems)
        temperaments = set(s["temperament"] for s in systems)
        avg_press = sum(s["press_line_y"] for s in systems) / count if count else 0
        avg_depth = sum(s["block_depth"] for s in systems) / count if count else 0

        lines = [f"**{formation} Formation Analysis**", f"Based on {count} tactical system(s) in the database."]
        lines.append(f"\n**Temperament styles:** {', '.join(sorted(temperaments))}")
        lines.append(f"\n**Average press line:** {avg_press:.1f} (higher = more aggressive)")
        lines.append(f"**Average block depth:** {avg_depth:.1f} (lower = deeper defensive block)")

        # Add specific system details
        for sys in systems[:3]:  # Show top 3
            lines.append(f"\n- **{sys['name']}**: {sys['temperament']}, press={sys['press_line_y']:.1f}, depth={sys['block_depth']:.1f}")

        lines.append("\n\n*Tactical measurements are derived from stored coordinate geometry.*")
        return "\n".join(lines)

    def _compare_systems(self, systems: list[dict], formation: str, topic: str) -> str:
        """Compare systems on a specific tactical dimension."""
        topic_labels = {
            "pressing": ("press_line_y", "Press line height"),
            "width": ("narrowing", "Defensive narrowing"),
            "depth": ("block_depth", "Block depth"),
        }

        metric_key, metric_label = topic_labels.get(topic, (None, None))
        if not metric_key:
            return f"I can analyze {topic} but need more specific tactical parameters. Try asking about pressing intensity, defensive width, or build-up patterns."

        values = [(s["name"], s[metric_key]) for s in systems]
        values.sort(key=lambda x: x[1], reverse=True)

        lines = [f"**{formation} - {metric_label} Comparison**", f"Comparing {len(systems)} systems:"]

        for name, value in values:
            bar = "█" * int(value / 5) + "░" * (10 - int(value / 5))
            lines.append(f"- {name}: {value:.1f} [{bar}]")

        highest = values[0]
        lowest = values[-1]
        lines.append(f"\n**Most {topic}:** {highest[0]} ({highest[1]:.1f})")
        lines.append(f"**Least {topic}:** {lowest[0]} ({lowest[1]:.1f})")

        lines.append("\n\n*Values represent measured tactical geometry from stored coordinates.*")
        return "\n".join(lines)

    def _explain_concept(self, systems: list[dict], topic: str) -> str:
        """Explain a tactical concept using available systems as examples."""
        concept_explanations = {
            "pressing": "High pressing involves pushing the defensive line forward to compress space and win the ball early. Press line height (y-coordinate) indicates how aggressive the press is.",
            "width": "Width in attack stretches the opposition defense horizontally. Defensive narrowing measures how compact a team stays when defending - lower values mean wider defensive coverage.",
            "depth": "Block depth determines how deep a team sits. A low block depth means the team defends close to their own goal, while a high value indicates a high defensive line.",
            "space": "Space occupation is determined by player positioning relative to teammates and opponents. Balanced formations distribute players evenly across zones.",
            "transition": "Transitions involve rapid changes between attacking and defending. Systems with moderate press lines and flexible block depths handle transitions better.",
            "build-up": "Build-up play starts from deep positions. Systems with deeper press lines typically have more structured build-up patterns through midfield.",
            "counter-attack": "Counter-attacks exploit space left by the opposition. Compact defensive blocks with quick transition capabilities are key.",
            "possession": "Possession-based systems maintain shape and pass patiently. Balanced formations with good spacing facilitate possession retention.",
            "compact": "Compactness refers to vertical and horizontal distance between players. Narrower formations with similar press/block values are more compact.",
            "narrow": "Narrow formations concentrate players centrally, forcing play wide but creating central overloads.",
            "balance": "Balance measures how evenly distributed players are across the pitch. Well-balanced systems cover all zones without gaps.",
        }

        explanation = concept_explanations.get(topic, f"{topic.capitalize()} is a key tactical concept in modern football.")

        # Find relevant examples
        if topic in ["pressing", "depth"]:
            sorted_sys = sorted(systems, key=lambda s: s.get("press_line_y", 0), reverse=True)
            example_high = sorted_sys[0] if sorted_sys else None
            example_low = sorted_sys[-1] if sorted_sys else None

            lines = [
                f"**{topic.capitalize()} Analysis**",
                explanation,
                "",
            ]

            if example_high and example_low:
                lines.append(f"**High {topic} example:** {example_high['name']} ({example_high['press_line_y']:.1f})")
                lines.append(f"**Low {topic} example:** {example_low['name']} ({example_low['press_line_y']:.1f})")
                lines.append(f"\nDifference: {example_high['press_line_y'] - example_low['press_line_y']:.1f} units")

            lines.append(f"\n*Analysis based on {len(systems)} tactical systems in database.*")
            return "\n".join(lines)

        return f"**{topic.capitalize()}**\n\n{explanation}\n\n*Concept illustrated using {len(systems)} tactical systems from the database.*"
