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
from app.core.rate_policy import caller_key
from app.core.ratelimit import Policy, get_limiter

if TYPE_CHECKING:
    from app.models import User

ROLES = ("fan", "player", "coach", "manager", "scout", "academy", "admin")

#: The three sentences this platform answers 403 with, registered as a tier's set so `services/club/answers.py`
#: assembles them into the one table every door answers from. Until this landing the table knew one 403
#: (`insufficient_role`, §39's) while three sites raised a second (`account_inactive`) and two raised a third
#: (`forbidden`) without registering either: the ledger said one thing and the territory said three, which is how
#: a test could assert "403 is the matrix's single answer" truthfully while a router minted an off-table 403 a few
#: files away. Each code here still means one thing — `insufficient_role` is "your standing is below this door",
#: `account_inactive` is "this account is switched off", `invalid_password` is "the password you just typed for
#: this act is not the one on the account" — and the claim that 403 names *one* right belongs to the club matrix's
#: own set, not to this one.
#:
#: `invalid_password` is the third code, and §60's census named the gap before the route that needed it landed:
#: `DELETE /auth/account` spells a confirmation password and answered 403 from `auth.py` itself, a module that
#: registers nothing. The census case that bans a third 403 holder went red on it while that route was being
#: written, so the code is registered here with its own builder rather than the door keeping the literal.
#:
#: Written as constants because §49 asks for one name that publishes the code, guards the door that uses it and
#: builds the answer, so no raise site can spell a third.
INSUFFICIENT_ROLE: Final = "insufficient_role"
ACCOUNT_INACTIVE: Final = "account_inactive"
INVALID_PASSWORD: Final = "invalid_password"
FORBIDDEN_CODES: Final[frozenset[str]] = frozenset({INSUFFICIENT_ROLE, ACCOUNT_INACTIVE, INVALID_PASSWORD})

#: The answers this module mints that are not 403, registered for the same reason the 403s are: it is the
#: platform's own tier, and the codes above are raised *here* (`decode_token`, `current_user`, the limiter,
#: `ownership_or_admin`). Measured before this landing, the answer table knew none of them while six raise
#: sites did — 401 for a session that proves nothing, 429 for a budget or a burst, 404 for an owner check that
#: answers absence rather than refusal (§51's shape: `ownership_or_admin` is a 404 by design, so an id another
#: account holds is not discoverable through it). `tests/test_answer_census.py` reads the tree and holds each
#: of these sites to the row registered here.
UNAUTHORIZED_CODES: Final[frozenset[str]] = frozenset({"token_expired", "token_invalid", "token_wrong_type", "unauthenticated"})
TOO_MANY_REQUESTS_CODES: Final[frozenset[str]] = frozenset({"rate_limited"})
NOT_FOUND_CODES: Final[frozenset[str]] = frozenset({"not_found"})

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
    if user is None:
        # The row is gone: the account was erased, or the token was minted for an id that never existed.
        # There is no identity here to be forbidden from anything, so this is the same 401 an undecodable
        # token earns — answering 403 `account_inactive` described a switched-off account that is not there,
        # and §51 gives that code one meaning. `tests/test_account_deletion.py::
        # test_confirmed_deletion_erases_rows_media_and_identity` is what read the difference.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "unauthenticated", "message": "Authentication required"})
    if not user.is_active:
        raise inactive_refusal(message="Account is not active")
    return user


def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """The session, when one is carried, or None. The same checks (valid token, row exists, active) as
    current_user, but answering None instead of 401 — for doors any reader may open with a signed-in or signed-out face."""
    try:
        return current_user(credentials=credentials, db=db)
    except HTTPException:
        return None


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


def password_refusal(*, message: str) -> HTTPException:
    """The one way this platform answers a re-typed password that does not match the stored hash.

    §60's census reserves a status literal to the two modules that own the codes; a door that spells 403
    is a door whose refusal is missing from the assembled table, so account erasure raises through here.
    """
    return HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": INVALID_PASSWORD, "message": message})


