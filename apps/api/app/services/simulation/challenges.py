"""Manager live challenges (M6, spec §21): authored scenarios a season can be played *under*.

§21 asks for three things of a challenge — **time limited**, **goal based**, **reward based** — and
this module is written so that each of the three is a fact a reader can check rather than a heading:

* **Time limited.** Every scenario names a `window_rounds`. The window is stored on the career the
  scenario opens, and `career.play_round` refuses to play past it, so the limit is enforced by the one
  play path rather than by a rule the page is trusted to apply.
* **Goal based.** The scenario fixes its objectives and the start endpoint accepts none, so the target
  cannot be moved after the fact. Every verdict prints the objective's own formula beside the number,
  taken from `OBJECTIVE_FORMULA` — the same table Career Mode judges open careers with.
* **Reward based.** The reward is stated in the catalogue and *earned* by the verdict: a run that
  meets every objective inside its window earns it, and one that does not, does not. The reward is
  computed from the run's own rows and nothing consumes it yet, which the response says in words
  rather than letting a credit total imply a wallet.

Two further rules keep it consistent with the rest of M6:

1. **A run is a career, not a second container.** Starting a challenge opens a normal `careers` row
   carrying `challenge_slug` and `challenge_window`; its rounds are `career_fixtures`; each round is
   decided by `run_simulation`. There is still exactly one match model and one fixture store.
2. **Constraints say whether they bind.** §21's own examples (no transfers, academy players, a
   low budget) mostly describe rules the engine has no mechanism to apply yet. Each one is published
   with `enforced: true|false` and a sentence naming what it actually does — a scenario must not read
   as a constraint that was tested when nothing tested it.

The weakest club a scenario can hand you is chosen by **measurement**: `team_profile` builds every
club in the named competition the way the engine builds a side, and the lowest selected-eleven rating
is the club you take over. The measurement and its formula ship with the choice.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import func, inspect, or_, select
from sqlalchemy.orm import Session

from app.models import OBJECTIVE_FORMULA, OBJECTIVE_KINDS, Career, CareerFixture, Competition, Team
from app.services.simulation.career import (
    CAREER_DISCLAIMER,
    career_view,
    create_career,
    fixtures_of,
    record_of,
    resolve_club,
)
from app.services.simulation.profile import team_profile

CHALLENGE_DISCLAIMER: Final = (
    "A live challenge is a fictional scenario played with the labelled simulation engine: the club, the "
    "fixtures and every result are generated, and nothing here reports a real club, a real competition or "
    "a real season."
)

DIFFICULTIES: Final[tuple[str, ...]] = ("medium", "hard", "extreme")
CLUB_SELECTORS: Final[tuple[str, ...]] = ("weakest", "any")
VERDICT_STATUSES: Final[tuple[str, ...]] = ("in_progress", "met", "missed")
REWARD_UNITS: Final = "career credits"


@dataclass(frozen=True)
class Constraint:
    """One rule a scenario states, and whether the build actually applies it."""

    key: str
    label: str
    enforced: bool
    how: str

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "label": self.label, "enforced": self.enforced, "how": self.how}


@dataclass(frozen=True)
class Challenge:
    """An authored scenario: a window, a goal, a reward, and the constraints it admits to."""

    slug: str
    name: str
    brief: str
    difficulty: str
    window_rounds: int
    club_selector: str
    philosophy: str
    budget: int
    system_slug: str
    objectives: tuple[dict[str, Any], ...]
    constraints: tuple[Constraint, ...]
    reward: dict[str, Any]

    @property
    def objectives_total(self) -> int:
        return len(self.objectives)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "brief": self.brief,
            "difficulty": self.difficulty,
            "window_rounds": self.window_rounds,
            "window": f"{self.window_rounds} rounds, enforced by career.play_round — the window is not advice",
            "club_selector": self.club_selector,
            "philosophy": self.philosophy,
            "budget": self.budget,
            "budget_units": REWARD_UNITS,
            "system_slug": self.system_slug,
            "objectives": [dict(objective) for objective in self.objectives],
            "constraints": [constraint.to_dict() for constraint in self.constraints],
            "reward": dict(self.reward),
        }


# --- the authored scenarios (spec §21's own list) -------------------------------------------------

_WINDOW: Final = Constraint(
    key="window",
    label="Time limited",
    enforced=True,
    how="career.play_round refuses to play past window_rounds and answers 409 window_closed, so the limit is applied by the only path that can play a round.",
)
_FIXED_GOAL: Final = Constraint(
    key="fixed_goal",
    label="Goal fixed by the scenario",
    enforced=True,
    how="the scenario names its objectives and the start endpoint accepts none, so the target cannot be lowered after the run opens.",
)
_NO_TRANSFERS: Final = Constraint(
    key="no_transfers",
    label="No transfers",
    enforced=True,
    how=(
        "market.transferable() refuses every deal for a career whose scenario carries this rule (409 "
        "transfers_forbidden), so the market that would break it is closed rather than merely discouraged. "
        "Published as enforced since §22 landed; before that it was stated intent with nothing to apply it."
    ),
)
_ACADEMY_ONLY: Final = Constraint(
    key="academy_only",
    label="Academy players only",
    enforced=False,
    how="the eleven is selected by the formation from the club's stored squad (app/services/simulation/profile.py), and that selection has no age filter — an under-23 rule is published, not applied.",
)


def _budget_constraint(amount: int) -> Constraint:
    return Constraint(
        key="budget",
        label=f"Budget fixed at {amount:,} {REWARD_UNITS}",
        enforced=True,
        how="the scenario sets the budget and the start endpoint accepts no budget field, so it cannot be raised; nothing spends it yet, so it constrains the record rather than the fixtures.",
    )


def _draft() -> tuple[Challenge, ...]:
    """The catalogue. Six scenarios, each one of §21's examples, authored for this project."""
    return (
        Challenge(
            slug="save-a-relegation-threatened-club",
            name="Save a relegation-threatened club",
            brief=(
                "Take the weakest club in a competition of your choosing and get 14 points out of eight rounds. "
                "The club is not described to you as weak — it is measured, and the measurement is printed."
            ),
            difficulty="hard",
            window_rounds=8,
            club_selector="weakest",
            philosophy="pressing",
            budget=250_000,
            system_slug="",
            objectives=({"kind": "points", "target": 14, "label": "14 points from eight rounds"},),
            constraints=(_WINDOW, _FIXED_GOAL, _budget_constraint(250_000), _NO_TRANSFERS),
            reward={"key": "survival-specialist", "label": "Survival specialist", "credits": 250_000, "xp": 400},
        ),
        Challenge(
            slug="build-a-u23-squad",
            name="Build a U23 squad",
            brief="Ten rounds to win five of them and take fifteen points, with an under-23 rule you are trusted to keep.",
            difficulty="medium",
            window_rounds=10,
            club_selector="any",
            philosophy="possession",
            budget=400_000,
            system_slug="",
            objectives=(
                {"kind": "wins", "target": 5, "label": "Five wins"},
                {"kind": "points", "target": 15, "label": "Fifteen points"},
            ),
            constraints=(_WINDOW, _FIXED_GOAL, _budget_constraint(400_000), _ACADEMY_ONLY),
            reward={"key": "academy-builder", "label": "Academy builder", "credits": 400_000, "xp": 500},
        ),
        Challenge(
            slug="win-with-academy-players",
            name="Win with academy players",
            brief="The shortest and hardest window in the catalogue: four wins from six rounds, from the weakest club available.",
            difficulty="extreme",
            window_rounds=6,
            club_selector="weakest",
            philosophy="pressing",
            budget=100_000,
            system_slug="",
            objectives=({"kind": "wins", "target": 4, "label": "Four wins from six"},),
            constraints=(_WINDOW, _FIXED_GOAL, _budget_constraint(100_000), _ACADEMY_ONLY),
            reward={"key": "homegrown", "label": "Homegrown", "credits": 200_000, "xp": 350},
        ),
        Challenge(
            slug="three-year-rebuild",
            name="Three-year rebuild",
            brief=(
                "Eighteen rounds — three six-round seasons — to reach thirty points and a goal difference that is not negative. The longest window, and the only one that asks for two things at once."
            ),
            difficulty="extreme",
            window_rounds=18,
            club_selector="weakest",
            philosophy="balanced",
            budget=600_000,
            system_slug="",
            objectives=(
                {"kind": "points", "target": 30, "label": "Thirty points"},
                {"kind": "goal_difference", "target": 0, "label": "Goal difference not negative"},
            ),
            constraints=(_WINDOW, _FIXED_GOAL, _budget_constraint(600_000)),
            reward={"key": "architect", "label": "Architect", "credits": 900_000, "xp": 800},
        ),
        Challenge(
            slug="no-transfer-challenge",
            name="No transfer challenge",
            brief="Twelve rounds, zero budget, and a squad you may not add to. Sixteen points and a four-match unbeaten run.",
            difficulty="hard",
            window_rounds=12,
            club_selector="any",
            philosophy="direct",
            budget=0,
            system_slug="",
            objectives=(
                {"kind": "points", "target": 16, "label": "Sixteen points"},
                {"kind": "unbeaten", "target": 4, "label": "Four matches unbeaten"},
            ),
            constraints=(_WINDOW, _FIXED_GOAL, _budget_constraint(0), _NO_TRANSFERS),
            reward={"key": "as-you-were", "label": "As you were", "credits": 300_000, "xp": 450},
        ),
        Challenge(
            slug="low-budget-challenge",
            name="Low-budget challenge",
            brief="Ten rounds on fifty thousand credits: twelve points and three wins from a club of your choosing.",
            difficulty="medium",
            window_rounds=10,
            club_selector="any",
            philosophy="counter",
            budget=50_000,
            system_slug="",
            objectives=(
                {"kind": "points", "target": 12, "label": "Twelve points"},
                {"kind": "wins", "target": 3, "label": "Three wins"},
            ),
            constraints=(_WINDOW, _FIXED_GOAL, _budget_constraint(50_000)),
            reward={"key": "frugal", "label": "Frugal", "credits": 150_000, "xp": 300},
        ),
    )


