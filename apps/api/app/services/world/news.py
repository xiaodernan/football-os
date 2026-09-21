"""The generated newsroom: template prose over rows the builder already produced.

Spec §25 asks for title / source / published-at / author / url / summary / entities / topics, and
spec §26 asks that fact, analysis and speculation never blur together. Both are honoured
structurally rather than in prose:

* an article can only quote a number that exists in `real_matches`, `real_player_match_stats` or
  `real_players`, so a headline cannot drift away from the fixtures page beside it;
* `claim_class` labels the article's dominant register and the body keeps three labelled
  sections, so a reader can see which sentences describe the fiction, which interpret it and
  which are explicitly guesses about it;
* the byline is a desk, not a person, and `source_name` is the generator itself — there is no
  provider call, no crawl and nothing external to cite (spec §62, `AI_POLICY.md`).

Quotas are sized off the world the builder actually makes (122 played fixtures, 8 scheduled,
20 clubs, 300 players, 10 competitions), so every article has a distinct subject and the total
lands exactly on the spec §65 gate of 500.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Final

from app.models import WORLD_DISCLAIMER
from app.services.world.names import slugify
from app.services.world.plan import Planned, web_path, world_id
from app.services.world.rng import WorldRng

if TYPE_CHECKING:
    from app.services.world.builder import WorldDraft, _Club, _Fixture

NEWS_QUOTAS: Final[dict[str, int]] = {
    "match_report": 122,
    "tactical_analysis": 80,
    "player_spotlight": 150,
    "team_news": 60,
    "transfer_note": 60,
    "competition_note": 20,
    "match_preview": 8,
}

DESKS: Final[dict[str, str]] = {
    "match_report": "Synthetic World match desk",
    "tactical_analysis": "Synthetic World tactics desk",
    "player_spotlight": "Synthetic World player desk",
    "team_news": "Synthetic World club desk",
    "transfer_note": "Synthetic World transfers desk",
    "competition_note": "Synthetic World competitions desk",
    "match_preview": "Synthetic World fixtures desk",
}

TOPICS: Final[dict[str, tuple[str, ...]]] = {
    "match_report": ("match report", "results", "generated world"),
    "tactical_analysis": ("tactics", "possession", "formations"),
    "player_spotlight": ("player profile", "attributes", "form"),
    "team_news": ("club news", "selection", "squad"),
    "transfer_note": ("transfer speculation", "links", "contracts"),
    "competition_note": ("competition", "standings", "format"),
    "match_preview": ("fixture preview", "fixtures"),
}

CLAIM_CLASS: Final[dict[str, str]] = {
    "match_report": "fact",
    "competition_note": "fact",
    "team_news": "fact",
    "tactical_analysis": "analysis",
    "player_spotlight": "analysis",
    "transfer_note": "speculation",
    "match_preview": "speculation",
}

# Bodies are written "after" the season the builder simulated, so the feed has a fixed editorial
# today instead of a wall clock — which is what keeps two generation runs byte-identical.
NEWS_ANCHOR: Final = dt.datetime(2026, 12, 28, 9, 0, tzinfo=dt.UTC)
TEAM_ANGLES: Final = ("selection", "squad update", "run-in")
TRANSFER_ANGLES: Final = ("link", "contract talk", "loan interest")
COMPETITION_ANGLES: Final = ("season review", "format note")
ENTITY_KINDS: Final = {"competitions": "competition", "teams": "team", "players": "player", "matches": "match"}
NOTICE: Final = "Synthetic demo data: this item was generated locally from the FOOTBALL OS world seed. It names no real person, club, competition or event and reports nothing measured."


def _slug_key(*parts: str) -> str:
    """A URL-safe natural key inside the slug column, still unique when it has to be shortened."""
    raw = slugify("-".join(parts))
    if len(raw) <= 200:
        return raw
    return f"{raw[:180]}-{world_id('article', raw)[-12:]}"


def _sections(fact: str, analysis: str, speculation: str) -> str:
    return "\n\n".join(
        [
            f"Fact about this generated world: {fact}",
            f"Analysis: {analysis}" if analysis else "Analysis: no claim in this band.",
            f"Speculation: {speculation}" if speculation else "Speculation: no claim in this band.",
            NOTICE,
            WORLD_DISCLAIMER,
        ]
    )


def _named(items: list[str], empty: str) -> str:
    return ", ".join(items) if items else empty


def _goal_lines(fixture: _Fixture, side: str) -> str:
    return _named([f"{line.player.name} {line.goals}" for line in fixture.lines if line.side == side and line.goals > 0], "none")


def _team_fixtures(draft: WorldDraft, club: _Club, played: bool = True) -> list[_Fixture]:
    source = draft.played() if played else draft.upcoming()
    return [fixture for fixture in source if club.slug in (fixture.home.slug, fixture.away.slug)]


class _Emitter:
    """Collects articles plus their entity edges, one natural key per (category, subject)."""

    def __init__(self, seed: int) -> None:
        self.articles: list[Planned] = []
        self.links: list[Planned] = []
        self._seen: set[str] = set()
        self._rng = WorldRng(seed).fork("news-order")

    def add(
        self,
        *,
        category: str,
        key: str,
        title: str,
        summary: str,
        body: str,
        season: str,
        entities: dict[str, list[str]],
        published_at: dt.datetime,
    ) -> None:
        slug = _slug_key(key)
        if slug in self._seen:
            raise ValueError(f"duplicate article natural key: {slug}")
        self._seen.add(slug)
        article_id = world_id("article", slug)
        topics = list(TOPICS[category])
        entities_norm: dict[str, list[str]] = {group: sorted(dict.fromkeys(values)) for group, values in entities.items()}
        payload = {
            "slug": slug,
            "title": title[:300],
            "summary": summary,
            "body": body,
            "category": category,
            "claim_class": CLAIM_CLASS[category],
            "season": season,
            "source_name": "synthetic-world",
            "url": web_path("article", slug),
            "author": DESKS[category],
            "published_at": published_at,
            "entities": entities_norm,
            "topics": topics,
            "haystack": " ".join([title, summary, category, season, *topics, *(value for values in entities_norm.values() for value in values)]).lower(),
        }
        self.articles.append(Planned(natural_key=slug, payload=payload))
        for group, values in entities_norm.items():
            kind = ENTITY_KINDS[group]
            for entity_slug in values:
                self.links.append(
                    Planned(
                        natural_key=f"{slug}|{kind}|{entity_slug}",
                        payload={
                            "article_id": article_id,
                            "entity_type": kind,
                            "entity_slug": entity_slug[:200],
                            "entity_id": world_id(kind, entity_slug),
                        },
                    )
                )

    def stamp(self, index: int, *, hours: int) -> dt.datetime:
        """A deterministic publication time walking back from the editorial anchor."""
        local = self._rng.fork(f"offset-{index}")
        return NEWS_ANCHOR - dt.timedelta(hours=hours * index + local.randint(0, max(hours - 1, 0)))


def _match_reports(emitter: _Emitter, draft: WorldDraft) -> None:
    played = sorted(draft.played(), key=lambda fixture: (fixture.kickoff, fixture.slug))
    for fixture in played[: NEWS_QUOTAS["match_report"]]:
        stats = fixture.stats
        edge = float(stats["possession"]["home"]) - float(stats["possession"]["away"])
        best = max(fixture.lines, key=lambda line: (line.rating, line.player.slug), default=None)
        scoreline = f"{fixture.home.name} {fixture.home_goals}-{fixture.away_goals} {fixture.away.name}"
        leader = "the hosts" if edge > 0 else "the visitors" if edge < 0 else "neither side"
        fact = (
            f"{scoreline} in the {fixture.competition.name} ({fixture.season}, {fixture.round_label}) at {fixture.venue}. "
            f"{fixture.home.short} goals: {_goal_lines(fixture, 'home')}. {fixture.away.short} goals: {_goal_lines(fixture, 'away')}. "
            f"Generated shots {stats['shots']['home']}-{stats['shots']['away']} "
            f"({stats['shots_on_target']['home']}-{stats['shots_on_target']['away']} on target), "
            f"discipline {stats['discipline']['home']}-{stats['discipline']['away']}."
        )
        analysis = (
            f"Possession split {stats['possession']['home']}/{stats['possession']['away']} left {leader} with a "
            f"{'clear' if abs(edge) >= 8 else 'marginal'} territorial edge, against seeded expected goals of "
            f"{stats['expected_goals']['home']:.2f}-{stats['expected_goals']['away']:.2f}. " + (f"{best.player.name} rated highest at {best.rating:.2f}." if best else "")
        )
        emitter.add(
            category="match_report",
            key=f"report-{fixture.slug}",
            title=scoreline,
            summary=f"{scoreline} — a generated result from the demo world's {fixture.competition.name}.",
            body=_sections(fact, analysis, "Nothing here projects forward; the demo world has no fixtures beyond its scheduled round."),
            season=fixture.season,
            entities={
                "competitions": [fixture.competition.slug],
                "teams": [fixture.home.slug, fixture.away.slug],
                "players": sorted({line.player.slug for line in fixture.lines}),
                "matches": [fixture.slug],
            },
            published_at=fixture.kickoff + dt.timedelta(hours=3),
        )


def _tactical_analysis(emitter: _Emitter, draft: WorldDraft) -> None:
    played = sorted(
        draft.played(),
        key=lambda fixture: (-abs(float(fixture.stats["possession"]["home"]) - float(fixture.stats["possession"]["away"])), fixture.slug),
    )
    for fixture in played[: NEWS_QUOTAS["tactical_analysis"]]:
        stats = fixture.stats
        hosts, visitors = (fixture.home, fixture.away) if int(fixture.home_goals or 0) >= int(fixture.away_goals or 0) else (fixture.away, fixture.home)
        fact = (
            f"{fixture.home.name} were set up in a {fixture.home.formation} against {fixture.away.name}'s {fixture.away.formation}, "
            f"and the stored score is {fixture.home_goals}-{fixture.away_goals} with generated possession "
            f"{stats['possession']['home']}/{stats['possession']['away']}."
        )
        analysis = (
            f"{visitors.name} produced {sum(line.shots for line in fixture.lines if line.team_slug == visitors.slug)} generated shots "
            f"against {hosts.name}'s {sum(line.shots for line in fixture.lines if line.team_slug == hosts.slug)}, and recorded "
            f"{sum(line.tackles + line.interceptions for line in fixture.lines if line.team_slug == visitors.slug)} defensive actions "
            f"to {hosts.name}'s {sum(line.tackles + line.interceptions for line in fixture.lines if line.team_slug == hosts.slug)}. "
            "That is a description of the seeded line-ups, not a verdict on a coaching staff."
        )
        emitter.add(
            category="tactical_analysis",
            key=f"tactics-{fixture.slug}",
            title=f"Tactical notes: {fixture.home.short} {fixture.home_goals}-{fixture.away_goals} {fixture.away.short}",
            summary=f"How {fixture.home.formation} and {fixture.away.formation} matched up in a generated {fixture.competition.name} fixture.",
            body=_sections(fact, analysis, ""),
            season=fixture.season,
            entities={
                "competitions": [fixture.competition.slug],
                "teams": [fixture.home.slug, fixture.away.slug],
                "players": sorted({line.player.slug for line in fixture.lines}),
                "matches": [fixture.slug],
            },
            published_at=fixture.kickoff + dt.timedelta(days=1),
        )


def _player_spotlights(emitter: _Emitter, draft: WorldDraft) -> None:
    ranked = sorted(draft.players, key=lambda player: (-player.overall, player.slug))
    played = sorted(draft.played(), key=lambda fixture: fixture.kickoff)
    for index, player in enumerate(ranked[: NEWS_QUOTAS["player_spotlight"]]):
        club = draft.club(player.club)
        scored = [
            f"{fixture.round_label}: {line.goals} goals, {line.assists} assists" for fixture in played for line in fixture.lines if line.player.slug == player.slug and line.goals + line.assists > 0
        ]
        fact = (
            f"{player.name}, {player.age}, {player.position} for {club.name} in the {draft.sizes.season} season of the "
            f"{draft.competition(club.league).name}: {player.appearances} appearances ({player.starts} starts), "
            f"{player.minutes} minutes, {player.goals} goals, {player.assists} assists, {player.clean_sheets} clean sheets, "
            f"{player.yellow_cards} yellow and {player.red_cards} red cards, average generated rating {player.rating:.2f}."
        )
        analysis = (
            f"Profiled as a {player.archetype} (template fit {player.archetype_match:.2f}) at overall {player.overall} with potential "
            f"{player.potential}; the form figure {player.form:.2f} is the mean of the last five stored stat lines. "
            + (f"Scored appearances: {_named(scored[:6], 'none')}." if scored else "This player has no stored line-ups.")
        )
        emitter.add(
            category="player_spotlight",
            key=f"spotlight-{player.slug}",
            title=f"Spotlight: {player.name}, {player.position}, {club.short}",
            summary=f"A generated profile of {player.name}: overall {player.overall}, {player.goals} goals, archetype {player.archetype}.",
            body=_sections(fact, analysis, "Speculation about a real career is out of scope: this player does not exist."),
            season=draft.sizes.season,
            entities={"competitions": [club.league], "teams": [club.slug], "players": [player.slug], "matches": []},
            published_at=emitter.stamp(index, hours=11),
        )


def _team_news(emitter: _Emitter, draft: WorldDraft) -> None:
    for club_index, club in enumerate(sorted(draft.clubs, key=lambda item: item.slug)):
        completed = _team_fixtures(draft, club)
        scheduled = _team_fixtures(draft, club, played=False)
        used = {line.player.slug for fixture in completed for line in fixture.lines if line.team_slug == club.slug}
        leaders = sorted(club.players, key=lambda player: (-player.goals, player.slug))[:3]
        league_name = draft.competition(club.league).name
        for angle_index, angle in enumerate(TEAM_ANGLES):
            if angle == "selection":
                fact = (
                    f"{club.name} used {len(used)} different players across {len(completed)} completed fixtures in the {league_name}, "
                    f"in a {club.formation} managed by {club.manager}. Leading scorers: "
                    f"{_named([f'{player.name} {player.goals}' for player in leaders if player.goals > 0], 'none')}, totalling "
                    f"{sum(player.goals for player in club.players)} goals in the stored line-ups."
                )
                analysis = "The rotation count is a property of the seeded line-ups, not of a manager's preferences."
            elif angle == "squad update":
                fact = (
                    f"The {club.name} squad holds {len(club.players)} generated players at a mean overall of {club.overall}; "
                    f"{sum(1 for player in club.players if player.age <= 23)} are 23 or under and "
                    f"{sum(1 for player in club.players if player.nation != club.nation)} carry a nation other than {club.nation}."
                )
                analysis = "A young, mixed-nation squad reads as a development side inside this dataset; the label describes the numbers above only."
            else:
                wins = sum(1 for fixture in completed if fixture.result_for(club) == "W")
                draws = sum(1 for fixture in completed if fixture.result_for(club) == "D")
                fact = (
                    f"{wins} wins and {draws} draws from {len(completed)} completed fixtures are stored for {club.name}, and "
                    f"{len(scheduled)} fixtures are still marked 'scheduled' in the {draft.sizes.next_season} round."
                )
                analysis = "Win and draw counts come straight from the stored scores, so nothing in this line is a forecast."
            emitter.add(
                category="team_news",
                key=f"team-news-{club.slug}-{angle}",
                title=f"{club.name}: {angle}",
                summary=f"A generated {angle} note on {club.name} in the demo world's {league_name}.",
                body=_sections(fact, analysis, ""),
                season=draft.sizes.season,
                entities={
                    "competitions": [club.league],
                    "teams": [club.slug],
                    "players": sorted(player.slug for player in club.players),
                    "matches": [fixture.slug for fixture in completed[:12]],
                },
                published_at=emitter.stamp(club_index * 3 + angle_index, hours=5),
            )


def _transfer_notes(emitter: _Emitter, draft: WorldDraft) -> None:
    ranked = sorted(draft.players, key=lambda player: (-player.overall, player.slug))
    clubs = sorted(draft.clubs, key=lambda item: item.slug)
    for index, player in enumerate(ranked[: NEWS_QUOTAS["transfer_note"]]):
        angle = TRANSFER_ANGLES[index % len(TRANSFER_ANGLES)]
        home_club = draft.club(player.club)
        others = [club for club in clubs if club.slug != home_club.slug]
        suitor = min(others, key=lambda club: (abs(club.overall - player.overall), club.slug))
        fact = (
            f"{player.name} is registered to {home_club.name} in this generated world: {player.age}, {player.position}, "
            f"overall {player.overall}, {player.appearances} appearances and {player.goals} goals in the stored fixtures. "
            "Contract status is not modelled in the demo data."
        )
        analysis = f"{suitor.name} (mean overall {suitor.overall}, {suitor.formation}) are listed as monitoring the player, which is the only relational claim this note makes."
        emitter.add(
            category="transfer_note",
            key=f"transfer-{player.slug}-{angle}",
            title=f"Transfer {angle}: {player.name} linked to {suitor.short}",
            summary=f"A generated {angle} item about {player.name} and {suitor.name}. No fee, date or real transaction is implied.",
            body=_sections(
                fact,
                analysis,
                "A fee, wage or medical date would have to be invented, so none is stated: the demo world models no contracts and no money.",
            ),
            season=draft.sizes.season,
            entities={
                "competitions": [home_club.league, suitor.league],
                "teams": [home_club.slug, suitor.slug],
                "players": [player.slug],
                "matches": [],
            },
            published_at=emitter.stamp(index, hours=9),
        )


def _competition_notes(emitter: _Emitter, draft: WorldDraft) -> None:
    for index, competition in enumerate(sorted(draft.competitions, key=lambda item: item.slug)):
        fixtures = [fixture for fixture in draft.played() if fixture.competition.slug == competition.slug]
        members = sorted((club for club in draft.clubs if club.league == competition.slug), key=lambda club: club.slug)
        participants = {line.player.slug: line.player for fixture in fixtures for line in fixture.lines}
        leaders = sorted(participants.values(), key=lambda player: (-player.goals, player.slug))[:3]
        for angle_index, angle in enumerate(COMPETITION_ANGLES):
            fact = (
                f"{competition.name} is a fictional {competition.kind} in the {competition.region} region of the generated world, "
                f"listed at tier {competition.tier} for the {draft.sizes.season} season. {len(fixtures)} completed fixtures and "
                f"{sum(int(fixture.home_goals or 0) + int(fixture.away_goals or 0) for fixture in fixtures)} generated goals are stored"
                + (f" across {len(members)} registered clubs." if members else " across the eight seeded entrants.")
            )
            analysis = (
                f"Leading scorers on these stored lines are "
                f"{_named([f'{player.name} {player.goals}' for player in leaders if player.goals > 0], 'level')}, computed from "
                "`real_player_match_stats`, so the standings page and this note cannot disagree."
            )
            emitter.add(
                category="competition_note",
                key=f"competition-note-{competition.slug}-{angle}",
                title=f"{competition.name}: {angle}",
                summary=f"A generated {angle} for the {competition.name} in the demo world.",
                body=_sections(fact, analysis if angle_index == 0 else "", "This competition exists only inside this dataset; no real federation runs it."),
                season=draft.sizes.season,
                entities={
                    "competitions": [competition.slug],
                    "teams": [club.slug for club in members],
                    "players": sorted(player.slug for player in leaders),
                    "matches": [fixture.slug for fixture in fixtures[-12:]],
                },
                published_at=emitter.stamp(index * 2 + angle_index, hours=13),
            )


def _match_previews(emitter: _Emitter, draft: WorldDraft) -> None:
    for fixture in sorted(draft.upcoming(), key=lambda item: (item.kickoff, item.slug))[: NEWS_QUOTAS["match_preview"]]:
        fact = (
            f"{fixture.home.name} host {fixture.away.name} at {fixture.venue} on {fixture.kickoff.date().isoformat()} in the "
            f"{fixture.competition.name} {fixture.season} round. The fixture is marked 'scheduled', so no score, line-up or statistic "
            "exists for it yet."
        )
        analysis = f"The two recorded squads average {fixture.home.overall} and {fixture.away.overall} overall, which is the only basis this dataset offers for expecting anything."
        emitter.add(
            category="match_preview",
            key=f"preview-{fixture.slug}",
            title=f"Preview: {fixture.home.name} v {fixture.away.name}",
            summary="A generated preview of a fixture that has not been played in the demo world, so it carries no score.",
            body=_sections(fact, analysis, "Naming a favourite would be pure invention, because the match has not been simulated."),
            season=fixture.season,
            entities={
                "competitions": [fixture.competition.slug],
                "teams": [fixture.home.slug, fixture.away.slug],
                "players": sorted(player.slug for club in (fixture.home, fixture.away) for player in club.players),
                "matches": [fixture.slug],
            },
            published_at=fixture.kickoff - dt.timedelta(days=2),
        )


def plan_articles(draft: WorldDraft) -> tuple[list[Planned], list[Planned]]:
    """Build the 500-article feed and its entity edges from an already-consistent draft."""
    emitter = _Emitter(draft.seed)
    _match_reports(emitter, draft)
    _tactical_analysis(emitter, draft)
    _player_spotlights(emitter, draft)
    _team_news(emitter, draft)
    _transfer_notes(emitter, draft)
    _competition_notes(emitter, draft)
    _match_previews(emitter, draft)
    short = sorted(category for category, quota in NEWS_QUOTAS.items() if len([a for a in emitter.articles if a.payload["category"] == category]) != quota)
    if short:
        raise ValueError(f"news quota unmet: {short}")
    return emitter.articles, emitter.links


__all__ = ["NEWS_QUOTAS", "plan_articles"]
