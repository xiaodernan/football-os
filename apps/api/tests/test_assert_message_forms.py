"""#114: an `assert` message has to survive the traceback styles the legs actually use.

Two ways a message loses its verdict were measured on a plane outside this repository, both ways reproduced by a
command in `docs/ASSERT_MESSAGE_VERIFICATION.md`:

* **A message that is not a `str` is printed through a 240-character repr window.** The window keeps the head and the
  tail and replaces the middle with `...` — in *every* traceback style, the repo's default `-q` included. So
  `assert not rows, (name, got, wanted)` is a red case whose answer was thrown away on the way to the terminal.
* **A `str` message that contains a newline is clipped to its first line** by `--tb=line`, and three published leg
  commands use exactly that style (`docs/M8_ACADEMY_VERIFICATION.md:376-377`,
  `docs/M9_COMMUNITY_VERIFICATION.md:112`, `docs/M12_PRODUCTION_HARDENING_VERIFICATION.md:369`). A message that opens
  with a header sentence printed 0 of its 6 verdict tags under `--tb=line` and 6 of 6 under the default — which is
  how a joined message written to be *readable* ended up unreadable in the logs everyone cites.

`-rf` restores neither: the short summary line is derived from the same rendered message and is itself truncated.

So the rule is one clause, not two — **the message operand must be a `str` expression that provably carries no
newline** — and the proof is static, which bounds what this file can promise. A `Name`, an attribute, a subscript or
a call's return type is invisible to a syntax walk, so `UNPROVABLE:*` and `unknown-lines:*` sites are counted and
published, not refused. For f-strings the walk does have one decisive convention: `!r` is the only interpolation
whose result it can prove newline-free (`repr()` escapes `\n` for the strings and containers these sites carry), so
this file's own messages use it, and the per-carrier pins below read it. #114 converted all 40 offender sites to
those two shapes — the last two, in `test_boards.py`, only after the gallery lane's `862079a` landed and freed the
file — so the ledger below is empty and `BAD:*`/`CLIPPED:*` are 0 in the committed tree.

Everything is read from the committed tree: with a `.git` present that means `git show HEAD:…` / `git ls-tree HEAD`,
and on an extracted plane (no `.git`) the walk *is* the committed state. One policy, both planes — never the shared
working copy's uncommitted edits, which belong to a concurrent lane.
"""

from __future__ import annotations

import ast
import subprocess
from collections import Counter
from functools import cache
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[3]
POPULATION = ("apps/api/tests/", "apps/api/app/")
WALK_SKIP = {".git", ".scratch", ".next", ".venv", "node_modules", "__pycache__"}

#: What the walk measures at the commit that lands this file: 69 committed test modules and 145 app modules,
#: 4859 `assert` statements, 1411 of them carrying a message (measured on `git archive` of `862079a` plus this file
#: and the two `test_boards.py` conversions — the walk's own file is inside its population, so these numbers include
#: its own 17 asserts). Floors, not pins: the population grows, and a floor that a narrowing scan trips is the whole
#: point — finding nothing has to be louder than finding something dirty.
MIN_FILES = 214
MIN_ASSERTS = 4859
MIN_MESSAGES = 1411

#: The 15 files #114 converted, and the shape each of them holds now, counted per file at `71d6850` except the
#: `test_boards.py` row, which was measured on the landing plane. Floors, one per (file, shape): a carrier that drops
#: below its own reading had a converted message edited back.
#:
#: These used to be two repo-wide floors (`53` f-strings, `5` joins). The witness battery showed a global floor
#: cannot do this job: this file's own messages are part of the population it walks, so on a plane that contains
#: it the join bucket reads 11 where `71d6850` reads 5, and converting two of the 5 back to a `"\n".join` stays
#: green. A pin that the gate's own text outruns is not a pin, so the claim is per-carrier now.
CONVERTED: tuple[tuple[str, str, int], ...] = (
    ("apps/api/tests/test_answer_census.py", "single-line:binop-add", 2),
    ("apps/api/tests/test_boards.py", "single-line:fstring", 2),
    ("apps/api/tests/test_career.py", "single-line:fstring", 1),
    ("apps/api/tests/test_career_api.py", "single-line:fstring", 2),
    ("apps/api/tests/test_club_academy.py", "single-line:fstring", 3),
    ("apps/api/tests/test_club_academy.py", "single-line:binop-add", 1),
    ("apps/api/tests/test_club_announcements.py", "single-line:fstring", 2),
    ("apps/api/tests/test_club_organizations.py", "single-line:fstring", 16),
    ("apps/api/tests/test_club_sessions.py", "single-line:fstring", 1),
    ("apps/api/tests/test_error_answer_shape.py", "single-line:fstring", 5),
    ("apps/api/tests/test_error_answer_shape.py", "single-line:binop-add", 1),
    ("apps/api/tests/test_knowledge_rag.py", "single-line:fstring", 1),
    ("apps/api/tests/test_portfolio_share.py", "single-line:fstring", 2),
    ("apps/api/tests/test_spec_audit_currency.py", "single-line:fstring", 4),
    ("apps/api/tests/test_spec_audit_currency.py", "single-line:binop-add", 1),
    ("apps/api/tests/test_transfers.py", "single-line:fstring", 1),
    ("apps/api/tests/test_transfers_api.py", "single-line:fstring", 1),
    ("apps/api/tests/test_world.py", "single-line:fstring", 2),
)

