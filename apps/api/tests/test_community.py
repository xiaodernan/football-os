"""§35's Community tier: a post that points at an artifact, and the rows that decide who can read it.

The claims this file defends, in the order it attacks them:

* a post stores a **pointer and words**, and no figure about the thing it shares — the column list is the
  minimisation rule, so it is asserted as a set rather than hoped for;
* every figure a reader sees (`likes`, `comments`, `reposts`, `followers`, `following`) is a `count(*)` over the
  rows its own formula names, recomputed on the read, so deleting a row moves the figure and storing one could
  not;
* a reaction, a repost and a follow are **one row per pair** — held by the unique constraint, which a case
  violates on purpose through the model rather than trusting the door to have checked;
* reach is a predicate over follows, so an `unfollowed` reader loses a `followers` post at once without anything
  being deleted, and a post they cannot reach is answered as **absence**;
* each ceiling is one constant that publishes, guards and refuses with the same number (§49), tested at its edge
  and one past it;
* a refusal code means one HTTP status, and this tier registers no 403 of its own (§51);
* and the eleven private doors are the ones this module says it declares — each is routed, each asks a caller for
  a session *before* it looks up a row, and each answers a refusal with the status the project's one table
  publishes rather than a table written beside the route.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1 import community as community_router
from app.core.db import SessionLocal
from app.main import app
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
from app.services.club import answers as project_answers
from app.services.community import posts as com

WEB_APP = Path(__file__).resolve().parents[2] / "web" / "app"


@pytest.fixture()
def session() -> Iterator[Session]:
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _user(db: Session, name: str) -> User:
    """A community actor is an account and nothing else — no tenant, no role, no consent row.

    Every call gets its own address, because the run's database persists from case to case: a fixed email would
    collide with the case that ran before it, and one actor shared across cases would make a count answer about
    two of them at once.
    """
    tag = uuid4().hex[:8]
    row = User(id=f"usr_{name}_{tag}"[:40], email=f"{name}-{tag}@community.test", password_hash="not-a-password-just-a-column", display_name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture()
def cast(session: Session) -> dict[str, User]:
    return {name: _user(session, name) for name in ("ada", "bo", "cy", "di")}


def _post(db: Session, author: User, **kwargs: Any) -> dict[str, Any]:
    return com.create_post(db, author.id, **{"kind": "note", "body": "first words", **kwargs})["post"]


def _refused(callable_: Any, code: str) -> com.CommunityRefusal:
    with pytest.raises(com.CommunityRefusal) as caught:
        callable_()
    assert caught.value.code == code, f"expected {code!r}, the door answered {caught.value.code!r}: {caught.value.message}"
    return caught.value


# ------------------------------------------------------------------ the vocabulary the door publishes


def test_the_kind_a_user_may_publish_is_the_specs_six_plus_the_note_that_points_at_nothing(cast: dict[str, User], session: Session) -> None:
    published = com.rules(session, ready=True)["caps"]
    assert published["kinds"] == ["note", "my_goal", "my_training", "my_match", "my_tactic", "my_analysis", "my_career"]
    assert set(published["pointer_prefixes"]) == set(published["kinds"]) - {"note"}


def test_every_prefix_a_kind_points_at_is_a_page_the_web_tier_actually_has() -> None:
    """A pointer is only a promise if something answers it, and the promise is held against the route tree."""
    pages = {str(path.parent.relative_to(WEB_APP)).replace("\\", "/") for path in WEB_APP.rglob("page.tsx")}
    for kind, prefix in com.POINTER_PREFIXES.items():
        owner = [segment for segment in prefix.strip("/").split("/") if segment]
        # A prefix is a directory, and the page that answers it lives at or below it — `/challenges/runs/` is
        # kept by `challenges/runs/[slug]`, so the comparison is a leading-segment match, not an equality.
        matches = [candidate for candidate in pages if candidate.split("/")[: len(owner)] == owner]
        assert matches, f"{kind} promises {prefix!r} and no page directory answers it"


def test_an_unpublished_kind_is_refused_naming_the_ones_that_exist(cast: dict[str, User], session: Session) -> None:
    error = _refused(lambda: com.create_post(session, cast["ada"].id, kind="my_secret", body="x"), "post_kind")
    assert error.figures["kinds"] == list(com.POST_KINDS)


def test_a_post_that_is_not_a_note_must_point_at_its_own_kind(cast: dict[str, User], session: Session) -> None:
    _refused(lambda: com.create_post(session, cast["ada"].id, kind="my_tactic", body="my press"), "post_pointer")
    wrong = _refused(lambda: com.create_post(session, cast["ada"].id, kind="my_tactic", body="my press", pointer="/training/plan-1"), "post_pointer")
    assert wrong.figures["expected"] == "/tactics/boards/"
    board = _board(session, cast["ada"], f"press-high-{uuid4().hex[:8]}")
    shared = _post(session, cast["ada"], kind="my_tactic", pointer=f"/tactics/boards/{board.slug}")
    assert shared["pointer"] == f"/tactics/boards/{board.slug}" and shared["has_pointer"] is True


def test_a_note_carries_words_and_refuses_a_pointer_it_could_not_explain(cast: dict[str, User], session: Session) -> None:
    plain = _post(session, cast["ada"])
    assert plain["kind"] == "note" and plain["pointer"] == "" and plain["has_pointer"] is False
    _refused(lambda: com.create_post(session, cast["ada"].id, kind="note", body="x", pointer="/career/slug"), "post_pointer")


def test_a_pointer_is_one_path_not_a_query(cast: dict[str, User], session: Session) -> None:
    for pointer in ("/career/a?b=1", "/career/#x", "/career/a ", "/career/slug/"):
        # Bound as a default so the lambda holds *this* iteration's pointer rather than whatever the loop
        # variable ends up being by the time the call runs.
        _refused(lambda sent=pointer: com.create_post(session, cast["ada"].id, kind="my_career", body="x", pointer=sent), "post_pointer")


# ------------------------------------------- a pointer is a promise, and the artifact answers for it


def _board(session: Session, owner: User, slug: str) -> TacticBoard:
    row = TacticBoard(id=f"tac_{slug}"[:40], owner_id=owner.id, slug=slug, name=slug.replace("-", " "))
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _clip(session: Session, owner: User, ident: str) -> VideoAsset:
    row = VideoAsset(id=ident[:40], owner_id=owner.id, storage_key=f"videos/{ident}", content_type="video/mp4")
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _match(session: Session, owner: User, slug: str) -> SimulationMatch:
    row = SimulationMatch(id=f"sim_{slug}"[:40], owner_id=owner.id, slug=slug, model_version="pointer-promise")
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _career_for(session: Session, owner: User, slug: str, *, run: bool = False) -> Career:
    """A career, or a challenge run — which is a career whose window the scenario set."""
    row = Career(id=f"car_{slug}"[:40], slug=slug, owner_id=owner.id, challenge_slug="window-test" if run else "")
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _drill(session: Session, slug: str) -> TrainingDrill:
    row = TrainingDrill(
        id=f"drill_{slug}"[:40],
        slug=slug,
        title=slug.replace("-", " "),
        category="pressing",
        objective="hold the first line",
        setup="two gates, four cones, one ball",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


#: The address each kind publishes with, built per call: the run's database persists from case to case, so a
#: second call re-using one tag would collide on the unique slugs the artifacts hold.


def _live_pointers(session: Session, owner: User) -> dict[str, str]:
    """One live artifact per kind, owned by `owner`, each with its own address."""
    tag = uuid4().hex[:8]
    drill = _drill(session, f"press-{tag}")
    match = _match(session, owner, f"braeford-press-{tag}")
    board = _board(session, owner, f"my-press-{tag}")
    clip = _clip(session, owner, f"vid_{tag}")
    career = _career_for(session, owner, f"ada-career-{tag}")
    run = _career_for(session, owner, f"ada-run-{tag}", run=True)
    return {
        "my_training": f"/training/{drill.slug}",
        "my_match": f"/match/{match.slug}",
        "my_tactic": f"/tactics/boards/{board.slug}",
        "my_analysis": f"/video/{clip.id}",
        "my_career": f"/career/{career.slug}",
        "my_goal": f"/challenges/runs/{run.slug}",
    }


def test_a_pointer_publishes_only_when_its_artifact_answers_for_it(cast: dict[str, User], session: Session) -> None:
    """Every kind's address resolves to a row: five the author owns, one the project authored."""
    ada = cast["ada"]
    for kind, pointer in _live_pointers(session, ada).items():
        published = _post(session, ada, kind=kind, body=f"sharing {kind}", pointer=pointer)
        assert published["pointer"] == pointer and published["has_pointer"] is True, f"{kind} published nothing at its own address"


