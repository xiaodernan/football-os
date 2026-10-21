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
| the copy gate | `apps/web/scripts/qa-i18n-literals.mjs` | **8 checks**, three floors at 0, **3593 key calls** checked for existence, for their values, for the keys the page names in its own data, and for the sentences that say a word twice |
| the field-name gate | `apps/web/scripts/qa-field-labels.mjs` | **2 checks**: no two panels on one page may give a field the same accessible name |
| the metadata gate | `apps/web/scripts/qa-metadata-title.mjs` | **165 checks**: every page's tab and heading agree, and neither is a load-time literal |
| the crawl gate | `apps/web/scripts/qa-crawl-policy.mjs` | **9 checks**: the three files that decide what a crawler may see reconcile against every page's own `robots:` |

The three catalogues hold **3736 keys each** — 3654 translated in Simplified Chinese, 3655 in
Traditional, and 82 (81 in `zh-TW.json`) that are *identical* in every catalogue because they are
technical tokens (a product name, an enum, a unit). `apps/web/messages/README.md` carries those
figures, and `apps/api/tests/test_locale_claims.py` recomputes them.

> **The "0 English literal sites" was green for the wrong reason, and a browser found it.** The gate
> decided a string was "already translated" by asking whether it held *any* character outside ASCII.
> A middle dot, an em dash, a curly apostrophe and a `×` are all outside ASCII, so every English
> sentence in this project carrying one of those marks was read as Chinese and never counted. The rule
> now asks whether the string holds a **letter** from another script, and the gate immediately reported
> **47 English strings over 15 files** the arc had left behind. All of them are in the catalogue and both
> floors are 0 again — with a gate that can see them. The lesson is the one this arc exists to teach:
> **a floor is a statement about the gate before it is a statement about the tree.** Section 7 records
> the finding in full.

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

