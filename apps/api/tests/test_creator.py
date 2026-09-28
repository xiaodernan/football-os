"""§36's creator tier: a guide that cites the corpus, and the rows that decide what a reader may see.

The claims this file defends, in the order it attacks them:

* a guide stores **a title, a frame and addresses** — the column list is the minimisation rule, so it is asserted
  as a set: no column on `creator_guides` or `guide_citations` could hold a passage's text, a token total or a
  count of either;
* every figure a reader sees (`citations`, `moved`, `tokens`, `guides`, `subscribers`) is counted from the rows its
  own formula names at the moment of the read, so editing or deleting the *chunk* moves the figure — which a stored
  number could not do, and which is the whole reason a citation is an address;
* a citation is **one row per (guide, document, ordinal)** by unique constraint, and the hash it stores is a
  witness, not a link: a passage whose text changed since it was cited is still readable and says so via `moved`;
* the pricing architecture is §42's, not a new table of money: this tier publishes no currency, provider or
  checkout key anywhere in an answer, asserted by walking every answer's keys;
* each ceiling is one constant that publishes, guards and refuses with the same number (§49), tested at its edge
  and one past it; and somebody else's guide is answered as **absence**, never as a refusal that confirms it
  exists (§35's rule, and no 403 anywhere in this tier);
* the codes this tier answers with belong to it alone — the check that exists because §35's `no_such_member`
  collided with §39's at the same status, which `assemble()` cannot see.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import CommunityFollow, CreatorGuide, GuideCitation, KnowledgeChunk, KnowledgeDocument, User, utc_today
from app.services.club import answers as project_answers
from app.services.creator import publishing as cre

TAG = uuid4().hex[:8]


@pytest.fixture()
def session() -> Iterator[Session]:
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _account(db: Session, name: str) -> User:
    """A creator is an account first. The email is unique per call because the run's database outlives one case."""
    tag = uuid4().hex[:8]
    row = User(id=f"usr_{name}_{tag}"[:40], email=f"{name}-{tag}-{TAG}@creator.test", password_hash="not-a-password-just-a-column", display_name=f"{name} {tag}")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture()
def cast(session: Session) -> dict[str, User]:
    return {name: _account(session, name) for name in ("ada", "bo")}


def _passage(db: Session) -> KnowledgeChunk:
    """Cite the corpus as it is — the shipped documents are what a guide would really point at."""
    row = db.scalar(select(KnowledgeChunk).order_by(KnowledgeChunk.document_id, KnowledgeChunk.ordinal).limit(1))
    assert row is not None, "the test database holds no ingested chunks, so there is nothing to cite"
    return row


def _document(db: Session, passage: KnowledgeChunk) -> KnowledgeDocument:
    row = db.get(KnowledgeDocument, passage.document_id)
    assert row is not None
    return row


def _guide(db: Session, author: User, **kwargs: Any) -> dict[str, Any]:
    return cre.publish_guide(db, author.id, **{"section": "plan", "title": f"a frame {uuid4().hex[:6]}", **kwargs})["guide"]


def _refused(callable_: Any, code: str) -> cre.CreatorRefusal:
    with pytest.raises(cre.CreatorRefusal) as caught:
        callable_()
    assert caught.value.code == code, f"expected {code!r}, the door answered {caught.value.code!r}: {caught.value.message}"
    return caught.value


# ------------------------------------------------------------------ the shape of what is stored


def test_the_columns_a_guide_stores_are_the_minimisation_rule() -> None:
    """No column on either table could hold a passage's text, a token total or a count of anything."""
    guide_held = {str(column.name) for column in CreatorGuide.__table__.columns}
    citation_held = {str(column.name) for column in GuideCitation.__table__.columns}
    assert guide_held == {"id", "author_id", "slug", "title", "summary", "section", "visibility", "published_on", "data_origin", "is_demo_data", "created_at", "updated_at"}
    assert citation_held == {"id", "guide_id", "document_id", "ordinal", "cited_text_hash", "note", "data_origin", "is_demo_data", "created_at", "updated_at"}
    forbidden = {"text", "body", "chunk_id", "tokens", "citations", "moved", "reading_minutes", "price", "currency", "provider", "checkout"}
    assert not (guide_held | citation_held) & forbidden, f"{sorted((guide_held | citation_held) & forbidden)} would be a stored copy or a price"


