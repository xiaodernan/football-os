# The message catalogues

Three files, one per locale the spec asks for (`apps/api/app/api/v1/meta.py` publishes them as `locales_planned`):

| File | Holds today | Advertised today |
| --- | --- | --- |
| `en.json` | the interface's own strings | **yes** |
| `zh.json` | the same strings, copied | no |
| `zh-TW.json` | the same strings, copied | no |

## Read this before trusting a filename

`zh.json` and `zh-TW.json` are **not translations**. They carry all 278 keys and every one of those values is the
English value, byte for byte — they are copies with Chinese filenames. `GET /capabilities` says
`locales: ["en"]`, and that is the true answer; `locales_planned: ["en","zh","zh-TW"]` is the plan.

The files exist so the key set is fixed before the translating starts. A catalogue that is *short* is worse than
one that is absent: a missing key is a blank on a page in that locale, and nobody notices a blank in a language
they do not read.

## The rule for switching `locales`

`locales` names the languages whose catalogue is not the English one. It is asserted against these files by
`apps/api/tests/test_locale_claims.py`, in both directions:

* a locale in `locales` whose catalogue is a copy of English **fails** the suite;
* a catalogue that differs from English and is *not* in `locales` **also fails**.

So the switch is not a judgement call and not a hand-edit somebody has to remember:

1. translate a value in `zh.json` so it differs from `en.json`;
2. run the suite — it now fails and names the locale;
3. add that locale to `locales` in `app/api/v1/meta.py`;
4. the suite passes.

Step 2 is the point. A partially translated catalogue is advertised as soon as one value differs, which is
deliberate: the field answers "is this language shipped", and half a translation is shipped. What it must never
answer is "yes" while the pages still read English, which is the state all three files are in today.