def test_a_pointer_to_an_address_nothing_answers_is_refused(cast: dict[str, User], session: Session) -> None:
    """The wall's own claim: a pointer is a promise. An address with no row behind it is not one."""
    ada = cast["ada"]
    for kind, pointer in {
        "my_training": "/training/no-such-drill",
        "my_match": "/match/no-such-match",
        "my_tactic": "/tactics/boards/no-such-board",
        "my_analysis": "/video/vid_nothing_here",
        "my_career": "/career/no-such-career",
        "my_goal": "/challenges/runs/no-such-run",
    }.items():
        _refused(lambda sent=pointer, which=kind: com.create_post(session, ada.id, kind=which, body="x", pointer=sent), "post_artifact")


def test_a_run_is_a_career_with_a_window_and_a_point_at_an_open_career_is_refused(cast: dict[str, User], session: Session) -> None:
    """`/challenges/runs/` names the windowed kind; an open career is a different artifact and a different prefix."""
    ada = cast["ada"]
    open_career = _career_for(session, ada, f"open-not-a-run-{uuid4().hex[:8]}")
    _refused(lambda: com.create_post(session, ada.id, kind="my_goal", body="x", pointer=f"/challenges/runs/{open_career.slug}"), "post_artifact")
    posted = _post(session, ada, kind="my_career", body="my season", pointer=f"/career/{open_career.slug}")
    assert posted["pointer"] == f"/career/{open_career.slug}"


