# §81 — the interface in the reader's language, and the gates that hold it there

What this certifies: that every string a reader sees on the web tier is read from a **catalogue**, in one
of three languages, and that four gates refuse the day it stops being true.

The arc began as a copy gate with a ceiling and became something else: a gate can count what it can see,
and what it could not see turned out to be most of the copy in the tree. Every number below is measured
on the tree this document names, and every figure in it is reproducible by running the gate that produced
it.

**The figures in §1 are the arc's opening figures.** The tree as the arc left it is in **§14** (the
walk on it: 298/298, exit 0) and **§15** (the boundary), and the catalogue's own current table is
`apps/web/messages/README.md` — which the locale-claims test recomputes and holds to the live key
count.

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
| `visual-qa.mjs` | **298** | 141/143 | **298/298**, exit 0 — including the locale sweep, which had never been observed |

**All ten were re-run together on 2026-10-22**, on build `eSZ6okbO84ws9gJKLQbxQ` — the build that carries the
catalogue as committed — each against its own API on its own port over its own fresh SQLite database, by the
same harness: **10/10 walks green**, every one of them exit 0. That run is the evidence for the catalogue work
that followed: **226** keys removed from all three catalogues, **eleven** English phrases translated, and the
English catalogue's one Chinese sentence replaced with English. Three of those pages render differently now —
the club page's cap row, the academy's placeholders and the scout's search placeholder — and the walks are the
only thing that can say the change did not break them.

### The visual walk, re-run on 2026-10-22 (201/205, exit 1)

The visual walk was run again on the build that carries the catalogue work — build `HRuYA1koLs7jIG6XG1qIS`
(`.next-i18n13`), API on `:8773`, the web tier on `:3250`, its own fresh SQLite database, by the same
`scripts/run-walks.mjs` harness that runs every other walk. It read **201 of 205** checks and exited **1**.

What it proved:

* **The sitemap probe is whole.** **1039 URLs probed, 1039 answered 200** — no timeouts, no 408s. The
  retry the harness carries (`ef584d4`) has now cleared the class of failure that had killed four runs,
  and the ten slow renders that read as ten broken routes are gone.
* **Every page the walk visited renders the Chinese catalogue.** Each of the nine per-page checks —
  the coach screen, the development screen, the training log, the academy index, the knowledge base,
  the challenges catalogue, the scout screen — read the page again with the Chinese cookie and compared
  it with `messages/zh.json`, and each also checked that the English copy is *gone* and that switching
  back leaves the screen in English. All passed.
* **The tier log carries no `MISSING_MESSAGE`**, so no page asked its catalogue for a key it does not
  hold — which is what says the catalogue work broke nothing.

What it did not prove, and why:

* **The locale sweep did not run, because the career section threw before it** — and the throw was the
  walk's own timing, not the product's. The record on the career page is **server-rendered**: the "Round 1
  played" block is the client's own state and appears at once, but the record beside it comes back from
  the server on the next refresh, and the walk waited a fixed two seconds for a round-trip it had never
  measured. It read a zero record under a season that had just played a round, and called it "the record
  the page prints is not the arithmetic of the round it just played". The same race, the other way round,
  retired the season: the button's own label **is** the season's status, so until the refresh lands the page
  still says "Retire from this club", still offers "Play the next round" enabled, and carries no retired
  copy — three more reported defects, all one timing — and then the walk threw looking for a button the
  fresh page would have had. **That throw ended the walk before the sweep.**

* **Those three were the harness's measurement, and the fix is a wait for the condition rather than a
  sleep.** The waits now ask for what each check measures: the record's own `Rounds` cell after "Play the
  next round", a button labelled "Take charge again" after "Retire from this club", and the play button
  enabled after taking charge again. A timeout is swallowed, because the check behind each one reports the
  truth rather than the harness throwing in its place. With the first two fixed the walk read **297 of 298**, and the one that still failed was the third step of the same race — fixed the same way, and the walk then read **298 of 298**, exit **0**, on the fourth run.

* **The sweep ran, and it found one thing.** With the career section past, the last check before the walk's
  own completion check ran for the first time: *"every page this walk visited reads the Chinese catalogue,
  and none of them carries an English sentence"* — **49 pages read in Chinese, 1964 English phrases
  compared, 4 corpus pages skipped**. It reported three pages, and the finding was real in the sense that
  matters: `tactics.phaseOutLower` is the catalogue's phase label, its Chinese value is "无球时" /
  "無球時", and the English text on those pages came from the API's **authored metric prose** — "Mean 12.3 m
  to the nearest team-mate while out of possession, which is the distance a combination has to cover" —
  which is quoted rather than translated, the same kind of English the knowledge corpus publishes on
  purpose. The sweep had been matching a catalogue value **anywhere** in the page's text, so the label's
  own words inside a longer English sentence read as an untranslated label. The comparison is now **per
  element**: an element whose text **is** the value is a label the page forgot to translate — the defect
  the sweep was born to find, and the "Not played · Data unavailable" it was born to find — while an element
  whose text merely *contains* it is a longer sentence. The whole-phrase boundary rule the page-level match
  needed is implied by equality, and the sweep now reads **PASS**.

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
  56 identical values are the ones that are supposed to be identical.
