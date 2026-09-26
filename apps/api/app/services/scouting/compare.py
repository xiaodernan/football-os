"""M7 §27 — Player A against Player B, answered as ten dimensions and no single score.

The spec asks for `Compare Player A vs Player B` over ten named dimensions and then prints the one thing not
to do: 避免单一 Overall 分数决定一切. A comparison that returns one number with a decimal point attached is
exactly that number whatever it is called, so this module never forms one:

* every dimension is a list of **measures**, and every measure is a figure read from a stored row — the four
  attribute groups from `app.models.ATTRIBUTES` through §24's `group_score` key list, the three event groups
  summed out of this world's own `real_player_match_stats` lines;
* a measure prints `left`, `right`, their difference and which side is greater **in the direction that measure
  declares**. Age prints `direction: none` because younger is not better by itself, and a competition name
  prints `not_scorable` rather than being turned into a number so that a comparison can prefer it;
* a dimension gets a leader only when its measures do not disagree. Two sides winning different measures of
  one dimension is reported as `split`, which is the answer rather than a failure to find one;
* an attribute key a row does not carry, and any rate for a player with no stored lines, is `unknown`, not
  zero — the refusal §24 applies to a group mean, applied per key.

`NO_WINNER_NOTE` travels inside the payload rather than in this docstring, because the first thing a reader
does with a comparison is look for the winner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ATTRIBUTES, RealPlayer, RealPlayerMatchStat, Team
from app.services.scouting.report import ReportRefusal, group_score
from app.services.scouting.search import Candidate, pool, world_account
from app.services.simulation import market

#: §27's dimension list, in the order the spec prints it.
DIMENSIONS: Final = ("technical", "physical", "mental", "tactical", "production", "possession", "defensive", "progression", "age", "context")

#: What a measure's `leader` can be. `not_scorable` and `unknown` are answers rather than gaps in the code: a
#: measure can be printed and still refuse to rank, and a key a row does not hold is a fact about that row.
LEADERS: Final = ("left", "right", "even", "unknown", "not_scorable")

#: What a dimension's leader can be, once its measures are counted.
DIMENSION_LEADERS: Final = ("left", "right", "even", "split", "unresolved")

NO_WINNER_NOTE: Final = (
    "this payload has no overall rating, no winner score and no weighted index: each dimension is called `left`, `right`, `even`, `split` or `unresolved` from the measures printed under it, "
    "and a reader who wants one number to decide the pair has to bring that number themselves"
)
MEASURE_RULE: Final = (
    "every measure carries `left`, `right`, `delta` (left minus right), `direction`, `leader` and the `source` it was read from; "
    "`direction` is `higher_is_greater`, `lower_is_greater` or `none`, and a measure with `direction: none` is printed without a leader rather than ranked"
)
DIMENSION_RULE: Final = (
    "a dimension is led by `left` or `right` only when that side wins every scorable measure of it, `even` when all scorable measures tie, "
    "`split` when the two sides win different measures, and `unresolved` when none of its measures is scorable"
)

#: The columns this module sums out of `real_player_match_stats`. Every one of them exists on the table, and
#: a rate is only ever formed from a column listed here.
STAT_COLUMNS: Final = ("minutes", "goals", "assists", "shots", "shots_on_target", "passes", "passes_accurate", "key_passes", "tackles", "interceptions", "duels_won")

#: dimension -> (measure key, numerator columns, denominator, direction)
EVENT_MEASURES: Final = {
    "production": (
        ("goals_per_90", ("goals",), "higher_is_greater"),
        ("assists_per_90", ("assists",), "higher_is_greater"),
        ("shots_on_target_per_90", ("shots_on_target",), "higher_is_greater"),
    ),
    "possession": (
        ("pass_accuracy", ("passes_accurate", "passes"), "higher_is_greater"),
        ("key_passes_per_90", ("key_passes",), "higher_is_greater"),
    ),
    "defensive": (
        ("tackles_per_90", ("tackles",), "higher_is_greater"),
        ("interceptions_per_90", ("interceptions",), "higher_is_greater"),
        ("duels_won_per_90", ("duels_won",), "higher_is_greater"),
    ),
}

#: Progression is the one event dimension these lines cannot carry: no progressive-carry or
#: field-progression event exists in this world, so it is answered by the attributes that describe it plus the
#: single recorded event a defence has to react to.
PROGRESSION_ATTRIBUTES: Final = ("long_passing", "passing", "vision")
PROGRESSION_RULE: Final = (
    "these stat lines carry no progressive carries, so Progression is the three stored attributes that describe moving the ball forward plus `key_passes_per_90`; "
    "it is a thinner dimension than Production, Possession and Defensive, and `source` says which measures come from the row and which from the lines"
)

#: dimension -> (measure key, direction, how it is read, how it is formed)
AGE_MEASURES: Final = (
    ("age", "none", "each row's stored age", "younger is not better by itself, so this measure is printed and not ranked"),
    ("headroom", "higher_is_greater", "`potential - overall` on each row", "the same ceiling arithmetic §24's potential line publishes"),
    ("age_curve", "higher_is_greater", "§22's valuation curve at each row's age", "so a difference in years left is priced the way a fee would be"),
    ("years_past_peak", "lower_is_greater", f"whole years past §22's plateau (peak ends at {market.PEAK_AGE_END})", "zero while a player is still inside the plateau"),
)
CONTEXT_MEASURES: Final = (
    ("club_overall", "higher_is_greater", "the stored `overall` of the club each row plays for", "a stronger club is the context §22's team fit also reads"),
    ("competition_name", "none", "the name of the competition each club plays in", "a name cannot be subtracted, so this measure is printed without a leader"),
    (
        "competition_tier",
        "lower_is_greater",
        "the stored tier of that competition, where 1 is the top",
        "two players in different tiers are not in the same league, which is a fact about the pair rather than a rating",
    ),
    ("starts_per_appearance", "higher_is_greater", "stored starts over stored appearances", "what a squad player and a first choice look like on paper"),
)


@dataclass
class Side:
    """One player of the pair, with everything read from the store before the comparison is formed."""

    candidate: Candidate
    totals: dict[str, int]
    club: Team | None

    @property
    def player(self) -> RealPlayer:
        return self.candidate.player

    @property
    def lines(self) -> int:
        return int(self.totals.get("lines", 0))

    @property
    def minutes(self) -> int:
        return int(self.totals.get("minutes", 0))

    @property
    def competition(self) -> Any:
        return self.club.competition if self.club else None


def _stat_totals(session: Session, player_ids: list[str]) -> dict[str, dict[str, int]]:
    """Sum each side's stored stat lines in one read, keyed by player id."""
    totals = {pid: dict(dict.fromkeys(STAT_COLUMNS, 0), lines=0) for pid in player_ids}
    for line in session.scalars(select(RealPlayerMatchStat).where(RealPlayerMatchStat.player_id.in_(player_ids))).all():
        bucket = totals.get(line.player_id)
        if bucket is None:  # pragma: no cover - the query is bounded to the two ids asked for
            continue
        for column in STAT_COLUMNS:
            bucket[column] += int(getattr(line, column) or 0)
        bucket["lines"] += 1
    return totals


