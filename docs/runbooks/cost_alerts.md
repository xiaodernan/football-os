# Cost alerts: the monthly ceiling's out-of-band channel

The advisor names a month over its ceiling on a page. This channel is the part that tells somebody without being
asked. It was built as M13 Phase 6 item 21, and the delivery decision is written down here because the item named
delivery as the open question: **a signed webhook plus a stored ledger**. A webhook is the transport every pager,
chat room and email relay accepts, so the platform needs one URL rather than a vendor SDK; the ledger is what
makes "was it sent?" answerable after the HTTP answer is gone.

## What fires

`POST /api/v1/metrics/alerts/check` (admin standing, inherited from the metrics router) is the sweep a scheduler
calls. It recomputes `cost_advisor.monthly_state()` from `model_calls` and raises one row in `ops_alerts` when
`AI_MONTHLY_CEILING_USD` is configured and the month is

- **over its ceiling** -- a `critical` alert, or
- **projected over it** by the month's pace -- a `warning`.

`dedupe_key = cost_monthly_ceiling:<YYYY-MM>:<projected_over|exceeded>` makes each condition one row however many
sweeps see it. A month that is first over its pace and later over its ceiling owns two rows, because a pace
warning and a breach are different facts.

A sweep with no ceiling configured raises nothing: the monthly block says so, and no threshold is invented.

## What leaves the building

With `OPS_ALERT_WEBHOOK_URL` set, the sweep POSTs every undelivered row as JSON. The request carries:

- `X-Football-Alert-Signature: sha256=<hex>` -- HMAC-SHA256 over the **exact request body**, keyed by `APP_SECRET`;
- `X-Football-Alert-Id: <alert id>`;
- a body with `alert`, `kind`, `level`, `month`, `summary`, `detail`, `raised_at`, `sent_at` and
  `signature_version: 1`.

A 2xx stamps `delivered_at` and stops further attempts. A failure records the receiver's own words in
`delivery_error` and retries on the next sweep, up to five attempts; past that the row stays on the ledger,
undelivered, with its last error. With no URL configured the row is `recorded` and the ledger is the channel; a URL
configured later delivers the undelivered rows on the next sweep, so a month already over its ceiling is not
silenced by the channel arriving late.

A receiver that cannot verify the signature should answer 4xx. That is recorded as a delivery error rather than a
success, which is the point of verifying it.

## What an operator does

1. `GET /api/v1/metrics/alerts?state=open` -- what is open, with its delivery state beside it. `pending_delivery`
   counts rows a webhook may still take; a row at the attempt ceiling is not pending, and its `delivery_error` says
   why.
2. `POST /api/v1/metrics/alerts/{alert}/acknowledge` -- record that a human read it. This changes the operator's
   half of the row only: it does not mark anything delivered, and it does not stop the month's figure from being
   recomputed.
3. Decide the budget change in `AI_MONTHLY_CEILING_USD`. The alert changes no routing (§45) and enforces no limit;
   the advisor is still an advisor.

## What this runbook does not claim

- **Delivery is best-effort.** Five failed sweeps and the row stays on the ledger, undelivered. Nothing here
  guarantees a pager received anything, and `delivered_at` is the only field that says a receiver answered 2xx.
- **The sweep runs only when called.** There is no in-process scheduler; if nothing calls
  `POST /metrics/alerts/check`, no alert exists. A deployment wires a cron or an external scheduler to that door.
- **Only the monthly ceiling alerts.** The daily budget and the routing recommendations remain on
  `GET /api/v1/metrics/cost-optimisation`.
- **The figure is the ledger's**, not a provider invoice, and it is recomputed at each sweep rather than carried
  from the sweep that raised the alert.
