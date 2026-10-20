"""Training programs: the runnable object §36 names and the creator tier did not have.

§36 lists six kinds of content a user can create, and the first is a *Training Program*. The tier
publishes guides, and its own verification record said what a guide is not: "Nothing here is a
runnable program: no row carries a schedule, a dose or a progression."

A program is those three things and nothing more:

* a **schedule** - the steps, in order, one row each;
* a **dose** - the minutes each step asks for;
* a **progression** - the order, which is the position column and nothing else.

Every step names a drill from the training catalogue, so a program is runnable by construction: the
drill is the one the learner opens and the minutes are the ones the learner is asked for. A step
naming a drill the catalogue does not hold is refused **at publication**, not at the learner's first
session - a plan that cannot be walked is not a plan.

The figures are counted now, like every other figure in this tier, and the formulas are published
beside them: `steps` is a count of the step rows, `minutes` is their sum, and `sessions` is the count
of the planned sessions this program has produced for the account that started it.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import (
    CreatorProgram,
    CreatorProgramStep,
    TrainingDrill,
    TrainingSession,
    User,
    UserPlayer,
    utc_today,
)
from app.services.creator.publishing import (
    VISIBILITIES,
    CreatorRefusal,
    _slug_of,
    _text,
    ensure_profile,
)

#: How many programs one creator may publish.
MAX_PROGRAMS_PER_CREATOR: Final = 20
PROGRAM_TITLE_MAX: Final = 160
PROGRAM_SLUG_MAX: Final = 80
PROGRAM_SUMMARY_MAX: Final = 600
#: A program is a sequence a learner can do in a fortnight, not a curriculum.
PROGRAM_STEPS_MAX: Final = 12
PROGRAM_STEPS_MIN: Final = 1
STEP_MINUTES_MIN: Final = 5
STEP_MINUTES_MAX: Final = 180
STEP_NOTE_MAX: Final = 300

#: The tier's own vocabulary for a program, published by the rules door beside the guide's.
FORMULAS: Final = {
    "steps": "count of the step rows this program holds - one per position, so it is a number of sessions, not of presses",
    "minutes": "sum of the minutes over the step rows - the dose the program asks for in total",
    "programs": "count of every program row this database holds",
    "program_total": "count of program rows whose author is this account",
    "sessions": "count of the planned training sessions this program has produced for the account that started it",
}

#: The codes are the creator tier's own, declared there: one tier owns its codes, and a second
#: module claiming the same ones would be two owners of one answer. `no_player` is the one this
#: module raises and does not publish - it is the platform's code for an account with no player row,
#: and the tier that owns it publishes it.

LIMITATION: Final = (
    "a program stores a title, its own summary, a visibility and an ordered list of steps - each one a catalogue "
    "drill, the minutes it asks for and the author's own words. It stores no session, no completion and no "
    "progress: those are the learner's rows in the training tier, counted from there. A program is a plan a "
    "learner can walk, and the walk is the training tier's own sessions"
)


def _visibility(visibility: Any) -> str:
    word = str(visibility or "").strip().lower()
    if word not in VISIBILITIES:
        raise CreatorRefusal(
            "program_visibility",
            f"a program is {' or '.join(repr(item) for item in VISIBILITIES)}; {word!r} would select nobody and the door cannot tell that from a mistake",
            sent=word,
            visibilities=list(VISIBILITIES),
        )
    return word


def _drill(session: Session, slug: Any) -> TrainingDrill:
    """The catalogue drill a step names. A step that names no drill cannot be walked."""
    key = str(slug or "").strip().lower()
    if not key:
        raise CreatorRefusal("no_such_drill", "a step names the drill it asks for, and this one names none", drill=key)
    row = session.scalar(select(TrainingDrill).where(TrainingDrill.slug == key))
    if row is None:
        raise CreatorRefusal(
            "no_such_drill",
            f"the training catalogue holds no drill called {key!r}, so a step naming it could not be walked",
            drill=key,
        )
    return row


def _steps(session: Session, steps: Any) -> list[dict[str, Any]]:
    """The program's steps, in the order they were sent."""
    raw = list(steps or [])
    if len(raw) < PROGRAM_STEPS_MIN:
        raise CreatorRefusal(
            "program_steps",
            f"a program is at least {PROGRAM_STEPS_MIN} step and at most {PROGRAM_STEPS_MAX}",
            steps=len(raw),
            min=PROGRAM_STEPS_MIN,
            max=PROGRAM_STEPS_MAX,
        )
    if len(raw) > PROGRAM_STEPS_MAX:
        raise CreatorRefusal(
            "program_steps",
            f"a program is at most {PROGRAM_STEPS_MAX} steps and this one has {len(raw)}",
            steps=len(raw),
            min=PROGRAM_STEPS_MIN,
            max=PROGRAM_STEPS_MAX,
        )
    resolved: list[dict[str, Any]] = []
    for index, step in enumerate(raw):
        if not isinstance(step, dict):
            raise CreatorRefusal("program_steps", f"step {index} is not a step", step=index)
        drill = _drill(session, step.get("drill"))
        minutes = step.get("minutes")
        if minutes is None:
            raise CreatorRefusal(
                "step_minutes",
                f"step {index} asks for no minutes at all",
                step=index,
                min=STEP_MINUTES_MIN,
                max=STEP_MINUTES_MAX,
            )
        try:
            dose = int(minutes)
        except (TypeError, ValueError):
            raise CreatorRefusal(
                "step_minutes",
                f"step {index} asks for {minutes!r} minutes, which is not a number of minutes",
                step=index,
                min=STEP_MINUTES_MIN,
                max=STEP_MINUTES_MAX,
            ) from None
        if dose < STEP_MINUTES_MIN or dose > STEP_MINUTES_MAX:
            raise CreatorRefusal(
                "step_minutes",
                f"step {index} asks for {dose} minutes; a step asks for between {STEP_MINUTES_MIN} and {STEP_MINUTES_MAX}",
                step=index,
                minutes=dose,
                min=STEP_MINUTES_MIN,
                max=STEP_MINUTES_MAX,
            )
        resolved.append(
            {
                "position": index + 1,
                "drill": drill.slug,
                "drill_title": drill.title,
                "minutes": dose,
                "note": _text(step.get("note"), STEP_NOTE_MAX, "step_note", "step note", required=False),
            }
        )
    return resolved