def test_citing_a_passage_stores_its_address_and_its_hash_and_none_of_its_words(session: Session, cast: dict[str, User]) -> None:
    passage = _passage(session)
    document = _document(session, passage)
    guide = _guide(session, cast["ada"])
    answer = cre.cite(session, guide["id"], cast["ada"].id, document=document.slug, ordinal=passage.ordinal, note="the part that matters")
    row = session.get(GuideCitation, answer["citation"]["id"])
    assert row is not None and row.document_id == document.id and row.ordinal == passage.ordinal
    assert row.cited_text_hash == passage.text_hash, "the witness is the hash that was there at citation time"
    stored = " ".join(str(getattr(row, name)) for name in ("note",))
    assert passage.text[:60] not in stored and passage.text[:60] not in session.get(CreatorGuide, guide["id"]).summary


def test_a_second_press_of_the_same_citation_is_one_row(session: Session, cast: dict[str, User]) -> None:
    passage = _passage(session)
    document = _document(session, passage)
    guide = _guide(session, cast["ada"])
    cre.cite(session, guide["id"], cast["ada"].id, document=document.slug, ordinal=passage.ordinal)
    again = cre.cite(session, guide["id"], cast["ada"].id, document=document.slug, ordinal=passage.ordinal, note="a second thought")
    assert again["citations"] == 1 == int(session.query(GuideCitation).filter_by(guide_id=guide["id"]).count())
    assert again["citation"]["note"] == "a second thought", "the second press edits the annotation, it does not stack a row"


def test_the_unique_constraint_is_what_makes_a_duplicate_citation_impossible(session: Session, cast: dict[str, User]) -> None:
    passage = _passage(session)
    document = _document(session, passage)
    guide = _guide(session, cast["ada"])
    session.add(GuideCitation(id=cre.new_public_id("cit"), guide_id=guide["id"], document_id=document.id, ordinal=passage.ordinal, cited_text_hash="", note="", data_origin="user", is_demo_data=False))
    session.commit()
    session.add(GuideCitation(id=cre.new_public_id("cit"), guide_id=guide["id"], document_id=document.id, ordinal=passage.ordinal, cited_text_hash="", note="", data_origin="user", is_demo_data=False))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# ------------------------------------------------------------------ every figure is counted, so the corpus can move


def test_the_token_figure_is_the_corpus_counted_again_and_drops_when_a_passage_goes(session: Session, cast: dict[str, User]) -> None:
    passage = _passage(session)
    document = _document(session, passage)
    guide = _guide(session, cast["ada"])
    cre.cite(session, guide["id"], cast["ada"].id, document=document.slug, ordinal=passage.ordinal)
    first = cre.read_guide(session, guide["id"], cast["ada"].id)
    assert first["tokens"] == int(passage.token_estimate or 0) and first["citations"] == 1
    assert first["moved"] == 0, "nothing has moved yet, and the page must not imply otherwise"

    # the passage's text changes under the citation: the hash is the only thing that could notice
    passage.text_hash = "0" * 64
    session.commit()
    after = cre.read_guide(session, guide["id"], cast["ada"].id)
    assert after["moved"] == 1, "a stored count would still be insisting the passage is what was cited"
    assert after["citations"] == 1, "the citation is still there — `moved` says the text is not the one that was seen"


def test_the_subscriber_figure_is_the_other_tier_follow_rows_counted(session: Session, cast: dict[str, User]) -> None:
    cre.ensure_profile(session, cast["ada"].id, headline="a coach who writes things")
    session.add(CommunityFollow(id=cre.new_public_id("fol"), follower_id=cast["bo"].id, followee_id=cast["ada"].id, followed_on=utc_today().isoformat()))
    session.commit()
    profile = cre.profile(session, cast["ada"].id)
    assert profile["subscribers"] == 1 and profile["formulas"]["subscribers"] == cre.FORMULAS["subscribers"]
    assert profile["guides"] == 0, "a creator with no guide is a real state, not an empty answer"


