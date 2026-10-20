"""The three helpers every stored-timestamp comparison is supposed to go through (ADR-002).

SQLite returns naive datetimes and PostgreSQL returns aware ones, so any comparison of a stored
timestamp in Python has to normalise before it can be right on both. `app/core/timeutil.py` is
that normalisation, and until now nothing tested it — while three queries bypassed it by
rendering the window boundary as a *date string* and comparing a `DateTime(timezone=True)`
column against it.

What that string actually means depends on the engine asking. On PostgreSQL, `created_at >=
'2026-10-15'` casts the literal to `timestamptz` in the session's `TimeZone`, so the same
question is answered with midnight UTC on one host and 04:00 UTC on another — measured, not
assumed:

    session TimeZone            2026-10-15::timestamptz, as UTC
    UTC                         2026-10-15 00:00:00
    America/New_York            2026-10-15 04:00:00
    Asia/Tokyo                  2026-10-14 15:00:00

`app/core/timeutil.py` is where the answer is supposed to be UTC, and the suite runs on SQLite,
which is the engine where the string happens to work — so nothing could see it.
"""

from __future__ import annotations

import io
import re
import tokenize
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import Select, create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.core.timeutil import as_utc, is_expired, now_utc, utc_midnight
from app.models import Base, User, UserPlayer, XpEvent


class TestAsUtc:
    def test_a_naive_value_is_understood_as_utc(self) -> None:
        assert as_utc(datetime(2026, 10, 15, 12, 0, 0)) == datetime(2026, 10, 15, 12, 0, 0, tzinfo=UTC)

    def test_an_aware_value_is_taken_as_itself(self) -> None:
        elsewhere = datetime(2026, 10, 15, 12, 0, 0, tzinfo=UTC)

        assert as_utc(elsewhere) is elsewhere

    def test_a_non_utc_aware_value_is_converted_not_relabelled(self) -> None:
        # Naive-fit would call this 2026-10-15 12:00 UTC, which is four hours later than it is.
        five_hours_ahead = datetime(2026, 10, 15, 12, 0, 0, tzinfo=UTC).astimezone()

        assert as_utc(five_hours_ahead) == datetime(2026, 10, 15, 12, 0, 0, tzinfo=UTC)


class TestIsExpired:
    def test_a_naive_future_value_is_not_expired(self) -> None:
        # SQLite hands back naive datetimes. Comparing one to an aware `now` raises TypeError, which is
        # exactly why the normalisation step exists and not just a nicety. A naive instant one hour ahead
        # of now — genuinely future on every day the suite runs, unlike a date written into the file.
        assert is_expired(datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)) is False

    def test_a_naive_past_value_is_expired(self) -> None:
        assert is_expired(datetime(2020, 1, 1, 0, 0, 0)) is True

    def test_an_aware_future_value_is_not_expired(self) -> None:
        assert is_expired(datetime.now(UTC) + timedelta(hours=1)) is False


class TestUtcMidnight:
    def test_it_is_the_start_of_the_day_in_utc_and_nothing_else(self) -> None:
        assert utc_midnight(date(2026, 10, 15)) == datetime(2026, 10, 15, 0, 0, 0, 0, tzinfo=UTC)

    def test_it_carries_utc_rather_than_assuming_it(self) -> None:
        assert utc_midnight(date(2026, 10, 15)).tzinfo is UTC

    def test_a_local_date_anchor_can_land_after_utc_now(self) -> None:
        """Why the anchor has to be the UTC day: on a host ahead of UTC it can be a date UTC has not reached.

        This host is UTC+8, so for the last eight hours of every UTC day the process's `date.today()` is
        already tomorrow. A window whose start is that local date's midnight has not begun yet as far as
        the stored timestamps are concerned — every row it was meant to cover is on the wrong side of it.
        The arithmetic is fixed here rather than read off the clock so the case is on the record whichever
        hour the suite runs at.
        """
        utc_evening = datetime(2026, 10, 15, 20, 0, tzinfo=UTC)
        local_date = (utc_evening + timedelta(hours=8)).date()

        assert local_date == date(2026, 10, 16)
        assert utc_midnight(local_date) > utc_evening, "the local anchor starts a window that has not begun"
        assert utc_midnight(utc_evening.date()) <= utc_evening, "the UTC anchor starts a window that contains it"


