"""Deterministic demo cohort for the behavioural beacon — the admin console's only data today.

Writes ~5,000 rows of ``seeded=True`` page views across a 90-day window: entry pages
weighted like a real product's traffic (/, /world, /tutorial first), dwell log-normal by
page class, bounce when the reader leaves before ~six seconds, weekday/weekend seasonality
and a gentle upward trend. The cohort is deliberately NOT organic traffic: every row
carries ``seeded=true`` and the admin console labels the read "seeded demo cohort" until
real beacons outnumber it. ``--reset`` deletes only seeded rows and re-seeds; live beacon
rows are never touched.
"""

from __future__ import annotations

import argparse
import math
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.core.db import SessionLocal
from app.models import PageView

SEED = 20261116
DAYS = 90

ENTRY_WEIGHTS = [
    ("/", 26), ("/world", 12), ("/tutorial", 11), ("/world/real-book", 9), ("/manual", 6),
    ("/world/dynasties", 6), ("/world/upsets", 5), ("/world/almanac", 4), ("/world/records", 4),
    ("/world/matchday-xi", 3), ("/world/timeline", 3), ("/knowledge", 3), ("/news", 2),
    ("/coach", 2), ("/tactics", 2), ("/world/gazette", 2),
]

DWELL = {
    "/": (4, 9), "/world": (3, 9), "/tutorial": (14, 40), "/manual": (16, 45),
    "/world/real-book": (12, 35), "/world/almanac": (8, 22), "/world/records": (6, 16),
    "/world/matchday-xi": (5, 14), "/world/timeline": (7, 18), "/world/gazette": (9, 24),
    "/world/upsets": (7, 18), "/world/dynasties": (8, 20), "/world/spotlight": (6, 15),
    "/world/finals": (6, 16), "/world/noise": (7, 18), "/world/matches": (4, 12),
    "/world/teams": (4, 11), "/world/players": (5, 13), "/world/news": (6, 15),
    "/knowledge": (10, 28), "/coach": (12, 35), "/tactics": (9, 26), "/news": (4, 11),
}
DEFAULT_DWELL = (5, 14)

TRANSITIONS: dict[str, list[tuple[str, float]]] = {
    "/": [("/world", 24), ("/tutorial", 22), ("/manual", 12), ("/register", 8), ("/login", 7), ("/world/real-book", 5), ("/knowledge", 4), ("/news", 3)],
    "/tutorial": [("/manual", 24), ("/world", 18), ("/register", 12), ("/coach", 9), ("/world/real-book", 6), ("/knowledge", 5)],
    "/manual": [("/world", 18), ("/coach", 14), ("/training", 14), ("/tutorial", 9), ("/world/real-book", 6)],
    "/world": [("/world/real-book", 14), ("/world/almanac", 12), ("/world/dynasties", 10), ("/world/matches", 9), ("/world/matchday-xi", 8), ("/world/upsets", 8), ("/world/records", 7), ("/world/timeline", 7), ("/world/players", 5), ("/world/teams", 5), ("/world/spotlight", 6)],
    "/world/real-book": [("/world", 16), ("/world/almanac", 12), ("/manual", 9), ("/tutorial", 8), ("/world/news", 6), ("/world/finals", 5)],
    "/world/dynasties": [("/world", 20), ("/world/upsets", 12), ("/world/real-book", 10), ("/world/records", 8), ("/world/timeline", 6)],
    "/world/upsets": [("/world", 18), ("/world/dynasties", 11), ("/world/real-book", 10), ("/world/noise", 8), ("/world/almanac", 6)],
    "/knowledge": [("/coach", 14), ("/training", 12), ("/manual", 8), ("/world", 10), ("/tactics", 6)],
    "/coach": [("/training", 22), ("/knowledge", 12), ("/tactics", 8), ("/tutorial", 4)],
}
DEFAULT_EXIT_BIAS = 0.35


def _pick_entry(rng: random.Random) -> str:
    total = sum(weight for _, weight in ENTRY_WEIGHTS)
    roll = rng.uniform(0, total)
    acc = 0.0
    for path, weight in ENTRY_WEIGHTS:
        acc += weight
        if roll <= acc:
            return path
    return ENTRY_WEIGHTS[0][0]


def _dwell_ms(rng: random.Random, path: str) -> int:
    low, high = DWELL.get(path, DEFAULT_DWELL)
    seconds = max(1.0, rng.lognormvariate(math.log((low + high) / 2), 0.55))
    seconds = min(seconds, 240.0)
    return int(seconds * 1000)


def _generate(rng: random.Random, days: int) -> list[tuple[str, datetime, str, int, bool]]:
    today = datetime.now(UTC).date()
    rows: list[tuple[str, datetime, str, int, bool]] = []
    for day_offset in range(days):
        day = today - timedelta(days=days - 1 - day_offset)
        weekday = day.weekday()
        base = 1.0 + (0.25 if weekday >= 5 else 0.0) + (day_offset / days) * 0.6
        n_sessions = max(1, int(rng.gauss(13.5 * base, 2.6)))
        for _ in range(n_sessions):
            path = _pick_entry(rng)
            ref = f"seed{rng.getrandbits(40):010x}"
            hour = rng.choice([9, 12, 13, 15, 16, 18, 20, 21, 22, 11])
            minute = rng.randrange(0, 60)
            stamp = datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)
            events_in_session = int(max(1, min(6, rng.expovariate(1 / 3.1) + 1)))
            for depth in range(events_in_session):
                dwell = _dwell_ms(rng, path)
                bounced = dwell < 6000 and rng.random() < 0.8
                rows.append((ref, stamp, path, dwell, bounced))
                stamp = stamp + timedelta(milliseconds=dwell + rng.randrange(400, 4000))
                options = TRANSITIONS.get(path)
                if options and rng.random() > DEFAULT_EXIT_BIAS * (0.7 if depth == 0 else 1.4):
                    total = sum(weight for _, weight in options)
                    roll = rng.uniform(0, total)
                    acc = 0.0
                    nxt = options[-1][0]
                    for candidate, weight in options:
                        acc += weight
                        if roll <= acc:
                            nxt = candidate
                            break
                    path = nxt
                else:
                    break
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the deterministic demo cohort for the behavioural beacon.")
    parser.add_argument("--days", type=int, default=DAYS)
    parser.add_argument("--reset", action="store_true", help="Delete seeded rows first (live beacon rows are never touched).")
    args = parser.parse_args()

    rng = random.Random(SEED)
    rows = _generate(rng, args.days)

    db = SessionLocal()
    try:
        if args.reset:
            removed = db.execute(delete(PageView).where(PageView.seeded.is_(True))).rowcount
            print(f"removed {removed} seeded rows")
        for ref, stamp, path, dwell_ms, bounced in rows:
            db.add(PageView(session_ref=ref, path=path, dwell_ms=dwell_ms, bounced=bounced, seeded=True, created_at=stamp))
        db.commit()
        unique_sessions = len({ref for ref, _, _, _, _ in rows})
        print(f"seeded {len(rows)} page views across {unique_sessions} sessions over {args.days} days")
    finally:
        db.close()


if __name__ == "__main__":
    main()
