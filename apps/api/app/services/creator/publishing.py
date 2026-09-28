"""§36's creator tier: a publication that cites the corpus, and counts everything it says about itself.

The rule is §35's, carried to the second milestone: **a publication stores an address and the author's own words,
never a copy of what it points at**. A guide therefore holds a title, a section, a summary and an ordering; the
passages it cites stay in `knowledge_chunks`, and `citations`, `tokens` and `moved` are `count(*)`/`sum()` over the
rows the formulas name at the moment of the read. That is the only way a guide can be honest after an operator edits
the corpus, which `sync_knowledge` invites at any time.

Three consequences, each held by a named case rather than by this paragraph:

* **a citation keys on (document, ordinal) and remembers the hash.** `services/knowledge/ingest.py` keeps a
  document row across re-syncs but mints a fresh chunk id every time, so an id-keyed pointer dangles on the first
  edit while (document, ordinal) still resolves. The stored `cited_text_hash` is not a link — it is the witness that
  lets a read say *this passage has moved since it was cited* rather than silently quoting something else.
* **a creator is derived, not a role.** `creator_profiles` existence is the state; `ROLES` stays at seven. A second
  home for the fact would have to be kept in step with the first, and §41's matrix page already has enough to say.
* **no money anywhere.** The pricing architecture is §42's `entitlements` rows — a feature, a plan, a ceiling, a
  period — and this tier adds features to that table rather than a currency, provider or checkout field, which is
  the narrow claim `docs/M9_COMMUNITY_VERIFICATION.md` now records.

Every ceiling is one constant that `CAPS` publishes, that one guard below applies, and whose refusal prints it
beside `held` — §49's rule, applied before it could recur.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import (
    CommunityFollow,
    CreatorGuide,
    CreatorProfile,
    GuideCitation,
    KnowledgeChunk,
    KnowledgeDocument,
    User,
    utc_today,
)


class CreatorRefusal(RuntimeError):
    """A refusal with the figures beside the sentence, in the shape both §35 and §39 publish."""

    def __init__(self, code: str, message: str, **figures: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.figures = figures

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.figures}


#: Which slice of a football life the guide is about. Closed, because a section a page cannot link to is a label
#: nobody reads — the same argument that keeps §41's report kinds enumerated.
GUIDE_SECTIONS: Final = ("plan", "drill", "match", "tactic", "scout", "video")

#: §35's three reach levels, with the same meaning: `unlisted` answers at its own address and appears in no
#: listing, `followers` reaches the accounts whose follow rows point at the author right now.
VISIBILITIES: Final = ("public", "unlisted", "followers")

MAX_GUIDES_PER_CREATOR: Final = 100
GUIDE_TITLE_MAX: Final = 160
GUIDE_SLUG_MAX: Final = 80
GUIDE_SUMMARY_MAX: Final = 600
PROFILE_HEADLINE_MAX: Final = 160
PROFILE_BIO_MAX: Final = 1500
MAX_CITATIONS_PER_GUIDE: Final = 24
CITATION_NOTE_MAX: Final = 400

#: What the derived figures on this tier's answers are made of, printed beside the figures themselves.
FORMULAS: Final = {
    "citations": "count of this guide's citation rows — one per (guide, document, ordinal) by constraint, so it is a number of passages, not of presses",
    "moved": "count of this guide's citation rows whose stored `cited_text_hash` no longer matches the chunk now at that address — the passage is still there to read, but it is not the text that was cited",
    "tokens": "sum of `token_estimate` over the chunk rows the citations resolve to right now; no minutes are published, because this project has no reading-rate to derive them from",
    "guides": "count of guide rows whose author is this account",
    "subscribers": "count of `community_follows` rows whose `followee_id` is this account — §35's follow rows, not a second follow table",
    "guide_total": "count of every guide row this database holds",
}

REFUSALS: Final = (
    "no_such_guide",
    "no_such_creator",
    "no_such_document",
    "no_such_citation",
    "guide_section",
    "guide_title",
    "guide_summary",
    "guide_visibility",
    "citation_ordinal",
    "citation_note",
    "profile_headline",
    "profile_bio",
    "slug_taken",
    "guide_limit",
    "citation_limit",
)

NOT_FOUND_CODES: Final = frozenset({"no_such_guide", "no_such_creator", "no_such_document", "no_such_citation"})
UNPROCESSABLE_CODES: Final = frozenset(
    {
        "guide_section",
        "guide_title",
        "guide_summary",
        "guide_visibility",
        "citation_ordinal",
        "citation_note",
        "profile_headline",
        "profile_bio",
    }
)
CONFLICT_CODES: Final = frozenset({"slug_taken", "guide_limit", "citation_limit"})
#: 403 is the permission matrix's single meaning (§51) and this tier has no matrix of its own.
FORBIDDEN_CODES: Final[frozenset[str]] = frozenset()

PUBLISHED: Final = REFUSALS

CAPS: Final = {
    "guide_max": MAX_GUIDES_PER_CREATOR,
    "guide_title_max": GUIDE_TITLE_MAX,
    "guide_slug_max": GUIDE_SLUG_MAX,
    "guide_summary_max": GUIDE_SUMMARY_MAX,
    "citation_max": MAX_CITATIONS_PER_GUIDE,
    "citation_note_max": CITATION_NOTE_MAX,
    "profile_headline_max": PROFILE_HEADLINE_MAX,
    "profile_bio_max": PROFILE_BIO_MAX,
    "sections": list(GUIDE_SECTIONS),
    "visibilities": list(VISIBILITIES),
    "visibility_rule": "`public` reaches a listing, `unlisted` is readable at its own address and appears in no listing, `followers` reaches its author and the accounts whose follow rows point at that author right now",
}

LIMITATION: Final = (
    "a guide stores its title, its section, its own summary and the *address* of each passage it cites — never the "
    "text, so re-ingesting the corpus cannot leave a guide quoting words the document no longer holds; the passage "
    "is read where it lives, and a citation whose passage has changed says so through `moved`. Nothing in this tier "
    "carries money: the plan/feature/ceiling rows in `entitlements` are the whole pricing architecture here, and no "
    "currency, provider or checkout field appears in any payload"
)


def _today() -> str:
    return utc_today().isoformat()


def creator_counts(session: Session, *, ready: bool) -> dict[str, int]:
    """The rulebook's counts of this tier's three tables — 0 rather than a crash before the migration is applied."""
    if not ready:
        return {name: 0 for name in ("profiles", "guides", "citations")}
    return {
        "profiles": int(session.scalar(select(func.count()).select_from(CreatorProfile)) or 0),
        "guides": int(session.scalar(select(func.count()).select_from(CreatorGuide)) or 0),
        "citations": int(session.scalar(select(func.count()).select_from(GuideCitation)) or 0),
    }


def _account(session: Session, ident: str) -> User:
    row = session.get(User, str(ident))
    if row is None:
        raise CreatorRefusal("no_such_creator", f"no account answers to {str(ident)!r}", account=str(ident))
    return row


def _slug_of(title: str) -> str:
    characters = "".join(character.lower() if character.isalnum() else "-" for character in title.strip())
    collapsed = "-".join(part for part in characters.split("-") if part)
    return collapsed[:GUIDE_SLUG_MAX]


def _guide(session: Session, ident: str) -> CreatorGuide:
    row = session.get(CreatorGuide, str(ident))
    if row is None:
        raise CreatorRefusal("no_such_guide", f"no guide answers to {str(ident)!r}", guide=str(ident))
    return row


def _section(section: Any) -> str:
    word = str(section or "").strip().lower()
    if word not in GUIDE_SECTIONS:
        raise CreatorRefusal(
            "guide_section",
            f"a guide is about one of {' '.join(repr(item) for item in GUIDE_SECTIONS)}; {word!r} would name a slice of the game no page can open",
            sent=word,
            sections=list(GUIDE_SECTIONS),
        )
    return word


def _visibility(visibility: Any) -> str:
    word = str(visibility or "").strip().lower()
    if word not in VISIBILITIES:
        raise CreatorRefusal(
            "guide_visibility",
            f"a guide is {' or '.join(repr(item) for item in VISIBILITIES)}; {word!r} would select nobody and the door cannot tell that from a mistake",
            sent=word,
            visibilities=list(VISIBILITIES),
        )
    return word


def _text(value: Any, maximum: int, code: str, field: str, *, required: bool) -> str:
    words = str(value or "").strip()
    if required and not words:
        raise CreatorRefusal(code, f"a {field} cannot be blank", field=field, max=maximum)
    if len(words) > maximum:
        raise CreatorRefusal(code, f"a {field} is at most {maximum} characters and this one is {len(words)}", length=len(words), max=maximum)
    return words


def profile(session: Session, ident: str) -> dict[str, Any]:
    """An account as a creator: its own state, and the two figures that say how far it reaches."""
    account = _account(session, ident)
    row = session.scalar(select(CreatorProfile).where(CreatorProfile.user_id == account.id))
    if row is None:
        raise CreatorRefusal("no_such_creator", f"{account.display_name!r} has not published anything yet, so there is no creator page for them", account=account.id)
    return _profile_shape(session, row)


def _profile_shape(session: Session, row: CreatorProfile) -> dict[str, Any]:
    return {
        "id": row.id,
        "slug": row.slug,
        "account": {"id": row.user_id, "display_name": _account(session, row.user_id).display_name},
        "headline": row.headline,
        "bio": row.bio,
        "since": row.since,
        "guides": int(session.scalar(select(func.count()).select_from(CreatorGuide).where(CreatorGuide.author_id == row.user_id)) or 0),
        "subscribers": int(session.scalar(select(func.count()).select_from(CommunityFollow).where(CommunityFollow.followee_id == row.user_id)) or 0),
        "formulas": dict(FORMULAS),
        "rule": LIMITATION,
    }


def ensure_profile(session: Session, actor_id: str, *, slug: Any = "", headline: Any = "", bio: Any = "") -> dict[str, Any]:
    """The first publication writes the creator state; it is never switched on by a flag."""
    account = _account(session, actor_id)
    row = session.scalar(select(CreatorProfile).where(CreatorProfile.user_id == account.id))
    wanted = str(slug or "").strip().lower() or _slug_of(account.display_name)
    if row is None:
        taken = session.scalar(select(CreatorProfile).where(CreatorProfile.slug == wanted))
        if taken is not None:
            raise CreatorRefusal("slug_taken", f"another account already publishes as {wanted!r}, and a reader cannot tell two creators apart by a name", slug=wanted)
        row = CreatorProfile(
            id=new_public_id("crt"),
            user_id=account.id,
            slug=wanted,
            headline=_text(headline, PROFILE_HEADLINE_MAX, "profile_headline", "headline", required=False),
            bio=_text(bio, PROFILE_BIO_MAX, "profile_bio", "biography", required=False),
            since=_today(),
            data_origin="user",
            is_demo_data=False,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
    return {**_profile_shape(session, row), "created": True}


def publish_guide(session: Session, actor_id: str, *, section: Any, title: Any, summary: Any = "", visibility: Any = "public") -> dict[str, Any]:
    """Publish the frame; the substance stays where it is written."""
    chosen = _section(section)
    words = _text(title, GUIDE_TITLE_MAX, "guide_title", "title", required=True)
    frame = _text(summary, GUIDE_SUMMARY_MAX, "guide_summary", "summary", required=False)
    seen = _visibility(visibility)
    held = int(session.scalar(select(func.count()).select_from(CreatorGuide).where(CreatorGuide.author_id == actor_id)) or 0)
    if held >= MAX_GUIDES_PER_CREATOR:
        raise CreatorRefusal("guide_limit", f"this account already publishes {MAX_GUIDES_PER_CREATOR} guides, which is the cap", held=held, limit=MAX_GUIDES_PER_CREATOR)
    slug = _slug_of(words)
    if session.scalar(select(CreatorGuide).where(CreatorGuide.author_id == actor_id, CreatorGuide.slug == slug)) is not None:
        raise CreatorRefusal("slug_taken", f"this account already publishes a guide addressed {slug!r}; a second one would be unreachable", slug=slug, author=actor_id)
    row = CreatorGuide(
        id=new_public_id("guide"),
        author_id=actor_id,
        slug=slug,
        title=words,
        summary=frame,
        section=chosen,
        visibility=seen,
        published_on=_today(),
        data_origin="user",
        is_demo_data=False,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"guide": view(session, row, actor_id), "published": True, "rule": LIMITATION}


def cite(session: Session, guide_id: str, actor_id: str, *, document: Any, ordinal: Any = 0, note: Any = "") -> dict[str, Any]:
    """Point at one passage. The chunk's own row is read to take its hash, and nothing of its text is stored."""
    guide = _owned(session, guide_id, actor_id)
    document_row = session.scalar(select(KnowledgeDocument).where(KnowledgeDocument.slug == str(document or "").strip()))
    if document_row is None:
        raise CreatorRefusal("no_such_document", f"the corpus holds no document addressed {str(document)!r}, so there is nothing to cite", document=str(document))
    try:
        position = int(ordinal)
    except (TypeError, ValueError):
        raise CreatorRefusal("citation_ordinal", f"an ordinal must be a whole passage number, and {ordinal!r} is not", sent=str(ordinal)) from None
    if position < 0:
        raise CreatorRefusal("citation_ordinal", f"a passage number cannot be negative, and {position} is", ordinal=position)
    passage = session.scalar(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document_row.id, KnowledgeChunk.ordinal == position))
    if passage is None:
        raise CreatorRefusal("citation_ordinal", f"{document_row.slug} holds no passage number {position}, so the guide would point at nothing", document=document_row.slug, ordinal=position)
    held = int(session.scalar(select(func.count()).select_from(GuideCitation).where(GuideCitation.guide_id == guide.id)) or 0)
    if held >= MAX_CITATIONS_PER_GUIDE:
        raise CreatorRefusal("citation_limit", f"this guide already cites {MAX_CITATIONS_PER_GUIDE} passages, which is the cap", held=held, limit=MAX_CITATIONS_PER_GUIDE)
    comment = _text(note, CITATION_NOTE_MAX, "citation_note", "note", required=False)
    row = session.scalar(select(GuideCitation).where(GuideCitation.guide_id == guide.id, GuideCitation.document_id == document_row.id, GuideCitation.ordinal == position))
    if row is None:
        row = GuideCitation(
            id=new_public_id("cit"), guide_id=guide.id, document_id=document_row.id, ordinal=position, cited_text_hash=passage.text_hash, note=comment, data_origin="user", is_demo_data=False
        )
        session.add(row)
    else:
        row.note = comment
    session.commit()
    session.refresh(row)
    return {"citation": _citation_shape(row, passage), "recorded_now": True, **measures(session, guide), "formulas": dict(FORMULAS)}


