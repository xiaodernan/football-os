"""The policy table and the identity rule for the rate limiter.

Two questions are answered here, and both are policy rather than algorithm:

* **Which budget does this door carry?** A door that reads a row and a door that runs a language model
  cost the product different amounts, so they must not share a ceiling. The table is ordered —
  the first prefix that matches wins — and the order is the whole document: `/api/v1/auth/login`
  must be priced before `/api/v1`, or the generic rule would answer for it.

* **Who is asking?** A rate limit is only as good as the identity it counts. Three answers are
  possible and the order matters: a credentialed caller is counted by its credential (so a whole
  office behind one NAT does not share one budget), a caller arriving through a proxy this
  deployment trusts is counted by the address that proxy reports, and everyone else is counted by
  the address the socket actually came from. A forwarded header from an untrusted peer is not read
  at all — trusting it would let any caller mint a new identity per request by typing one.
"""

from __future__ import annotations

import hashlib
import ipaddress
from contextvars import ContextVar
from typing import Final

from app.core.ratelimit import Decision, Policy

#: Read by `dress_response` so every answer — including one served from the response cache, and the
#: 500 that never comes back through the middleware — carries the budget it was judged against. A
#: cached 200 replayed without these headers would tell a client nothing about the ceiling it is
#: about to hit, and a crash is the answer a client is most likely to retry in a loop.
#:
#: A context variable rather than `request.state` because `dress_response` is handed a response and
#: no request: the crash handler calls it from outside the middleware that holds the request object.
rate_decision_var: ContextVar[Decision | None] = ContextVar("rate_decision", default=None)

#: Doors that answer about the product's own liveness rather than about football. A health check
#: that can be rate-limited is a health check that reports the product down because a monitor was
#: enthusiastic; the docs page is a static document. Neither reads a row or calls a provider.
EXEMPT_PATHS: Final[frozenset[str]] = frozenset(
    {
        "/api/v1/healthz",
        "/api/v1/openapi.json",
        "/api/v1/docs",
        "/api/v1/docs/oauth2-redirect",
    }
)

#: `/api/v1/auth/*` is the one place where the budget is the anti-abuse control: an unlimited login
#: door is a password oracle and an unlimited register door is a free-account farm.
AUTH: Final = Policy("auth", capacity=12, refill_per_second=12 / 60)
#: Doors that spend money or CPU per call: a model call, a retrieval over the corpus, a simulation.
#: The burst is small because these are the calls an operator actually cares about.
EXPENSIVE: Final = Policy("expensive", capacity=24, refill_per_second=0.5)
#: Uploads. One clip is tens of megabytes, so the ceiling is about disk and ffmpeg, not about rows.
UPLOAD: Final = Policy("upload", capacity=8, refill_per_second=0.1)
#: Immutable media for owner-only clips: frame PNGs and byte ranges of the file itself. A browser
#: asking for one page of a report issues dozens of these in a second, so the ceiling is a reader's,
#: not a writer's — `default`'s arithmetic, named for the door it serves.
MEDIA: Final = Policy("media", capacity=240, refill_per_second=40.0)
#: Writes that create rows: community posts, comments, reactions, follows.
WRITE: Final = Policy("write", capacity=60, refill_per_second=1.0)
#: Everything else. 40/s sustained is far above what a reader or a browser walk asks for and far
#: below what a single-host denial of service needs to be interesting.
DEFAULT: Final = Policy("default", capacity=240, refill_per_second=40.0)

#: Prefix → policy, first match wins. Trailing slashes are included on purpose: FastAPI answers
#: `/api/v1/coach/ask`, and a prefix written without its slash would also match `/api/v1/coachwork`.
POLICY_TABLE: Final[tuple[tuple[str, Policy], ...]] = (
    ("/api/v1/auth/", AUTH),
    ("/api/v1/coach/ask", EXPENSIVE),
    ("/api/v1/knowledge/ask", EXPENSIVE),
    ("/api/v1/agents/", EXPENSIVE),
    ("/api/v1/model-router/", EXPENSIVE),
    ("/api/v1/scout/search", EXPENSIVE),
    ("/api/v1/scout/parse", EXPENSIVE),
    ("/api/v1/simulate", EXPENSIVE),
    ("/api/v1/video/upload", UPLOAD),
    # The upload door is one concrete path; every other /video/ path serves bytes to the owner's
    # own report page, which asks for a page's worth of frames per navigation. Pricing bytes-of-media
    # as uploads made the report unreadable the moment the limiter was on: the eighth frame 429'd.
    ("/api/v1/video/", MEDIA),
    ("/api/v1/community/posts", WRITE),
    ("/api/v1/community/comments", WRITE),
    ("/api/v1/community/reactions", WRITE),
    ("/api/v1/community/follows", WRITE),
    ("/api/v1/notifications/preferences", WRITE),
)


def policy_for(path: str) -> Policy | None:
    """The policy a path is judged by, or `None` when the path is exempt.

    Only `/api/v1` is priced. The web tier is served by Next.js and the service plane has its own
    limiter at the edge; a rule written for the API must not silently become a rule about the
    gateway's own `/actuator` surface.
    """
    if path in EXEMPT_PATHS:
        return None
    if not path.startswith("/api/v1/"):
        return None
    for prefix, policy in POLICY_TABLE:
        # A prefix is not a word. `/api/v1/coach/ask` must price that door and not
        # `/api/v1/coach/askers`, which a bare `startswith` would also match — so a prefix ending in
        # a slash matches anything below it, and one that does not must be followed by a slash or the
        # end of the path. Getting this wrong is silent: the request is simply charged the wrong price.
        if path == prefix or path.startswith(prefix if prefix.endswith("/") else prefix + "/"):
            return policy
    return DEFAULT


def _credential_key(authorization: str) -> str:
    """A stable name for a credential that is not the credential.

    The same reasoning as `app.main.caller_identity`: the key is written to Redis where an operator
    can read it, so it must not be the token. A truncated SHA-256 is stable for the token's life and
    useless without it.
    """
    return hashlib.sha256(authorization.encode("utf-8")).hexdigest()[:32]


def _is_trusted(peer: str, trusted: tuple[str, ...]) -> bool:
    """Whether `peer` is one of the proxies whose forwarded address may be believed."""
    try:
        address = ipaddress.ip_address(peer)
    except ValueError:
        return False
    for entry in trusted:
        try:
            if address in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def caller_key(
    *,
    authorization: str,
    peer: str,
    forwarded_for: str,
    trusted_proxies: tuple[str, ...],
) -> str:
    """The identity a request is counted against, as one string.

    Three cases, in order of strength:

    * `acct:<digest>` — the caller presented a credential. Per-account budgets survive NAT, and a
      single account cannot escape its budget by reconnecting.
    * `fwd:<address>` — the peer is a trusted proxy and reported an address. The **left-most** entry
      is the original client: each proxy appends, so the right-most is the one nearest this process,
      which is the proxy itself and would collapse every caller into one bucket.
    * `ip:<address>` — the socket's own peer. An empty peer (an ASGI transport in a test) is named
      `ip:unknown` rather than an empty string, because an empty key would put every such request in
      one bucket and make the gate's own tests fight each other.
    """
    credential = authorization.strip()
    if credential:
        return f"acct:{_credential_key(credential)}"
    if forwarded_for and _is_trusted(peer, trusted_proxies):
        first = forwarded_for.split(",")[0].strip()
        if first:
            return f"fwd:{first}"
    return f"ip:{peer or 'unknown'}"
