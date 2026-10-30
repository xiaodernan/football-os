"""Seeded synthesis of the Football World: 12 competitions / 32 teams / 480 players / 288 matches /
100 training sessions / 824 articles from a two-tier pyramid of four leagues, well above the spec
§65 floors of 10 competitions / 20 teams / 300 players / 100 matches / 100 sessions / 500 articles.

Two rules shape everything below:

1. **No wall clock, no shared `random` state.** Each phase draws from its own forked stream, so
   generating teams before players cannot change the players.
2. **Nothing is invented twice.** Scores come from a documented strength formula; stat lines sum to
   those scores; season totals sum from those lines; club ratings average those players. A number
   shown anywhere in M3 traces upward to the seed, which is what makes it demo data rather than a
   fake measurement (spec §62, §89, `DATA_POLICY.md` §2).
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Final

from app.services.attributes import compute_overall, derive_archetype, derive_baseline
from app.services.training_catalog import DRILLS
from app.services.world.names import (
    brand_colour,
    club_name,
    competition_name,
    formation,
    nation_name,
    person_name,
    region_name,
    slugify,
    stadium_name,
)
from app.services.world.news import plan_articles
from app.services.world.plan import Planned, WorldPlan, world_id
from app.services.world.rng import WorldRng

WORLD_VERSION: Final = "4.0"
SEASON_START: Final = dt.date(2026, 8, 8)
KICKOFF_SLOTS: Final = ((12, 30), (15, 0), (17, 30), (20, 15))
WORLD_COUNTRY: Final = "Generated World"

SQUAD_PLAN: Final = (
    ("GK", 2),
    ("CB", 3),
    ("LB", 1),
    ("RB", 1),
    ("CDM", 1),
    ("CM", 2),
    ("CAM", 1),
    ("LW", 1),
    ("RW", 1),
    ("ST", 2),
)
XI_BY_FORMATION: Final = {
    "4-4-2": ("GK", "CB", "CB", "LB", "RB", "LW", "RW", "CM", "CM", "ST", "ST"),
    "4-2-3-1": ("GK", "CB", "CB", "LB", "RB", "CDM", "CM", "LW", "CAM", "RW", "ST"),
    "4-3-3": ("GK", "CB", "CB", "LB", "RB", "CDM", "CM", "CM", "LW", "RW", "ST"),
}
SECONDARY_POSITIONS: Final = {
    "GK": (),
    "CB": ("CDM",),
    "LB": ("CB",),
    "RB": ("CB",),
    "CDM": ("CM", "CB"),
    "CM": ("CDM", "CAM"),
    "CAM": ("CM", "ST"),
    "LW": ("RW", "CAM"),
    "RW": ("LW", "CAM"),
    "ST": ("CAM",),
}
GOAL_SHARE: Final = {"ST": 6.0, "LW": 4.0, "RW": 4.0, "CAM": 3.0, "CM": 2.0, "CB": 1.6, "CDM": 1.2, "LB": 0.8, "RB": 0.8, "GK": 0.0}
CREATIVE_SHARE: Final = {"ST": 3.0, "LW": 5.0, "RW": 5.0, "CAM": 6.0, "CM": 4.0, "CDM": 2.0, "LB": 3.0, "RB": 3.0, "CB": 1.0, "GK": 0.2}
BASE_SHOTS: Final = {"ST": 2.6, "LW": 1.7, "RW": 1.7, "CAM": 1.4, "CM": 0.9, "CDM": 0.5, "LB": 0.4, "RB": 0.4, "CB": 0.7, "GK": 0.0}
PASS_VOLUME: Final = {"GK": 26, "CB": 52, "LB": 44, "RB": 44, "CDM": 56, "CM": 58, "CAM": 46, "LW": 34, "RW": 34, "ST": 24}
DEFENSIVE_ROLES: Final = ("CB", "LB", "RB", "CDM")
RATING_FORMULA: Final = (
    "6.00 + 0.45*goals + 0.30*assists + 0.06*shots_on_target + 0.03*duels_won + 0.04*interceptions "
    "+ 0.03*tackles + 0.04*saves + 0.50*(minutes/90) - 0.04*fouls - 0.15*yellow_cards - 0.50*red_cards, "
    "clamped to 4.50-9.80"
)
STAT_METHOD: Final = {
    "score": "seeded Poisson draw around expected goals = 1.30/1.05 +/- 1.85 * squad-strength difference, home advantage +/-0.25",
    "rating": RATING_FORMULA,
    "possession": "50 + 28 * squad-strength difference, jittered by the seeded stream, clamped to 34-66",
    "season_totals": "summed from this player's real_player_match_stats rows; nothing is stored that the stat lines do not add up to",
    "provenance": "generated locally from a fixed seed — no provider call, no web fetch, no measurement of the real world",
}


#: The strength band each league tier draws its clubs from. Tier 1 is the top flight; the ranges
#: overlap (0.52-0.66) so a promoted club is not outclassed by construction.
TIER_STRENGTH: Final[dict[int, tuple[float, float]]] = {
    1: (0.52, 0.95),
    2: (0.30, 0.66),
}


@dataclass(frozen=True)
class WorldSizes:
    """The M3 gate, two divisions deep. `players == teams * squad_size` by construction.

    `tiers` is the league pyramid, shallowest first: `(2, 2)` means two tier-1 leagues and two
    tier-2 leagues. A club's tier decides which strength band it is drawn from, so the world has
    a top flight and a second division rather than four parallel leagues. Cups are not part of the
    pyramid — they are open to every club and carry `tier = 0`, which is no level at all.
    """

    tiers: tuple[int, ...] = (2, 2)
    cups: int = 8
    teams_per_league: int = 8
    squad_size: int = 15
    season: str = "2026"
    next_season: str = "2027"
    training_sessions: int = 100

    @property
    def leagues(self) -> int:
        return sum(self.tiers)

    @property
    def teams(self) -> int:
        return self.leagues * self.teams_per_league

    @property
    def competitions(self) -> int:
        return self.leagues + self.cups

    @property
    def players(self) -> int:
        return self.teams * self.squad_size

    @property
    def played_matches(self) -> int:
        """Double round-robin in every league plus a 7-game knockout in every cup (spec §65 floor: 100)."""
        return self.leagues * self.teams_per_league * (self.teams_per_league - 1) + self.cups * 7

    @property
    def scheduled_matches(self) -> int:
        return self.leagues * 2


@dataclass
class _Competition:
    slug: str
    name: str
    kind: str
    tier: int
    region: str
    summary: str


@dataclass
class _Club:
    slug: str
    name: str
    short: str
    city: str
    stadium: str
    capacity: int
    formation: str
    colour: str
    nation: str
    league: str
    strength: float
    manager: str = ""
    players: list[_Player] = field(default_factory=list)
    overall: int = 0


@dataclass
class _Player:
    slug: str
    name: str
    position: str
    secondary: tuple[str, ...]
    age: int
    foot: str
    height: int
    nation: str
    club: str
    attributes: dict[str, int]
    reasons: list[str]
    overall: int
    potential: int
    archetype: str
    archetype_match: float
    rating_minutes: float = 0.0
    summary: str = ""
    appearances: int = 0
    starts: int = 0
    minutes: int = 0
    goals: int = 0
    assists: int = 0
    clean_sheets: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    rating: float = 0.0
    form: float = 0.0
    recent: list[float] = field(default_factory=list)


@dataclass
class _Line:
    player: _Player
    team_slug: str
    side: str
    role: str
    position: str
    minute_rank: int
    minutes: int
    goals: int = 0
    assists: int = 0
    shots: int = 0
    shots_on_target: int = 0
    passes: int = 0
    passes_accurate: int = 0
    key_passes: int = 0
    tackles: int = 0
    interceptions: int = 0
    duels_won: int = 0
    saves: int = 0
    fouls: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    rating: float = 0.0

    def columns(self, fixture: _Fixture) -> dict[str, Any]:
        return {
            "match_id": world_id("match", fixture.slug),
            "player_id": world_id("player", self.player.slug),
            "team_id": world_id("team", self.team_slug),
            "role": self.role,
            "position": self.position,
            "minute_rank": self.minute_rank,
            "minutes": self.minutes,
            "goals": self.goals,
            "assists": self.assists,
            "shots": self.shots,
            "shots_on_target": self.shots_on_target,
            "passes": self.passes,
            "passes_accurate": self.passes_accurate,
            "key_passes": self.key_passes,
            "tackles": self.tackles,
            "interceptions": self.interceptions,
            "duels_won": self.duels_won,
            "saves": self.saves,
            "fouls": self.fouls,
            "yellow_cards": self.yellow_cards,
            "red_cards": self.red_cards,
            "rating": self.rating,
        }


@dataclass
class _Fixture:
    slug: str
    season: str
    competition: _Competition
    home: _Club
    away: _Club
    round_label: str
    kickoff: dt.datetime
    status: str
    venue: str
    venue_city: str
    home_goals: int | None = None
    away_goals: int | None = None
    stats: dict[str, Any] = field(default_factory=dict)
    lines: list[_Line] = field(default_factory=list)
    summary: str = ""

    def score(self) -> tuple[int, int] | None:
        """Final goals as `(home, away)`, or `None` while the fixture is unplayed.

        The only safe way to read the score: `home_goals`/`away_goals` stay nullable for
        scheduled fixtures, so every consumer that needs numbers goes through here.
        """
        if self.status == "completed" and self.home_goals is not None and self.away_goals is not None:
            return self.home_goals, self.away_goals
        return None

    @property
    def completed(self) -> bool:
        return self.score() is not None

    def side_of(self, club: _Club) -> str:
        return "home" if club.slug == self.home.slug else "away"

    def goals_for(self, club: _Club) -> int:
        score = self.score()
        if score is None:
            return 0
        return score[0] if self.side_of(club) == "home" else score[1]

    def conceded_by(self, club: _Club) -> int:
        score = self.score()
        if score is None:
            return 0
        return score[1] if self.side_of(club) == "home" else score[0]

    def result_for(self, club: _Club) -> str:
        if not self.completed:
            return "P"
        own, conceded = self.goals_for(club), self.conceded_by(club)
        return "W" if own > conceded else "L" if own < conceded else "D"

    def columns(self) -> dict[str, Any]:
        haystack = " ".join([self.home.name, self.away.name, self.home.slug, self.away.slug, self.competition.name, self.season, self.round_label, self.status]).lower()
        return {
            "slug": self.slug,
            "season": self.season,
            "competition_id": world_id("competition", self.competition.slug),
            "home_team_id": world_id("team", self.home.slug),
            "away_team_id": world_id("team", self.away.slug),
            "round_label": self.round_label,
            "kickoff_at": self.kickoff,
            "venue_name": self.venue,
            "venue_city": self.venue_city,
            "status": self.status,
            "home_goals": self.home_goals,
            "away_goals": self.away_goals,
            "stats": self.stats,
            "haystack": haystack,
            "summary": self.summary,
        }


@dataclass
class WorldDraft:
    """Everything the news layer may quote, already consistent with itself."""

    seed: int
    sizes: WorldSizes
    competitions: list[_Competition]
    clubs: list[_Club]
    fixtures: list[_Fixture]

    @property
    def players(self) -> list[_Player]:
        return [player for club in self.clubs for player in club.players]

    def played(self) -> list[_Fixture]:
        return [fixture for fixture in self.fixtures if fixture.completed]

    def upcoming(self) -> list[_Fixture]:
        return [fixture for fixture in self.fixtures if not fixture.completed]

    def club(self, slug: str) -> _Club:
        return next(club for club in self.clubs if club.slug == slug)

    def competition(self, slug: str) -> _Competition:
        return next(competition for competition in self.competitions if competition.slug == slug)

    def leagues(self) -> list[_Competition]:
        return [c for c in self.competitions if c.kind == "league"]

    def cups(self) -> list[_Competition]:
        return [c for c in self.competitions if c.kind == "cup"]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _kickoff(rng: WorldRng, day: dt.date) -> dt.datetime:
    hour, minute = rng.choice(KICKOFF_SLOTS)
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=dt.UTC)


def _expected_goals(home: _Club, away: _Club) -> tuple[float, float]:
    diff = home.strength - away.strength
    return (
        round(_clamp(1.30 + 1.85 * diff + 0.25, 0.20, 3.60), 3),
        round(_clamp(1.05 + 1.85 * diff - 0.25, 0.15, 3.30), 3),
    )


def _round_robin(size: int) -> list[list[tuple[int, int]]]:
    """Circle-method rounds; with an odd field one club rests each round."""
    indices = list(range(size))
    if len(indices) % 2:
        indices.append(-1)
    length = len(indices)
    rounds: list[list[tuple[int, int]]] = []
    order = indices[:]
    for round_number in range(length - 1):
        pairs: list[tuple[int, int]] = []
        for index in range(length // 2):
            first, second = order[index], order[length - 1 - index]
            if first == -1 or second == -1:
                continue
            pairs.append((first, second) if round_number % 2 == 0 else (second, first))
        rounds.append(sorted(pairs))
        order = [order[0], order[-1]] + order[1:-1]
    return rounds


# --- structure -----------------------------------------------------------------------------


def _make_competitions(rng: WorldRng, sizes: WorldSizes) -> list[_Competition]:
    regions: set[str] = set()
    competitions: list[_Competition] = []
    for tier, count in enumerate(sizes.tiers, start=1):
        for _ in range(count):
            index = len(competitions)
            local = rng.fork(f"competition-{index}")
            region = local.unique(60, region_name, regions)
            regions.add(region)
            name = competition_name(local, region, "league")
            summary = f"The {name} is a fictional tier-{tier} league in the generated FOOTBALL OS world around {region}. It belongs to no real federation and reports no real results."
            competitions.append(_Competition(slug=slugify(name), name=name, kind="league", tier=tier, region=region, summary=summary))
    for _ in range(sizes.cups):
        index = len(competitions)
        local = rng.fork(f"competition-{index}")
        region = local.unique(60, region_name, regions)
        regions.add(region)
        name = competition_name(local, region, "cup")
        summary = f"The {name} is a fictional cup in the generated FOOTBALL OS world around {region}. It belongs to no real federation and reports no real results."
        # Cups are open to every club, so they sit at no level of the pyramid: `tier = 0` is
        # the honest answer, and a page that prints "tier 0" is printing a number that means
        # "not in the pyramid" rather than a second division.
        competitions.append(_Competition(slug=slugify(name), name=name, kind="cup", tier=0, region=region, summary=summary))
    return competitions


def _tier_strength(tier: int) -> tuple[float, float]:
    """The band a club in this tier is drawn from; the bands overlap so a promoted side can compete."""
    return TIER_STRENGTH.get(tier, (0.30, 0.95))


def _make_clubs(rng: WorldRng, sizes: WorldSizes, leagues: Sequence[_Competition]) -> list[_Club]:
    name_stream = rng.fork("club-names")
    clubs: list[_Club] = []
    for index in range(sizes.teams):
        local = name_stream.fork(f"club-{index}")
        title, city, short = club_name(local)
        while any(existing.name == title or existing.city == city for existing in clubs):
            title, city, short = club_name(local)
        league = leagues[index % len(leagues)]
        low, high = _tier_strength(league.tier)
        strength = round(_clamp(low + (high - low) * local.random(), 0.30, 0.95), 4)
        clubs.append(
            _Club(
                slug=slugify(title),
                name=title,
                short=short,
                city=city,
                stadium=stadium_name(local, city),
                capacity=local.randint(8000, 62000),
                formation=formation(local),
                colour=brand_colour(local),
                nation=nation_name(local),
                league=leagues[index % len(leagues)].slug,
                strength=strength,
            )
        )
    return clubs


def _league_of(clubs: Sequence[_Club], league_slug: str) -> list[_Club]:
    return sorted([club for club in clubs if club.league == league_slug], key=lambda club: club.slug)


def _level_for(strength: float) -> str:
    return "elite" if strength >= 0.72 else "advanced" if strength >= 0.52 else "intermediate"


def _make_players(rng: WorldRng, clubs: Sequence[_Club], taken_names: set[str]) -> None:
    nations = sorted({club.nation for club in clubs})
    for club_index, club in enumerate(clubs):
        local = rng.fork(f"squad-{club_index}-{club.slug}")
        for position, count in SQUAD_PLAN:
            for _ in range(count):
                name = local.unique(80, person_name, taken_names)
                taken_names.add(name)
                foot = local.weighted(("right", "left", "both"), (0.72, 0.22, 0.06))
                age = local.randint(21, 36) if position == "GK" else local.randint(17, 34)
                height = local.randint(183, 198) if position == "GK" else local.randint(178, 195) if position == "CB" else local.randint(165, 189)
                baseline = derive_baseline(position=position, age=age, level=_level_for(club.strength), preferred_foot=foot, height_cm=height)
                shift = round((club.strength - 0.62) * 14)
                attributes = {key: int(_clamp(value + shift + local.randint(-3, 3), 28, 96)) for key, value in baseline.attributes.items()}
                overall = compute_overall(position, attributes)
                potential = int(_clamp(max(baseline.potential + shift, overall + local.randint(0, 9)), overall, 99))
                archetype, match, arch_reasons = derive_archetype(position, attributes)
                club.players.append(
                    _Player(
                        slug=slugify(name),
                        name=name,
                        position=position,
                        secondary=SECONDARY_POSITIONS[position],
                        age=age,
                        foot=foot,
                        height=height,
                        nation=club.nation if local.random() < 0.6 else local.choice(nations),
                        club=club.slug,
                        attributes=attributes,
                        reasons=[
                            *baseline.reasons,
                            f"Generated world: club strength index {club.strength:.2f} sets level '{_level_for(club.strength)}' and {shift:+d} on every attribute",
                            arch_reasons[0] if arch_reasons else "",
                            "Seeded fiction: these values describe no real person and measure nothing",
                        ],
                        overall=overall,
                        potential=potential,
                        archetype=archetype,
                        archetype_match=match,
                    )
                )


def _assign_managers(rng: WorldRng, clubs: Sequence[_Club], taken_names: set[str]) -> None:
    """Managers draw from the same name pool as players, so one identity can never mean two things."""
    for index, club in enumerate(clubs):
        local = rng.fork(f"manager-{index}")
        name = local.unique(80, person_name, taken_names)
        taken_names.add(name)
        club.manager = name


def _fixture_slug(season: str, competition: _Competition, home: _Club, away: _Club, round_label: str) -> str:
    """Natural key for a fixture. The competition is part of it because two cups can pair the same
    clubs in the same round label, and a slug that collided would silently merge two matches."""
    raw = f"{season}-{competition.slug}-{home.slug}-{away.slug}-{slugify(round_label)}"
    if len(raw) <= 200:
        return raw
    return f"{raw[:180]}-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def _blank_stats(rng: WorldRng, home: _Club, away: _Club) -> dict[str, Any]:
    xg_home, xg_away = _expected_goals(home, away)
    possession_home = round(_clamp(50 + 28 * (home.strength - away.strength) + rng.uniform(-6, 6), 34, 66), 1)
    return {
        "expected_goals": {"home": xg_home, "away": xg_away},
        "possession": {"home": possession_home, "away": round(100 - possession_home, 1)},
        "attendance": int(home.capacity * rng.uniform(0.62, 0.99)),
        "shots": {"home": 0, "away": 0},
        "shots_on_target": {"home": 0, "away": 0},
        "passes": {"home": 0, "away": 0},
        "passes_accurate": {"home": 0, "away": 0},
        "discipline": {"home": 0, "away": 0},
        "corners": {"home": rng.randint(1, 11), "away": rng.randint(1, 11)},
        "method": STAT_METHOD,
    }


def _simulate(rng: WorldRng, fixture: _Fixture) -> tuple[int, int]:
    """One seeded score draw. Callers that cannot end level (a knockout tie) adjust afterwards."""
    local = rng.fork(f"outcome-{fixture.slug}")
    xg = fixture.stats["expected_goals"]
    fixture.home_goals = local.poisson(float(xg["home"]), cap=6)
    fixture.away_goals = local.poisson(float(xg["away"]), cap=6)
    return fixture.home_goals, fixture.away_goals


def _league_fixtures(rng: WorldRng, sizes: WorldSizes, clubs: Sequence[_Club], leagues: Sequence[_Competition]) -> list[_Fixture]:
    fixtures: list[_Fixture] = []
    for league_index, league in enumerate(leagues):
        members = _league_of(clubs, league.slug)
        local = rng.fork(f"league-{league_index}-{league.slug}")
        matchday = 0
        for half in range(2):
            for pairs in _round_robin(len(members)):
                matchday += 1
                for home_index, away_index in pairs:
                    home, away = (members[home_index], members[away_index]) if half == 0 else (members[away_index], members[home_index])
                    round_label = f"Matchday {matchday}"
                    day = SEASON_START + dt.timedelta(days=7 * (matchday - 1) + local.randint(0, 2))
                    fixture = _Fixture(
                        slug=_fixture_slug(sizes.season, league, home, away, round_label),
                        season=sizes.season,
                        competition=league,
                        home=home,
                        away=away,
                        round_label=round_label,
                        kickoff=_kickoff(local, day),
                        status="completed",
                        venue=home.stadium,
                        venue_city=home.city,
                        stats=_blank_stats(local, home, away),
                    )
                    _simulate(local, fixture)
                    fixtures.append(fixture)
    return fixtures


def _cup_fixtures(rng: WorldRng, sizes: WorldSizes, clubs: Sequence[_Club], cups: Sequence[_Competition]) -> list[_Fixture]:
    """Straight knockout of eight seeded entrants: 4 + 2 + 1 fixtures per cup."""
    fixtures: list[_Fixture] = []
    for cup_index, cup in enumerate(cups):
        local = rng.fork(f"cup-{cup_index}-{cup.slug}")
        bracket = local.sample(list(clubs), 8)
        for stage, (label, day_offset) in enumerate((("Quarter-final", 34), ("Semi-final", 62), ("Final", 151))):
            if len(bracket) < 2:
                break
            winners: list[_Club] = []
            for pair in range(len(bracket) // 2):
                home, away = bracket[2 * pair], bracket[2 * pair + 1]
                round_label = label if stage == 2 else f"{label} {pair + 1}"
                neutral = stage == 2
                day = SEASON_START + dt.timedelta(days=day_offset + local.randint(0, 3))
                fixture = _Fixture(
                    slug=_fixture_slug(sizes.season, cup, home, away, round_label),
                    season=sizes.season,
                    competition=cup,
                    home=home,
                    away=away,
                    round_label=round_label,
                    kickoff=_kickoff(local, day),
                    status="completed",
                    venue=away.stadium if neutral else home.stadium,
                    venue_city="Neutral venue" if neutral else home.city,
                    stats=_blank_stats(local, home, away),
                )
                home_goals, away_goals = _simulate(local, fixture)
                if home_goals == away_goals:
                    home_goals += 1
                    fixture.home_goals = home_goals
                    fixture.stats["extra_time"] = True
                winners.append(home if home_goals > away_goals else away)
                fixtures.append(fixture)
            bracket = winners
    return fixtures


def _upcoming_fixtures(rng: WorldRng, sizes: WorldSizes, clubs: Sequence[_Club], leagues: Sequence[_Competition]) -> list[_Fixture]:
    """Next season's opening round: on the calendar, but unplayed — so it carries no score at all."""
    fixtures: list[_Fixture] = []
    for league_index, league in enumerate(leagues):
        members = _league_of(clubs, league.slug)
        local = rng.fork(f"upcoming-{league_index}-{league.slug}")
        season_start = SEASON_START.replace(year=int(sizes.next_season))
        for pair_index, (home_index, away_index) in enumerate(_round_robin(len(members))[0][:2]):
            home, away = members[home_index], members[away_index]
            round_label = f"Matchday 1 game {pair_index + 1}"
            day = season_start + dt.timedelta(days=7 * pair_index + local.randint(0, 2))
            fixtures.append(
                _Fixture(
                    slug=_fixture_slug(sizes.next_season, league, home, away, round_label),
                    season=sizes.next_season,
                    competition=league,
                    home=home,
                    away=away,
                    round_label=round_label,
                    kickoff=_kickoff(local, day),
                    status="scheduled",
                    venue=home.stadium,
                    venue_city=home.city,
                    stats={},
                    summary=(
                        f"{home.name} host {away.name} in the {league.name} on {day.isoformat()} in this generated world. "
                        "The fixture has not been played, so there is no score, line-up or statistic to show."
                    ),
                )
            )
    return fixtures


