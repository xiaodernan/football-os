"""§38's CV, section by section (M10, spec §38).

Ten sections, in the spec's own order, each one a read of rows another tier owns. Nothing here writes, and nothing
here caches: `build_cv` is called and answers from the rows that exist at that moment, which is why the case that
adds a training session and re-reads the CV sees a different number.

The one judgement this file makes is about the two sections it cannot fill. It does not leave them out — a CV that
silently dropped `Matches` and `Stats` would look complete — and it does not print `0` for them. It prints the
reason, the tables that would have to hold the rows, and the foreign key that says why the tables that do exist are
about somebody else. That sentence is the honest form of "not in this build".
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Achievement,
    AttributeChange,
    CoachMessage,
    KnowledgeQuery,
    TrainingDrill,
    TrainingSession,
    User,
    UserAchievement,
    UserPlayer,
    VideoAsset,
    VideoDetection,
    XpEvent,
)

#: §38's ten sections, in the spec's order. A page renders them in this order, and the case file asserts the tuple
#: against the spec's own list rather than against itself.
SECTIONS: Final = (
    "position",
    "archetype",
    "skills",
    "matches",
    "stats",
    "training",
    "videos",
    "achievements",
    "ai_reports",
    "development",
)

#: §38's own words for its ten sections, so the case that guards them compares the payload against the spec
#: rather than against this file's idea of it.
SECTION_TITLES: Final = {
    "position": "Position",
    "archetype": "Archetype",
    "skills": "Skills",
    "matches": "Matches",
    "stats": "Stats",
    "training": "Training",
    "videos": "Videos",
    "achievements": "Achievements",
    "ai_reports": "AI Reports",
    "development": "Development History",
}

#: The two sections this build cannot fill, with the measurement that says so. Printed, never hidden.
UNFILLED_REASONS: Final = {
    "matches": (
        "nothing in this build records this player appearing in a match: `real_player_match_stats` is about generated "
        "world players, and `career_appearances.player_id` is a foreign key to `real_players` \u2014 the squad a career's "
        "manager selected, not this player. Of the 66 tables in the schema, four reference `user_players` at all "
        "(`training_sessions`, `training_plans`, `xp_events`, `attribute_changes`) and none of them is a match"
    ),
    "stats": (
        "every counted output of a match \u2014 appearances, minutes, goals, assists \u2014 needs the same rows `Matches` "
        "describes, so this section is empty for the same measured reason rather than for a different one"
    ),
}

#: What each section reads. A section that prints figures names the rows behind them, so a reader can go and look.
SOURCES: Final = {
    "position": "user_players",
    "archetype": "user_players",
    "skills": "user_players",
    "training": "training_sessions \u00d7 training_drills",
    "videos": "video_assets \u00d7 video_detections",
    "achievements": "user_achievements \u00d7 achievements",
    "ai_reports": "coach_messages, knowledge_queries",
    "development": "attribute_changes, xp_events",
}

#: For the two sections this build cannot fill: the rows that would have to exist, named rather than implied.
WOULD_READ_FROM: Final = {
    "matches": "`real_player_match_stats` (generated world players) or a future row that references `user_players.id`",
    "stats": "the same rows as `Matches`, counted rather than listed",
}

#: The expressions behind every derived figure, printed beside it. A figure with no entry here is a stored column,
#: and the section that prints it says which column.
FORMULAS: Final = {
    "training.minutes": "\u03a3 training_drills.duration_min over this player's `completed` sessions",
    "training.xp_awarded": "\u03a3 training_sessions.xp_awarded over this player's sessions",
    "training.mean_execution": "round(mean(training_sessions.execution_rating) over rated sessions, 2)",
    "videos.minutes": "round(\u03a3 video_assets.duration_s / 60, 1)",
    "videos.detections": "count(video_detections) over this account's assets",
    "achievements.awarded": "count(user_achievements) for this account",
    "ai_reports.messages": "count(coach_messages) for this account",
    "ai_reports.answered": "count(knowledge_queries where answered is true) for this account",
    "development.net_change": "\u03a3 attribute_changes.delta per attribute, over this player",
    "development.xp_total": "\u03a3 xp_events.amount for this account",
}

LIMITATION: Final = (
    "a CV is a read: nothing in this tier stores a section, a figure or a copy of the rows it summarises, so re-reading "
    "it after a session, an upload or a badge shows the new number and never a stale one. Two of the ten sections "
    "cannot be filled in this build \u2014 `Matches` and `Stats` \u2014 because no row in this tree records this player "
    "appearing in a match; the reason travels with the section instead of a zero. Where a section is filled, the tables "
    "it read and the expression behind every derived figure are printed with it."
)

#: §38's three permitted outputs, each with the state of this build rather than a flag that would read as done.
#: A CV is built; a public profile, a share link and a PDF are named here so a page can print what is missing
#: instead of letting a reader assume an omission means "not needed".
PUBLIC_OUTPUTS: Final = {
    "public_player_profile": (
        "built: GET /portfolio/share/{token} is the profile — the account's own player row as §38's sections "
        "print it, with no account block and no identifying field, which is what makes it a profile rather than "
        "the CV door behind a session"
    ),
    "share_link": (
        "built: POST /portfolio/share opens it and DELETE /portfolio/share/{token} closes it, on §17's "
        "revocable-token precedent — one token per account, kept while the link is open, and a closed link "
        "answers the same 404 as a token that never existed"
    ),
    "pdf": (
        "not in this build: no PDF renderer is a dependency of this project, and `build_cv` publishes every figure a "
        "renderer would need, so a PDF is a later slice over this same read rather than a second source of truth"
    ),
}

#: §38's own door still registers no refusal code, and that stays a decision rather than an omission: a CV door asks
#: only whether
#: the caller has a session, which `current_user` answers with a 401 before any row is read, and an account with no
#: player row is answered by a CV whose player-backed sections say so. The four codes this tier *does* answer with
#: belong to `services/portfolio/sharing.py`, and this tuple exists so `GET /portfolio/rules` prints one refusal
#: table from the project's one answer table (`services/club/answers.py`) rather than from a literal written inside
#: the router — the shape §51 was written for, kept even when one of the tier's two sets is empty.
REFUSALS: Final[tuple[str, ...]] = ()

#: How many rows of a list-shaped section travel with the CV. The figures count everything; the list is a window.
RECENT: Final = 5


def player_of(session: Session, user_id: str, player_id: str | None) -> UserPlayer | None:
    """The account's player: the one it names, or its oldest one when it names none.

    Deterministic on purpose (`created_at, id`): a CV read twice must not pick a different player the second time
    because two rows share a timestamp.
    """
    if player_id is not None:
        row = session.get(UserPlayer, player_id)
        return row if row is not None and row.user_id == user_id else None
    return session.scalars(select(UserPlayer).where(UserPlayer.user_id == user_id).order_by(UserPlayer.created_at, UserPlayer.id).limit(1)).first()


def _section(
    key: str,
    *,
    available: bool,
    figures: dict[str, Any] | None = None,
    items: list[dict[str, Any]] | None = None,
    formulas: dict[str, str] | None = None,
    data_origin: str = "user",
    missing_because: str | None = None,
) -> dict[str, Any]:
    """One section in the shape every other section has, so a page never special-cases a member of the ten."""
    payload: dict[str, Any] = {
        "section": key,
        "title": SECTION_TITLES[key],
        "available": available,
        "source": SOURCES.get(key, ""),
        "data_origin": data_origin,
    }
    if not available:
        payload["missing_because"] = missing_because or UNFILLED_REASONS.get(key, "no rows to read")
        payload["would_be_read_from"] = WOULD_READ_FROM.get(key) or SOURCES.get(key, "")
        return payload
    payload["figures"] = figures or {}
    payload["formulas"] = {name: expression for name, expression in (formulas or {}).items()}
    payload["items"] = items or []
    return payload


def _empty(key: str, *, because: str) -> dict[str, Any]:
    """A filled section with nothing in it yet: the rows exist, they are simply not this account's."""
    return _section(key, available=False, missing_because=because)