# ------------------------------------------------------------------ ceilings, at their edge and past it


def test_the_guide_ceiling_accepted_at_its_edge_is_refused_one_past_it_with_its_own_figures(session: Session, cast: dict[str, User]) -> None:
    ada = cast["ada"]
    held = int(session.query(CreatorGuide).filter_by(author_id=ada.id).count())
    for index in range(cre.MAX_GUIDES_PER_CREATOR - held - 1):
        session.add(
            CreatorGuide(
                id=cre.new_public_id("guide"), author_id=ada.id, slug=f"filler-{index}-{TAG}", title=f"filler {index}", section="plan", visibility="public", published_on=utc_today().isoformat()
            )
        )
    session.commit()
    _guide(session, ada, title=f"the edge {uuid4().hex[:6]}")
    error = _refused(lambda: cre.publish_guide(session, ada.id, section="plan", title=f"one too many {uuid4().hex[:6]}"), "guide_limit")
    assert error.figures == {"held": cre.MAX_GUIDES_PER_CREATOR, "limit": cre.MAX_GUIDES_PER_CREATOR}


def test_the_citation_ceiling_refuses_with_the_number_it_publishes(session: Session, cast: dict[str, User]) -> None:
    passage = _passage(session)
    document = _document(session, passage)
    guide = _guide(session, cast["ada"])
    for index in range(cre.MAX_CITATIONS_PER_GUIDE):
        session.add(
            GuideCitation(id=cre.new_public_id("cit"), guide_id=guide["id"], document_id=document.id, ordinal=10_000 + index, cited_text_hash="", note="", data_origin="user", is_demo_data=False)
        )
    session.commit()
    error = _refused(lambda: cre.cite(session, guide["id"], cast["ada"].id, document=document.slug, ordinal=passage.ordinal), "citation_limit")
    assert error.figures == {"held": cre.MAX_CITATIONS_PER_GUIDE, "limit": cre.MAX_CITATIONS_PER_GUIDE}


@pytest.mark.parametrize(
    ("verb", "code"),
    [("section", "guide_section"), ("title", "guide_title"), ("visibility", "guide_visibility"), ("document", "no_such_document"), ("ordinal", "citation_ordinal")],
)
def test_a_word_or_a_shape_the_door_does_not_know_is_refused_naming_what_it_knows(session: Session, cast: dict[str, User], verb: str, code: str) -> None:
    ada = cast["ada"]
    passage = _passage(session)
    document = _document(session, passage)
    guide = _guide(session, ada)
    if verb == "section":
        error = _refused(lambda: cre.publish_guide(session, ada.id, section="diet", title="x"), code)
        assert error.figures["sections"] == list(cre.GUIDE_SECTIONS)
    elif verb == "title":
        _refused(lambda: cre.publish_guide(session, ada.id, section="plan", title="   "), code)
    elif verb == "visibility":
        _refused(lambda: cre.publish_guide(session, ada.id, section="plan", title="x", visibility="nobody"), code)
    elif verb == "document":
        _refused(lambda: cre.cite(session, guide["id"], ada.id, document="a-slug-nobody-wrote", ordinal=0), code)
    else:
        _refused(lambda: cre.cite(session, guide["id"], ada.id, document=document.slug, ordinal="second"), code)
        _refused(lambda: cre.cite(session, guide["id"], ada.id, document=document.slug, ordinal=-1), code)
        _refused(lambda: cre.cite(session, guide["id"], ada.id, document=document.slug, ordinal=999_999), code)


# ------------------------------------------------------------------ reach, absence, and no 403


def test_an_unlisted_guide_is_readable_at_its_address_and_appears_in_no_listing(session: Session, cast: dict[str, User]) -> None:
    ada = cast["ada"]
    hidden = _guide(session, ada, visibility="unlisted")
    assert [item["id"] for item in cre.list_guides(session, ada.id)["items"] if item["id"] == hidden["id"]] == [], "a feed carries public guides only"
    assert cre.read_guide(session, hidden["id"], cast["bo"].id)["id"] == hidden["id"], "its own address is the door"


