"""The security probe's report is a ledger, so the contract it names and the population it counts get readers.

Until this file existed, three documents quoted the probe's contract SHA-256 and its door census and **nothing
read either**: `docs/SECURITY_PROBE_REPORT.md` (§1 and C0/S1), the M12 verification record, and the ROADMAP row.
The contract's descriptions changed four times after the first probe run (the trace, metrics, provider and jobs
tiers), which moved its bytes — and with them its SHA-256 — while all three ledgers still named
`31000605…`. The door population happened not to move (212 / 52 / 91), but no reader would have noticed if it had.

The cases below bind each *current* declaration to the committed contract and to the probe's own derivation:

* **A1** the report's §1 SHA is the SHA-256 of the committed `docs/api/openapi.json`;
* **A2/A3** the M12 record and the ROADMAP name that same SHA in their own sentences;
* **B1–B3** the report's census table (secured / public / private `GET`) recomputes from the committed contract
  through `scripts/security_probe.py`'s own `private_operations()` / `public_operations()` — not a retyped predicate;
* **B4** the report's floors are the probe's `MIN_SECURED` / `MIN_PUBLIC` / `MIN_PRIVATE_GET` constants;
* **B5** the M12 record quotes the same census and floors;
* **C1–C3** the S1 rows in the report and the M12 record, and the ROADMAP's secured ratio, knock the whole
  secured population — the run's measured number and the code-level count are the same number;
* **D1** the run table's latest column is a green run (`10 passed / 0 failed / 0 server errors`).

Historical SHA values stay in the documents on purpose: they name what runs A–C were made against. Each case
reads its own sentence, so a historical SHA is not mistaken for the current declaration."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from functools import cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = "docs/api/openapi.json"
PROBE = "scripts/security_probe.py"
REPORT = "docs/SECURITY_PROBE_REPORT.md"
M12 = "docs/M12_PRODUCTION_HARDENING_VERIFICATION.md"
ROADMAP = "ROADMAP.md"

REPORT_SHA = re.compile(r"contract's SHA-256 was\s+`([0-9a-f]{64})`")
M12_SHA = re.compile(r"SHA-256\s+`([0-9a-f]{64})`\s+that population is")
ROADMAP_SHA = re.compile(r"at contract SHA-256 `([0-9a-f]{64})`")
REPORT_CENSUS_ROW = re.compile(
    r"^\| (secured operations|public operations|private `GET` paths) \| (\d+) \| (\d+) \|$", re.MULTILINE
)
M12_CENSUS = re.compile(
    r"that population is \*\*(\d+)\s+secured operations, (\d+) public operations and (\d+) private GET paths\*\*,"
    r" with floors of (\d+)/(\d+)/(\d+)"
)
ROADMAP_SECURED = re.compile(r"\*\*(\d+)/(\d+) secured operations refuse")
REPORT_S1 = re.compile(r"\*\*(\d+) knocked, (\d+) answered 401\*\*")
M12_S1 = re.compile(r"\*\*(\d+) knocked, (\d+) × 401\*\*")
RESULT_ROW = re.compile(r"^\| result \|(.+)$", re.MULTILINE)
RUN_RESULT = re.compile(r"\*\*(\d+) passed / (\d+) failed / (\d+) server errors\*\*")


def _git(args: list[str]) -> bytes:
    done = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, timeout=120)
    assert done.returncode == 0, (
        f"`git {' '.join(args)}` failed rc={done.returncode}: {done.stderr.decode('utf-8', 'replace')[:300]}"
    )
    return done.stdout


@cache
def committed_text(rel: str) -> str:
    if (ROOT / ".git").exists():
        return _git(["show", f"HEAD:{rel}"]).decode("utf-8").replace("\r\n", "\n")
    return (ROOT / rel).read_text(encoding="utf-8").replace("\r\n", "\n")


def contract_sha() -> str:
    if (ROOT / ".git").exists():
        return hashlib.sha256(_git(["show", f"HEAD:{CONTRACT}"])).hexdigest()
    return hashlib.sha256((ROOT / CONTRACT).read_bytes()).hexdigest()


@cache
def probe_module():
    """The probe's committed source, executed in memory, so the gate derives the census the run derived."""
    source = committed_text(PROBE)
    spec = importlib.util.spec_from_loader("security_probe_committed", loader=None)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(ROOT / PROBE)
    sys.modules[spec.name] = module
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


def census() -> tuple[int, int, int]:
    module = probe_module()
    probe = module.Probe.__new__(module.Probe)
    probe.contract = json.loads(committed_text(CONTRACT))
    private = probe.private_operations()
    return (
        len(private),
        len(probe.public_operations()),
        sum(1 for method, _path, _op in private if method == "GET"),
    )


def floors() -> tuple[int, int, int]:
    module = probe_module()
    return module.MIN_SECURED, module.MIN_PUBLIC, module.MIN_PRIVATE_GET


def test_the_probe_report_names_the_contract_sha_of_the_run_it_records() -> None:
    found = REPORT_SHA.findall(committed_text(REPORT))
    assert len(found) == 1, (
        f"`{REPORT}` must name the current contract's SHA-256 exactly once after \"contract's SHA-256 was\"; "
        f"the grammar found {len(found)}. If the sentence was reworded, re-aim this case rather than dropping it."
    )
    assert found[0] == contract_sha(), (
        f"`{REPORT}` records contract SHA-256 `{found[0]}` but the committed `{CONTRACT}` hashes to "
        f"`{contract_sha()}`. Rerun `scripts/security_probe.py` against the committed contract and refresh the report."
    )


