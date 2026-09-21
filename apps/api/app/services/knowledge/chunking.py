"""Document parsing and chunking (spec §29: ingestion → cleaning → chunking → metadata).

The corpus is markdown with a small YAML-subset frontmatter block. Sections are the
chunk boundaries because that is where an author puts a complete thought; long sections
are split on paragraph edges with a small overlap so a cited chunk still reads alone.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

MAX_CHUNK_CHARS = 1300
TARGET_CHUNK_CHARS = 900
MIN_CHUNK_CHARS = 220
OVERLAP_CHARS = 180

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_WHITESPACE_RE = re.compile(r"[ \t\u00a0]+")

REQUIRED_FIELDS = ("id", "title", "category", "source")
KNOWN_CATEGORIES = (
    "training",
    "tactics",
    "rules",
    "coaching",
    "sports-science",
    "match-analysis",
    "player-profile",
    "team-profile",
    "history",
)


class KnowledgeDocumentError(ValueError):
    """Raised when a source file cannot be ingested — never silently skipped."""


@dataclass
class ParsedSection:
    heading: str
    body: str


@dataclass
class ParsedDocument:
    slug: str
    title: str
    category: str
    tags: list[str]
    applies_to: list[str]
    difficulty: str
    source_label: str
    confidence: str
    last_reviewed: str
    sections: list[ParsedSection]
    body_markdown: str = ""
    path: str = ""

    @property
    def content_hash(self) -> str:
        digest = hashlib.sha256()
        digest.update(self.body_markdown.encode("utf-8"))
        return digest.hexdigest()[:32]


@dataclass
class Chunk:
    ordinal: int
    heading: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    char_count: int = 0
    token_estimate: int = 0
    text_hash: str = ""


def parse_scalar(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_list(raw: str) -> list[str]:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [parse_scalar(item) for item in inner.split(",") if item.strip()] if inner else []
    return [parse_scalar(value)] if value else []


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split `---`-delimited frontmatter from the body. Only key: value and inline lists."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise KnowledgeDocumentError("missing YAML frontmatter block (--- ... ---)")
    fields: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        fields[key.strip()] = value.strip()
    return fields, text[match.end() :]


def clean_body(body: str) -> str:
    """Normalise whitespace and drop markdown noise a reader would never type."""
    lines: list[str] = []
    for raw in body.replace("\r\n", "\n").split("\n"):
        line = _WHITESPACE_RE.sub(" ", raw.strip())
        line = re.sub(r"^[-*]\s+", "- ", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"\*(.+?)\*", r"\1", line)
        line = re.sub(r"`([^`]*)`", r"\1", line)
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sections(body: str) -> list[ParsedSection]:
    """One section per `## ` heading; prose before the first heading becomes the lead section."""
    headings = list(_HEADING_RE.finditer(body))
    sections: list[ParsedSection] = []
    if not headings:
        if body.strip():
            sections.append(ParsedSection(heading="", body=body.strip()))
        return sections
    lead = body[: headings[0].start()].strip()
    if lead:
        sections.append(ParsedSection(heading="", body=lead))
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        chunk_body = body[match.end() : end].strip()
        if chunk_body:
            sections.append(ParsedSection(heading=match.group(1).strip(), body=chunk_body))
    return sections


def split_long_section(text: str) -> list[str]:
    """Break an oversized section at paragraph edges, carrying an overlap forward."""
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    pieces: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) > MAX_CHUNK_CHARS and current:
            pieces.append(current)
            tail = current[-OVERLAP_CHARS:] if OVERLAP_CHARS and len(current) > OVERLAP_CHARS else ""
            boundary = tail.find(" ")
            carry = tail[boundary + 1 :] if boundary != -1 else tail
            current = f"{carry} {paragraph}".strip()
        else:
            current = candidate
        while len(current) > MAX_CHUNK_CHARS:  # a single monster paragraph
            cut = current.rfind(" ", TARGET_CHUNK_CHARS, TARGET_CHUNK_CHARS + 200)
            cut = cut if cut != -1 else TARGET_CHUNK_CHARS
            pieces.append(current[:cut].strip())
            carry = current[cut : cut + OVERLAP_CHARS].strip()
            current = f"{carry} {current[cut + OVERLAP_CHARS :]}".strip()
    if current:
        pieces.append(current)
    return [p for p in pieces if p]


def merge_tiny_sections(pieces: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Attach sub-threshold fragments to the previous chunk so citations never look truncated."""
    merged: list[tuple[str, str]] = []
    for heading, text in pieces:
        if merged and len(text) < MIN_CHUNK_CHARS:
            previous_heading, previous_text = merged[-1]
            joined = f"{previous_text}\n\n{f'{previous_heading} · {text}' if not heading else text}"
            merged[-1] = (previous_heading or heading, joined.strip())
        else:
            merged.append((heading, text))
    return merged


