"""The scout's search: a requirement waterfall over the stored world, ranked by published arithmetic (M7, spec §23).

A search here is not a guess dressed up as a list. It is three things a reader can check:

* **A waterfall.** Each requirement the parser produced gets its own step, and each step reports how many
  rows it started with and how many it left. A shortlist that dropped 3,000 players to 3 is therefore
  legible: the reader can see which phrase did the cutting, and can ask for that phrase again without it.
* **Published arithmetic, twice over.** The fee beside a candidate is the market's own valuation formula
  (`app/services/simulation/market.py`) run on that player's stored row, and the ranking is the sorting
  `SORT_FORMULA` describes. Nothing here invents a second pricing model or a hidden score.
* **A refusal that survives the search.** A requirement the vocabulary did not understand is carried on the
  response beside the rows it did not filter, so a page cannot print "here are 12 left-footed strikers" when
  the foot was one of the phrases the parser refused. §23's example asks for an inverted full-back; this
  build has no such role, and the answer says so in the same breath as the players it did find.

What is deliberately *not* here: no model call, no embeddings, no relevance score. §23's scout is a query
planner over rows this project generated, and an answer built on arithmetic cannot drift from the rows it
claims to read. The language layer that decides *what* to filter is `requirements.py`; this module obeys that
and reports the cost.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Career, RealPlayer, Team
from app.services.attributes import ALL_ATTRIBUTES
from app.services.scouting.requirements import (
    BAND_RULE,
    CONNECTORS,
    FILTER_KINDS,
    FOOT_RULE,
    MATCH_RULE,
    MONEY_RULE,
    ROLE_POSITIONS,
    SAMPLE_REQUIREMENTS,
    SCOUT_DISCLAIMER,
    SORT_FORMULA,
    SORTS,
    STAFFED_POSITIONS,
    SUGGESTION_FORMULA,
    UNSTAFFED_POSITIONS,
    Parsed,
    Requirement,
    vocabulary_problems,
)
from app.services.simulation import market
from app.services.simulation.profile import BANDS, band_of_position
from app.services.tactics.feedback import fit_rows
from app.services.tactics.roles import ROLES, TACTICAL_ATTRIBUTES

DEFAULT_LIMIT: Final = 20
MAX_LIMIT: Final = 60
SORT_KEYS: Final = ("overall", "potential", "headroom", "value_for_money", "need_fit", "cheapest", "youth")

#: A candidate is *observed* when the world stores a season line for them. The distinction matters because
#: §24 forbids ungrounded praise: attributes exist for every generated player, minutes only for the ones who
#: played, and a report that quotes a rating for a player with no appearances is quoting nothing.
OBSERVED_RULE: Final = (
    "observed = the stored row carries at least one appearance; appearances, minutes, goals, assists and rating are "
    "published as null for a candidate who has not been observed rather than as zero, because zero would be a measurement"
)

WATERFALL_RULE: Final = (
    "the stored player rows are the starting pool; each filter is applied in the order the request stated it, and every "
    "step reports `rows_in` and `rows_out` for its own cut, so a shortlist can be read back as the sequence of phrases that produced it"
)

RANK_RULE: Final = (
    f"{SORT_FORMULA}. The sort is applied to the rows that survived every filter, never instead of them, and a tie is "
    "broken on the player's slug so the same pool answers the same question the same way twice"
)

SCAN_NOTE: Final = (
    "the waterfall is a scan of the stored player rows in Python, not an index: `rows_examined` is the size of the pool every "
    "step started from, and a search costs one read of that table plus the arithmetic below it"
)

VALUATION_NOTE: Final = (
    "the fee beside a candidate is this project's valuation of their stored row — the same arithmetic the transfer market prices a listing with — not a price any club has answered at"
)


class SearchRefusal(RuntimeError):
    """A search this build cannot run, with the numbers that decided it."""

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), **self.detail}


@dataclass
class Step:
    """One filter's effect on the pool, in the order the request stated it."""

    kind: str
    field: str
    phrase: str
    rows_in: int
    rows_out: int
    rule: str
    source: str = "parsed"
    detail: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "field": self.field,
            "phrase": self.phrase,
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "cut": self.rows_in - self.rows_out,
            "rule": self.rule,
            "source": self.source,
            **({"example_of_a_row_dropped": self.detail} if self.detail else {}),
        }


