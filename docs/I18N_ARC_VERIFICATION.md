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

### The honest remainder

The claim "the interface is in the reader's language" now holds for the interface's **own** copy **and**
for the refusals the catalogue can reproduce. It does **not** hold for the refusals whose message names
a value the request supplied — those are the API's own words, and the catalogue cannot carry a value it
does not have. Each of them needs a catalogue sentence written for the reader, and each one lowers the
named list; that is the next slice, and it is text work rather than mechanism.