def parse_document(text: str, *, path: str = "") -> ParsedDocument:
    fields, raw_body = parse_frontmatter(text)
    missing = [key for key in REQUIRED_FIELDS if not fields.get(key)]
    if missing:
        raise KnowledgeDocumentError(f"frontmatter missing required fields: {', '.join(missing)}")
    category = parse_scalar(fields["category"])
    if category not in KNOWN_CATEGORIES:
        raise KnowledgeDocumentError(f"unknown category '{category}' (allowed: {', '.join(KNOWN_CATEGORIES)})")
    difficulty = parse_scalar(fields.get("difficulty", "intermediate"))
    if difficulty not in ("beginner", "intermediate", "advanced"):
        raise KnowledgeDocumentError(f"unknown difficulty '{difficulty}'")
    body = clean_body(raw_body)
    return ParsedDocument(
        slug=parse_scalar(fields["id"]),
        title=parse_scalar(fields["title"]),
        category=category,
        tags=parse_list(fields.get("tags", "")),
        applies_to=[p.lower() for p in parse_list(fields.get("applies_to", ""))],
        difficulty=difficulty,
        source_label=parse_scalar(fields["source"]),
        confidence=parse_scalar(fields.get("confidence", "medium")),
        last_reviewed=parse_scalar(fields.get("last_reviewed", "")),
        sections=split_sections(body),
        body_markdown=body,
        path=path,
    )


def strip_header(text: str) -> str:
    """Drop the 'Title — Section' line the chunker prefixed, leaving the author's prose."""
    return text.split("\n", 1)[1].strip() if "\n" in text else text.strip()


def chunk_document(document: ParsedDocument) -> list[Chunk]:
    """Chunk with the document title prefixed onto every section heading.

    The prefix is what makes a lone cited chunk attributable when the answer shows only
    a quote, and it gives the embedding the topic words a section may not repeat.
    """
    pieces: list[tuple[str, str]] = []
    for section in document.sections:
        heading = section.heading or document.title
        for piece in split_long_section(section.body):
            pieces.append((heading, piece))
    chunks: list[Chunk] = []
    for ordinal, (heading, text) in enumerate(merge_tiny_sections(pieces)):
        if not text.strip():
            continue
        header = f"{document.title} — {heading}" if heading and heading != document.title else document.title
        body = f"{header}\n{text}"
        digest = hashlib.sha256(f"{document.slug}:{ordinal}:{text}".encode()).hexdigest()[:32]
        chunks.append(
            Chunk(
                ordinal=ordinal,
                heading=heading,
                text=body,
                metadata={
                    "slug": document.slug,
                    "title": document.title,
                    "category": document.category,
                    "tags": document.tags,
                    "applies_to": document.applies_to,
                    "difficulty": document.difficulty,
                    "source": document.source_label,
                    "confidence": document.confidence,
                    "last_reviewed": document.last_reviewed,
                },
                char_count=len(body),
                token_estimate=max(1, len(body) // 4),
                text_hash=digest,
            )
        )
    return chunks