* **The copy gate counts; it does not judge.** It cannot tell a wrong sentence from a right one, and it
  cannot tell whether a key means what the page needs it to mean. The gates hold the *shape* of the
  contract; the walks and the API's own tests hold the meaning.
* **The API's refusal messages are still English, and the reader sees them.** This is the arc's open
  edge, and it is named here rather than left implied. The API publishes **66 refusal codes**, each with
  an English sentence (`detail.code` + `detail.message`), and the web tier's `errorMessage()` returns
  `error.message` — so a Chinese reader is told "The current password is incorrect" in English. It is
  the same shape as the two claims above: a convention ("a refusal is printed as the code and the
  figure the API answered with rather than a shrug", which is what `SessionReportTools.tsx` says) that
  the implementation does not match (what it prints is the message, not the code). Neither the copy gate
  (it reads the web tier's source) nor the locale sweep (it looks for *catalogue values* on a page)
  can see it, because the English is in the **API's** answer.

  The design that was worked out, for whoever takes it:

  * the catalogue holds one key per refusal code — `errors.<code>` — with the **English value being the
    API's message verbatim**, so the English rendering is byte-identical and the change is a translation
    rather than a copy change, exactly as the arc's method requires;
  * the **code** is the stable half of a refusal and is already locale-neutral, so it needs no
    translation and stays the operator's handle;
  * the switch is **one place, not 31 files**: every browser request passes through
    `app/api/v1/[...path]/route.ts` (the cookie proxy) and every server read passes through
    `lib/server.ts`'s `serverFetch`, so the refusal's message can be rewritten in one of those two
    places — or, better, in `lib/api.ts`'s `errorMessage`, which both paths already share. The 42 call
    sites across 31 files pass a *generic* fallback today ("askFailed", "signInFailed"), so the
    specificity of the API's message is the thing a per-code catalogue would restore;
  * a gate then holds the two in step **in both directions**: every code the API publishes has a
    catalogue key whose English value is the API's message, and every `errors.*` key the catalogue
    holds is a code the API publishes.

  **It landed on 2026-10-22** — see §11.
* **A key's *existence* is not a key's *use*, and neither gate can see the third thing.** The copy gate
  asks whether every key asked for is held; the dead-key gate asks whether every key held is asked for.
  Between them, they hold that the catalogue and the tree agree — and neither can see a key that a page
  *builds* rather than names, which is the shape §9 found in the club tier's thirty-six placeholder
  messages. A message whose value is only a placeholder name (`"{rule}"`) is the same string in all three
  catalogues, so it is not a translation at all; the club page does not read those, it prints the rule the
  API sends, and that rule is the tier's own published English — the same kind the knowledge corpus
  publishes on purpose, and the same kind the locale sweep deliberately does not judge.

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

### The second slice: the shared verb table (2026-10-22)

**67** of the remaining keys were one thing: a **shared vocabulary for copy the interface has not written**.
`common.or`, `common.and`, `common.of`, `common.in`, `common.for`, `common.with`, `common.by`, `common.on`,
`common.at`, `common.to`, `common.from`, `common.as`, `common.is`, `common.not` — and the same list of verbs
around them (`loading`, `error`, `retry`, `cancel`, `edit`, `back`, `submit`, `confirm`, `ok`, `done`, `hide`,
`show`, `more`, `less`, `none`, `select`, `choose`, `required`, `description`, `details`, `actions`, `active`,
`inactive`, `enabled`, `disabled`, `public`, `private`, `draft`, `archived`, `deleted`, `restored`, `created`,
`updated`, `removed`, `added`, `changed`, `duplicated`, `imported`, `exported`, `downloaded`, `uploaded`, `sent`,
`read`, `unread`, `seen`, `unseen`, `completed`, `pending`, `failed`, `success`, `warning`, `info`, `alert`,
`critical`).

They were written so that a sentence could be **assembled from parts**. No message in this catalogue is
assembled from parts: every one is a whole sentence with its own placeholders, which is what the ICU gate
holds them to. So the table was never used, and it cost **67 × 3 = 201** translated strings that had to be
right and had to be re-read whenever a message beside them changed.

They are gone from all three catalogues. The floor is **96**, and the catalogue holds **3606** keys (was 3736).

### The third slice: the last 96 (2026-10-22)

The floor is now **0**. Every key the catalogue holds is asked for by a page.

| namespace | dead keys | what they were |
| --- | --- | --- |
| `club` | 36 | the club tier's rules and table headers — **thirty-six of them hold nothing but a placeholder name** (`club.matrixRule` is `"{rule}"`, `club.figuresFrom` is `"{figures}"`), so they are not translations at all: they are the same string in all three catalogues, and a Chinese page reading one would print the API's English sentence with an empty frame around it |
| `scout` | 16 | the scouting panel's copy |
| `auth` | 15 | the sign-up, password-reset and account-state flows — **the plan itself records that `validation` "waits for a form that shows custom messages"**, and the reset and confirm flows are not built |
| `validation` | 8 | the custom validation messages, for the same reason |
| `nav` | 6 | labels for entries the nav does not offer (`nav.challenges`, `nav.market`, `nav.onboarding`) and the stale twins of the entries it does |
| `career` | 6 | the career form's pickers |
| `settings` | 5 | the settings panel's headings |
| `creator` | 3 | the creator tier's programme receipts |
| `disclaimer` | 1 | one sentence the disclaimer does not carry |

The rule the catalogue now holds is the one the nav's own comment states: **a catalogue nothing reads is
a translation that ships to nobody.** A key is created when a page needs a sentence and removed when no
page needs it; when a future page needs one, the arc's method writes it from that page's own strings.

The catalogue holds **3510** keys (was 3736). The two Chinese files still fall back on the same
**82** / **81** technical tokens, because every removed key was translated in every locale — so nothing
about the *coverage* moved, only the size of the thing being covered.

## 10. The two locale claims that were conventions (2026-10-22)

The arc made two claims about the catalogues that were **conventions rather than measurements**, and
neither had ever been checked.

### "The identical values are the ones that are supposed to be identical"

A key whose Chinese value is byte-identical to its English value is, by that claim, a technical token. The
claim was never checked, so an English **phrase** could sit in the Chinese catalogue untranslated and nobody
would know. Eleven did:

| key | the English a Chinese reader was shown |
| --- | --- |
| `club.capVisibilityDefaults` | visibility defaults |
| `club.capAddressing` | addressing |
| `club.capInvitations` | invitations |
| `club.capAxes` | axes |
| `club.capWeeklyMinutes` | weekly minutes |
| `club.capFocusItemsGoals` | focus items / goals |
| `club.capGoalKeys` | goal keys |
| `club.capFeedbackAssessment` | feedback / assessment text |
| `club.capPlanStatuses` | plan statuses |
| `academy.focusPlaceholder` | technique, tactics |
| `academy.sessionFocusPlaceholder` | pressing, transitions |

They are the club tier's **cap names** — the row that prints each cap's ceiling — and the academy's
**example placeholders**. A cap is named in English while the five caps beside it are named by the API's
own field name (`name_max`, `team_name_max`, `note_max`, `country`, `kinds`), so the row was half field
names and half English sentences. All eleven are translated now.

The five that *are* field names stay as they are: a field name printed as itself is the convention, and it
is the same in every language.

### "The English catalogue is English"

`en.json` held `scout.placeholder` in **Chinese** — "e.g. 找一个 22 岁以下、左脚、能踢 CM、预算 2000 万以下的球员" —
so an English reader was shown a Chinese sentence. And because the Chinese catalogue held the same Chinese
sentence, the *identical values* counted it as translated, and the coverage figure was wrong about it.

Neither the copy gate nor the locale sweep could see it: the copy gate reads the source rather than the
catalogue, and the sweep looks for **English** on a Chinese page. The defect was found by listing the
identical values and reading them.

### The gate

`apps/web/scripts/qa-locale-tokens.mjs` holds both claims, and the set of identical values is **named** —
44 keys, each with the reason it is the same in every language: an acronym or a unit (`OVR`, `POT`, `RPE`,
`xG`, `PDF`, `HTTP`, `API`, `bm25`), an API field name printed as itself (`name_max`, `country`, `kinds`,
`rating_range`, `recent_form`, `shared_with_guardian`, `comparison: null`), a template whose parts are names
or figures (`{name} · {formation} · {overall}`, `{kind}: {slug}`), a proper name used as an example
(`Riverside Academy`, `ada-doler`), or a punctuation mark. A value that is identical **without** a name is
a finding, and a name that is no longer a token is a finding.

Its red path was watched: an English phrase planted in the Chinese catalogue and a Chinese sentence planted
in the English catalogue, and the gate named both.

**The lesson.** A claim about what *should* be true is a convention until something checks it. "The
identical values are the technical tokens" was true of every key anybody had looked at, and false of eleven
that nobody had.

## 11. The refusals the API answers with (2026-10-22)

### What was found

The API answers a refusal with a **code** and a **sentence**. The code is the stable handle — the
operator's, the log's, the page's — and the sentence is the API's own English. The web tier shows the
sentence: `errorMessage()` in `lib/api.ts` returns `error.message`, and the forty-two call sites that
pass it a translated fallback never see that fallback used. So a Chinese reader was told *"The current
password is incorrect"* in English, on a page whose every other sentence came from the Chinese
catalogue.

It is the same shape as §7 and §10 — a convention the implementation did not match. `SessionReportTools.tsx`
says a refusal is printed as "the code and the figure the API answered with rather than a shrug", and
what the reader got was the API's English sentence.

### Why neither gate could see it

The copy gate reads the **web tier's source**, and the English was in the **API's answer**. The locale
sweep looks for **catalogue values** on a page, and the API's sentences are not catalogue values. The
sweep's *tolerated* list — the API's authored prose it prints and does not judge — could not have shown
it either, because the refusal never reaches the page as a catalogue value at all.

### The fix, and its shape

The arc's method, applied to the other side of the wire: **the catalogue holds one key per refusal
code, and the English value is the API's message verbatim.** So the English rendering is byte-identical
and this is a *translation* rather than a copy change — and the code needs no translation at all, because
it is already the locale-neutral handle the page prints beside the sentence.

The switch is **one place, not thirty-one files**:

| where | what it does |
| --- | --- |
| `apps/web/lib/refusals.ts` | the shared shape handling and the lookup, read through next-intl's translator so the locale is the reader's own |
| `lib/server.ts`'s `serverFetch` | the server's own reads |
| `app/api/v1/[...path]/route.ts` | the browser's traffic |

`errorMessage()` and the forty-two call sites that pass it a fallback are **untouched**, and the
fallback they pass is still what a reader sees when the API sends no message at all.

The proxy had to learn the locale for itself: the middleware skips `/api`, so the proxy's own request
carries no `x-next-intl-locale` header and next-intl would answer it in English whatever the reader
chose. The reader's choice is in the `fo_locale` cookie, which the middleware writes on every response,
so `i18n/request.ts` now falls back to it.

### What is covered, and what is named

The catalogue holds **26** codes. The API publishes **65**, and the other **39** have a message that
names a value the request supplied ("philosophy must be one of [...]") or that a helper chooses at the
raise site ("The current password is incorrect"). A catalogue cannot reproduce a sentence that changes
with the request, so those keep the API's own words — and they are **named** in the test rather than
left implied.

`apps/api/tests/test_locale_claims.py` holds the two in step in **both directions**:

* every code the API publishes with a fixed message has a catalogue key, and the catalogue's English
  value is that message, so the two cannot drift apart;
* every `errors.*` key the catalogue holds is such a code, so a key nothing reads cannot sit in the
  catalogue;
* every code whose message is not fixed is named in `NOT_FIXED_CODES`, so a new refusal has to be
  classified before it can be published.

Its red path was watched: a catalogue sentence that no longer matched the API's message, and a key for
a refusal the API does not publish, both made it fail by name.

And the walk was re-run on the build that carries it: the nine tier walks are green (**scout 124,
community 39, timeline 29, carry 45, ledger 39, club 252, creator 97, portfolio 53, market 106**) and the
visual walk **298/298, exit 0**. The sweep printed its exemption's surface for the first time — the
elements that carry a catalogue value inside a longer text — and it is the API's own prose, quoted rather
than translated.

### The read, in the reader's language

The claim was read through the **proxy** — the browser's path — because that is the path a reader takes
and because the proxy is where the locale had to be learned from the `fo_locale` cookie. One door, one
refusal, three languages:

```
EN      401  "Email or password is incorrect"
zh      401  "邮箱或密码不正确"
zh-TW   401  "信箱或密碼不正確"
```

The English rendering is the API's own message, byte for byte; the other two are the catalogue's. That is
the whole slice in three lines: a refusal used to be English on a Chinese page whatever the reader had
chosen, and now it is the reader's language with the English untouched.

The same read, taken after the asymmetry slice added `invalid_password` and the rule that the English
reader keeps the API's wording, reads the same way — the English is unchanged and the Chinese is the
catalogue's — which is what "the English does not move" means in practice. The walk was re-run on the
build that carries it: **298/298, exit 0**.

### Which language gets which words (2026-10-22)

The second slice added `invalid_password` — "The current password is incorrect", which the API's helper
takes as an argument and every call site fixes — and it needed a decision the first slice had not
forced: **which of the two sentences does a reader see?**

The API's message names a value the request supplied ("philosophy must be one of
`['balanced', 'counter', ...]`"), so the catalogue's sentence for such a code is the *general* one, and
the API's message is the one that says what actually happened. Where the API's message is fixed — 26 of
the codes — the catalogue's English value **is** that message, so the two agree and nothing changes.

So the rule is:

* the **English** reader is shown the API's own message, byte for byte;
* **every other language** is shown the catalogue's sentence for the code;
* a code the catalogue does not name keeps the API's words in every language.

The English does not move, because the arc's own rule is that an i18n change should not be a copy
change — and the API's wording is the more specific of the two ("The current password is incorrect"
names what is wrong; a general sentence does not). The catalogue's English value for a code whose
message varies is the general sentence, and it is the fallback for the case where the API sends no
message at all.

The contract test now holds the wider contract: a code **either** carries a catalogue sentence **or** is
named in `NOT_FIXED_CODES`; a named code that carries one is held to the same drift rule as the rest —
its English value must still be the API's message — and a catalogue sentence must name a code the API
publishes at all.

### What the census can and cannot see (2026-10-22)

The contract test's census reads a refusal's message **where it is written**, so a message a helper
takes as an argument — `password_refusal(message=...)` — is not a literal it can see, and the code was
named as one the catalogue cannot reproduce. That is **conservative in the safe direction** — a code the
census cannot resolve is named rather than silently left uncovered — and `invalid_password` was carried
by hand for exactly that reason.

**The census now follows the call** (2026-10-22), and finding that took two bugs of its own:

* it read the API's **documentation** as if it were code — `security.py` explains the refusal it
  documents by quoting the line that raises it, so the census counted a comment as a second raise site.
  The census now strips the comments first, with a small state machine that knows a `#` inside a
  string is not a comment;
* it classified a helper's message as an f-string, because the check for "a message with no letters in
  it" ran before the check for "a message that is a parameter" — and an empty literal has no letters in
  it either.

With both fixed, the census resolves `invalid_password` through `password_refusal()` to the one
message its callers pass — **"The current password is incorrect"** — and the code leaves the named list
and joins the covered ones, where the drift rule holds it to the API's message. The named list is
**38** codes, and each is a message that genuinely varies with the request or that a helper is called
with more than one sentence.

### The first batch of the varying ones (2026-10-22)

Seven of the codes whose API message names a value the request supplied now carry a catalogue
sentence — the ones a reader is most likely to meet:

| code | the API's message | the catalogue's sentence (English) |
| --- | --- | --- |
| `bad_philosophy` | "philosophy must be one of `['balanced', 'counter', …]`" | That is not one of the philosophies the engine accepts. |
| `bad_objective` | "objective kind '…' is not one of `[…]`" | That is not one of the objective kinds the engine accepts. |
| `bad_minutes` | "minutes must be one of `[…]`" | That is not one of the durations the engine accepts. |
| `unknown_change` | "change must be one of `[…]`" | That is not one of the changes the tactics catalogue holds. |
| `no_such_system` | "system '…' is not one of the 50 authored tactical systems" | That is not one of the authored tactical systems. |
| `no_such_club`, `no_such_team` | "'…' is not a club in the generated world" | That is not a club in the generated world. |

A second batch followed the same day — the family the API publishes the same way every time: the five
**limits** (`board_limit`, `career_limit`, `run_limit`, `simulation_limit`, `video_limit`), the
**not-found** family (`not_found`, under which the API publishes sixteen sentences — "Drill not found",
"No such board in the gallery", "This link no longer points at a clip"), the three **ids**
(`no_such_job`, `no_such_trace`, `no_such_memory`) and `no_such_challenge`.

A third batch finished it — the account and role doors (the phrase deleting an account asks for, the
switched-off account, the role that does not allow it), the job and board refusals (a job that has
already finished, a board that could not be read), the media refusals (the clip the server cannot read,
the byte range past the end, the file that is too large, the container it does not know), and the rest
(no fixture to play, no frame with that id, the scenario whose window has closed, the path that does not
serve this, the challenge played without transfers).

**The catalogue holds all 65** — every refusal code the API publishes — and the contract is stronger
than it was: **every** code carries a sentence, not "a sentence or a name in the list". The two Chinese
files still fall back on the same **44** technical tokens, because every key added here is translated
in every locale.

The list that remains is therefore the census's **verdict** rather than a gap: it names the codes whose
API message varies with the request, and it is checked in both directions, so a new refusal has to be
classified before it can be published.

**What the walk covered.** The walk that proved this slice ran on the build that carries the **third**
and final batch — the catalogue as it now holds it, **all 65** codes, build `.next-i18n18` — which made
the evidence and the tree the same tree: **298/298 checks passed, exit 0**, on the web tier `:3250` and
the API `:8773`, its own fresh SQLite database, by the same `scripts/run-walks.mjs` harness. The locale
sweep read **49 pages in Chinese, 2035 English phrases compared, 4 corpus pages skipped**, and printed
its exemption's surface for the first time — the **101 elements** that carry a catalogue value inside a
longer text. The refusal read was then taken on that same build through the proxy, in **English** with the
API's own message and in **Chinese** and **Traditional** with the catalogue's, and all three came back
true.

### The honest remainder

The claim "the interface is in the reader's language" now holds for the interface's **own** copy **and**
for the refusals the catalogue can reproduce, and the catalogue has since written a sentence for **every**
one of the **65** the API publishes — three batches of text work, and the final batch taken on a build
that carried it, which proved it: **298/298, exit 0**, with the refusal read in three languages coming
back true. There is no code left that the catalogue cannot speak for; the list that remains is the
census's verdict about which messages vary with the request, and it is checked in both directions, so a
new refusal has to be classified before it can be published.

## 12. The API's sentences, and the copies the web tier holds (2026-10-22)

### The question the dead-key gate asked of the other tier

The dead-key gate (§9) asks whether every key the catalogue holds is **asked for**. It found 226 that were
read by nothing, and the floor is now zero. That question was never asked of the **other side of the
wire**: the API publishes sentences — 65 refusal messages, the metric prose the sweep tolerates, the
corpus's own English — and the web tier reads some of them. Where else does the web tier hold a **copy**?

A copy is a **dead string**. The API's sentence is the live one: it is what the API answers with, and the
refusal boundary hands it to the reader. A copy in a page is a sentence the API can change without the
page following it, and a second place to fix when it does.

### Where the API's sentences live

The API's refusal sentences reach the web tier through the **catalogue** — the `errors` namespace, one key
per code — and the contract test in `apps/api/tests/test_locale_claims.py` holds the English value to be
the API's own message. So the catalogue is the source of truth for "the API's sentences", and the gate
reads them from there rather than teaching a second census of the API's source — which is how the census's
own two bugs (a comment read as code, and a helper's parameter read as a literal) would have been written
twice.

### The gate

`apps/web/scripts/qa-api-strings.mjs` is **3/3** today, over **65** sentences and the web tier's own
source:

| check | what it holds |
| --- | --- |
| no copy in the web tier's code | no file may hold a sentence the catalogue owns — and a comment is not a literal, and a regular expression is not a string, so the boundary's own comment (which quotes the API's sentence to explain why the sentence is the API's) is not a copy |
| the boundary is wired | the localiser is **used**, not merely imported, on both paths a refusal arrives through: the server's own read and the browser's proxy |
| every refusal is translated | no refusal code's sentence may be the English one in a Chinese catalogue |

### Its red path was watched

A copy planted in the web tier's own code was named with the file and the line
(`lib/_qa_probe.ts:1 holds a copy of errors.invalid_credentials`); the server's own read losing the
localiser was named; and a refusal's sentence left in English in the Chinese catalogue was named.

**The first version of the second check reported a false finding**, and the arc's own lesson applies to
the gate as much as to the tree: it looked for a **call** where the server's own read passes the localiser
as a **reference** (`readError(response, localiseRefusal)`). The check now asks whether the name is used,
and used outside the import that brings it in — which is the question the check meant to ask.

The gate joins `scripts/check.sh` and CI; the gate inventory is **93/93**.

## 13. The copy gate had never read a `.ts` file (2026-10-22)

### The claim

The copy gate's population was "every `.tsx` under `app/` and every `.tsx` under `components/`" — and
**not one `.ts`**, while the reader-facing sentences live in exactly those files. So the gate's claim, "0
English literal sites", was true of the files it read and untested of the rest of the tier.

The population is now the whole tier: `.tsx` and `.ts`, under `app/`, `components/` and `lib/`.

### What it found the moment it could see

| what | where | what the reader saw |
| --- | --- | --- |
| seven column headers and seven tooltips | `lib/ledger.ts` | "Matches", "Goals", "Attempts", "Yellow", "Red", "Injury" — in **every** language, on the career page's ledger panel |
| the tier's own error sentences | `lib/api.ts`, `lib/world.ts`, `lib/server.ts` | "Request failed with status 422", "Something went wrong", "The web tier could not reach the API.", "The generated world could not be read right now." — English, on a Chinese page |
| five call sites with no fallback at all | `app/agents/page.tsx`, `components/CommunityTools.tsx`, the three scout panels | the tier's English default |

### The fix, and the shape it took

* the ledger's labels and hints are **catalogue keys** now, in three languages, and the panel reads them;
* the tier's own generic answers carry a **code and no sentence** — the reader's sentence is the call
  site's fallback, and the localiser fills the rest on the two paths that can read the catalogue (the
  server's own read and the browser's proxy). `errorMessage`'s fallback is now **required**, so a call
  site that passes none is a compile error rather than an English default;
* `lib/site.ts` is the one file the gate does not read, and it is **named** as such. Its two sentences are
  the site's brand line and the metadata sentence it is printed into — the layout's description, the
  `WebSite` graph, the share card's alt text — and that is the **crawler's** surface, not a reader's.
  The reader never sees a meta description: it is not rendered. And the locale is a **cookie**, not a URL
  segment, so a crawler and a share scraper arrive without one and read the default locale — which is
  English, and so is the description they read. The English metadata is the right sentence for the
  reader it is written for. The one thing that stays English in every language is the **OG image's own
  pixels** (a single picture cannot be two languages), and that is the card a scraper sees.

The error-shape gate's contract moved with it: **an answer the API named carries its sentence; the
tier's own generic answer does not.** And the locale-token gate holds the new "xG" token by name.

### The lesson, again

This is §7's lesson in a new place. The floor was **0** and it was green, and the green said only that
the gate could see what it looked at. The tree was full of English copy in files the gate had never
opened. The **lesson** is the one the arc keeps teaching: *a floor is a statement about the gate before
it is a statement about the tree* — and a population is a statement about the gate too.

## 14. The reader's sentence, on every path an answer can take (2026-10-22)

### The shape the slice left behind

The tier's own generic answers now carry **a code and no sentence** — the reader's sentence is the call
site's fallback, and the localiser fills the rest on the paths that can read the catalogue. That left
two paths where the reader could have been shown a code and an empty sentence, and both were closed.

**The proxy.** The browser cannot read the catalogue, so every answer has to be localised on the way,
and the proxy is the door. It already localised the refusals, but an answer it could **not parse** used
to travel as the API's own bytes: the proxy forwarded the raw body, the browser could not read it
either, and the tier's answer for it carried no sentence at all. The proxy now asks the localiser for
every answer it forwards, parsed or not.

**The twelve client sites.** They printed `error.message` and nothing else, so a generic answer reached
the reader as a code and an empty sentence. They now print the code *and* the sentence, and the sentence
is the catalogue's when the answer named none. Each site uses the translator already in scope at its
printing site, which is not the same translator in every file: three of them had a "common" translator
of their own, two had a translator of their own namespace (so two namespaces gained the sentence), and
the workbench's module-level line has none at all — so the sentence is **handed to it** as an argument,
and seven call sites hand it over. The callbacks that now read the translator name it in their
dependency lists, which the hook rule holds.

### The last English, and why it is the crawler's

The site's brand line and its metadata sentence are still English in every language, and that is now
settled rather than open. The locale is a **cookie**, not a URL segment, so a crawler and a share
scraper arrive without one and read the default locale — which is English, and so is the description
they read. A reader never sees a meta description, because it is not rendered.

The **share card's own pixels** are the same argument, one step further: a picture cannot be two
languages, and the card is fetched by a scraper that sends no cookie, so the card it fetches is the
default locale's card whatever the layout's metadata says. A per-locale card would need the locale to
travel in the **URL** — a change to how the site addresses its pages, not a change to a sentence — and
so it is a design question rather than a copy fix. Until that question is answered, the card is English
on purpose: it is the picture a scraper without a cookie receives.

### The figures, on the day

The three catalogues hold **3596 keys** each — 3551 translated in Simplified Chinese and 3551 in
Traditional, and **45** the same in every language because they are technical tokens. The `errors`
namespace holds all **65** refusal codes, and `careerDetail` holds **115** keys — fourteen of them the
ledger's labels and hints, which are the copy the copy gate found on the day it was taught to read the
tier's `.ts` files.

### The walk, on the tree this arc left

The visual walk was re-run on the build that carries this arc's work — **298/298, exit 0** — and the locale
sweep read **49 pages in Chinese, 2047 English phrases compared, 4 corpus pages skipped**. The number
that moved most is the sweep's **tolerated list**: the elements that carry a catalogue value inside a
longer text fell from **101 to 55**, because the JSON-LD block's text no longer reaches the comparison
through every ancestor that contains it. Structured data is data; the reader never sees it, so the
sweep must not read it, and the surface of the exemption is now what it says it is.

### The table that went stale, and the floor beside the pin

The catalogue's own table (`apps/web/messages/README.md`) said **3531 of 3575** when the catalogue held
**3551 of 3596** — and nothing said so, because the test that recomputes the table asserts the
**translated count** as a *floor* (`stated <= translated`). A floor is right there: a translation batch
raises the count without touching the file, and the file is not supposed to be rewritten for every
sentence that lands. But the **population** beside it is a **pin** — the test fails if the table's
denominator is not the live key count — and the population was stale too, so the pin would have caught
the whole table had the test been run.

It had not been run: the arc added **61** keys over its last stretch and the API's suite was not run
after them, because the web tier's own gates do not run it and the pre-commit hook's fast checks are
not the repository's gate. The repository's gate is `scripts/check.sh`, and it *does* run
`python -m pytest` over the API — so the rule the arc records is its own: **after a change to the
catalogue, run the API's suite, not only the web's gates.** The table is recomputed and the pin holds.

**And the pin has now caught it twice.** The second time was the `errorBoundary` namespace: four keys
landed after the last recompute, the web's gates said nothing (they do not read the table), and the
API's suite named the stale population and the stale count. The rule is not advice — it is the only
thing standing between the table and a silent lie, and the table is the number a reader is given.

**And now the web's gates can see it too.** The population and the translated count are both derivable
from the three catalogues, so `qa-locale-tokens.mjs` holds the two numbers the table states against the
catalogue itself — the cross-tier check that used to live only in the API's suite now lives in the tier
that owns the catalogue. Its red path was watched: a table one key out of date is named, in both
locales.

## 15. The failure the reader meets most often (2026-10-22)

### The question

The tree had a `not-found.tsx` in the catalogue — so what did a page that **throws** show? The
framework's own error screen: "Application error: a server-side exception has occurred while loading
the page", in every language, on a page whose every other sentence comes from the catalogue. The tree
had a localised way to say *this page does not exist* and no localised way to say *this page failed* —
and the failure is the one a reader meets far more often.

### The fix, and the gate

`app/error.tsx` is the tree's own boundary: it says the page could not be loaded, it offers the one
thing a reader can do with a page that failed — ask for it again — and it shows the reader nothing the
server already has in its log. Four keys in three languages, in their own `errorBoundary` namespace.

`apps/web/scripts/qa-error-boundary.mjs` holds it: **2/2**, in `scripts/check.sh` and in CI. The
boundary must be there, it must be a client component, and its sentences must be in the catalogue with
the same keys in all three languages. Its red path was watched: with the file moved aside the gate
reads **0/2** and names both findings — that the boundary does not exist, and that it reads no
catalogue namespace.

A `global-error.tsx` — the boundary for a failure in the *root layout* — is deliberately absent: it
replaces the layout itself, so it has no locale provider, and a page that never renders is not worth a
catalogue in the bundle. The framework's default is the honest answer for that case.

### The walk on the final tree

The visual walk was run on the build that carries **every** slice of this arc — the boundary, the
client sites, the proxy, the refusals, the whole-tier copy gate — and it read **298/298, exit 0**. The
locale sweep read **49 pages in Chinese, 2049 English phrases compared, 4 corpus pages skipped**, and
the tree's own failure boundary is now part of what a broken page shows the reader.

That is the arc's evidence and the arc's tree, in one run: the numbers and the code are the same
thing, and the doc's figures are the figures that run read.

### The surface of the sweep's claim

The sweep's claim is about *the pages this walk visited* — so the list of those pages **is** the surface
of the claim, and a page the sweep never read is a page nobody has judged in the reader's language.
The sweep now prints the pages it read, in full, beside the check that says they are all in the
Chinese catalogue.

The static census says the tree holds **61 route patterns** and the walk's own source names **54**
concrete paths, leaving **33** routes with no named path under them — and most of those are the
dynamic ones the walk reaches at runtime (the career it opened, the team it read out of the API, the
share link it minted). The runtime list is the one that settles it, and it is now printed rather than
assumed.

And the walk now **holds** it: it reads the tree's own routes and refuses to finish green while one of
them has no page the sweep read under it. The corpus routes are the exception the sweep already names
— they carry the project's own English documents, published in English on purpose. A route nobody read
in the reader's language is a page the claim does not cover, so the coverage is a check rather than an
assumption.

### The pages no walk reads

A static census of the tree's routes against the ten walks' own paths says five of them are named by
**no** walk at all: `/tactics/gallery`, `/world/competitions`, `/world/matches`, `/world/news` and
`/world/teams`. Three more — `/portfolio`, `/club` and `/club/rules` — are read by their own tier's
walk and by no other, so the locale sweep, which is the visual walk's, never reads them in Chinese
either.

A page no walk reads is a page whose copy is unjudged and unproven: the sweep's claim is about the
pages it read, and the route-coverage check now says so at runtime, in the walk that can see it.

### The three fixes that question asked for

The same question, asked one layer deeper each time, found three things:

| the question | the finding | the fix |
| --- | --- | --- |
| does the sweep judge every page? | it judges the pages the walk **visited**, and that list was not printed | the sweep prints the pages it read, in full |
| does the walk visit every route the tree holds? | five routes are named by **no** walk, three more only by their own tier's | the visual walk opens the five, and the two that need a session **before it signs out** |
| is "visited" the same as "read"? | **no** — the walk signs out before the sweep, so a session-gated page redirects to the login | the sweep records the path the browser **landed on**, so a redirect is not a read |

The third is the one that would have lied: a coverage check that counted the path it asked for would
have called a redirected page read, and the check would have been green about a page nobody saw.

### The catalogue's own shape

A census of the catalogue's shape, asked because nobody had asked it: **41 namespaces and 3600 keys**,
the largest `club` at 449 and the smallest `validation` at **zero** — the namespace the dead-key
deletions left behind, holding nothing. It is gone: a namespace nothing reads is a translation that
ships to nobody, and this one shipped nothing at all. Forty namespaces, 3600 keys.

The census also counted the **sentences more than one key holds: 82** — "Tactical system" five times,
"Clear filters" and "Attribute profile" four each. A sentence written twice is a translation written
twice, and the two will drift, so that surface is measured now. Some of the repeats are the nav's
label and the page's own title, which differ in case by convention; the rest are the same sentence
under two surfaces, and the decision about them is its own slice rather than a gate's blind sweep.

**The split is what makes the 82 readable.** One of them is the nav's label against a page's own title
— the convention, and deliberate. **29** are inside one namespace: a tier's own name in its own
surfaces, which is deliberate too (the video tier's title is the same in its page title, its
unavailable notice and its link back). **52** are across namespaces, which is a translation written
twice, and the two will drift.

So the surface that needs a decision is the 52, not the 82 — and within them, some are a tier's name
wherever it appears ("Tactical system", five namespaces) and are deliberate, while the rest are
ordinary sentences that happen to be written twice. The gate to hold them would name each one with the
reason it is allowed, the way the locale-token gate names the technical tokens: a list without reasons
is the same as no list at all.
