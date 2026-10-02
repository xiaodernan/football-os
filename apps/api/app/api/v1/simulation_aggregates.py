"""Aggregate simulation endpoints (M6 item 10 open item): league-wide and cross-career reads.

The ROADMAP open item reads: "no cross-career or league-wide aggregate reads these rows".
This router adds two public aggregate endpoints that span multiple careers:

* GET /simulation/aggregates/league/{competition_slug} — league-wide ledger
* GET /simulation/aggregates/player/{player_slug} — player career aggregate
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import limit
from app.models import Competition, Career, CareerFixture, CareerAppearance
from app.services.simulation.aggregates import league_ledger_view, player_career_aggregate_view
from app.services.simulation.engine import SIMULATION_DISCLAIMER

router = APIRouter(prefix="/simulation/aggregates", tags=["simulation-aggregates"])

NOT_FOUND = {"code": "not_found", "message": "No such resource"}


@router.get("/league/{competition_slug}")
def read_league_ledger(
    competition_slug: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """League-wide ledger: all careers whose club is in this competition, summed together.
    
    Public read: no session required. The club is the unit of aggregation — a club
    may have multiple careers (one per account), and a fixture belongs to one club.
    """
    limit(request, 30, 60, scope="sim_agg_league")
    competition = db.scalar(select(Competition).where(Competition.slug == competition_slug))
    if competition is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return league_ledger_view(db, competition)


@router.get("/player/{player_slug}")
def read_player_career_aggregate(
    player_slug: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Player career aggregate: all careers with a player matching this slug, summed.
    
    Public read: no session required. The player is identified by slug (which is
    unique per career, but a real player may have multiple careers — one per account).
    We find all careers that have a player with this slug and sum their events.
    """
    limit(request, 30, 60, scope="sim_agg_player")
    # Find careers that have a player with this slug via CareerAppearance
    career_ids = [
        str(row[0]) for row in
        db.execute(
            select(Career.id)
            .join(CareerAppearance, CareerAppearance.career_id == Career.id)
            .where(CareerAppearance.player_slug == player_slug)
            .distinct()
        ).all()
    ]
    if not career_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return player_career_aggregate_view(db, career_ids, player_slug)