def test_the_m12_record_names_the_same_contract_sha() -> None:
    found = M12_SHA.findall(committed_text(M12))
    assert len(found) == 1, f"`{M12}` must name the contract SHA before \"that population is\"; found {len(found)}."
    assert found[0] == contract_sha(), (
        f"`{M12}` names contract SHA-256 `{found[0]}` where the committed contract hashes to `{contract_sha()}`."
    )


def test_the_roadmap_names_the_same_contract_sha() -> None:
    found = ROADMAP_SHA.findall(committed_text(ROADMAP))
    assert len(found) == 1, f"`{ROADMAP}` must name the contract SHA once as \"at contract SHA-256\"; found {len(found)}."
    assert found[0] == contract_sha(), (
        f"`{ROADMAP}` names contract SHA-256 `{found[0]}` where the committed contract hashes to `{contract_sha()}`."
    )


LABELS = {
    "secured operations": 0,
    "public operations": 1,
    "private `GET` paths": 2,
}


@pytest.mark.parametrize("label", sorted(LABELS))
def test_the_probe_report_s_census_recomputes_from_the_committed_contract(label: str) -> None:
    rows = {row[0]: (int(row[1]), int(row[2])) for row in REPORT_CENSUS_ROW.findall(committed_text(REPORT))}
    assert set(rows) == set(LABELS), (
        f"`{REPORT}` census table no longer parses its three rows; found {sorted(rows)}. "
        "A grammar that matches nothing would make every count below vacuously true."
    )
    declared, floor = rows[label]
    measured = census()[LABELS[label]]
    assert declared == measured, (
        f"`{REPORT}` declares {label} = {declared} (floor {floor}) but the committed contract answers {measured} "
        f"through `{PROBE}`'s own census."
    )


def test_the_probe_report_s_floors_are_the_probe_s_constants() -> None:
    rows = {row[0]: int(row[2]) for row in REPORT_CENSUS_ROW.findall(committed_text(REPORT))}
    declared = (rows["secured operations"], rows["public operations"], rows["private `GET` paths"])
    assert declared == floors(), (
        f"`{REPORT}` prints floors {declared} but `{PROBE}` enforces {floors()}; a floor that drifts below the "
        "contract's population lets a half-read contract pass as a clean probe."
    )


def test_the_m12_record_quotes_the_report_s_census_and_floors() -> None:
    found = M12_CENSUS.findall(committed_text(M12))
    assert len(found) == 1, f"`{M12}` must quote the census and floors once; the grammar found {len(found)}."
    secured, public, private_gets, f_secured, f_public, f_private_gets = (int(value) for value in found[0])
    assert (secured, public, private_gets) == census(), (
        f"`{M12}` quotes {secured} / {public} / {private_gets} where the committed contract answers {census()}."
    )
    assert (f_secured, f_public, f_private_gets) == floors(), (
        f"`{M12}` quotes floors {f_secured}/{f_public}/{f_private_gets} where the probe enforces {floors()}."
    )


def test_the_probe_report_s_s1_row_knocks_the_secured_population() -> None:
    found = REPORT_S1.findall(committed_text(REPORT))
    assert len(found) == 1, f"`{REPORT}` must record the S1 knock count once; the grammar found {len(found)}."
    knocked, answered = (int(value) for value in found[0])
    secured = census()[0]
    assert (knocked, answered) == (secured, secured), (
        f"`{REPORT}` records {knocked} knocked / {answered} answered 401 but the committed contract publishes "
        f"{secured} secured operations; the run and the population must be the same number."
    )


def test_the_m12_record_s_s1_row_knocks_the_secured_population() -> None:
    found = M12_S1.findall(committed_text(M12))
    assert len(found) == 1, f"`{M12}` must record the S1 knock count once; the grammar found {len(found)}."
    knocked, answered = (int(value) for value in found[0])
    secured = census()[0]
    assert (knocked, answered) == (secured, secured), (
        f"`{M12}` records {knocked} knocked / {answered} × 401 but the committed contract publishes "
        f"{secured} secured operations."
    )


def test_the_roadmap_quotes_the_secured_population_it_records() -> None:
    found = ROADMAP_SECURED.findall(committed_text(ROADMAP))
    assert len(found) == 1, f"`{ROADMAP}` must record the secured ratio once; the grammar found {len(found)}."
    knocked, answered = (int(value) for value in found[0])
    secured = census()[0]
    assert (knocked, answered) == (secured, secured), (
        f"`{ROADMAP}` records {knocked}/{answered} secured operations where the committed contract publishes "
        f"{secured} made private by a security requirement."
    )


def test_the_latest_recorded_run_is_green() -> None:
    rows = RESULT_ROW.findall(committed_text(REPORT))
    assert len(rows) == 1, f"`{REPORT}` must carry one run-result row; the grammar found {len(rows)}."
    cells = [cell.strip() for cell in rows[0].split("|") if cell.strip()]
    assert cells, f"`{REPORT}`'s run-result row parses to no cells; the table shape changed."
    latest = RUN_RESULT.search(cells[-1])
    assert latest is not None, (
        f"the latest run's result cell is {cells[-1]!r}, which this case cannot read; "
        "A grammar that matches nothing would call every run green."
    )
    passed, failed, server_errors = (int(value) for value in latest.groups())
    assert (passed, failed, server_errors) == (10, 0, 0), (
        f"the latest run in `{REPORT}` reads {passed} passed / {failed} failed / {server_errors} server errors; "
        "a report that records a red run must not be quoted as the clean probe."
    )
