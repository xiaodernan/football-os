"""§80: the spec-coverage audit is a ledger, so every figure and every cited scan in it gets recomputed.

Two documents carry the project's own coverage claims, and until this file nothing read them:

* `docs/SPEC_COVERAGE_AUDIT.md` maps each spec module to "measured evidence", where *measured* means a `git grep`
  citation with a published file count. Those citations went stale in the loud direction — two rows still said
  "no route, no table, no service" for modules whose doors the committed contract answers.
* `ROADMAP.md` summarizes that audit and quotes its three headline figures, and counts the items the audit leaves
  unowned.

Nine claims, one case each, each killed by its own arm (`docs/SPEC_AUDIT_CURRENCY_VERIFICATION.md`):

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
* **C6** every repository path the two verdict ledgers cite — the audit's §A table and the ROADMAP's
  "no milestone owns" section — resolves to a committed file or a committed directory. This is the case that retired
  §38's `services/portfolio/pdf.py`: a citation of a file that has never been committed, in a row whose verdict said
  *landed*. Brace groups expand member by member, a token carrying two groups is refused rather than guessed at, and
  the population is derived from the claim (a repo path cited by its segment sequence), not from an exemption table.

* **C7** every census the §A table publishes recomputes: `N paths / M operations under `/api/v1/…`` against the
  committed contract, and a page-family count against committed `apps/web/app/**/page.tsx`. Measured before this case
  existed: five rows printed one bare number beside a route family with no unit at all — seven counts, two of which
  matched neither the path count nor the operation count the contract answers for that prefix — while a sixth row
  published 33 paths where `/api/v1/club*` answers 36 and 5 pages where the family holds 4, and two rows carried a
  whole-contract total that was a past commit's snapshot in present tense.
* **C8** the table publishes no count that has no reader: a `(N doors)` whose unit is unstated, a bare `(N)` after a
  `/api/v1/…` token, and a whole-contract total inside a module row are each refused. Spelled numerals — row 30's
  "Three committed doors" — are outside this grammar and named as such in the record rather than left implied.
* **C9** every `/api/v1/…` route citation in the audit — both its verdict tables, not just §A — names a door the
  committed contract publishes, or a family that holds at least one, or a parameterized path whose *parameter names*
  are the contract's own, or an explicitly negated absence. A token that is the referent of a C7/C8 census is skipped:
  there it is a prefix, and `/api/v1/community` / `/api/v1/creator` are families with no bare door, so resolving a
  census referent as a path would red a token another case already reads. This is the case that retired
  `/api/v1/video/{upload,{id},analyse,file,frames/{i},jobs}` — one brace group mixing door literals with a path
  parameter whose name the contract had already chosen (`{ident}`, `{index}`) — and `/progress/export`, which is
  spelled like a web page and means an API door. A third row's `/trainings/{drills,sessions/{id}/complete}` carries
  both defects at once (no prefix *and* a brace inside a brace), so it sits outside this population until it is
  rewritten into it — the case cannot retire a citation it cannot see, which is why the record names that limit.

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

# C7/C8 — the censuses the §A table publishes. Each accepted shape names its own unit and its own referent; a count
# that names neither is C8's business, because there is nothing to recompute it against. The two floors are the
# counts this scan finds at `8b68b0f`; a drop means the grammar stopped matching the ledger's spelling, not that the
# ledger got honest.
CENSUS_DUAL = re.compile(r"(\d+)\s+paths\s*/\s*(\d+)\s+operations(?:\*\*)?\s+under\s+`(/api/v1/[^`]+)`")
CENSUS_PAGES_BEFORE = re.compile(r"(\d+)\s+`(/[a-z][a-z0-9_*/-]*)`\s+pages")
CENSUS_PAGES_AFTER = re.compile(r"`(/[a-z][a-z0-9_*/-]*)`\s+pages\s+\((\d+)\)")
DOORS_WITHOUT_UNIT = re.compile(r"\(\s*(\d+)\s+doors?\b")
COUNT_AFTER_ROUTE = re.compile(r"`(/api/v1/[^`]+)`\s+\((\d+)\)")
WHOLE_CONTRACT_TOTAL = re.compile(r"contract\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)
MIN_DUAL_CENSUSES = 10
MIN_PAGE_CENSUSES = 3

# C9 — the route citations the audit publishes. These four floors are the counts this scan finds over the ledger as
# §83 lands it (all four malformed citations rewritten into the grammar); a drop means the grammar stopped matching
# the ledger's spelling (or a citation was deleted) rather than the ledger getting shorter, which is exactly when a
# reader is worth having. The label names the unit, not a commit: the corrected ledger is the one this case arrives
# with, so the ref that holds these bytes is this file's own commit.
ROUTE_CITATION = re.compile(r"`(/api/v1/[^`]+)`")
BRACE_INNER = re.compile(r"\{([^{}]*)\}")
PARAMETER = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")
NEGATION = re.compile(r"(?:[Nn]o|never)\s+\*{0,2}`$")
MIN_ROUTE_CITATIONS = 49
MIN_PARAMETER_CITATIONS = 12
MIN_NEGATED_CITATIONS = 1
MIN_CENSUS_REFERENTS_SKIPPED = 10

BACKTICK = re.compile(r"`([^`\n]+)`")
BRACE_GROUP = re.compile(r"\{[^{}]*\}")
# a `.git`-less plane walks the filesystem, and `.scratch` holds planes extracted from git; letting one resolve a
# citation for another would be a false green, so the walk reads the repository's own directories only
WALK_SKIP = {".git", ".scratch", ".next", ".venv", "node_modules", "__pycache__"}


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


def committed_tree() -> set[str]:
    """Every committed path, or — on a `.git`-less plane — every file the extracted tree holds outside the scratch."""
    if (ROOT / ".git").exists():
        listing = _git(["ls-tree", "-r", "--name-only", "HEAD"]).decode("utf-8")
        return {line for line in listing.splitlines() if line.strip()}
    found = set()
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(part in WALK_SKIP for part in rel.split("/")[:-1]):
            continue
        found.add(rel)
    return found


def path_shaped(token: str) -> bool:
    """A repository citation as these two ledgers write it: slash-separated, no prose, rooted inside the repo."""
    if not token or " " in token or ":" in token or "@" in token or token.startswith("/"):
        return False
    if any(bracket in token for bracket in "()[`\"'"):
        return False
    return token.count("/") >= 1


def cited_path_tokens(*sections: str) -> list[str]:
    tokens = []
    for section in sections:
        for line in section.splitlines():
            for raw in BACKTICK.findall(line):
                for piece in re.split(r",\s+", raw):
                    piece = piece.strip().strip("`").rstrip(".,;")
                    if path_shaped(piece):
                        tokens.append(piece)
    return sorted(set(tokens))


def expand_citation(token: str) -> list[str]:
    groups = BRACE_GROUP.findall(token)
    assert len(groups) <= 1, (
        f"the citation `{token}` carries {len(groups)} brace groups — this case refuses to guess which member list "
        "belongs to which segment"
    )
    if not groups:
        return [token]
    first = groups[0]
    head, rest = token.split(first, 1)
    members = []
    for member in first.strip("{}").split(","):
        members.extend(expand_citation(head + member.strip() + rest))
    return members


def resolves(token: str, tree: set[str]) -> bool:
    token = token.rstrip("/")
    if "**" in token:
        prefix = token.split("/**", 1)[0].rstrip("/")
        return any(p.startswith(prefix + "/") for p in tree)
    return any(p == token or p.endswith("/" + token) or f"/{token}/" in f"/{p}" for p in tree)


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


def test_every_repository_path_the_verdict_ledgers_cite_is_committed() -> None:
    tree = committed_tree()
    assert AUDIT in tree, f"the committed-tree walk did not find `{AUDIT}` — the population it is checking against is wrong"
    tokens = cited_path_tokens(table_section(), unowned_section())
    assert tokens, (
        "the audit's §A table and the ROADMAP's unowned-modules section cite no repository path — the scan read "
        "nothing, which is not a pass"
    )
    candidates = sorted({c for token in tokens for c in expand_citation(token)})
    unresolved = [c for c in candidates if not resolves(c, tree)]
    assert not unresolved, (
        f"{len(tokens)} cited path tokens expand to {len(candidates)} candidates; these name nothing in the "
        f"committed tree: {unresolved}"
    )


def contract_census(prefix: str) -> tuple[int, int]:
    paths = json.loads(committed_text(CONTRACT))["paths"]
    chosen = [p for p in paths if p.startswith(prefix.rstrip("*"))]
    return len(chosen), sum(len(paths[p]) for p in chosen)


def page_family_count(family: str) -> int:
    stem = family.strip("/").rstrip("*").rstrip("/")
    routes = [p[len(WEB_APP) + 1:] for p in committed_paths(WEB_APP) if p.endswith("/page.tsx")]
    return len([r for r in routes if r == f"{stem}/page.tsx" or r.startswith(f"{stem}/")])


def published_censuses() -> tuple[list[tuple[int, int, str]], list[tuple[int, str]]]:
    section = table_section()
    duals = [(int(paths), int(ops), prefix) for paths, ops, prefix in CENSUS_DUAL.findall(section)]
    pages = [(int(count), family) for count, family in CENSUS_PAGES_BEFORE.findall(section)]
    pages += [(int(count), family) for family, count in CENSUS_PAGES_AFTER.findall(section)]
    return duals, pages


def test_every_door_and_page_census_in_the_module_table_recomputes() -> None:
    duals, pages = published_censuses()
    assert len(duals) >= MIN_DUAL_CENSUSES, (
        f"the §A table yields {len(duals)} 'N paths / M operations under a /api/v1 prefix' censuses where `8b68b0f` "
        f"yields {MIN_DUAL_CENSUSES} — the grammar stopped matching the ledger's spelling, so this case read less "
        "than the ledger published"
    )
    for paths_claimed, operations_claimed, prefix in duals:
        got = contract_census(prefix)
        assert got == (paths_claimed, operations_claimed), (
            f"`{prefix}` is published as {paths_claimed} paths / {operations_claimed} operations; the committed "
            f"{CONTRACT} answers {got[0]} paths / {got[1]} operations under that prefix"
        )
    assert len(pages) >= MIN_PAGE_CENSUSES, (
        f"the §A table yields {len(pages)} page-family censuses where `8b68b0f` yields {MIN_PAGE_CENSUSES} — the "
        "grammar read less than the ledger published"
    )
    for count, family in pages:
        got = page_family_count(family)
        assert got == count, (
            f"the table says {count} '{family}' pages; committed {WEB_APP} holds {got} page.tsx under that family"
        )


def test_the_module_table_publishes_no_count_that_has_no_reader() -> None:
    section = table_section()
    for rx, why in (
        (DOORS_WITHOUT_UNIT,
         "a '(N doors)' count: this ledger has used 'door' for one path in one row and for one operation in another, "
         "so the number cannot be checked until the row says which"),
        (COUNT_AFTER_ROUTE,
         "a bare '(N)' after a /api/v1 route token, which names neither paths nor operations and so answers to "
         "neither count the contract publishes"),
        (WHOLE_CONTRACT_TOTAL,
         "a whole-contract total inside a module row: the current triple is the AUDIT_FIGURES line, which C1 "
         "recomputes, and a per-row total is a snapshot of a past commit no reader here can recompute"),
    ):
        found = rx.findall(section)
        assert not found, f"the §A table still publishes {found} — {why}"


def census_referent_spans(doc: str) -> list[tuple[int, int]]:
    """Spans C7/C8 already recompute. Inside one of them a `/api/v1/…` token is a *prefix*, not a door."""
    spans: list[tuple[int, int]] = []
    for rx in (CENSUS_DUAL, CENSUS_PAGES_BEFORE, CENSUS_PAGES_AFTER):
        spans += [m.span() for m in rx.finditer(doc)]
    return spans


def route_shape(candidate: str) -> re.Pattern[str]:
    parts = re.split(r"(\{[A-Za-z_][A-Za-z0-9_]*\}|\*)", candidate)
    out = []
    for part in parts:
        if PARAMETER.fullmatch(part):
            out.append("[^/]+")
        elif part == "*":
            out.append(".*")
        else:
            out.append(re.escape(part))
    return re.compile("^" + "".join(out) + "$")


def cite_refusal(token: str) -> str | None:
    """Why this citation is not a citation at all — reported as a defect, never raised, because a case that stops at
    the first malformed token leaves the other malformed tokens published and unread."""
    groups = BRACE_INNER.findall(token)
    if token.count("{") != len(groups):
        return (f"CONFLATED `{token}` carries a brace inside a brace: it mixes a path parameter with the door "
                "literals beside it, so no reader can tell which segment each member lives under")
    commas = [g for g in groups if "," in g]
    if len(commas) > 1:
        return (f"MULTIPLE-ENUMERATIONS `{token}` carries {len(commas)} comma-bearing groups; this case refuses to "
                "guess which segment each list belongs to")
    if commas and any("{" in member for member in commas[0].split(",")):
        return f"CONFLATED `{token}` enumerates a path parameter alongside door literals"
    return None


def cite_candidates(token: str) -> list[str]:
    groups = BRACE_INNER.findall(token)
    commas = [g for g in groups if "," in g]
    if not commas:
        return [token]
    head, tail = token.split("{" + commas[0] + "}", 1)
    return [f"{head}{member.strip()}{tail}" for member in commas[0].split(",")]


def test_every_api_route_citation_in_the_verdict_ledger_resolves() -> None:
    doc = committed_text(AUDIT)
    doors = json.loads(committed_text(CONTRACT))["paths"]
    spans = census_referent_spans(doc)
    assert spans, f"no census phrase was found in `{AUDIT}` — C9 excluded nothing, so it read nothing"

    resolved: list[str] = []
    parameterized: list[str] = []
    negated: list[str] = []
    defects: list[str] = []
    skipped = 0
    for match in ROUTE_CITATION.finditer(doc):
        if any(start <= match.start() < end for start, end in spans):
            skipped += 1
            continue
        token = match.group(1)
        refused = cite_refusal(token)
        if refused is not None:
            defects.append(refused)
            continue
        is_absence = bool(NEGATION.search(doc[max(0, match.start() - 30):match.start() + 1]))
        for candidate in cite_candidates(token):
            if is_absence:
                # "No `/api/v1/community`" is false while eight doors live under that prefix, whether or not the
                # family has a bare collection door — an absence claim is about the family, not about one path
                stem = candidate.rstrip("*").rstrip("/")
                hits = sorted(p for p in doors if p == stem or p.startswith(stem + "/"))
                negated.append(candidate)
                if hits:
                    defects.append(f"CLAIMED-ABSENT `{candidate}` is cited as not existing but the contract "
                                   f"publishes {len(hits)} door(s) under it: {hits[:4]}")
                continue
            if candidate.endswith("*"):
                hits = sorted(p for p in doors if p.startswith(candidate[:-1]))
            elif PARAMETER.search(candidate):
                hits = sorted(p for p in doors if route_shape(candidate).match(p))
            else:
                hits = [candidate] if candidate in doors else []
            if not hits:
                defects.append(f"NO-SUCH-DOOR `{candidate}` (from `{token}`) is cited as landed; the committed "
                               f"{CONTRACT} publishes nothing at or under it")
                continue
            if PARAMETER.search(candidate):
                cited = PARAMETER.findall(candidate)
                spellings = {tuple(PARAMETER.findall(h)) for h in hits}
                if spellings != {tuple(cited)}:
                    defects.append(f"PARAMETER-NAME `{candidate}` names {cited} where the contract spells that door "
                                   f"{sorted(spellings)}")
                    continue
                parameterized.append(candidate)
            resolved.append(candidate)

    assert not defects, (
        f"{len(resolved)} of the ledger's route citations resolve; these name a door the committed contract does not "
        f"answer for:\n  " + "\n  ".join(defects)
    )
    assert len(resolved) >= MIN_ROUTE_CITATIONS, (
        f"the audit yields {len(resolved)} resolvable route citations where `§83` yields {MIN_ROUTE_CITATIONS} — "
        "either a citation was deleted or the grammar stopped matching the ledger's spelling; both mean this case "
        "read less than the ledger published"
    )
    assert len(parameterized) >= MIN_PARAMETER_CITATIONS, (
        f"the audit yields {len(parameterized)} parameterized citations where `§83` yields "
        f"{MIN_PARAMETER_CITATIONS}; without one the parameter-name clause above has nothing to check"
    )
    assert len(negated) >= MIN_NEGATED_CITATIONS, (
        f"the audit yields {len(negated)} citations the prose introduces as absent "
        f"(floor {MIN_NEGATED_CITATIONS}); the absence clause would be measuring an empty set"
    )
    assert skipped >= MIN_CENSUS_REFERENTS_SKIPPED, (
        f"C9 skipped {skipped} census-referent tokens where `§83` skips {MIN_CENSUS_REFERENTS_SKIPPED} — the "
        "exclusion moved, so either a census left the grammar or a family prefix is now being read as a door"
    )