# --- match content -------------------------------------------------------------------------


def _lineup_for(club: _Club, shape: Sequence[str], rng: WorldRng) -> list[tuple[_Player, str, bool, str]]:
    """`[(player, shape role, is starter, replaces slug)]` — the best available player per role,
    then two substitutes drawn from the bench who take the place of two outfield starters. The
    draw is what rotates a 15-man squad through a season instead of playing the same eleven."""
    ranked = sorted(club.players, key=lambda player: (-player.overall, player.slug))
    chosen: list[_Player] = []
    starters: list[tuple[_Player, str]] = []
    for role in shape:
        used = {player.slug for player in chosen}
        pick = next((player for player in ranked if player.position == role and player.slug not in used), None)
        if pick is None:
            pick = next((player for player in ranked if role in player.secondary and player.slug not in used), None)
        if pick is None:  # a squad that cannot field the shape still fields eleven people
            pick = next(player for player in ranked if player.slug not in used)
        chosen.append(pick)
        starters.append((pick, role))
    bench = [player for player in ranked if player.slug not in {started.slug for started in chosen}]
    takers = sorted([(player, role) for player, role in starters if role != "GK"], key=lambda pair: (pair[0].overall, pair[0].slug))
    incoming = rng.sample(bench, min(2, len(bench)))
    lineup: list[tuple[_Player, str, bool, str]] = [(player, role, True, "") for player, role in starters]
    for (departing, role), arriving in zip(takers[: len(incoming)], incoming, strict=True):
        lineup.append((arriving, role, False, departing.slug))
    return lineup