class TestTheWindowBoundaryBindsADatetime:
    """A date string bound to a datetime column is the defect, stated as what gets sent.

    The three queries that had it compared `DateTime(timezone=True)` columns against `str(date)`.
    The string reaches the engine as text, and each engine then decides for itself what that text
    means. Binding an aware datetime instead makes the boundary unambiguous — the value is a
    timestamptz in UTC, on every engine, whatever the session's timezone.
    """

    def _rows_and_boundary(self, boundary: object) -> tuple[int, tuple[object, ...]]:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()

        now = datetime.now(UTC)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        user = User(id="usr_p", email="p@x.test", password_hash="x", display_name="p")
        db.add(user)
        db.flush()
        player = UserPlayer(id="usr_pl", user_id=user.id, name="p", position="cm", age=17)
        db.add(player)
        db.flush()
        # One exactly on the boundary, one a microsecond before it, one well inside the window.
        db.add_all(
            [
                XpEvent(id="xp_on", user_id=user.id, player_id=player.id, amount=1, reason="r", formula="f", created_at=midnight),
                XpEvent(id="xp_before", user_id=user.id, player_id=player.id, amount=1, reason="r", formula="f", created_at=midnight - timedelta(microseconds=1)),
                XpEvent(id="xp_after", user_id=user.id, player_id=player.id, amount=1, reason="r", formula="f", created_at=now),
            ]
        )
        db.commit()

        captured: list[Select] = []

        # `before_execute`, not `before_cursor_execute`. By the time the DBAPI is asked, SQLite's dialect
        # has formatted whatever it was given into its own timestamp string, so the two shapes this file
        # distinguishes are indistinguishable there. The comparison also embeds its boundary inside the
        # statement rather than handing it over at the DBAPI call, so this is the layer that still has
        # the Python object that was bound.
        @event.listens_for(engine, "before_execute")
        def _capture(_conn, clause, _multiparams, _params, _options) -> None:  # type: ignore[no-untyped-def]
            if isinstance(clause, Select) and "xp_events" in str(clause):
                captured.append(clause)

        count = len(db.scalars(select(XpEvent).where(XpEvent.created_at >= boundary)).all())

        assert captured, "the query should have reached the engine"
        return count, tuple(captured[0].compile().params.values())

    def test_the_boundary_is_sent_as_a_datetime_rather_than_a_date_string(self) -> None:
        boundary = utc_midnight(date(2026, 10, 15))

        _count, bound = self._rows_and_boundary(boundary)

        assert len(bound) == 1
        assert isinstance(bound[0], datetime), "a date string is what the engine reinterpreted per session TimeZone"
        assert getattr(bound[0], "tzinfo", None) is not None, "the boundary has to carry its UTC rather than assume one"

    def test_the_window_starts_at_utc_midnight_exactly(self) -> None:
        boundary = utc_midnight(now_utc().date())

        count, _bound = self._rows_and_boundary(boundary)

        # The row on the boundary and the one inside the window; not the microsecond-before one.
        assert count == 2, "a window bounded by UTC midnight includes the instant it starts and excludes the one before it"

    def test_the_old_shape_bound_a_date_string(self) -> None:
        """The comparison the three queries used, run side by side, so the difference is on the record.

        This case is not a claim that the string answer is wrong on SQLite — it is not, on a host whose
        process and database both sit in UTC. It is here so the reader can see both shapes execute and
        that this suite covers the one the app now uses.
        """
        boundary = str(now_utc().date())

        count, bound = self._rows_and_boundary(boundary)

        assert count == 2
        assert isinstance(bound[0], str), "the shape this file exists to replace"


class TestTheRuleIsHeldAcrossTheApp:
    """The two ways to get this wrong are greppable, so a future edit cannot quietly reintroduce one.

    Both scans read tokens rather than text, because the docstring in `timeutil` that names the old
    shape would otherwise be reported as an instance of it.
    """

    APP = Path(__file__).resolve().parents[1] / "app"

    def _host_clock_days(self) -> list[str]:
        offenders = []
        for path in sorted(self.APP.rglob("*.py")):
            tokens = list(tokenize.generate_tokens(io.StringIO(path.read_text(encoding="utf-8")).readline))
            for first, dot, name in zip(tokens, tokens[1:], tokens[2:], strict=False):
                sequence = (first.type, first.string, dot.string, name.type, name.string)
                if sequence == (tokenize.NAME, "date", ".", tokenize.NAME, "today"):
                    offenders.append(f"{path.relative_to(self.APP.parent)}:{first.start[0]}")
        return offenders

    def test_no_module_takes_its_day_from_the_host_clock(self) -> None:
        # `date.today()` is the host's date. The platform's day is `utc_today()` (app/models:64), and the
        # two disagree for the hours a host ahead of UTC sits past the UTC midnight.
        assert self._host_clock_days() == []

    def test_no_datetime_column_is_compared_against_a_string(self) -> None:
        # A date string reaches PostgreSQL as text that PostgreSQL casts in the session's TimeZone, so
        # the window slides with the host. This is the pattern that was on four lines.
        offenders = []
        pattern = re.compile(r",\s*[A-Za-z_][\w.]*(created_at|updated_at|completed_at|awarded_at|revoked_at|last_login_at)\s*(?:>=|<=|>|<)\s*str\(")
        for path in sorted(self.APP.rglob("*.py")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(self.APP.parent)}:{number}")
        assert offenders == []