CHALLENGES: Final[tuple[Challenge, ...]] = _draft()


def challenge_by_slug(slug: str) -> Challenge | None:
    return next((challenge for challenge in CHALLENGES if challenge.slug == slug), None)


def challenge_problems(catalogue: tuple[Challenge, ...] | None = None) -> list[str]:
    """Integrity of the catalogue itself — the same guard `tactical_problems()` gives the 50 systems.

    A scenario that names an objective kind nobody can measure, or a window of zero rounds, would be a
    challenge no run could ever satisfy. Better to fail here than to open a run that cannot be won.
    """
    entries = CHALLENGES if catalogue is None else catalogue
    problems: list[str] = []
    seen: set[str] = set()
    for challenge in entries:
        if challenge.slug in seen:
            problems.append(f"{challenge.slug}: duplicate slug")
        seen.add(challenge.slug)
        if challenge.difficulty not in DIFFICULTIES:
            problems.append(f"{challenge.slug}: difficulty {challenge.difficulty!r} is not one of {list(DIFFICULTIES)}")
        if challenge.club_selector not in CLUB_SELECTORS:
            problems.append(f"{challenge.slug}: club_selector {challenge.club_selector!r} is not one of {list(CLUB_SELECTORS)}")
        if challenge.window_rounds < 1:
            problems.append(f"{challenge.slug}: a window of {challenge.window_rounds} rounds cannot be played")
        if not challenge.objectives:
            problems.append(f"{challenge.slug}: no objectives, so there is nothing to judge the run by")
        for objective in challenge.objectives:
            kind = str(objective.get("kind", ""))
            if kind not in OBJECTIVE_KINDS:
                problems.append(f"{challenge.slug}: objective kind {kind!r} is not one of {list(OBJECTIVE_KINDS)}")
        for constraint in challenge.constraints:
            if not constraint.how:
                problems.append(f"{challenge.slug}: constraint {constraint.key!r} does not say what it does")
        if not challenge.reward.get("key") or not challenge.reward.get("label"):
            problems.append(f"{challenge.slug}: reward has no key/label")
        if not challenge.system_slug and "system" in {constraint.key for constraint in challenge.constraints}:
            problems.append(f"{challenge.slug}: pins a system but names none")
    return problems


