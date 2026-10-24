"""§35's Community tier: a post points at an artifact and stores no figure about it.

This is the first thing stored about a *person* rather than a tenant, and the one decision that shapes it is that
**a share is a pointer, never a copy**. A post that carried a board's possession figures, or a plan's weekly load,
would keep asserting them after the artifact behind it changed — which is the same failure §41 named for a stored
report and §57 for a stored readership. So `community_posts` holds a `kind`, a `pointer` (the path of the thing
being shared) and the author's own words, and every number a reader sees about a post is a `count(*)` over the
reaction, comment, repost and follow rows at the moment of the read, with its formula printed beside it.

Three consequences follow, and each is held by a named case rather than by this paragraph:

* **A reaction, a repost and a follow are one row per pair**, because a unique constraint says so rather than
  because a code path happens to check — §40's consent row and §57's receipt row, reused. Pressing twice answers
  `already recorded` with `recorded_now: false` and moves no figure.
* **Reach is a predicate over follows, not a recipient list.** `visibility` selects *which authors' posts* a
  reader sees; nothing here stores who may read a given post. A `followers` post is visible to its author and to
  the accounts whose follow rows point at that author, recomputed on every read, so an unfollow removes reach at
  once and deletes nothing.
* **There is no private channel in this tier.** No column can name a recipient, no door takes one, and the six
  kinds a user may publish all point at artifacts that are the author's own to share. §40's minimisation rule is
  the shape of the table rather than a validation inside it.
* **A pointer is a promise, and the row behind it answers.** The shape of an address is checked at the door, and
  so is the artifact: five kinds resolve to rows the author owns (a run and a career in `careers`, a played match
  in `sim_matches`, a drawn board in `tactic_boards`, an uploaded clip in `video_assets`) and one resolves to the
  project's own drill catalogue. A missing row and another account's row answer one sentence — a message that
  told them apart would let a caller learn which guessed ids are rows that exist — and the figures carry the
  author's own words only, never the row's. `_artifact` is the whole rule, and `test_community.py` holds both
  halves: the live artifact publishes, and every other address answers `post_artifact` (404).

Every ceiling is one constant that `CAPS` publishes, that one guard below applies, and that its own refusal
prints with `held` beside `limit` — §49's rule, applied before it could recur.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import func, inspect, or_, select
from sqlalchemy.orm import Session

from app.core.db import Base
from app.core.security import new_public_id
from app.models import (
    Career,
    CommunityComment,
    CommunityFollow,
    CommunityPost,
    CommunityReaction,
    CommunityRepost,
    SimulationMatch,
    TacticBoard,
    TrainingDrill,
    User,
    VideoAsset,
    utc_today,
)


class CommunityRefusal(RuntimeError):
    """A refusal with the figures beside the sentence.

    Deliberately not `club.organizations.ClubRefusal`: the club class carries a tenant in its payload, and this
    tier has no tenant to carry — an absent post is answered by its own id and nothing else.
    """

    def __init__(self, code: str, message: str, **figures: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.figures = figures

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.figures}


#: The six kinds the spec lets a user publish, plus `note` for the words that point at nothing.
POST_KINDS: Final = ("note", "my_goal", "my_training", "my_match", "my_tactic", "my_analysis", "my_career")

#: Which page each publishing kind points at. Every value here is a route the web tier actually has, and a case
#: in the suite re-reads `apps/web/app` to hold that claim rather than trusting this literal.
POINTER_PREFIXES: Final = {
    "my_goal": "/challenges/runs/",
    "my_training": "/training/",
    "my_match": "/match/",
    "my_tactic": "/tactics/boards/",
    "my_analysis": "/video/",
    "my_career": "/career/",
}

VISIBILITIES: Final = ("public", "unlisted", "followers")
REACTIONS: Final = ("like",)

MAX_POSTS_PER_USER: Final = 500
POST_BODY_MAX: Final = 1500
POINTER_MAX: Final = 160
COMMENT_BODY_MAX: Final = 600
MAX_COMMENTS_PER_POST: Final = 200
MAX_FOLLOWING: Final = 500

#: What the derived figures on this tier's answers are made of, printed beside the figures themselves.
FORMULAS: Final = {
    "likes": "count of this post's reaction rows — one per account by constraint, so this is a number of people, not of presses",
    "comments": "count of this post's comment rows",
    "reposts": "count of this post's repost rows, none of which is the author's own",
    "following": "count of follow rows whose `follower_id` is this account",
    "followers": "count of follow rows whose `followee_id` is this account",
    "feed_total": "count of posts whose author is this account or one they follow, with `unlisted` left out",
    "post_total": "count of every post row this database holds",
}

REFUSALS: Final = (
    "no_such_post",
    "no_such_account",
    "post_kind",
    "post_body",
    "post_pointer",
    "post_artifact",
    "visibility_kind",
    "reaction_kind",
    "comment_body",
    "follow_self",
    "post_limit",
    "comment_limit",
    "following_limit",
    "repost_of_own",
)

# `no_such_account`, not `no_such_member`: §39 owns that code for "no standing in this tenant", and a community
# door has no tenant to stand in. Same status, different sentence — which is the one collision `assemble()` is
# blind to, because it only refuses a code two tiers answer *differently*.
NOT_FOUND_CODES: Final = frozenset({"no_such_post", "no_such_account", "post_artifact"})
UNPROCESSABLE_CODES: Final = frozenset(
    {
        "post_kind",
        "post_body",
        "post_pointer",
        "visibility_kind",
        "reaction_kind",
        "comment_body",
        "follow_self",
    }
)
CONFLICT_CODES: Final = frozenset({"post_limit", "comment_limit", "following_limit", "repost_of_own"})
#: 403 is the permission matrix's single meaning (§51), and this tier has no matrix: a community door asks only
#: whether the caller has a session, which `current_user` answers with a 401 before any code below can be raised.
FORBIDDEN_CODES: Final[frozenset[str]] = frozenset()

PUBLISHED: Final = REFUSALS

CAPS: Final = {
    "post_max": MAX_POSTS_PER_USER,
    "post_body_max": POST_BODY_MAX,
    "pointer_max": POINTER_MAX,
    "comment_max": MAX_COMMENTS_PER_POST,
    "comment_body_max": COMMENT_BODY_MAX,
    "following_max": MAX_FOLLOWING,
    "kinds": list(POST_KINDS),
    "reactions": list(REACTIONS),
    "visibilities": list(VISIBILITIES),
    "pointer_prefixes": dict(POINTER_PREFIXES),
    "visibility_rule": "`public` reaches a feed, `unlisted` is readable at its own address and appears in no feed, `followers` reaches its author and the accounts whose follow rows point at that author right now",
}

LIMITATION: Final = (
    "a post stores a pointer and the author's own words, and no figure about the artifact it points at: the "
    "board, plan or match behind a share is re-read where it lives, so a post can never carry a stale stat line "
    "and can never carry a child's data either. Nothing in this tier is gated on a plan — the entitlement table "
    "has no community feature today, so posting costs nothing and the ceiling is a row count, not a price"
)

COMMUNITY_TABLES: Final = (
    CommunityPost.__tablename__,
    CommunityComment.__tablename__,
    CommunityReaction.__tablename__,
    CommunityRepost.__tablename__,
    CommunityFollow.__tablename__,
)

READY_RULE: Final = (
    "`ready` is one condition: this database holds every table this tier counts. When it does not, the door "
    "still answers, every count is a zero, and the vocabulary is the tier's own — a database that has not run "
    "the migration is empty, not broken."
)


def community_tables_present(session: Session) -> bool:
    """Whether the five tables this tier counts exist — presence, not usage."""
    existing = set(inspect(session.get_bind()).get_table_names())
    return all(table in existing for table in COMMUNITY_TABLES)


def _today() -> str:
    """The project's own clock, not the host's local one: a post's day has to agree with every other row's."""
    return utc_today().isoformat()


def community_counts(session: Session, *, ready: bool) -> dict[str, int]:
    """The rulebook's counts of this tier's five tables — 0 rather than a crash when they do not exist yet."""
    if not ready:
        return {name: 0 for name in ("posts", "comments", "reactions", "reposts", "follows")}
    return {
        "posts": int(session.scalar(select(func.count()).select_from(CommunityPost)) or 0),
        "comments": int(session.scalar(select(func.count()).select_from(CommunityComment)) or 0),
        "reactions": int(session.scalar(select(func.count()).select_from(CommunityReaction)) or 0),
        "reposts": int(session.scalar(select(func.count()).select_from(CommunityRepost)) or 0),
        "follows": int(session.scalar(select(func.count()).select_from(CommunityFollow)) or 0),
    }


def _member(session: Session, ident: str) -> User:
    row = session.get(User, str(ident))
    if row is None:
        raise CommunityRefusal("no_such_account", f"no account answers to {str(ident)!r}", member=str(ident))
    return row


def _post(session: Session, ident: str) -> CommunityPost:
    row = session.get(CommunityPost, str(ident))
    if row is None:
        raise CommunityRefusal("no_such_post", f"no post answers to {str(ident)!r}", post=str(ident))
    return row


def _kind(kind: Any) -> str:
    text = str(kind or "").strip().lower()
    if text not in POST_KINDS:
        raise CommunityRefusal(
            "post_kind",
            f"a post is one of {' '.join(repr(item) for item in POST_KINDS)}; {text!r} is none of them, and an unknown kind would publish a label nothing reads",
            sent=text,
            kinds=list(POST_KINDS),
        )
    return text


def _visibility(visibility: Any) -> str:
    text = str(visibility or "").strip().lower()
    if text not in VISIBILITIES:
        raise CommunityRefusal(
            "visibility_kind",
            f"a post is {' or '.join(repr(item) for item in VISIBILITIES)}; {text!r} would select nobody and the door cannot tell that from a mistake",
            sent=text,
            visibilities=list(VISIBILITIES),
        )
    return text


def _pointer(kind: str, pointer: Any) -> str:
    """A `note` points at nothing; every publishing kind points at its own artifact, and the door checks which.

    No trimming here, unlike a body: a pointer is an address, and a row that stored something other than the
    bytes the author sent would send every reader to a different artifact than the one they meant (§50).
    """
    text = str(pointer or "")
    if kind == "note":
        if text:
            raise CommunityRefusal("post_pointer", "a `note` carries words only — a pointer belongs to a kind that names what it points at", kind=kind, pointer=text)
        return ""
    prefix = POINTER_PREFIXES[kind]
    if not text.startswith(prefix):
        raise CommunityRefusal(
            "post_pointer",
            f"a {kind!r} post points at {prefix!r} plus the artifact's own address, because that is the page this kind names; {text!r} is not one",
            kind=kind,
            expected=prefix,
            sent=text,
        )
    if len(text) > POINTER_MAX:
        raise CommunityRefusal("post_pointer", f"a pointer is at most {POINTER_MAX} characters and this one is {len(text)}", length=len(text), max=POINTER_MAX)
    if text.endswith("/") or any(character.isspace() for character in text) or "?" in text or "#" in text:
        raise CommunityRefusal("post_pointer", "a pointer is one path — no query, no fragment, no trailing slash", pointer=text)
    return text


def _artifact(session: Session, kind: str, actor_id: str, address: str) -> None:
    """The promise the pointer makes, honoured: something answers at that address, and it is the author's.

    Five kinds name rows an account owns — a challenge run and a career (`careers`), a played match
    (`sim_matches`), a drawn board (`tactic_boards`), an uploaded clip (`video_assets`) — and one names the
    project's own drill catalogue (`training_drills`), which has no owner to check and answers to every
    account. A run is a career whose window the scenario set, so `/challenges/runs/` refuses an open career
    on the same rule: it is the windowed artifact that prefix names.

    Both failures answer one code, and the code's figures are the author's own words. A sentence that told
    a guessed address apart from a row the caller does not own would be an oracle — a caller could learn
    which ids are rows that exist by which refusal came back, which is the disclosure `ownership_or_admin`
    makes with a 404 and this tier makes with the same answer. So a missing row and someone else's row are
    one sentence, and     the row's own facts (whose it is, what it is called) never travel.
    """
    if kind == "note":
        # A note points at nothing, and `_pointer` has already refused it a pointer — there is no address
        # to resolve, and an empty tail would otherwise read as a missing row in some other kind's table.
        return
    tail = address.rsplit("/", 1)[-1]
    found: Base | None = None
    if kind == "my_training":
        found = session.scalar(select(TrainingDrill).where(TrainingDrill.slug == tail))
    elif kind == "my_analysis":
        found = session.scalar(select(VideoAsset).where(VideoAsset.id == tail, VideoAsset.owner_id == actor_id))
    elif kind == "my_match":
        found = session.scalar(select(SimulationMatch).where(SimulationMatch.slug == tail, SimulationMatch.owner_id == actor_id))
    elif kind == "my_career":
        found = session.scalar(select(Career).where(Career.slug == tail, Career.owner_id == actor_id, Career.challenge_slug == ""))
    elif kind == "my_goal":
        found = session.scalar(select(Career).where(Career.slug == tail, Career.owner_id == actor_id, Career.challenge_slug != ""))
    else:
        found = session.scalar(select(TacticBoard).where(or_(TacticBoard.id == tail, TacticBoard.slug == tail), TacticBoard.owner_id == actor_id))
    if found is None:
        raise CommunityRefusal(
            "post_artifact",
            "that address answers to nothing this account may point at",
            kind=kind,
            pointer=address,
        )


def _body(body: Any, maximum: int, code: str, field: str) -> str:
    words = str(body or "").strip()
    if not words:
        raise CommunityRefusal(code, f"a {field} cannot be blank", field=field, max=maximum)
    if len(words) > maximum:
        raise CommunityRefusal(code, f"a {field} is at most {maximum} characters and this one is {len(words)}", length=len(words), max=maximum)
    return words


def author_of(session: Session, ident: str) -> dict[str, Any]:
    """The two things a post says about who wrote it. A departed account is answered as absence, not as a blank."""
    row = _member(session, ident)
    return {"id": row.id, "display_name": row.display_name}


def visible_authors(session: Session, viewer_id: str) -> list[str]:
    """The authors whose posts reach this reader: the account itself and the ones its follow rows point at."""
    return [viewer_id, *[str(followee) for followee in session.scalars(select(CommunityFollow.followee_id).where(CommunityFollow.follower_id == viewer_id))]]


def _reacted(session: Session, post_id: str, user_id: str) -> bool:
    return bool(session.scalar(select(func.count()).select_from(CommunityReaction).where(CommunityReaction.post_id == post_id, CommunityReaction.user_id == user_id)))


def measures(session: Session, row: CommunityPost) -> dict[str, int]:
    """The three figures a post publishes, each counted from the rows named in its own formula."""
    return {
        "likes": int(session.scalar(select(func.count()).select_from(CommunityReaction).where(CommunityReaction.post_id == row.id)) or 0),
        "comments": int(session.scalar(select(func.count()).select_from(CommunityComment).where(CommunityComment.post_id == row.id)) or 0),
        "reposts": int(session.scalar(select(func.count()).select_from(CommunityRepost).where(CommunityRepost.post_id == row.id)) or 0),
    }


def view(session: Session, row: CommunityPost, viewer_id: str) -> dict[str, Any]:
    """One post as one reader sees it: its figures, and whether that reader has already reacted to it."""
    return {
        **_shape(row),
        **measures(session, row),
        "author": author_of(session, row.author_id),
        "viewer_liked": bool(_reacted(session, row.id, viewer_id)),
        "formulas": dict(FORMULAS),
    }


def _shape(row: CommunityPost) -> dict[str, Any]:
    return {
        "id": row.id,
        "kind": row.kind,
        "body": row.body,
        "pointer": row.pointer,
        "visibility": row.visibility,
        "shared_on": row.shared_on,
        "has_pointer": bool(row.pointer),
    }


def create_post(session: Session, actor_id: str, *, kind: Any, body: Any, pointer: Any = "", visibility: Any = "public") -> dict[str, Any]:
    """Publish the author's own words, and the address of the thing they are sharing."""
    chosen = _kind(kind)
    words = _body(body, POST_BODY_MAX, "post_body", "post")
    seen = _visibility(visibility)
    held = int(session.scalar(select(func.count()).select_from(CommunityPost).where(CommunityPost.author_id == actor_id)) or 0)
    if held >= MAX_POSTS_PER_USER:
        raise CommunityRefusal(
            "post_limit",
            f"this account already publishes {MAX_POSTS_PER_USER} posts, which is the cap",
            held=held,
            limit=MAX_POSTS_PER_USER,
        )
    address = _pointer(chosen, pointer)
    _artifact(session, chosen, actor_id, address)
    row = CommunityPost(
        id=new_public_id("post"),
        author_id=actor_id,
        kind=chosen,
        body=words,
        pointer=address,
        visibility=seen,
        shared_on=_today(),
        data_origin="user",
        is_demo_data=False,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"post": view_for_author(session, row), "posted": True, "rule": LIMITATION}