def _citation_shape(row: GuideCitation, passage: KnowledgeChunk | None = None) -> dict[str, Any]:
    return {
        "id": row.id,
        "document": row.document_id,
        "ordinal": row.ordinal,
        "note": row.note,
        "heading": passage.heading if passage is not None else None,
        "moved": bool(passage is not None and passage.text_hash != row.cited_text_hash),
    }


def _owned(session: Session, guide_id: str, actor_id: str) -> CreatorGuide:
    row = _guide(session, guide_id)
    if row.author_id != actor_id:
        # Somebody else's guide is answered as absence, exactly as §35 answers a post it is not yours to erase:
        # this tier has no tenant matrix to consult, so the only honest distinction is reachable or not.
        raise CreatorRefusal("no_such_guide", f"no guide of yours answers to {str(guide_id)!r}", guide=str(guide_id))
    return row


def measures(session: Session, row: CreatorGuide) -> dict[str, int]:
    """The three figures a guide publishes, each counted from the rows its own formula names."""
    citations = list(session.scalars(select(GuideCitation).where(GuideCitation.guide_id == row.id)))
    tokens = 0
    moved = 0
    for citation in citations:
        passage = session.scalar(select(KnowledgeChunk).where(KnowledgeChunk.document_id == citation.document_id, KnowledgeChunk.ordinal == citation.ordinal))
        if passage is None:
            moved += 1
            continue
        tokens += int(passage.token_estimate or 0)
        if passage.text_hash != citation.cited_text_hash:
            moved += 1
    return {"citations": len(citations), "moved": moved, "tokens": tokens}