def _appearance_minutes(rng: WorldRng, lineup: Sequence[tuple[_Player, str, bool, str]]) -> dict[str, int]:
    """Minutes add up to 11 x 90: a substitute's time on is exactly the time his man loses."""
    played: dict[str, int] = {player.slug: 90 for player, _role, is_starter, _ in lineup if is_starter}
    for player, _role, is_starter, replaces in lineup:
        if is_starter or replaces not in played:
            continue
        on = rng.randint(8, 34)
        played[player.slug] = on
        played[replaces] -= on
    return played


def _draw_scorers(rng: WorldRng, participants: Sequence[_Player], count: int) -> tuple[list[int], list[int]]:
    """Per goal: one scorer by attacking weight, then a 72% chance an assist goes to a teammate."""
    goals = [0] * len(participants)
    assists = [0] * len(participants)
    weights = [max(0.0, GOAL_SHARE.get(player.position, 1.0)) for player in participants]
    if sum(weights) <= 0:
        weights = [1.0 if player.position != "GK" else 0.0 for player in participants]
    creative = [max(0.1, CREATIVE_SHARE.get(player.position, 1.0)) for player in participants]
    for _ in range(count):
        scorer = rng.weighted(list(range(len(participants))), weights)
        goals[scorer] += 1
        if rng.random() > 0.72:
            continue
        providers = [index for index in range(len(participants)) if index != scorer and participants[index].position != "GK"]
        if providers:
            assists[rng.weighted(providers, [creative[index] for index in providers])] += 1
    return goals, assists