def fingerprint() -> str:
    """A stable digest of the catalogue, so a stored run can be traced to the scenarios that existed."""
    canonical = json.dumps([challenge.to_dict() for challenge in CHALLENGES], sort_keys=True, separators=(",", ":"))
    return hashlib.blake2b(canonical.encode(), digest_size=8).hexdigest()


def limitations() -> dict[str, str]:
    """What the challenge layer does not claim, in the words the page prints."""
    return {
        "window": ("A window closes on the number of rounds played, not on a calendar: there is no clock, no transfer deadline and no season end in this build."),
        "reward": ("A reward is earned by the verdict and recorded on the run. Nothing spends or grants it yet — there is no wallet, no shop and no entitlement behind these numbers."),
        "constraints": (
            "Each constraint publishes whether it is enforced. A constraint marked enforced=False is published, not applied, and the sentence beside it names the mechanism the build is missing."
        ),
        "club": (
            "The weakest club is the lowest selected-eleven rating as the engine measures it, from the club's own "
            "stored squad — not a league position, which this world does not keep for a career's own competition."
        ),
    }


# --- choosing the club a scenario hands you -------------------------------------------------------


def _competition(session: Session, ident: str) -> Competition | None:
    return session.scalar(select(Competition).where(or_(Competition.id == ident, Competition.slug == ident)))