def view_for_author(session: Session, row: CommunityPost) -> dict[str, Any]:
    return view(session, row, row.author_id)


def list_posts(session: Session, viewer_id: str, *, author: Any = None, limit: int = 20) -> dict[str, Any]:
    """A page of posts this reader may reach: somebody's wall, or the reader's own feed.

    `unlisted` is in neither listing — its own address is the only door that shows it — and a wall answers
    `followers` only to accounts that follow its author right now.
    """
    reachable = visible_authors(session, viewer_id)
    if author is None:
        statement = select(CommunityPost).where(CommunityPost.author_id.in_(reachable), CommunityPost.visibility != "unlisted")
        wall, seen = None, len(reachable)
    else:
        target = _member(session, str(author))
        own = target.id == viewer_id
        following = any(followee == target.id for followee in reachable[1:])
        allowed = list(VISIBILITIES) if own else (["public", "followers"] if (own or following) else ["public"])
        statement = select(CommunityPost).where(CommunityPost.author_id == target.id, CommunityPost.visibility.in_(allowed))
        wall, seen = target.id, None
    total = int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = list(session.scalars(statement.order_by(CommunityPost.shared_on.desc(), CommunityPost.id.desc()).limit(max(1, min(int(limit), 100)))))
    return {
        "items": [view(session, row, viewer_id) for row in rows],
        "total": total,
        "limit": int(MAX_POSTS_PER_USER),
        "wall": wall,
        "feed_authors": seen,
        "formulas": dict(FORMULAS),
        "rule": LIMITATION,
    }


