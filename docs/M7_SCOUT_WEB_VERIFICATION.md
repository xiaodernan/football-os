# M7 — the §23/§24/§27 scouting screen, verified in a browser

What this certifies: that the `/scout` page does the four things it says it does, on a **production build**,
against the API's own answers — and that a visitor can check each of them without reading a line of code.

* **API tier:** `uvicorn app.main:app --port 8734`, the development PostgreSQL world (300 stored players, 20 clubs).
* **Web tier:** `API_INTERNAL_URL=http://127.0.0.1:8734 next start -p 3213`, `next build` compiled in 67 s.
* **Walk:** `QA_BASE=http://127.0.0.1:3213 node scripts/qa-scout.mjs` → **68/68 checks passed** at 00:24, then **97/97** at 02:57 local time on 2026-09-25 after §23's shortlist panel joined the screen; 7 screenshots in `docs/screenshots/`, exit 0. Both runs against this tree.

The walk is its own script (`apps/web/scripts/qa-scout.mjs`) rather than a section of `visual-qa.mjs`, for the
same reason `qa-market.mjs` is: that walk is another milestone's live working copy, and a page cannot be folded
into it without editing underneath its author.

---

## 1. What landed

| File | Role |
| --- | --- |
| `apps/web/lib/scout.ts` | The response shapes of `/scout/{rules,parse,search,report,compare}`, read off the JSON those routes return. Types only: no derived figure, no re-implementation of an API formula. |
| `apps/web/app/scout/page.tsx` | The server half. `force-dynamic`, `noindex`, a session or a redirect to `/login`, one `serverFetch` of `/scout/rules`, and the two vocabulary panels the workbench reasons over. |
| `apps/web/components/ScoutWorkbench.tsx` | The client half: the sentence box, the candidate table, the waterfall, and the A/B slots. |
| `apps/web/components/ScoutShortlistPanel.tsx` | §23's shortlist on the same screen: open a list from the sentence just typed, add a player the search returned, read the list back, refuse a duplicate, take a player off, delete the list. |
| `apps/web/components/ScoutReportPanel.tsx` | §24's thirteen fields, each with the sentence that produced its figure. |
| `apps/web/components/ScoutComparePanel.tsx` | §27's ten dimensions and 47 measures, and no summary figure. |
| `apps/web/app/robots.ts`, `components/Nav.tsx` | `/scout` disallowed for crawlers; "Scouting" added to the nav. |

## 2. The four rules the screen is built on

Each one exists because the API already prints the evidence, and the page's job is to not lose it.

1. **Words are checked before they are spent.** "Check my words first" calls `/scout/parse`, which reads the
   sentence and touches no row; "Search the world" is a different button. The walk asserts
   `tr[data-candidate]` count is `0` immediately after a parse — 0 rows on screen, and the panel's own eyebrow
   says `no row read`.
2. **A refusal travels with the results.** `refused`, `assumptions`, `unaccounted` and `connectors_ignored`
   print above the table, not in a console. Measured: the phrase 擅长推进 is refused by the parse, refused again
   above the search results, and appears in **no** waterfall row — `a refused phrase never became a filter`.
   The fee assumption prints the number it read (`was read as 20,000,000`), because a bare 2000 万 is only a
   claim once its unit is stated.
3. **The waterfall is the proof.** Every cut prints rows in, what it cut, rows out and the rule. The walk
   re-adds each row from the DOM rather than trusting the figure beside it.
4. **A comparison has no winner.** The panel prints ten leaders and 47 measures; the walk asserts the payload's
   own refusal sentence is on screen *and* that no composite figure was added in the browser.
5. **A list stores membership, so the page shows today's numbers or says nothing.** The shortlist panel prints
   the search's own candidate projection for each member and never a figure of its own; the walk compares the
   two tables cell by cell, and checks that a refusal (`already_listed`, with its figures) stays on screen after
   the re-read that follows it.

## 3. What the walk measured

**Getting in.** Registration through the cookie proxy `HTTP 201`; `/auth/me` `200`; `robots.txt` carries
`Disallow: /scout`; the sitemap's **1037 urls** contain no `/scout`; the page's own `meta robots` is
`noindex, nofollow`; an anonymous visit is a `307` to `/login?next=%2Fscout`.

**The search, arithmetic first.** One sentence — `找一个 22 岁以下、左脚、擅长推进、预算 2000 万以下的中场` — with
role `CM`, produced five cuts and closed on every one of them. The numbers are the page's; the rule column is
abbreviated here, and the page prints each rule in full beside its own cut:

```text
300 − 212 = 88   22 岁以下       stored `age` ≤ the stated value
 88 −  59 = 29   左脚            preferred_foot is that foot or `both`
 29 −   0 = 29   预算 2000 万     the asking-fee ceiling (nothing was cut here, and the row says so)
 29 −   3 = 26   中场            a band keeps a player whose position or any secondary position is in it
 26 −  14 = 12   stated role=CM the role's own occupancy rule
```

Each cut starts where the previous one ended (`300 → 88 → 29 → 29 → 26`), the first cut entered the same pool
the page announced (`300 stored players`), and the last cut's `rows_out` equals the header's match count (12).
All 12 printed rows honour the stated ceiling (ages `21,17,22,19,19,17,22,18,19,21,18,17`) and the stated foot
(`left` × 12), and `headroom` equals `potential − overall` on every row (`68/77/9`, `68/76/8`, `65/71/6`).
A zero-cut filter is printed as a zero-cut filter — the fee cut removed nothing and the row says `29 − 0 = 29`.

