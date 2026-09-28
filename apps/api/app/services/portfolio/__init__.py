"""§38's Football Career Portfolio (M10): a CV of ten sections, assembled from rows that already exist.

The CV is a **read**. This package owns no table of its own — no `portfolio*` or `*_cv` name exists in
`Base.metadata`, and the case that guards this file asserts that over the schema rather than promising it in prose —
because every figure a CV prints is a fact another tier already stores: §7's player row, §10's training sessions,
§8's XP and attribute changes, §13's clips, §37's achievements and §9's coach messages. A stored CV would be a copy
of those rows, and the copy is what goes stale.

Two of §38's ten sections cannot be filled in this build, and this tier prints the measurement rather than a zero:
**Matches** and **Stats** describe a player appearing in a match, and the only match rows in this tree are about
generated players (`real_player_match_stats`) or about the squad a career's *manager* selected — `career_appearances.player_id`
is a foreign key to `real_players`, not to `user_players`. §20's career mode is a manager's season, so nothing here
records this player playing, and a CV that claimed otherwise would be inventing a match.

House rules applied rather than restated:

* every figure is counted at the moment of the read, and the expression that produced it is printed beside it;
* a section with nothing in it says which rows it looked for, and prints no figure at all — `0` reads as a
  measurement and would be the same defect as a stored report;
* each section names the tables it read and the `data_origin` those rows carry, because a CV mixes the account's own
  rows with derived ones and a reader is entitled to know which is which.
"""

from app.services.portfolio.cv import (
    FORMULAS,
    LIMITATION,
    PUBLIC_OUTPUTS,
    REFUSALS,
    SECTION_TITLES,
    SECTIONS,
    UNFILLED_REASONS,
    WOULD_READ_FROM,
    build_cv,
)

__all__ = [
    "FORMULAS",
    "LIMITATION",
    "PUBLIC_OUTPUTS",
    "REFUSALS",
    "SECTIONS",
    "SECTION_TITLES",
    "UNFILLED_REASONS",
    "WOULD_READ_FROM",
    "build_cv",
]
