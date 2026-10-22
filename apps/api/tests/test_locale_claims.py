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

**The prose is part of the claim.** Five carriers describe these catalogues in the present tense, and on
2026-10-21 they named three different denominators for the same file — 288, 393 and 2890 — while the repo's front
door still said the translation layer was not built. A figure in prose has no reader, so the only figure allowed
to persist is the one `test_the_readme_table_states_the_coverage…` recomputes from the catalogues on every run;
the others must not state one at all. Dated run records (`PLAN.md`, `ROADMAP.md`, the M3/M4 verification logs) are
outside that population by identity, not by pattern: a figure measured at a named run is evidence about that run,
and rewriting it to today's number would destroy the record. `docs/SEO_VERIFICATION.md` is *inside* it: it
specifies the layer, so its present tense is a claim about today.
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

#: The repository root, for the carriers that *describe* these files rather than hold them.
REPO = Path(__file__).resolve().parents[3]

#: The one place a coverage figure may live, because `test_the_readme_table_recomputes…` below recomputes it.
README = "apps/web/messages/README.md"

#: Carriers that describe the catalogues in the present tense. A dated run record — `PLAN.md`, `ROADMAP.md`,
#: `docs/*_VERIFICATION.md` — is exempt by identity, not by pattern: a figure measured at a named run is evidence
#: about that run, and re-writing it to today's number would destroy the record. What may not happen is a
#: *undated* sentence about today carrying a number nobody recomputes.
PROSE_CARRIERS: tuple[str, ...] = ("README.md", "ARCHITECTURE.md", "CONTRIBUTING.md", "apps/api/app/api/v1/meta.py", "docs/SEO_VERIFICATION.md")

#: The exact spellings of the claim that no i18n exists. Contradicted by the tree since 2026-10-01; all three were
#: live sentences on 2026-10-21, in the two places a reader starts from — the repository README and the SEO record —
#: while `ARCHITECTURE.md` §6 said i18n was built. Each claim is retired by naming it, so a future edit that writes
#: it again has to delete this entry first, which is the argument.
CHARGED_CLAIMS: tuple[tuple[str, str], ...] = (
    ("README.md", "The UI speaks English only today"),
    ("README.md", "the translation layer itself is not built yet"),
    ("docs/SEO_VERIFICATION.md", "## 5. i18n (spec §81) — not built"),
    ("docs/SEO_VERIFICATION.md", "The UI is English-only"),
)

#: A coverage fraction as prose writes it: `287/288`, `392 of 393`, `2816 of 2890`.
_COVERAGE = re.compile(r"(\d{2,5})\s*(?:/\s*|\bof\s+(?:the\s+)?)(\d{2,5})")

#: What makes a line about these files rather than about some other pair of numbers in the same document.
_NEAR_LOCALE = re.compile(r"zh-TW|zh\.json|`zh`|catalou?gue|locale|key", re.IGNORECASE)

#: The lowest figure the README may state per locale. Floors, not pins: translating a key raises what the catalogue
#: holds without touching the prose, and a pinned equality would make every translation batch edit this file.
#: What the pair of assertions below refuses is the direction that lies — a stated count above the real one, or a
#: denominator that is not the live key population.
README_FLOORS: dict[str, int] = {"zh": 2816, "zh-TW": 2817}


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


def _prose(rel: str) -> list[str]:
    path = REPO / rel
    assert path.is_file(), f"the locale carrier {rel} is missing, so the check that reads it is blind"
    return path.read_text(encoding="utf-8").splitlines()


def _coverage_claims(rel: str) -> list[str]:
    """Lines in a prose carrier that state a locale coverage figure — `287/288`, `392 of 393 keys`."""
    return [f"{rel}:{i} {line.strip()[:70]!r}" for i, line in enumerate(_prose(rel), 1) if _NEAR_LOCALE.search(line) and _COVERAGE.search(line)]


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


def test_the_readme_table_states_the_coverage_the_catalogues_actually_have() -> None:
    """The one figure prose may state about translation progress is recomputed here, from these files.

    Three carriers named three denominators for the same catalogue on the day this case was written — `ARCHITECTURE.md`
    and `meta.py` said 288, `messages/README.md` said 393, and `en.json` held 2890 keys — and none of them could fail
    anything, because a number in prose has no reader. The population is what drifts silently: every key added to the
    interface moves it, so it is pinned to equality. The numerator is pinned below the real count and above a floor,
    which forbids over-claiming progress without forcing a prose edit every time somebody translates a key.
    """
    catalogues = _catalogues()
    left = _untranslated(catalogues)
    total = len(catalogues[FALLBACK])
    lines = _prose(README)
    for locale in sorted(k for k in catalogues if k != FALLBACK):
        row = next((line for line in lines if f"`{locale}.json`" in line and line.lstrip().startswith("|")), None)
        assert row is not None, f"{README} has no table row for {locale}, so nothing recomputes its coverage"
        found = _COVERAGE.search(row)
        assert found is not None, f"the {locale} row states no `N of M` figure: {row.strip()[:70]!r}"
        stated, population = int(found.group(1)), int(found.group(2))
        translated = total - len(left[locale])
        assert population == total, f"the {locale} row counts a population of {population}; `en.json` holds {total} keys"
        assert stated <= translated, f"the {locale} row claims {stated} translated keys, the catalogue holds {translated}"
        assert stated >= README_FLOORS[locale], f"the {locale} row fell below its floor of {README_FLOORS[locale]}: {stated}"