@dataclass
class Candidate:
    """A stored player plus every figure this search computes over that row."""

    player: RealPlayer
    club_name: str
    club_slug: str
    valuation: dict[str, Any]

    @property
    def asking_fee(self) -> int:
        return int(self.valuation["asking_fee"])

    @property
    def band(self) -> str:
        return band_of_position(self.player.position)

    @property
    def positions(self) -> list[str]:
        codes = [self.player.position, *[str(item) for item in self.player.secondary_positions or []]]
        return list(dict.fromkeys(codes))

    @property
    def observed(self) -> bool:
        return int(self.player.appearances or 0) > 0

    def attribute(self, key: str) -> int:
        return int((self.player.attributes or {}).get(key, 0) or 0)

    def headroom(self) -> int:
        return int(self.player.potential) - int(self.player.overall)

    def value_for_money(self) -> float:
        return round(int(self.player.overall) * 1_000_000 / max(self.asking_fee, market.CREDIT_ROUND), 3)

    def to_dict(self, *, wanted_attributes: list[str], answers: list[dict[str, Any]], fit: dict[str, Any] | None, role_fit: dict[str, Any] | None) -> dict[str, Any]:
        player = self.player
        return {
            "slug": player.slug,
            "name": player.name,
            "path": f"/player/{player.slug}",
            "age": int(player.age),
            "position": player.position,
            "positions": self.positions,
            "band": self.band,
            "preferred_foot": player.preferred_foot,
            "overall": int(player.overall),
            "potential": int(player.potential),
            "headroom": self.headroom(),
            "archetype": player.archetype,
            "attributes": {key: self.attribute(key) for key in wanted_attributes},
            "club": ({"name": self.club_name, "slug": self.club_slug, "path": f"/team/{self.club_slug}"} if self.club_slug else None),
            "observed": self.observed,
            "season": (
                {
                    "appearances": int(player.appearances),
                    "minutes": int(player.minutes),
                    "goals": int(player.goals),
                    "assists": int(player.assists),
                    "rating": round(float(player.rating), 2),
                }
                if self.observed
                else None
            ),
            "valuation": {key: self.valuation[key] for key in ("asking_fee", "release_clause", "weekly_wage", "contract_years", "quality_points", "headroom_points", "age_curve")},
            "value_for_money": self.value_for_money(),
            "tactical_fit": fit,
            "role_fit": role_fit,
            "answers": answers,
            "data_origin": player.data_origin,
            "is_demo_data": bool(player.is_demo_data),
        }


def pool(session: Session) -> list[Candidate]:
    """Every stored player, with the club their row points at and the valuation their row implies.

    Ordered by slug before anything else, so a later tie-break and the database cannot disagree.
    """
    rows = list(session.execute(select(RealPlayer, Team.name, Team.slug).outerjoin(Team, Team.id == RealPlayer.team_id).order_by(RealPlayer.slug)).all())
    return [Candidate(player=row[0], club_name=row[1] or "", club_slug=row[2] or "", valuation=market.valuation(row[0])) for row in rows]


def world_account(session: Session) -> dict[str, Any]:
    """What was scanned, counted in the database rather than from the list this page returns."""
    players = int(session.scalar(select(func.count(RealPlayer.id))) or 0)
    attached = int(session.scalar(select(func.count(RealPlayer.id)).where(RealPlayer.team_id.is_not(None))) or 0)
    return {
        "players_stored": players,
        "players_at_a_club": attached,
        "players_with_no_club": players - attached,
        "clubs_stored": int(session.scalar(select(func.count(Team.id))) or 0),
        "rule": WATERFALL_RULE,
    }