def _build_match_lines(rng: WorldRng, fixture: _Fixture) -> None:
    local = rng.fork(f"lines-{fixture.slug}")
    for side in ("home", "away"):
        club = fixture.home if side == "home" else fixture.away
        rank_base = 0 if side == "home" else 100
        lineup = _lineup_for(club, XI_BY_FORMATION[club.formation], local)
        played = _appearance_minutes(local, lineup)
        participants = [player for player, _role, _starter, _ in lineup]
        goals, assists = _draw_scorers(local.fork(f"scorers-{side}"), participants, fixture.goals_for(club))
        for index, (player, role, is_starter, _replaces) in enumerate(lineup):
            minutes = played.get(player.slug, 0)
            if minutes <= 0:
                continue
            line_rng = local.fork(f"line-{player.slug}")
            scored, created = goals[index], assists[index]
            shots = scored + line_rng.poisson(BASE_SHOTS.get(player.position, 0.8) * minutes / 90, cap=7)
            on_target = max(scored, min(shots, scored + line_rng.poisson(0.55 * minutes / 90, cap=5)))
            volume = max(1, int(PASS_VOLUME.get(player.position, 40) * minutes / 90))
            accuracy = _clamp(0.62 + player.attributes["passing"] / 260 + line_rng.uniform(-0.04, 0.04), 0.45, 0.96)
            fouls = line_rng.poisson(0.45 * minutes / 90, cap=5)
            fixture.lines.append(
                _Line(
                    player=player,
                    team_slug=club.slug,
                    side=side,
                    role="starter" if is_starter else "sub",
                    position=role,
                    minute_rank=rank_base + index + 1,
                    minutes=minutes,
                    goals=scored,
                    assists=created,
                    shots=shots,
                    shots_on_target=on_target,
                    passes=volume,
                    passes_accurate=int(round(volume * accuracy)),
                    key_passes=created + line_rng.poisson(0.35 * minutes / 90, cap=5),
                    tackles=line_rng.poisson((1.6 if role in DEFENSIVE_ROLES + ("CM",) else 0.8) * minutes / 90, cap=9),
                    interceptions=line_rng.poisson((1.2 if role in DEFENSIVE_ROLES else 0.6) * minutes / 90, cap=7),
                    duels_won=line_rng.poisson((1.0 + player.attributes["strength"] / 60) * minutes / 90, cap=12),
                    fouls=fouls,
                    yellow_cards=1 if fouls >= 3 and line_rng.random() < 0.16 else 0,
                    red_cards=1 if fouls >= 4 and line_rng.random() < 0.015 else 0,
                )
            )
    _apply_keeper_saves(fixture)
    for line in fixture.lines:
        line.rating = _rate(line)
        _roll_up_player(line, fixture)
    _roll_up_team(fixture)
    fixture.summary = _match_summary(fixture)