def test_a_pointer_to_another_accounts_artifact_answers_exactly_as_nothing_does(cast: dict[str, User], session: Session) -> None:
    """One answer for a guessed id and for a row the caller does not own, and the answer names no row.

    A sentence that told the two apart would be an oracle — a caller could learn which guessed ids are
    rows that exist, which is the disclosure `ownership_or_admin` refuses by answering 404. So the figures
    are the author's own words: the kind, and the address they sent. This is §35's "artifacts that are
    the author's own to share" held by the door rather than asserted in a paragraph.
    """
    ada, bo = cast["ada"], cast["bo"]
    tag = uuid4().hex[:8]
    owned = {
        "my_match": f"/match/{_match(session, ada, f'ada-match-{tag}').slug}",
        "my_tactic": f"/tactics/boards/{_board(session, ada, f'ada-board-{tag}').slug}",
        "my_analysis": f"/video/{_clip(session, ada, f'vid_ada_only_{tag}').id}",
        "my_career": f"/career/{_career_for(session, ada, f'ada-season-{tag}').slug}",
        "my_goal": f"/challenges/runs/{_career_for(session, ada, f'ada-window-{tag}', run=True).slug}",
    }
    for kind, pointer in owned.items():
        error = _refused(lambda sent=pointer, which=kind: com.create_post(session, bo.id, kind=which, body="x", pointer=sent), "post_artifact")
        assert set(error.figures) == {"kind", "pointer"}, f"{kind} named facts about a row it did not reach: {sorted(error.figures)}"
        assert error.figures["pointer"] == pointer


def test_a_pointer_a_drill_a_board_and_a_clip_answer_from_their_own_table(cast: dict[str, User], session: Session) -> None:
    """Each resolver reads its own table, so a tail from the right prefix and the wrong table is refused on the same rule."""
    ada = cast["ada"]
    tag = uuid4().hex[:8]
    board = _board(session, ada, f"wrong-table-board-{tag}")
    match = _match(session, ada, f"wrong-table-match-{tag}")
    _refused(lambda: com.create_post(session, ada.id, kind="my_training", body="x", pointer=f"/training/{board.slug}"), "post_artifact")
    _refused(lambda: com.create_post(session, ada.id, kind="my_tactic", body="x", pointer=f"/tactics/boards/{match.slug}"), "post_artifact")
    own = _post(session, ada, kind="my_tactic", body="the real one", pointer=f"/tactics/boards/{board.slug}")
    assert own["pointer"] == f"/tactics/boards/{board.slug}"


# ------------------------------------------------------------------ a post stores no figure


def test_the_columns_a_post_stores_are_the_minimisation_rule(cast: dict[str, User], session: Session) -> None:
    """No column here could hold a count, a recipient or a copy of something else's numbers."""
    held = {str(column.name) for column in CommunityPost.__table__.columns}
    assert held == {"id", "author_id", "kind", "body", "pointer", "visibility", "shared_on", "data_origin", "is_demo_data", "created_at", "updated_at"}
    assert not held & {"likes", "comments", "reposts", "recipient", "user_id", "to_user"}


def test_no_answer_in_this_tier_carries_a_recipient_shaped_key(cast: dict[str, User], session: Session) -> None:
    post = _post(session, cast["ada"])
    com.react(session, post["id"], cast["bo"].id)
    answers = [com.rules(session), com.list_posts(session, cast["ada"].id), com.read_post(session, post["id"], cast["bo"].id), com.profile(session, cast["ada"].id)]

    def names(node: Any) -> set[str]:
        if isinstance(node, dict):
            return set(node) | {found for value in node.values() for found in names(value)}
        if isinstance(node, list):
            return {found for value in node for found in names(value)}
        return set()

    forbidden = {"recipient", "recipients", "to_user", "user_ids", "readers", "reader_ids", "child_id"}
    for answer in answers:
        assert not names(answer) & forbidden, f"{sorted(names(answer) & forbidden)} names a person this tier has no business storing"


# ------------------------------------------------------------------ ceilings, at their edge and past it


