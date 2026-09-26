"""§42: a plan is a ceiling read from data, usage is counted from acts, and no payment appears anywhere.

What this file holds the tier to: the matrix is the table rather than a constant; a ceiling refuses before the row
it would exceed exists; the same act cannot spend twice; a period roll-over returns the allowance; what is
published as enforced is exactly what a door refuses on; and no price, currency or provider is anywhere in a
payload, because §42 asks for the architecture before any payment.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import Entitlement, Organization, UsageEvent
from app.services import entitlements as ent
from tests.test_club_academy import session, world  # noqa: F401 — one generated world, the same fixture §40/§41 use
from tests.test_club_reports import ACADEMY, _ask, _team_of, _tenant

ENTITLEMENTS = "/api/v1/entitlements"


def _organization_id(session: Any, slug: str) -> str:  # noqa: ANN001 - the fixture's session
    row = session.scalar(select(Organization).where(Organization.slug == slug))
    assert row is not None
    return str(row.id)


class TestTheMatrixIsData:
    def test_every_plan_times_every_feature_is_stored_and_the_door_reports_the_stored_number(self, client: TestClient, session: Any) -> None:  # noqa: ANN001, E501
        body = client.get(f"{ENTITLEMENTS}/capabilities").json()
        assert body["plans"] == list(ent.PLANS) and len(body["plans"]) == 7
        assert set(body["features"]) == set(ent.FEATURES)
        held = {(row.feature, row.plan): (int(row.limit_value), row.period) for row in session.scalars(select(Entitlement))}
        assert len(held) == 7 * len(ent.FEATURES), "the matrix is total, or a plan silently has no ceiling for a feature"
        assert held[("organizations", "free")] == (1, "month")
        assert body["matrix"]["free"]["organizations"] == [1, "month"], "the published number is the stored one"
        assert body["enforced"] == ["reports_saved"]
        assert set(body["published_not_enforced"]) == set(ent.FEATURES) - {"reports_saved"}

    def test_editing_the_table_changes_the_answer_because_no_door_keeps_its_own_copy(self, client: TestClient, session: Any) -> None:  # noqa: ANN001, E501
        ent.ensure_matrix(session)
        row = session.scalar(select(Entitlement).where(Entitlement.plan == "free", Entitlement.feature == "reports_saved"))
        assert row is not None, "the seed is the only thing that puts these rows there"
        row.limit_value = 0
        session.commit()
        try:
            answer = client.get(f"{ENTITLEMENTS}/capabilities").json()
            assert answer["matrix"]["free"]["reports_saved"][0] == 0, "a ceiling printed from a constant would not have moved"
        finally:
            row.limit_value = 1
            session.commit()

    def test_the_rulebook_offers_nothing_a_payment_could_hang_on(self, client: TestClient) -> None:
        """No pricing *field*, and the sentence that says so is allowed to name the thing it refuses.

        A substring scan would fail on the tier's own disclaimer — "no price, no currency, no payment provider" —
        which is the opposite of a violation, so the check is on the keys: a payload that carried a price would
        have somewhere to carry it.
        """
        body = client.get(f"{ENTITLEMENTS}/capabilities").json()

        def keys(node: Any) -> set[str]:
            if isinstance(node, dict):
                return set(node) | {key for child in node.values() for key in keys(child)}
            if isinstance(node, list):
                return {key for child in node for key in keys(child)}
            return set()

        names = keys(body)
        assert not [name for name in names if any(word in name.lower() for word in ("price", "currency", "amount", "fee", "billing", "provider", "checkout", "trial"))], sorted(names)
        assert "no_payment" in body and "payment" in body["no_payment"]


class TestCeilingsAndUsage:
    def test_an_act_past_the_ceiling_is_refused_before_the_row_exists_and_prints_its_figures(self, client: TestClient, session: Any) -> None:  # noqa: ANN001, E501
        owner, ident = _tenant("Ceiling Bites")
        _team_of(owner, ident, "Under 16s")
        assert _ask(owner, ident).status_code == 200
        second = _ask(owner, ident, window_from="2022-01-01", window_to="2022-12-31")
        assert second.status_code == 409, second.text
        detail = second.json()["detail"]
        assert detail["code"] == "entitlement_limit"
        assert detail["limit"] == 1 and detail["used"] == 1 and detail["period"] == "day" and detail["enforced"] is True
        assert owner.get(f"{ACADEMY}/{ident}/reports").json()["total"] == 1, "the refused act wrote nothing"

    def test_asking_the_same_question_again_does_not_spend_the_ceiling_twice(self, client: TestClient, session: Any) -> None:  # noqa: ANN001, E501
        owner, ident = _tenant("Idempotent Act")
        _team_of(owner, ident, "Under 16s")
        first = _ask(owner, ident)
        again = _ask(owner, ident)
        assert first.status_code == 200 and again.status_code == 200, again.text
        assert again.json()["report"]["id"] == first.json()["report"]["id"]
        rows = list(session.scalars(select(UsageEvent).where(UsageEvent.subject_id == _organization_id(session, ident), UsageEvent.feature == "reports_saved")))
        assert len(rows) == 1 and rows[0].units == 1, "one act, one row — an update is not a second spend"

    def test_a_ceiling_spent_today_is_free_again_tomorrow_because_the_period_is_part_of_the_row(self, client: TestClient, session: Any) -> None:  # noqa: ANN001, E501
        subject = "org_period_probe"
        today = date.today()
        assert ent.guard(session, subject_id=subject, feature="reports_saved", plan="free", source_id="act-one")["remaining"] == 1
        ent.record(session, subject_id=subject, subject_kind="organization", feature="reports_saved", plan="free", source_id="act-one", on=today)
        assert ent.used(session, subject, "reports_saved", on=today) == 1
        assert ent.used(session, subject, "reports_saved", on=today + timedelta(days=1)) == 0, "a daily ceiling does not carry forward"
        assert ent.period_key("month", today) == today.isoformat()[:7]
        assert ent.period_key("day", today) == today.isoformat()

    def test_an_unknown_feature_or_plan_is_answered_as_absent_rather_than_as_an_unlimited_one(self, client: TestClient) -> None:
        refused = client.post(f"{ENTITLEMENTS}/me", json={})
        assert refused.status_code in (404, 405), refused.text
        body = client.get(f"{ENTITLEMENTS}/capabilities").json()
        assert "no_such_feature" in body["refusals"] and "no_such_plan" in body["refusals"], "a ceiling nobody can mistype is not published"


class TestTheOwnReading:
    def test_an_account_reads_only_its_own_metered_feature_and_the_period_it_lives_in(self, client: TestClient, session: Any) -> None:  # noqa: ANN001, E501
        from tests.test_club_academy import _account

        owner = _account("Entitled Account")
        mine = owner.get(f"{ENTITLEMENTS}/me")
        assert mine.status_code == 200, mine.text
        body = mine.json()
        assert body["plan"] == "free", "nothing grants a plan yet, and the door says so rather than implying otherwise"
        assert {row["feature"] for row in body["items"]} == {"organizations"}, "an account is metered on its own features only"
        assert all(row["limit"] == 1 and row["period"] == "month" for row in body["items"])
        assert "sum of `units`" in body["formula"]
        assert body["as_of"] == date.today().isoformat()

    def test_a_stranger_is_not_handed_somebody_elses_usage(self, client: TestClient) -> None:
        refused = client.get(f"{ENTITLEMENTS}/me")
        assert refused.status_code == 401, refused.text