def _position(player: UserPlayer) -> dict[str, Any]:
    return _section(
        "position",
        available=True,
        figures={
            "position": player.position,
            "secondary_positions": list(player.secondary_positions or []),
            "preferred_foot": player.preferred_foot,
            "weak_foot_rating": player.weak_foot_rating,
            "age": player.age,
            "height_cm": player.height_cm,
            "level": player.level,
            "goal": player.goal,
        },
        data_origin=player.data_origin,
    )


def _archetype(player: UserPlayer) -> dict[str, Any]:
    return _section(
        "archetype",
        available=True,
        figures={
            "archetype": player.archetype,
            "archetype_match": player.archetype_match,
            "style": player.style,
        },
        items=[{"reason": reason} for reason in (player.derivation_reasons or [])],
        data_origin=player.data_origin,
    )


def _skills(player: UserPlayer) -> dict[str, Any]:
    return _section(
        "skills",
        available=True,
        figures={
            "attributes": dict(player.attributes or {}),
            "overall": player.overall,
            "potential": player.potential,
            "form": player.form,
            "level_number": player.level_number,
            "xp": player.xp,
        },
        items=[{"attribute": name, "value": value} for name, value in sorted((player.attributes or {}).items())],
        data_origin=player.data_origin,
    )


def _training(session: Session, user_id: str, player_id: str) -> dict[str, Any]:
    rows = list(session.scalars(select(TrainingSession).where(TrainingSession.user_id == user_id, TrainingSession.player_id == player_id)))
    if not rows:
        return _empty("training", because="this account has no training session on record yet; the rows live in `training_sessions` and are written by §10's academy")
    minutes = 0
    for row in rows:
        drill = session.get(TrainingDrill, row.drill_id)
        minutes += int(drill.duration_min) if drill is not None and row.status == "completed" else 0
    rated = [row.execution_rating for row in rows if row.execution_rating is not None]
    completed = [row for row in rows if row.status == "completed"]
    recent = sorted(completed, key=lambda row: (row.completed_at is None, row.completed_at, row.id))[-RECENT:]
    items = []
    for row in recent:
        drill = session.get(TrainingDrill, row.drill_id)
        items.append(
            {
                "session": row.id,
                "drill": drill.title if drill is not None else "",
                "category": drill.category if drill is not None else "",
                "completed_at": row.completed_at.isoformat() if row.completed_at is not None else None,
                "execution_rating": row.execution_rating,
                "xp_awarded": row.xp_awarded,
            }
        )
    return _section(
        "training",
        available=True,
        figures={
            "sessions": len(rows),
            "completed": len(completed),
            "planned": len(rows) - len(completed),
            "minutes": minutes,
            "xp_awarded": sum(int(row.xp_awarded or 0) for row in rows),
            "mean_execution": round(sum(rated) / len(rated), 2) if rated else None,
        },
        formulas={key.split(".", 1)[1]: value for key, value in FORMULAS.items() if key.startswith("training.")},
        items=items,
    )