def program_counts(session: Session, *, ready: bool) -> dict[str, int]:
    """The rulebook's counts of this tier's program tables."""
    if not ready:
        return {"programs": 0, "steps": 0}
    return {
        "programs": int(session.scalar(select(func.count()).select_from(CreatorProgram)) or 0),
        "steps": int(session.scalar(select(func.count()).select_from(CreatorProgramStep)) or 0),
    }


def publish_program(
    session: Session,
    actor_id: str,
    *,
    title: Any,
    summary: Any = "",
    visibility: Any = "public",
    steps: Any = None,
) -> dict[str, Any]:
    """Publish a program: a title, a visibility and an ordered list of steps."""
    ensure_profile(session, actor_id)
    wanted_title = _text(title, PROGRAM_TITLE_MAX, "program_title", "program title", required=True)
    wanted_visibility = _visibility(visibility)
    resolved = _steps(session, steps)

    mine = int(
        session.scalar(select(func.count()).select_from(CreatorProgram).where(CreatorProgram.author_id == actor_id)) or 0
    )
    if mine >= MAX_PROGRAMS_PER_CREATOR:
        raise CreatorRefusal(
            "program_limit",
            f"a creator may publish {MAX_PROGRAMS_PER_CREATOR} programs and this account has {mine}",
            programs=mine,
            max=MAX_PROGRAMS_PER_CREATOR,
        )

    slug = _slug_of(wanted_title)
    taken = session.scalar(
        select(CreatorProgram).where(CreatorProgram.author_id == actor_id, CreatorProgram.slug == slug)
    )
    if taken is not None:
        raise CreatorRefusal(
            "slug_taken",
            f"this account already publishes a program called {slug!r}, and a reader cannot tell two programs apart by a name",
            slug=slug,
        )

    row = CreatorProgram(
        id=new_public_id("cmp"),
        author_id=actor_id,
        slug=slug,
        title=wanted_title,
        summary=_text(summary, PROGRAM_SUMMARY_MAX, "program_summary", "program summary", required=False),
        visibility=wanted_visibility,
    )
    session.add(row)
    for step in resolved:
        session.add(
            CreatorProgramStep(
                id=new_public_id("cps"),
                program_id=row.id,
                position=step["position"],
                drill_slug=step["drill"],
                minutes=step["minutes"],
                note=step["note"],
            )
        )
    session.commit()
    return read_program(session, row.id)


def _program(session: Session, ident: str) -> CreatorProgram:
    row = session.get(CreatorProgram, str(ident))
    if row is None:
        raise CreatorRefusal("no_such_program", f"no program answers to {str(ident)!r}", program=str(ident))
    return row


def _steps_of(session: Session, program_id: str) -> list[CreatorProgramStep]:
    return list(
        session.scalars(
            select(CreatorProgramStep).where(CreatorProgramStep.program_id == program_id).order_by(CreatorProgramStep.position)
        ).all()
    )


def read_program(session: Session, ident: str) -> dict[str, Any]:
    """One program with its steps and the figures counted now."""
    row = _program(session, ident)
    steps = _steps_of(session, row.id)
    minutes = sum(step.minutes for step in steps)
    sessions = int(
        session.scalar(
            select(func.count())
            .select_from(TrainingSession)
            .where(TrainingSession.program_id == row.id)
        )
        or 0
    )
    author = session.get(User, row.author_id)
    return {
        "id": row.id,
        "slug": row.slug,
        "title": row.title,
        "summary": row.summary,
        "visibility": row.visibility,
        "published_on": row.published_on,
        "data_origin": row.data_origin,
        "is_demo_data": row.is_demo_data,
        "author": {"id": row.author_id, "display_name": author.display_name if author else ""},
        "steps": [
            {
                "position": step.position,
                "drill": step.drill_slug,
                "minutes": step.minutes,
                "note": step.note,
            }
            for step in steps
        ],
        "figures": {
            "steps": len(steps),
            "minutes": minutes,
            "sessions": sessions,
        },
        "formulas": dict(FORMULAS),
        "rule": LIMITATION,
    }


