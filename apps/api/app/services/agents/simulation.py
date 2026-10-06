"""Simulation agent for M11 (spec §32).

Explains the deterministic match simulation engine, interprets match reports, and answers
questions about what the model does/doesn't simulate. Uses the existing simulation.engine
module to access coefficients, formulas, and calibration notes.
"""

from __future__ import annotations

from typing import Any

from app.services.agents.base import BaseAgent
from app.services.simulation.engine import (
    CALIBRATION_NOTE,
    COEFFICIENTS,
    ENGINE_NAME,
    ENGINE_VERSION,
    SIMULATION_DISCLAIMER,
)


class SimulationAgent(BaseAgent):
    """Football simulation agent that explains match modeling.

    Answers questions about the deterministic simulation engine: how it works, what it
    models (possession, shots, xG, goals, cards), what it doesn't model (substitutions,
    dynamic possession shifts), and how to interpret simulation reports. Persists
    explanations in agent memory for follow-up questions.
    """

    def run(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """Answer a question about football simulation.

        Returns a dict with keys: answer, citations, confidence, from_cache, stored_key.
        """
        # Check if we've answered this before
        cache_key = f"simulation:{query.lower().strip()}"
        cached = self.recall(cache_key)
        if cached:
            return {
                "answer": cached.get("answer", ""),
                "citations": cached.get("citations", []),
                "confidence": cached.get("confidence", 0.0),
                "from_cache": True,
                "stored_key": cache_key,
            }

        # Analyze and answer
        result = self._analyze(query)

        # Store in memory (TTL: 7 days)
        self.remember(
            cache_key,
            {
                "answer": result["answer"],
                "citations": result["citations"],
                "confidence": result["confidence"],
                "query": query,
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

    def _analyze(self, query: str) -> dict[str, Any]:
        """Analyze simulation-related query."""
        query_lower = query.lower()

        # Determine topic
        if any(word in query_lower for word in ["how", "work", "engine", "model"]):
            return self._explain_engine()
        elif any(word in query_lower for word in ["xg", "expected goal", "chance"]):
            return self._explain_xg()
        elif any(word in query_lower for word in ["possession", "ball", "minute"]):
            return self._explain_possession()
        elif any(word in query_lower for word in ["press", "pressing", "turnover"]):
            return self._explain_pressing()
        elif any(word in query_lower for word in ["card", "yellow", "red", "foul"]):
            return self._explain_cards()
        elif any(word in query_lower for word in ["not model", "doesn't", "limitation", "deliberately"]):
            return self._explain_limitations()
        elif any(word in query_lower for word in ["deterministic", "reproducible", "seed", "same"]):
            return self._explain_determinism()
        elif any(word in query_lower for word in ["coefficient", "formula", "rate", "constant"]):
            return self._explain_coefficients()
        else:
            return self._general_overview()

    def _explain_engine(self) -> dict[str, Any]:
        """Explain how the simulation engine works."""
        answer = f"""**{ENGINE_NAME} v{ENGINE_VERSION} - Match Simulation Engine**

The simulation engine models a 90-minute football match deterministically:

**Core approach:**
- Possession is divided into ball-minutes based on squad attributes and tactical systems
- Each ball-minute generates passes, shots, and pressing events at modeled rates
- Shots are classified as big chances, normal chances, or long-range attempts
- Each shot has its own xG probability, and actual goals are Bernoulli draws (can differ from xG)
- Cards and injuries occur at rates dependent on fouls and pressing intensity

**What makes it deterministic:**
- Same seed + same input squads = same output every time
- Uses WorldRng (not Python's random) for cross-version reproducibility
- Every rate names its formula in the report's model.factors field

**Calibration:**
{CALIBRATION_NOTE}

*{SIMULATION_DISCLAIMER}*"""

        citations = [{"type": "simulation_engine", "version": f"{ENGINE_NAME}@{ENGINE_VERSION}"}]
        return {"answer": answer, "citations": citations, "confidence": 0.95}

    def _explain_xg(self) -> dict[str, Any]:
        """Explain expected goals modeling."""
        answer = f"""**Expected Goals (xG) in the Simulation**

The engine distinguishes between xG and actual goals:

**Chance types and their base xG:**
- Big chance: {COEFFICIENTS['xg_big_chance']:.0%} xG
- Normal chance: {COEFFICIENTS['xg_normal_chance']:.0%} xG
- Long range: {COEFFICIENTS['xg_long_range']:.1%} xG

**How chances are generated:**
- Shot rate: {COEFFICIENTS['shot_rate_per_ball_minute']:.2f} shots per ball-minute
- Chance distribution: 14% big, 62% normal, 24% long-range
- Transition bonus: xG multiplied by {COEFFICIENTS['xg_transition_bonus']:.2f}x

**Goals vs xG:**
Each shot is a Bernoulli draw on its modeled probability. A team can finish above or below its xG — this is intentional. The report prints both values so you can see the gap.

**On-target conversion:**
- Base on-target rate: {COEFFICIENTS['on_target_base']:.0%}
- Slope based on xG: {COEFFICIENTS['on_target_xg_slope']:.0%} additional per unit xG

*{SIMULATION_DISCLAIMER}*"""

        citations = [{"type": "xg_model", "coefficients_count": str(len(COEFFICIENTS))}]
        return {"answer": answer, "citations": citations, "confidence": 0.95}

    def _explain_possession(self) -> dict[str, Any]:
        """Explain possession modeling."""
        answer = f"""**Possession Modeling**

The engine divides 90 minutes into ball-minutes for each team:

**How possession share is calculated:**
- Based on squad attribute means (technical, physical, mental)
- Tactical system geometry affects spacing and passing options
- Possession share is computed before the match starts and remains fixed

**What happens during ball-minutes:**
- Passes: {COEFFICIENTS['passes_per_ball_minute']:.1f} per ball-minute
- Shots: {COEFFICIENTS['shot_rate_per_ball_minute']:.2f} per ball-minute
- Fouls: {COEFFICIENTS['fouls_per_ball_minute']:.3f} per ball-minute

**What possession does NOT do:**
- Does not shift dynamically with the scoreline
- Does not change when a team goes down to 10 men (but attack/concede rates do adjust)
- Is a pre-match calculation, not a live simulation

**Late match effects:**
- Shot drift: {COEFFICIENTS['late_match_shot_drift']:.0%} increase in final phase
- xG drift: {COEFFICIENTS['late_match_xg_drift']:.0%} increase in final phase
- Fatigue slope: {COEFFICIENTS['fatigue_slope']:.2f} effect on performance

*{SIMULATION_DISCLAIMER}*"""

        citations = [{"type": "possession_model", "key_rates": "3"}]
        return {"answer": answer, "citations": citations, "confidence": 0.95}

    def _explain_pressing(self) -> dict[str, Any]:
        """Explain pressing and turnover modeling."""
        answer = f"""**Pressing and Turnover Modeling**

The engine models pressing as attempts to win the ball back:

**Pressing rates:**
- Press attempts: {COEFFICIENTS['press_attempts_per_opp_ball_minute']:.2f} per opponent ball-minute
- Press conversion base: {COEFFICIENTS['press_conversion_base']:.0%} success rate
- Press conversion slope: {COEFFICIENTS['press_conversion_slope']:.2f} additional per unit advantage

**Turnover outcomes:**
- High turnover share: {COEFFICIENTS['high_turnover_share']:.0%} of turnovers lead to dangerous positions
- Press shot share: {COEFFICIENTS['press_shot_share']:.0%} of high turnovers result in shots
- Transition share: {COEFFICIENTS['transition_share']:.0%} of possessions start from transitions
- Transition shot share: {COEFFICIENTS['transition_shot_share']:.0%} of transitions result in shots

**Pressing costs:**
- Increases foul rate via yellow_per_foul_press_slope: +{COEFFICIENTS['yellow_per_foul_press_slope']:.3f} per press attempt
- Higher pressing intensity = more fatigue accumulation

*{SIMULATION_DISCLAIMER}*"""

        citations = [{"type": "pressing_model", "parameters": "6"}]
        return {"answer": answer, "citations": citations, "confidence": 0.95}

    def _explain_cards(self) -> dict[str, Any]:
        """Explain card and injury modeling."""
        answer = f"""**Cards and Injury Modeling**

**Fouls:**
- Rate: {COEFFICIENTS['fouls_per_ball_minute']:.3f} fouls per ball-minute
- Increases with pressing intensity

**Yellow cards:**
- Base rate: {COEFFICIENTS['yellow_per_foul_base']:.1%} per foul
- Additional slope: +{COEFFICIENTS['yellow_per_foul_press_slope']:.3f} per press attempt
- Total yellow rate depends on both fouls and pressing intensity

**Red cards:**
- Rate: {COEFFICIENTS['red_per_foul']:.1%} per foul
- Very rare event (< 1% per foul)

**Injuries:**
- Rate: {COEFFICIENTS['injury_rate_per_minute']:.4f} per minute
- Approximately 0.14 injuries per 100 minutes across both teams
- Not affected by pressing or foul count directly

**Man-down effects:**
- Attack rate multiplier: {COEFFICIENTS['man_down_attack']:.2f}x (reduced)
- Concede rate multiplier: {COEFFICIENTS['man_down_concede']:.2f}x (increased)

*{SIMULATION_DISCLAIMER}*"""

        citations = [{"type": "cards_injury_model", "rates": "4"}]
        return {"answer": answer, "citations": citations, "confidence": 0.95}

    def _explain_limitations(self) -> dict[str, Any]:
        """Explain what the engine deliberately does not model."""
        answer = f"""**What the Simulation Engine Does NOT Model**

The engine is transparent about its limitations:

**Deliberately excluded:**
1. **Dynamic possession shifts** - Possession share is calculated pre-match and stays fixed. It does not change when a team scores or concedes.

2. **Substitutions** - No player changes during the match. All 90 minutes are played by the starting XI.

3. **Tactical adjustments** - Teams cannot change formation or strategy mid-match based on the scoreline.

4. **Momentum effects** - No "confidence boost" after scoring or "desperation" when trailing.

5. **Weather/pitch conditions** - All matches are played under identical ideal conditions.

6. **Individual brilliance** - No single player can exceed their attribute-based contribution.

**Why these exclusions:**
- Keeps the model auditable and reproducible
- Prevents over-fitting to real-world narratives
- Makes every factor traceable to published formulas

These limitations are listed in every simulation report under `model.what_it_does_not_model`.

*{SIMULATION_DISCLAIMER}*"""

        citations = [{"type": "limitations", "exclusions": "6"}]
        return {"answer": answer, "citations": citations, "confidence": 0.95}

    def _explain_determinism(self) -> dict[str, Any]:
        """Explain deterministic nature of the engine."""
        answer = f"""**Deterministic Simulation**

The engine is fully deterministic:

**Same inputs = same outputs:**
- Same seed value
- Same squad attributes
- Same tactical systems
- Same version ({ENGINE_VERSION})

→ Identical match report every time

**How this is achieved:**
- Uses WorldRng instead of Python's random module
- Python's random.sample/shuffle internals change between versions
- WorldRng provides stable cross-version reproducibility

**Reproducibility across:**
- Different processes
- Different database engines (SQLite and PostgreSQL)
- Different machines

**When results differ:**
- Different seed value
- Different squad composition
- Engine version upgrade (would be noted in report)

**Why determinism matters:**
- Allows fair comparison between tactical setups
- Enables "what-if" analysis with controlled variables
- Makes the model auditable and debuggable

*{SIMULATION_DISCLAIMER}*"""

        citations = [{"type": "determinism", "rng": "WorldRng"}]
        return {"answer": answer, "citations": citations, "confidence": 0.95}

    def _explain_coefficients(self) -> dict[str, Any]:
        """Explain the coefficient system."""
        answer = f"""**Simulation Coefficients**

The engine uses {len(COEFFICIENTS)} authored constants:

**Key coefficients:**
- Shot rate: {COEFFICIENTS['shot_rate_per_ball_minute']:.2f}/min
- Pass rate: {COEFFICIENTS['passes_per_ball_minute']:.1f}/min
- Press conversion: {COEFFICIENTS['press_conversion_base']:.0%} base + {COEFFICIENTS['press_conversion_slope']:.2f} slope
- xG big chance: {COEFFICIENTS['xg_big_chance']:.0%}
- xG normal: {COEFFICIENTS['xg_normal_chance']:.0%}
- xG long range: {COEFFICIENTS['xg_long_range']:.1%}

**Where they come from:**
{CALIBRATION_NOTE}

**Transparency:**
Every coefficient is published in the code. The report's `model.factors` field shows which formulas were used for each metric.

**Can they be changed?**
Yes, but doing so would change all simulation results. The current values represent the project's best estimate of realistic football dynamics without fitting to real match data.

*{SIMULATION_DISCLAIMER}*"""

        citations = [{"type": "coefficients", "count": str(len(COEFFICIENTS))}]
        return {"answer": answer, "citations": citations, "confidence": 0.95}

    def _general_overview(self) -> dict[str, Any]:
        """Provide general overview of simulation capabilities."""
        answer = f"""**Football Match Simulation Overview**

I can explain the deterministic match simulation engine ({ENGINE_NAME} v{ENGINE_VERSION}).

**Topics I can cover:**
- How the engine works (possession blocks, shot generation, goal modeling)
- Expected goals (xG) vs actual goals
- Possession modeling and ball-minutes
- Pressing and turnover mechanics
- Card and injury rates
- What the engine deliberately does NOT model
- Why the simulation is deterministic
- The coefficient system and formulas

**Try asking:**
- "How does the simulation engine work?"
- "Explain xG in the simulation"
- "What does the engine not model?"
- "How is pressing modeled?"
- "Why is the simulation deterministic?"

*{SIMULATION_DISCLAIMER}*"""

        citations = [{"type": "simulation_overview", "engine": f"{ENGINE_NAME}@{ENGINE_VERSION}"}]
        return {"answer": answer, "citations": citations, "confidence": 0.85}