**One report.** `POST /scout/report` for `fariel-toban` printed 13 fields; the checks re-derived from those
figures, not from prose:

* stored overall `68`, recomputed `68`, and the card says *agrees with the stored column*;
* percentile `97.7% of 300 rows · 97.5% inside midfield (80 rows)` — a share of the pool and a share of a band
  no larger than it;
* ceiling `77` − overall `68` = headroom `9`;
* weekly wage `2,675` × 52 = season wage `139,100`; value for money `50.879` against `68 × 1,000,000 ÷ 1,336,500`
  = `50.8791…`;
* the four attribute groups are measured over `9 + 6 + 6 + 6 = 27` keys and every one of them is measured, i.e.
  `missing` is empty for a generated row — the sentence that once claimed twenty-four keys is now wrong in
  neither the code nor the page;
* the role-fit gaps are printed as have minus demanded (`60−70=-10`, `62−78=-16`, `68−74=-6`) over 4 attributes;
* `team_fit` is printed as `team_fit: null` with its reason, because no career was named — an unanswered §24
  field stays unanswered;
* the verdict quotes its own deciding figures (`decided by role_fit.mean_gap -14.75 · share_of_band 0.975`),
  and one risk factor matched, while the panel still distinguishes "no factor matched" from "no risk".

**The pair.** `fariel-toban` against `janand-sielelli`: ten dimensions, and the counts chip's `10/47` equals the
number of blocks and measure rows on screen. Every one of the 47 printed deltas equals its own printed
`A − B`. Directions come from §27's vocabulary — `higher_is_greater`, `lower_is_greater`, `none` — and both
sides' stored season totals agree with the sum of their own match lines (`AGREE · AGREE`). Seven of the ten
dimension leaders in this pair are `SPLIT`; the walk accepted only `A AHEAD`, `B AHEAD`, `EVEN`, `SPLIT`,
`UNRESOLVED`, `UNKNOWN` or `NOT SCORABLE`, and the panel's refusal sentence is on screen beside them.

The seven dimensions the page folds away are opened by the walk before they are read: a closed `<details>`
prints no text at all, and a check that reads only the three open blocks would certify a page it had not seen.

## 4. What the walk corrected

Six failures on the first two runs, and each one moved a real fact into the open:

* `BrowserContext.dispose()` does not exist in puppeteer-core 23 — the walk died on it and the open browser kept
  the Node process alive for the caller, so an aborted walk looked like a slow one. Now `close()`, and the abort
  path exits.
* A helper defined in Node does not cross into `page.$$eval`. Three readers (`waterfallRows`, the two report
  tables, the totals table) used the Node-side cell reader; each now carries its own. `qa-market.mjs` documents
  this trap in its own comment and the new walk fell into it anyway.
* `.eyebrow` is set in capitals by the stylesheet, so `includes("300 stored players")` is false on a page that
  says exactly that. The copy checks are case-folded now; the figures are not.
* The direction words are `higher_is_greater`/`lower_is_greater`, not `higher`/`lower`. The walk had invented a
  shorter vocabulary than the API publishes — the same class of error as a stale attribute count, caught by
  reading the page instead of recalling it.
* `ScoutReportPanel` printed `share_of_band * 100` unrounded beside a `share_of_pool` that was rounded to one
  decimal: two shares, two formats, one sentence. Both are `.toFixed(1)` now.
* §27's payload names the sides `left` and `right`, and this page labels them A and B, so a badge reading
  `LEFT` above a column headed `A` was a second vocabulary for the same two players. The badges and count chips
  now say `A AHEAD` / `B AHEAD`; the payload's own sentence, which explains the words `left` and `right`, is
  printed unchanged in the same panel.

* `ScoutShortlistPanel` erased the refusal it had just printed. The panel re-reads the list after every write,
  and the re-read's success cleared `fault` — so `already_listed` appeared and vanished in the same tick, leaving
  the table quietly unchanged and the reader with no sentence explaining why. A re-read now reports its own
  failure but never overwrites the refusal that made it necessary. The walk asserts both halves: the notice stays,
  and the count it complains about is still the old one.
* Two more of that panel's checks were wrong before any of its code was: the eyebrow is uppercase in rendered
  text (`0 MEMBERSHIP ROWS STORED`), and `left` is not a number, so a cell-by-cell comparison of the list table
  against the search table read a matching pair as a mismatch. Both assertions now compare like with like, and
  one waits for the row's own button to stop being disabled rather than sleeping.

## 5. Where this tier stops

* **A shortlist is stored; nothing else here is.** The page now has one persistent object — §23's list, behind
  migration `0015` — and it holds membership and the manager's own words, never a figure; the search, the report
  and the comparison on the same screen stay recomputed per request. The list's own evidence is
  [docs/M7_SHORTLIST_VERIFICATION.md](M7_SHORTLIST_VERIFICATION.md).
* **`team_fit` needs a career slug typed by hand.** The report answers §24's team field only when the reader
  names a career; the walk deliberately left it `null` and asserted that the null is printed with its reason.
* **Rate limits are the server's.** 20 searches, reports and comparisons a minute; a `429` prints the API's own
  sentence rather than being retried quietly.
* **No model call.** Nothing on this screen asks a model anything: §24's verdict is arithmetic over the figures
  above it, and the page says so in the API's words.
* `docs/screenshots/*.png` stay untracked by policy; the walk's 6 images are evidence of a run, not content.
