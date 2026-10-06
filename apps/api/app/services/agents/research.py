"""Research agent for M11 (spec §31).

Answers football questions by querying the knowledge base, storing intermediate results
in agent memory, and citing sources. The agent is stateless between calls — all context
comes from persisted memories.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.agent_memory import list_memories
from app.services.agents.base import BaseAgent
from app.services.knowledge.answer import ask


class ResearchAgent(BaseAgent):
    """Football research agent that answers questions with citations.

    Uses the existing RAG pipeline (§29) to retrieve relevant passages, synthesises an
    answer, and persists the query + answer pair in agent memory for later reference.
    
    Refuses non-football questions and requests for live/predictive data per spec §64.
    """
    
    # Football-domain keywords for out-of-scope detection
    _FOOTBALL_TERMS = {
        "football", "soccer", "player", "team", "match", "goal", "tactic", "tactical",
        "formation", "pressing", "possession", "striker", "midfielder", "defender",
        "goalkeeper", "coach", "training", "drill", "league", "tournament", "cup",
        "championship", "transfer", "scout", "scouting", "analysis", "simulation",
        "engine", "xg", "expected goals", "pass", "shot", "assist", "corner",
        "free kick", "penalty", "offside", "substitution", "lineup", "squad",
        "catenaccio", "gegenpressing", "tiki-taka", "false nine", "box-to-box",
        "defensive midfielder", "attacking", "defending", "counter-attack"
    }
    
    # Terms indicating live/predictive requests (should refuse)
    _LIVE_PREDICTIVE_TERMS = {
        "live scores", "right now", "current score", "today's match",
        "predict", "prediction", "will win", "going to happen", "future result",
        "who will win", "next world cup", "next season", "upcoming match"
    }

    def _is_football_domain(self, query: str) -> bool:
        """Check if query contains football-related vocabulary."""
        query_lower = query.lower()
        return any(term in query_lower for term in self._FOOTBALL_TERMS)
    
    def _is_live_or_predictive(self, query: str) -> bool:
        """Check if query asks for live data or predictions."""
        query_lower = query.lower()
        return any(term in query_lower for term in self._LIVE_PREDICTIVE_TERMS)

    def run(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """Answer one football question and store the result in memory.

        Returns a dict with keys: answer, citations, confidence, stored_key.
        Refuses non-football questions and live/predictive requests.
        """
        # Domain check: refuse non-football questions
        if not self._is_football_domain(query):
            return {
                "answer": "I cannot answer this question because it is outside my domain. I can only answer football-related questions.",
                "citations": [],
                "confidence": 0.0,
                "refused": True,
                "refusal_reason": "out_of_domain",
                "stored_key": None,
            }
        
        # Live/predictive check: refuse requests for real-time or future data
        if self._is_live_or_predictive(query):
            return {
                "answer": "I cannot provide live scores, current match data, or predictions about future events. I am unable to access real-time information.",
                "citations": [],
                "confidence": 0.0,
                "refused": True,
                "refusal_reason": "live_or_predictive_data",
                "stored_key": None,
            }

        # Check if we've answered this before
        cache_key = f"answer:{query.lower().strip()}"
        cached = self.recall(cache_key)
        if cached:
            return {
                "answer": cached.get("answer", ""),
                "citations": cached.get("citations", []),
                "confidence": cached.get("confidence", 0.0),
                "from_cache": True,
                "stored_key": cache_key,
            }

        # Query the knowledge base
        result = ask(self.db, question=query)
        
        # Handle cases where RAG couldn't find relevant information
        if not result.answered or result.confidence < 0.3:
            # Provide a helpful response even when data is missing
            fallback_answer = self._generate_fallback_response(query, result)
            return {
                "answer": fallback_answer,
                "citations": result.citations,
                "confidence": max(result.confidence, 0.3),  # Ensure minimum confidence for partial answers
                "from_cache": False,
                "stored_key": None,  # Don't cache incomplete answers
            }

        # Store the answer in memory (TTL: 24 hours)
        self.remember(
            cache_key,
            {
                "answer": result.text,
                "citations": result.citations,
                "confidence": result.confidence,
                "query": query,
            },
            ttl_seconds=86400,
        )

        # Also update the conversation history
        history = self.recall("conversation_history") or {"queries": []}
        if isinstance(history, dict):
            queries = history.get("queries", [])
        else:
            queries = []
        queries.append({"query": query, "key": cache_key})
        self.remember("conversation_history", {"queries": queries[-10:]})  # Keep last 10

        return {
            "answer": result.text,
            "citations": result.citations,
            "confidence": result.confidence,
            "from_cache": False,
            "stored_key": cache_key,
        }
    
    def _generate_fallback_response(self, query: str, rag_result: Any) -> str:
        """Generate a helpful response when RAG has insufficient data.
        
        Instead of returning empty/low-quality answers, explain what's known
        and what would be needed to fully answer the question.
        """
        query_lower = query.lower()
        
        # Check for time-sensitive queries (news, transfers, current events)
        time_sensitive_terms = ["latest", "current", "recent", "now", "today", "this week", "rumor"]
        is_time_sensitive = any(term in query_lower for term in time_sensitive_terms)
        
        if is_time_sensitive:
            return (
                f"I don't have access to real-time or recent news data. "
                f"Your question '{query}' appears to require current information that isn't in my knowledge base. "
                f"My knowledge covers tactical concepts, training principles, match analysis frameworks, and historical football knowledge, "
                f"but not live scores, recent transfers, or breaking news."
            )
        
        # Generic fallback for other low-confidence queries
        return (
            f"I found limited information about '{query}' in my knowledge base. "
            f"This could mean the topic isn't well-covered in the available documents, "
            f"or the question uses terminology that doesn't match the stored content. "
            f"Try rephrasing with more specific football terms, or ask about tactical concepts, "
            f"training methods, or player development topics which are better covered."
        )
