"""§81's one claim about language, held to the catalogues it is a claim about.

`GET /capabilities` publishes `locales` — the languages the UI ships — and `locales_planned` — the ones the spec
asks for. The whole point of the pair is that the first is a promise and the second is a plan, so the first must
never be set by hand and left there. It was set by hand, in `app/api/v1/meta.py`, with a comment saying to switch
it when translations actually exist, and nothing checked that the switch happened or that it did not happen early.

**What "ships" means here.** `middleware.ts` answers a request in the best locale it carries, chosen from the
`fo_locale` cookie, the browser's `Accept-Language` and the account's own column — so the set of catalogues the
app carries *is* the set of languages it will answer in. A locale therefore ships as soon as its catalogue is not
merely a copy of English, and untranslated keys inside it fall back per key, which is what every i18n runtime
does and what a reader sees today. The alternative — advertising only a 100%-complete catalogue — sounds
stricter but is *less* true here: the middleware has always resolved `zh` for a Chinese browser, and before any
component read a catalogue nobody could tell, because the interface was English literals throughout.

That is also why this file exists. `zh.json` and `zh-TW.json` were, when it was written, byte-for-byte the
English values with Chinese filenames — 278 keys each, none translated — so `locales: ["en"]` was the true answer
and the app was serving English to everybody while claiming to have started three languages.

The assertion is an equality in both directions, because one direction alone is satisfiable by a lie: with only
the over-claiming check, a translated catalogue sits unadvertised forever; with only the stale-field check,
`locales` can be narrowed to nothing.

**Two things this file can see that nothing else can.** `json.load` keeps the last of a duplicated key and
discards the earlier one silently, so a key set compared as *parsed objects* cannot notice that the file declares
`common.error` twice — which all three catalogues did, four times over. And a catalogue that is *short* is worse
than one that is absent: a missing key is a blank on a page in a language nobody on this project reads.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.main import app

#: The catalogues live with the app that reads them. `parents[3]` is the repository root: this file is
#: `apps/api/tests/test_locale_claims.py`.
MESSAGES = Path(__file__).resolve().parents[3] / "apps" / "web" / "messages"
#: The language every other catalogue falls back to, and the one the interface is written in.
FALLBACK = "en"
#: Keys allowed to read the same in every language. Kept explicit rather than guessed from the value, so that
#: "this one does not need translating" is a decision somebody wrote down and can be argued with.
LANGUAGE_NEUTRAL: frozenset[str] = frozenset({"common.ok"})

#: A JSON leaf line: its indentation, its key, and whatever follows the colon.
_LEAF = re.compile(r'^(\s*)"([^"]+)":\s*(\{|.*)')


def _flatten(node: Any, prefix: str = "") -> dict[str, str]:
    """Every leaf as `dotted.key -> value`, so two catalogues can be compared without caring about nesting."""
    if isinstance(node, dict):
        flat: dict[str, str] = {}
        for key, value in node.items():
            flat.update(_flatten(value, f"{prefix}{key}."))
        return flat
    return {prefix.rstrip("."): str(node)}


def _raw(name: str) -> str:
    return (MESSAGES / f"{name}.json").read_text(encoding="utf-8")


def _names() -> list[str]:
    assert MESSAGES.is_dir(), f"the message catalogues are missing from {MESSAGES}"
    names = sorted(path.stem for path in MESSAGES.glob("*.json"))
    assert names, f"no catalogues under {MESSAGES}"
    return names


def _catalogues() -> dict[str, dict[str, str]]:
    return {name: _flatten(json.loads(_raw(name))) for name in _names()}


def _capabilities() -> dict[str, Any]:
    response = TestClient(app).get("/api/v1/capabilities")
    assert response.status_code == 200, response.text
    return response.json()


def _untranslated(catalogues: dict[str, dict[str, str]]) -> dict[str, list[str]]:
    """Per locale, the keys still holding the English value — ignoring the language-neutral allowlist."""
    english = catalogues[FALLBACK]
    return {
        locale: sorted(key for key, value in english.items() if key not in LANGUAGE_NEUTRAL and values.get(key) == value)
        for locale, values in catalogues.items()
        if locale != FALLBACK
    }


def _shipped(catalogues: dict[str, dict[str, str]]) -> list[str]:
    """The locales whose catalogue is not merely the English one — what `middleware.ts` will answer in."""
    english = catalogues[FALLBACK]
    return sorted(locale for locale, values in catalogues.items() if locale != FALLBACK and any(values.get(key) != value for key, value in english.items()))


def test_no_catalogue_declares_a_key_twice() -> None:
    """A duplicate key is invisible to every reader that parses the file, including the checks in this module.

    `json.load` keeps the last and drops the rest without a word, so `common.error` declared twice looks like one
    key to the app, to a diff, and to the key-set assertions below. All three catalogues carried four such pairs
    (`common.{no,yes,close,error}`) when this test was written; the values happened to agree, which is why nobody
    noticed, and a translator editing the shadowed copy would have watched their change do nothing.
    """
    for name in _names():
        seen: set[str] = set()
        duplicates: list[str] = []
        path: list[str] = []
        for line in _raw(name).splitlines():
            match = _LEAF.match(line)
            if not match:
                continue
            indent, key, tail = match.group(1), match.group(2), match.group(3)
            path = path[: len(indent) // 2 - 1]
            if tail == "{":
                path.append(key)
                continue
            full = ".".join([*path, key])
            if full in seen:
                duplicates.append(full)
            seen.add(full)
        assert not duplicates, f"{name}.json declares {len(duplicates)} key(s) twice: {duplicates}"


def test_every_catalogue_carries_the_same_keys_as_the_fallback() -> None:
    """A translation may be missing, but it may not be *short*: a dropped key is a blank on a page in that locale."""
    catalogues = _catalogues()
    english = catalogues[FALLBACK]
    for locale, values in catalogues.items():
        if locale == FALLBACK:
            continue
        missing = sorted(set(english) - set(values))
        extra = sorted(set(values) - set(english))
        assert not missing, f"{locale} is missing {len(missing)} key(s) the fallback has, e.g. {missing[:3]}"
        assert not extra, f"{locale} carries {len(extra)} key(s) the fallback does not, e.g. {extra[:3]}"


def test_the_published_locales_are_the_ones_the_app_will_answer_in() -> None:
    """`locales` must name exactly the catalogues that are not copies of English — no more, no fewer.

    The failure message names the keys still holding English, because a partially translated catalogue is served
    and the count is the work remaining rather than a reason to withhold it.
    """
    catalogues = _catalogues()
    shipped = _shipped(catalogues)
    left = _untranslated(catalogues)
    body = _capabilities()
    published = list(body["locales"])
    remaining = " · ".join(f"{locale} has {len(keys)} key(s) still falling back to English" for locale, keys in left.items() if keys)
    assert published == [FALLBACK, *shipped], f"`locales` says {published} and the catalogues say {[FALLBACK, *shipped]}. {remaining}"


def test_the_plan_still_covers_what_ships_and_what_is_promised() -> None:
    """`locales_planned` is a plan: it must include what ships, and it must not quietly drop a promised locale."""
    body = _capabilities()
    planned = list(body["locales_planned"])
    assert set(body["locales"]) <= set(planned), f"{body['locales']} ships but {planned} does not plan for it"
    # The spec's own three. Removing one from the plan is a scope decision that belongs in a document, not a diff.
    assert {"en", "zh", "zh-TW"} <= set(planned), f"the spec's three locales are not all planned: {planned}"
    assert set(planned) <= set(_catalogues()), f"a planned locale has no catalogue at all: {sorted(set(planned) - set(_catalogues()))}"
