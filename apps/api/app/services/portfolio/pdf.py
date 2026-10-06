"""§38's third permitted output: a rendered Football CV, built from the same live read as the page.

The PDF is a presentation of `build_cv`, not another assembler. It stores nothing, reads no table of its own, and
recomputes every section at render time. Latin text uses Helvetica so the resulting PDF stays inspectable in tests;
text containing non-ASCII characters switches to reportlab's CID font, which keeps Chinese names and prose readable
without shipping a licensed font file in the repository.
"""

from __future__ import annotations

from html import escape
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.models import utcnow
from app.services.portfolio import cv as portfolio

LATIN_FONT = "Helvetica"
CID_FONT = "STSong-Light"

pdfmetrics.registerFont(UnicodeCIDFont(CID_FONT))


def _xml(text: Any) -> str:
    """Escape user text before handing it to reportlab's mini-markup."""
    return escape(str(text), quote=False).replace("\n", "<br/>").replace("\u2192", "-&gt;")


def _font(text: Any) -> str:
    return LATIN_FONT if str(text).isascii() else CID_FONT


def _style(text: Any, *, size: float = 9, leading: float | None = None, color: colors.Color = colors.black, space_after: float = 2) -> ParagraphStyle:
    return ParagraphStyle(
        name=f"portfolio-{_font(text)}-{size}",
        fontName=_font(text),
        fontSize=size,
        leading=leading or size + 3,
        textColor=color,
        alignment=TA_LEFT,
        spaceAfter=space_after,
    )


def _paragraph(text: Any, **kwargs: Any) -> Paragraph:
    return Paragraph(_xml(text), _style(text, **kwargs))


def _figure_text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(entry) for entry in value)
    if isinstance(value, dict):
        return " · ".join(f"{key} {inner}" for key, inner in value.items())
    if value is None:
        return "null"
    return str(value)


def _footer(canv: pdf_canvas.Canvas, doc: SimpleDocTemplate) -> None:
    canv.saveState()
    canv.setFont(LATIN_FONT, 8)
    canv.setFillColor(colors.HexColor("#64748b"))
    canv.drawString(18 * mm, 12 * mm, "FOOTBALL OS · Football CV")
    canv.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Page {doc.page}")
    canv.restoreState()


def _section_flow(section: dict[str, Any], width: float) -> list[Any]:
    rows: list[Any] = [
        _paragraph(section.get("title", section.get("section", "Section")), size=12, leading=15, space_after=2),
        _paragraph(f"{section.get('source') or 'no source published'} · origin {section.get('data_origin', 'unknown')}", size=7.5, color=colors.HexColor("#475569"), space_after=5),
    ]
    if not section.get("available"):
        rows.append(_paragraph(f"Not filled in this build. {section.get('missing_because', '')}", size=8.5, color=colors.HexColor("#92400e"), space_after=2))
        rows.append(_paragraph(f"Would be read from: {section.get('would_be_read_from') or 'no table published'}", size=7.5, color=colors.HexColor("#475569"), space_after=7))
        return rows

    figures = section.get("figures") or {}
    formulas = section.get("formulas") or {}
    for name, value in figures.items():
        rows.append(_paragraph(f"{name}: {_figure_text(value)}", size=8.5, space_after=1))
        rows.append(_paragraph(formulas.get(name, "printed by the CV door for the section as a whole"), size=7.3, color=colors.HexColor("#475569"), space_after=4))

    items = section.get("items") or []
    for index, item in enumerate(items, start=1):
        pairs = " · ".join(f"{key}: {_figure_text(value)}" for key, value in item.items())
        rows.append(_paragraph(f"{index}. {pairs}", size=7.8, color=colors.HexColor("#334155"), space_after=2))
    if not figures and not items:
        rows.append(_paragraph("This section is filled and its source answers with no rows and no figure yet.", size=8.2, color=colors.HexColor("#475569"), space_after=5))
    rows.append(Spacer(1, 5))
    return rows


def build_cv_pdf(session: Session, user_id: str, *, player_id: str | None = None) -> bytes:
    """Render §38's ten sections to a PDF and return the bytes; no file or database row is written."""
    cv = portfolio.build_cv(session, user_id, player_id=player_id)
    stream = BytesIO()
    doc = SimpleDocTemplate(
        stream,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=19 * mm,
        title="Football CV",
        author=str(cv["account"].get("display_name") or "FOOTBALL OS"),
        subject="Football Career Portfolio (spec §38)",
        creator="FOOTBALL OS",
        pageCompression=0,
    )
    width = A4[0] - 36 * mm
    story: list[Any] = [
        _paragraph("Football CV", size=20, leading=23, space_after=3),
        _paragraph(cv["account"].get("display_name") or "FOOTBALL OS account", size=9, color=colors.HexColor("#475569"), space_after=2),
    ]
    player = cv.get("player")
    if player:
        story.append(_paragraph(f"{player['name']} · {player['position']} · {player['data_origin']}", size=10, space_after=2))
    else:
        story.append(_paragraph("No player row on this account yet.", size=9, color=colors.HexColor("#92400e"), space_after=2))
    story.extend(
        [
            _paragraph(f"Generated {utcnow().isoformat()} from the live rows §38's formulas name.", size=7.5, color=colors.HexColor("#475569"), space_after=2),
            _paragraph(cv["limitation"], size=7.5, color=colors.HexColor("#475569"), space_after=10),
        ]
    )

    summary = [
        ["Sections", "Filled", "Not filled"],
        [str(cv["counts"]["sections"]), str(cv["counts"]["filled"]), ", ".join(cv["counts"]["unfilled"]) or "none"],
    ]
    table = Table(summary, colWidths=[width / 3] * 3, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), LATIN_FONT),
                ("FONTNAME", (0, 1), (-1, 1), LATIN_FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([table, Spacer(1, 11)])
    for section in cv["sections"]:
        story.extend(_section_flow(section, width))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return stream.getvalue()
