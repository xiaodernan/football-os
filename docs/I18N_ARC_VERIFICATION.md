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

## 8. The gate could not see a translator it had not been told the name of (2026-10-22)

§7 was about a rule inside the copy gate that decided a string was already translated. This is a rule
inside the *same* gate about something else: **who is a translator.**

### What the rule actually did

The gate decided that a call was a read of the catalogue by looking at the **name** of the function being
called:

```js
} else if (callee && /^t[a-z]{0,2}$/.test(callee) && ts.isStringLiteral(first) && …) {
```

`t`, `tc`, `tn`, `tw`, `td` are all one or two lowercase letters after a `t`, so they matched. Three
translators in this tree are named outside that convention:

| name | bound where | namespace |
| --- | --- | --- |
| `tAuth` | `components/Nav.tsx` — the sign-in link, the sign-out button | `auth` |
| `tCommon` | `components/Nav.tsx` — the demo-mode badge | `common` |
| `settingsT` | `app/register/RegisterForm.tsx` — the display-name field | `settings` |

Seven literal key reads go through them, and the gate saw **none** of them: not checked for existence
in the catalogue, not checked for the placeholders their messages need, not checked for a word said
twice. All seven keys are in the catalogue, so **nothing was broken** — the same "green for the wrong
reason" as §7, one layer down.

### What found it

Not the browser this time. The question asked was a different one — *which catalogue keys does nothing
read?* — and the answer needed a resolver that could tell a translator from a local function. Reading
the tree's translator bindings gave sixteen names, and three of them were invisible to the copy gate.

### The rule now

A translator is identified by its **binding**, not by its name, and the binding is resolved in the scope
that holds it. Four shapes had to be learned:

* **A named binding.** `const t = useTranslations("nav")` says what `t` reads.
* **A scope.** A function body is a scope. `components/ClubTools.tsx` binds `t` to `club` in one
  function and to `common` in the next; the old rule's file-wide map resolved the first function's
  fifteen reads against `common`, which is the wrong catalogue.
* **A destructured binding.** `const [t, td, ta, tn, tc] = await Promise.all([currentUser(), …,
  getTranslations("home"), getTranslations("disclaimer"), getTranslations("auth"),
  getTranslations("nav"), getTranslations("common")])` binds each name **positionally**.
  `app/layout.tsx` and `app/page.tsx` both read five namespaces that way.
* **A parameter.** A component that is *handed* a translator reads it through a parameter, and the
  parameter's name is not the name the caller's translator has: `shelfEyebrow(shelf, tp)` hands the
  `creator` translator to a parameter called `t`. The call site is the fact, so the resolver records
  every call site's arguments and binds each callable's parameters from them.

The gate now checks **3600** key calls against the namespace each is asked of — up from 3593 — and
nothing the old rule saw was lost: every one of the old rule's eighteen unqualified keys is now held
under a namespace (the old rule could not say which), and fourteen qualified keys are new.

### The red path, watched

The gate's green is only worth what its red is worth, so the red was watched. A file reading two keys
the catalogue does not hold through `tAuth` and `tCommon`:

```
FAIL  every key the source asks for is in the catalogue — 2 key(s) the catalogue does not hold
  components/_gate_probe.tsx: auth has no key "aKeyNobodyHolds"
  components/_gate_probe.tsx: common has no key "anotherKeyNobodyHolds"
```

The **old** rule reported **8/8 PASS** on the same file, with the same two missing keys being read.

### The lesson

The name of a thing is not the thing. A gate that recognises a translator by how it is *spelled* holds
its floor for a reason that has nothing to do with the code it is watching — and the same is true of
the scope a name is read in, and of the way it was handed over. **A gate must ask about the binding.**

## 9. The catalogue's dead keys (2026-10-22)

The copy gate asks whether every key the source asks for **is** in the catalogue. The other half of the
same question had never been asked: whether every key the catalogue holds is **asked for**.

### What the number was

`apps/web/scripts/qa-unused-keys.mjs` resolves every read in the web tier and reports the keys no read
can reach. On 2026-10-22 it read:

| | |
| --- | --- |
| catalogue keys | **3736** |
| asked for by a page | **3510** |
| **asked for by nothing** | **226** |

| namespace | dead keys |
| --- | --- |
| `common` | 77 |
| `scout` | 53 |
| `club` | 42 |
| `auth` | 15 |
| `nav` | 9 |
| `validation` | 8 |
| `settings` | 7 |
| `career` | 6 |
| `creator` | 6 |
| `disclaimer`, `home`, `worldNews` | 1 each |

### What the number is made of

Three classes, and they are not the same kind of thing:

