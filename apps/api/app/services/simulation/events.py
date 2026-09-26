"""The stored timeline (ROADMAP item 4): the engine's event list as rows, and the check that the rows
still say what the match report says.

One correction to the roadmap line this closes. The timeline was never regenerated on a view:
`simulate_match` builds the event list once, `run_simulation` stores the whole report — events included —
in `sim_matches.report`, and `GET /api/v1/simulations/{slug}` reads that JSON back without asking the
engine anything. The only path that re-derives events is `/replay`, and it does so deliberately, to prove
the engine still agrees with itself.

So these rows earn their keep by being *addressable*, not by being new. A report is one blob per match;
"who scored most in this career" or "how many sendings-off in this competition" meant loading every
report in the world and picking JSON out of it in Python. One row per event answers those in a query, and
gives the next module — a scoring chart, a disciplinary balance, an AI scout (§23) that reasons over a
season rather than a match — something to read.

Two rules this module will not bend:

* **The rows are a copy, not a second opinion.** They are written in the same transaction as the report
  they came from, they never feed the engine, and nothing here recomputes an event. A timeline that
  disagrees with its report is reported as a disagreement, in the report's favour, rather than silently
  averaged.
* **A name is not an identity.** The engine names a scorer out of the side's eleven and the printed
  `lineup` is inside every stored match's digest, so it cannot carry ids without making every stored
  report disagree with its own hash. Identity is recovered by looking the name back up in that same
  eleven, and where two selected players share one name the row says `ambiguous` and claims no player —
  picking between them would write one man's record under another's name.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import SimulationEvent, SimulationMatch
from app.services.simulation.engine import SIMULATION_DISCLAIMER
from app.services.simulation.profile import SideProfile

# What a row is, in the reader's terms: the report's own list, one entry per row, in the report's order.
TIMELINE_FORMULA = "one row per entry in report.events, keyed by (match_id, ordinal) where ordinal is its index in that list"
# The report prints names only, so this is the sentence that says how far a name can be trusted.
ATTRIBUTION_FORMULA = "player_id = the one selected player whose name the event printed, when exactly one of that side's eleven has it"

# Which keys a report event carries beyond the six every event has. The engine writes these three by
# event type and never otherwise, so a rebuild that follows the same rule reproduces the report's dicts
# exactly — which is what makes the field-by-field check below a check rather than a guess.
_CHANCE_TYPES = frozenset({"goal", "shot_saved", "shot_off_target"})
_SCORE_TYPES = frozenset({"goal"})


def _as_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _as_mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def identities(profile: SideProfile) -> dict[str, list[tuple[str, str]]]:
    """Every name this side's eleven printed, with each player row that answers to it.

    `lineup` and `selected` are built from the same ordered list in `team_profile`, so a name here is
    backed by the same slot the engine drew from; the list is what makes a duplicate surname visible
    instead of quietly taking the first match.
    """
    found: dict[str, list[tuple[str, str]]] = {}
    for player_id, slug, name, _position, _band in profile.selected:
        found.setdefault(name, []).append((player_id, slug))
    return found


def _attribution(name: str, by_name: Mapping[str, list[tuple[str, str]]], team_id: str | None) -> tuple[str, str | None, str, str | None]:
    """(attribution, player_id, player_slug, team_id) for one printed name."""
    if not team_id:
        # No side row to look in: the engine printed a team's short name because it had no eleven.
        return ("unnamed", None, "", team_id)
    matches = by_name.get(name, [])
    if len(matches) == 1:
        player_id, slug = matches[0]
        return ("identified", player_id, slug, team_id)
    if len(matches) > 1:
        return ("ambiguous", None, "", team_id)
    return ("unnamed", None, "", team_id)


def build_rows(match: SimulationMatch, report: Mapping[str, Any], sides: Mapping[str, SideProfile]) -> list[SimulationEvent]:
    """The event rows this report implies, without touching a session.

    Split from the writer so the mapping from report to rows is testable on its own, and so a caller that
    has already deleted the match can still see what its timeline should have been.
    """
    events = _as_list(report.get("events"))
    stored = _as_mapping(report.get("sides"))
    rows: list[SimulationEvent] = []
    for ordinal, raw in enumerate(events):
        event = _as_mapping(raw)
        side_key = str(event.get("side", ""))
        profile = sides.get(side_key)
        team_id = profile.team_id if profile is not None else str(_as_mapping(stored.get(side_key)).get("team_id", "")) or None
        name = str(event.get("player", ""))
        by_name = identities(profile) if profile is not None else {}
        attribution, player_id, player_slug, resolved_team = _attribution(name, by_name, team_id)
        xg = event.get("expected_goals")
        rows.append(
            SimulationEvent(
                id=new_public_id("sev"),
                match_id=match.id,
                match_slug=match.slug,
                ordinal=ordinal,
                minute=int(event.get("minute", 0)),
                event_type=str(event.get("type", "")),
                side=side_key,
                team=str(event.get("team", "")),
                team_id=resolved_team,
                player_name=name,
                player_id=player_id,
                player_slug=player_slug,
                position=str(event.get("position", "")),
                chance=str(event.get("chance", "")),
                expected_goals=float(xg) if isinstance(xg, int | float) else None,
                score=str(event.get("score", "")),
                detail=str(event.get("detail", "")),
                attribution=attribution,
                data_origin="simulation",
                is_demo_data=True,
            )
        )
    return rows


def write_timeline(session: Session, match: SimulationMatch, *, sides: Mapping[str, SideProfile]) -> list[SimulationEvent]:
    """Store this match's timeline. Idempotent: re-writing replaces the rows rather than doubling them.

    The caller adds the rows *before* its own commit, so a match and its timeline appear in the same
    transaction — a report on file with no rows means it predates this table, and nothing else.

    Both flushes are load-bearing, because the session does not autoflush: the first one puts rows an
    earlier call queued in this same transaction where a query can find them, and the second lands the
    deletes before new rows claim the ordinals. Without them, rewriting a timeline collides with the
    copy it is replacing — `(match_id, ordinal)` is unique, so a half-written rewrite is refused rather
    than silently doubled.
    """
    session.flush()
    for row in rows_of(session, match):
        session.delete(row)
    session.flush()
    rows = build_rows(match, _as_mapping(match.report), sides)
    session.add_all(rows)
    return rows


def rows_of(session: Session, match: SimulationMatch) -> list[SimulationEvent]:
    return list(session.scalars(select(SimulationEvent).where(SimulationEvent.match_id == match.id).order_by(SimulationEvent.ordinal)).all())


def event_dict(row: SimulationEvent) -> dict[str, Any]:
    """One row back in the shape the report printed, keys and all.

    A card event has no `chance` and no `expected_goals` in the report, so neither appears here: the
    rebuild is meant to be comparable to `report["events"][i]` with `==`, not merely close to it.
    """
    event: dict[str, Any] = {
        "minute": row.minute,
        "type": row.event_type,
        "side": row.side,
        "team": row.team,
        "player": row.player_name,
        "position": row.position,
        "detail": row.detail,
    }
    if row.event_type in _CHANCE_TYPES:
        event["chance"] = row.chance
        event["expected_goals"] = row.expected_goals
    if row.event_type in _SCORE_TYPES:
        event["score"] = row.score
    return event


def timeline_of(session: Session, match: SimulationMatch) -> list[dict[str, Any]]:
    return [event_dict(row) for row in rows_of(session, match)]


def _differences(stored: Mapping[str, Any], rebuilt: Mapping[str, Any]) -> list[str]:
    keys = [key for key in sorted({*stored, *rebuilt}) if stored.get(key) != rebuilt.get(key)]
    return [f"{key} ({stored.get(key, 'absent')!r} in the report, {rebuilt.get(key, 'absent')!r} on the row)" for key in keys]


def compare_with_report(session: Session, match: SimulationMatch) -> dict[str, Any]:
    """Re-read the rows and hold them against the report they were copied from, event by event.

    Counting rows would catch a deletion and nothing else: a report rewritten in place keeps its length,
    so the comparison is on the report's own ordering, key by key, and the first offenders are named.
    """
    events = _as_mapping(match.report).get("events")
    rows = rows_of(session, match)
    report_events = _as_list(events)
    if not rows:
        return {
            "checked": 0,
            "report_events": len(report_events),
            "agree": not report_events,
            "offenders": [],
            "verdict": (
                "no rows for this match: it was played before the events table existed, so its timeline is read off the report itself"
                if report_events
                else "no rows and no events, which is a match the engine reported with no events in it"
            ),
        }
    offenders: list[str] = []
    if len(rows) != len(report_events):
        offenders.append(f"the report lists {len(report_events)} events and {len(rows)} rows are stored")
    # `strict=False` is deliberate and is not hiding a truncation: a length difference is already an
    # offender by the time this loop runs, and the shared prefix is still worth comparing field by field.
    for row, raw in zip(rows, report_events, strict=False):
        stored = _as_mapping(raw)
        rebuilt = event_dict(row)
        found = _differences(stored, rebuilt)
        if found:
            offenders.append(f"minute {row.minute} ({row.event_type or 'no type'}): " + "; ".join(found))
    return {
        "checked": len(rows),
        "report_events": len(report_events),
        "agree": not offenders,
        "offenders": offenders[:3],
        "verdict": (
            f"{len(rows)} events re-read from the timeline table; all of them agree with the report"
            if not offenders
            else f"{len(offenders)} of {len(rows)} events disagree with the report they were copied from: {'; '.join(offenders[:3])} — the report is the engine's output and is treated as the record"
        ),
    }


def timeline_view(session: Session, match: SimulationMatch) -> dict[str, Any]:
    """What a reader gets: the timeline as rows where rows exist, and never a silence passed off as an
    empty match.

    `source` is the field a page has to print, because the two branches are different claims — rows means
    "the stored timeline, one query per event", the report means "this match predates the table, and the
    blob is all that survives of it".
    """
    rows = rows_of(session, match)
    report_events = _as_list(_as_mapping(match.report).get("events"))
    from_rows = bool(rows)
    events = timeline_of(session, match) if from_rows else [dict(_as_mapping(raw)) for raw in report_events]
    by_type: dict[str, int] = {}
    for event in events:
        by_type[str(event.get("type", "unknown"))] = by_type.get(str(event.get("type", "unknown")), 0) + 1
    ambiguous = sorted({row.player_name for row in rows if row.attribution == "ambiguous"})
    unnamed = sorted({row.player_name for row in rows if row.attribution == "unnamed" and row.player_name})
    return {
        "events": events,
        "count": len(events),
        "stored_rows": len(rows),
        "report_events": len(report_events),
        "source": "sim_events rows" if from_rows else "the match report's own JSON",
        "source_note": (
            "read from one row per event, which is what lets a season be queried instead of a match being unrolled"
            if from_rows
            else "this match was played before the events table existed; the report is its only surviving timeline"
        ),
        "consistency": compare_with_report(session, match)["verdict"],
        "by_type": by_type,
        "identified": sum(1 for row in rows if row.attribution == "identified"),
        "ambiguous_names": ambiguous,
        "unnamed_names": unnamed,
        "formula": TIMELINE_FORMULA,
        "attribution_formula": ATTRIBUTION_FORMULA,
        "disclaimer": SIMULATION_DISCLAIMER,
        "data_origin": "simulation",
        "is_demo_data": True,
    }


__all__ = [
    "ATTRIBUTION_FORMULA",
    "TIMELINE_FORMULA",
    "build_rows",
    "compare_with_report",
    "event_dict",
    "identities",
    "rows_of",
    "timeline_of",
    "timeline_view",
    "write_timeline",
]
