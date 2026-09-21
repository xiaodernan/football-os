# SECURITY — FOOTBALL OS

Threat posture owned by the same repo as the code; changes here require an ADR.

## Baseline controls (enforced in code, not aspirational)

| Control | Implementation |
| --- | --- |
| Password storage | `hashlib.scrypt`, N=2^14, r=8, p=1, 16-byte per-user salt, versioned envelope |
| Sessions | Short-lived JWT access token (15 min) + rotating refresh token in httpOnly/SameSite=Strict/Secure cookie; `revoked_tokens` table |
| Authorization | Role-based (`fan/player/coach/manager/scout/academy/admin`) + row ownership checks; default-deny on every route except public SEO/read endpoints |
| Input validation | Pydantic DTOs with strict types, enums, bounds; no raw ORM field assignment (`from_data` allow-lists) |
| SQL injection | SQLAlchemy ORM/parameterised expressions only; no string SQL interpolation |
| XSS | React text escaping by default; no `dangerouslySetInnerHTML`; user content sanitised server-side |
| CSRF | SameSite=Strict cookies + `Origin` check on state-changing routes |
| Rate limiting | In-memory token bucket per IP + per user on auth, coach, AI and upload routes; 429 with `Retry-After` |
| Uploads (M5) | MIME + extension allow-list, size caps, content sniffing, EXIF/GPS stripped, private storage bucket, signed URLs |
| Secrets | `.env` only (git-ignored), `.env.example` documents names; no secret in logs or error payloads; fail fast if `APP_SECRET` is default in `ENV=production` |
| Headers | `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`, CSP on web, HSTS behind TLS |
| Audit | `audit_log` table for auth events, permission changes, deletions, exports |
| Dependencies | `pip-audit` + `npm audit` gate in CI; lockfiles committed |
| Error handling | Uniform error envelope; stack traces never reach clients (spec §74) |

## Data governance

Deletion and export endpoints are user-facing from M1 (spec §61). Youth/minor records: private by default, no precise location, no public video, parental consent flag required before any public surface (spec §40).

## Reporting

See `SECURITY.md` contact placeholder in README; never open a public issue for a vulnerability. Revalidation: run `scripts/security_checklist.md` items before each milestone tag.

## Explicit non-goals for MVP

No payment card data (no PCI scope). No health/medical claims — training advice is labelled as informational, injury-related questions route to a medical professional (spec §62).