def _per_90(minutes: int, counted: int) -> float | None:
    """A rate needs a denominator. No minutes is an unknown, not a zero."""
    return round(counted * 90 / minutes, 2) if minutes > 0 else None


def _measure(key: str, left: Any, right: Any, direction: str, source: str, **extra: Any) -> dict[str, Any]:
    """One printed comparison. Leaders are decided here and nowhere else, so no dimension can rank on its own."""
    delta: Any = None
    leader = "unknown"
    if direction == "none":
        leader = "not_scorable"
    elif isinstance(left, int | float) and isinstance(right, int | float):
        delta = round(float(left) - float(right), 4)
        if left == right:
            leader = "even"
        else:
            leader = "left" if bool(left > right) ^ (direction == "lower_is_greater") else "right"
    return {"key": key, "left": left, "right": right, "delta": delta, "direction": direction, "leader": leader, "source": source, **extra}


def _leader_for(measures: list[dict[str, Any]], counts: dict[str, int]) -> str:
    if counts["left"] and counts["right"]:
        return "split"
    if counts["left"]:
        return "left"
    if counts["right"]:
        return "right"
    if counts["even"]:
        return "even"
    return "unresolved"


def _dimension(name: str, source: str, measures: list[dict[str, Any]], note: str = "") -> dict[str, Any]:
    """Assemble one §27 dimension. Its leader is recomputed from the measures it is about to print."""
    counts = {leader: sum(1 for item in measures if item["leader"] == leader) for leader in LEADERS}
    row: dict[str, Any] = {"dimension": name, "source": source, "counts": counts, "leader": _leader_for(measures, counts), "measures": measures, "rule": DIMENSION_RULE}
    if note:
        row["note"] = note
    return row