def view(session: Session, row: CreatorGuide, viewer_id: str) -> dict[str, Any]:
    return {
        "id": row.id,
        "slug": row.slug,
        "title": row.title,
        "summary": row.summary,
        "section": row.section,
        "visibility": row.visibility,
        "published_on": row.published_on,
        "author": {"id": row.author_id, "display_name": _account(session, row.author_id).display_name},
        **measures(session, row),
        "formulas": dict(FORMULAS),
    }


def list_guides(session: Session, viewer_id: str, *, creator: Any = None, section: Any = None, limit: int = 20) -> dict[str, Any]:
    """A listing of what reaches this reader: everybody's public shelf, one creator's shelf, or one section's."""
    allowed = list(VISIBILITIES) if creator is not None and str(creator) == viewer_id else ["public"]
    statement = select(CreatorGuide).where(CreatorGuide.visibility.in_(allowed))
    if creator is not None:
        statement = statement.where(CreatorGuide.author_id == str(creator))
    if section is not None:
        statement = statement.where(CreatorGuide.section == _section(section))
    total = int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = list(session.scalars(statement.order_by(CreatorGuide.published_on.desc(), CreatorGuide.id.desc()).limit(max(1, min(int(limit), 100)))))
    return {
        "items": [view(session, row, viewer_id) for row in rows],
        "total": total,
        "limit": int(MAX_GUIDES_PER_CREATOR),
        "creator": str(creator) if creator is not None else None,
        "section": str(section) if section is not None else None,
        "formulas": dict(FORMULAS),
        "rule": LIMITATION,
    }


