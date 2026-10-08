"""Transfer market endpoints (M6, spec §22).

One door, §61, the same one every other piece of user state uses: the market's *rules* are public
fiction (the valuation, the negotiation ladder, the clause), a career's offers and deals are not. A
slug belonging to another account is a 404 rather than a 403, so the existence of someone else's
transfer history is never confirmed.

`GET` reads; it never reprices. Opening the market for a round is a `POST /market`, because listing a
player at a price is an event with consequences — a negotiated discount does not survive it — and an
event that loading a page should not be able to trigger by accident.

Every refusal answers with the figures that produced it. `insufficient_budget` carries the fee and the
balance, `rival_will_not_sell` carries the clause, `would_not_field_a_side` carries the player and
keeper counts: a market a reader cannot check is a market a reader has to trust.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, limit, ownership_or_admin
from app.models import MOVE_EFFECT, Career, User
from app.services.club import answers
from app.services.simulation.market import (
    MARKET_DISCLAIMER,
    RULES,
    MarketRefusal,
    buy,
    loan,
    market_view,
    move_row,
    negotiate,
    open_market,
    release,
    sell,
    transferable,
)

router = APIRouter(prefix="/transfers", tags=["transfers"])

NOT_FOUND = {"code": "not_found", "message": "No such career for this account"}


class OfferIn(BaseModel):
    listing: str = Field(min_length=1, max_length=60)
    offer: int = Field(ge=0, le=1_000_000_000)


class BuyIn(BaseModel):
    listing: str = Field(min_length=1, max_length=60)
    use_clause: bool = False


class LoanIn(BaseModel):
    listing: str = Field(min_length=1, max_length=60)
    rounds: int = Field(default=4, ge=1, le=40)


class OutIn(BaseModel):
    player: str = Field(min_length=1, max_length=160)


def _career(db: Session, user: User, ident: str) -> Career:
    row = db.scalar(select(Career).where(Career.slug == ident)) or db.scalar(select(Career).where(Career.id == ident))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    ownership_or_admin(user, row.owner_id, "career")
    return row


def _refusal(error: MarketRefusal) -> HTTPException:
    payload = error.to_dict()
    return HTTPException(answers.ANSWERS.get(str(payload["code"]), status.HTTP_409_CONFLICT), detail=payload)


@router.get("/rules")
def read_rules(request: Request) -> dict[str, Any]:
    """The market's arithmetic, published for anyone: how a price, a clause, a wage and a fit are made."""
    limit(request, 60, 60, scope="transfer_rules")
    return {
        "rules": RULES,
        "move_effects": dict(MOVE_EFFECT),
        "disclaimer": MARKET_DISCLAIMER,
        "data_origin": "simulation",
        "is_demo_data": True,
    }


@router.get("/{ident}")
def read_market(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Everything one career's market holds: the need, the offers, the squad, and the ledger."""
    limit(request, 60, 60, scope="transfer_read")
    career = _career(db, user, ident)
    return market_view(db, career)


@router.post("/{ident}/market")
def open_the_market(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Price this round's offers. A re-listed price starts afresh, so a negotiated discount ends with it."""
    limit(request, 20, 60, scope="transfer_open")
    career = _career(db, user, ident)
    verdict = transferable(db, career)
    if not verdict["ok"]:
        raise HTTPException(answers.ANSWERS.get(str(verdict["code"]), status.HTTP_409_CONFLICT), detail=verdict)
    report = open_market(db, career)
    return {"opened": True, "listing_report": report, **market_view(db, career)}


@router.post("/{ident}/negotiate")
def make_offer(ident: str, payload: OfferIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Put an offer in and take the answer the seller's rule gives, with the rule printed beside it."""
    limit(request, 30, 60, scope="transfer_negotiate")
    career = _career(db, user, ident)
    try:
        outcome = negotiate(db, career, ident=payload.listing, offer=payload.offer)
    except MarketRefusal as error:
        raise _refusal(error) from None
    return {"negotiated": True, "result": outcome, **market_view(db, career)}


@router.post("/{ident}/buy")
def sign_player(ident: str, payload: BuyIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Pay the current price — or the release clause, if a rival has to be moved."""
    limit(request, 20, 60, scope="transfer_buy")
    career = _career(db, user, ident)
    try:
        move, detail = buy(db, career, ident=payload.listing, use_clause=payload.use_clause)
    except MarketRefusal as error:
        raise _refusal(error) from None
    return {"bought": True, "move": move_row(move), "detail": detail, **market_view(db, career)}


@router.post("/{ident}/loan")
def loan_player(ident: str, payload: LoanIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Take a player for a stated number of rounds at a fraction of the fee."""
    limit(request, 20, 60, scope="transfer_loan")
    career = _career(db, user, ident)
    try:
        move, detail = loan(db, career, ident=payload.listing, rounds=payload.rounds)
    except MarketRefusal as error:
        raise _refusal(error) from None
    return {"loaned": True, "move": move_row(move), "detail": detail, **market_view(db, career)}


@router.post("/{ident}/sell")
def sell_player(ident: str, payload: OutIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Sell one of this career's own players; the proceeds arrive against the next round."""
    limit(request, 20, 60, scope="transfer_sell")
    career = _career(db, user, ident)
    try:
        move, detail = sell(db, career, ident=payload.player)
    except MarketRefusal as error:
        raise _refusal(error) from None
    return {"sold": True, "move": move_row(move), "detail": detail, **market_view(db, career)}


@router.post("/{ident}/release")
def release_player(ident: str, payload: OutIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Let one go for nothing. No fee either way, and the eleven still loses a player."""
    limit(request, 20, 60, scope="transfer_release")
    career = _career(db, user, ident)
    try:
        move, detail = release(db, career, ident=payload.player)
    except MarketRefusal as error:
        raise _refusal(error) from None
    return {"released": True, "move": move_row(move), "detail": detail, **market_view(db, career)}