* **Two answers to one question.** `nav.video` ("Video Analysis") and `nav.videoShort` ("Video") both
  name the nav's video entry; the nav prints the second. `nav.login` and `auth.signIn` both say "Sign
  in"; the nav prints the second. `nav.register` and `auth.createAccount`; `nav.simulate` and
  `nav.simulator`. The page's own title lives in its own namespace (`video.metaTitle`,
  `simulate.metaTitle`), so the `nav` copy is a second, stale answer to a question the page already
  answers.
* **A vocabulary for a page that does not exist yet.** `auth.forgotPassword`, `auth.resetPassword`,
  `auth.confirmPassword`, `auth.passwordTooShort` — the sign-up and password-reset flows the spec names
  and the tree has not built. `validation.*` is the same: the plan records that it "waits for a form
  that shows custom messages".
* **A preposition table.** `common.or`, `common.and`, `common.of`, `common.in`, `common.for` … seventy
  entries of the smallest English words, written so that a sentence could be assembled from parts and
  never assembled.

### Why the gate is shaped the way it is

The gate's only hard job is to be **right about what it calls dead**. A gate that reports a key as
dead when a read of it is merely *unresolved* would send someone to delete a key the page needs — and
the tree has four shapes of read that a naive resolver cannot see:

| shape | example |
| --- | --- |
| a named read | `t("key")` |
| a destructured read | `const [t, td, tc] = await Promise.all([…, getTranslations("home"), …])` — the namespace is the **position** |
| a dynamic read | `t(band.key)` — the value is in the page's own data |
| a named-key read | `t(link.key)`, `labelKey="rowSession"` — the key is in the page's data, not at the call |

and two more that only a *tree-wide* resolver sees: a **callback parameter**
(`SUGGESTIONS.map((suggestion) => t(suggestion))`) and a **parameter handed a translator by another
file** (`EraseRow` reads `t(whatKey)`, and the three call sites that hand it `"rowSession"`,
`"rowQuestion"` and `"rowReview"` are in two other files).

So the rule is: **a read that cannot be resolved exempts its whole namespace.** A key that cannot be
shown to be dead is not dead, and the gate reports how many namespaces it had to leave alone rather
than pretending it judged them. On 2026-10-22 it had to leave **none** — every read in the tree
resolved — and that is the number the finding rests on.

### The floor

The floor is **226**, the count this gate read, and it may only fall. A key that is wired to a page
lowers it; a key that is added and read by nothing raises it, and the gate says so. The list of 226 is
the work: each is either wired, deleted, or held with a reason.

### The first slice: the stale twins (2026-10-22)

The gate names, for each dead key, the **live key that holds the same English sentence**. That is the
class with a mechanical answer: two answers to one question, one of them a stale copy that no page
reads. **63** of the 226 were in it:

| dead key | the same sentence, and it is read |
| --- | --- |
| `nav.video` | `nav.videoShort` |
| `nav.simulate` | `nav.simulator` |
| `nav.login` | `auth.signIn`, `knowledge.searchSignIn` |
| `nav.career` | `career.title` |
| `nav.settings` | `settings.title` |
| `common.next`, `common.previous` | `common.nextPage`, `common.previousPage` |
| `common.pitchCaption3d` | `tactics.pitchCaption3d` |
| `scout.shortlistTitle`, `scout.shortlistName`, `scout.openList`, `scout.addPlayer`, `scout.noLists` | `scout.listsTitle`, `scout.listNamePlaceholder`, `scout.openAList`, `scout.addToList`, `scout.noListYet` |
| `scout.asksFee`, `scout.releaseClause`, `scout.weeklyWage`, `scout.seasonWage`, `scout.contractYears`, `scout.budgetLeft` | the `scout.kv*` keys the same panel reads |
| `club.tableHeaderDate2`, `club.tableHeaderCoach2`, `club.tableHeaderErase3` | `club.tableHeaderDate`, `club.tableHeaderCoach`, `club.tableHeaderErase` |
| `creator.thMinutes`, `creator.thSessions` | `creator.programMinutesLabel`, `club.tableHeaderSessions` |

All **63** are gone from all three catalogues, and the floor is where they left it: **163**.

The interesting one is the `club.tableHeader*2` / `*3` family. The suffixes are the **field-name
gate** at work: `qa-field-labels.mjs` refuses two panels on one page giving a field the same
accessible name, so a second "Date" column was disambiguated with a suffixed key. The suffixed key was
then never read — the panel it was disambiguated from is not on the same page as the panel that needed
it — so it was a second answer to a question no page was asking. The gate still reads **2/2** after the
deletion, which is the proof that the disambiguation was never needed.