def test_the_post_ceiling_accepted_at_its_edge_is_refused_one_past_it_with_its_own_figures(cast: dict[str, User], session: Session) -> None:
    ada = cast["ada"]
    held = int(session.query(CommunityPost).filter_by(author_id=ada.id).count())
    for _ in range(com.MAX_POSTS_PER_USER - held - 1):
        session.add(CommunityPost(id=com.new_public_id("post"), author_id=ada.id, kind="note", body="filler", visibility="public", shared_on=utc_today().isoformat()))
    session.commit()
    edge = _post(session, ada)
    assert com.list_posts(session, ada.id)["total"] == com.MAX_POSTS_PER_USER, f"the ceiling has to be reachable, and {edge['id']} is the row that fills it"
    error = _refused(lambda: com.create_post(session, ada.id, kind="note", body="one too many"), "post_limit")
    assert error.figures == {"held": com.MAX_POSTS_PER_USER, "limit": com.MAX_POSTS_PER_USER}
    assert int(session.query(CommunityPost).filter_by(author_id=ada.id).count()) == com.MAX_POSTS_PER_USER, "a refusal that also wrote would be a lie about the cap"


def test_the_comment_ceiling_and_the_following_ceiling_each_refuse_with_the_number_they_publish(cast: dict[str, User], session: Session) -> None:
    post = _post(session, cast["ada"])
    for _ in range(com.MAX_COMMENTS_PER_POST):
        session.add(CommunityComment(id=com.new_public_id("cmt"), post_id=post["id"], author_id=cast["bo"].id, body="filler", commented_on=utc_today().isoformat()))
    session.commit()
    error = _refused(lambda: com.add_comment(session, post["id"], cast["cy"].id, body="late"), "comment_limit")
    assert error.figures == {"held": com.MAX_COMMENTS_PER_POST, "limit": com.MAX_COMMENTS_PER_POST}

    ada = cast["ada"]
    others = [_user(session, f"followable-{index}") for index in range(com.MAX_FOLLOWING - 1)]
    for target in others:
        com.follow(session, ada.id, target.id)
    com.follow(session, ada.id, cast["bo"].id)
    refused = _refused(lambda: com.follow(session, ada.id, cast["cy"].id), "following_limit")
    assert refused.figures == {"held": com.MAX_FOLLOWING, "limit": com.MAX_FOLLOWING}


@pytest.mark.parametrize(
    ("verb", "code"),
    [("blank", "post_body"), ("long", "post_body"), ("visibility", "visibility_kind"), ("reaction", "reaction_kind")],
)
def test_a_body_or_a_word_the_door_does_not_know_is_a_422_shape_not_a_default(cast: dict[str, User], session: Session, verb: str, code: str) -> None:
    ada = cast["ada"]
    if verb == "blank":
        _refused(lambda: com.create_post(session, ada.id, kind="note", body="   "), code)
    elif verb == "long":
        _refused(lambda: com.create_post(session, ada.id, kind="note", body="x" * (com.POST_BODY_MAX + 1)), code)
    elif verb == "visibility":
        error = _refused(lambda: com.create_post(session, ada.id, kind="note", body="x", visibility="nobody"), code)
        assert error.figures["visibilities"] == list(com.VISIBILITIES)
    else:
        post = _post(session, ada)
        error = _refused(lambda: com.react(session, post["id"], ada.id, reaction="pity"), code)
        assert error.figures["reactions"] == list(com.REACTIONS)


def test_a_body_exactly_at_the_published_maximum_is_accepted(cast: dict[str, User], session: Session) -> None:
    edge = _post(session, cast["ada"], body="x" * com.POST_BODY_MAX)
    assert len(edge["body"]) == com.POST_BODY_MAX


# ------------------------------------------------------------------ one row per pair, by constraint


def test_pressing_a_reaction_twice_is_one_row_and_the_second_answer_says_so(cast: dict[str, User], session: Session) -> None:
    post = _post(session, cast["ada"])
    first = com.react(session, post["id"], cast["bo"].id)
    second = com.react(session, post["id"], cast["bo"].id)
    assert first["recorded_now"] is True and second["recorded_now"] is False
    assert second["reaction"] == "already recorded"
    assert first["likes"] == second["likes"] == int(session.query(CommunityReaction).filter_by(post_id=post["id"]).count()) == 1


def test_the_unique_constraint_is_what_makes_a_second_reaction_impossible(cast: dict[str, User], session: Session) -> None:
    """The door's check is convenient; the index is the guarantee. This case bypasses the door on purpose."""
    post = _post(session, cast["ada"])
    session.add(CommunityReaction(id=com.new_public_id("rct"), post_id=post["id"], user_id=cast["bo"].id, reaction="like", reacted_on=utc_today().isoformat()))
    session.commit()
    session.add(CommunityReaction(id=com.new_public_id("rct"), post_id=post["id"], user_id=cast["bo"].id, reaction="like", reacted_on=utc_today().isoformat()))
    _expect_integrity(session)


