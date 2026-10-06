"""Scout agent for M11 (spec §32).

Searches for players based on natural language requirements and generates structured
scouting reports. Uses the existing scouting.search and scouting.requirements modules
to parse queries, filter RealPlayer rows, and compute market valuations.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.agents.base import BaseAgent
from app.services.scouting.requirements import parse_requirements
from app.services.scouting.search import search


class ScoutAgent(BaseAgent):
    """Football scout agent that finds players matching requirements.

    Parses natural language scouting requests (e.g., "find me a 22-year-old left-footed
    striker under €20m"), searches the player database, and returns ranked candidates
    with market valuations. Persists searches in agent memory for shortlist building.
    """

    def run(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """Execute a scouting search and return ranked candidates.

        Returns a dict with keys: answer, citations, confidence, from_cache, stored_key.
        """
        # Check if we've answered this before
        cache_key = f"scout:{query.lower().strip()}"
        cached = self.recall(cache_key)
        if cached:
            return {
                "answer": cached.get("answer", ""),
                "citations": cached.get("citations", []),
                "confidence": cached.get("confidence", 0.0),
                "from_cache": True,
                "stored_key": cache_key,
            }

        # Parse and execute search
        result = self._search(query)

        # Store in memory (TTL: 7 days - scouting context is shorter-lived than research)
        self.remember(
            cache_key,
            {
                "answer": result["answer"],
                "citations": result["citations"],
                "confidence": result["confidence"],
                "query": query,
                "candidate_count": result.get("candidate_count", 0),
            },
            ttl_seconds=604800,
        )

        return {
            "answer": result["answer"],
            "citations": result["citations"],
            "confidence": result["confidence"],
            "from_cache": False,
            "stored_key": cache_key,
        }

    def _search(self, query: str) -> dict[str, Any]:
        """Parse query and search for matching players."""
        # Parse requirements from natural language
        try:
            parsed = parse_requirements(query)
        except Exception as exc:
            return {
                "answer": f"I couldn't understand any scouting requirements from your query: {exc}. Try phrases like 'left-footed striker', 'under 25 years old', 'budget €30m', or 'high potential midfielder'.",
                "citations": [],
                "confidence": 0.0,
            }

        if not parsed.requirements:
            return {
                "answer": "I couldn't understand any scouting requirements from your query. Try phrases like 'left-footed striker', 'under 25 years old', 'budget €30m', or 'high potential midfielder'.",
                "citations": [],
                "confidence": 0.0,
            }

        # Execute search
        try:
            search_result = search(self.db, parsed)
        except Exception as exc:
            return {
                "answer": f"Search failed: {exc}. The scouting database may not be fully populated.",
                "citations": [],
                "confidence": 0.0,
            }

        candidates = search_result.get("candidates", [])
        problems = search_result.get("problems", [])
        waterfall = search_result.get("waterfall", [])

        # Build answer
        if not candidates:
            answer_lines = [f"**No players found matching your criteria.**"]
            answer_lines.append(f"\n**Requirements parsed:**")
            for req in parsed.requirements:
                answer_lines.append(f"- {req.kind}: {req.value}")

            if problems:
                answer_lines.append(f"\n**Unrecognized requirements:**")
                for prob in problems:
                    answer_lines.append(f"- {prob}")

            answer_lines.append("\n\nTry relaxing some constraints or using different terminology.")
            answer = "\n".join(answer_lines)
            confidence = 0.5  # Understood query but no matches
        else:
            # Format candidate list
            limit = min(len(candidates), 10)  # Show top 10
            answer_lines = [f"**Found {len(candidates)} candidates. Top {limit}:**"]

            for i, candidate in enumerate(candidates[:limit], 1):
                player = candidate.player
                name = player.display_name
                age = player.age
                position = player.position
                overall = player.overall
                potential = player.potential
                value = candidate.market_value
                fee = candidate.transfer_fee

                answer_lines.append(
                    f"\n{i}. **{name}** ({age}yo, {position})"
                )
                answer_lines.append(f"   OVR: {overall}, POT: {potential}")
                answer_lines.append(f"   Value: €{value/1_000_000:.1f}M, Fee: €{fee/1_000_000:.1f}M")

            # Add requirement breakdown
            answer_lines.append(f"\n\n**Search criteria:**")
            for req in parsed.requirements:
                answer_lines.append(f"- {req.kind}: {req.value}")

            # Add waterfall if available
            if waterfall:
                answer_lines.append(f"\n**Filter breakdown:**")
                for step in waterfall:
                    answer_lines.append(f"- {step['requirement']}: {step['before']} → {step['after']}")

            if problems:
                answer_lines.append(f"\n**Ignored (not understood):**")
                for prob in problems:
                    answer_lines.append(f"- {prob}")

            answer_lines.append("\n\n*Market values computed from stored player attributes using published valuation formula.*")
            answer = "\n".join(answer_lines)
            confidence = 0.9 if len(candidates) >= 5 else 0.75

        citations = [
            {
                "type": "player_search",
                "requirements": str(len(parsed.requirements)),
                "candidates_found": str(len(candidates)),
            }
        ]

        return {
            "answer": answer,
            "citations": citations,
            "confidence": confidence,
            "candidate_count": len(candidates),
        }
