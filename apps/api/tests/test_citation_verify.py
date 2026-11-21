"""The knowledge door never prints a citation marker for a passage it did not retrieve."""

from __future__ import annotations

from app.services.knowledge.answer import _strip_fabricated_citations


def test_valid_markers_survive_untouched():
    text = "Pressing triggers are coached early [1], and rest defence matters too [2]."
    out, removed = _strip_fabricated_citations(text, {1, 2, 3})
    assert removed == 0
    assert out == text


def test_a_fabricated_marker_is_stripped():
    text = "This claim cites a passage that was never retrieved [7]."
    out, removed = _strip_fabricated_citations(text, {1, 2, 3})
    assert removed == 1
    assert "[7]" not in out
    assert "never retrieved" in out


def test_mixed_valid_and_fabricated():
    text = "Grounded [1] but also invented [9] and grounded again [2]."
    out, removed = _strip_fabricated_citations(text, {1, 2})
    assert removed == 1
    assert "[1]" in out and "[2]" in out and "[9]" not in out


def test_multi_digit_refs():
    text = "From passage [12] and the fake [120]."
    out, removed = _strip_fabricated_citations(text, {12})
    assert removed == 1
    assert "[12]" in out and "[120]" not in out