def test_the_follow_and_repost_constraints_each_hold_their_own_pair(cast: dict[str, User], session: Session) -> None:
    post = _post(session, cast["ada"])
    session.add(CommunityRepost(id=com.new_public_id("rps"), post_id=post["id"], user_id=cast["bo"].id, reposted_on=utc_today().isoformat()))
    session.commit()
    session.add(CommunityRepost(id=com.new_public_id("rps"), post_id=post["id"], user_id=cast["bo"].id, reposted_on=utc_today().isoformat()))
    _expect_integrity(session)

    session.add(CommunityFollow(id=com.new_public_id("fol"), follower_id=cast["cy"].id, followee_id=cast["di"].id, followed_on=utc_today().isoformat()))
    session.commit()
    session.add(CommunityFollow(id=com.new_public_id("fol"), follower_id=cast["cy"].id, followee_id=cast["di"].id, followed_on=utc_today().isoformat()))
    _expect_integrity(session)


def _expect_integrity(session: Session) -> None:
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_an_account_cannot_follow_itself_and_a_repost_of_your_own_words_is_not_a_repost(cast: dict[str, User], session: Session) -> None:
    ada = cast["ada"]
    _refused(lambda: com.follow(session, ada.id, ada.id), "follow_self")
    post = _post(session, ada)
    refused = _refused(lambda: com.repost(session, post["id"], ada.id), "repost_of_own")
    assert refused.figures["author"] == ada.id
    carried = com.repost(session, post["id"], cast["bo"].id)
    assert carried["recorded_now"] is True and carried["reposts"] == 1
    again = com.repost(session, post["id"], cast["bo"].id)
    assert again["recorded_now"] is False and again["reposts"] == 1


# ------------------------------------------------------------------ reach is arithmetic, not a stored list


def test_a_followers_post_reaches_a_follower_and_answers_absence_to_everybody_else(cast: dict[str, User], session: Session) -> None:
    ada, bo, cy = cast["ada"], cast["bo"], cast["cy"]
    secret = _post(session, ada, visibility="followers")
    assert com.list_posts(session, bo.id, author=ada.id)["total"] == 0, "a stranger must not even be told a wall holds this"
    refused = _refused(lambda: com.read_post(session, secret["id"], cy.id), "no_such_post")
    assert refused.figures["post"] == secret["id"]

    com.follow(session, bo.id, ada.id)
    assert com.read_post(session, secret["id"], bo.id)["id"] == secret["id"]
    assert [item["id"] for item in com.list_posts(session, bo.id, author=ada.id)["items"]] == [secret["id"]]

    com.unfollow(session, bo.id, ada.id)
    assert com.list_posts(session, bo.id, author=ada.id)["total"] == 0, "an unfollow has to withdraw reach, not annotate it"
    # Counted over *this* actor's follows: the run's database carries the following-ceiling case's rows too, and
    # a whole-table count would be a claim about both cases at once.
    assert int(session.query(CommunityFollow).filter(CommunityFollow.follower_id == bo.id).count()) == 0, "and it withdraws by removing the row it owned"


def test_an_unlisted_post_is_readable_at_its_address_and_appears_in_no_listing(cast: dict[str, User], session: Session) -> None:
    ada, bo = cast["ada"], cast["bo"]
    hidden = _post(session, ada, visibility="unlisted")
    com.follow(session, bo.id, ada.id)
    assert [item["id"] for item in com.list_posts(session, ada.id)["items"]] == []
    assert [item["id"] for item in com.list_posts(session, bo.id)["items"]] == [], "a feed carries public and followers posts only"
    assert com.read_post(session, hidden["id"], bo.id)["id"] == hidden["id"]
    assert [item["id"] for item in com.list_posts(session, ada.id, author=ada.id)["items"]] == [hidden["id"]], "an author's own wall is not hidden from them"


def test_a_feed_is_the_authors_a_reader_follows_plus_themself_recounted_every_read(cast: dict[str, User], session: Session) -> None:
    ada, bo, cy = cast["ada"], cast["bo"], cast["cy"]
    mine = _post(session, ada)
    theirs = _post(session, bo)
    _post(session, cy)
    feed = com.list_posts(session, ada.id)
    assert [item["id"] for item in feed["items"]] == [mine["id"]], "the reader themself is the only author before a follow"
    assert feed["feed_authors"] == 1

    com.follow(session, ada.id, bo.id)
    after = com.list_posts(session, ada.id)
    assert sorted(item["id"] for item in after["items"]) == sorted([mine["id"], theirs["id"]])
    assert after["feed_authors"] == 2 == after["total"]

    com.unfollow(session, ada.id, bo.id)
    assert com.list_posts(session, ada.id)["total"] == 1


