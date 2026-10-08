"""M7 §24 — a scouting report in which every line names the row, formula or count behind it.

§24 asks for a *structured* report and then draws the line under it: 不要输出没有依据的"天赋". So this
module is built the other way round from a prose generator: the thirteen fields are chosen first, and each
one is answered only by a figure that can be recomputed from a stored row —

* the four group scores (§24's Technical / Physical / Mental / Tactical) are means over
  `app.models.ATTRIBUTES`, which is the taxonomy this project's own player rows are written in. The report
  does not invent a grouping and does not average a missing attribute as a zero: `measured` counts the keys
  the row actually holds and `missing` names the rest;
* Current Level carries the stored `overall` *and* the value `compute_overall` derives from the same
  attributes, because a report that printed one number and had quietly used the other would be unauditable;
* Potential is `potential - overall` beside the age-curve share §22's valuation already uses, so the ceiling
  and the years left to reach it are the same arithmetic the fee was;
* Role Fit is §23's role fit, called through the same function the search used, and Team Fit is §22's
  `tactical_fit` against the band a career is thinnest in;
* Cost is `market.valuation` for that row;
* Comparison refuses rather than comparing to nobody;
* Recommendation is a ladder over the figures above, published as `RECOMMENDATION_RULE` with the two
  deciding numbers beside the verdict.

Nothing here calls a model. That is stated in `limitations()` too, because "AI Scout" invites a reader to
expect generated prose about a player's character, and this build has no evidence for a word of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ATTRIBUTES, Career, RealPlayer
from app.services.attributes import compute_overall
from app.services.scouting.search import Candidate, _role_fit, pool, world_account
from app.services.simulation import market
from app.services.simulation.profile import band_of_position
from app.services.tactics.roles import ROLES

#: The §24 field list, in the order the spec prints it. Published so a page and a test can hold the report
#: to the structure that was asked for rather than to whatever the module happened to fill.
REPORT_FIELDS: Final = (
    "player",
    "current_level",
    "potential",
    "technical",
    "physical",
    "mental",
    "tactical",
    "role_fit",
    "team_fit",
    "risk",
    "cost",
    "comparison",
    "recommendation",
)

GROUP_RULE: Final = (
    "a group score is the unweighted mean over the stored `attributes` keys this project lists under that group (`app.models.ATTRIBUTES`); "
    "a key the row does not hold is named in `missing` and is not averaged as zero"
)
LEVEL_RULE: Final = (
    "`current_level.overall` is the stored column; `recomputed` is `compute_overall(position, attributes)` over the same row's attributes, "
    "and `percentile` is the share of stored players at or below that overall, counted in the database"
)
POTENTIAL_RULE: Final = (
    "`headroom` is `potential - overall` from the row; `age_curve` is §22's valuation curve for the stored age, so the ceiling and the fee are priced against the same years-left assumption"
)
RECOMMENDATION_RULE: Final = (
    "the verdict is a ladder over the figures in this report, first match wins: "
    "`sign now` when current level is at or above the band median and the fit this report carries (`role_fit.mean_gap`, or `team_fit.fit` when no role was asked) is non-negative; "
    "`develop` when headroom is at least 5 and the age curve is still at full value; "
    "`monitor` when fit is negative but the level is above the band median; "
    "`pass` otherwise. `decided_by` names the two figures that matched"
)
COMPARISON_RULE: Final = "deltas are `this - other` per §24 group, plus overall, headroom, asking fee and value-for-money; both sides are stored rows read the same way"


class ReportRefusal(ValueError):
    """A report field that cannot be answered, said as plainly as a parser refuses a word."""

    def __init__(self, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.extra}


#: §51's sets for this tier — the split `/scout`'s report and compare doors used to keep in a local
#: constant (`POOL_NOT_FOUND_CODES`): a name that is not in the stored pool is a 404 (the row is
#: genuinely not there) while a word this catalogue does not hold answers 422. Registered here the
#: split is one fact, and `answers.ANSWERS` is the only copy the routers read.
NOT_FOUND_CODES: Final = frozenset({"no_such_player"})
UNPROCESSABLE_CODES: Final = frozenset({"no_such_measure", "same_player", "unknown_role"})


@dataclass
class GroupScore:
    """One of §24's four group lines, with the keys that produced the mean."""

    group: str
    attributes: dict[str, int]
    mean: float
    strongest: str
    weakest: str
    measured: int
    missing: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "group": self.group,
            "attributes": self.attributes,
            "mean": self.mean,
            "strongest": self.strongest,
            "weakest": self.weakest,
            "measured": self.measured,
            "missing": self.missing,
            "rule": GROUP_RULE,
        }


