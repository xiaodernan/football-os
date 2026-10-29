# M13 verification - the cost ceiling rings a signed bell, and the ledger remembers whether it rang

Phase 6's item 21 asked for an out-of-band alert channel above the monthly AI ceiling, and left one
decision open: what carries the alert. This increment makes that decision - a signed webhook plus a
stored ledger - and lands both halves, with the three admin doors that raise, read and acknowledge it.

Date: 2026-10-30.

## 1. The delivery decision, and why

Every pager, chat room and email relay this project is likely to use accepts an HTTPS POST, so the
channel is one URL and no vendor SDK. Email over SMTP would have made the suite depend on a mailbox,
and a vendor client would have made the alert channel a second thing to configure, pin and mock. The
decision is a webhook, and the reason is stated here rather than discovered by a reader of the code.

The ledger is the other half. An outbound POST is a fact that disappears when the answer does, so the
row is written *before* any attempt and keeps the question "was it sent, and if not why not" answerable
afterwards. It is also the sweep's queue: a failed POST is retried by the next sweep, up to
`MAX_DELIVERY_ATTEMPTS = 5`, because a webhook that was down for one minute swallowing the month's only
warning is the failure this channel exists to prevent.

## 2. What raises, and how often

`apps/api/app/services/ops_alerts.py` recomputes `cost_advisor.monthly_state()` on every sweep. A
sweep raises at most one row, and the row's `dedupe_key` names the condition rather than the reader:

| month state | level | `dedupe_key` | summary it carries |
| --- | --- | --- | --- |
| spend above the ceiling | `critical` | `cost_monthly_ceiling:<YYYY-MM>:exceeded` | `$12.00 spent in 2026-10 against a $10.00 ceiling, $2.00 over` |
| pace projected over the ceiling | `warning` | `cost_monthly_ceiling:<YYYY-MM>:projected_over` | `$4.00 spent in 2026-10, projected $124.00 by month end against a $10.00 ceiling` |

One month over its ceiling raises one row however many sweeps see it. A month first over its *pace* and
later over its ceiling raises the warning and then the critical alert, because those are two different
facts and a pager should hear both. No configured ceiling (`AI_MONTHLY_CEILING_USD=0`) raises nothing,
and the sweep's answer says so through the monthly block it recomputes.

The row's `detail` carries the whole monthly block beside `trigger` and `source`, so the arithmetic
that produced the sentence travels with it. `ALERT_FORMULA` is published in every sweep answer and in
the ledger's listing.

## 3. What leaves the building

- The body is canonical JSON: `sort_keys=True`, separators `(",", ":")`, UTF-8, so the bytes a receiver
  hashes are the bytes that were signed.
- `X-Football-Alert-Signature: sha256=<hex>` is HMAC-SHA256 over those exact bytes, keyed by
  `APP_SECRET` - the platform's own secret, not a second one to configure.
- `X-Football-Alert-Id` names the ledger row; `User-Agent: football-os-ops-alerts/1` names the sender.
- The POST has a 5 s timeout. Any 2xx marks `delivered_at`; anything else (an HTTP error, a refused
  connection, a timeout) is recorded verbatim in `delivery_error` - truncated to 300 characters - and
  attempted again on the next sweep.
- With no `OPS_ALERT_WEBHOOK_URL`, rows are marked `delivery_channel = "recorded"` and the ledger is the
  channel. A webhook configured later delivers the undelivered backlog on the next sweep, so a month
  already over its ceiling does not go unannounced merely because the channel arrived after it did.
- `pending_delivery` means "a webhook would attempt this on the next sweep". With no webhook configured
  it reads 0: a recorded alert is complete in the only channel it has, and counting it as pending would
  make every ledger look like a backlog of failed deliveries.

## 4. The three doors

All three sit under the metrics router's own `standing_check(("admin",))` dependency, so they inherit
the 403 `insufficient_role` refusal the other metrics doors carry; an anonymous caller gets the bearer
check's 401 before any row is read.

| Door | What it does | Refusals it adds |
| --- | --- | --- |
| `GET /api/v1/metrics/alerts` | the ledger newest first, with `total` / `open` / `acknowledged` / `pending_delivery`, `state` filter and `limit` 1-200 | an unknown `state` is 422, not a calm empty list |
| `POST /api/v1/metrics/alerts/check` | one sweep: raise what the month warrants, once, then deliver what is undelivered | none of its own |
| `POST /api/v1/metrics/alerts/{alert}/acknowledge` | stamps `acknowledged_at` and the operator's id, state `acknowledged` | 404 `no_such_alert` for an unknown id |

