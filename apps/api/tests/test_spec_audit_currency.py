"""§80: the spec-coverage audit is a ledger, so every figure and every cited scan in it gets recomputed.

Two documents carry the project's own coverage claims, and until this file nothing read them:

* `docs/SPEC_COVERAGE_AUDIT.md` maps each spec module to "measured evidence", where *measured* means a `git grep`
  citation with a published file count. Those citations went stale in the loud direction — two rows still said
  "no route, no table, no service" for modules whose doors the committed contract answers.
* `ROADMAP.md` summarizes that audit and quotes its three headline figures, and counts the items the audit leaves
  unowned.

Five claims, one case each, each killed by its own arm (`docs/SPEC_AUDIT_CURRENCY_VERIFICATION.md`):

* **C1** the audit's machine-readable `AUDIT_FIGURES` line equals the committed tree: contract paths come from
  `docs/api/openapi.json`, page routes from committed `apps/web/app/**/page.tsx`, migrations from committed
  `apps/api/migrations/versions/*.py`.
* **C2** the ROADMAP's quoted triple is that same triple — not an older snapshot of it.
* **C3** every `git grep -li … → N file(s)` citation the audit publishes recomputes to N over the committed tree.
  This is the case that turns "measured" from a style into a check. It reads the singular spelling too: a count of
  1 written "→ 1 file" is otherwise a citation no reader ever sees.
* **C4** the audit's §A table covers the section range its own heading declares, exactly once — no spec section
  silently unmapped, none mapped twice.
* **C5** the ROADMAP's "…has a door except <count>" sentence counts the unchecked items in the section it introduces.

Everything is read from the committed tree: with a `.git` present that means `git show HEAD:…` /
`git ls-tree HEAD`, and on an extracted plane (`git archive`, no `.git`) the walk *is* the committed state. One
policy, both planes — never the shared working copy's uncommitted edits.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AUDIT = "docs/SPEC_COVERAGE_AUDIT.md"
MAP = "ROADMAP.md"
CONTRACT = "docs/api/openapi.json"
WEB_APP = "apps/web/app"
MIGRATIONS = "apps/api/migrations/versions"
TABLE_SECTION = "## A."
UNOWNED_SECTION = "## Spec modules no milestone owns"

FIGURES = re.compile(r"AUDIT_FIGURES contract_paths=(\d+) page_routes=(\d+) migrations=(\d+)")
QUOTED = re.compile(r"\((\d+)\s+contract\s+paths,\s*(\d+)\s+page\s+routes,\s*(\d+)\s+migrations\)")
CITED_SCAN = re.compile(r"`git grep -li (\S+) -- ([^`]+)` → (\d+) files?\b")
DECLARED_RANGE = re.compile(r"spec §\d+'s list, §(\d+)[–-]§(\d+)")
EXCEPT_WORD = re.compile(r"has a door\s+except\s+(\w+),")
CARDINALS = {"none": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
SCAN_SKIP = "__pycache__"


def _git(args: list[str]) -> bytes:
    done = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, timeout=120)
    assert done.returncode == 0, f"`git {' '.join(args)}` failed rc={done.returncode}: {done.stderr.decode('utf-8', 'replace')[:300]}"
    return done.stdout


def committed_text(rel: str) -> str:
    if (ROOT / ".git").exists():
        return _git(["show", f"HEAD:{rel}"]).decode("utf-8")
    return (ROOT / rel).read_text(encoding="utf-8")


def committed_paths(directory: str) -> list[str]:
    if (ROOT / ".git").exists():
        listing = _git(["ls-tree", "-r", "--name-only", "HEAD", "--", directory]).decode("utf-8")
        return [line for line in listing.splitlines() if line.strip()]
    base = ROOT / directory
    return sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in base.rglob("*") if p.is_file())


def scan_count(pattern: str, directories: list[str]) -> int:
    rx = re.compile(pattern, re.IGNORECASE)
    hits = set()
    for directory in directories:
        for rel in committed_paths(directory.strip()):
            if SCAN_SKIP in rel:
                continue
            try:
                body = committed_text(rel)
            except (UnicodeDecodeError, OSError):
                continue
            if rx.search(body):
                hits.add(rel)
    return len(hits)


def table_section() -> str:
    doc = committed_text(AUDIT)
    assert TABLE_SECTION in doc, f"`{AUDIT}` has no {TABLE_SECTION!r} section — the table this gate reads moved"
    return doc.split(TABLE_SECTION, 1)[1].split("\n## ", 1)[0]


def module_rows() -> list[list[str]]:
    rows = []
    for line in table_section().splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or set(cells[0]) <= set("-: ") or cells[0] == "§":
            continue
        rows.append(cells)
    assert rows, f"the {TABLE_SECTION} table answered with 0 rows — the scan read nothing, which is not a pass"
    return rows


def unowned_section() -> str:
    doc = committed_text(MAP)
    assert UNOWNED_SECTION in doc, f"`{MAP}` has no {UNOWNED_SECTION!r} section"
    return doc.split(UNOWNED_SECTION, 1)[1].split("\n## ", 1)[0]


def test_the_audit_s_declared_figures_answer_for_the_committed_tree() -> None:
    found = FIGURES.findall(committed_text(AUDIT))
    assert len(found) == 1, f"the audit must publish exactly one AUDIT_FIGURES line, found {len(found)}: {found}"
    paths, routes, migrations = (int(x) for x in found[0])

    contract = json.loads(committed_text(CONTRACT))
    actual_paths = len(contract["paths"])
    assert paths == actual_paths, (
        f"AUDIT_FIGURES says {paths} contract paths; the committed {CONTRACT} lists {actual_paths}"
    )

    actual_routes = len([p for p in committed_paths(WEB_APP) if p.endswith("/page.tsx")])
    assert routes == actual_routes, f"AUDIT_FIGURES says {routes} page routes; {WEB_APP} has {actual_routes} committed page.tsx"

    actual_migrations = len([p for p in committed_paths(MIGRATIONS) if p.endswith(".py")])
    assert migrations == actual_migrations, (
        f"AUDIT_FIGURES says {migrations} migrations; {MIGRATIONS} holds {actual_migrations} committed .py files"
    )


def test_the_roadmap_quotes_the_audit_s_current_figures_not_an_older_snapshot() -> None:
    declared = FIGURES.search(committed_text(AUDIT))
    assert declared is not None, "C1's figure line is gone, so C2 has no reference to compare against"
    quoted = QUOTED.search(committed_text(MAP))
    assert quoted is not None, (
        f"`{MAP}` no longer quotes a (contract paths, page routes, migrations) triple next to the audit link — "
        "the sentence this case exists to keep honest was reworded out of reach"
    )
    want = tuple(int(x) for x in declared.groups())
    got = tuple(int(x) for x in quoted.groups())
    assert got == want, f"{MAP} quotes {got[0]}/{got[1]}/{got[2]} where the audit declares {want[0]}/{want[1]}/{want[2]}"


def test_every_cited_scan_in_the_audit_answers_with_the_count_its_row_publishes() -> None:
    doc = committed_text(AUDIT)
    cites = CITED_SCAN.findall(doc)
    assert cites, "the audit publishes no `git grep -li … → N file(s)` citations — 'measured' has no carrier to check"
    for pattern, dirs, claimed in cites:
        directories = [d.strip() for d in dirs.split(",")]
        found = scan_count(pattern, directories)
        assert found == int(claimed), (
            f"`git grep -li {pattern} -- {dirs}` recomputes to {found} committed files; the row publishes {claimed}"
        )


def test_the_module_table_covers_its_declared_section_range_exactly_once() -> None:
    heading = table_section().splitlines()[0]
    declared = DECLARED_RANGE.search(heading)
    assert declared is not None, (
        f"the audit heading no longer declares a section range ({heading!r}), so the table's coverage has no floor"
    )
    low, high = int(declared.group(1)), int(declared.group(2))
    covered: list[int] = []
    for cells in module_rows():
        numbers = [int(n) for n in re.findall(r"\d+", cells[0])]
        assert numbers, f"a module row declares no section number: {cells[0]!r}"
        if len(numbers) == 2 and numbers[0] < numbers[1] and re.search(r"\d\s*[–-]\s*\d", cells[0]):
            covered.extend(range(numbers[0], numbers[1] + 1))
        else:
            covered.extend(numbers)
    repeats = sorted({n for n in covered if covered.count(n) > 1})
    assert not repeats, f"sections mapped more than once: {repeats}"
    gaps = sorted(set(range(low, high + 1)) - set(covered))
    assert not gaps, f"sections in the declared range §{low}–§{high} that no module row maps: {gaps}"


def test_the_roadmap_sentence_counts_the_items_it_introduces() -> None:
    section = unowned_section()
    unchecked = len(re.findall(r"^- \[ \]", section, re.MULTILINE))
    checked = len(re.findall(r"^- \[[xX]\]", section, re.MULTILINE))
    sentence = re.search(r"Everything in[^\n]*", section)
    assert sentence is not None, "`ROADMAP.md` no longer states how many modules have no door"
    word = EXCEPT_WORD.search(sentence.group(0) + " " + section)
    assert word is not None, f"the sentence {sentence.group(0)!r} does not publish an `except <count>` figure"
    token = word.group(1).strip(",.")
    claimed = int(token) if token.isdigit() else CARDINALS.get(token, -1)
    assert claimed >= 0, f"unrecognized cardinal {token!r} in {sentence.group(0)!r}"
    assert claimed == unchecked, (
        f"the sentence says {claimed} module(s) lack a door; the section lists {unchecked} unchecked and "
        f"{checked} checked item(s)"
    )
