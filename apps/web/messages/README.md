# The message catalogues

Three files, one per locale (`apps/api/app/api/v1/meta.py` publishes them as `locales` and `locales_planned`):

| File | Holds today | Served today |
| --- | --- | --- |
| `en.json` | the interface's own strings | **yes**, and it is the fallback for every missing key |
| `zh.json` | 3791 of 3836 keys in Simplified Chinese, and all 3836 present (the other 45 are placeholders, machine tokens and acronyms that are identical in every locale) | **yes** |
| `zh-TW.json` | 3791 of 3836 keys written in Traditional Chinese, not converted from the `zh` file, and all 3836 present (same 45 identical tokens) | **yes** |

## What a reader gets today

Both Chinese catalogues cover every key the interface publishes. A new string added to `en.json` without
translations falls back per key until it is translated — which is the one way a page can show English inside a
Chinese interface now. Before 2026-10-01 the two Chinese files were **byte-for-byte the English values** with
Chinese filenames, and nothing read a catalogue anyway — the interface was English literals from top to bottom,
so the locale the middleware had always resolved was invisible. `apps/api/tests/test_locale_claims.py` is what
stopped that being invisible: it holds `locales` to these files in both directions.

**Every page reads the catalogue.** The arc that wired the interface namespace by namespace is finished: the copy gate (`apps/web/scripts/qa-i18n-literals.mjs`) reads **0 English literal sites** over every `app/**/*.tsx` **and every `components/**/*.tsx`**, and it holds the count at 0 on two floors: the three shapes the arc knew about (JSX text, a label-ish attribute, a label-ish object property) and the **fifth** shape it found on 2026-10-21 — a string literal that reaches the reader from somewhere else, a sentence a helper returns, a wording a ternary chooses, or a template that assembles one. Both are 0 now, so a page that adds copy in English fails the build; the metadata gate agrees that every page's tab and heading is now locale-driven (**tabs keyed 51 / literal 0, headings keyed 43 / literal 0**). The gate's **fifth check** holds the other half of the contract: a key read without the values its message needs prints the placeholders themselves, so every key call is checked for its values as well as for its existence. The 45 keys that still fall back in `zh.json` (45 in `zh-TW.json`) are the ones that are *supposed* to: a value that is identical in both catalogues is a technical token - a product name, an enum, a unit - and the translated counts above are floors rather than pins, so a translation batch raises them without touching this file. That set is **named**, not assumed: `apps/web/scripts/qa-locale-tokens.mjs` lists all 44 with the reason each one is the same in every language (an acronym, an API field name printed as itself, a template of names, a proper name used as an example), and a value that is identical without a name is a finding. The same gate holds the other half — **the English catalogue holds no Chinese**, which it did not before 2026-10-22 (`en.json` carried `scout.placeholder` as a Chinese sentence, so an English reader saw Chinese and the Chinese copy of it made the coverage figures call it translated). The **population** is a pin, not a floor: `test_locale_claims.py` recomputes it from `en.json` and fails if this table's number is not the number of keys the catalogue holds, so a key added or removed here without this table being recomputed fails the suite.

### The 0 was wrong twice, and the gate that found it (2026-10-21)

The "0 English literal sites" above was **an artefact of a rule**, not a measurement, and it took a
browser to find it. The gate decided a string was "already translated" by asking whether it held
*any* character outside ASCII — and a middle dot, an em dash, a curly apostrophe and a `×` are all
outside ASCII. Every English sentence in this project that contained one of those marks was read as
Chinese and was never counted. The rule now asks whether the string holds a **letter** from another
script, and the moment it did, the gate reported **47 English strings across 15 files** that the arc
had left behind: the settings page's ten milestone labels, the pitch's axis labels and captions, the
scout workbench's eyebrows, the erase row's sentence, the page title template. All of them are now in
the catalogue, and both floors are 0 again — with a gate that can see them.

The lesson is the one the project's gates exist for: **a floor is a statement about the gate before it
is a statement about the tree.** A gate that cannot see a class of defect holds its floor for a
reason that has nothing to do with the code it is watching. This is the second time the arc's own
ceiling has been found to be narrower than it looked — the first was the fifth shape, a string a helper
returns that no JSX-shaped scan reaches — and both times the **browser** found it, because the source
is where a gate looks and the page is where the copy lives.