def read_post(session: Session, post_id: str, viewer_id: str) -> dict[str, Any]:
    """One post at its own address, to a reader who can reach it.

    A post the reader cannot reach is answered as **absence**, not as a refusal: the answer must not tell a
    stranger that a `followers` post exists, which is §39's isolation argument carried over to a person.
    """
    row = _post(session, post_id)
    reachable = set(visible_authors(session, viewer_id))
    if row.visibility == "followers" and row.author_id not in reachable:
        raise CommunityRefusal("no_such_post", f"no post answers to {post_id!r}", post=str(post_id))
    return {**view(session, row, viewer_id), "liked_by_viewer": bool(_reacted(session, row.id, viewer_id))}


def erase_post(session: Session, post_id: str, actor_id: str) -> dict[str, Any]:
    """Erase your own post, and be told how many rows went with it.

    Somebody else's post is answered as absence, not as a refusal: this tier has no tenant matrix to consult, so
    the only distinction it can honestly draw is *reachable or not* — the same rule `read_post` applies to a
    `followers` post, and the reason one code still means one status.
    """
    row = _post(session, post_id)
    if row.author_id != actor_id:
        raise CommunityRefusal("no_such_post", f"no post of yours answers to {post_id!r}", post=str(post_id))
    gone = measures(session, row)
    session.delete(row)
    session.commit()
    return {"erased": row.id, "author_id": actor_id, **gone}