def _attribute_measures(left: Side, right: Side, group: str) -> list[dict[str, Any]]:
    left_line, right_line = group_score(left.candidate, group), group_score(right.candidate, group)
    measures: list[dict[str, Any]] = []
    for key in ATTRIBUTES[group]:
        a, b = left_line.attributes.get(key), right_line.attributes.get(key)
        extra: dict[str, Any] = {}
        if a is None or b is None:
            extra["missing"] = [side for side, value in (("left", a), ("right", b)) if value is None]
        measures.append(_measure(key, a, b, "higher_is_greater", f"`attributes.{key}` on each row", **extra))
    return measures


def _rate(side: Side, columns: tuple[str, ...]) -> float | None:
    """One event measure out of a side's summed lines: a ratio where two columns speak, a per-90 rate where one does."""
    if len(columns) == 2:
        accurate, attempted = columns
        return round(side.totals[accurate] / side.totals[attempted], 3) if side.totals[attempted] else None
    return _per_90(side.minutes, side.totals[columns[0]])


def _event_measures(left: Side, right: Side, dimension: str) -> list[dict[str, Any]]:
    measures: list[dict[str, Any]] = []
    for key, columns, direction in EVENT_MEASURES[dimension]:
        if len(columns) == 2:
            unit, source = "accurate passes over passes attempted, from each side's summed lines", f"`sum({columns[0]}) / sum({columns[1]})` over each side's `real_player_match_stats` lines"
        else:
            unit, source = "events per 90 minutes of the lines behind this comparison", f"`sum({columns[0]}) * 90 / sum(minutes)` over each side's `real_player_match_stats` lines"
        a, b = _rate(left, columns), _rate(right, columns)
        extra: dict[str, Any] = {"unit": unit}
        if a is None or b is None:
            extra["unobserved"] = [side for side, value in (("left", a), ("right", b)) if value is None]
        measures.append(_measure(key, a, b, direction, source, **extra))
    return measures


def _progression_measures(left: Side, right: Side) -> list[dict[str, Any]]:
    def stored(side: Side, key: str) -> int | None:
        return (side.player.attributes or {}).get(key)

    measures = [_measure(key, stored(left, key), stored(right, key), "higher_is_greater", f"`attributes.{key}` on each row") for key in PROGRESSION_ATTRIBUTES]
    a, b = _per_90(left.minutes, left.totals["key_passes"]), _per_90(right.minutes, right.totals["key_passes"])
    extra: dict[str, Any] = {"unit": "key passes per 90 minutes"}
    if a is None or b is None:
        extra["unobserved"] = [side for side, value in (("left", a), ("right", b)) if value is None]
    measures.append(_measure("key_passes_per_90", a, b, "higher_is_greater", "`sum(key_passes) * 90 / sum(minutes)` over each side's `real_player_match_stats` lines", **extra))
    return measures