def _videos(session: Session, user_id: str) -> dict[str, Any]:
    assets = list(session.scalars(select(VideoAsset).where(VideoAsset.owner_id == user_id).order_by(VideoAsset.created_at, VideoAsset.id)))
    if not assets:
        return _empty("videos", because="this account has uploaded no clip yet; the rows live in `video_assets` and are written by §13's upload door")
    ids = [asset.id for asset in assets]
    detections = int(session.scalar(select(func.count()).select_from(VideoDetection).where(VideoDetection.asset_id.in_(ids))) or 0)
    items = [
        {
            "asset": asset.id,
            "title": asset.title,
            "status": asset.status,
            "duration_s": asset.duration_s,
            "frame_count": asset.frame_count,
        }
        for asset in sorted(assets, key=lambda row: (row.created_at, row.id))[-RECENT:]
    ]
    return _section(
        "videos",
        available=True,
        figures={
            "assets": len(assets),
            "analysed": len([asset for asset in assets if asset.status == "analysed"]),
            "failed": len([asset for asset in assets if asset.status == "failed"]),
            "minutes": round(sum(float(asset.duration_s or 0.0) for asset in assets) / 60, 1),
            "frames": sum(int(asset.frame_count or 0) for asset in assets),
            "detections": detections,
        },
        formulas={key.split(".", 1)[1]: value for key, value in FORMULAS.items() if key.startswith("videos.")},
        items=items,
        data_origin="user",
    )


def _achievements(session: Session, user_id: str) -> dict[str, Any]:
    awarded = list(session.execute(select(UserAchievement, Achievement).join(Achievement, Achievement.id == UserAchievement.achievement_id).where(UserAchievement.user_id == user_id)))
    catalogue = int(session.scalar(select(func.count()).select_from(Achievement)) or 0)
    if not awarded:
        return _empty("achievements", because=f"no badge has been awarded to this account yet; {catalogue} are defined in `achievements` and §37's rules award them")
    items = [
        {
            "slug": achievement.slug,
            "title": achievement.title,
            "description": achievement.description,
            "criterion": achievement.criterion,
            "awarded_at": row.awarded_at.isoformat() if row.awarded_at is not None else None,
        }
        for row, achievement in awarded
    ]
    return _section(
        "achievements",
        available=True,
        figures={"awarded": len(items), "catalogue": catalogue},
        formulas={"awarded": FORMULAS["achievements.awarded"]},
        items=items,
    )


def _ai_reports(session: Session, user_id: str) -> dict[str, Any]:
    messages = list(session.scalars(select(CoachMessage).where(CoachMessage.user_id == user_id).order_by(CoachMessage.created_at, CoachMessage.id)))
    queries = list(session.scalars(select(KnowledgeQuery).where(KnowledgeQuery.user_id == user_id)))
    if not messages and not queries:
        return _empty("ai_reports", because="this account has asked the coach or the knowledge base nothing yet; the rows live in `coach_messages` and `knowledge_queries`")
    kinds: dict[str, int] = {}
    for message in messages:
        kinds[message.kind] = kinds.get(message.kind, 0) + 1
    items = [
        {
            "kind": message.kind,
            "role": message.role,
            "provider": message.provider,
            "model": message.model,
            "demo_mode": message.demo_mode,
            "confidence": message.confidence,
            "created_at": message.created_at.isoformat() if message.created_at is not None else None,
        }
        for message in sorted(messages, key=lambda row: (row.created_at, row.id))[-RECENT:]
    ]
    return _section(
        "ai_reports",
        available=True,
        figures={
            "messages": len(messages),
            "kinds": kinds,
            "demo_mode": len([message for message in messages if message.demo_mode]),
            "questions": len(queries),
            "answered": len([query for query in queries if query.answered]),
        },
        formulas={key.split(".", 1)[1]: value for key, value in FORMULAS.items() if key.startswith("ai_reports.")},
        items=items,
        data_origin="user+demo",
    )