def list_programs(session: Session, *, creator: str | None = None, page_size: int = 20) -> dict[str, Any]:
    """The public shelf of programs."""
    stmt = select(CreatorProgram).where(CreatorProgram.visibility == "public")
    if creator:
        stmt = stmt.where(CreatorProgram.author_id == creator)
    rows = list(session.scalars(stmt.order_by(CreatorProgram.published_on.desc()).limit(max(1, page_size))).all())
    return {
        "programs": [
            {
                "id": row.id,
                "slug": row.slug,
                "title": row.title,
                "summary": row.summary,
                "author": row.author_id,
                "published_on": row.published_on,
                "steps": len(_steps_of(session, row.id)),
            }
            for row in rows
        ],
        "total": int(session.scalar(select(func.count()).select_from(CreatorProgram)) or 0),
        "formulas": dict(FORMULAS),
    }


def erase_program(session: Session, actor_id: str, ident: str) -> dict[str, Any]:
    """Erase your own program and the sessions it planned."""
    row = _program(session, ident)
    if row.author_id != actor_id:
        raise CreatorRefusal("no_such_program", f"no program answers to {str(ident)!r}", program=str(ident))
    planned = list(
        session.scalars(select(TrainingSession).where(TrainingSession.program_id == row.id)).all()
    )
    for session_row in planned:
        session.delete(session_row)
    #: The program goes first and the database's cascade takes its steps with it: deleting the
    #: steps by hand as well would issue a second delete for a row the cascade already took.
    session.delete(row)
    session.commit()
    return {"status": "erased", "program": row.id, "sessions_erased": len(planned)}


def start_program(session: Session, actor_id: str, ident: str, *, player_id: str | None = None) -> dict[str, Any]:
    """Plan a program's steps as the caller's training sessions - the runnable half.

    The sessions are the training tier's own rows, so completing one of them is the same act as
    completing any other session, and the progression is the program's order.
    """
    row = _program(session, ident)
    if row.visibility != "public" and row.author_id != actor_id:
        raise CreatorRefusal("no_such_program", f"no program answers to {str(ident)!r}", program=str(ident))

    player: UserPlayer | None = None
    if player_id:
        player = session.get(UserPlayer, player_id)
        if player is None or player.user_id != actor_id:
            raise CreatorRefusal("no_player", f"no player of this account answers to {player_id!r}", player=player_id)
    else:
        player = session.scalar(
            select(UserPlayer).where(UserPlayer.user_id == actor_id).order_by(UserPlayer.created_at)
        )
    if player is None:
        raise CreatorRefusal(
            "no_player",
            "a program needs a player to plan for, and this account has none",
        )

    steps = _steps_of(session, row.id)
    planned: list[str] = []
    for step in steps:
        drill = session.scalar(select(TrainingDrill).where(TrainingDrill.slug == step.drill_slug))
        if drill is None:
            raise CreatorRefusal(
                "no_such_drill",
                f"the training catalogue holds no drill called {step.drill_slug!r} any more, so this program cannot be walked",
                drill=step.drill_slug,
            )
        planned_row = TrainingSession(
            id=new_public_id("ses"),
            user_id=actor_id,
            player_id=player.id,
            drill_id=drill.id,
            #: The schedule: the first step is today and each later step is the next day, so a
            #: program is a plan a learner can walk rather than a list of drills.
            planned_date=(utc_today() + timedelta(days=step.position - 1)).isoformat(),
            recommendation_reasons=[
                f"Step {step.position} of the program “{row.title}”",
                f"Targets {', '.join(drill.target_attributes)}",
                f"{step.minutes} min",
            ],
            program_id=row.id,
        )
        session.add(planned_row)
        planned.append(planned_row.id)
    session.commit()
    return {
        "program": row.id,
        "player": player.id,
        "sessions": planned,
        "minutes": sum(step.minutes for step in steps),
        "status": "planned",
    }


def rules(session: Session, *, ready: bool) -> dict[str, Any]:
    """The program's own vocabulary, published beside the guide's."""
    return {
        "program_caps": {
            "program_max": MAX_PROGRAMS_PER_CREATOR,
            "program_title_max": PROGRAM_TITLE_MAX,
            "program_slug_max": PROGRAM_SLUG_MAX,
            "program_summary_max": PROGRAM_SUMMARY_MAX,
            "program_steps_max": PROGRAM_STEPS_MAX,
            "step_minutes_min": STEP_MINUTES_MIN,
            "step_minutes_max": STEP_MINUTES_MAX,
            "step_note_max": STEP_NOTE_MAX,
        },
        "program_formulas": dict(FORMULAS),
        "program_counts": program_counts(session, ready=ready),
        "program_rule": LIMITATION,
    }