def _meets(candidate: Candidate, requirement: Requirement) -> tuple[bool, dict[str, Any]]:
    """Whether one row answers one requirement, and the figures that said so."""
    kind = requirement.kind
    if kind == "age_max":
        return int(candidate.player.age) <= int(requirement.value), {"age": int(candidate.player.age), "stated": int(requirement.value)}
    if kind == "age_min":
        return int(candidate.player.age) >= int(requirement.value), {"age": int(candidate.player.age), "stated": int(requirement.value)}
    if kind == "foot":
        stored = str(candidate.player.preferred_foot)
        return stored == str(requirement.value), {"stored_foot": stored, "stated": str(requirement.value)}
    if kind == "position":
        return requirement.value in candidate.positions, {"positions": candidate.positions, "stated": requirement.value}
    if kind == "band":
        bands = sorted({band_of_position(code) for code in candidate.positions} - {""})
        return requirement.value in bands, {"bands": bands, "stated": requirement.value}
    if kind == "role":
        staffed = list(ROLE_POSITIONS.get(str(requirement.value), ()))
        return bool(set(staffed) & set(candidate.positions)), {"positions": candidate.positions, "occupiable_by": staffed}
    if kind == "attribute_min":
        key = str(requirement.field).split(".")[-1]
        return candidate.attribute(key) >= int(requirement.value), {"attribute": key, "have": candidate.attribute(key), "floor": int(requirement.value)}
    if kind == "fee_max":
        return candidate.asking_fee <= int(requirement.value), {"asking_fee": candidate.asking_fee, "stated": int(requirement.value)}
    return False, {"unhandled_kind": kind}


def _rule_for(requirement: Requirement) -> str:
    if requirement.kind == "role":
        staffed = ", ".join(ROLE_POSITIONS.get(str(requirement.value), ())) or "no stored position"
        return f"{MATCH_RULE}; the {ROLES[str(requirement.value)].label} slot is occupied by {staffed}"
    if requirement.kind == "band":
        return f"{BAND_RULE}; this request asked for {requirement.value} ({', '.join(BANDS[str(requirement.value)])})"
    if requirement.kind == "fee_max":
        return f"{requirement.rule}; {VALUATION_NOTE}"
    return requirement.rule


def _role_fit(candidate: Candidate, role_key: str) -> dict[str, Any]:
    """The role's tactical demands against this player's stored tactical attributes — a fit, never a cut."""
    role = ROLES[role_key]
    rows = fit_rows(role.demands, {key: candidate.attribute(key) for key in role.demands})
    return {"role": role_key, "label": role.label, "board_band": role.band, "occupiable_by": list(ROLE_POSITIONS.get(role_key, ())), "risk": role.risk, **rows}


def _sort_key(sort: str, need: dict[str, Any] | None) -> Any:
    if sort == "overall":
        return lambda candidate: (-int(candidate.player.overall), candidate.player.slug)
    if sort == "potential":
        return lambda candidate: (-int(candidate.player.potential), candidate.player.slug)
    if sort == "headroom":
        return lambda candidate: (-candidate.headroom(), candidate.player.slug)
    if sort == "value_for_money":
        return lambda candidate: (-candidate.value_for_money(), candidate.player.slug)
    if sort == "need_fit":
        if need is None:
            raise SearchRefusal("need_fit_needs_career", "sorting by need fit asks which band a club is weakest in, which only a career can answer", sort=sort)
        wanted_band = str(need["needed_band"])
        return lambda candidate: (-float(market.tactical_fit(candidate.player, wanted_band)["fit"]), candidate.player.slug)
    if sort == "cheapest":
        return lambda candidate: (candidate.asking_fee, candidate.player.slug)
    if sort == "youth":
        return lambda candidate: (int(candidate.player.age), candidate.player.slug)
    raise SearchRefusal("unknown_sort", f"{sort!r} is not one of the published sortings", sort=sort, sorts=list(SORT_KEYS))


