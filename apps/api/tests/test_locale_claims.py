"""§81's one claim about language, held to the catalogues it is a claim about.

`GET /capabilities` publishes `locales` — the languages the UI ships — and `locales_planned` — the ones the spec
asks for. The whole point of the pair is that the first is a promise and the second is a plan, so the first must
never be set by hand and left there. It is set by hand today, in `app/api/v1/meta.py`, with a comment saying to
switch it when translations actually exist, and nothing checks that the switch happened or that it did not happen
early.

It did not happen early, and that is worth recording: `messages/zh.json` and `messages/zh-TW.json` exist, carry
all 278 keys, and are **byte-for-byte the English values** — copies with Chinese filenames. The field says
`["en"]`, which is true. Switching it today would tell every client the interface ships Chinese while the
interface still reads English, and that is the exact class of lie the rest of this project spends its tests
preventing.

So this file holds the claim to the files it is about, in both directions:

* every locale in `locales` must have a catalogue that actually differs from English;
* every catalogue that differs from English must appear in `locales`.

The first direction is the one that matters today: it fails the moment somebody sets `locales: ["en","zh"]`
without translating anything. The second fails when a real translation lands and the field is not moved with it,
which is the reminder the hand-written field needs and cannot give itself.

Both directions are needed because one alone is satisfiable by a lie: only the first, and an untranslated
catalogue sits unadvertised forever; only the second, and `locales` can be narrowed to nothing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.main import app

#: The catalogues live with the app that reads them. `parents[3]` is the repository root: this file is
#: `apps/api/tests/test_locale_claims.py`.
MESSAGES = Path(__file__).resolve().parents[3] / "apps" / "web" / "messages"
#: The language every other catalogue falls back to, and the one the interface is written in.
FALLBACK = "en"


def _flatten(node: Any, prefix: str = "") -> dict[str, str]:
    """Every leaf as `dotted.key -> value`, so two catalogues can be compared without caring about nesting."""
    if isinstance(node, dict):
        flat: dict[str, str] = {}
        for key, value in node.items():
            flat.update(_flatten(value, f"{prefix}{key}."))
        return flat
    return {prefix.rstrip("."): str(node)}


def _catalogues() -> dict[str, dict[str, str]]:
    assert MESSAGES.is_dir(), f"the message catalogues are missing from {MESSAGES}"
    files = sorted(MESSAGES.glob("*.json"))
    assert files, f"no catalogues under {MESSAGES}"
    return {path.stem: _flatten(json.loads(path.read_text(encoding="utf-8"))) for path in files}


def _capabilities() -> dict[str, Any]:
    response = TestClient(app).get("/api/v1/capabilities")
    assert response.status_code == 200, response.text
    return response.json()


def _translated(catalogues: dict[str, dict[str, str]]) -> list[str]:
    """A locale is translated when at least one of its values is not the English one.

    Deliberately a value-level test rather than a filename test. A file named `zh.json` full of English is not a
    translation, and the difference is the whole subject of this module.
    """
    english = catalogues[FALLBACK]
    return sorted(
        locale for locale, values in catalogues.items() if locale != FALLBACK and any(values.get(key) != value for key, value in english.items())
    )


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


def test_the_published_locales_are_the_ones_with_something_to_show() -> None:
    """`locales` must name exactly the languages whose catalogue is not the English one — no more, no fewer.

    The failing direction today is over-claiming: a catalogue that is a copy of English must not be advertised.
    The other direction is why the assertion is an equality rather than a subset — a real translation landing
    without the field moving is the same defect read the other way, and this is the only place that can notice.
    """
    catalogues = _catalogues()
    translated = _translated(catalogues)
    body = _capabilities()
    published = list(body["locales"])
    untranslated = sorted(set(catalogues) - {FALLBACK} - set(translated))
    assert published == [FALLBACK, *translated], (
        f"`locales` says {published} and the catalogues say {[FALLBACK, *translated]}. "
        f"The catalogue(s) {untranslated} currently hold the English values, so advertising them would claim a "
        f"translation that does not exist."
    )


def test_the_plan_still_covers_what_ships_and_what_is_promised() -> None:
    """`locales_planned` is a plan: it must include what ships, and it must not quietly drop a promised locale."""
    body = _capabilities()
    planned = list(body["locales_planned"])
    assert set(body["locales"]) <= set(planned), f"{body['locales']} ships but {planned} does not plan for it"
    # The spec's own three. Removing one from the plan is a scope decision that belongs in a document, not a diff.
    assert {"en", "zh", "zh-TW"} <= set(planned), f"the spec's three locales are not all planned: {planned}"
    assert set(planned) <= set(_catalogues()), f"a planned locale has no catalogue at all: {sorted(set(planned) - set(_catalogues()))}"