def _apply_keeper_saves(fixture: _Fixture) -> None:
    """Saves are not a free draw: they are exactly the shots on target the keeper faced and did not stop."""
    score = fixture.score()
    if score is None:
        return
    for side in ("home", "away"):
        faced = sum(line.shots_on_target for line in fixture.lines if line.side != side)
        conceded = score[1] if side == "home" else score[0]
        for line in fixture.lines:
            if line.side == side and line.position == "GK":
                line.saves = max(0, faced - conceded)


def _rate(line: _Line) -> float:
    value = (
        6.00
        + 0.45 * line.goals
        + 0.30 * line.assists
        + 0.06 * line.shots_on_target
        + 0.03 * line.duels_won
        + 0.04 * line.interceptions
        + 0.03 * line.tackles
        + 0.04 * line.saves
        + 0.50 * (line.minutes / 90)
        - 0.04 * line.fouls
        - 0.15 * line.yellow_cards
        - 0.50 * line.red_cards
    )
    return round(_clamp(value, 4.5, 9.8), 2)


def _roll_up_player(line: _Line, fixture: _Fixture) -> None:
    player = line.player
    player.appearances += 1
    player.starts += 1 if line.role == "starter" else 0
    player.minutes += line.minutes
    player.goals += line.goals
    player.assists += line.assists
    player.yellow_cards += line.yellow_cards
    player.red_cards += line.red_cards
    player.rating_minutes += line.rating * line.minutes
    player.recent.append(line.rating)
    conceded = fixture.conceded_by(fixture.home if line.side == "home" else fixture.away)
    if line.position == "GK" and line.role == "starter" and conceded == 0:
        player.clean_sheets += 1


