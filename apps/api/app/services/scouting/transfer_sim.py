"""M7's last verb — simulate a transfer, and write nothing.

§22's market moves a player: it writes a move row, charges the budget, and re-prices the wage bill. The scout's
question is the other way round and comes first: *if this career signed the player I have just been shown, what
would actually be different?* Answering it by calling `market.buy()` would answer a different question — the
manager's — and would leave rows behind for a hypothesis. So this module reads and computes and stores nothing:
no match row, no move row, no budget change, no listing, no offer.

What it composes is arithmetic the rest of the project already publishes, called directly rather than re-derived
here:

* **the price** — `market.valuation` for fee, clause, wage and contract length, set against
  `market.budget_position`'s standing figure and `market.wage_bill`'s committed rate. Fee and wage are checked
  separately, because a deal that fits the balance on day one and cannot pay its own wage after six rounds is the
  mistake a scout screen exists to catch before a manager makes it;
* **the side** — `profile.team_profile` twice: the squad this career holds at that round, and that squad with the
  signing added. The eleven, the four band indices and the press index come from the selector the engine actually
  plays, so a player who would sit on the bench is shown sitting there;
* **the fixtures** — `career.next_fixture_plan` at a round number, and `engine.simulate_match`, the engine's pure
  step, run at *the same seed* for both squads. The seed is not re-rolled to favour the signing, so the only thing
  that differs between the two lines of a round is the eleven.

One limit is printed in every answer rather than left to the reader: a fixture is one draw from a stochastic
model. The projections come round by round, with the pre-dice indices and possession share beside them, so the
part of the difference that is a better side can be told apart from the part that is the dice landing well.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Career, RealPlayer
from app.services.scouting.search import Candidate, pool
from app.services.simulation import market
from app.services.simulation.career import next_fixture_plan
from app.services.simulation.engine import MatchInputs, possession_share, simulate_match
from app.services.simulation.profile import SideProfile, SquadOverlay, team_profile
from app.services.simulation.service import BLOCK_MINUTES
from app.services.simulation.squad import squad_as_of

#: How many future fixtures a projection looks at, and the ceiling on that. The plan is a pure function of the
#: round number, so a projection may read ahead — but a few rounds, not a season, and every round it prints names
#: the opponent and the seed it used.
DEFAULT_ROUNDS: Final = 3
MAX_ROUNDS: Final = 6
MINUTES: Final = 90

#: Which answer each refusal deserves, in the same three shapes the rest of the scout tier uses.
REFUSALS: Final = ("no_such_player", "retired_career", "window_closed", "already_at_this_club", "no_opponent", "bad_rounds")
NOT_FOUND_CODES: Final = frozenset({"no_such_player", "already_at_this_club", "no_opponent"})
UNPROCESSABLE_CODES: Final = frozenset({"retired_career", "bad_rounds"})
CONFLICT_CODES: Final = frozenset({"window_closed"})

SIMULATION_RULE: Final = (
    "each future round is played twice at that round's own seed — once with the squad this career holds at that "
    "round, once with the signing added to it — so the only thing that differs between the two scorelines is the eleven"
)


class TransferRefusal(RuntimeError):
    """A refusal that carries the figures behind its sentence, as §22's and §23's do."""

    def __init__(self, code: str, message: str, **figures: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.figures = figures

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.figures}


def _candidate_for(session: Session, slug: str) -> Candidate:
    text = str(slug).strip()
    candidate = next((item for item in pool(session) if item.player.slug == text), None)
    if candidate is None:
        raise TransferRefusal("no_such_player", f"no stored player answers to {text!r}, so there is nothing here to simulate signing", ident=text)
    return candidate


def _indices(profile: SideProfile) -> dict[str, float]:
    return {
        "attack": round(profile.attack, 3),
        "midfield": round(profile.midfield, 3),
        "defence": round(profile.defence, 3),
        "keeper": round(profile.keeper, 3),
        "press": round(profile.press, 3),
        "form": round(profile.form, 3),
        "overall": round(profile.overall, 3),
    }


def _eleven(profile: SideProfile) -> list[dict[str, Any]]:
    return [{"player_id": player_id, "slug": slug, "name": name, "position": position, "band": band} for player_id, slug, name, position, band in profile.selected]


def _outcome(goals: int, against: int) -> str:
    return "W" if goals > against else "L" if goals < against else "D"


def _points(outcome: str) -> int:
    return {"W": 3, "D": 1, "L": 0}[outcome]


def _add_to_overlay(base: SquadOverlay | None, player: RealPlayer) -> SquadOverlay:
    """The overlay the career's own deals produce, with one more row added and nothing removed.

    `added` carries the player record itself, exactly as a signed deal does, so the attributes the engine reads are
    the ones on file now rather than a summary of them.
    """
    return SquadOverlay(added=(*(base.added if base else ()), player), removed=frozenset(base.removed) if base else frozenset(), label=f"{base.label if base else 'stored squad'} + hypothesis")


def _club_line(club: SideProfile, opponent: SideProfile, club_home: bool, seed: int) -> dict[str, Any]:
    """One fixture, one eleven, one seed: the scoreline the engine produces and the share it played for.

    The seed is carried on the line itself, not only on the round beside it, so a reader can see that both lines of
    a round were played at the same number — the claim `same_seed` makes would otherwise be the code's word alone.
    """
    home, away = (club, opponent) if club_home else (opponent, club)
    report = simulate_match(MatchInputs(home=home, away=away, seed=seed, minutes=MINUTES, block_minutes=BLOCK_MINUTES))
    share = possession_share(home, away, home.tactics, away.tactics)
    goals, against = int(report["score"]["home" if club_home else "away"]), int(report["score"]["away" if club_home else "home"])
    return {
        "seed": seed,
        "for": goals,
        "against": against,
        "outcome": _outcome(goals, against),
        "possession": round(share if club_home else 1.0 - share, 3),
        "digest": str(report["digest"]),
    }


def simulate_transfer(session: Session, career: Career, *, player: str, rounds: int = DEFAULT_ROUNDS) -> dict[str, Any]:
    """What would be different if this career signed this player — computed, and stored nowhere."""
    if str(career.status) != "active":
        raise TransferRefusal("retired_career", f"{career.slug} is {career.status}, so it signs nobody and has no future round to project", career=career.slug, status=str(career.status))
    window = int(career.challenge_window or 0)
    if window and int(career.rounds_played) >= window:
        raise TransferRefusal(
            "window_closed",
            f"this challenge's window closed at {window} rounds, so the next fixture will not be played and nothing can be projected past it",
            career=career.slug,
            played=int(career.rounds_played),
            window=window,
            challenge_slug=career.challenge_slug,
        )
    wanted = int(rounds)
    if wanted < 1 or wanted > MAX_ROUNDS:
        raise TransferRefusal("bad_rounds", f"a projection covers between 1 and {MAX_ROUNDS} future fixtures, and {wanted} was asked for", rounds=wanted, min=1, max=MAX_ROUNDS)

    candidate = _candidate_for(session, player)
    signing = candidate.player
    if signing.team_id == career.club_id:
        raise TransferRefusal(
            "already_at_this_club",
            f"{signing.name} is already on {career.club_name}'s stored books, so signing him changes nothing and this route would be reporting its own no-op",
            player=signing.slug,
            club=career.club_name,
        )

    base_round = int(career.rounds_played) + 1
    balance = market.budget_position(session, career)
    standing = market.wage_bill(session, career, round_index=base_round)
    valuation = candidate.valuation
    fee, clause, weekly = int(valuation["asking_fee"]), int(valuation["release_clause"]), int(valuation["weekly_wage"])
    remaining, committed = int(balance["remaining"]), int(standing["fee"])
    squad_rows = list(session.scalars(select(RealPlayer).where(RealPlayer.team_id == career.club_id)))
    need = market.club_need(session, career, round_index=base_round)

    cost = {
        "asking_fee": fee,
        "release_clause": clause,
        "weekly_wage": weekly,
        "season_wage": weekly * 52,
        "contract_years": int(valuation["contract_years"]),
        "units": balance["units"],
        "remaining_now": remaining,
        "affordable_by_fee": fee <= remaining,
        "headroom_after_fee": remaining - fee,
        "wage_committed_per_week": committed,
        "wage_after_this_player_per_week": committed + weekly,
        "season_wage_after": (committed + weekly) * 52,
        "rounds_the_wage_bills_for": (remaining - fee) // max(weekly, 1),
        "budget_formula": balance["formula"],
        "valuation_note": (
            "the fee, clause and wage are §22's valuation of this player's row as it stands; no seller has been asked, and a negotiation or a rival can move the number the market would really take"
        ),
        "note": (
            "the fee leaves the balance once; the wage leaves it every round this career plays. "
            "`rounds_the_wage_bills_for` counts whole rounds the money left after the fee would carry this player's wage — "
            "a fee that fits is not the same claim as a season that does"
        ),
    }

    base_overlay = squad_as_of(session, career, base_round)
    signed_overlay = _add_to_overlay(base_overlay, signing)
    before = team_profile(session, str(career.club_id), system_slug=career.system_slug or None, squad=base_overlay)
    after = team_profile(session, str(career.club_id), system_slug=career.system_slug or None, squad=signed_overlay)
    before_ids = {str(row["player_id"]) for row in _eleven(before)}
    after_ids = {str(row["player_id"]) for row in _eleven(after)}
    before_indices, after_indices = _indices(before), _indices(after)

    rounds_out: list[dict[str, Any]] = []
    totals = {"without": {"goals": 0, "against": 0, "points": 0}, "with_signing": {"goals": 0, "against": 0, "points": 0}}
    better = same = worse = 0
    blocked: dict[str, Any] | None = None
    for offset in range(wanted):
        round_index = base_round + offset
        plan = next_fixture_plan(session, career, round_index=round_index)
        if not plan.get("available"):
            blocked = {"round_index": round_index, "reason": str(plan.get("reason", "no competition to rotate through"))}
            break
        club_home = str(plan["side"]) == "home"
        opponent = team_profile(session, str(plan["opponent_team_id"]))
        without = _club_line(before, opponent, club_home, int(plan["seed"]))
        with_signing = _club_line(after, opponent, club_home, int(plan["seed"]))
        for key, line in (("without", without), ("with_signing", with_signing)):
            totals[key]["goals"] += int(line["for"])
            totals[key]["against"] += int(line["against"])
            totals[key]["points"] += _points(str(line["outcome"]))
        if _points(str(with_signing["outcome"])) > _points(str(without["outcome"])):
            better += 1
        elif _points(str(with_signing["outcome"])) < _points(str(without["outcome"])):
            worse += 1
        else:
            same += 1
        rounds_out.append(
            {
                "round_index": round_index,
                "side": str(plan["side"]),
                "opponent": plan["opponent_name"],
                "venue": plan["venue_name"],
                "seed": int(plan["seed"]),
                "same_seed": without["seed"] == with_signing["seed"] == int(plan["seed"]),
                "without": without,
                "with_signing": with_signing,
            }
        )
    if not rounds_out:
        raise TransferRefusal("no_opponent", str((blocked or {}).get("reason", "the career has no fixture left to project")), career=career.slug)

    return {
        "career": {
            "slug": career.slug,
            "club_name": career.club_name,
            "club_id": career.club_id,
            "rounds_played": int(career.rounds_played),
            "system_slug": career.system_slug,
            "formation": before.formation,
            "challenge_slug": career.challenge_slug,
            "window": window or None,
        },
        "player": {
            "slug": signing.slug,
            "name": signing.name,
            "path": f"/player/{signing.slug}",
            "age": int(signing.age),
            "position": signing.position,
            "positions": candidate.positions,
            "band": candidate.band,
            "preferred_foot": signing.preferred_foot,
            "overall": int(signing.overall),
            "potential": int(signing.potential),
            "headroom": candidate.headroom(),
            "archetype": signing.archetype,
            "from_club": ({"name": candidate.club_name, "slug": candidate.club_slug, "path": f"/team/{candidate.club_slug}"} if candidate.club_slug else None),
            "season": candidate.to_dict(wanted_attributes=[], answers=[], fit=None, role_fit=None)["season"],
            "observed": candidate.observed,
        },
        "need": {
            "needed_band": need["needed_band"],
            "this_player_fills_it": candidate.band == str(need["needed_band"]),
            "bands": need["bands"],
            "positions_in_band": need["positions_in_band"],
            "judged_on": need["judged_on"],
            "formation": need["formation"],
            "as_of_round": base_round,
            "rule": need.get("squad_applied", ""),
        },
        "fit": dict(market.tactical_fit(signing, str(need["needed_band"])), formula=market.FIT_FORMULA),
        "cost": cost,
        "squad": {
            "size_before": len(squad_rows),
            "size_after": len(squad_rows) + 1,
            "fielding_before": market.can_field_side(squad_rows),
            "fielding_after": market.can_field_side([*squad_rows, signing]),
            "rule": "a signing adds a row to the squad and the eleven is then selected from the bigger pool, so the bench gets deeper and the starting side may or may not change at all",
        },
        "side": {
            "before": {"indices": before_indices, "eleven": _eleven(before)},
            "after": {"indices": after_indices, "eleven": _eleven(after)},
            "indices_delta": {key: round(after_indices[key] - before_indices[key], 3) for key in before_indices},
            "comes_in": [row for row in _eleven(after) if str(row["player_id"]) not in before_ids],
            "goes_out": [row for row in _eleven(before) if str(row["player_id"]) not in after_ids],
            "eleven_unchanged": before_ids == after_ids,
            "rule": "both elevens come from `team_profile` over the rows this career holds at the round it would play them — the selector the engine uses, not a guess about the manager's preference",
        },
        "projection": {
            "rounds_asked": wanted,
            "rounds_projected": len(rounds_out),
            "rounds": rounds_out,
            "totals": totals,
            "points_delta": totals["with_signing"]["points"] - totals["without"]["points"],
            "goals_for_delta": totals["with_signing"]["goals"] - totals["without"]["goals"],
            "goals_against_delta": totals["with_signing"]["against"] - totals["without"]["against"],
            "better": better,
            "same": same,
            "worse": worse,
            "stopped_at": blocked,
            "rule": SIMULATION_RULE,
            "one_sample": (
                "a fixture is one draw from a stochastic model: the same eleven at another seed wins a different match. "
                "The indices and the possession share are the pre-dice part of this answer — they move only because the eleven moved — "
                "and the scorelines move because of both"
            ),
        },
        "what_this_does_not_do": not_does(),
        "rules": rules(),
        "limitations": limitations(),
        "data_origin": "synthetic",
        "is_demo_data": True,
        "disclaimer": market.MARKET_DISCLAIMER,
        "demo_data": True,
    }


def rules() -> dict[str, Any]:
    return {
        "default_rounds": DEFAULT_ROUNDS,
        "max_rounds": MAX_ROUNDS,
        "writes": "nothing: no sim match row, no move row, no wage charge, no budget change, no listing, no offer",
        "price_from": "market.valuation of the player's row, set against market.budget_position and market.wage_bill for the career",
        "side_from": "profile.team_profile run twice — the squad the career holds at the round, and that squad with the signing added",
        "fixtures_from": "career.next_fixture_plan at a round number, so the projection follows the generated calendar the career's season drew (or, once that calendar is exhausted, the career's own published rotation)",
        "seed_rule": SIMULATION_RULE,
        "refusals": list(REFUSALS),
    }


def limitations() -> list[str]:
    return [
        "nothing here is stored: this is arithmetic over rows that already exist, and no money, listing, contract or squad row is created by asking",
        "a fixture is one sample of a stochastic model, so one better scoreline is not evidence the signing is an improvement — the per-round lines and the indices are printed beside it for that reason",
        "the projection assumes this career's current system and no other comings or goings; a real window moves several players, and each one changes the eleven",
        "the price is §22's valuation of the row as it stands, not a negotiated figure: no seller has been asked, and a clause or a rival can move what the market would really take",
        "the wage arithmetic adds this player's weekly figure to the standing committed rate and charges it every round; it forecasts no renewal, no sale, and no window it was not told about",
        "every club, player and figure in this answer belongs to a generated fictional world, and a projection about them is arithmetic about that fiction",
    ]


def not_does() -> list[str]:
    return [
        "does not write a row — no SimulationMatch, no CareerSquadMove, no wage charge, no transfer listing",
        "does not move money: the career's stored budget is read, not decremented",
        "does not make an offer or open negotiations; `POST /transfers/{career}/buy` is the door that does, and it is not called here",
        "does not reprice the seller, the rivals, or this player's contract",
        "does not predict: it replays the same seed against two elevens and reports the difference it had to compute to do so",
    ]


def transfer_sim_ready(session: Session) -> bool:
    """Ready when there is a player to sign and a career to sign him to — both read from stored rows."""
    return bool(pool(session)) and int(session.scalar(select(func.count()).select_from(Career)) or 0) > 0


def transfer_sim_counts(session: Session) -> dict[str, Any]:
    return {
        "players_in_pool": len(pool(session)),
        "careers_stored": int(session.scalar(select(func.count()).select_from(Career)) or 0),
        "default_rounds": DEFAULT_ROUNDS,
        "max_rounds": MAX_ROUNDS,
        "rows_written_by_a_simulation": 0,
        "rule": "that last figure is the claim this tier is built on: a simulation writes nothing, whatever else it reads",
    }