#: Forbidden shapes: what the syntax *proves* loses a verdict. `BAD` = provably not a `str`, `CLIPPED` = provably
#: newline-bearing.
FORBIDDEN = ("BAD:", "CLIPPED:")

#: Sites this file refuses to convert but does not pretend are clean: `path`, shape, count, and the proof that
#: makes the exemption someone else's work rather than a silent skip. Keyed by identity — a file and a shape and a
#: count — never by line number, which moves (the gallery lane's commit `862079a` shifted `test_boards.py`'s two
#: sites from 104/156 to 106/158 and this ledger read the same count either way).
#:
#: It is empty, and emptiness is a reading, not a default: `#114` exempted `test_boards.py`'s two
#: `BAD:tuple-literal` sites while a concurrent lane held that file modified, then converted both of them once the
#: lane landed. What keeps the ledger case decisive with no rows is its second clause — a forbidden site in a file
#: the ledger does not name goes red — witnessed by battery arm A1, and its first clause is witnessed the other way
#: by A5, which plants a row naming a site the walk cannot find.
EXEMPTIONS: tuple[tuple[str, str, int, str], ...] = ()

REPR_CONVERSION = 114  # ast.FormattedValue.conversion for `!r`, which is ord("r"); -1 means no conversion

#: Every verdict `classify` can return. The self-test covers all of them, so a branch that no site exercises is
#: still a branch someone reads, and a branch added without a row is caught by the coverage clause.
CLASSIFIABLE = (
    "BAD:tuple-literal", "BAD:list-literal", "BAD:set-literal", "BAD:dict-literal",
    "BAD:list-comprehension", "BAD:set-comprehension", "BAD:dict-comprehension", "BAD:generator",
    "BAD:self-form-name",
    "UNPROVABLE:Name", "UNPROVABLE:Attribute", "UNPROVABLE:Subscript",
    "single-line:constant", "single-line:fstring", "single-line:binop-add", "single-line:call",
    "CLIPPED:constant", "CLIPPED:fstring", "CLIPPED:binop-add", "CLIPPED:call",
    "unknown-lines:constant", "unknown-lines:fstring", "unknown-lines:binop-add", "unknown-lines:call",
)


def _git(args: list[str]) -> bytes:
    done = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, timeout=120)
    assert done.returncode == 0, f"`git {' '.join(args)!r}` failed rc={done.returncode!r}: {done.stderr.decode('utf-8', 'replace')[:300]!r}"
    return done.stdout


@cache
def committed_text(rel: str) -> str:
    if (ROOT / ".git").exists():
        return _git(["show", f"HEAD:{rel}"]).decode("utf-8")
    return (ROOT / rel).read_text(encoding="utf-8")


def committed_paths(directory: str) -> list[str]:
    """Committed `.py` files under `directory`, on either plane, with the scratch planes left out of the walk."""
    if (ROOT / ".git").exists():
        listing = _git(["ls-tree", "-r", "--name-only", "HEAD", "--", directory]).decode("utf-8")
        paths = [line for line in listing.splitlines() if line.strip()]
    else:
        base = ROOT / directory
        paths = sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in base.rglob("*") if p.is_file())
    return [p for p in paths if p.endswith(".py") and not any(part in WALK_SKIP for part in Path(p).parts)]