def test_the_figures_beside_a_post_are_counted_from_the_rows_and_drop_when_one_goes(cast: dict[str, User], session: Session) -> None:
    ada, bo, cy = cast["ada"], cast["bo"], cast["cy"]
    post = _post(session, ada)
    com.react(session, post["id"], bo.id)
    com.react(session, post["id"], cy.id)
    com.add_comment(session, post["id"], bo.id, body="agreed")
    seen = com.read_post(session, post["id"], ada.id)
    assert seen["likes"] == 2 and seen["comments"] == 1 and seen["reposts"] == 0
    # The viewer's own reaction, not anybody's: ada wrote the post and never liked it, bo did.
    assert com.read_post(session, post["id"], bo.id)["liked_by_viewer"] is True
    assert com.read_post(session, post["id"], cast["di"].id)["liked_by_viewer"] is False
    assert seen["liked_by_viewer"] is False, "authorship is not a reaction, and the two figures are not the same one"

    session.query(CommunityReaction).filter_by(post_id=post["id"], user_id=bo.id).delete()
    session.commit()
    assert com.read_post(session, post["id"], ada.id)["likes"] == 1, "a stored count would still be insisting two people read this"


def test_a_profile_counts_both_sides_of_a_follow_and_its_own_post_rows(cast: dict[str, User], session: Session) -> None:
    ada, bo, cy = cast["ada"], cast["bo"], cast["cy"]
    com.follow(session, bo.id, ada.id)
    com.follow(session, cy.id, ada.id)
    com.follow(session, ada.id, bo.id)
    _post(session, ada)
    _post(session, ada, body="second")
    profile = com.profile(session, ada.id)
    assert profile["followers"] == 2 and profile["following"] == 1 and profile["posts"] == 2
    assert profile["formulas"]["followers"] == com.FORMULAS["followers"]
    withdrawing = com.unfollow(session, cy.id, ada.id)
    assert withdrawing["removed"] is True and com.profile(session, ada.id)["followers"] == 1
    again = com.unfollow(session, cy.id, ada.id)
    assert again["removed"] is False and again["follow"] == "was not followed"


# ------------------------------------------------------------------ absence, answers and the status table


def test_an_absent_post_or_account_is_answered_as_absence_by_its_own_address(cast: dict[str, User], session: Session) -> None:
    _refused(lambda: com.read_post(session, "post_never_written", cast["ada"].id), "no_such_post")
    _refused(lambda: com.add_comment(session, "post_never_written", cast["ada"].id, body="x"), "no_such_post")
    _refused(lambda: com.profile(session, "usr_never_here"), "no_such_account")


def test_every_code_this_tier_answers_with_means_exactly_one_status_in_the_shipped_table(cast: dict[str, User]) -> None:
    """Read off the object the doors answer from, not off a table assembled by hand for this case.

    An earlier draft called `assemble(club, com)` here, which would have kept passing if the community tier were
    never appended to `TIERS` — the subset assembled for the test would agree while the shipped door fell through
    to a 400 for every code in it.
    """
    table = project_answers.ANSWERS
    assert com in project_answers.TIERS, "the tier is not registered, so its own door would answer every code with a 400"
    assert set(com.REFUSALS) <= set(table)
    for code in com.REFUSALS:
        expected = 404 if code in com.NOT_FOUND_CODES else 422 if code in com.UNPROCESSABLE_CODES else 409 if code in com.CONFLICT_CODES else None
        assert expected is not None, f"{code} is published but in no set, so its status would be a fall-through"
        assert table[code] == expected
    assert not com.FORBIDDEN_CODES, "403 is the permission matrix's meaning and this tier has no matrix"
    assert len(com.REFUSALS) == len(set(com.REFUSALS))


def test_no_other_tier_publishes_a_code_this_tier_publishes() -> None:
    """One code, one *meaning* — and `assemble()` cannot see it when two tiers agree on the status.

    This case exists because the first draft of the community tier registered `no_such_member`, which §39 already
    owned for "no standing in this tenant". Both answered 404, so the collision check stayed silent and the two
    sentences would have shipped behind one word. The check is over `answers.TIERS` rather than a list of modules
    written here, so the next tier to join is measured too.
    """
    for tier in project_answers.TIERS:
        if tier is com:
            continue
        name = tier.__name__.rpartition(".")[2]
        held = set(getattr(tier, "PUBLISHED", getattr(tier, "REFUSALS", ())) or ())
        shared = held & set(com.REFUSALS)
        assert not shared, f"{sorted(shared)} is {name}'s sentence and this tier's; one code cannot mean two things"


