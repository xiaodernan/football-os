# M13 Phase 9 item 35 - the world draws next season's cup

**Status: done 2026-11-05.** Items 32-34 made a cup a run a career plays, pays and develops in - but only
for 2026, the season the world simulated. A career that closed its first season and started a second found
`cup_view` answering *the world's 2027 season drew no cup bracket this club entered*, because
`world/builder.py` drew exactly one thing for the future: two opening league games per league.

## The rule

* The world now stores, for every cup, next season's **four quarter-final ties** (eight entrants, drawn from
  the clubs as the boundary left them), dated in the new season, `status = "scheduled"`, no score. That is
  as far as a knockout can be drawn: the semi-finalists are winners nobody has produced yet.
* When a career's route first needs a tie the world has not drawn as a row, `cup.py::_slot` resolves it
  from the stored draw. The career's semi-final opponent is the winner of the **adjacent quarter-final**;
  the final's opponent is the winner of the other half's two quarter-finals and their semi-final. Each tie
  is played by the engine's pure entry point (`simulate_match` over the two clubs' stored profiles) with a
  seed derived from the row's slug or from the cup and stage, so the answer is reproducible and asking
  twice names the same club. No `sim_matches` row is written for a match nobody watched.
* The side is a bracket rule, stated rather than guessed: the first quarter-final of a half hosts the
  semi-final, and the higher half is the nominal home side of the final, which is played at a neutral
  venue. A resolved slot's `basis` says both facts - which quarter-finals decide it and how the engine
  read the adjacent tie.
* `WorldSizes.scheduled_matches` is `leagues x 2 + cups x 4`, so the world's own count assertion still
  holds; the default world gains 32 scheduled cup rows for 2027.

## What a reader sees

* A second-season career's cup panel lists the drawn quarter-final with the stored world row named in
  `world_match_id`; after a win, the semi-final's row carries `world_match_id = null` and a `basis` that
  reads *the Semi-final is not a drawn row yet: Quarter-final 1 meets Quarter-final 2, and the adjacent tie
  decides this opponent (engine 2-1 (seed ...))*.
* `career_cup_ties.basis` is widened to 512 characters (migration `0053`): a resolved slot's sentence plus
  the tie's own would have overflowed 255 on Postgres - the same trap item 32 hit with `penalty_note`.

## Tests

`apps/api/tests/test_cup.py::TestDrawnBracket` (3 cases; the file is 19) proves:

* a career in 2027 reads the drawn quarter-final, and the row behind it is `scheduled` with no score;
* a won quarter-final advances to a semi-final whose opponent is exactly the engine's winner of the
  adjacent quarter-final, stable across two reads, with the bracket pairing named in `basis`;
* two wins reach the final, at a neutral venue, against the resolved winner of the other half.

`apps/api/tests/test_world.py` grows `test_next_seasons_cup_is_drawn_to_its_quarter_finals` (four ties per
cup, eight distinct clubs, the four labels, all scheduled) and scopes the membership claim to league
fixtures, because a cup is not a membership. 59 cases in that file.

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_cup.py -q
# 19 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_world.py -q
# 59 passed
```

`alembic upgrade head` moved `0052 -> 0053` and `alembic check` is clean; ruff clean; `mypy app` clean.

## Live walk

`.scratch/walk-cup-2027.py` on the configured Postgres database at `0053`, a 2027 career at Corgard Town
in the Haldhurst Invitation Cup:

* the quarter-final was the world's own drawn row (`wmat_dcac0e4417d8172012`), 0-0 at home, won on
  penalties;
* the semi-final had **no world row**: opponent Ostdera Naval, `basis` naming *Quarter-final 1 meets
  Quarter-final 2* and the adjacent tie's engine reading `2-1 (seed 1174159400)`; the semi finished 1-1 and
  was lost on penalties;
* `status eliminated`, record 1-1, gates **135,057** over the two home ties, one prize of **40,000**.

## What it still does not do

* Only the quarter-finals are stored for a future season. The later rounds exist as a resolution rule, not
  as calendar rows, so a world page cannot list a 2027 semi-final as a fixture.
* A resolved world tie carries no attendance or gate of its own; only the career's own ties are played,
  and only they are paid.
* The draw is made when the world is generated, so it does not respond to a club's later transfers - the
  same rule the 2026 bracket follows.
