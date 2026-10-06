"""Portfolio endpoints (M10, spec §38): the Football CV, read section by section from rows other tiers own.

One public rulebook, one private CV, and — since §38's second permitted output landed — one link an unauthenticated
reader can open. `GET /portfolio/rules` prints only the tier's own vocabulary: §38's ten sections in §38's order, the
expression behind every derived figure, the two sections this build cannot fill and the measurement that says why,
the three outputs §38 permits with the door that serves each, and the share tier's rules — the names a link may
carry, the one a minor's link may not, and the threshold that decides it. That is §39's, §35's and §36's precedent: a
rulebook is not a person's rows, a CV is.

`GET /portfolio/cv` is the CV itself. The only thing this tier stores is a share link, and a link stores no figures:
`services/portfolio/sharing.py` keeps a token and a list of section names, and `GET /portfolio/share/{token}` rebuilds
the CV from the rows its published formulas name at the moment of the request. So completing a session and re-reading
a link that was minted before the session shows the new number, and nothing here can go stale, because nothing here
is a copy.

Two doors in this file answer 401 before any row is read — the CV and the three share doors — because the only
question they ask first is whether the caller has a session. The share read answers 404 for a token that never
existed, one that has been closed and one that belongs to somebody else, in the same sentence; §35's rule that
absence must not confirm existence, applied to a link. `refusal_answers` is printed from the project's one table
(`services/club/answers.py`) over both of this tier's code sets, so a code added by a later slice cannot be answered
one way here and another at `/club`.
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, limit
from app.models import User
from app.services.club import answers
from app.services.portfolio import cv as portfolio
from app.services.portfolio import pdf as portfolio_pdf
from app.services.portfolio import sharing

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

#: Every door this module declares, in the order a reader meets them. Held against the live route table by
#: `test_portfolio.py` in both directions, because the rules door prints this list to the browser as the tier's own
#: description of itself.
ROUTE_GUIDE: Final[tuple[dict[str, str], ...]] = (
    {"method": "GET", "path": "/portfolio/rules", "door": "the tier's vocabulary: §38's ten sections, the formulas, the two the build cannot fill, the share tier's rules"},
    {"method": "GET", "path": "/portfolio/cv", "door": "your Football CV: ten sections, each a read of the rows its source names"},
    {"method": "GET", "path": "/portfolio/cv.pdf", "door": "the same ten-section read rendered as a PDF; nothing is stored and the response is never cached"},
    {"method": "POST", "path": "/portfolio/share", "door": "open a link over the sections you name, or re-point the one that is already open"},
    {"method": "GET", "path": "/portfolio/shares", "door": "every link this account opened, with the live one's token and a closed one's timestamp"},
    {"method": "DELETE", "path": "/portfolio/share/{token}", "door": "close one link; the row stays so the account can say when it shut"},
    {"method": "GET", "path": "/portfolio/share/{token}", "door": "the public read: no session, no account block, only the sections this link publishes"},
)


def _refusal(error: sharing.ShareRefusal) -> HTTPException:
    """The HTTP answer a share refusal deserves, from the same table every other tier answers from (§51)."""
    return HTTPException(answers.ANSWERS.get(error.code, status.HTTP_400_BAD_REQUEST), detail=error.to_dict())


def _vocabulary() -> list[dict[str, Any]]:
    """§38's ten sections as data: the key, the spec's word for it, the rows behind it, and whether this build fills it."""
    return [
        {
            "section": key,
            "title": portfolio.SECTION_TITLES[key],
            "source": portfolio.SOURCES.get(key, ""),
            "fillable": key not in portfolio.UNFILLED_REASONS,
        }
        for key in portfolio.SECTIONS
    ]


@router.get("/rules")
def read_rules() -> dict[str, Any]:
    """The rulebook door: no account, no player, no figure about anybody — only what a CV and a link are made of."""
    return {
        "routes": [dict(item) for item in ROUTE_GUIDE],
        "refusal_answers": answers.published(portfolio.REFUSALS, sharing.REFUSALS),
        "sections": _vocabulary(),
        "unfilled": {key: portfolio.UNFILLED_REASONS[key] for key in portfolio.SECTIONS if key in portfolio.UNFILLED_REASONS},
        "would_read_from": dict(portfolio.WOULD_READ_FROM),
        "formulas": dict(portfolio.FORMULAS),
        "public_outputs": dict(portfolio.PUBLIC_OUTPUTS),
        "share": {
            "publishable": list(sharing.PUBLISHABLE),
            "minor_blocked": list(sharing.MINOR_BLOCKED),
            "minor_age": sharing.MINOR_AGE,
            "token_shape": f"secrets.token_hex({sharing.TOKEN_BYTES}) — {sharing.TOKEN_BYTES * 2} hex characters, §17's board-token shape",
            "private_keys_dropped": list(sharing.PRIVATE_KEYS),
        },
        "limitation": portfolio.LIMITATION,
    }


@router.get("/cv")
def read_cv(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The account's CV, ten sections in §38's order. Nothing here is stored and nothing is cached."""
    limit(request, 60, 60, scope="portfolio_read")
    return portfolio.build_cv(db, user.id)


@router.get(
    "/cv.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The account's Football CV rendered from the live read."}},
)
def download_cv_pdf(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Response:
    """Render the same live CV read as a downloadable PDF without persisting the document or its figures."""
    limit(request, 20, 60, scope="portfolio_pdf")
    return Response(
        content=portfolio_pdf.build_cv_pdf(db, user.id),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="football-cv.pdf"',
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/share")
def open_share(
    body: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Publish the sections the body names behind a fresh token, or re-point the link that is already open.

    The body carries section names and nothing else: a link points at an account, so there is no id here whose
    ownership a caller could probe. See `services/portfolio/sharing.py` for why that is a reach rule, not a shortcut.
    """
    limit(request, 20, 60, scope="portfolio_share_write")
    try:
        return sharing.share(db, user.id, sections=body.get("sections"))
    except sharing.ShareRefusal as error:
        raise _refusal(error) from error


@router.get("/shares")
def read_shares(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The account's own link ledger: what is open now, and when each closed one shut."""
    limit(request, 60, 60, scope="portfolio_share_list")
    return sharing.list_shares(db, user.id)


@router.delete("/share/{token}")
def close_share(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Take the link back. §38's output is revocable, which is the whole difference between a link and a leak."""
    limit(request, 20, 60, scope="portfolio_share_write")
    try:
        return sharing.revoke(db, user.id, token)
    except sharing.ShareRefusal as error:
        raise _refusal(error) from error


@router.get("/share/{token}")
def read_shared(token: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """The public read. No `current_user` dependency: the token is the whole credential, as it is at §17's board door.

    Rate-limited on its own scope, because a public door is the one a stranger can knock on. The answer carries no
    account identity — `sharing.public_cv` subtracts the account block and the keys listed as private before the
    payload is built, so there is nothing here to scrub afterwards.
    """
    limit(request, 60, 60, scope="portfolio_share_read")
    try:
        return sharing.public_cv(db, token)
    except sharing.ShareRefusal as error:
        raise _refusal(error) from error
