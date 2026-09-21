"""Password hashing (ADR-003), JWT tokens, RBAC + ownership dependencies, rate limiting."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from typing import TYPE_CHECKING, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db

if TYPE_CHECKING:
    from app.models import User

ROLES = ("fan", "player", "coach", "manager", "scout", "academy", "admin")

_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LEN = 32
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_KEY_LEN)
    return "$".join(
        (
            "scrypt",
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            base64.b64encode(salt).decode(),
            base64.b64encode(digest).decode(),
        )
    )


def verify_password(password: str, envelope: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, hash_b64 = envelope.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(hash_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.b64decode(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(expected, actual)


def create_token(subject: str, token_type: str, ttl_seconds: int, extra: dict[str, Any] | None = None) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {"sub": subject, "type": token_type, "iat": now, "exp": now + ttl_seconds, "jti": secrets.token_urlsafe(12)}
    payload.update(extra or {})
    return jwt.encode(payload, settings.app_secret, algorithm="HS256")


def create_access_token(user_id: str, role: str) -> str:
    return create_token(user_id, "access", settings.access_token_ttl_minutes * 60, {"role": role})


def create_refresh_token(user_id: str) -> str:
    return create_token(user_id, "refresh", settings.refresh_token_ttl_days * 24 * 3600)


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.app_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "token_expired", "message": "Session expired"}) from None
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "token_invalid", "message": "Invalid session"}) from None
    if payload.get("type") != expected_type:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "token_wrong_type", "message": "Invalid token type"})
    return payload


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    from app.models import User

    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "unauthenticated", "message": "Authentication required"})
    payload = decode_token(credentials.credentials, "access")
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "account_inactive", "message": "Account is not active"})
    return user


def require_roles(*roles: str):
    def dependency(user=Depends(current_user)):
        if "admin" in (user.role,) or user.role in roles:
            return user
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "forbidden", "message": "Role not permitted"})

    return dependency


class RateLimiter:
    """Fixed-window in-memory limiter; swap for Redis when horizontally scaled (ADR-001)."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}

    def check(self, bucket: str, limit: int, window_seconds: int) -> None:
        now = time.time()
        hits = [t for t in self._hits.get(bucket, []) if now - t < window_seconds]
        if len(hits) >= limit:
            retry = int(window_seconds - (now - hits[0])) + 1
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "rate_limited", "message": "Too many requests, slow down"},
                headers={"Retry-After": str(max(retry, 1))},
            )
        hits.append(now)
        self._hits[bucket] = hits
        if len(self._hits) > 5000:  # keep the map bounded
            self._hits = {k: v for k, v in self._hits.items() if now - v[-1] < window_seconds}


rate_limiter = RateLimiter()


def limit(request: Request, limit_per_window: int, window_seconds: int = 60, scope: str = "route") -> None:
    if settings.env == "test":
        return
    client = request.client.host if request.client else "unknown"
    rate_limiter.check(f"{scope}:{client}:{request.url.path}", limit_per_window, window_seconds)


def new_public_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(12)}"


def ownership_or_admin(user, owner_id: str, resource: str = "resource") -> None:
    if user.role != "admin" and user.id != owner_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": f"{resource} not found"})


__all__ = [
    "ROLES",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "current_user",
    "require_roles",
    "limit",
    "new_public_id",
    "ownership_or_admin",
]