def has_newline(node: ast.expr) -> bool | None:
    """True/False when the literal parts prove it; None when a hole in the expression could hide a newline."""
    if isinstance(node, ast.Constant):
        return "\n" in node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.JoinedStr):
        answers: list[bool | None] = []
        for part in node.values:
            if isinstance(part, ast.FormattedValue):
                answers.append(False if part.conversion == REPR_CONVERSION else None)
                answers.append(has_newline(part.format_spec) if part.format_spec is not None else False)
            else:
                answers.append(has_newline(part))
        if any(answer is True for answer in answers):
            return True
        return None if any(answer is None for answer in answers) else False
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        answers = [has_newline(node.left), has_newline(node.right)]
        if any(answer is True for answer in answers):
            return True
        return None if any(answer is None for answer in answers) else False
    if isinstance(node, ast.Call):
        # `"SEP".join(...)` — the separator is what the walk can see, and it decides whether the result can span
        # lines by construction. A `str(...)`/`len(...)` message returns None: its type is not a syntax fact.
        if isinstance(node.func, ast.Attribute) and node.func.attr == "join" and isinstance(node.func.value, ast.Constant):
            return "\n" in node.func.value.value if isinstance(node.func.value.value, str) else None
        return None
    return None


NON_STR_COMPREHENSIONS = {"ListComp": "list-comprehension", "SetComp": "set-comprehension", "DictComp": "dict-comprehension"}
# A message operand is one expression, so these are the node types whose runtime type a syntax walk cannot know.
# `Starred` is deliberately absent: `assert ok, *rest` does not parse, so no site can be one.
UNPROVABLE_NODES = {"Name", "Attribute", "Subscript"}
SHAPES = {"Constant": "constant", "JoinedStr": "fstring", "BinOp": "binop-add", "Call": "call"}


def classify(msg: ast.expr, test: ast.expr) -> str:
    """One verdict per message operand: `BAD:*`, `UNPROVABLE:*`, `CLIPPED:*`, `single-line:*` or `unknown-lines:*`."""
    node_name = type(msg).__name__
    if node_name in {"List", "Tuple", "Set", "Dict"}:
        return f"BAD:{node_name.lower()}-literal"
    if node_name == "GeneratorExp":
        return "BAD:generator"
    if node_name in NON_STR_COMPREHENSIONS:
        return f"BAD:{NON_STR_COMPREHENSIONS[node_name]}"
    if node_name == "Name" and isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not) \
            and isinstance(test.operand, ast.Name) and test.operand.id == msg.id:
        # `assert not problems, problems` — the message is the very object that just proved it is non-empty.
        return "BAD:self-form-name"
    if node_name in UNPROVABLE_NODES:
        return f"UNPROVABLE:{node_name}"
    shape = SHAPES.get(node_name, f"other:{node_name}")
    newline = has_newline(msg)
    if newline is True:
        return f"CLIPPED:{shape}"
    return f"single-line:{shape}" if newline is False else f"unknown-lines:{shape}"


class Scan(NamedTuple):
    files: int
    asserts: int
    messages: int
    buckets: Counter[str]
    per_file: dict[str, Counter[str]]  # path -> {verdict: site count}, the reading CONVERTED is pinned against
    forbidden: dict[str, Counter[str]]  # path -> {verdict: site count}
    rows: list[str]  # one line per forbidden site, for the red message


@cache
def scan() -> Scan:
    files = sorted({path for directory in POPULATION for path in committed_paths(directory)})
    buckets: Counter[str] = Counter()
    per_file: dict[str, Counter[str]] = {}
    forbidden: dict[str, Counter[str]] = {}
    rows: list[str] = []
    total = 0
    for path in files:
        try:
            tree = ast.parse(committed_text(path))
        except (SyntaxError, UnicodeDecodeError) as error:
            raise AssertionError(f"{path!r} does not parse for this walk: {error!r}") from error
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assert):
                continue
            total += 1
            if node.msg is None:
                buckets["no-message"] += 1
                per_file.setdefault(path, Counter())["no-message"] += 1
                continue
            verdict = classify(node.msg, node.test)
            buckets[verdict] += 1
            per_file.setdefault(path, Counter())[verdict] += 1
            if verdict.startswith(FORBIDDEN):
                forbidden.setdefault(path, Counter())[verdict] += 1
                rows.append(f"{path}:{node.lineno} {verdict}")
    with_message = total - buckets["no-message"]
    assert with_message > 0 and total > 0, f"the walk over {len(files)!r} committed files found {total!r} assert statements and {with_message!r} messages; a gate reading an empty population proves nothing"
    return Scan(len(files), total, with_message, buckets, per_file, forbidden, rows)


