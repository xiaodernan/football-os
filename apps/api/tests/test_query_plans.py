"""Query plans, not query guesses: the four hot reads must keep using an index.

The audit that produced this file ran `EXPLAIN QUERY PLAN` against the real fixture (16 481 news links,
7 280 stat lines, 856 articles) and found every hot read on an index already — the largest table in this
product is four figures, and an index added "for performance" at that size buys nothing and costs every
write. What the audit *did* find worth keeping is the ability to notice the day that stops being true: a
new `order_by` on an unindexed column, a filter added to a hot door, a join that flips the planner to a
scan. These four assertions are that notice.

The rule this file enforces is narrow on purpose. A plan may sort in a temporary B-tree (a player's
fifteen stat lines are cheaper to sort than to index for), but it must not read the table it filters:

* `SCAN <table>` on a hot table means the filter has no index — that is the regression.
* `SEARCH <table> USING INDEX …` means it does.

SQLite is the engine that can answer this without a server, which is why the assertions run on every
suite rather than in a performance job nobody opens. PostgreSQL's planner is exercised by the same
queries in CI against a real instance; the property asserted here is engine-independent — *the filter is
served by an index* — even though the spelling of the plan is not.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text

from app.core.db import SessionLocal, init_db


@pytest.fixture()
def db() -> Any:
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _plan(db: Any, sql: str) -> list[str]:
    rows = db.execute(text("EXPLAIN QUERY PLAN " + sql)).all()
    # SQLite answers (id, parent, notused, detail); the detail is the only column that matters here.
    return [str(row[-1]) for row in rows]


HOT_READS: tuple[tuple[str, str, str], ...] = (
    (
        "a team's sheet for the matches on screen",
        "SELECT * FROM real_player_match_stats WHERE team_id = 'tm_x' AND match_id IN ('mt_a', 'mt_b') "
        "ORDER BY match_id, minute_rank",
        "real_player_match_stats",
    ),
    (
        "one player's season lines, newest first",
        "SELECT s.* FROM real_player_match_stats s JOIN real_matches m ON m.id = s.match_id "
        "WHERE s.player_id = 'pl_x' ORDER BY m.kickoff_at DESC, s.id LIMIT 300",
        "real_player_match_stats",
    ),
    (
        "the articles that name one entity",
        "SELECT a.* FROM news_articles a JOIN news_article_links l ON l.article_id = a.id "
        "WHERE l.entity_type = 'player' AND l.entity_slug = 'pl_x' ORDER BY a.published_at DESC LIMIT 10",
        "news_article_links",
    ),
    (
        "the article list for a category",
        "SELECT * FROM news_articles WHERE category = 'match_report' ORDER BY published_at DESC LIMIT 20",
        "news_articles",
    ),
    (
        "the queue's claim scan",
        "SELECT * FROM jobs WHERE status = 'QUEUED' ORDER BY created_at, id LIMIT 8",
        "jobs",
    ),
)


@pytest.mark.parametrize(("label", "sql", "table"), HOT_READS, ids=[row[0] for row in HOT_READS])
def test_a_hot_read_is_served_by_an_index(db: Any, label: str, sql: str, table: str) -> None:
    # Every relation in these reads is reached by a key, so *no* SCAN is acceptable — not just none on
    # the table the test names. A join that flips one side to a scan is the same defect wearing a
    # different name, and the assertion is cheaper to trust than a per-table needle that an alias hides.
    plan = _plan(db, sql)
    assert plan, f"{label}: the planner said nothing, which means the statement did not parse"
    assert not any(line.startswith("SCAN") for line in plan), (
        f"{label}: a relation in this read is scanned, so a filter has no index — plan was {plan}"
    )
    assert any("USING INDEX" in line or "USING COVERING INDEX" in line for line in plan), (
        f"{label}: nothing in this read used an index — plan was {plan}"
    )


def test_the_queue_index_is_the_one_the_claim_orders_by(db: Any) -> None:
    """`ix_jobs_status_created` exists so the claim's ORDER BY is free; a scan here is the whole queue."""
    plan = _plan(db, "SELECT * FROM jobs WHERE status = 'QUEUED' ORDER BY created_at ASC, id ASC LIMIT 8")
    assert any("ix_jobs_status_created" in line for line in plan), plan
    assert not any("TEMP B-TREE" in line for line in plan), f"the claim sorts in memory: {plan}"
