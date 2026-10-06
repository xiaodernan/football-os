"""M12 account erasure: inventory, blockers, one confirmed transaction and private-media cleanup."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import (
    AuditLog,
    Job,
    KnowledgeQuery,
    ModelCall,
    Organization,
    RevokedToken,
    TacticBoard,
    UsageEvent,
    User,
    UserPlayer,
    VideoAsset,
)
from app.services.tactics.plan import tactical_systems

API = "/api/v1"
PASSWORD = "strong-pass-1234"


def _register(client, email: str) -> str:  # type: ignore[no-untyped-def]
    response = client.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "Delete Me",
            "role": "player",
            "accepts_data_policy": True,
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["access_token"])


def _sign_in(client, token: str) -> None:  # type: ignore[no-untyped-def]
    client.headers.update({"Authorization": f"Bearer {token}"})


def _account_id(client) -> str:  # type: ignore[no-untyped-def]
    response = client.get(f"{API}/auth/me")
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


def _authored_board(name: str) -> dict[str, object]:
    """A board as §4's plan authors it.

    `POST /boards` validates an eleven-a-side arrangement, so a name and an origin slug are not a
    payload: this case first sent those two fields and read `422 phase_in: 0 positions, expected 11`,
    which is the contract refusing a board that could not have been drawn. The positions come from the
    same plan the boards suite draws them from rather than being retyped here.
    """
    system = tactical_systems()[0]
    return {
        "name": name,
        "note": "private",
        "origin_system": system.slug,
        "phase_in": system.phase_in.as_dict(),
        "phase_out": system.phase_out.as_dict(),
    }


def test_account_deletion_requires_a_session_and_exact_confirmation(client) -> None:  # type: ignore[no-untyped-def]
    assert client.get(f"{API}/auth/account").status_code == 401
    assert client.request("DELETE", f"{API}/auth/account", json={"confirm": "DELETE", "password": PASSWORD}).status_code == 401

    email = f"delete-{uuid4().hex[:10]}@example.test"
    token = _register(client, email)
    _sign_in(client, token)
    account_id = _account_id(client)

    refused = client.request("DELETE", f"{API}/auth/account", json={"confirm": "delete", "password": PASSWORD})
    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "account_delete_confirmation"

    wrong_password = client.request("DELETE", f"{API}/auth/account", json={"confirm": "DELETE", "password": "wrong-pass-0000"})
    assert wrong_password.status_code == 403
    assert wrong_password.json()["detail"]["code"] == "invalid_password"

    with SessionLocal() as session:
        assert session.get(User, account_id) is not None
        assert session.scalar(select(func.count()).select_from(User).where(User.id == account_id)) == 1


def test_confirmed_deletion_erases_rows_media_and_identity(client) -> None:  # type: ignore[no-untyped-def]
    email = f"erase-{uuid4().hex[:10]}@example.test"
    token = _register(client, email)
    _sign_in(client, token)
    account_id = _account_id(client)

    player = client.post(
        f"{API}/players",
        json={"name": "Erasable Player", "position": "CM", "age": 24, "level": "intermediate", "preferred_foot": "right", "goal": "become_box_to_box"},
    )
    assert player.status_code == 201, player.text
    board = client.post(f"{API}/boards", json=_authored_board("Erase Board"))
    assert board.status_code == 201, board.text
    organization = client.post(f"{API}/club", json={"name": f"Erase Solo Club {uuid4().hex[:8]}", "kind": "club", "country": "GB"})
    assert organization.status_code == 200, organization.text
    organization_id = str(organization.json()["organization"]["id"])

    asset_id = f"vid_{uuid4().hex[:12]}"
    storage_key = f"video/{account_id}/{asset_id}.mp4"
    original = Path(settings.storage_dir) / storage_key
    frames = Path(settings.storage_dir) / "frames" / asset_id
    original.parent.mkdir(parents=True, exist_ok=True)
    frames.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"private-video" * 12)
    (frames / "frame-0000.ppm").write_bytes(b"frame-zero")
    (frames / "frame-0001.ppm").write_bytes(b"frame-one")

    job_id = f"job_{uuid4().hex[:12]}"
    call_id = f"mc_{uuid4().hex[:12]}"
    query_id = f"kqy_{uuid4().hex[:12]}"
    usage_id = f"use_{uuid4().hex[:12]}"
    jti = uuid4().hex
    with SessionLocal() as session:
        session.add(
            VideoAsset(
                id=asset_id,
                owner_id=account_id,
                title="Private clip",
                filename="private.mp4",
                storage_key=storage_key,
                content_type="video/mp4",
                size_bytes=original.stat().st_size,
                sha256="a" * 64,
                status="analysed",
                frame_count=2,
                data_origin="user",
                is_demo_data=False,
            )
        )
        session.add(Job(id=job_id, type="video.analyse", status="COMPLETED", payload={"asset_id": asset_id}, progress=100, attempts=1, max_attempts=3, user_id=account_id))
        session.add(ModelCall(id=call_id, provider="demo", model="rule", feature="account-test", user_id=account_id, input_tokens=2, output_tokens=3))
        session.add(KnowledgeQuery(id=query_id, user_id=account_id, question="my private question", mode="hybrid", answered=True))
        session.add(
            UsageEvent(
                id=usage_id,
                subject_id=account_id,
                subject_kind="user",
                feature="coach_messages",
                plan="free",
                period_key="2026-09",
                source_id=job_id,
                units=1,
                recorded_on="2026-09-29",
            )
        )
        session.add(RevokedToken(jti=jti, user_id=account_id, expires_at=datetime.now(UTC) + timedelta(days=1)))
        session.commit()

    preview = client.get(f"{API}/auth/account")
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["can_delete"] is True
    assert payload["confirmation"] == {"phrase": "DELETE", "password_required": True}
    assert payload["deletes"]["rows"]["video_assets.owner_id"] == 1
    assert payload["deletes"]["video_bytes"] == original.stat().st_size
    assert payload["deletes"]["organizations"][0]["id"] == organization_id

    deleted = client.request("DELETE", f"{API}/auth/account", json={"confirm": "DELETE", "password": PASSWORD})
    assert deleted.status_code == 200, deleted.text
    receipt = deleted.json()
    assert receipt["deleted"] is True and receipt["identity_retained"] is False
    assert receipt["rows_erased"] >= 1 and receipt["video_assets_erased"] == 1
    assert receipt["files_removed"] == 3 and receipt["bytes_removed"] > 0
    assert receipt["organizations_deleted"]

    assert client.get(f"{API}/auth/me").status_code == 401
    login = client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 401
    assert not original.exists()
    assert not frames.exists()

    with SessionLocal() as session:
        assert session.get(User, account_id) is None
        assert session.get(UserPlayer, player.json()["id"]) is None
        assert session.get(TacticBoard, board.json()["id"]) is None
        assert session.get(Organization, organization_id) is None
        assert session.get(VideoAsset, asset_id) is None
        assert session.get(Job, job_id) is None
        assert session.get(KnowledgeQuery, query_id) is None
        assert session.get(RevokedToken, jti) is None
        assert session.scalar(select(func.count()).select_from(UsageEvent).where(UsageEvent.id == usage_id)) == 0
        retained_call = session.get(ModelCall, call_id)
        assert retained_call is not None and retained_call.user_id is None
        assert session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.user_id == account_id)) == 0
        account_audit = session.scalar(select(AuditLog).where(AuditLog.action == "account.deleted").order_by(AuditLog.created_at.desc()))
        assert account_audit is not None
        assert account_audit.detail["identity_retained"] is False
        assert email not in str(account_audit.detail)


def test_an_escaping_storage_key_stops_the_erasure_before_a_single_write(client) -> None:  # type: ignore[no-untyped-def]
    """`storage_key` is a stored string, so a path that leaves private storage must refuse the delete.

    The containment check is the only thing between a corrupted or hostile `video_assets` row and an
    `unlink()` on an arbitrary path, and it runs **before** the database transaction begins — a run that
    removed somebody else's file and then failed to erase the account would be the worst of both. This
    case was written because a planted-defect probe found the guard unguarded: deleting the check turned
    no case red, since every other case stores a key the service itself built.
    """
    email = f"escape-{uuid4().hex[:10]}@example.test"
    token = _register(client, email)
    _sign_in(client, token)
    account_id = _account_id(client)

    storage_root = Path(settings.storage_dir)
    outside = storage_root.parent / f"not-private-{uuid4().hex[:8]}.bin"
    outside.write_bytes(b"belongs to no account and to no erasure")
    asset_id = f"vid_{uuid4().hex[:12]}"
    try:
        with SessionLocal() as session:
            session.add(
                VideoAsset(
                    id=asset_id,
                    owner_id=account_id,
                    title="Escaping clip",
                    filename="escape.mp4",
                    storage_key=f"../{outside.name}",
                    content_type="video/mp4",
                    size_bytes=outside.stat().st_size,
                    sha256="b" * 64,
                    status="analysed",
                    frame_count=0,
                    data_origin="user",
                    is_demo_data=False,
                )
            )
            session.commit()

        refused = client.request("DELETE", f"{API}/auth/account", json={"confirm": "DELETE", "password": PASSWORD})
        assert refused.status_code == 503, refused.text
        assert refused.json()["detail"]["code"] == "private_media_not_erased"
        assert outside.exists(), "the erasure removed a file outside private storage before it refused"
        assert client.get(f"{API}/auth/me").status_code == 200, "a refused erasure must leave the account standing"
        with SessionLocal() as session:
            assert session.get(User, account_id) is not None
            assert session.get(VideoAsset, asset_id) is not None
    finally:
        outside.unlink(missing_ok=True)


def test_last_owner_with_other_active_members_blocks_before_any_change(client) -> None:  # type: ignore[no-untyped-def]
    owner_email = f"owner-{uuid4().hex[:10]}@example.test"
    owner_token = _register(client, owner_email)
    _sign_in(client, owner_token)
    owner_id = _account_id(client)
    organization = client.post(f"{API}/club", json={"name": f"Shared Club {uuid4().hex[:8]}", "kind": "club", "country": "GB"})
    assert organization.status_code == 200, organization.text
    slug = str(organization.json()["organization"]["slug"])
    organization_id = str(organization.json()["organization"]["id"])

    member_email = f"member-{uuid4().hex[:10]}@example.test"
    client.headers.pop("Authorization", None)
    member_token = _register(client, member_email)
    _sign_in(client, owner_token)
    invite = client.post(f"{API}/club/{slug}/invites", json={"email": member_email, "role": "coach"})
    assert invite.status_code == 200, invite.text
    _sign_in(client, member_token)
    accepted = client.post(f"{API}/club/{slug}/accept")
    assert accepted.status_code == 200, accepted.text

    _sign_in(client, owner_token)
    preview = client.get(f"{API}/auth/account")
    assert preview.status_code == 200, preview.text
    assert preview.json()["can_delete"] is False
    assert [row["id"] for row in preview.json()["blocking_organizations"]] == [organization_id]

    refused = client.request("DELETE", f"{API}/auth/account", json={"confirm": "DELETE", "password": PASSWORD})
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "organization_owner_required"

    with SessionLocal() as session:
        assert session.get(User, owner_id) is not None
        assert session.get(Organization, organization_id) is not None
