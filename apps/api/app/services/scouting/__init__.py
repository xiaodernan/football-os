"""Scouting and recruitment (M7, spec §23–§24).

The pipeline §23 draws as `Search → Filter → Retrieve → Compare → Tactical Fit → Generate Scout Report`
lives here in two steps at a time: `requirements.py` decides what a request is *asking* — and says out loud
what it could not understand — and `search.py` answers it against the stored world rows, reporting how many
rows each requirement cut. Nothing in this package invents a number: every figure is arithmetic over
`real_players`, `teams` and the market's own valuation, and every judgement travels with the formula that
produced it.
"""