def exempt(path: str, verdict: str) -> bool:
    return any(row[0] == path and row[1] == verdict for row in EXEMPTIONS)


def offending(scan_: Scan, prefix: str) -> list[str]:
    return [row for row in scan_.rows if row.split(" ")[1].startswith(prefix) and not exempt(row.split(":")[0], row.split(" ")[1])]


def test_no_message_operand_is_provably_not_a_string() -> None:
    """A collection or generator message goes through pytest's 240-character repr window in every traceback style."""
    result = scan()
    bad = offending(result, "BAD:")
    counted = sum(count for path, kinds in result.forbidden.items() for verdict, count in kinds.items() if verdict.startswith("BAD:"))
    assert not bad, f"{len(bad)!r} of the {counted!r} provably non-`str` assert messages in the committed tree are not exempted; each one is printed through a 240-character repr window, head and tail only, in every traceback style including `-q`: " + " | ".join(bad)


def test_no_message_carries_a_newline_in_its_own_syntax() -> None:
    """`--tb=line` — the style three published leg commands use — prints only a message's first line."""
    result = scan()
    clipped = offending(result, "CLIPPED:")
    assert not clipped, f"{len(clipped)!r} assert messages carry a newline in their own syntax, so a leg run with `--tb=line` reads only their first line and names none of the verdicts below it: " + " | ".join(clipped)


def ledger_defects(
    rows: tuple[tuple[str, str, int, str], ...],
    forbidden: dict[str, Counter[str]],
    site_rows: list[str],
) -> list[str]:
    """Where a ledger and a walk disagree, in both directions: a row naming no site, a site naming no row."""
    defects: list[str] = []
    for path, verdict, count, _proof in rows:
        found = forbidden.get(path, Counter())[verdict]
        if found != count:
            defects.append(f"{path} {verdict} is ledged at {count!r} but the walk finds {found!r}")
    for path in sorted({row.split(":")[0] for row in site_rows} - {row[0] for row in rows}):
        defects.append(f"{path} holds forbidden sites and no ledger row names it")
    for path, kinds in sorted(forbidden.items()):
        for verdict, found in sorted(kinds.items()):
            ledged = [row[2] for row in rows if row[0] == path and row[1] == verdict]
            if ledged and sum(ledged) != found:
                defects.append(f"{path} {verdict} appears {found!r} times against a ledger total of {sum(ledged)!r}")
    return defects


def test_the_exemption_ledger_names_sites_that_exist() -> None:
    """Every exemption is charged against what the walk actually finds, in both directions."""
    result = scan()
    defects = ledger_defects(EXEMPTIONS, result.forbidden, result.rows)
    assert not defects, "the exemption ledger and the walk disagree, so an exemption is hiding a site or outliving one: " + " | ".join(defects)
    # The ledger is empty, which makes the agreement clause above read nothing. These three calls run it on a
    # one-site plant — agreeing, stale, and unledged — so an empty ledger cannot become a silent one.
    plant = "apps/api/tests/test_the_ledger_plant.py"
    plant_rows = [(plant, "BAD:tuple-literal", 1, "a plant, not a site in the tree")]
    plant_forbidden = {plant: Counter({"BAD:tuple-literal": 1})}
    plant_sites = [f"{plant}:7 BAD:tuple-literal"]
    assert not ledger_defects(plant_rows, plant_forbidden, plant_sites), f"the ledger check refuses a row that matches its own walk, so it cannot be trusted when the real ledger is empty: {ledger_defects(plant_rows, plant_forbidden, plant_sites)!r}"
    stale = ledger_defects(((plant, "BAD:tuple-literal", 2, "a stale plant"),), plant_forbidden, plant_sites)
    assert stale, "the ledger check accepts a row counting 2 sites where its walk finds 1, so a converted exemption would outlive itself green"
    unledged = ledger_defects((), plant_forbidden, plant_sites)
    assert unledged, "the ledger check accepts a forbidden site that no row names, which is the only way an exemption can hide a site silently"


