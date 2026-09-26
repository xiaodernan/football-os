# ruff: noqa: F811 — `session` and `world` are imported to expose §40's fixtures, and a test's parameter
# of the same name is how pytest hands them over; the shadowing is the mechanism, not a redefinition.
"""§42: a plan is a ceiling read from data, usage is counted from acts, and no payment appears anywhere.

What this file holds the tier to: the matrix is the table rather than a constant; a ceiling refuses before the row
it would exceed exists; the same act cannot spend twice; a period roll-over returns the allowance; what is
published as enforced is exactly what a door refuses on; and no price, currency or provider is anywhere in a
payload, because §42 asks for the architecture before any payment.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import Entitlement, Organization, UsageEvent, utc_today
from app.services import entitlements as ent
from app.services.club import organizations as club
from tests.test_club_academy import _joined, session, world  # noqa: F401 — one generated world, the fixture §40/§41 use
from tests.test_club_reports import ACADEMY, CLUB, _account, _ask, _team_of, _tenant

ENTITLEMENTS = "/api/v1/entitlements"


def _organization_id(session: Any, slug: str) -> str:  # noqa: ANN001 - the fixture's session
    row = session.scalar(select(Organization).where(Organization.slug == slug))
    assert row is not None
    return str(row.id)


class TestTheMatrixIsData:
    def test_every_plan_times_every_feature_is_stored_and_the_door_reports_the_stored_number(self, client: TestClient, session: Any) -> None:  # noqa: E501
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
    def test_an_act_past_the_ceiling_is_refused_before_the_row_exists_and_prints_its_figures(self, client: TestClient, session: Any) -> None:  # noqa: E501
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

    def test_a_ceiling_spent_today_is_free_again_tomorrow_because_the_period_is_part_of_the_row(self, client: TestClient, session: Any) -> None:  # noqa: E501
        subject = "org_period_probe"
        today = utc_today()
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
        assert body["as_of"] == utc_today().isoformat(), "the meter and the ceiling it measures roll over on one clock"

    def test_a_stranger_is_not_handed_somebody_elses_usage(self, client: TestClient) -> None:
        refused = client.get(f"{ENTITLEMENTS}/me")
        assert refused.status_code == 401, refused.text


class TestTheTenantsOwnMeter:
    """`GET /club/{ident}/entitlements` — §42's ceiling read through §39's standing rather than a permission.

    The door exists because the enforced ceiling is the tenant's, not the caller's: `/entitlements/me` answers
    for an account and can only ever show `organizations`, so without this door a coach could be refused a
    report by a meter nobody in the tenant could see.
    """

    def test_the_meter_is_the_tenant_s_own_subject_and_holds_every_feature_of_its_kind(self, client: TestClient, session: Any) -> None:  # noqa: E501
        owner, ident = _tenant("Metered Tenant")
        body = owner.get(f"{CLUB}/{ident}/entitlements").json()
        assert body["plan"] == ent.DEFAULT_PLAN and body["subject_kind"] == "organization"
        assert body["subject_id"] == _organization_id(session, ident), "the meter counts the tenant's acts, not the reader's"
        assert {row["feature"] for row in body["items"]} == {
            feature for feature, kind in ent.FEATURES.items() if kind == "organization"
        }, "an account's own feature does not belong on a tenant's meter"
        assert all(
            row["plan"] == ent.DEFAULT_PLAN and row["limit"] == ent.DEFAULT_MATRIX[ent.DEFAULT_PLAN][row["feature"]][0] for row in body["items"]
        ), "the ceiling printed is the stored row of the plan named"
        assert all(row["enforced"] is (row["feature"] in ent.ENFORCED) for row in body["items"]), "what the page may call a rule is exactly what a door refuses on"
        assert (
            body["tier_limits"]["members"] == club.MAX_MEMBERS_PER_ORGANIZATION and body["tier_limits"]["teams"] == club.MAX_TEAMS_PER_ORGANIZATION
        ), "the two kinds of limit are printed apart rather than blended"
        assert body["no_payment"] == ent.NO_PAYMENT

    def test_the_spend_rises_with_the_act_and_falls_back_when_the_act_is_deleted(self, client: TestClient, session: Any) -> None:  # noqa: E501
        owner, ident = _tenant("Spend And Meter")
        _team_of(owner, ident, "Under 16s")

        def reports_row() -> dict[str, Any]:
            return next(row for row in owner.get(f"{CLUB}/{ident}/entitlements").json()["items"] if row["feature"] == "reports_saved")

        before = reports_row()
        assert before["used"] == 0 and before["remaining"] == before["limit"] and before["acts"] == 0
        asked = _ask(owner, ident)
        assert asked.status_code == 200, asked.text
        spent = reports_row()
        assert spent["used"] == 1 and spent["remaining"] == spent["limit"] - 1 and spent["acts"] == 1, "a write is a row, and the count is taken from the rows"
        refused = _ask(owner, ident, window_from="2022-01-01", window_to="2022-12-31")
        assert refused.status_code == 409 and refused.json()["detail"]["code"] == "entitlement_limit"
        assert reports_row()["used"] == 1, "a refusal spends nothing"
        assert owner.delete(f"{ACADEMY}/{ident}/reports/{asked.json()['report']['id']}").status_code == 200
        assert reports_row()["used"] == 0, "the published rule says deleting an act removes its spend, so it had better"

    def test_a_parent_holding_no_staff_permission_is_still_told_what_their_tenant_is_entitled_to(self, client: TestClient) -> None:
        owner, ident = _tenant("Parent Reads The Ceiling")
        guest = _joined(owner, ident, "parent", "Waiting Parent")
        answer = guest.get(f"{CLUB}/{ident}/entitlements")
        assert answer.status_code == 200, answer.text
        body = answer.json()
        assert body["role"] == "parent" and body["read_through"].startswith("standing"), "the door's own sentence names the gate it used"
        assert {row["feature"] for row in body["items"]} == {row["feature"] for row in owner.get(f"{CLUB}/{ident}/entitlements").json()["items"]}, "a ceiling is not a per-role figure"

    def test_a_stranger_hears_the_same_absence_as_at_every_other_door_that_names_a_tenant(self, client: TestClient) -> None:
        owner, ident = _tenant("Metered From Outside")
        nosy = _account("Nosy Neighbour")
        refused = nosy.get(f"{CLUB}/{ident}/entitlements")
        assert refused.status_code == 404 and refused.json()["detail"]["code"] == "no_such_organization"
        assert "limit" not in refused.text, "a plan ceiling of another tenant is not an answer to a stranger"
        assert owner.get(f"{CLUB}/{ident}/entitlements").status_code == 200, "the tenant itself is untouched by the refusal"

    def test_the_day_the_meter_stamps_and_the_day_the_session_door_refuses_on_are_one_day(self, client: TestClient, session: Any) -> None:  # noqa: E501
        """§41's date rule and §42's period key are read by two doors that must not run on two clocks.

        The defect this test exists for: the session door compared `datetime.now(UTC).date()` while the meter
        stamped `date.today()`, so on a host ahead of UTC a tenant's daily report allowance rolled over up to a
        day away from the day its own sessions could be dated — and both figures print on one page. One shared
        `utc_today()` is the fix; this is the witness that keeps the doors from drifting apart silently again.
        """
        owner, ident = _tenant("One Clock Tenant")
        meter = owner.get(f"{CLUB}/{ident}/entitlements").json()
        listing = owner.get(f"{ACADEMY}/{ident}/sessions").json()
        assert listing["today"] == meter["as_of"], "a period key and a date rule printed on one page must name one day"

        saved = _ask(owner, ident)
        assert saved.status_code == 200, saved.text
        row = session.scalar(select(UsageEvent).where(UsageEvent.subject_id == _organization_id(session, ident), UsageEvent.feature == "reports_saved"))  # noqa: E501
        assert row is not None and row.period_key == listing["today"], "the row the meter counted is keyed on the day the tenant's own doors publish"