def read_guide(session: Session, guide_id: str, viewer_id: str, *, with_citations: bool = True) -> dict[str, Any]:
    """One guide at its own address, and the passages it points at as they read right now."""
    row = _guide(session, guide_id)
    if row.visibility == "followers" and row.author_id != viewer_id:
        raise CreatorRefusal("no_such_guide", f"no guide answers to {str(guide_id)!r}", guide=str(guide_id))
    # `citations` stays the count the formula names, and the list of passages answers under its own key: one
    # key that meant a number on one read and a list on another is the defect class §51 exists to prevent.
    answer = {**view(session, row, viewer_id), "passages": citations_of(session, row) if with_citations else []}
    return answer


def citations_of(session: Session, row: CreatorGuide) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for citation in session.scalars(select(GuideCitation).where(GuideCitation.guide_id == row.id).order_by(GuideCitation.ordinal)):
        passage = session.scalar(select(KnowledgeChunk).where(KnowledgeChunk.document_id == citation.document_id, KnowledgeChunk.ordinal == citation.ordinal))
        items.append(_citation_shape(citation, passage))
    return items


def uncite(session: Session, guide_id: str, citation_id: str, actor_id: str) -> dict[str, Any]:
    row = session.get(GuideCitation, str(citation_id))
    if row is None or row.guide_id != guide_id:
        raise CreatorRefusal("no_such_citation", f"this guide holds no citation answering {str(citation_id)!r}", guide=str(guide_id), citation=str(citation_id))
    guide = _owned(session, guide_id, actor_id)
    session.delete(row)
    session.commit()
    return {"removed": True, "citation": str(citation_id), **measures(session, guide)}


def erase_guide(session: Session, guide_id: str, actor_id: str) -> dict[str, Any]:
    row = _owned(session, guide_id, actor_id)
    gone = measures(session, row)
    session.delete(row)
    session.commit()
    return {"erased": row.id, "author_id": actor_id, **gone}


def rules(session: Session, *, ready: bool = True) -> dict[str, Any]:
    """The vocabulary door: what may be published, what each figure means, and what a caller can be refused with."""
    return {
        "caps": dict(CAPS),
        "counts": creator_counts(session, ready=ready),
        "formulas": dict(FORMULAS),
        "refusals": list(PUBLISHED),
        "limitation": LIMITATION,
    }
