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
    """

    def run(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """Answer one football question and store the result in memory.

        Returns a dict with keys: answer, citations, confidence, stored_key.
        """
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
