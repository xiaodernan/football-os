# The message catalogues

Three files, one per locale (`apps/api/app/api/v1/meta.py` publishes them as `locales` and `locales_planned`):

| File | Holds today | Served today |
| --- | --- | --- |
| `en.json` | the interface's own strings | **yes**, and it is the fallback for every missing key |
| `zh.json` | 3460 of 3542 keys in Simplified Chinese, and all 3542 present | **yes** |
| `zh-TW.json` | 3461 of 3542 keys written in Traditional Chinese, not converted from the `zh` file, and all 3542 present | **yes** |

## What a reader gets today

Both Chinese catalogues cover every key the interface publishes. A new string added to `en.json` without
translations falls back per key until it is translated — which is the one way a page can show English inside a
Chinese interface now. Before 2026-10-01 the two Chinese files were **byte-for-byte the English values** with
Chinese filenames, and nothing read a catalogue anyway — the interface was English literals from top to bottom,
so the locale the middleware had always resolved was invisible. `apps/api/tests/test_locale_claims.py` is what
stopped that being invisible: it holds `locales` to these files in both directions.

**Every page reads the catalogue.** The arc that wired the interface namespace by namespace is finished: the copy gate (`apps/web/scripts/qa-i18n-literals.mjs`) reads **0 English literal sites** over every `app/**/*.tsx` and holds the count at 0, so a page that adds copy in English fails the build; the metadata gate agrees that every page's tab and heading is now locale-driven (**tabs keyed 51 / literal 0, headings keyed 43 / literal 0**). The 82 keys that still fall back are the ones that are *supposed* to: a value that is identical in both catalogues is a technical token - a product name, an enum, a unit - and the figures above are floors rather than pins, so a translation batch raises them without touching this file.

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
* **No key twice.** `json.load` keeps the last duplicate and drops the rest silently, so a translator editing the
  shadowed copy watches their change do nothing. All three files carried four such pairs when this was written
  (`common.{no,yes,close,error}`); the test parses the raw text, because every check that reads the parsed object
  is blind to them.

## Adding a string

Put it in `en.json`, then in the other two. If it is a *page*, wire it with `useTranslations`/`getTranslations`
rather than a literal — the nav (`components/Nav.tsx`) is the worked example, and it is the only component that
read a catalogue at all until 2026-10-02.