def _read(side: Side, key: str) -> Any:
    """One of §27's non-attribute measures, read from a side that is already loaded."""
    player = side.player
    if key == "age":
        return int(player.age)
    if key == "headroom":
        return side.candidate.headroom()
    if key == "age_curve":
        return market.age_curve(int(player.age))
    if key == "years_past_peak":
        return max(0, int(player.age) - market.PEAK_AGE_END)
    if key == "club_overall":
        return int(side.club.overall) if side.club else None
    if key == "competition_name":
        return side.competition.name if side.competition else None
    if key == "competition_tier":
        return int(side.competition.tier) if side.competition else None
    if key == "starts_per_appearance":
        appearances = int(player.appearances or 0)
        return round(int(player.starts or 0) / appearances, 3) if appearances else None
    raise ReportRefusal("no_such_measure", f"{key!r} is not a measure this module knows how to read", key=key)  # pragma: no cover - the tables below are the only callers


def _table_measures(left: Side, right: Side, table: tuple[tuple[str, str, str, str], ...]) -> list[dict[str, Any]]:
    return [_measure(key, _read(left, key), _read(right, key), direction, source, note=note) for key, direction, source, note in table]


def _brief(side: Side) -> dict[str, Any]:
    player, club, competition = side.player, side.club, side.competition
    return {
        "slug": player.slug,
        "name": player.name,
        "path": f"/player/{player.slug}",
        "age": int(player.age),
        "position": player.position,
        "positions": side.candidate.positions,
        "band": side.candidate.band,
        "overall": int(player.overall),
        "potential": int(player.potential),
        "asking_fee": side.candidate.asking_fee,
        "club": ({"name": club.name, "slug": club.slug, "path": f"/team/{club.slug}", "overall": int(club.overall)} if club else None),
        "competition": ({"name": competition.name, "tier": int(competition.tier), "slug": competition.slug} if competition else None),
        "observed": side.candidate.observed,
        "stat_lines": side.lines,
        "minutes_in_lines": side.minutes,
    }


def _totals_check(side: Side) -> dict[str, Any]:
    player = side.player
    return {
        "slug": player.slug,
        "stored_minutes": int(player.minutes or 0),
        "lines_minutes": side.minutes,
        "stored_goals": int(player.goals or 0),
        "lines_goals": int(side.totals.get("goals", 0)),
        "stored_appearances": int(player.appearances or 0),
        "lines": side.lines,
        "agree": int(player.minutes or 0) == side.minutes and int(player.goals or 0) == int(side.totals.get("goals", 0)),
    }