def search(
    session: Session,
    parsed: Parsed,
    *,
    career: Career | None = None,
    round_index: int | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Run the requirement waterfall and rank what survives.

    The search takes a `Parsed` rather than a list of requirements on purpose: the refusals and assumptions
    travel in the same object as the filters, so no caller can produce a candidate list that quietly dropped
    the phrase it did not understand. A career is optional because "who fits *my* squad" needs one — `need` is
    computed only for a career, and a sort that asks for it without one is refused rather than guessed at.
    """
    cap = max(1, min(int(limit), MAX_LIMIT))
    requirements = list(parsed.requirements)
    filters = [item for item in requirements if item.kind != "sort"]
    sort = next((str(item.value) for item in requirements if item.kind == "sort"), "overall")
    if sort not in SORT_KEYS:
        raise SearchRefusal("unknown_sort", f"{sort!r} is not one of the published sortings", sort=sort, sorts=list(SORT_KEYS))

    candidates = pool(session)
    need: dict[str, Any] | None = None
    if career is not None:
        need = market.club_need(session, career, round_index=int(round_index if round_index is not None else career.rounds_played))
    elif sort == "need_fit":
        raise SearchRefusal(
            "need_fit_needs_career",
            f"sorting by {sort!r} asks which band this club is weakest in, and that is a question about a squad a career owns",
            sort=sort,
            see="/api/v1/scout/rules",
        )

    steps: list[Step] = []
    #: What each surviving row measured against each phrase, so a candidate can be read back as the request that found it.
    answered: dict[str, list[dict[str, Any]]] = {}
    survivors = candidates
    for requirement in filters:
        rows_in = len(survivors)
        kept: list[Candidate] = []
        dropped: dict[str, Any] = {}
        for candidate in survivors:
            ok, detail = _meets(candidate, requirement)
            if ok:
                answered.setdefault(candidate.player.id, []).append({"phrase": requirement.phrase, "kind": requirement.kind, **detail})
                kept.append(candidate)
            elif not dropped:
                dropped = detail
        survivors = kept
        steps.append(
            Step(
                kind=requirement.kind,
                field=requirement.field,
                phrase=requirement.phrase,
                rows_in=rows_in,
                rows_out=len(survivors),
                rule=_rule_for(requirement),
                source=requirement.source,
                detail=dropped,
            )
        )

    survivors.sort(key=_sort_key(sort, need))
    page = survivors[:cap]
    role_keys = [str(item.value) for item in filters if item.kind == "role"]
    wanted = sorted(
        {str(item.field).split(".")[-1] for item in filters if item.kind == "attribute_min"} | set(TACTICAL_ATTRIBUTES) | ({key for key in ROLES[role_keys[0]].demands} if role_keys else set())
    )
    rows = [
        candidate.to_dict(
            wanted_attributes=wanted,
            answers=answered.get(candidate.player.id, []),
            fit=(dict(market.tactical_fit(candidate.player, str(need["needed_band"])), formula=market.FIT_FORMULA) if need else None),
            role_fit=(_role_fit(candidate, role_keys[0]) if role_keys else None),
        )
        for candidate in page
    ]
    return {
        "query": parsed.text,
        "requirements": [item.to_dict() for item in requirements],
        "filters_applied": len(filters),
        "waterfall": [step.to_dict() for step in steps],
        "waterfall_rule": WATERFALL_RULE,
        "world": world_account(session),
        "rows_examined": len(candidates),
        "sort": {"key": sort, "formula": RANK_RULE, "applied_to": len(survivors), "career_dependent": need is not None},
        "candidates": rows,
        "returned": len(rows),
        "total_matches": len(survivors),
        "truncated": len(survivors) > len(rows),
        "limit": cap,
        "max_limit": MAX_LIMIT,
        "refused": [item.to_dict() for item in parsed.refused],
        "assumptions": list(parsed.assumptions),
        "connectors_ignored": list(parsed.connectors),
        "unaccounted": list(parsed.unaccounted),
        "need": need,
        "career": ({"slug": career.slug, "club_name": career.club_name, "season": career.season, "rounds_played": career.rounds_played} if career else None),
        "suggestion_formula": SUGGESTION_FORMULA,
        "match_rule": MATCH_RULE,
        "observed_rule": OBSERVED_RULE,
        "valuation_note": VALUATION_NOTE,
        "scan_note": SCAN_NOTE,
        "limitations": limitations(),
        "rules": {"money": MONEY_RULE, "feet": FOOT_RULE, "bands": BAND_RULE, "rank": RANK_RULE, "valuation": market.VALUATION_FORMULA},
        "data_origin": "simulation",
        "is_demo_data": True,
        "disclaimer": SCOUT_DISCLAIMER,
    }


def search_problems(session: Session) -> list[str]:
    """Run every requirement kind the parser can emit against a stored candidate and report the unhandled ones.

    This is the cross-module gate: `requirements.py` publishes `FILTER_KINDS` and `SORTS`, and a kind the
    search cannot answer would silently drop a filter — the pool would look filtered when it was not. Each
    check is executed against a real row rather than compared against a list of names, so a handler that was
    deleted cannot pass it by editing a constant.
    """
    problems: list[str] = []
    if set(SORT_KEYS) != set(SORTS):
        problems.append(f"the parser publishes the sortings {sorted(SORTS)} and the search can apply {sorted(SORT_KEYS)}")
    candidates = pool(session)
    if not candidates:
        return [f"the search has no stored player rows to answer a requirement over: {len(SAMPLE_REQUIREMENTS)} kinds and {len(SORT_KEYS)} sortings are unproven", *problems]
    probe = candidates[0]
    for requirement in SAMPLE_REQUIREMENTS:
        if requirement.kind == "sort":
            continue
        _, detail = _meets(probe, requirement)
        if "unhandled_kind" in detail:
            problems.append(f"requirement kind {requirement.kind!r} reaches the search and answers `unhandled_kind`")
    probed = {item.kind for item in SAMPLE_REQUIREMENTS if item.kind != "sort"}
    for kind in FILTER_KINDS:
        if kind not in probed:
            problems.append(f"the parser publishes kind {kind!r} and no probe ever asks the search to handle it")
    for sort in SORT_KEYS:
        try:
            _sort_key(sort, {"needed_band": "midfield"})(probe)
        except SearchRefusal as error:
            problems.append(f"sorting {sort!r} is published and refuses: {error}")
        except Exception as error:  # noqa: BLE001 - a probe reports any failure rather than raising one
            problems.append(f"sorting {sort!r} is published and crashes on a stored row: {type(error).__name__}: {error}")
    return problems


def scout_counts(session: Session) -> dict[str, Any]:
    """How much vocabulary and how many rows the scout has to work with, counted rather than asserted."""
    return {
        "positions": len(STAFFED_POSITIONS),
        "positions_unstaffed": len(UNSTAFFED_POSITIONS),
        "roles": len(ROLES),
        "roles_occupiable": sum(1 for key in ROLE_POSITIONS if ROLE_POSITIONS[key]),
        "attributes": len(ALL_ATTRIBUTES),
        "sortings": len(SORT_KEYS),
        "connectors": len(CONNECTORS),
        **world_account(session),
    }


def scout_ready(session: Session) -> bool:
    """Whether the scout can serve: the vocabulary agrees with itself, the search answers every kind, rows exist.

    Deliberately not "someone has run a search" — the gate is whether the surface works, and the counts
    beside it say how much of the world it can read.
    """
    from app.services.world import world_ready

    return not vocabulary_problems() and not search_problems(session) and world_ready(session)


def limitations() -> list[str]:
    """What this search does not know, said before a reader assumes it does."""
    return [
        "the scout scans every stored player, including any the world holds at no club; §22's market offers only players another club stores, so a candidate with `club: null` is a player this build's transfer market does not list",
        "a fee beside a candidate is this project's valuation of their row, which is not necessarily what the club holding them would answer — that number is the market's negotiation, and only a market listing carries it",
        "an unobserved candidate has attributes and no season line: appearances, minutes, goals, assists and rating are published as null rather than as zero, because a generated player who never played has not been measured",
        "role fit is reported as the role's tactical demands against the player's stored tactical attributes; it is never a cut, so no candidate here was dropped for being a poor fit for a role",
        "the two band vocabularies in this project disagree by name: `simulation/profile.BANDS` keys the four bands the engine measures (keeper, defence, midfield, attack) and `tactics/roles.BANDS` keys the board's zones (goalkeeper, defensive, midfield, attacking). A band requirement here is the profile's, and a role's own zone is published as `role_fit.board_band`",
        "no model call is involved: the requirements are vocabulary arithmetic and nothing in this response was generated as prose",
    ]


__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "OBSERVED_RULE",
    "RANK_RULE",
    "SCAN_NOTE",
    "SORT_KEYS",
    "Candidate",
    "SearchRefusal",
    "Step",
    "VALUATION_NOTE",
    "WATERFALL_RULE",
    "limitations",
    "pool",
    "search",
    "world_account",
]
