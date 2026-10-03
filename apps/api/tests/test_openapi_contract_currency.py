"""#79 — the committed OpenAPI contract must describe the app that is committed next to it.

`docs/api/openapi.json` is the artifact the spec's §80/§81 gates and every "contract: N paths / M operations" line in
`docs/*_VERIFICATION.md` quote. Until this file existed, **nothing in `apps/api/tests` read it**: the numbers were
re-typed by hand at each export, and the exporter fetched them over HTTP from a *running* service whose default port
(8731) is shared with other processes on this machine. The drift that produced this gate was measured at `3651587`:
the committed contract answered 149 paths / 193 operations while the same commit's own `app.openapi()` answered
160 / 205 — 11 routes shipped without ever entering the contract (`graph` x3, `simulation/aggregates` x3,
`video` x5, `careers/{ident}/ledger`), and 0 routes in the contract that the app does not answer.

Each case below fails on its own clause, so the first red names the shape of the drift rather than just its presence.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "docs" / "api" / "openapi.json"
EXPORTER = ROOT / "scripts" / "export_openapi.py"

VERBS = {"get", "put", "post", "patch", "delete", "head", "options", "trace"}


def committed() -> dict:
    return json.loads(CONTRACT.read_bytes().decode("utf-8"))


def answers() -> dict:
    return app.openapi()


def operations(spec: dict) -> set[tuple[str, str]]:
    return {(path, verb) for path, ops in spec["paths"].items() for verb in ops if verb in VERBS}


def test_the_contract_lists_every_route_the_app_answers_and_no_route_it_does_not() -> None:
    missing = sorted(set(answers()["paths"]) - set(committed()["paths"]))
    extra = sorted(set(committed()["paths"]) - set(answers()["paths"]))
    assert not missing and not extra, (
        f"`docs/api/openapi.json` is stale: {len(missing)} route(s) the app answers but the contract does not list "
        f"{missing[:6]}, {len(extra)} listed but not answered {extra[:6]}. "
        "Regenerate with `python scripts/export_openapi.py`."
    )


def test_the_contract_counts_each_verb_on_each_route_the_way_the_app_answers_it() -> None:
    # A route that gains a second verb on an already-listed path cannot go red in the case above; this one is for it.
    drifted = sorted(operations(committed()) ^ operations(answers()))
    assert not drifted, f"the contract and the app disagree on these (path, verb) pairs: {drifted[:8]}"


def test_the_contract_declares_the_same_component_schemas_the_app_does() -> None:
    def schemas(spec: dict) -> set[str]:
        return set(spec.get("components", {}).get("schemas", {}))

    drifted = sorted(schemas(committed()) ^ schemas(answers()))
    assert not drifted, f"component schema names differ from the app's: {drifted[:8]}"


def test_the_exporter_derives_the_contract_from_the_tree_and_reproduces_the_committed_bytes() -> None:
    """Runs the shipped exporter against a temp path and asks what it wrote.

    No `--base` exists any more, so a restored HTTP scrape would have to find a server answering the same surface;
    what this actually proves is the claim that matters: the bytes on disk are exactly what the tree serialises to.
    """
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "spec.json"
        child = subprocess.run([sys.executable, str(EXPORTER), "--out", str(out)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", cwd=str(ROOT))
        assert child.returncode == 0, f"the exporter exited {child.returncode}: {child.stdout[-300:]}{child.stderr[-300:]}"
        written = out.read_bytes()
    assert b"\r\n" not in written, "the exporter wrote CRLF: the committed contract is LF, so a gate on its bytes " \
                                   "would fail for the host's newline policy rather than for the artifact"
    assert written == CONTRACT.read_bytes(), (
        "`scripts/export_openapi.py` and `docs/api/openapi.json` disagree on the same tree: the committed contract is "
        f"{len(CONTRACT.read_bytes())} bytes, the tree serialises to {len(written)}. Edit the app, never the file."
    )
