"""The manual-ask door verifies cited headings and figures against the manual it prints."""

from __future__ import annotations

from app.services import manual_ask as ma


def test_a_real_heading_and_real_figure_survive():
    # "five-step" and the quickstart heading are in the manual (steps 1-5, "five-step quickstart")
    answer = "Start with the five-step quickstart: create the account, name the captain, walk the world."
    text, verified, repairs = ma._verify_manual_answer(answer)
    assert verified is True
    assert repairs == 0
    assert text == answer


def test_an_invented_figure_is_dropped():
    answer = "The manual says the world has 999 doors. Start with the quickstart."
    text, verified, repairs = ma._verify_manual_answer(answer)
    assert verified is False
    assert repairs == 1
    assert "999" not in text
    assert "quickstart" in text


def test_an_invented_bold_heading_is_dropped():
    answer = "See **The Secret Door** for details. The quickstart is the place to begin."
    text, verified, repairs = ma._verify_manual_answer(answer)
    assert verified is False
    assert "The Secret Door" not in text
    assert "quickstart" in text


def test_a_real_bold_heading_survives():
    heading = next(iter(ma._MANUAL_HEADINGS))
    answer = f"See **{heading}** for the full walkthrough."
    text, verified, repairs = ma._verify_manual_answer(answer)
    assert verified is True
    assert heading in text


def test_all_drifted_sentences_fall_back_to_an_honest_answer():
    answer = "There are 999 secret doors. See **The Secret Door**."
    text, verified, repairs = ma._verify_manual_answer(answer)
    assert verified is False
    assert "999" not in text and "Secret Door" not in text
    assert "does not cover" in text


def test_manual_headings_and_figures_are_derived_from_the_context():
    assert len(ma._MANUAL_HEADINGS) >= 40
    assert "five-step" in ma.MANUAL_CONTEXT or "5" in ma._MANUAL_FIGURES