def test_no_other_carrier_states_a_locale_figure() -> None:
    """A second place to state a figure is a second place to be wrong, so prose names the table instead.

    The regex is pinned to a positive control below: a ban that matches nothing is not a ban, and the two carriers
    this case was written to cure — `ARCHITECTURE.md:130` and `meta.py:131`, both reading `287/288` — prove it matches
    the spelling they used.
    """
    assert _COVERAGE.search("both Chinese catalogues carry the full key set (`zh` 287/288") is not None
    offenders = [claim for rel in PROSE_CARRIERS for claim in _coverage_claims(rel)]
    assert not offenders, f"{len(offenders)} locale figure(s) stated outside {README}, which no reader recomputes: {' · '.join(offenders[:3])}"
    charged = [f"{rel} carries {text!r}" for rel, text in CHARGED_CLAIMS if any(text in line for line in _prose(rel))]
    assert not charged, f"a retired claim about i18n is back: {' · '.join(charged)}"


#: The API's own source, for the refusal census below.
APP_SOURCE = Path(__file__).resolve().parents[1] / "app"

#: A refusal's code and message, as a door writes them: `detail={"code": ..., "message": ...}`.
#: The code is a literal or a module-level constant; the message is a literal, an f-string, or a
#: variable a helper filled in — which is what makes a message *not* fixed.
_REFUSAL = re.compile(
    r"""["']code["']\s*:\s*(?:["']([a-z][a-z0-9_]{2,48})["']|([A-Z][A-Z0-9_]{2,}))"""
    r"""\s*,\s*["']message["']\s*:\s*(?:(f?)(["'])(.*?)(?<!\\)\4|([A-Za-z_][A-Za-z0-9_]*))""",
    re.DOTALL,
)

#: The four handlers' own answers: `_answer("code", "message")`.
_ANSWERED = re.compile(r"""_answer\(\s*["']([a-z][a-z0-9_]{2,48})["']\s*,\s*(f?)(["'])(.*?)(?<!\\)\3""", re.DOTALL)

#: A module-level constant: `NAME = "value"` or `NAME: Final = "value"`.
_CONSTANT = re.compile(r"""^([A-Z][A-Z0-9_]{2,})\s*(?::[^=]+)?=\s*["']([a-z][a-z0-9_]{2,48})["']""", re.MULTILINE)

#: The refusal codes whose message the catalogue cannot reproduce, and why they are named rather than
#: translated. Every one of them either names a value the request supplied ("philosophy must be one of
#: [...]") or is chosen by a helper at the raise site ("The current password is incorrect"). The
#: catalogue cannot hold a sentence that changes with the request, so these keep the API's own words —
#: and a new code has to be added here before it can be published, which is the point of the list.
NOT_FIXED_CODES: frozenset[str] = frozenset(
    {
        "account_delete_confirmation",
        "account_inactive",
        "bad_minutes",
        "bad_objective",
        "bad_philosophy",
        "bad_status",
        "board_limit",
        "cannot_choose_club",
        "cannot_play",
        "career_limit",
        "insufficient_role",
        "invalid_board",
        "invalid_password",
        "job_not_cancellable",
        "job_not_deletable",
        "media_tools_missing",
        "no_fixture",
        "no_such_challenge",
        "no_such_club",
        "no_such_frame",
        "no_such_input",
        "no_such_job",
        "no_such_memory",
        "no_such_system",
        "no_such_team",
        "no_such_trace",
        "not_found",
        "private_media_not_erased",
        "range_not_satisfiable",
        "run_limit",
        "simulation_limit",
        "too_large",
        "transfers_forbidden",
        "unknown_agent_type",
        "unknown_change",
        "unsupported_container",
        "video_limit",
        "window_closed",
        "wrong_path",
    }
)