def test_the_walk_reads_the_population_it_claims() -> None:
    """Floors from the same scan the refusals run on, plus the balance that makes the buckets a reading of everything."""
    result = scan()
    assert result.files >= MIN_FILES, f"the walk reads {result.files!r} committed files across {list(POPULATION)!r}, below the {MIN_FILES!r} the census measured — the scan narrowed, so every count below it is a reading of less than the tree"
    assert result.asserts >= MIN_ASSERTS, f"the walk reads {result.asserts!r} assert statements where the census counted {MIN_ASSERTS!r}"
    assert result.messages >= MIN_MESSAGES, f"only {result.messages!r} of them carry a message against the measured floor {MIN_MESSAGES!r}"
    balanced = sum(result.buckets.values())
    assert balanced == result.asserts, f"the buckets sum to {balanced!r} against {result.asserts!r} assert statements — a message operand went unclassified, so the walk is reporting a population it did not read"
    per_file_total = sum(sum(counts.values()) for counts in result.per_file.values())
    assert per_file_total == result.asserts, f"the per-file buckets sum to {per_file_total!r} against the {result.asserts!r} the global buckets hold, so the reading the (file, shape) pins are charged against is not the reading this scan took"


def test_the_converted_carriers_still_hold_their_shape() -> None:
    """Each file #114 converted still carries the shape it was converted to, counted against its own reading."""
    result = scan()
    defects: list[str] = []
    for path, shape, minimum in CONVERTED:
        found = result.per_file.get(path, Counter())[shape]
        if found < minimum:
            defects.append(f"{path} holds {found} {shape} messages where {minimum} were measured at 71d6850")
    assert not defects, f"{len(CONVERTED)!r} (file, shape) pins name the carriers this unit converted; " + " | ".join(defects) + " — a converted message was edited back to a bare interpolation or a newline join, which is the shape that loses its verdict"


def test_the_classifier_judges_every_shape_it_claims_to() -> None:
    """Synthetic sites, one per verdict: the scanner's vocabulary is pinned, so a narrowed scan cannot pass quiet."""

    def verdict(source: str) -> str:
        node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Assert))
        return classify(node.msg, node.test)

    cases = {
        "assert ok, (name, got, wanted)": "BAD:tuple-literal",
        "assert ok, [name, got]": "BAD:list-literal",
        "assert ok, {name, got}": "BAD:set-literal",
        "assert ok, {name: got}": "BAD:dict-literal",
        "assert ok, [row for row in rows]": "BAD:list-comprehension",
        "assert ok, {row for row in rows}": "BAD:set-comprehension",
        "assert ok, {k: v for k, v in rows}": "BAD:dict-comprehension",
        "assert ok, (row for row in rows)": "BAD:generator",
        "assert not problems, problems": "BAD:self-form-name",
        "assert ok, rows": "UNPROVABLE:Name",
        "assert ok, obj.detail": "UNPROVABLE:Attribute",
        "assert ok, rows[0]": "UNPROVABLE:Subscript",
        "assert ok, 'plain prose'": "single-line:constant",
        "assert ok, 'line one\\nline two'": "CLIPPED:constant",
        "assert ok, 42": "unknown-lines:constant",
        "assert ok, f'{name!r} over {want!r}'": "single-line:fstring",
        "assert ok, f'{name} over {want!r}'": "unknown-lines:fstring",
        "assert ok, f'see this:\\n{name!r}'": "CLIPPED:fstring",
        "assert ok, 'prose: ' + ' | '.join(rows)": "single-line:binop-add",
        "assert ok, 'prose: ' + detail": "unknown-lines:binop-add",
        "assert ok, 'prose:\\n' + '\\n'.join(rows)": "CLIPPED:binop-add",
        "assert ok, ' | '.join(rows)": "single-line:call",
        "assert ok, '\\n'.join(rows)": "CLIPPED:call",
        "assert ok, str(rows)": "unknown-lines:call",
        "assert ok, len(rows)": "unknown-lines:call",
    }
    wrong = [f"{source!r} judged {verdict(source)!r}, expected {expected!r}" for source, expected in cases.items() if verdict(source) != expected]
    unexercised = [kind for kind in CLASSIFIABLE if kind not in set(cases.values())]
    unseen = [kind for kind in scan().buckets if kind != "no-message" and kind not in CLASSIFIABLE]
    assert not wrong, "the classifier mislabelled its own examples: " + " | ".join(wrong)
    assert not unexercised, f"{len(CLASSIFIABLE)!r} verdicts are declared and {len(cases)!r} examples cover {len(set(cases.values()))!r} of them; unexercised: " + " | ".join(unexercised)
    assert not unseen, "the committed tree contains message shapes outside the declared vocabulary, so the walk grew a branch no test reads: " + " | ".join(unseen)
