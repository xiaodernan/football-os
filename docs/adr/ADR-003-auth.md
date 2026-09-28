# ADR-003 — Auth: stdlib scrypt + JWT, RBAC from day one

- Status: Accepted · Relates to: §60, §42
- **Context**: Multi-role product (fan/player/coach/manager/scout/academy/admin) needing session auth now and B2B tenancy later. Managed identity providers add a credential dependency the MVP must not require.
- **Problem**: Secure auth that installs with no native-compilation risk and no external service.
- **Options**: (a) Auth.js/Clerk/Supabase Auth; (b) passlib+bcrypt; (c) `hashlib.scrypt` (stdlib) + hand-rolled JWT access token + httpOnly refresh cookie.
- **Decision**: (c). scrypt with per-user random salt and explicit cost parameters; JWT HS256 signed from `APP_SECRET`; role set stored on the user; FastAPI dependencies enforce role + ownership; refresh token rotated, with the live row in `refresh_sessions` acting as the credential itself. (b) was dropped after `passlib`/`bcrypt>=4` incompatibility risk on Python 3.11+; (a) deferred until a real deployment target exists — the token contract is provider-neutral so a swap touches one module.
- **Consequences**: No OAuth/social login yet (added behind the same session contract). Password hash parameters must be versioned in the hash envelope (`scrypt$N$r$p$salt$hash`) to allow future rehash-on-login.
- **Amended 2026-09-23 — rotation needs a reuse grace window.** Strict single-use rotation signed a browser out under its own feet: one page load fans out into several proxied calls through the Next cookie proxy, every call that finds the 15-minute access token expired spends the same single-use refresh cookie, and only the first wins. Two changes, measured rather than assumed (a 19-minute browser walk used to land on `/login` partway through):
  - `REFRESH_REUSE_GRACE_SECONDS` (default 60) — a rotated-out token presented back inside the window is accepted, because that is what a race looks like. Past the window, no property available to the server distinguishes a race from a kept copy of a dead cookie, so it is treated as a copy: **every** `refresh_sessions` row for that account is destroyed and the client is told `refresh_reused`.
  - Logout destroys the row instead of flagging `revoked_at`. A flagged row would sit inside the same grace window and re-admit the credential logout is supposed to kill.
  - The proxy mints at most one refresh per outstanding cookie (single-flight), so the common case never needs the grace window at all.
- **Amended 2026-09-28 — the refresh cookie has to reach the tiers that refresh it.** The rotation above never
  fired from a browser. `fo_refresh` was set with `Path=/api/v1/auth`, and a cookie's path is a filter the
  *browser* applies before a request exists, so neither tier that reads the cookie out of the incoming jar ever
  received it: not the middleware before it renders a protected page, not the proxy before it forwards a call.
  Both then behaved exactly as designed, with nothing to act on. At the 15-minute mark a protected page
  answered `307 → /login` and an API call answered `401`, while a valid 30-day credential sat in the
  reader's own jar — so any session older than the access token ended, and a browser walk past a quarter of an
  hour landed on `/login` partway through. Measured rather than inferred, from a live jar with `fo_access` deleted
  (which is what its 900s `Max-Age` does): **before**, `/my-football` answered `307 → /login?next=%2Fmy-football`
  — without the `expired=1` the middleware sets for a credential it can see has lapsed, because the cookie it
  would have read never arrived, so a lapsed session looked like a signed-out visitor — and a proxied
  `GET /api/v1/careers` answered **401**; **after**, the same two calls answered `307 → /onboarding` (that
  account's own next stop, a page no signed-out visitor reaches) and **200**. The path is one constant,
  `REFRESH_COOKIE_PATH`, which the proxy and the middleware both read. The token stays `httpOnly` and
  `SameSite=Strict`, and the proxy already attached it to every call it forwards to the API, so the wider path
  exposes it to nothing it did not already travel to. The walk now proves the mechanism instead of waiting for
  the clock: three checks drop `fo_access` in the browser, re-load a protected page and re-read a proxied call.