def _refusals() -> dict[str, dict[str, Any]]:
    """Every refusal code the API publishes, with the messages it publishes for it."""
    constants: dict[str, str] = {}
    found: dict[str, dict[str, Any]] = {}
    for path in sorted(APP_SOURCE.rglob("*.py")):
        if "tests" in path.parts:
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        constants.update(dict(_CONSTANT.findall(source)))
        pairs = [(code, "", f, q, message, "") for code, f, q, message in _ANSWERED.findall(source)]
        for literal, name, is_f, _quote, message, variable in _REFUSAL.findall(source) + pairs:
            code = literal or constants.get(name)
            if not code:
                continue
            entry = found.setdefault(code, {"messages": set(), "dynamic": False})
            if variable or is_f or "{" in message or not re.search(r"[A-Za-z]", message):
                entry["dynamic"] = True
            else:
                entry["messages"].add(message)
    return found


def test_every_refusal_the_api_publishes_has_a_catalogue_sentence() -> None:
    """A refusal is the reader's copy, so the catalogue holds it — and the two cannot drift.

    The API answers a refusal with a **code** and a **sentence**, and the web tier shows the sentence:
    `errorMessage()` returns `error.message`. So a Chinese reader was told "The current password is
    incorrect" in English, on a page whose every other sentence came from the Chinese catalogue.

    The catalogue now holds one key per refusal code, with the **English value being the API's message
    verbatim** — so the English rendering is byte-identical and this is a translation rather than a copy
    change — and the code needs no translation at all.

    This case holds the two in step in both directions:

    * every code the API publishes with a **fixed** message has a catalogue key, and the catalogue's
      English value is that message, so the two cannot drift apart;
    * every `errors.*` key the catalogue holds is such a code, so a key nothing reads cannot sit in
      the catalogue;
    * every code whose message is **not** fixed is named in `NOT_FIXED_CODES`, so a new refusal has to
      be classified before it can be published — a list without reasons is the same as no list at all.
    """
    refusals = _refusals()
    assert refusals, "the refusal census found no code at all, so every check below would pass by finding nothing"

    fixed = {
        code: sorted(entry["messages"])
        for code, entry in refusals.items()
        if not entry["dynamic"] and len(entry["messages"]) == 1
    }
    not_fixed = {code for code, entry in refusals.items() if code not in fixed}

    catalogue = _catalogues()[FALLBACK]
    sentences = {key.split(".", 1)[1]: value for key, value in catalogue.items() if key.startswith("errors.")}

    missing = [
        f"{code} -> {messages[0]!r}"
        for code, messages in sorted(fixed.items())
        if code not in sentences
    ]
    assert not missing, (
        f"{len(missing)} refusal code(s) the API publishes with a fixed message have no catalogue "
        f"sentence, so a reader is shown the API's English: {missing[:4]}"
    )

    drifted = [
        f"{code}: catalogue {sentences[code]!r} != API {messages[0]!r}"
        for code, messages in sorted(fixed.items())
        if sentences[code] != messages[0]
    ]
    assert not drifted, (
        f"{len(drifted)} catalogue sentence(s) no longer match the API's message, so the English "
        f"rendering would change: {drifted[:4]}"
    )

    unheld = sorted(sentences.keys() - set(refusals))
    assert not unheld, (
        f"{len(unheld)} catalogue sentence(s) name a code the API does not publish at all: {unheld[:4]}"
    )

    # A code the census calls *not fixed* may still carry a catalogue sentence: the message names a
    # value the request supplied, and a helper chooses it at the raise site, but the sentence itself
    # can be fixed by the caller — `invalid_password` is "The current password is incorrect" at every
    # call site, even though the helper takes it as an argument. So the rule is: every code either
    # carries a sentence or is named, and a named code that carries one is held to the same contract.
    unnamed = sorted(not_fixed - set(NOT_FIXED_CODES) - set(sentences))
    assert not unnamed, (
        f"{len(unnamed)} refusal code(s) publish a message the catalogue neither carries nor names: "
        f"{unnamed[:4]}"
    )

    stale = sorted(NOT_FIXED_CODES - not_fixed)
    assert not stale, (
        f"{len(stale)} named code(s) now publish a fixed message, so the catalogue should carry them: "
        f"{stale[:4]}"
    )

    # A sentence that does not match the API's message is a drift, and the English rendering would
    # change with it: the catalogue's English value IS what an English reader is shown.
    drifted = [
        f"{code}: catalogue {sentences[code]!r} != API {entry['messages']!r}"
        for code, entry in sorted(refusals.items())
        if code in sentences
        and not entry["dynamic"]
        and len(entry["messages"]) == 1
        and sentences[code] != next(iter(entry["messages"]))
    ]
    assert not drifted, (
        f"{len(drifted)} catalogue sentence(s) no longer match the API's message, so the English "
        f"rendering would change: {drifted[:4]}"
    )