def competition_options(session: Session) -> list[dict[str, Any]]:
    """The competitions a `weakest` scenario can be pointed at, each with how many clubs it holds.

    The count travels because it is the reader's check on the measurement: a scenario that takes the
    lowest-rated club of a five-club competition is a different promise from one that scans twenty.
    """
    rows = list(session.scalars(select(Competition).order_by(Competition.tier, Competition.slug)).all())
    counts: dict[str, int] = {str(team_id): int(total) for team_id, total in session.execute(select(Team.competition_id, func.count(Team.id)).group_by(Team.competition_id)).all() if team_id}
    return [
        {
            "id": row.id,
            "slug": row.slug,
            "name": row.name,
            "kind": row.kind,
            "tier": row.tier,
            "season": row.season,
            "clubs": int(counts.get(row.id, 0)),
            "path": f"/competition/{row.slug}",
        }
        for row in rows
    ]


def _measure_clubs(session: Session, teams: list[Team]) -> list[dict[str, Any]]:
    """Rate every club the way the engine rates a side, skipping any club it cannot build a side from."""
    measured: list[dict[str, Any]] = []
    for team in teams:
        try:
            profile = team_profile(session, team.id)
        except LookupError as error:
            measured.append({"team_id": team.id, "name": team.name, "short_name": team.short_name, "measurable": False, "why": str(error)})
            continue
        measured.append(
            {
                "team_id": team.id,
                "slug": team.slug,
                "name": team.name,
                "short_name": team.short_name,
                "measurable": True,
                "overall": round(profile.overall, 4),
                "attack": round(profile.attack, 4),
                "midfield": round(profile.midfield, 4),
                "defence": round(profile.defence, 4),
                "formation": profile.formation,
                "eleven": len(profile.lineup),
            }
        )
    return measured