def group_score(candidate: Candidate, group: str) -> GroupScore:
    """The mean over the attributes a row actually carries for one §24 group."""
    stored = candidate.player.attributes or {}
    keys = list(ATTRIBUTES[group])
    have = {key: int(stored[key]) for key in keys if key in stored}
    missing = [key for key in keys if key not in have]
    if not have:  # pragma: no cover - every generated row carries all twenty-seven keys; a hand-made row may not
        return GroupScore(group, {}, 0.0, "", "", 0, missing)
    ranked = sorted(have.items(), key=lambda item: (-item[1], item[0]))
    return GroupScore(
        group,
        have,
        round(sum(have.values()) / len(have), 2),
        ranked[0][0],
        ranked[-1][0],
        len(have),
        missing,
    )


def _percentile(session: Session, candidate: Candidate, candidates: list[Candidate]) -> dict[str, Any]:
    """Where this row's overall sits among the stored pool, counted twice: whole pool and own band."""
    overall = int(candidate.player.overall)
    total = int(session.scalar(select(func.count()).select_from(RealPlayer)) or 0)
    at_or_below = int(session.scalar(select(func.count()).select_from(RealPlayer).where(RealPlayer.overall <= overall)) or 0)
    band = str(band_of_position(candidate.player.position))
    same_band = [item for item in candidates if item.band == band]
    band_below = sum(1 for item in same_band if int(item.player.overall) <= overall)
    return {
        "overall": overall,
        "players_in_pool": total,
        "at_or_below": at_or_below,
        "share_of_pool": round(at_or_below / total, 3) if total else 0.0,
        "band": band,
        "players_in_band": len(same_band),
        "share_of_band": round(band_below / len(same_band), 3) if same_band else 0.0,
        "rule": LEVEL_RULE,
    }


def _level(session: Session, candidate: Candidate, candidates: list[Candidate]) -> dict[str, Any]:
    player = candidate.player
    recomputed = compute_overall(str(player.position), {key: int(value) for key, value in (player.attributes or {}).items()})
    row = _percentile(session, candidate, candidates)
    row.update(
        {
            "recomputed": recomputed,
            "agrees_with_stored": recomputed == int(player.overall),
            "archetype": str(player.archetype or ""),
            "archetype_match": round(float(player.archetype_match or 0.0), 3),
        }
    )
    return row


def _potential(candidate: Candidate) -> dict[str, Any]:
    player = candidate.player
    age = int(player.age)
    return {
        "potential": int(player.potential),
        "overall": int(player.overall),
        "headroom": candidate.headroom(),
        "age": age,
        "age_curve": market.age_curve(age),
        "peak_age_end": market.PEAK_AGE_END,
        "years_past_peak": max(0, age - market.PEAK_AGE_END),
        "rule": POTENTIAL_RULE,
    }


def _cost(candidate: Candidate, career: Career | None) -> dict[str, Any]:
    valuation = dict(candidate.valuation)
    fee = int(valuation["asking_fee"])
    wage = int(valuation["weekly_wage"])
    row: dict[str, Any] = {
        "asking_fee": fee,
        "weekly_wage": wage,
        "season_wage": wage * 52,
        "wage_share_of_fee": round(wage * 52 / fee, 4) if fee else 0.0,
        "release_clause": int(valuation["release_clause"]),
        "contract_years": int(valuation["contract_years"]),
        "value_for_money": candidate.value_for_money(),
        "components": {key: valuation[key] for key in ("quality_points", "headroom_points", "age_curve") if key in valuation},
        "formula": market.VALUATION_FORMULA,
        "note": "the fee is this project's valuation of the row, not an offer a holding club would answer; only a §22 market listing carries an answer",
    }
    if career is not None:
        budget = int(career.budget)
        row["against_career_budget"] = {
            "budget": budget,
            "units": career.budget_units,
            "share_of_budget": round(fee / budget, 4) if budget else None,
            "fits_without_selling": fee <= budget,
            "rule": "the fee beside §22's stored budget for this career, which is what a manager would actually spend against; no transfer is attempted here",
        }
    return row