def build_comparison(session: Session, left_ident: str, right_ident: str) -> dict[str, Any]:
    """§27's ten dimensions for a pair of stored players, refused in the same style §24 refuses a field."""
    candidates = pool(session)
    sides: list[Candidate] = []
    for ident in (left_ident, right_ident):
        found = next((item for item in candidates if item.player.slug == str(ident) or item.player.id == str(ident)), None)
        if found is None:
            raise ReportRefusal("no_such_player", f"no stored player answers to {str(ident)!r}", ident=str(ident), players_in_pool=len(candidates))
        sides.append(found)
    if sides[0].player.id == sides[1].player.id:
        raise ReportRefusal(
            "same_player",
            "both sides of this comparison are the same stored row, so every measure would print an even line",
            slug=sides[0].player.slug,
            players_in_pool=len(candidates),
            note="§27 asks for Player A against Player B; a pair has to be two players",
        )
    totals = _stat_totals(session, [sides[0].player.id, sides[1].player.id])
    team_ids = [item for item in (sides[0].player.team_id, sides[1].player.team_id) if item] or ["-"]
    clubs = {row.id: row for row in session.scalars(select(Team).where(Team.id.in_(team_ids))).all()}
    left = Side(sides[0], totals[sides[0].player.id], clubs.get(sides[0].player.team_id or ""))
    right = Side(sides[1], totals[sides[1].player.id], clubs.get(sides[1].player.team_id or ""))

    dimensions = [
        _dimension(group, "`app.models.ATTRIBUTES`, one measure per key the group lists", _attribute_measures(left, right, group)) for group in ("technical", "physical", "mental", "tactical")
    ]
    dimensions += [
        _dimension(name, "this project's generated `real_player_match_stats` lines, summed per side", _event_measures(left, right, name)) for name in ("production", "possession", "defensive")
    ]
    dimensions.append(_dimension("progression", "attributes plus the one recorded event that describes it", _progression_measures(left, right), PROGRESSION_RULE))
    dimensions.append(_dimension("age", "each row's stored age against §22's valuation curve", _table_measures(left, right, AGE_MEASURES)))
    dimensions.append(_dimension("context", "each row's club, its competition and the stored appearance split", _table_measures(left, right, CONTEXT_MEASURES)))

    measures = [item for dimension in dimensions for item in dimension["measures"]]
    return {
        "left": _brief(left),
        "right": _brief(right),
        "dimensions": dimensions,
        "overall_line": {
            "left": int(left.player.overall),
            "right": int(right.player.overall),
            "delta": int(left.player.overall) - int(right.player.overall),
            "note": "the two stored overall columns printed side by side, because §27 names Overall as one of the things a comparison must not decide with; this is not the verdict of this payload",
        },
        "counts": {
            "dimensions": len(dimensions),
            "measures": len(measures),
            "by_leader": {leader: sum(1 for item in measures if item["leader"] == leader) for leader in LEADERS},
            "dimension_leaders": {leader: sum(1 for item in dimensions if item["leader"] == leader) for leader in DIMENSION_LEADERS},
        },
        "totals_check": {
            "left": _totals_check(left),
            "right": _totals_check(right),
            "rule": "the stored season columns on `real_players` against the sum of that player's `real_player_match_stats` lines — the same check the player page prints, since a rate is only worth as much as the lines under it",
        },
        "dimensions_list": list(DIMENSIONS),
        "no_single_score": NO_WINNER_NOTE,
        "measure_rule": MEASURE_RULE,
        "world": world_account(session),
        "limitations": limitations(),
        "data_origin": left.player.data_origin if left.player.data_origin == right.player.data_origin else f"{left.player.data_origin}+{right.player.data_origin}",
        "is_demo_data": bool(left.player.is_demo_data or right.player.is_demo_data),
    }


def comparison_ready(session: Session) -> bool:
    """A comparison needs two rows. One is not a pair, and none is not a pair either."""
    return len(pool(session)) >= 2


def comparison_counts(session: Session) -> dict[str, Any]:
    return {"players_in_pool": len(pool(session)), "dimensions": list(DIMENSIONS), "stat_columns": list(STAT_COLUMNS)}


