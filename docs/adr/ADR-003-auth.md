# ADR-003 — Auth: stdlib scrypt + JWT, RBAC from day one

- Status: Accepted · Relates to: §60, §42
- **Context**: Multi-role product (fan/player/coach/manager/scout/academy/admin) needing session auth now and B2B tenancy later. Managed identity providers add a credential dependency the MVP must not require.
- **Problem**: Secure auth that installs with no native-compilation risk and no external service.
- **Options**: (a) Auth.js/Clerk/Supabase Auth; (b) passlib+bcrypt; (c) `hashlib.scrypt` (stdlib) + hand-rolled JWT access token + httpOnly refresh cookie.
- **Decision**: (c). scrypt with per-user random salt and explicit cost parameters; JWT HS256 signed from `APP_SECRET`; role set stored on the user; FastAPI dependencies enforce role + ownership; refresh token rotated and revocable in `revoked_tokens`. (b) was dropped after `passlib`/`bcrypt>=4` incompatibility risk on Python 3.11+; (a) deferred until a real deployment target exists — the token contract is provider-neutral so a swap touches one module.
- **Consequences**: No OAuth/social login yet (added behind the same session contract). Password hash parameters must be versioned in the hash envelope (`scrypt$N$r$p$salt$hash`) to allow future rehash-on-login.
