"""Community endpoints (M9, spec §35): what an account publishes, and the rows that decide who reads it.

One public door and eleven private ones. The public door (`GET /community/rules`) prints only the tier's own
vocabulary — the kinds, the ceilings, the formulas, the refusal codes and the limitation sentence — which is
§39's precedent for a rulebook page: published rules are not a person's data, a feed of posts is.

There is no 403 anywhere in this file, and that is a decision rather than an omission. §51 reserves 403 for the
permission matrix's answer, and the community has no matrix: the only question a door here asks is whether the
caller has a session, which `current_user` answers with a 401 before any service code can run. What a caller
may not reach is therefore answered as **absence** — `no_such_post`, `no_such_account` — with the same shape a
genuinely missing row earns, so no door here confirms that somebody else's private wall exists.

Every figure on every answer is counted by the service at read time (`services/community/posts.py`), so nothing
in this module could cache one: a post's `likes`, a profile's `followers` and a feed's `feed_total` are the same
rows the tier stores, recounted per request. A refusal is answered from the one table §51 assembled
(`services/club/answers.py`), which is why this router has no answer dict of its own.
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, limit
from app.models import User
from app.services.club import answers
from app.services.community import posts as com

router = APIRouter(prefix="/community", tags=["community"])

#: Which answer each code earns is decided once, in `services/club/answers.py`, over every tier's own sets. This
#: is the *same object* the club doors answer from — `test_community.py` asserts the identity, because a door
#: that re-forked the table would answer a shared code one way here and another way at `/club`.
_ANSWERS: Final[dict[str, int]] = answers.ANSWERS

#: Every door this module declares, in the order a reader meets them. Held against the live route table by
#: `test_community.py`, the way §39 holds club's guide — a list that drifts from the routes would otherwise be
#: a page pointing at doors that are not there.
ROUTE_GUIDE: tuple[dict[str, str], ...] = (
    {"method": "GET", "path": "/community/rules", "door": "the tier's own vocabulary: kinds, ceilings, formulas, refusals"},
    {"method": "POST", "path": "/community/posts", "door": "publish words, or words plus a pointer to your own artifact"},
    {"method": "GET", "path": "/community/posts", "door": "your feed, or one author's wall as far as you may read it"},
    {"method": "GET", "path": "/community/posts/{post}", "door": "one post with its figures counted now"},
    {"method": "DELETE", "path": "/community/posts/{post}", "door": "erase your own post, and the rows on it"},
    {"method": "POST", "path": "/community/posts/{post}/comments", "door": "reply in words"},
    {"method": "GET", "path": "/community/posts/{post}/comments", "door": "the replies, newest first"},
    {"method": "POST", "path": "/community/posts/{post}/reactions", "door": "react; a second press is the same row"},
    {"method": "POST", "path": "/community/posts/{post}/reposts", "door": "carry somebody else's post to your followers"},
    {"method": "POST", "path": "/community/follows/{member}", "door": "follow an account; it decides who a `followers` post reaches"},
    {"method": "DELETE", "path": "/community/follows/{member}", "door": "unfollow; reach is withdrawn, nothing already read is deleted"},
    {"method": "GET", "path": "/community/members/{member}", "door": "an account's wall counts, both sides of a follow"},
)


def _refusal(error: com.CommunityRefusal) -> HTTPException:
    """The answer a community refusal deserves, read out of the project's one table (§51)."""
    return HTTPException(_ANSWERS.get(error.code, status.HTTP_400_BAD_REQUEST), detail=error.to_dict())


class PostIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # No `min_length` on any of these: a blank body and an over-long one are the *tier's* refusals, with the
    # figures that explain them beside the sentence. A pydantic bound would answer the same mistake with a
    # validation list that names no ceiling.
    kind: str = Field(default="note", max_length=24)
    body: str = Field(default="", max_length=com.POST_BODY_MAX + 200)
    pointer: str = Field(default="", max_length=com.POINTER_MAX + 40)
    visibility: str = Field(default="public", max_length=12)


class CommentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(default="", max_length=com.COMMENT_BODY_MAX + 100)


class ReactionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reaction: str = Field(default="like", max_length=16)


@router.get("/rules")
def read_rules(db: Session = Depends(get_db)) -> dict[str, Any]:
    """The tier's own rulebook: no post, no profile, no figure about anybody — only what may be published.

    `refusal_answers` is derived here, from the same table `_refusal` reads, rather than written beside the route:
    a page that prints a status the door does not use teaches a caller to expect an answer that never comes.
    """
    return {"routes": [dict(item) for item in ROUTE_GUIDE], "refusal_answers": answers.published(com.REFUSALS), **com.rules(db, ready=True)}


@router.post("/posts")
def publish(payload: PostIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Publish. A `note` carries words; every other kind carries words *and* the address of your own artifact."""
    limit(request, 10, 60, scope="community_write")
    try:
        return com.create_post(db, user.id, kind=payload.kind, body=payload.body, pointer=payload.pointer, visibility=payload.visibility)
    except com.CommunityRefusal as error:
        raise _refusal(error) from None


@router.get("/posts")
def read_feed(request: Request, author: str | None = None, page_size: int = 20, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Your feed — the accounts you follow plus you — or one author's wall as far as your reach extends."""
    limit(request, 60, 60, scope="community_read")
    try:
        return com.list_posts(db, user.id, author=author, limit=page_size)
    except com.CommunityRefusal as error:
        raise _refusal(error) from None


@router.get("/posts/{post}")
def read_post(post: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """One post, its figures counted from the rows at this moment, and whether you have reacted."""
    limit(request, 60, 60, scope="community_read")
    try:
        return com.read_post(db, post, user.id)
    except com.CommunityRefusal as error:
        raise _refusal(error) from None


@router.delete("/posts/{post}")
def erase_post(post: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Erase your own post. Its replies, reactions and reposts go with it, and the answer says how many did."""
    limit(request, 10, 60, scope="community_write")
    try:
        return com.erase_post(db, post, user.id)
    except com.CommunityRefusal as error:
        raise _refusal(error) from None


@router.post("/posts/{post}/comments")
def comment(post: str, payload: CommentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    limit(request, 20, 60, scope="community_write")
    try:
        return com.add_comment(db, post, user.id, body=payload.body)
    except com.CommunityRefusal as error:
        raise _refusal(error) from None


@router.get("/posts/{post}/comments")
def read_comments(post: str, request: Request, page_size: int = 50, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    limit(request, 60, 60, scope="community_read")
    try:
        return com.list_comments(db, post, limit=page_size)
    except com.CommunityRefusal as error:
        raise _refusal(error) from None


@router.post("/posts/{post}/reactions")
def react(post: str, payload: ReactionIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """React. The schema, not this handler, is what makes a second press the same row."""
    limit(request, 30, 60, scope="community_write")
    try:
        return com.react(db, post, user.id, reaction=payload.reaction)
    except com.CommunityRefusal as error:
        raise _refusal(error) from None


@router.post("/posts/{post}/reposts")
def repost(post: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Carry another account's post to your followers. What travels is the pointer, never a copy of figures."""
    limit(request, 20, 60, scope="community_write")
    try:
        return com.repost(db, post, user.id)
    except com.CommunityRefusal as error:
        raise _refusal(error) from None


@router.post("/follows/{member}")
def follow(member: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    limit(request, 30, 60, scope="community_write")
    try:
        return com.follow(db, user.id, member)
    except com.CommunityRefusal as error:
        raise _refusal(error) from None


@router.delete("/follows/{member}")
def unfollow(member: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Withdraw reach. Idempotent, and it deletes nothing that was already read."""
    limit(request, 30, 60, scope="community_write")
    try:
        return com.unfollow(db, user.id, member)
    except com.CommunityRefusal as error:
        raise _refusal(error) from None


@router.get("/members/{member}")
def read_profile(member: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    limit(request, 60, 60, scope="community_read")
    try:
        return com.profile(db, member)
    except com.CommunityRefusal as error:
        raise _refusal(error) from None
