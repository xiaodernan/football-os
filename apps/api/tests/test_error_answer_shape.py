"""§51's other half: one refusal *shape*, at every door and at each of the four handlers.

`tests/test_authorization_census.py` proved that every 403 this API answers comes from a code the assembled table
knows. This file asks what a code's *address* raises, which nothing measured before it: when a client is refused,
where does it look?

Two walks, two populations, deliberately not comparable. The richer one (`.scratch/r69_census.py`, artifact
`.scratch/r69_census.out`, on a `git archive HEAD` plane at `ad7b6d7`) follows constants and helper returns as
well as literals: **101** refusal-spelling rows across **18** modules, **51** distinct codes. The walk below is
literal-only — it reads a dict written at its own answer site — and on the working copy sees **72** refusal dicts
across **14** modules, **48** codes, plus one non-refusal `JSONResponse` body (`app/main.py:156`, `/healthz`).
The subset is not a disagreement: `ClubRefusal.to_dict()` and the five `*_CODES` sets in `services/club/answers.py`
carry codes this walk cannot see, which is exactly why the floors are set from this walk's own count. Run against
a committed plane rather than a working copy the same walk sees **63** across **14** modules (the working copy's
72 includes an untracked router), which is what the three floors below sit under.

What was wrong, and why it was user-visible rather than cosmetic: every door raises
`HTTPException(…, detail={"code", "message", …})`, so a code has always sat at `detail.code`. The four handlers in
`app/core/errors.py` answered `{"error": {…}}` instead, and a class in the same module (`AppError`, zero raise
sites repo-wide, one importer of the module: `app/main.py:41`) nested it a third way, `{"detail": {"error": …}}`.
`normalizeError` in `apps/web/lib/api.ts` reads `payload.detail` when that key exists and otherwise treats the
whole payload as the refusal, so a handler answer gave it no `code`, no `message` and no `details`, and the page
printed its fallback string. Reproduce it through the product: `/register` with a one-character display name
passes the form's own check (it only tests for empty), `RegisterIn.display_name` is `min_length=2`, so the answer
is a 422 — and `_rejected` had already built the list saying *which box, which rule*, with the typed value
deliberately dropped for §40's minors' data promise. All of that arrived in a shape the reader ignores.

Which case holds which half:

* the three behavioural cases go red the moment a handler wraps again anywhere else — they are the ones the
  mutation arms kill;
* the installer's own syntax tree is checked per handler, so a fifth handler that hand-writes a body cannot
  slip in unnoticed (the census below is literal-only and would not see it);
* the census floor is counted by the same walk as the census, so "nobody else wraps" cannot be read as "the
  scan saw nothing to check".
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.core import errors


def _app_root() -> Path:
    root = Path(errors.__file__).resolve().parent.parent
    assert root.name == "app", f"errors.__file__ is {errors.__file__}, which is not this app's package"
    return root


def _http_answer_dicts(app_root: Path) -> list[tuple[str, int, str, ast.Dict]]:
    """(module, line, kind, node) for every dict literal this API hands straight to an HTTP answer.

    `kind` is `detail` when the dict is the `detail=` keyword of an `HTTPException`, and `body` when it is the
    positional payload of a `JSONResponse`. One walk of one parsed tree per module produces both the population
    and its floor, so the two cannot disagree the way two scans can.
    """
    out: list[tuple[str, int, str, ast.Dict]] = []
    for path in sorted(app_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        module = path.relative_to(app_root.parent).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
            if fn == "HTTPException":
                for kw in node.keywords:
                    if kw.arg == "detail" and isinstance(kw.value, ast.Dict):
                        out.append((module, kw.value.lineno, "detail", kw.value))
            elif fn == "JSONResponse" and node.args and isinstance(node.args[0], ast.Dict):
                out.append((module, node.args[0].lineno, "body", node.args[0]))
    assert len(out) > 0, "the walk read no answer dicts at all — it is pointed at the wrong tree"
    return out


def _keys(node: ast.Dict) -> set[Any]:
    return {k.value for k in node.keys if isinstance(k, ast.Constant)}


def _first_arg_producer(node: ast.Call) -> str:
    """The bare name of the callable that built this call's first positional argument.

    `JSONResponse(_answer(…))` puts a `Call` in `args[0]`, so the producer's name sits on that call's `func`, not
    on the argument node itself; reading `args[0].id` would answer `""` for the shipped code and for any hand-
    written body alike, which is a check that cannot fail.
    """
    if not node.args:
        return ""
    first = node.args[0]
    return getattr(getattr(first, "func", first), "id", "")


class _Probe(BaseModel):
    count: int = Field(ge=1, le=3)


def _app_with_handlers() -> FastAPI:
    """An app whose only error machinery is the shipped installer, with one route per handler.

    `RequestValidationError` is not here because the real app already exercises it through `/register` below;
    these three routes exist so the other three handlers are reached as handlers, not inferred from a door.
    """
    app = FastAPI()
    errors.install_error_handlers(app)

    @app.get("/conflict")
    def _conflict() -> None:
        raise IntegrityError("INSERT INTO players ...", {"id": 1}, Exception('duplicate key value violates unique constraint "players_email_key"'))

    @app.get("/invalid")
    def _invalid() -> None:
        _Probe.model_validate({"count": 99})

    @app.get("/boom")
    def _boom() -> None:
        raise RuntimeError("a service raised where no door did")

    return app


class TestASchemaRefusalAnswersWhereTheProductReads:
    def test_a_bound_the_form_cannot_guard_answers_at_detail_code(self, client: TestClient) -> None:
        """/register: the form only checks the name is not empty, so `min_length=2` is reached from a keystroke."""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "shape-probe@example.test", "password": "strong-pass-1234", "display_name": "X", "accepts_data_policy": True},
        )
        assert response.status_code == 422, response.text
        body = response.json()
        assert "error" not in body, f"a second shape is back, and the only client of this API reads neither: {body}"
        detail = body["detail"]
        assert detail["code"] == "validation_error", detail
        assert detail["message"] == "Request validation failed", detail

    def test_the_field_and_rule_list_is_readable_and_never_echoes_the_value_that_failed_it(self, client: TestClient) -> None:
        marker = "echo-probe-4f9c2a"
        response = client.post(
            "/api/v1/auth/register",
            json={"email": f"{marker}@example.test" + "x" * 400, "password": "123", "display_name": "", "accepts_data_policy": True},
        )
        assert response.status_code == 422, response.text
        detail = response.json()["detail"]
        entries = detail["details"]
        assert isinstance(entries, list) and len(entries) >= 2, entries
        locs = {str(item.get("loc")) for item in entries}
        assert any("email" in loc for loc in locs), locs
        assert any("password" in loc for loc in locs), locs
        assert all(set(item) <= {"type", "loc", "msg"} for item in entries), f"an entry carries a key outside type/loc/msg: {[sorted(item) for item in entries]!r}"
        printed = json.dumps(response.json(), ensure_ascii=False)
        assert marker not in printed, "the answer that names the offending field must not repeat its contents"

    def test_the_code_a_door_spells_and_the_code_a_framework_spells_share_one_address(self, client: TestClient) -> None:
        """A 401 from a door and a 422 from the framework are read by the same line of the same helper."""
        refused = client.post("/api/v1/auth/refresh", json={})
        schema = client.post("/api/v1/auth/register", json={"email": "a" * 3})
        assert refused.status_code == 401 and schema.status_code == 422, f"the unauthenticated call answered {refused.status_code!r} and the schema call {schema.status_code!r}; 401 and 422 were required"
        for response in (refused, schema):
            body = response.json()
            assert sorted(body) == ["detail"], f"{response.status_code} answered outside the one address: {body}"
            assert isinstance(body["detail"]["code"], str) and isinstance(body["detail"]["message"], str), body
            assert "error" not in body["detail"], body


class TestTheInstalledHandlersAnswerLikeTheDoors:
    @pytest.mark.parametrize(
        ("path", "expected_status", "expected_code"),
        [("/conflict", 409, "conflict"), ("/invalid", 422, "validation_error"), ("/boom", 500, "internal_error")],
    )
    def test_each_handler_puts_its_code_under_detail(self, path: str, expected_status: int, expected_code: str) -> None:
        with TestClient(_app_with_handlers(), raise_server_exceptions=False) as test_client:
            response = test_client.get(path)
        assert response.status_code == expected_status, response.text
        body = response.json()
        assert sorted(body) == ["detail"], f"{path} answered outside the one address: {body}"
        assert body["detail"]["code"] == expected_code, body

    def test_the_only_producer_of_a_handler_body_is_the_one_wrapper(self) -> None:
        """Every `JSONResponse` the installer returns is built by `_answer`.

        Checked on the shipped module's own syntax tree, per handler: a new handler that hand-writes a body is
        how a second shape comes back, and the literal census below cannot see a body built by a call.
        """
        path = Path(errors.__file__).resolve()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        installers = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "install_error_handlers"]
        assert len(installers) == 1, "the seam this case polices is the installer the app calls at import"
        responses = [node for node in ast.walk(installers[0]) if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "JSONResponse"]
        wrapped = [node for node in responses if _first_arg_producer(node) == "_answer"]
        assert responses, "the installer returns no JSONResponse — the scan read the wrong module"
        assert len(wrapped) == len(responses), f"{len(responses) - len(wrapped)} handler bodies were not built by `_answer`"

    def test_the_wrapper_that_nests_a_third_way_is_gone(self) -> None:
        """`AppError` had zero raise sites, and would have answered `detail.error`.

        The name census is scoped to `app/` on purpose: a class nobody imports can only be raised from there, and
        this file's own prose names it. The behavioural half is `hasattr` below, which no amount of prose can
        satisfy.
        """
        assert not hasattr(errors, "AppError"), "a dead class is a live invitation to print the third shape"
        users = sorted(
            p.relative_to(_app_root().parent).as_posix()
            for p in _app_root().rglob("*.py")
            if "__pycache__" not in p.parts and "AppError" in p.read_text(encoding="utf-8")
        )
        assert users == [], f"AppError is being raised after all: {users}"


class TestTheCensusPopulationIsReal:
    def test_the_floor_is_counted_by_the_same_walk_that_counts_the_doors(self) -> None:
        """"Nobody else wraps" is worth nothing if the walk saw no answers to check."""
        answers = _http_answer_dicts(_app_root())
        refusals = [row for row in answers if {"code", "message"} <= _keys(row[3])]
        assert len(refusals) >= 50, f"the walk found {len(refusals)} refusal dicts; it measured 72 here and ~101 with constants, so this scan is reading the wrong tree"
        modules = {row[0] for row in refusals}
        assert len(modules) >= 12, f"only {sorted(modules)} answer refusals — the population is not the API"
        from_doors = [row for row in refusals if row[2] == "detail"]
        assert len(from_doors) >= 40, f"{len(from_doors)} of {len(refusals)} came from a door; the doors are the half this file is about"

    def test_no_refusal_answer_puts_its_code_anywhere_but_detail(self) -> None:
        """One address for a code in the shipped literals: no top-level `error`, no `detail.error`, no bare body."""
        offenders = []
        for module, line, kind, node in _http_answer_dicts(_app_root()):
            keys = _keys(node)
            detail_value = next((v for k, v in zip(node.keys, node.values, strict=True) if isinstance(k, ast.Constant) and k.value == "detail"), None)
            nested_error = isinstance(detail_value, ast.Dict) and "error" in _keys(detail_value)
            if "error" in keys:
                offenders.append(f"{module}:{line} wraps its answer under a top-level `error`")
            elif nested_error:
                offenders.append(f"{module}:{line} nests its answer under `detail.error`")
            elif {"code", "message"} <= keys and kind == "body":
                offenders.append(f"{module}:{line} answers a refusal at the top level, with no `detail`")
        assert offenders == [], "a second shape is back: " + "; ".join(offenders)


class TestTheWebReaderIsGatedOnAnswersThisApiProduces:
    """§74's other end: `apps/web/lib/api.ts` is the product's only reader of a refusal, and its fixture file
    is checked here rather than trusted.

    `apps/web/scripts/qa-error-shape.mjs` drives the shipped reader over `fixtures/refusals.json`; this class
    holds that file to the backend's own bytes. Without it the web gate could be green over payloads no door
    and no handler answers, which is the failure mode where a reader test proves the test's own imagination.
    """

    @staticmethod
    def _entries() -> list[dict[str, Any]]:
        file = Path(__file__).resolve().parents[2] / "web" / "fixtures" / "refusals.json"
        assert file.is_file(), f"{file} is where the web reader's fixtures live"
        entries = json.loads(file.read_text(encoding="utf-8"))["entries"]
        assert isinstance(entries, list) and len(entries) >= 8, f"the fixture file carries {entries!r}; a gate needs a real population"
        return entries

    def test_a_handler_fixture_is_what_the_wrapper_answers(self) -> None:
        """For each handler entry, `errors._answer(code, message, details)` reproduces the body byte for byte.

        The three shipped handlers must all be present, so the fixture set cannot quietly shrink to the one
        answer that happens to have a field list.
        """
        entries = [entry for entry in self._entries() if entry["producer"]["kind"] == "handler"]
        assert len(entries) >= 3, f"{len(entries)} handler fixtures; the installer has three answers to represent"
        seen: set[str] = set()
        for entry in entries:
            detail = dict(entry["body"]["json"]["detail"])
            code, message = detail.pop("code"), detail.pop("message")
            assert detail in ({}, {"details": detail.get("details")}), f"{entry['name']}: a handler answers code, message and at most one details key"
            answered = errors._answer(code, message, *([detail["details"]] if detail else []))
            assert answered == entry["body"]["json"], f"{entry['name']} is not what `_answer` returns: {answered}"
            seen.add(code)
        assert {"validation_error", "conflict", "internal_error"} <= seen, sorted(seen)

    def test_a_door_fixture_is_a_literal_the_named_module_raises(self) -> None:
        """Each door entry names its module, and that module must actually answer this code and sentence.

        Checked on the parsed tree, with the key names and (where the source states it as a constant or a
        `status.HTTP_*` name) the status code compared too — a fixture that drifted from the door is a fixture
        the reader gate is no longer testing against the product.
        """
        from fastapi import status as http_status

        app_root = _app_root()
        entries = [entry for entry in self._entries() if entry["producer"]["kind"] == "door"]
        assert len(entries) >= 2, f"{len(entries)} door fixtures; two are the minimum for a census of one"
        for entry in entries:
            module = entry["producer"]["module"]
            path = app_root.parent / module
            assert path.is_file(), f"{entry['name']} cites {module}, which is not in this tree"
            tree = ast.parse(path.read_text(encoding="utf-8"))
            calls = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and (getattr(node.func, "id", "") or getattr(node.func, "attr", "")) == "HTTPException"
                and any(kw.arg == "detail" and isinstance(kw.value, ast.Dict) for kw in node.keywords)
            ]
            matches = []
            for call in calls:
                detail_node = next(kw.value for kw in call.keywords if kw.arg == "detail")
                pairs = {k.value: v for k, v in zip(detail_node.keys, detail_node.values, strict=True) if isinstance(k, ast.Constant)}
                if {"code", "message"} <= set(pairs) and all(isinstance(pairs[key], ast.Constant) for key in ("code", "message")):
                    if (pairs["code"].value, pairs["message"].value) == (entry["producer"]["code"], entry["producer"]["message"]):
                        matches.append((call, detail_node, pairs))
            assert len(matches) >= 1, f"{module} never raises {entry['producer']['code']!r} with that sentence — the fixture drifted from the door"
            call, detail_node, pairs = matches[0]
            assert _keys(detail_node) == set(entry["body"]["json"]["detail"]), f"{entry['name']}'s figures are not the door's: {_keys(detail_node)}"
            status_node = call.args[0] if call.args else None
            resolved: Any = None
            if isinstance(status_node, ast.Constant):
                resolved = status_node.value
            elif isinstance(status_node, ast.Attribute) and getattr(status_node.value, "id", "") == "status":
                resolved = getattr(http_status, status_node.attr, None)
            if resolved is not None:
                assert resolved == entry["status"], f"{module}:{call.lineno} answers {resolved}, the fixture says {entry['status']}"

    def test_the_two_halves_still_point_at_each_other(self) -> None:
        """The reader gate must read this file, and the reader must still unwrap a `detail` key.

        Either half can be rewritten out from under the other: a web gate that stops naming the fixture, or a
        reader that stops looking under `detail`, leaves the API-side cases above green and a user still
        holding a fallback string.
        """
        web = Path(__file__).resolve().parents[2] / "web"
        gate = (web / "scripts" / "qa-error-shape.mjs").read_text(encoding="utf-8")
        reader = (web / "lib" / "api.ts").read_text(encoding="utf-8")
        assert len(gate) > 2000 and len(reader) > 500, f"the gate is {len(gate)!r} chars and the reader {len(reader)!r}; the floors 2000 and 500 both have to hold"
        for needle in ("refusals.json", "browserFetch", "normalizeError"):
            assert needle in gate, f"the web gate no longer names {needle}, so this file is not its fixture"
        assert '"detail" in payload' in reader, "normalizeError no longer unwraps a detail key"
        assert "readError(response)" in reader, "browserFetch no longer sends a refusal answer through the reader"
        tolerant = [entry for entry in self._entries() if entry["producer"]["kind"] == "reader-tolerance"]
        assert len(tolerant) <= 5, f"{len(tolerant)} tolerance entries out of the set — a fixture file of inventions is not a contract"
        assert all(len(str(entry["producer"].get("why", ""))) > 30 for entry in tolerant), f"an entry named a producer of 30 characters or less: {[entry['name'] for entry in tolerant]!r}"
