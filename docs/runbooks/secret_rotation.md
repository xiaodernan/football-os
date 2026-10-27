# Runbook — secret rotation

**When:** a secret is suspected exposed, a holder leaves, or the quarterly rotation in
[`BACKUP_RECOVERY.md`](../BACKUP_RECOVERY.md) comes due.

**What counts as a secret here** (`apps/api/app/core/config.py`):

| Variable | Used for | Default |
|---|---|---|
| `APP_SECRET` | signing access/refresh tokens | `dev-only-insecure-secret`; production **raises** if unset |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | model calls | unset |
| `NEWS_API_KEY` / `FOOTBALL_DATA_API_KEY` | external data | unset |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | database | from `infra/docker-compose.yml` |

`ACCESS_TOKEN_TTL_MINUTES` (default 15) and `REFRESH_TOKEN_TTL_DAYS` (default 30) decide how long a token signed
with the old `APP_SECRET` would otherwise live.

## 1. `APP_SECRET`

1. Generate a new value (32+ random bytes, base64/hex).
2. Set it in the environment/secret store, then restart the API.
3. **Every issued token becomes invalid at once.** There is no dual-secret grace window in this build: the
   verifier checks one secret. Plan the rotation for a low-traffic window and expect all sessions to re-login.
4. Verify: a fresh login succeeds, an old token is rejected (`401`), `/healthz` is green.
5. Rollback: restoring the old value also restores the old tokens' validity — so keep the old value until step 4
   passes, then destroy it.

## 2. Model / data API keys

1. Rotate at the provider (new key first; do not revoke the old one yet).
2. Update the environment and restart the API.
3. Verify the feature that uses the key (a model-backed endpoint, a news/data fetch).
4. Revoke the old key at the provider.
5. If the feature fails, roll back to the old key before revoking it.

## 3. Database credentials

1. `ALTER ROLE <user> WITH PASSWORD '<new>';` on the server.
2. Update `POSTGRES_PASSWORD` (and any `DATABASE_URL`) in the environment/secret store.
3. Restart the API, and confirm the DR scripts still connect — they read host/port/db/user from
   `infra/docker-compose.yml` and take the password from the environment:
   ```bash
   ./scripts/backup_db.sh full   # a backup that cannot connect exits non-zero
   ```
4. Verify a read and a write through the API, not only `psql`.

## What this runbook does not claim

- It does not rotate secrets automatically, and there is no dual-secret window for `APP_SECRET`.
- It does not cover secrets held outside this repository (CI, cloud provider, S3 credentials for backups).
- It does not verify that the old value is gone everywhere; the secret store's audit log is the evidence.