def add_comment(session: Session, post_id: str, actor_id: str, *, body: Any) -> dict[str, Any]:
    row = _post(session, post_id)
    words = _body(body, COMMENT_BODY_MAX, "comment_body", "comment")
    held = int(session.scalar(select(func.count()).select_from(CommunityComment).where(CommunityComment.post_id == row.id)) or 0)
    if held >= MAX_COMMENTS_PER_POST:
        raise CommunityRefusal("comment_limit", f"this post already holds {MAX_COMMENTS_PER_POST} comments, which is the cap", held=held, limit=MAX_COMMENTS_PER_POST)
    comment = CommunityComment(
        id=new_public_id("cmt"),
        post_id=row.id,
        author_id=actor_id,
        body=words,
        commented_on=_today(),
        data_origin="user",
        is_demo_data=False,
    )
    session.add(comment)
    session.commit()
    session.refresh(comment)
    return {
        "comment": {"id": comment.id, "body": comment.body, "author": author_of(session, actor_id), "commented_on": comment.commented_on},
        **measures(session, row),
        "formulas": dict(FORMULAS),
        "rule": "a comment is a row beside its post and stores no figure about it — the counts printed here are re-counted on every read",
    }


def list_comments(session: Session, post_id: str, *, limit: int = 50) -> dict[str, Any]:
    row = _post(session, post_id)
    held = int(session.scalar(select(func.count()).select_from(CommunityComment).where(CommunityComment.post_id == row.id)) or 0)
    rows = list(
        session.scalars(
            select(CommunityComment).where(CommunityComment.post_id == row.id).order_by(CommunityComment.commented_on.desc(), CommunityComment.id.desc()).limit(max(1, min(int(limit), 200)))
        )
    )
    return {
        "items": [{"id": item.id, "body": item.body, "author": author_of(session, item.author_id), "commented_on": item.commented_on} for item in rows],
        "total": held,
        **measures(session, row),
        "formulas": dict(FORMULAS),
    }


