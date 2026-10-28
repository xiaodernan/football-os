# Runbook — erasure

**When:** an account asks to be deleted, a guardian asks for a child's data to be erased, or a retention
review needs the inventory of what a tenant holds about one child.

Two erasures live in different places and must not be confused:

- **An account** — `GET`/`DELETE /api/v1/auth/account`, backed by `app/services/account_deletion.py`.
- **A child's data in one tenant** — `GET`/`DELETE /api/v1/club/academy/{ident}/players/{player}/data`,
  backed by `app/services/club/academy.py`.

## 1. Account deletion

Always print the receipt first — it changes nothing:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/v1/auth/account"
```

It answers `can_delete`, the rows and video assets that would go, the rows **retained anonymized**, the
organisations deleted/left, and any **blocking** organisation. A last active owner cannot delete while other
active members still use the tenant (`AccountDeletionBlocked` → the door's 409 with the blocking list).

Then delete, with the phrase **and** the password:

```bash
curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"confirm": "<phrase from the preview>", "password": "<password>"}' \
  "$API/api/v1/auth/account"
```

A wrong phrase or password removes nothing. What happens, in order: video originals and frames are unlinked
from private storage **before** the database transaction starts; the user's organisations are deleted or
left; `jobs`, `knowledge_queries`, `revoked_tokens` and the user's `usage_events` are deleted;
`model_calls.user_id` and `audit_logs.user_id` are **nulled** (cost totals and action counts survive without
identity, and the audit detail is cleared); an `account.deleted` audit row is written with no user id.

## 2. A child's data in a tenant

Inventory first — what this tenant holds about one child, per table, with the column list and the never-held
list:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$API/api/v1/club/academy/$ORG/players/$PLAYER/data"
```

Then erase. **Without `confirm=true` this is a dry run that removes nothing:**

```bash
curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" \
  "$API/api/v1/club/academy/$ORG/players/$PLAYER/data?confirm=true"
```

`DELETE /api/v1/club/academy/$ORG/plans/$PLAN?confirm=true` erases one development plan and its rows.

## 3. Verify

- The erase response's counts match the preview's (a difference means the rows moved between the two reads).
- `GET /auth/account` now answers `no_such_account`/401 for the deleted account.
- The `account.deleted` audit row exists with `identity_retained: false`.
- For a child: the inventory after the erase answers zero rows, and another tenant's inventory is unchanged.

## What this runbook does not claim

- It does not erase rows the retention policy requires an operator to keep (see `docs/DATA_GOVERNANCE.md`).
- It does not verify guardianship; a guardian consent is self-declared, and `limitations()` says so.
- It does not touch backups. A row in a dump is erased when that dump ages out; see
  [`full_restore.md`](full_restore.md) for what a restore brings back.
