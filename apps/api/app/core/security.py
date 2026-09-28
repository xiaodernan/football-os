"""Password hashing (ADR-003), JWT tokens, RBAC + ownership dependencies, rate limiting."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Final

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db

if TYPE_CHECKING:
    from app.models import User

ROLES = ("fan", "player", "coach", "manager", "scout", "academy", "admin")

#: The two sentences this platform answers 403 with, registered as a tier's set so `services/club/answers.py`
#: assembles them into the one table every door answers from. Until this landing the table knew one 403
#: (`insufficient_role`, §39's) while three sites raised a second (`account_inactive`) and two raised a third
#: (`forbidden`) without registering either: the ledger said one thing and the territory said three, which is how
#: a test could assert "403 is the matrix's single answer" truthfully while a router minted an off-table 403 a few
#: files away. Each code here still means one thing — `insufficient_role` is "your standing is below this door",
#: `account_inactive` is "this account is switched off" — and the claim that 403 names *one* right belongs to the
#: club matrix's own set, not to this one.
#:
#: Written as constants because §49 asks for one name that publishes the code, guards the door that uses it and
#: builds the answer, so no raise site can spell a third.
INSUFFICIENT_ROLE: Final = "insufficient_role"
ACCOUNT_INACTIVE: Final = "account_inactive"
FORBIDDEN_CODES: Final[frozenset[str]] = frozenset({INSUFFICIENT_ROLE, ACCOUNT_INACTIVE})

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
        raise inactive_refusal(message="Account is not active")
    return user


def standing_check(allowed: Sequence[str], vocabulary: Sequence[str] = ROLES) -> tuple[str, ...]:
    """Refuse a door that asks for a standing no account can hold, before it ever answers a request.

    This is not a style rule. `/knowledge/ingest` shipped gating on `("admin", "staff", "operator")`, and
    `staff`/`operator` are in neither vocabulary the platform has: `ROLES` here holds seven account standings,
    and `services/club/access.py` holds six *tenant* standings. `staff` is real in the club tier as an
    announcement **audience** — a predicate over a roster — which is exactly the kind of word that reads like a
    role and is not one. A door naming an unreachable standing does not leak: it silently means *only the
    reachable half of the list is a policy*, and the day somebody adds a `staff` account role the door's meaning
    changes under the person who did not edit it. So the list is checked against the vocabulary at import, where
    the mistake is a crash in the developer's face, not a sentence in front of a caller.
    """
    named = tuple(str(item) for item in allowed)
    unknown = sorted(set(named) - set(str(item) for item in vocabulary))
    if unknown:
        raise RuntimeError(f"a door asks for {unknown}, which is not a standing any account can hold; the vocabulary is {list(vocabulary)}")
    return named


def role_refusal(*, held: str, required: Sequence[str], message: str) -> HTTPException:
    """The one way this platform turns 'your standing is below this door' into an answer."""
    return HTTPException(
        status.HTTP_403_FORBIDDEN,
        detail={"code": INSUFFICIENT_ROLE, "message": message, "held": held, "required": [str(item) for item in required], "roles": list(ROLES)},
    )


def inactive_refusal(*, message: str) -> HTTPException:
    """The one way this platform turns 'this account is switched off' into an answer."""
    return HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": ACCOUNT_INACTIVE, "message": message})


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
    "ACCOUNT_INACTIVE",
    "FORBIDDEN_CODES",
    "INSUFFICIENT_ROLE",
    "ROLES",
    "hash_password",
    "inactive_refusal",
    "role_refusal",
    "standing_check",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "current_user",
    "limit",
    "new_public_id",
    "ownership_or_admin",
]