def react(session: Session, post_id: str, actor_id: str, *, reaction: Any = "like") -> dict[str, Any]:
    """One account's one reaction to one post. Pressing it twice is the same row, and says so."""
    row = _post(session, post_id)
    word = str(reaction or "").strip().lower()
    if word not in REACTIONS:
        raise CommunityRefusal(
            "reaction_kind", f"the only reaction this tier records is {' '.join(repr(item) for item in REACTIONS)}; {word!r} would be a feeling nothing counts", sent=word, reactions=list(REACTIONS)
        )
    already = bool(_reacted(session, row.id, actor_id))
    if not already:
        session.add(CommunityReaction(id=new_public_id("rct"), post_id=row.id, user_id=actor_id, reaction=word, reacted_on=_today(), data_origin="user", is_demo_data=False))
        session.commit()
    return {"reaction": "already recorded" if already else "recorded", "recorded_now": not already, **measures(session, row), "formulas": dict(FORMULAS)}


def repost(session: Session, post_id: str, actor_id: str) -> dict[str, Any]:
    """Carry somebody else's post to the accounts that follow you. The pointer is what travels, not a copy."""
    row = _post(session, post_id)
    if row.author_id == actor_id:
        raise CommunityRefusal(
            "repost_of_own", "a repost carries another account's post; your own words are already on your wall, and a row here would make `reposts` mean two things", post=row.id, author=row.author_id
        )
    already = int(session.scalar(select(func.count()).select_from(CommunityRepost).where(CommunityRepost.post_id == row.id, CommunityRepost.user_id == actor_id)) or 0)
    if not already:
        session.add(CommunityRepost(id=new_public_id("rps"), post_id=row.id, user_id=actor_id, reposted_on=_today(), data_origin="user", is_demo_data=False))
        session.commit()
    return {"repost": "already recorded" if already else "recorded", "recorded_now": not already, **measures(session, row), "formulas": dict(FORMULAS)}