def _roll_up_team(fixture: _Fixture) -> None:
    for side in ("home", "away"):
        lines = [line for line in fixture.lines if line.side == side]
        for column, key in (("shots", "shots"), ("shots_on_target", "shots_on_target"), ("passes", "passes"), ("passes_accurate", "passes_accurate")):
            fixture.stats[key][side] = sum(getattr(line, column) for line in lines)
        fixture.stats["discipline"][side] = sum(line.yellow_cards + line.red_cards for line in lines)


def _match_summary(fixture: _Fixture) -> str:
    stats = fixture.stats
    return (
        f"{fixture.home.name} {fixture.home_goals}-{fixture.away_goals} {fixture.away.name} "
        f"({fixture.competition.name}, {fixture.season}, {fixture.round_label}). "
        f"Possession {stats['possession']['home']}/{stats['possession']['away']}; "
        f"shots {stats['shots']['home']}-{stats['shots']['away']} "
        f"(on target {stats['shots_on_target']['home']}-{stats['shots_on_target']['away']}); "
        f"discipline {stats['discipline']['home']}-{stats['discipline']['away']}. "
        "Generated fixture: every figure is seeded demo data and measures nothing in the real world."
    )


def _finish_clubs(draft: WorldDraft) -> None:
    for club in draft.clubs:
        club.overall = int(round(sum(player.overall for player in club.players) / len(club.players)))
        for player in club.players:
            player.rating = round(player.rating_minutes / player.minutes, 2) if player.minutes else 0.0
            recent = player.recent[-5:]
            player.form = round(sum(recent) / len(recent), 2) if recent else 0.0
            player.summary = (
                f"{player.name} is a {player.age}-year-old {player.position} from {player.nation}, listed with {club.name} "
                f"in the {draft.sizes.season} season of the generated world. "
                f"{player.appearances} appearances, {player.goals} goals, {player.assists} assists, "
                f"{player.minutes} minutes, average generated rating {player.rating:.2f}. "
                f"Profiled as a {player.archetype}. Synthetic demo data only."
            )