def resolve_challenge_club(
    session: Session,
    challenge: Challenge,
    *,
    club: str | None = None,
    competition: str | None = None,
) -> tuple[Team, dict[str, Any]]:
    """The club a scenario gives you, and the sentence saying how it was chosen.

    `any` takes the club the caller names. `weakest` measures every club in the named competition with
    the engine's own squad reader and takes the lowest selected-eleven rating, publishing the whole
    ranking so a reader can see the gap rather than being told the club is weak.
    """
    if challenge.club_selector == "any":
        if not club:
            raise ValueError(f"{challenge.slug} lets you choose the club, so a club is required")
        resolved = resolve_club(session, club)
        return resolved, {
            "selector": "any",
            "chosen": {"team_id": resolved.id, "name": resolved.name, "short_name": resolved.short_name},
            "how": "you named the club, and it is one of the generated world's own clubs",
        }

    if not competition:
        raise ValueError(f"{challenge.slug} hands you the weakest club in a competition, so a competition is required")
    row = _competition(session, competition)
    if row is None:
        raise ValueError(f"no such competition in the generated world: {competition}")
    teams = list(session.scalars(select(Team).where(Team.competition_id == row.id).order_by(Team.slug)).all())
    if not teams:
        raise ValueError(f"{row.name} has no clubs to choose from")
    measured = _measure_clubs(session, teams)
    playable = [entry for entry in measured if entry.get("measurable")]
    if not playable:
        raise ValueError(f"no club in {row.name} has a squad the engine can build a side from")
    ranking = sorted(playable, key=lambda entry: (float(entry["overall"]), str(entry["slug"])))
    weakest = ranking[0]
    team = session.get(Team, str(weakest["team_id"]))
    if team is None:  # pragma: no cover - the row was read a moment ago in the same session
        raise ValueError(f"club {weakest['name']} disappeared between measuring and choosing it")
    runner_up = ranking[1] if len(ranking) > 1 else None
    return team, {
        "selector": "weakest",
        "competition": {"id": row.id, "slug": row.slug, "name": row.name},
        "chosen": {"team_id": team.id, "name": team.name, "short_name": team.short_name, "overall": weakest["overall"]},
        "ranking": [{"name": entry["name"], "overall": entry["overall"], "measurable": bool(entry.get("measurable"))} for entry in measured],
        "gap_to_runner_up": None if runner_up is None else round(float(runner_up["overall"]) - float(weakest["overall"]), 4),
        "how": (
            f"every club in {row.name} was read the way the engine builds a side (app/services/simulation/profile.py: "
            "mean overall of the eleven the formation selects, printed on the engine's 0–1 scale, from player attributes written /100) and the lowest was taken. "
            + (
                f"{runner_up['name']} measured {runner_up['overall']}, so the gap is {round(float(runner_up['overall']) - float(weakest['overall']), 4)}."
                if runner_up
                else "It is the only club in this competition the engine can build a side from."
            )
        ),
    }


# --- the verdict ----------------------------------------------------------------------------------


def verdict_for(challenge: Challenge, career: Career, rows: list[CareerFixture]) -> dict[str, Any]:
    """Judge a run from its own fixture rows. Nothing here is stored, so nothing here can go stale."""
    record = record_of(rows)
    actual_by_kind = {
        "wins": record["won"],
        "points": record["points"],
        "goal_difference": record["goal_difference"],
        "unbeaten": record["unbeaten_run"],
    }
    objectives: list[dict[str, Any]] = []
    for objective in challenge.objectives:
        kind = str(objective.get("kind", ""))
        target = int(objective.get("target", 0))
        actual = int(actual_by_kind.get(kind, 0))
        objectives.append(
            {
                "kind": kind,
                "label": str(objective.get("label") or kind),
                "target": target,
                "actual": actual,
                "met": actual >= target,
                "formula": OBJECTIVE_FORMULA.get(kind, "not a recognised objective kind"),
            }
        )

    window = int(career.challenge_window or challenge.window_rounds)
    played = len(rows)
    remaining = max(0, window - played)
    window_closed = played >= window
    objectives_met = sum(1 for item in objectives if item["met"])
    every_objective_met = objectives_met == len(objectives)
    status = "met" if window_closed and every_objective_met else "missed" if window_closed else "in_progress"
    earned = status == "met"
    reward = {
        "key": challenge.reward.get("key"),
        "label": challenge.reward.get("label"),
        "credits": challenge.reward.get("credits"),
        "credits_units": REWARD_UNITS,
        "xp": challenge.reward.get("xp"),
        "earned": earned,
        "reason": (
            f"the window closed after {played} of {window} rounds with all {len(objectives)} objectives met"
            if earned
            else f"{objectives_met} of {len(objectives)} objectives met after {played} of {window} rounds" + ("" if window_closed else ", and the window is still open")
        ),
    }
    return {
        "challenge_slug": challenge.slug,
        "challenge_name": challenge.name,
        "status": status,
        "window_rounds": window,
        "rounds_played": played,
        "rounds_remaining": remaining,
        "window_closed": window_closed,
        "objectives": objectives,
        "objectives_met": objectives_met,
        "objectives_total": len(objectives),
        "reward": reward,
        "judged_on": "the sums of this run's own career_fixtures rows, recomputed on every read",
        "closed_by": (f"the window closed at round {window}" if window_closed else f"{remaining} of {window} rounds remain"),
    }