## The rule

`locales` names every catalogue that is not merely a copy of English. `middleware.ts` answers a request in the
best locale it carries — from the `fo_locale` cookie, the browser's `Accept-Language`, then the account's own
column — so "a catalogue that is not a copy" and "a language a reader can be served" are the same set. A locale
is not withheld until it is complete; missing keys fall back, which is what every i18n runtime does.

`apps/api/tests/test_locale_claims.py` asserts this both ways, and a locale that is a copy fails the suite:

1. translate any value in `zh.json` so it differs from `en.json`;
2. run the suite — it now fails and names the locale, and prints how many keys still fall back;
3. add that locale to `locales` in `app/api/v1/meta.py`;
4. the suite passes.

The reverse also fails: advertising a locale whose catalogue is still a copy. That was the state all three files
were in, and it is the check that would have caught somebody switching the field early.

## Two things to keep true

* **A key must exist in all three files.** A translation may be *missing* — it falls back — but a catalogue that
  is *short* is worse than one that is absent, because a dropped key is a blank on a page in a language nobody
  on this project reads.
* **A key must parse.** A catalogue message is a program, not a string: next-intl parses it when the page
  renders it, and a message that does not parse throws instead of printing. Nothing in the build reads a
  catalogue — next-intl resolves a key in the browser — so a malformed message compiles, typechecks, lints and
  then 500s the page that reads it. `apps/web/scripts/qa-icu-messages.mjs` parses **every** message in all
  three files with the app's own ICU parser, refuses a plural or a select with no `other` branch, and holds the
  same key to the same placeholders in all three. It was written on 2026-10-21 and found five messages written
  with mustache placeholders (`{{count}}`), which ICU reads as an argument that never began: they are fixed,
  and the gate now keeps that class out.
* **No key twice.** `json.load` keeps the last duplicate and drops the rest silently, so a translator editing the
  shadowed copy watches their change do nothing. All three files carried four such pairs when this was written
  (`common.{no,yes,close,error}`); the test parses the raw text, because every check that reads the parsed object
  is blind to them.
* **A refusal is the reader's copy too.** The `errors` namespace holds one key per refusal code the API publishes, and the **English value is the API's message verbatim** — so the English rendering is byte-identical and the change is a translation rather than a copy change. The code itself needs no translation: it is the locale-neutral handle the page prints beside the sentence. The API's other 39 codes publish a message that names a value the request supplied (“philosophy must be one of […]”) or that a helper chooses at the raise site (“The current password is incorrect”), so the catalogue cannot reproduce them; they keep the API's own words and are **named** in `apps/api/tests/test_locale_claims.py`, which holds the catalogue and the API in step in both directions.
* **A key must be asked for.** The other half of the contract, and the one nothing had ever checked: a key no
  page reads is a translation that ships to nobody — written three times, and re-read whenever the message beside
  it changes. `apps/web/scripts/qa-unused-keys.mjs` resolves every read in the web tier and reports the keys no
  read can reach. On 2026-10-22 it found **226**, and all of them are now gone from all three files: **63** held
  the **same English sentence as a key that is read** (`nav.video` and `nav.videoShort`, `nav.login` and
  `auth.signIn`, `common.pitchCaption3d` and `tactics.pitchCaption3d`); **67** were a shared vocabulary for copy
  the interface never wrote (the verbs and prepositions `common.or`, `common.and`, `common.of`, `common.retry`,
  written so a sentence could be assembled from parts, and never assembled, because every message here is a whole
  sentence); and the last **96** were the club tier's rules, the sign-up and password-reset flows, the validation
  messages and the nav entries for pages the nav does not offer — of which **36** held nothing but a placeholder
  name (`club.matrixRule` is `"{rule}"`), so they were not translations at all, and **26** were never translated
  and were sitting in the Chinese catalogues as English. **The floor is 0**: every key this catalogue holds is
  asked for by a page. A read the gate cannot resolve **exempts its whole namespace** rather than guessing, so a
  key that cannot be shown to be dead is never reported as dead.

## Adding a string

Put it in `en.json`, then in the other two. If it is a *page*, wire it with `useTranslations`/`getTranslations`
rather than a literal — the nav (`components/Nav.tsx`) is the worked example, and it is the only component that
read a catalogue at all until 2026-10-02.
