"""The Chronicle never prints a figure the gathered constitution did not contain."""

from __future__ import annotations

from app.services.chronicle import _strip_unprinted_figures

CONSTITUTION = "Edition 14 of 24. Goals 11, draws 2. Table: 23 points from 14 played."


def test_real_figures_survive():
    text = "After 14 played the leader holds 23 points, with 11 goals this round."
    out, dropped = _strip_unprinted_figures(text, CONSTITUTION)
    assert dropped == 0
    assert out == text


def test_an_invented_figure_sentence_is_struck():
    text = "The leader scored 999 goals. The table stands as printed."
    out, dropped = _strip_unprinted_figures(text, CONSTITUTION)
    assert dropped == 1
    assert "999" not in out
    assert "table stands" in out


def test_decimal_figures_are_checked():
    text = "Average was 2.1 goals. A fake 9.9 average was claimed."
    out, dropped = _strip_unprinted_figures(text, CONSTITUTION + " average 2.1")
    assert dropped == 1
    assert "9.9" not in out


def test_all_invented_sentences_leave_empty_text():
    text = "There were 999 goals and 777 cards."
    out, dropped = _strip_unprinted_figures(text, CONSTITUTION)
    assert dropped > 0
    assert "999" not in out and "777" not in out