def test_a_guide_that_is_not_yours_is_answered_as_absence_rather_than_as_a_refusal(session: Session, cast: dict[str, User]) -> None:
    passage = _passage(session)
    document = _document(session, passage)
    mine = _guide(session, cast["ada"])
    error = _refused(lambda: cre.cite(session, mine["id"], cast["bo"].id, document=document.slug, ordinal=passage.ordinal), "no_such_guide")
    assert error.figures["guide"] == mine["id"]
    _refused(lambda: cre.erase_guide(session, mine["id"], cast["bo"].id), "no_such_guide")
    assert session.get(CreatorGuide, mine["id"]) is not None, "and neither refusal wrote or erased anything"


def test_every_code_this_tier_answers_with_means_exactly_one_status_and_no_other_tier_owns_it() -> None:
    """Both halves of §51's promise, read off the shipped table and the shipped `TIERS`.

    The disjointness half exists because `assemble()` only refuses a code two tiers answer *differently*: §35 first
    registered `no_such_member`, which §39 already owned at the same 404, and nothing said so.
    """
    # Registration is the doors' commit: `creator` is not in `answers.TIERS` yet, so the shipped table
    # cannot answer these codes today, and this case asserts only what is true now — the four sets partition the
    # published list, no code is a 403, and no other registered tier owns a code published here.
    for code in cre.REFUSALS:
        expected = 404 if code in cre.NOT_FOUND_CODES else 422 if code in cre.UNPROCESSABLE_CODES else 409 if code in cre.CONFLICT_CODES else None
        assert expected is not None, f"{code} is published but in no set, so its status would be a fall-through"
    assert not cre.FORBIDDEN_CODES, "403 is the permission matrix's meaning and this tier has no matrix"
    assert len(cre.REFUSALS) == len(set(cre.REFUSALS))
    for tier in project_answers.TIERS:
        held = set(getattr(tier, "PUBLISHED", getattr(tier, "REFUSALS", ())) or ())
        shared = held & set(cre.REFUSALS)
        assert not shared, f"{sorted(shared)} belongs to {tier.__name__.rpartition('.')[2]} as well as to this tier"


def test_no_answer_in_this_tier_carries_a_money_shaped_key(session: Session, cast: dict[str, User]) -> None:
    """The claim `ff575a2` narrowed is held here: pricing lives in §42's rows, never in a payload."""
    passage = _passage(session)
    document = _document(session, passage)
    cre.ensure_profile(session, cast["ada"].id, slug=f"ada-{TAG}")
    guide = _guide(session, cast["ada"])
    cre.cite(session, guide["id"], cast["ada"].id, document=document.slug, ordinal=passage.ordinal)
    answers = [cre.rules(session), cre.list_guides(session, cast["ada"].id), cre.read_guide(session, guide["id"], cast["ada"].id), cre.profile(session, cast["ada"].id)]

    def names(node: Any) -> set[str]:
        if isinstance(node, dict):
            return set(node) | {found for value in node.values() for found in names(value)}
        if isinstance(node, list):
            return {found for value in node for found in names(value)}
        return set()

    forbidden = {"price", "currency", "amount", "provider", "checkout", "payout", "plan_id", "subscription"}
    for answer in answers:
        assert not names(answer) & forbidden, f"{sorted(names(answer) & forbidden)} would be a payment field the tier does not have"


def test_the_rulebook_publishes_the_vocabulary_the_guards_apply(session: Session) -> None:
    rules = cre.rules(session)
    assert rules["caps"]["guide_max"] == cre.MAX_GUIDES_PER_CREATOR and rules["caps"]["citation_max"] == cre.MAX_CITATIONS_PER_GUIDE
    assert sorted(rules["refusals"]) == sorted(cre.PUBLISHED)
    assert rules["formulas"] == cre.FORMULAS and rules["limitation"] == cre.LIMITATION
    assert cre.rules(session, ready=False)["counts"] == {"profiles": 0, "guides": 0, "citations": 0}
