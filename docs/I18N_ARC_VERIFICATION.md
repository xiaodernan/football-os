# §81 — the interface in the reader's language, and the gates that hold it there

What this certifies: that every string a reader sees on the web tier is read from a **catalogue**, in one
of three languages, and that four gates refuse the day it stops being true.

The arc began as a copy gate with a ceiling and became something else: a gate can count what it can see,
and what it could not see turned out to be most of the copy in the tree. Every number below is measured
on the tree this document names, and every figure in it is reproducible by running the gate that produced
it.

---

## 1. The claim

| what | where it lives | what it says |
| --- | --- | --- |
| the copy gate | `apps/web/scripts/qa-i18n-literals.mjs` | **5 checks**, three floors at 0, **3479 key calls** checked for existence *and* for their values |
| the field-name gate | `apps/web/scripts/qa-field-labels.mjs` | **2 checks**: no two panels on one page may give a field the same accessible name |
| the metadata gate | `apps/web/scripts/qa-metadata-title.mjs` | **165 checks**: every page's tab and heading agree, and neither is a load-time literal |
| the crawl gate | `apps/web/scripts/qa-crawl-policy.mjs` | **9 checks**: the three files that decide what a crawler may see reconcile against every page's own `robots:` |

The three catalogues hold **3636 keys each** — 3554 translated in Simplified Chinese, 3555 in
Traditional, and 82 that are *identical* in every catalogue because they are technical tokens (a product
name, an enum, a unit). `apps/web/messages/README.md` carries those figures, and
`apps/api/tests/test_locale_claims.py` recomputes them.

## 2. The shapes, and what each one is

The copy gate's first three shapes were the ones the arc found by reading the code:

* **JSX text** — `>No round played yet<`. The copy the reader sees, standing between two tags.
* **A label-ish attribute** — `title="…"`, `label="…"`, `placeholder="…"`, `aria-label="…"`.
* **A label-ish object property** — `metadata = { title: "…" }`, `back={{ label: "…" }}`.

The **fifth shape** was found on 2026-10-21, and it is the one that matters: a **string literal that
reaches the reader from somewhere else**. The scout's compare panel prints `A AHEAD` from a helper, so no
JSX text, no label attribute and no label property ever saw it — the gate reported zero while the page
was English. The class held **61** sites across twenty-six files, and it now holds **0**. A **template** is
part of the same shape and is read as the one sentence it is: `` `${method} ${path} was refused with ${status}` ``
is one catalogue key with placeholders, not five fragments. The template class held **26** sentences
across eighteen files, and it now holds **0** too.

The exclusions are **structural**, so a new class name or a new API field does not need an allowlist entry
to keep the gate quiet: an import specifier, a naming attribute, a `data-` hook, a class name (in an
expression, in a template, or held in a variable), a style value, a comparison operand, a schema.org type,
field or vocabulary value, a snake_case property, a language tag, a colour, a measurement, a byte unit, a
path, a query parameter, a cookie, a date or time format, a field name, an SVG reference, a locale's own
name, the framework's own directive, a CSS custom property, and a marker that matches the tier's own
wording (`line.startsWith("not in this build")` matches the API's sentence rather than writing one).

## 3. The sixth check: a key's values are part of the contract

A key the catalogue does not hold is a **runtime error** in next-intl — `MISSING_MESSAGE` — not a build
error, so the page renders an exception instead of a sentence and nothing says so. The gate's third check
has held that since the arc began.

Its **fifth** check holds the other half, and it found four pages that were broken in a way nobody could
see:

* the scout's rules panel printed **`{default} by default, {max} at most`** in the column that should read
  "Search limits", and **`{count} phrases (articles, fillers and conjunctions in six languages)`** in the
  column that should read "Connectors ignored" — the arc had wired two *labels* to keys that hold a
  *pattern*;
* the scout's candidate table printed **`headroom {value}`** as a column header;
* the club tier's session note printed a literal **`{rule}`** where the API's own sentence should have
  been.

The check reads ICU the way next-intl reads it: `{name}` is a placeholder, and
`{name, plural, one {…} other {…}}` is a placeholder whose branches are the words the reader sees — so a
catalogue full of plurals does not read as a catalogue full of missing values.

## 4. The field-name gate, and the collision it exists for

The scout's shortlist and the scout's transfer panel were given one accessible name between them during
the arc, so a script that filled a field by name filled the wrong one: the browser walk typed the
projection's career into the **list's** field, the projection's own career stayed empty, the button stayed
server-rendered `disabled`, and seventeen of the walk's checks went red over a transfer projection that
never ran.

`apps/web/scripts/qa-field-labels.mjs` reads every page's own component graph and refuses two different
components on one page declaring the same constant `aria-label` key. It is **2/2** today over **111
`.tsx` files, 61 pages, 104 constant keys, 0 unresolved imports, 0 collisions**, and it is green because
the one collision the walk found is closed, not because it cannot see one: the defect planted back into a
scratch copy of the tree turns it red and names it (`app/scout/page.tsx: "careerAria" is declared by
components/ScoutTransferPanel.tsx, components/ScoutShortlistPanel.tsx`), exit 1.

## 5. The evidence in a browser

The five walks that had not been re-run since the arc were re-run on 2026-10-21, on production builds,
each against its own API on its own fresh SQLite database:

| walk | checks | before | after |
| --- | --- | --- | --- |
| `qa-scout.mjs` | 124 | 107/124 | **124/124**, exit 0 |
| `qa-community.mjs` | 39 | aborted (exit 2) | **39/39**, exit 0 |
| `qa-timeline.mjs` | 29 | 29/29 | **29/29**, exit 0 |
| `qa-carry.mjs` | 45 | 45/45 | **45/45**, exit 0 |
| `qa-ledger.mjs` | 39 | 38/39 | **39/39**, exit 0 |

What the re-runs found is recorded in each milestone's own document: the doubled percentile in
[M7_SCOUT_WEB_VERIFICATION.md](M7_SCOUT_WEB_VERIFICATION.md), the walk pointing at an address the tier
had stopped accepting in [M9_COMMUNITY_VERIFICATION.md](M9_COMMUNITY_VERIFICATION.md), and the needle
that outlived the sentence it checked in [M6_SIM_LEDGER_VERIFICATION.md](M6_SIM_LEDGER_VERIFICATION.md).

## 6. What this does not claim

* **The gate reads a lone word by its shape, and a unit by its name.** "min", "ms", "yrs", "x", "v",
  "sha" and "xp" are in a list of units rather than in the catalogues, because a unit is a unit in every
  language; a new unit in the tree is a new name in that list. The class was **32** lone words, of which
  eighteen were units and field names and fourteen were real copy — all fourteen are in the catalogues
  now.
* **The API's own English is not the web tier's.** A sentence the API publishes is the API's copy; the
  page quotes it, and the gate holds the quotation as a value rather than as a sentence.
* **A locale may lag.** Every key is present in all three catalogues — a catalogue that is *short* is
  worse than one that is absent — but a value may still fall back to English until it is translated. The
  82 identical values are the ones that are supposed to be identical.
* **The copy gate counts; it does not judge.** It cannot tell a wrong sentence from a right one, and it
  cannot tell whether a key means what the page needs it to mean. The gates hold the *shape* of the
  contract; the walks and the API's own tests hold the meaning.