def follow(session: Session, follower_id: str, followee_id: Any) -> dict[str, Any]:
    """The one row that decides what a reader can reach. Recomputed everywhere, stored nowhere else."""
    target = _member(session, str(followee_id))
    if target.id == follower_id:
        raise CommunityRefusal("follow_self", "an account cannot follow itself: the row would be its own audience, and `followers` would mean nobody", member=follower_id)
    held = int(session.scalar(select(func.count()).select_from(CommunityFollow).where(CommunityFollow.follower_id == follower_id)) or 0)
    if held >= MAX_FOLLOWING:
        raise CommunityRefusal("following_limit", f"this account already follows {MAX_FOLLOWING} others, which is the cap", held=held, limit=MAX_FOLLOWING)
    already = int(session.scalar(select(func.count()).select_from(CommunityFollow).where(CommunityFollow.follower_id == follower_id, CommunityFollow.followee_id == target.id)) or 0)
    if not already:
        session.add(CommunityFollow(id=new_public_id("fol"), follower_id=follower_id, followee_id=target.id, followed_on=_today(), data_origin="user", is_demo_data=False))
        session.commit()
    return {"follow": "already recorded" if already else "recorded", "recorded_now": not already, **profile(session, follower_id)}


def unfollow(session: Session, follower_id: str, followee_id: Any) -> dict[str, Any]:
    """Withdraw reach. The follow row goes, and every post that needed it leaves the feed at once."""
    target = _member(session, str(followee_id))
    row = session.scalar(select(CommunityFollow).where(CommunityFollow.follower_id == follower_id, CommunityFollow.followee_id == target.id))
    if row is None:
        # Not a refusal, and not `no_such_account` wearing another meaning: withdrawing a follow you never made
        # changes no row, which is the same answer the door gives for a second press of any other verb here.
        return {"follow": "was not followed", "removed": False, **profile(session, follower_id)}
    session.delete(row)
    session.commit()
    return {"follow": "withdrawn", "removed": True, **profile(session, follower_id)}