def comparison_problems(session: Session) -> list[str]:
    """Form one comparison over the stored pool and check it holds the structure §27 asked for.

    These are the checks a reader cannot do without: that all ten dimensions are present in the order printed,
    that no composite score crept in under another name, and that every leader is the leader the measures
    beneath it actually give — which is why the ladder below is walked again instead of being handed to
    `_leader_for`. A gate that asks the audited function for its own verdict audits nothing.
    """
    candidates = pool(session)
    if len(candidates) < 2:
        return ["the stored player pool has fewer than two rows, so no pair can be compared here"]
    payload = build_comparison(session, str(candidates[0].player.slug), str(candidates[1].player.slug))
    problems: list[str] = []
    if [item["dimension"] for item in payload["dimensions"]] != list(DIMENSIONS):
        problems.append("the dimensions built are not §27's ten in the order the spec prints them")
    for dimension in payload["dimensions"]:
        measures = dimension["measures"]
        if not measures:
            problems.append(f"`{dimension['dimension']}` has no measures, so its leader is unfounded")
            continue
        recount = {leader: sum(1 for item in measures if item["leader"] == leader) for leader in LEADERS}
        if recount != dimension["counts"]:
            problems.append(f"`{dimension['dimension']}` published counts its own measures do not give")
        # The ladder is walked again here rather than delegated to `_leader_for`: a gate that asks the
        # function it is auditing what the answer should be cannot catch that function being wrong.
        if recount["left"] and recount["right"]:
            expected = "split"
        elif recount["left"]:
            expected = "left"
        elif recount["right"]:
            expected = "right"
        elif recount["even"]:
            expected = "even"
        else:
            expected = "unresolved"
        if expected != dimension["leader"]:
            problems.append(f"`{dimension['dimension']}` is led by {dimension['leader']} but its measures give {expected}")
        for measure in measures:
            if measure["leader"] not in LEADERS:
                problems.append(f"`{dimension['dimension']}.{measure['key']}` has a leader outside the published set")
            if measure["direction"] == "none" and measure["leader"] != "not_scorable":
                problems.append(f"`{measure['key']}` says it cannot be ranked and ranks anyway")
            if measure["direction"] != "none" and measure["left"] is not None and measure["right"] is not None and measure["leader"] == "unknown":
                problems.append(f"`{measure['key']}` has both sides and still calls itself unknown")
            # A measure's own difference is a second, independent copy of the answer: `counts` and the
            # dimension leader are both derived from the leader column, so a leader that was rewritten after
            # the figures were formed slips past those — but not past the subtraction printed beside it.
            delta = measure["delta"]
            if delta is not None:
                if abs(float(delta) - (float(measure["left"]) - float(measure["right"]))) > 1e-6:
                    problems.append(f"`{measure['key']}` prints a delta that is not its own left minus right")
                elif float(delta) != 0.0:
                    points = "left" if (float(delta) > 0) ^ (measure["direction"] == "lower_is_greater") else "right"
                    if measure["leader"] != points:
                        problems.append(f"`{measure['key']}` leads {measure['leader']} while the delta it prints points {points}")
    forbidden = sorted(key for key in payload if key in ("winner", "score", "overall_score", "index", "rating", "combined"))
    if forbidden:
        problems.append(f"the comparison carries {forbidden}, which is the single score §27 rules out")
    if payload["counts"]["measures"] != sum(len(item["measures"]) for item in payload["dimensions"]):
        problems.append("`counts.measures` does not match the measures printed")
    try:
        build_comparison(session, str(candidates[0].player.slug), str(candidates[0].player.slug))
        problems.append("comparing a player with themself was answered instead of refused")
    except ReportRefusal as error:
        if error.code != "same_player":
            problems.append(f"a same-player pair refused as {error.code}, not `same_player`")
    return problems


def limitations() -> list[str]:
    """What this comparison cannot say, printed with it."""
    return [
        "the four attribute dimensions compare stored attribute keys one at a time and do not weight them for a role, which is what §23's role fit is for",
        "Production, Possession and Defensive are rates over this project's own generated stat lines, not over a broadcast tracking feed: a side with no lines has those measures printed as `unknown`, never as zero",
        "Progression has no progressive-carry event in these lines, so it is answered by three attributes and key passes, and it is a weaker dimension than the other three event dimensions",
        "the Age dimension prints `age` with no leader on purpose: a two-year gap decides nothing by itself, and `age_curve` and `years_past_peak` are the parts that touch a fee",
        "Context is the stored club, its competition and the starts split — not a tactical system, a coach or the quality of the players around them, none of which this comparison has evidence for",
        "no model call is involved anywhere here: nothing in this payload has an opinion about either player, and there is no number in it that ranks the pair as a whole",
    ]


__all__ = [
    "AGE_MEASURES",
    "CONTEXT_MEASURES",
    "DIMENSIONS",
    "DIMENSION_LEADERS",
    "DIMENSION_RULE",
    "EVENT_MEASURES",
    "LEADERS",
    "MEASURE_RULE",
    "NO_WINNER_NOTE",
    "PROGRESSION_ATTRIBUTES",
    "PROGRESSION_RULE",
    "STAT_COLUMNS",
    "Side",
    "build_comparison",
    "comparison_counts",
    "comparison_problems",
    "comparison_ready",
    "limitations",
]