def _development(session: Session, user_id: str, player_id: str) -> dict[str, Any]:
    changes = list(session.scalars(select(AttributeChange).where(AttributeChange.player_id == player_id).order_by(AttributeChange.created_at, AttributeChange.id)))
    xp_events = list(session.scalars(select(XpEvent).where(XpEvent.player_id == player_id).order_by(XpEvent.created_at, XpEvent.id)))
    if not changes and not xp_events:
        return _empty(
            "development", because="this player has no recorded attribute change or XP award yet; the rows live in `attribute_changes` and `xp_events` and are written when a session is completed"
        )
    net: dict[str, int] = {}
    for change in changes:
        net[change.attribute] = net.get(change.attribute, 0) + int(change.delta)
    items = [
        {
            "attribute": change.attribute,
            "delta": change.delta,
            "before": change.before,
            "after": change.after,
            "reason": change.reason,
            "evidence_ids": list(change.evidence_ids or []),
            "created_at": change.created_at.isoformat() if change.created_at is not None else None,
        }
        for change in changes[-RECENT:]
    ]
    items += [
        {
            "xp": event.amount,
            "reason": event.reason,
            "formula": event.formula,
            "source_type": event.source_type,
            "created_at": event.created_at.isoformat() if event.created_at is not None else None,
        }
        for event in xp_events[-RECENT:]
    ]
    return _section(
        "development",
        available=True,
        figures={
            "changes": len(changes),
            "net_change": dict(sorted(net.items())),
            "xp_total": sum(int(event.amount) for event in xp_events),
            "first_change": changes[0].created_at.isoformat() if changes else None,
            "last_change": changes[-1].created_at.isoformat() if changes else None,
        },
        formulas={key.split(".", 1)[1]: value for key, value in FORMULAS.items() if key.startswith("development.")},
        items=items,
    )


#: The three sections an account's CV reads without a player row. They are resolved before the player is looked
#: for, because an account that has asked the coach a question but written no player still has an AI Reports
#: section — and the absence of a player must not be a crash on the way to it.
_ACCOUNT_SECTIONS: Final = {
    "videos": _videos,
    "achievements": _achievements,
    "ai_reports": _ai_reports,
}


def build_cv(session: Session, user_id: str, *, player_id: str | None = None) -> dict[str, Any]:
    """The account's CV: §38's ten sections, in order, each a read of rows that already exist.

    An account with no player row is not an error — it is a CV whose player-backed sections say so — because a door
    that answered `404` would be telling the reader less than the payload can.
    """
    account = session.get(User, user_id)
    player = player_of(session, user_id, player_id)
    sections: list[dict[str, Any]] = []
    for key in SECTIONS:
        if key in UNFILLED_REASONS:
            sections.append(_section(key, available=False))
            continue
        builder = _ACCOUNT_SECTIONS.get(key)
        if builder is not None:
            sections.append(builder(session, user_id))
            continue
        if player is None:
            sections.append(_empty(key, because="this account has no player row yet; §7's identity is the first thing a CV needs, and the row lives in `user_players`"))
            continue
        if key == "position":
            sections.append(_position(player))
        elif key == "archetype":
            sections.append(_archetype(player))
        elif key == "skills":
            sections.append(_skills(player))
        elif key == "training":
            sections.append(_training(session, user_id, player.id))
        elif key == "development":
            sections.append(_development(session, user_id, player.id))
        else:  # pragma: no cover - SECTIONS is checked against the builders by the test file
            raise AssertionError(f"{key!r} is one of the ten and has no builder")

    filled = [section["section"] for section in sections if section["available"]]
    unfilled = [section["section"] for section in sections if not section["available"]]
    return {
        "account": {"user_id": user_id, "display_name": account.display_name if account is not None else ""},
        "player": ({"id": player.id, "name": player.name, "position": player.position, "visibility": player.visibility, "data_origin": player.data_origin} if player is not None else None),
        "has_player": player is not None,
        "sections": sections,
        "counts": {"sections": len(sections), "filled": len(filled), "unfilled": unfilled},
        "unfilled_reasons": {key: UNFILLED_REASONS[key] for key in unfilled if key in UNFILLED_REASONS},
        "formulas": dict(FORMULAS),
        "limitation": LIMITATION,
    }
