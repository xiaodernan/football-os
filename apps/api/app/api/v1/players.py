"""My Football: player creation and profile (spec §5–§7, §51)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, new_public_id, ownership_or_admin
from app.models import User, UserPlayer
from app.schemas import PlayerIn, PlayerOut
from app.services.attributes import ALL_ATTRIBUTES, derive_archetype, derive_baseline
from app.services.progression import refresh_derived_state

router = APIRouter(prefix="/players", tags=["players"])

DERIVATION_KEY = "derivation_reasons"


def to_out(player: UserPlayer, reasons: list[str] | None = None) -> PlayerOut:
    payload = PlayerOut.model_validate(player)
    payload.attributes = {k: v for k, v in player.attributes.items() if not k.startswith("_sp_")}
    payload.derivation_reasons = reasons or list(player.derivation_reasons)
    return payload


@router.post("", response_model=PlayerOut, status_code=status.HTTP_201_CREATED)
def create_player(payload: PlayerIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> PlayerOut:
    if db.scalar(select(UserPlayer).where(UserPlayer.user_id == user.id)):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "player_exists", "message": "One player profile per account in M1; multiple squads arrive with Club OS (M8)"},
        )
    baseline = derive_baseline(
        position=payload.position,
        age=payload.age,
        level=payload.level,
        preferred_foot=payload.preferred_foot,
        height_cm=payload.height_cm,
    )
    attributes = dict(baseline.attributes)
    reasons = list(baseline.reasons)
    if payload.self_rated_attributes:
        for name, rating in payload.self_rated_attributes.items():
            derived = attributes.get(name, 40)
            blended = round(derived * 0.6 + rating * 0.4)
            attributes[name] = blended
        reasons.append("Self-rated assessment blended 60/40 with the positional baseline — the baseline stays the ceiling until training proves otherwise")
    archetype, match, arch_reasons = derive_archetype(payload.position, attributes)
    reasons += arch_reasons
    player = UserPlayer(
        id=new_public_id("ply"),
        user_id=user.id,
        name=payload.name.strip(),
        position=payload.position,
        preferred_foot=payload.preferred_foot,
        age=payload.age,
        level=payload.level,
        height_cm=payload.height_cm,
        goal=payload.goal,
        attributes=attributes,
        derivation_reasons=reasons,
        archetype=archetype,
        archetype_match=match,
        data_origin="user",
    )
    player.overall = player.overall or baseline.overall
    player.potential = baseline.potential
    refresh_derived_state(player)
    db.add(player)
    db.commit()
    return to_out(player, reasons)


@router.get("", response_model=list[PlayerOut])
def list_players(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[PlayerOut]:
    rows = db.scalars(select(UserPlayer).where(UserPlayer.user_id == user.id).order_by(UserPlayer.created_at)).all()
    return [to_out(row) for row in rows]


@router.get("/{player_id}", response_model=PlayerOut)
def get_player(player_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> PlayerOut:
    player = db.get(UserPlayer, player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "Player not found"})
    ownership_or_admin(user, player.user_id, "player")
    return to_out(player)


@router.patch("/{player_id}", response_model=PlayerOut)
def update_player(player_id: str, payload: PlayerIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> PlayerOut:
    player = db.get(UserPlayer, player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "Player not found"})
    ownership_or_admin(user, player.user_id, "player")
    player.name = payload.name.strip()
    player.age = payload.age
    player.height_cm = payload.height_cm
    player.goal = payload.goal
    player.preferred_foot = payload.preferred_foot
    if payload.position != player.position:
        player.position = payload.position
        baseline = derive_baseline(position=player.position, age=player.age, level=player.level, preferred_foot=player.preferred_foot, height_cm=player.height_cm)
        for name in ALL_ATTRIBUTES:
            player.attributes = {**player.attributes, name: max(int(player.attributes.get(name, 40)), baseline.attributes[name] - 6)}
    clean = {k: v for k, v in player.attributes.items() if not k.startswith("_sp_")}
    archetype, match, _reasons = derive_archetype(player.position, clean)
    player.derivation_reasons = [*player.derivation_reasons, f"Updated on {payload.position} / goal {payload.goal}"]
    player.archetype, player.archetype_match = archetype, match
    refresh_derived_state(player)
    db.commit()
    return to_out(player)


@router.delete("/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_player(player_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    player = db.get(UserPlayer, player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "Player not found"})
    ownership_or_admin(user, player.user_id, "player")
    db.delete(player)
    db.commit()