# --- emission ------------------------------------------------------------------------------


def _competition_row(competition: _Competition, sizes: WorldSizes) -> Planned:
    payload = {
        "slug": competition.slug,
        "name": competition.name,
        "country": WORLD_COUNTRY,
        "kind": competition.kind,
        "tier": competition.tier,
        "region": competition.region,
        "season": sizes.season,
        "summary": competition.summary,
    }
    return Planned(natural_key=competition.slug, payload=payload)


def _team_row(club: _Club, sizes: WorldSizes) -> Planned:
    payload = {
        "slug": club.slug,
        "name": club.name,
        "competition_id": world_id("competition", club.league),
        "logo_ref": None,
        "short_name": club.short,
        "city": club.city,
        "stadium": club.stadium,
        "capacity": club.capacity,
        "manager_name": club.manager,
        "formation": club.formation,
        "brand_color": club.colour,
        "nation": club.nation,
        "season": sizes.season,
        "squad_size": len(club.players),
        "overall": club.overall,
        "summary": (
            f"{club.name} are a fictional club from {club.city}, managed by {club.manager} and set up in a {club.formation} "
            f"at the {club.capacity:,}-capacity {club.stadium}. Squad rating {club.overall} is the mean of their generated players."
        ),
    }
    return Planned(natural_key=club.slug, payload=payload)


def _player_row(player: _Player, sizes: WorldSizes) -> Planned:
    payload = {
        "slug": player.slug,
        "name": player.name,
        "position": player.position,
        "secondary_positions": list(player.secondary),
        "age": player.age,
        "preferred_foot": player.foot,
        "height_cm": player.height,
        "nation": player.nation,
        "team_id": world_id("team", player.club),
        "season": sizes.season,
        "attributes": dict(player.attributes),
        "derivation_reasons": [reason for reason in player.reasons if reason],
        "overall": player.overall,
        "potential": player.potential,
        "archetype": player.archetype,
        "archetype_match": player.archetype_match,
        "minutes": player.minutes,
        "appearances": player.appearances,
        "starts": player.starts,
        "goals": player.goals,
        "assists": player.assists,
        "clean_sheets": player.clean_sheets,
        "yellow_cards": player.yellow_cards,
        "red_cards": player.red_cards,
        "rating": player.rating,
        "form": player.form,
        "summary": player.summary,
    }
    return Planned(natural_key=player.slug, payload=payload)


