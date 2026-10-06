"""Auth routes: register, login, refresh, logout, me (ADR-003)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import (
    create_access_token,
    current_user,
    hash_password,
    inactive_refusal,
    limit,
    new_public_id,
    password_refusal,
    verify_password,
)
from app.core.timeutil import as_utc, is_expired, now_utc
from app.models import AuditLog, RefreshSession, User
from app.schemas import AccountDeleteIn, LoginIn, RegisterIn, TokenPair, UserOut
from app.services import account_deletion

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "fo_refresh"


def _issue_refresh(db: Session, user_id: str) -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    expires = datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days)
    db.add(RefreshSession(id=new_public_id("rs"), user_id=user_id, token_hash=digest, expires_at=expires))
    return raw, digest


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        path="/api/v1/auth",
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)) -> TokenPair:
    limit(request, 5, 300, scope="register")
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "email_taken", "message": "An account already uses this email"})
    user = User(
        id=new_public_id("usr"),
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip(),
        role=payload.role,
    )
    db.add(user)
    db.add(AuditLog(id=new_public_id("aud"), user_id=user.id, action="user.registered", detail={"role": user.role}))
    db.commit()
    refresh, _digest = _issue_refresh(db, user.id)
    db.commit()
    _set_refresh_cookie(response, refresh)
    return TokenPair(
        access_token=create_access_token(user.id, user.role),
        expires_in_seconds=settings.access_token_ttl_minutes * 60,
        demo_mode=settings.is_demo_mode,
    )


@router.post("/login", response_model=TokenPair)
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> TokenPair:
    limit(request, 10, 300, scope="login")
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if user is None or not verify_password(payload.password, user.password_hash):
        # identical error for unknown email and wrong password (no account enumeration)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "invalid_credentials", "message": "Email or password is incorrect"})
    if not user.is_active:
        raise inactive_refusal(message="This account is disabled")
    user.last_login_at = datetime.now(UTC)
    db.add(AuditLog(id=new_public_id("aud"), user_id=user.id, action="user.login", detail={}))
    refresh, _digest = _issue_refresh(db, user.id)
    db.commit()
    _set_refresh_cookie(response, refresh)
    return TokenPair(
        access_token=create_access_token(user.id, user.role),
        expires_in_seconds=settings.access_token_ttl_minutes * 60,
        demo_mode=settings.is_demo_mode,
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> TokenPair:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "no_refresh", "message": "No active session"})
    digest = hashlib.sha256(raw.encode()).hexdigest()
    stored = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == digest))
    if stored is None or is_expired(stored.expires_at):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "refresh_invalid", "message": "Session expired, please sign in again"})
    user = db.get(User, stored.user_id)
    if user is None:
        # `refresh_sessions.user_id` cascades with the account, so an erased account takes this row with it
        # and lands on `refresh_invalid` above. A row that survived its own account is therefore a database
        # that disagrees with itself, and the honest answer is the same 401 rather than a 403 describing an
        # account that is not there — §60's census named both this site and `current_user`; see
        # `docs/SECURITY_AUTHORIZATION_VERIFICATION.md` §9.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "refresh_invalid", "message": "Session expired, please sign in again"})
    if not user.is_active:
        raise inactive_refusal(message="This account is disabled")
    now = now_utc()
    if stored.revoked_at is not None:
        # A refresh token is single-use, so a revoked one arriving back is either the same browser
        # racing its own rotation across parallel requests, or a copy of a cookie someone kept. Age
        # is the only distinction available without a device fingerprint, and it is a real one: the
        # race completes in milliseconds, a replay of a dead cookie does not arrive inside a minute.
        grace = timedelta(seconds=settings.refresh_reuse_grace_seconds)
        if as_utc(stored.revoked_at) + grace < now:
            # Nothing can tell a kept copy from a browser presenting an old cookie it forgot to drop,
            # so the whole account is signed out: every row is destroyed, which is the same thing
            # logout does. Flagging them instead would leave each one inside the grace window below
            # and re-admit the very replay that caused it.
            db.execute(delete(RefreshSession).where(RefreshSession.user_id == stored.user_id))
            db.commit()
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail={"code": "refresh_reused", "message": "This session was signed out because its token was presented twice"},
            )
    else:
        stored.revoked_at = now  # rotate
    new_raw, _ = _issue_refresh(db, user.id)
    db.commit()
    _set_refresh_cookie(response, new_raw)
    return TokenPair(
        access_token=create_access_token(user.id, user.role),
        expires_in_seconds=settings.access_token_ttl_minutes * 60,
        demo_mode=settings.is_demo_mode,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        digest = hashlib.sha256(raw.encode()).hexdigest()
        stored = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == digest))
        if stored is not None:
            # The row is the credential, so signing out destroys it rather than flagging it: a
            # flagged row would still sit inside the rotation grace window below and could be
            # presented back for a fresh session. Nothing else reads these rows after the fact.
            db.delete(stored)
            db.commit()
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.get("/account")
def account_deletion_preview(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, object]:
    """Print the full deletion inventory without changing a row."""
    return account_deletion.preview(db, user)


@router.delete("/account")
def delete_account(
    payload: AccountDeleteIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, object]:
    """Erase the account after a phrase and password check; blocked before any write when a tenant would be orphaned."""
    limit(request, 3, 3600, scope="account_delete")
    if payload.confirm != account_deletion.ACCOUNT_DELETE_PHRASE:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "account_delete_confirmation",
                "message": f'Type {account_deletion.ACCOUNT_DELETE_PHRASE!r} exactly to delete this account',
                "confirm_required": True,
                "expected": account_deletion.ACCOUNT_DELETE_PHRASE,
            },
        )
    if not verify_password(payload.password, user.password_hash):
        raise password_refusal(message="The current password is incorrect")
    try:
        result = account_deletion.erase(db, user)
    except account_deletion.AccountDeletionBlocked as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "organization_owner_required",
                "message": "This account is the last active owner of an organisation with other active members",
                "organisations": error.organizations,
            },
        ) from error
    except account_deletion.AccountDeletionStorageError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "private_media_not_erased", "message": str(error)}) from error
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    return result