#: One `Policy` per (scope, ceiling, window) the doors publish, built once. `Policy` validates its own
#: arithmetic in `__post_init__`, and a door called a thousand times a second must not re-run that
#: validation or re-allocate the object on every call.
_DOOR_POLICIES: dict[tuple[str, int, int], Policy] = {}


def _door_policy(scope: str, limit_per_window: int, window_seconds: int) -> Policy:
    """The token bucket that means what `limit_per_window per window_seconds` used to mean.

    Burst `limit_per_window`, sustained `limit_per_window / window_seconds` — both numbers the fixed
    window already published, so no door's stated ceiling moves. What changes is the boundary: a fixed
    window admits `2 × limit` across one (`limit` at 00:59.9 and `limit` again at 01:00.1), while a
    bucket admits `capacity + rate × t` over *any* interval, which is the property the `Retry-After`
    on the refusal actually promises.
    """
    key = (scope, limit_per_window, window_seconds)
    policy = _DOOR_POLICIES.get(key)
    if policy is None:
        policy = Policy(scope, capacity=limit_per_window, refill_per_second=limit_per_window / window_seconds)
        _DOOR_POLICIES[key] = policy
    return policy


def limit(request: Request, limit_per_window: int, window_seconds: int = 60, scope: str = "route") -> None:
    """Charge this door against the same tier, the same identity and the same clock as the middleware.

    This used to be a second limiter — a fixed window in a process-local dict, keyed on the socket's
    peer — and two things were wrong with it that no tuning inside it could fix. Behind this project's
    own edge every caller arrives from the proxy's address, so one bucket counted the whole internet;
    and a caller presenting a credential was counted by address anyway, so one account could spend
    another's budget by sharing its NAT. `caller_key` is the one identity rule now and `get_limiter`
    the one tier: process-local when no store is configured, cluster-wide when one is, and the answer
    says which (`X-RateLimit-Scope`).

    The path stays in the key, and it has to. `scope` is not a door identifier: the tree reuses
    `academy_write` at four different ceilings and `club_write` at three, so a bucket per scope would
    merge doors that were priced apart and let whichever was called last decide the ceiling for all of
    them. The method is in it for the same reason one level down — `/careers/{ident}/tickets` is a GET
    priced at 60 a minute and a PUT priced at 20, and without the verb those are one bucket: twenty
    writes leave the read door serving nothing, against a ceiling it publishes as sixty.
    `test_a_read_door_and_a_write_door_on_one_path_keep_their_own_budgets` holds that apart.

    The bound on distinct buckets is `ratelimit.MAX_LOCAL_BUCKETS`, and evicting one there is
    safe for the reason its own comment gives — the shared store is the authority, so an evicted
    pre-filter bucket costs a round trip, not a budget.
    """
    if settings.env == "test":
        return
    policy = _door_policy(scope, limit_per_window, window_seconds)
    identity = caller_key(
        authorization=request.headers.get("authorization", ""),
        peer=request.client.host if request.client else "",
        forwarded_for=request.headers.get("x-forwarded-for", ""),
        trusted_proxies=settings.rate_limit_trusted_proxies,
    )
    key = f"door:{scope}:{request.method}:{identity}:{request.url.path}"
    decision = get_limiter(settings.rate_limit_redis_url).decide(key, policy)
    if not decision.allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "rate_limited",
                "message": f"Too many requests for {scope}; retry in {max(1, decision.retry_after)}s",
            },
            headers={"Retry-After": str(max(1, decision.retry_after))},
        )


def new_public_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(12)}"


def ownership_or_admin(user, owner_id: str, resource: str = "resource") -> None:
    if user.role != "admin" and user.id != owner_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": f"{resource} not found"})


__all__ = [
    "ACCOUNT_INACTIVE",
    "FORBIDDEN_CODES",
    "INSUFFICIENT_ROLE",
    "INVALID_PASSWORD",
    "NOT_FOUND_CODES",
    "ROLES",
    "TOO_MANY_REQUESTS_CODES",
    "UNAUTHORIZED_CODES",
    "hash_password",
    "inactive_refusal",
    "password_refusal",
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