def profile(session: Session, ident: str) -> dict[str, Any]:
    """An account as the community sees it: its own counts, and the posts it publishes that reach whoever reads."""
    row = _member(session, ident)
    followers = int(session.scalar(select(func.count()).select_from(CommunityFollow).where(CommunityFollow.followee_id == row.id)) or 0)
    following = int(session.scalar(select(func.count()).select_from(CommunityFollow).where(CommunityFollow.follower_id == row.id)) or 0)
    posts = int(session.scalar(select(func.count()).select_from(CommunityPost).where(CommunityPost.author_id == row.id)) or 0)
    return {
        "member": {"id": row.id, "display_name": row.display_name},
        "followers": followers,
        "following": following,
        "posts": posts,
        "formulas": dict(FORMULAS),
        "rule": LIMITATION,
    }


def rules(session: Session, *, ready: bool) -> dict[str, Any]:
    """The vocabulary door: what may be published, what it costs, and what each figure on an answer means.

    `ready` has no default on purpose: the caller measures it from the tables' presence, so a door that forgot
    to would fail loudly here rather than publish a zero for a database that merely looked empty.
    """
    return {
        "ready": ready,
        "ready_rule": READY_RULE,
        "caps": dict(CAPS),
        "counts": community_counts(session, ready=ready),
        "formulas": dict(FORMULAS),
        "refusals": list(PUBLISHED),
        "limitation": LIMITATION,
    }
