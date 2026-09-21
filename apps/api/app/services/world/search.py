"""Unified search across the generated world (spec §56 SEARCH: one box, typed results).

Ranking is deliberately explainable rather than clever: a row scores on how much of the query its
own words cover, weighted by where they appear (name > subtitle > body), with a small boost for the
stored quality figure so a club called "Viremont" outranks a fringe player called "Viremont". Every
hit reports its reasons. Nothing is embedded and no provider is called — the world is ~950 rows, so
an honest term-overlap score beats an opaque one and behaves identically on SQLite and PostgreSQL.

Each hit also carries its canonical web path (spec §80) and its provenance flags, so a client can
link straight to the page and cannot render a result without also rendering "DEMO DATA".
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from app.models import Competition, NewsArticle, RealMatch, RealPlayer, Team
from app.services.knowledge.text import content_words
from app.services.world.plan import SEO_ROUTES, web_path, world_id

RESULT_TYPES: Final[dict[str, str]] = {
    "players": "player",
    "teams": "team",
    "competitions": "competition",
    "matches": "match",
    "news": "article",
}
ALIASES: Final[dict[str, str]] = {
    "player": "players",
    "players": "players",
    "team": "teams",
    "teams": "teams",
    "club": "teams",
    "competition": "competitions",
    "competitions": "competitions",
    "league": "competitions",
    "cup": "competitions",
    "match": "matches",
    "matches": "matches",
    "fixture": "matches",
    "fixtures": "matches",
    "news": "news",
    "article": "news",
    "articles": "news",
}
NAME_WEIGHT: Final = 3.0
SUBTITLE_WEIGHT: Final = 1.5
BODY_WEIGHT: Final = 1.0
EXACT_PHRASE_BONUS: Final = 6.0
POPULARITY_WEIGHT: Final = 0.5


@dataclass(frozen=True)
class SearchHit:
    """One typed result: what it is, where it lives, why it ranked."""

    type: str
    slug: str
    id: str
    title: str
    subtitle: str
    score: float
    path: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "slug": self.slug,
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "score": round(self.score, 4),
            "path": self.path,
            "reasons": list(self.reasons),
            "data_origin": "synthetic",
            "is_demo_data": True,
        }


@dataclass(frozen=True)
class _Source:
    name: str
    kind: str
    model: Any
    filter_columns: tuple[str, ...]
    popularity: str = ""

    def statement(self, terms: Sequence[str]) -> Any:
        clauses = [getattr(self.model, column).like(f"%{term}%") for column in self.filter_columns for term in terms]
        return select(self.model).where(or_(*clauses))


def _terms(text: str) -> list[str]:
    return content_words(text)


def _score(query: Sequence[str], name: str, subtitle: str, body: str) -> tuple[float, list[str]]:
    """Coverage-weighted term overlap; a row matching nothing scores 0 and gets dropped."""
    name_terms = set(_terms(name))
    subtitle_terms = set(_terms(subtitle))
    body_terms = set(_terms(body))
    score = 0.0
    reasons: list[str] = []
    for term in query:
        weight = NAME_WEIGHT if term in name_terms else SUBTITLE_WEIGHT if term in subtitle_terms else BODY_WEIGHT if term in body_terms else 0.0
        if weight:
            score += weight
            reasons.append(f"matched '{term}'")
    phrase = " ".join(query)
    haystack = " ".join([name, subtitle, body]).lower()
    if len(query) > 1 and phrase in haystack:
        score += EXACT_PHRASE_BONUS
        reasons.append(f"'{phrase}' appears verbatim")
    if len(query) > 1 and score:
        score *= len(set(query)) / len(query)
    return score, reasons


def _describe_players(row: RealPlayer) -> tuple[str, str, str]:
    return (
        row.name,
        f"{row.position} · {row.nation} · overall {row.overall}",
        " ".join([row.slug, row.nation, row.archetype, row.summary, str(row.goals), str(row.assists)]),
    )


def _describe_teams(row: Team) -> tuple[str, str, str]:
    return (row.name, f"{row.short_name} · {row.city} · {row.formation}", " ".join([row.slug, row.city, row.stadium, row.nation, row.manager_name, row.summary]))


def _describe_competitions(row: Competition) -> tuple[str, str, str]:
    return (row.name, f"{row.kind} · {row.region}", " ".join([row.slug, row.region, row.kind, row.summary]))


def _describe_news(row: NewsArticle) -> tuple[str, str, str]:
    return (row.title, f"{row.category} · {row.claim_class}", " ".join([row.slug, row.summary, row.haystack, row.author or ""]))


def _describe_match(row: RealMatch, home_name: str, away_name: str) -> tuple[str, str, str]:
    score = f"{row.home_goals}-{row.away_goals}" if row.status == "completed" and row.home_goals is not None else "not played"
    return (f"{home_name} v {away_name}", f"{score} · {row.round_label} · {row.season}", " ".join([row.slug, row.haystack, row.summary, score]))


SOURCES: Final[dict[str, _Source]] = {
    "players": _Source("players", "player", RealPlayer, ("name", "slug", "nation", "position", "archetype", "summary"), popularity="overall"),
    "teams": _Source("teams", "team", Team, ("name", "slug", "short_name", "city", "stadium", "nation", "summary"), popularity="overall"),
    "competitions": _Source("competitions", "competition", Competition, ("name", "slug", "region", "kind", "summary")),
    "news": _Source("news", "article", NewsArticle, ("title", "slug", "haystack", "summary", "category", "claim_class")),
    "matches": _Source("matches", "match", RealMatch, ("slug", "haystack", "summary", "round_label", "season")),
}


def _requested(types: Sequence[str] | None) -> list[str]:
    if not types:
        return list(SOURCES)
    wanted = {ALIASES.get(str(item).strip().lower(), "") for item in types}
    resolved = [name for name in SOURCES if name in wanted]
    return resolved or list(SOURCES)


def search_world(session: Session, query: str, *, types: Sequence[str] | None = None, limit: int = 20) -> list[SearchHit]:
    """Typed, ranked results across players, teams, competitions, matches and news."""
    terms = _terms(query)
    if not terms:
        return []
    hits: list[SearchHit] = []
    for name in _requested(types):
        source = SOURCES[name]
        if name == "matches":
            home, away = aliased(Team), aliased(Team)
            statement = (
                select(RealMatch, home.name, away.name)
                .join(home, home.id == RealMatch.home_team_id)
                .join(away, away.id == RealMatch.away_team_id)
                .where(or_(*[RealMatch.haystack.like(f"%{term}%") for term in terms]))
            )
            pairs = [(row, home_name, away_name) for row, home_name, away_name in session.execute(statement).all()]
        else:
            pairs = [(row, "", "") for row in session.scalars(source.statement(terms)).all()]
        for row, home_name, away_name in pairs:
            if name == "matches":
                title, subtitle, body = _describe_match(row, home_name or "", away_name or "")
            elif name == "news":
                title, subtitle, body = _describe_news(row)
            elif name == "players":
                title, subtitle, body = _describe_players(row)
            elif name == "teams":
                title, subtitle, body = _describe_teams(row)
            else:
                title, subtitle, body = _describe_competitions(row)
            score, reasons = _score(terms, title, subtitle, body)
            if score <= 0:
                continue
            slug = str(row.slug or "")
            if source.popularity:
                score += min(float(getattr(row, source.popularity) or 0) / 100.0, 1.0) * POPULARITY_WEIGHT
            reasons.append("synthetic demo world — matches no real entity")
            hits.append(
                SearchHit(
                    type=source.kind,
                    slug=slug,
                    id=str(row.id or world_id(source.kind, slug)),
                    title=title,
                    subtitle=subtitle,
                    score=score,
                    path=web_path(source.kind, slug),
                    reasons=tuple(reasons),
                )
            )
    hits.sort(key=lambda hit: (-hit.score, hit.type, hit.slug))
    return hits[: max(1, limit)]


__all__ = ["RESULT_TYPES", "SEO_ROUTES", "SOURCES", "SearchHit", "search_world", "web_path"]