def _stat_rows(fixture: _Fixture) -> list[Planned]:
    return [Planned(natural_key=f"{fixture.slug}|{line.player.slug}", payload=line.columns(fixture)) for line in fixture.lines]


TRAINING_WINDOW_DAYS: Final = 42
TRAINING_RPE: Final = (5, 9)


def _drills_for(position: str) -> list[dict[str, Any]]:
    """Catalogue drills that name this position, falling back to the whole catalogue.

    The drills are project-authored coaching material (spec §10), so a world training session
    reuses one rather than inventing a plausible-sounding exercise.
    """
    matched = [drill for drill in DRILLS if position in drill["positions"]]
    if matched:
        return matched
    general = [drill for drill in DRILLS if not drill["positions"]]
    return general or list(DRILLS)


def _training_rows(rng: WorldRng, draft: WorldDraft) -> list[Planned]:
    """Spec §65's 100 training sessions: demo history for demo players.

    The spread is derived, not decorative — a player is drawn in proportion to the minutes they
    played in the generated fixtures, so the squad's regulars accumulate log rows and the fringe
    does not. Load is the session-RPE formula (duration × RPE), the same arithmetic the user-side
    logger applies, and the row says so in words.
    """
    stream = rng.fork("training-sessions")
    players = sorted(draft.players, key=lambda player: player.slug)
    weights = [max(player.minutes, 1) for player in players]
    sizes = draft.sizes
    taken: set[str] = set()
    rows: list[Planned] = []
    for _ in range(sizes.training_sessions):
        player = stream.weighted(players, weights)
        drill = stream.choice(_drills_for(player.position))
        day = SEASON_START + dt.timedelta(days=stream.int_below(TRAINING_WINDOW_DAYS))
        first_index = (day - SEASON_START).days
        for offset in range(TRAINING_WINDOW_DAYS):
            slot = SEASON_START + dt.timedelta(days=(first_index + offset) % TRAINING_WINDOW_DAYS)
            key = f"{player.slug}|{slot.isoformat()}|{drill['slug']}"
            if key not in taken:
                break
        taken.add(key)
        duration = int(drill["duration_min"])
        rpe = stream.randint(*TRAINING_RPE)
        payload = {
            "player_slug": player.slug,
            "player_id": world_id("player", player.slug),
            "team_id": world_id("team", player.club),
            "player_name": player.name,
            "position": player.position,
            "season": sizes.season,
            "session_date": slot.isoformat(),
            "drill_slug": str(drill["slug"]),
            "drill_title": str(drill["title"]),
            "category": str(drill["category"]),
            "difficulty": int(drill["difficulty"]),
            "duration_min": duration,
            "rpe": rpe,
            "load_units": duration * rpe,
            "status": "completed",
            "summary": (
                f"{player.name} ({player.position}, {draft.club(player.club).short}) trained {drill['title']} for "
                f"{duration} min on {slot.isoformat()} at RPE {rpe}. Session load {duration * rpe} units is "
                f"duration x RPE. The drill is the project-authored catalogue item '{drill['slug']}'; this log row "
                f"belongs to a generated player and records no real person."
            ),
        }
        rows.append(Planned(natural_key=key, payload=payload))
    rows.sort(key=lambda row: (row.payload["session_date"], row.natural_key))
    return rows


@lru_cache(maxsize=8)
def plan_world(seed: int, sizes: WorldSizes | None = None) -> WorldPlan:
    """Build the whole world in memory. Cached because the plan is a pure function of the seed."""
    dims = sizes or WorldSizes()
    rng = WorldRng(seed)
    competitions = _make_competitions(rng, dims)
    leagues = [competition for competition in competitions if competition.kind == "league"]
    cups = [competition for competition in competitions if competition.kind == "cup"]
    clubs = _make_clubs(rng, dims, leagues)
    taken_names: set[str] = {club.name for club in clubs}
    _make_players(rng, clubs, taken_names)
    _assign_managers(rng, clubs, taken_names)
    fixtures = [*_league_fixtures(rng, dims, clubs, leagues), *_cup_fixtures(rng, dims, clubs, cups), *_upcoming_fixtures(rng, dims, clubs, leagues)]
    fixtures.sort(key=lambda fixture: (fixture.kickoff, fixture.slug))
    for fixture in fixtures:
        if fixture.completed:
            _build_match_lines(rng, fixture)
    draft = WorldDraft(seed=seed, sizes=dims, competitions=competitions, clubs=clubs, fixtures=fixtures)
    _finish_clubs(draft)

    plan = WorldPlan(
        seed=seed,
        version=WORLD_VERSION,
        competitions=[_competition_row(competition, dims) for competition in competitions],
        teams=[_team_row(club, dims) for club in sorted(clubs, key=lambda club: club.slug)],
        players=[_player_row(player, dims) for player in sorted(draft.players, key=lambda player: player.slug)],
        matches=[Planned(natural_key=fixture.slug, payload=fixture.columns()) for fixture in fixtures],
        stat_lines=[row for fixture in fixtures for row in _stat_rows(fixture)],
        training_sessions=_training_rows(rng, draft),
    )
    plan.articles, plan.article_links = plan_articles(draft)
    return plan


__all__ = ["STAT_METHOD", "WorldDraft", "WorldSizes", "plan_world"]