def run_view(session: Session, career: Career, *, include_fixtures: bool = True) -> dict[str, Any]:
    """A run: the career it is played in, the scenario it is played under, and its live verdict."""
    challenge = challenge_by_slug(career.challenge_slug)
    view = career_view(session, career, include_fixtures=include_fixtures)
    if challenge is None:
        view["challenge"] = None
        view["verdict"] = None
        view["run"] = {
            "id": career.id,
            "slug": career.slug,
            "challenge_slug": career.challenge_slug,
            "challenge_window": career.challenge_window,
            "scenario_known": False,
            "note": f"this career names the scenario {career.challenge_slug!r}, which is not in the catalogue any more",
        }
        return view
    rows = fixtures_of(session, career)
    view["challenge"] = challenge.to_dict()
    view["verdict"] = verdict_for(challenge, career, rows)
    view["run"] = {
        "id": career.id,
        "slug": career.slug,
        "challenge_slug": challenge.slug,
        "challenge_window": int(career.challenge_window or challenge.window_rounds),
        "scenario_known": True,
        "fingerprint": fingerprint(),
    }
    view["limitations"] = {**view.get("limitations", {}), **limitations()}
    view["disclaimer"] = f"{CHALLENGE_DISCLAIMER} {CAREER_DISCLAIMER}"
    return view


def start_run(
    session: Session,
    challenge: Challenge,
    *,
    owner_id: str,
    club: Team,
    manager_name: str,
    system_slug: str,
    season: str,
) -> Career:
    """Open a career under a scenario: its window, its budget and its objectives, none of them the caller's."""
    career = create_career(
        session,
        owner_id=owner_id,
        club=club,
        manager_name=manager_name,
        philosophy=challenge.philosophy,
        system_slug=system_slug or challenge.system_slug,
        budget=challenge.budget,
        objectives=[dict(objective) for objective in challenge.objectives],
        season=season,
    )
    career.challenge_slug = challenge.slug
    career.challenge_window = challenge.window_rounds
    session.commit()
    session.refresh(career)
    return career


# --- readiness, reported from the data rather than from the code (spec §59) ------------------------


def challenge_columns_present(session: Session) -> bool:
    """Whether the run columns are on `careers`, i.e. whether migration 0010 has been applied."""
    bind = session.get_bind()
    if "careers" not in inspect(bind).get_table_names():
        return False
    columns = {column["name"] for column in inspect(bind).get_columns("careers")}
    return {"challenge_slug", "challenge_window"} <= columns


def challenge_counts(session: Session) -> dict[str, int]:
    if not challenge_columns_present(session):
        return {"runs": 0, "scenarios": len(CHALLENGES)}
    runs = int(session.scalar(select(func.count()).select_from(Career).where(Career.challenge_slug != "")) or 0)
    return {"runs": runs, "scenarios": len(CHALLENGES)}


def challenge_ready(session: Session) -> bool:
    """The feature can serve when the catalogue is sound, the run columns exist and the world is there.

    Deliberately not "someone has started a run": the gate is whether the surface can work, and the
    counts travel beside it so an empty-but-working catalogue reads as exactly that.
    """
    from app.services.world import world_ready

    return not challenge_problems() and challenge_columns_present(session) and world_ready(session)


__all__ = [
    "CHALLENGES",
    "CHALLENGE_DISCLAIMER",
    "CLUB_SELECTORS",
    "DIFFICULTIES",
    "REWARD_UNITS",
    "VERDICT_STATUSES",
    "Challenge",
    "Constraint",
    "challenge_by_slug",
    "challenge_columns_present",
    "challenge_counts",
    "challenge_problems",
    "challenge_ready",
    "competition_options",
    "fingerprint",
    "limitations",
    "resolve_challenge_club",
    "run_view",
    "start_run",
    "verdict_for",
]