**And it holds every key against the namespace it was asked of, not against the file's union.** That
distinction is the check's own correction: a file that binds `club` and `common` used to pass a key check
that asked "does *any* of them hold this key?", so a page reading `t("yes")` — where `t` is the club
translator and `yes` lives in common — was invisible to it, and the page threw `MISSING_MESSAGE` at
runtime. The check now resolves the translator each key was read through and holds it against that
namespace; it found four such reads on its first run (the plan page's `yes` and `no`, the knowledge
search's two badges), and the club rulebook's runtime-built keys — `capNamemax` where the catalogue holds
`capNameMax` — are now written out one literal call per field so that the gate reads them too.

**And a sixth check holds the keys a page names in its own data.** `t(link.key)`, `t(option.labelKey)` — a
key read out of the page's own data rather than written at the call — cannot be read by the key-existence
check at all, and a key the catalogue does not hold is a runtime error nobody sees. The check finds those
literals (a `key`, `labelKey` or `msg` property whose value reads like a key) and holds them against the
catalogue: **63 named keys** today, 0 missing. The rule that tells a key from a field is a distinction the
copy heuristic cannot make — a key *is* an identifier, so `labelKey: "attrFirstTouch"` and
`key: "first_touch"` are separated by their shape (camelCase against snake_case), not by their spelling.

**And two checks hold the sentences that are half-translated or say a word twice.** A template that carries
a translator call *and* a word of its own is a sentence in two languages — the board editor's save button
read `` `${t("save")} board` ``, which is "保存 board" in Chinese, and no shape the gate read could see it,
because the untranslated half is one lowercase word. And two translated fragments side by side, where the
first is already the beginning of the second, is a sentence that says a word twice: the career's delete
button read `` `${t("delete")} ${tc("deleteThisCareer")}` `` — "Delete Delete this career" in English, and
the walk's own cleanup could not find the button it was looking for, because the page said something else.
Both are checkable, because the catalogue holds the values. The same key twice is a range ("first · last")
and is not a duplication.

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
| `qa-club.mjs` | 252 | 199/200 (crashed) | **252/252**, exit 0 |
| `qa-creator.mjs` | 72 | 72/72 | **72/72**, exit 0 |
| `qa-portfolio.mjs` | 53 | 53/53 | **53/53**, exit 0 |
| `qa-market.mjs` | 106 | 106/106 | **106/106**, exit 0 |
| `visual-qa.mjs` | 297 | 141/143 | **297/297**, exit 0 |

Every one of them ran against the build that carries the arc, each on its own API port over its own fresh
SQLite database, by `scripts/run-walks.mjs` — the harness that is in the repository now, and that reads the
tiers' own log for `MISSING_MESSAGE` (an error raised on the server, where no browser console can see it).

What the re-runs found is recorded in each milestone's own document: the doubled percentile in
[M7_SCOUT_WEB_VERIFICATION.md](M7_SCOUT_WEB_VERIFICATION.md), the walk pointing at an address the tier
had stopped accepting in [M9_COMMUNITY_VERIFICATION.md](M9_COMMUNITY_VERIFICATION.md), and the needle
that outlived the sentence it checked in [M6_SIM_LEDGER_VERIFICATION.md](M6_SIM_LEDGER_VERIFICATION.md).

One harness fix came out of the same re-runs, and it is worth naming because it is the third time a
walk's own measurement was mistaken for the product's: **a probe timeout is the harness's measurement,
not the route's answer.** The sitemap probe gave each of its 1039 URLs 25 seconds and recorded a
timeout as a `408`, so on a loaded host ten slow renders read as ten broken routes and the walk called
the sitemap wrong — twice, on two different builds. A timed-out URL is now asked once more with a
longer budget, and the number that answered only on the second ask is printed in the check's own
line, so a route that answers late is visibly slow and a route that does not answer is visibly
broken. Measured after the fix: **1039 URLs probed, 1039 answered 200**.

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

## 7. The floor was a statement about the gate, not about the tree (2026-10-21)

The arc closed with **0 English literal sites** over every `.tsx` in the web tier, on two floors at 0,
and the claim was checked by a gate that had been read and re-read. It was also **wrong**, and a browser
found it.

### What the rule actually did

The gate asked, of every string: *is this already translated?* — and the answer was "yes" whenever the
string held **any character outside ASCII**:

```js
if (/[^\x00-\x7F]/.test(text)) return false; // already translated
```

This project's copy is full of typographic marks: the separators in a row of figures (` · `), the dashes
that join a clause to its consequence (` — `), the apostrophe in `opponent's goal` (`’`), the `×` in
`68 m × 105 m`, the `§` in `spec §78`. **Every one of them is outside ASCII.** So every English sentence
containing one of them was read as Chinese and was never counted — and the arc wired what the gate could
still see, which was the copy with no marks in it.

### What found it

The **locale sweep** — a new check in `apps/web/scripts/visual-qa.mjs` that opens every page the walk
visited with the Chinese cookie and asks whether the page carries any of the English catalogue's own
sentences. It answered with three pages, and one of them was this, on the world's match rows:

```jsx
<span className="unavailable">Not played · Data unavailable</span>
```

A hard-written English sentence, on the world's own fixture rows, invisible to a gate that thought a
middle dot meant Chinese.

Two rules the sweep had to learn before it could be trusted, both from what it found on its own second
run:

* **The corpus is skipped.** The knowledge base's pages carry the project's own English documents, which
  are published in English on purpose and are not interface copy; a sentence in a document that happens
  to be worded like a catalogue value is a coincidence, not a page that forgot its language.
* **A phrase is matched as a whole phrase.** The tier's own English is quoted rather than translated,
  and it sometimes *contains* a catalogue value: the tactics disclaimer reads "Tactical systems are
  project-authored coaching structures", which contains the label "Tactical system" — as the beginning
  of a longer word, not as the label itself. A substring match called that an English sentence on a
  Chinese page, on every page that quotes the disclaimer. The boundary rule asks for the phrase with a
  non-letter on each side, so "Tactical system" standing on its own is caught and "Tactical systems
  are…" is not.

### The rule now

A string is "already translated" when it holds a **letter** from another script — not a mark:

```js
if ([...text].some((character) => character.codePointAt(0) > 127 && /\p{L}/u.test(character))) return false;
```

The moment that was true, the gate reported **47 English strings over 15 files**:

| where | what was left behind |
| --- | --- |
| `app/settings/page.tsx` | the ten milestone labels (`M0 · Foundation (accounts, training loop, progress)`) |
| `components/pitch.tsx` | the two axis labels, the 2D and 3D captions, and the projection formula |
| `components/ScoutWorkbench.tsx` | five eyebrows and two sentences |
| `app/club/[ident]/page.tsx` | the grant eyebrow, the members eyebrow, the filtered-to clause, the load formula's tooltip |
| `components/SessionReportTools.tsx` | the erase row's sentence and its button |
| the rest | the career form, the scout report, the creator workbench, the portfolio panel, the world components, the tactics pages, the knowledge page, the layout's title template |

All of them are in the catalogue now, in three languages, and both floors are **0** again — with a gate
that can see them.

### One exemption, and why it is structural

The projection **formula** (`screen_x = ((x + 34) − (105 − y)) × cos30 + 105 × cos30   ·   screen_y = …`)
is now exempt, because it is an expression rather than a sentence: its words are variable names and
function names, which are the same in every language, and translating it would make the page wrong.
The test is structural — an arithmetic operator and an equality, with no sentence punctuation outside
the numbers — so a new formula is exempt without an allowlist entry, and a sentence that merely *holds*
a formula (`duration_min × rpe ÷ 60, over this row's own two columns`) is still copy and was wired.

### The lesson

**A floor is a statement about the gate before it is a statement about the tree.** A gate that cannot see
a class of defect holds its floor for a reason that has nothing to do with the code it is watching, and
the number it reports is true — of the gate. The arc's own record is the second time this has happened
here (the first was the fifth shape, the string a helper returns), and the browser is what found both:
the source is where a gate looks, and the page is where the copy lives.