The 404 is the same absence every private tier gives a caller probing for ids. `errors.no_such_alert`
was added to all three catalogues in the same commit, so the sentence a reader sees is translated.

## 5. The table

`ops_alerts` (migration `0043_ops_alerts.py`) stores the question, never the answer: `id`, `kind`,
`level`, `dedupe_key` (unique), `summary`, `detail`, `state`, `acknowledged_at`, `acknowledged_by`
(`users.id`, `ON DELETE SET NULL`), `delivery_channel`, `delivery_attempts`, `delivered_at`,
`delivery_error`, and the timestamp mixin. One index covers the operator's query
(`ix_ops_alert_state_created` on `state, created_at`). The unique key is the deduplication: the database,
not a reader's memory, is what makes one condition one row.

## 6. Evidence

- **The new file:** `apps/api/tests/test_ops_alerts.py`, 17 cases - no ceiling raises nothing; the pace
  warning and the breach with exact sentences; the dedupe key holding across sweeps; two rows when a
  month moves from pace to breach; last month's spend never read; the formula and limitation published;
  a recorded alert when no webhook is configured; a real local receiver checking the HMAC over the exact
  body; no re-send after delivery; a dead port retried to the attempt ceiling; a late webhook delivering
  a recorded row; the listing's shape; the check door idempotent; the acknowledge door recording the
  operator; the state filter; a 422 for junk state; a 404 for an unknown alert; and the standing checks
  (403 for a player, 401 anonymous) on all three doors.
- **Adjacent suites:** 38 passed across the new file, `test_cost_advisor.py` and `test_locale_claims.py`;
  31 more across `test_metrics.py`, `test_request_metrics.py` and `test_trace_store.py`.
- **Types and lint:** `mypy app` clean over 161 source files; `ruff` clean over the new and patched files.
- **Migration:** `alembic upgrade head` applied `0042 -> 0043` on a fresh SQLite database, and
  `alembic check` answered "No new upgrade operations detected."
- **The live walk:** `.scratch/walk-alerts.py` **29/29** against a live uvicorn on `127.0.0.1:8743` and a
  real local sink on 8899, with `AI_MONTHLY_CEILING_USD=10` and the webhook configured: the month recomputed
  from two seeded `model_calls` rows, the critical sentence checked against the spend the walk itself
  computed, the receiver's signature checked byte for byte, the ledger's delivery fields checked, a second
  sweep raising nothing and sending nothing, the acknowledge and filter doors, the 422, the 404
  `no_such_alert`, the player's 403 and the anonymous 401.
- **The security probe, run G:** 10 passed / 0 failed / 0 server errors in 17.58 s, contract SHA-256
  `59ed99d469adb1b2d9e43b1aa9160af6eb9432dfcede521a00891b0c481640e2`, census **226 secured / 54 public /
  97 private GET paths**, S1 **226 knocked, 226 answered 401**.
- **The contract:** `docs/api/openapi.json` regenerated from the tree - **218 paths / 280 operations** -
  with the three alert doors present.
- **Catalogue gates:** `qa-i18n-literals` 9/9, `qa-locale-tokens` 5/5 (it reads the README table and
  answered "3957 key(s), 3912 translated"), `qa-key-drift` 4/4, `qa-key-drift-witness` 10/10.
- **A debt this commit pays:** item 18's four new doors moved the committed contract but left the three
  probe ledgers quoting run F's 220 / 53 / 95, so ten `test_security_probe_report_currency.py` cases were
  red at HEAD. Run G is measured over the combined contract, and the report, the M12 record, the ROADMAP
  row and the audit's figures now quote it. The full gate suite for item 18 stopped at that red
  (2040 passed, 10 failed) and is rerun after this commit.

## 7. What this does not claim

- **Delivery is best-effort, not guaranteed.** The attempt ceiling and the record are the guarantee;
  a receiver that is down for every attempt in a month will not receive that alert.
- **There is no in-process scheduler.** Something outside the process - cron, an operator, the smoke
  script - must call `POST /metrics/alerts/check`; this build ships the door and the runbook, not a timer.
- **No email, no SMTP, no vendor pager.** The webhook is chosen because a relay can be put behind it;
  the relay itself is not part of this increment.
- **The monthly ceiling is the only condition.** The daily budget stays an advisor recommendation, and
  the per-feature and per-model figures stay advisory.
- **The ledger is not a provider invoice.** Every figure is recomputed from `model_calls`; a demo-mode
  call costs nothing and is counted as such.
- **One URL, one channel.** There is no per-account fan-out and no multi-receiver dispatch.
- **The signature proves possession of `APP_SECRET`, nothing more.** Verifying it is the receiver's job;
  this build signs and records, and does not manage the receiver's trust store.