def test_the_tier_counts_its_own_tables_without_reading_a_missing_one(session: Session) -> None:
    held = com.community_counts(session, ready=True)
    assert set(held) == {"posts", "comments", "reactions", "reposts", "follows"}
    assert all(value >= 0 for value in held.values())
    assert com.community_counts(session, ready=False) == {name: 0 for name in held}


# ------------------------------------------------------------------ the doors


PASSWORD = "strong-pass-1234"

#: The public surface, named once so a door added later is a private door until this line says otherwise.
PUBLIC_DOORS = frozenset({"/community/rules"})


def _account(name: str) -> TestClient:
    """Its own client with its own registered account — a community is made of accounts, so a door needs two."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"community-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": name, "role": "player", "accepts_data_policy": True},
    )
    assert response.status_code == 201, response.text
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


def _id_of(client: TestClient) -> str:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


def _detail(response: Any) -> Any:
    body = response.json()["detail"]
    assert isinstance(body, dict), f"a refusal must answer with the tier's own payload and figures, and this door sent {body!r}"
    return body


@pytest.fixture()
def voices() -> dict[str, TestClient]:
    """A fresh pair of accounts per case: the feed and follower counts these cases assert are exact, and an account
    shared across cases would make each figure a claim about two of them at once."""
    return {"ada": _account("Ada Wall"), "bo": _account("Bo Reader")}


def _live_doors() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        path = str(getattr(route, "path", ""))
        if not path.startswith("/api/v1/community"):
            continue
        for method in set(getattr(route, "methods", ()) or ()) - {"HEAD", "OPTIONS"}:
            routes.add((method, path))
    return routes


def test_the_guide_names_exactly_the_doors_that_are_routed() -> None:
    """Both directions, because a guide is read by the page that has to reach the doors.

    An entry with no route is a link to a 404; a route with no entry is a door the rulebook does not publish, and
    `GET /community/rules` prints this list to the browser as the tier's own description of itself.
    """
    declared = {(entry["method"], f"/api/v1{entry['path']}") for entry in community_router.ROUTE_GUIDE}
    assert len(community_router.ROUTE_GUIDE) == len(declared), "two entries describe one door"
    live = _live_doors()
    assert declared == live, f"only in the guide: {sorted(declared - live)}; only routed: {sorted(live - declared)}"


def test_this_door_reads_the_same_object_the_club_doors_read() -> None:
    assert community_router._ANSWERS is project_answers.ANSWERS, "the community door assembled its own answer table again"


def test_the_one_public_door_prints_the_answers_it_will_give() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/community/rules")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["routes"] == [dict(item) for item in community_router.ROUTE_GUIDE]
    assert body["refusal_answers"] == {code: project_answers.ANSWERS[code] for code in com.REFUSALS}, "the rulebook printed a status the shipped table does not answer with"
    assert body["caps"]["kinds"] == list(com.POST_KINDS)
    # The three ceilings are a row count a caller cannot reach through HTTP in a test's budget; what a page can
    # check is that they are published with the status they earn, which the line above holds for all thirteen.
    assert all(body["refusal_answers"][code] == 409 for code in ("post_limit", "comment_limit", "following_limit"))
    assert set(body["counts"]) == {"posts", "comments", "reactions", "reposts", "follows"}


@pytest.mark.parametrize("door", [entry for entry in community_router.ROUTE_GUIDE if entry["path"] not in PUBLIC_DOORS], ids=lambda entry: f"{entry['method']} {entry['path']}")
def test_a_caller_without_a_session_is_answered_401_before_any_row_is_consulted(door: dict[str, str]) -> None:
    """401 for an id that does not exist is the point: a 404 would mean the service ran first.

    Every private door is walked, derived from the guide rather than a list written here, so a door added to the
    router cannot arrive unguarded — and none of them answers 403, which §51 reserves for the permission matrix.
    """
    path = door["path"].replace("{post}", "post_never_written").replace("{member}", "usr_never_here")
    client = TestClient(app)
    response = client.request(door["method"], f"/api/v1{path}", json={} if door["method"] == "POST" else None)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"{door['method']} {path} answered {response.status_code}: {response.text}"
    assert _detail(response)["code"] == "unauthenticated"


def test_every_code_a_door_can_refuse_with_is_answered_with_the_status_the_table_publishes(voices: dict[str, TestClient]) -> None:
    ada, bo = voices["ada"], voices["bo"]
    ada_id = _id_of(ada)
    theirs = ada.post("/api/v1/community/posts", json={"body": "a wall of one"}).json()["post"]["id"]

    earned = [
        ("post_kind", ada.post("/api/v1/community/posts", json={"kind": "my_secret", "body": "x"})),
        ("post_body", ada.post("/api/v1/community/posts", json={"body": "   "})),
        ("post_pointer", ada.post("/api/v1/community/posts", json={"kind": "my_tactic", "body": "press", "pointer": "/training/plan-1"})),
        ("visibility_kind", ada.post("/api/v1/community/posts", json={"body": "x", "visibility": "nobody"})),
        ("no_such_post", ada.get("/api/v1/community/posts/post_never_written")),
        ("no_such_account", ada.get("/api/v1/community/members/usr_never_here")),
        ("follow_self", ada.post(f"/api/v1/community/follows/{ada_id}")),
        ("repost_of_own", ada.post(f"/api/v1/community/posts/{theirs}/reposts")),
        ("reaction_kind", bo.post(f"/api/v1/community/posts/{theirs}/reactions", json={"reaction": "pity"})),
        ("comment_body", bo.post(f"/api/v1/community/posts/{theirs}/comments", json={"body": "   "})),
    ]
    for code, response in earned:
        published = project_answers.ANSWERS[code]
        assert response.status_code == published, f"{code} is published as {published} and the door answered {response.status_code}: {response.text}"
        assert _detail(response)["code"] == code, f"the door answered {published} for the wrong reason: {_detail(response)}"


def test_following_through_a_door_is_what_opens_a_followers_post_to_that_reader(voices: dict[str, TestClient]) -> None:
    """The wiring, not the arithmetic: the door has to pass the *caller* as the reader and the path as the other half."""
    ada, bo = voices["ada"], voices["bo"]
    bo_id = _id_of(bo)
    secret = bo.post("/api/v1/community/posts", json={"body": "only for the people who follow me", "visibility": "followers"}).json()["post"]["id"]

    closed = ada.get(f"/api/v1/community/posts/{secret}")
    assert closed.status_code == 404 and _detail(closed)["code"] == "no_such_post", "a wall the reader cannot reach is answered as absence, not as a refusal"
    assert ada.get("/api/v1/community/posts").json()["total"] == 0

    opened = ada.post(f"/api/v1/community/follows/{bo_id}")
    assert opened.status_code == 200, opened.text
    assert opened.json()["recorded_now"] is True
    assert ada.get(f"/api/v1/community/posts/{secret}").json()["id"] == secret
    assert ada.get("/api/v1/community/posts").json()["total"] == 1, "the feed carries the author it now follows"
    # Bo is an account this case created, so every follow row pointing at it is this case's row.
    assert ada.get(f"/api/v1/community/members/{bo_id}").json()["followers"] == 1

    withdrawn = ada.delete(f"/api/v1/community/follows/{bo_id}")
    assert withdrawn.status_code == 200 and withdrawn.json()["removed"] is True
    assert ada.get(f"/api/v1/community/posts/{secret}").status_code == 404, "reach is recomputed on the read, so withdrawing it is instant"
    assert int(_row_count(CommunityPost, CommunityPost.id == secret)) == 1, "and it deletes nothing that was already published"


def test_the_erase_door_takes_the_rows_on_your_own_post_down_and_answers_absence_for_everybody_else(voices: dict[str, TestClient], session: Session) -> None:
    ada, bo = voices["ada"], voices["bo"]
    tag = uuid4().hex[:8]
    owner = session.get(User, _id_of(ada))
    assert owner is not None, "the voice fixture registered the account this door runs as"
    career = _career_for(session, owner, f"erase-me-{tag}")
    post = ada.post("/api/v1/community/posts", json={"body": "here briefly", "kind": "my_career", "pointer": f"/career/{career.slug}"}).json()["post"]["id"]
    bo.post(f"/api/v1/community/posts/{post}/reactions", json={"reaction": "like"})
    bo.post(f"/api/v1/community/posts/{post}/comments", json={"body": "noted"})
    bo.post(f"/api/v1/community/posts/{post}/reposts")

    stranger = bo.delete(f"/api/v1/community/posts/{post}")
    assert stranger.status_code == 404 and _detail(stranger)["code"] == "no_such_post", "a post that is not yours is not confirmed to exist"
    assert int(_row_count(CommunityPost, CommunityPost.id == post)) == 1, "and the refusal wrote nothing"

    erased = ada.delete(f"/api/v1/community/posts/{post}")
    assert erased.status_code == 200, erased.text
    assert erased.json() == {"erased": post, "author_id": _id_of(ada), "likes": 1, "comments": 1, "reposts": 1}, "the answer says how many rows went with the post"

    assert ada.get(f"/api/v1/community/posts/{post}").status_code == 404
    for model, label in ((CommunityReaction, "reaction"), (CommunityComment, "comment"), (CommunityRepost, "repost")):
        assert int(_row_count(model, model.post_id == post)) == 0, f"the {label} row outlived the post it was about"


def _row_count(model: Any, *conditions: Any) -> int:
    """Counted on its own session: the door's session is not the one the case holds."""
    row = SessionLocal()
    try:
        return int(row.query(model).filter(*conditions).count())
    finally:
        row.close()