def _risk(candidate: Candidate, *, team_fit: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Named factors, each with the figure that raised it. An empty list means no factor matched, not no risk."""
    player = candidate.player
    factors: list[dict[str, Any]] = []
    if int(player.appearances or 0) == 0:
        factors.append({"factor": "unobserved_season", "value": 0, "rule": "the row carries no appearance, so nothing in this report is measured from played minutes"})
    curve = float(market.age_curve(int(player.age)))
    if curve < 1.0:
        direction = "past" if int(player.age) > market.PEAK_AGE_END else "before"
        factors.append(
            {"factor": "below_full_value_age", "value": int(player.age), "rule": f"§22 prices this age at {curve} of the same attributes {direction} the plateau, which is why the fee is what it is"}
        )
    headroom = candidate.headroom()
    if headroom <= 0:
        factors.append({"factor": "no_headroom", "value": headroom, "rule": "`potential - overall` is not above zero, so the stored ceiling is the level already reached"})
    elif headroom >= 10:
        factors.append(
            {"factor": "wide_headroom", "value": headroom, "rule": "headroom of this size is a ceiling in a generated row, not a measurement of progress; §24's risk line names it and stops there"}
        )
    wage = int(candidate.valuation["weekly_wage"])
    fee = max(int(candidate.valuation["asking_fee"]), 1)
    if wage * 52 / fee > 0.5:
        factors.append({"factor": "wage_heavy", "value": round(wage * 52 / fee, 3), "rule": "one season of wages is more than half the asking fee, so the fee is not the cost"})
    if team_fit is not None and int(team_fit.get("club_stores_in_band", 0)) >= 4:
        factors.append({"factor": "band_is_already_crowded", "value": int(team_fit["club_stores_in_band"]), "rule": "this club already stores at least four players in the band this candidate fills"})
    return factors


def _team_fit(session: Session, candidate: Candidate, career: Career | None, round_index: int | None) -> dict[str, Any] | None:
    if career is None:
        return None
    need = market.club_need(session, career, round_index=int(round_index if round_index is not None else career.rounds_played))
    fit = market.tactical_fit(candidate.player, str(need["needed_band"]))
    squad = list(session.scalars(select(RealPlayer).where(RealPlayer.team_id == career.club_id)))
    in_band = [row for row in squad if band_of_position(row.position) == str(need["needed_band"])]
    return {
        "career": career.slug,
        "club": {"name": career.club_name, "id": career.club_id},
        "needed_band": need["needed_band"],
        "bands": need["bands"],
        "positions_in_band": need["positions_in_band"],
        "fit": fit["fit"],
        "formula": market.FIT_FORMULA,
        "club_stores_in_band": len(in_band),
        "candidate_already_lists_there": candidate.player.team_id == career.club_id,
        "rule": "team fit is §22's tactical fit for the band this club is weakest in at the round the career has reached, and the count beside it is the players that club's own rows already carry in that band",
    }


def _comparison(session: Session, candidate: Candidate, other: Candidate | None) -> dict[str, Any] | None:
    if other is None:
        return None
    groups = {group: round(float(group_score(candidate, group).mean) - float(group_score(other, group).mean), 2) for group in ATTRIBUTES}
    return {
        "other": {"slug": other.player.slug, "name": other.player.name, "overall": int(other.player.overall), "path": f"/player/{other.player.slug}"},
        "groups": groups,
        "overall": int(candidate.player.overall) - int(other.player.overall),
        "headroom": candidate.headroom() - other.headroom(),
        "asking_fee": candidate.asking_fee - other.asking_fee,
        "value_for_money": round(candidate.value_for_money() - other.value_for_money(), 3),
        "rule": COMPARISON_RULE,
    }


def _recommendation(level: dict[str, Any], potential: dict[str, Any], role_fit: dict[str, Any] | None, team_fit: dict[str, Any] | None, risks: list[dict[str, Any]]) -> dict[str, Any]:
    """The ladder in `RECOMMENDATION_RULE`, over the figures this report already published."""
    band_median = 0.5
    # `mean_gap` is `have - demanded`, so a negative gap IS a shortfall. Negating it here would read a
    # player who is short in two of three role demands as a positive fit, and the report would then
    # publish a `decided_by` figure that contradicted its own `role_fit` line.
    fit: float | None = None
    evidence = ""
    if role_fit is not None:
        fit = float(role_fit["mean_gap"])
        evidence = "role_fit.mean_gap"
    elif team_fit is not None:
        fit = float(team_fit["fit"])
        evidence = "team_fit.fit"
    above_median = float(level["share_of_band"]) >= band_median
    decided: list[str] = []
    if above_median and (fit is None or fit >= 0):
        verdict = "sign now"
        decided = [f"share_of_band {level['share_of_band']}", (f"{evidence} {round(fit, 3)}" if fit is not None else "no fit was asked for")]
    elif int(potential["headroom"]) >= 5 and float(potential["age_curve"]) >= 1.0:
        verdict = "develop"
        decided = [f"headroom {potential['headroom']}", f"age_curve {potential['age_curve']}"]
    elif fit is not None and fit < 0 and above_median:
        verdict = "monitor"
        decided = [f"{evidence} {round(fit, 3)}", f"share_of_band {level['share_of_band']}"]
    else:
        verdict = "pass"
        decided = [f"share_of_band {level['share_of_band']}", f"headroom {potential['headroom']}"]
    return {
        "verdict": verdict,
        "decided_by": decided,
        "risk_factors_named": len(risks),
        "rule": RECOMMENDATION_RULE,
        "note": "this verdict is arithmetic over the figures above. No model was asked what it thinks of this player, and this build has no evidence for a sentence about their character",
    }


def find_comparator(ident: str, candidates: list[Candidate]) -> Candidate:
    """The same row the pool carries, found by slug or id rather than by a second read of the table."""
    for item in candidates:
        if item.player.slug == ident or item.player.id == ident:
            return item
    raise ReportRefusal("no_such_player", f"{ident!r} is not in the pool this report reads", ident=ident)


def build_report(session: Session, ident: str, *, role: str | None = None, career: Career | None = None, compare_to: str | None = None, round_index: int | None = None) -> dict[str, Any]:
    """§24's thirteen fields for one stored player, every figure recomputed from the row on the request."""
    candidates = pool(session)
    try:
        candidate = find_comparator(ident, candidates)
    except ReportRefusal:
        raise ReportRefusal("no_such_player", f"no stored player answers to {ident!r}", ident=ident) from None
    if role is not None and role not in ROLES:
        raise ReportRefusal("unknown_role", f"{role!r} is not one of the roles this catalogue holds", role=role, roles=sorted(ROLES))
    role_fit = _role_fit(candidate, str(role)) if role else None
    team_fit = _team_fit(session, candidate, career, round_index)
    level = _level(session, candidate, candidates)
    potential = _potential(candidate)
    risks = _risk(candidate, team_fit=team_fit)
    other = find_comparator(str(compare_to), candidates) if compare_to else None
    return {
        "player": {
            "slug": candidate.player.slug,
            "name": candidate.player.name,
            "path": f"/player/{candidate.player.slug}",
            "age": int(candidate.player.age),
            "position": candidate.player.position,
            "positions": candidate.positions,
            "band": candidate.band,
            "preferred_foot": candidate.player.preferred_foot,
            "club": ({"name": candidate.club_name, "slug": candidate.club_slug, "path": f"/team/{candidate.club_slug}"} if candidate.club_slug else None),
            "observed": candidate.observed,
        },
        "current_level": level,
        "potential": potential,
        "technical": group_score(candidate, "technical").to_dict(),
        "physical": group_score(candidate, "physical").to_dict(),
        "mental": group_score(candidate, "mental").to_dict(),
        "tactical": group_score(candidate, "tactical").to_dict(),
        "role_fit": role_fit,
        "team_fit": team_fit,
        "risk": risks,
        "cost": _cost(candidate, career),
        "comparison": _comparison(session, candidate, other),
        "recommendation": _recommendation(level, potential, role_fit, team_fit, risks),
        "fields": list(REPORT_FIELDS),
        "world": world_account(session),
        "groups": {group: list(keys) for group, keys in ATTRIBUTES.items()},
        "limitations": limitations(),
        "data_origin": candidate.player.data_origin,
        "is_demo_data": bool(candidate.player.is_demo_data),
    }


def report_ready(session: Session) -> bool:
    """Whether a report can be answered here at all: it reads the stored pool and nothing else."""
    return bool(pool(session))


def report_counts(session: Session) -> dict[str, Any]:
    return {"players_in_pool": len(pool(session)), "groups": {group: len(keys) for group, keys in ATTRIBUTES.items()}}


#: The verdicts `RECOMMENDATION_RULE` can produce. Published so the gate below can say when a report
#: invents a sixth one, and so a page can style a known set rather than a string it hopes in.
VERDICTS: Final = ("sign now", "develop", "monitor", "pass")

#: The keys a report carries beside §24's thirteen, each of which exists to make the thirteen checkable.
COMPANION_FIELDS: Final = ("fields", "groups", "world", "limitations", "data_origin", "is_demo_data")


def report_problems(session: Session) -> list[str]:
    """Build one report over the stored pool and check it answers the structure it publishes.

    §23's integrity gate in another shape: the thirteen fields are a claim, and a claim a reader can
    re-run is worth more than a sentence saying this module is careful. Each check below recomputes
    something from the payload it is judging, so a renamed line or a mean that drifted from the
    attributes printed beside it becomes a sentence rather than a silent pass.
    """
    candidates = pool(session)
    if not candidates:  # pragma: no cover - the seeded world always has rows; an empty store is its own answer
        return ["the stored player pool is empty, so no report can be answered here"]
    report = build_report(session, str(candidates[0].player.slug))
    problems: list[str] = []
    known = {*REPORT_FIELDS, *COMPANION_FIELDS}
    for field in REPORT_FIELDS:
        if field not in report:
            problems.append(f"`{field}` is in §24's field list but absent from a built report")
    for extra in sorted(set(report) - known):
        problems.append(f"a built report carries `{extra}`, which is neither a §24 field nor a published companion")
    if report.get("fields") != list(REPORT_FIELDS):
        problems.append("the report's own `fields` line disagrees with REPORT_FIELDS")
    for group in ATTRIBUTES:
        line = report.get(group)
        if not isinstance(line, dict):
            problems.append(f"the `{group}` line is not an object, so its mean cannot be checked")
            continue
        own = line.get("attributes") or {}
        expected = round(sum(int(value) for value in own.values()) / len(own), 2) if own else 0.0
        if abs(float(line.get("mean", -1)) - expected) > 0.01:
            problems.append(f"the `{group}` mean is {line.get('mean')} while the attributes it prints average {expected}")
        if int(line.get("measured", -1)) != len(own):
            problems.append(f"the `{group}` line says it measured {line.get('measured')} of the {len(own)} attributes it prints")
    verdict = str((report.get("recommendation") or {}).get("verdict", ""))
    if verdict not in VERDICTS:
        problems.append(f"the recommendation produced {verdict!r}, which RECOMMENDATION_RULE does not list")
    if not (report.get("recommendation") or {}).get("decided_by"):
        problems.append("the recommendation arrived without the two figures that decided it")
    return problems


def limitations() -> list[str]:
    """What this report cannot say, printed with the report rather than kept beside it in a test."""
    return [
        "the four group scores are means over stored attribute keys, so a player whose row carries an unusual mix reads as a flat profile here: `attributes` inside each group line shows the keys that made the mean",
        "potential is the generated row's ceiling, not a forecast: `wide_headroom` names a large gap without promising it, and nothing in this report ranks a player's unmeasured capacity",
        "cost is this project's valuation of the row, which is not an offer the club holding the player would answer",
        "team fit, the crowded-band risk factor and a squad comparison need a career: without one `team_fit` is null and the risk list simply has one factor fewer, rather than a guess about a squad",
        "recommendation is a published ladder over this report's own figures, not an opinion: the two deciding numbers travel in `decided_by`",
        'no model call is involved anywhere in this module: every line is arithmetic over a stored row, which is how §24\'s 不要输出没有依据的"天赋" is enforced rather than promised',
    ]


__all__ = [
    "COMPARISON_RULE",
    "COMPANION_FIELDS",
    "GROUP_RULE",
    "GroupScore",
    "LEVEL_RULE",
    "POTENTIAL_RULE",
    "RECOMMENDATION_RULE",
    "REPORT_FIELDS",
    "VERDICTS",
    "ReportRefusal",
    "build_report",
    "find_comparator",
    "group_score",
    "limitations",
    "report_counts",
    "report_problems",
    "report_ready",
]
