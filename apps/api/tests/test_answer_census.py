"""§51/§60's second census — every refusal code the source tree raises answers from the one table.

The first census (`test_authorization_census.py`) policed 403 and found the ledger saying one thing while
the territory said three. The scan behind it then looked at *every* inline `{"code": …}` raise, and this is
what it measured before this file existed: **69 literals across 18 modules, 48 distinct codes, 47 of them
outside `answers.ANSWERS`** — raised with a status spelled in the raise itself, known to no table. Five more
were reachable only through module constants (`detail=NOT_FOUND`), which is the same debt wearing a name.

The rule §51 states is one code one status assembled from one table. A test that reads `ANSWERS` cannot see
a door that never writes to it, so — exactly like the 403 census — **the population here is read off the
source tree**: every `HTTPException` in `app/` whose status and code are statically resolvable (a literal
or a `status.HTTP_*` name, and a dict literal or a module-level dict constant carrying `"code"`). Each site
must find its code registered and answering the very status it spells. A code missing from the table, or a
table row that disagrees with the raise, turns this file red with the site's own `file:line` in the message.

Sites this scan cannot resolve are counted rather than ignored: a status that comes from `ANSWERS.get(...)`
is the table driving the answer (the pattern `community`/`creator`/`graph`/`portfolio` builders use), while
a `detail=error.to_dict()` with a literal status is a refusal class whose codes are checked by their own
tier's tests. The floors below pin the populations so a scan that quietly stops parsing cannot pass by
finding nothing: the resolved site count and the table's own size only grow.
"""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.services.club.answers import ANSWERS

APP_ROOT = Path(__file__).resolve().parents[1] / "app"

#: Statuses this census can resolve from source, keyed the way `fastapi.status` spells them.
_STATUS_NAMES = {name: int(value) for name, value in vars(status).items() if name.startswith("HTTP_")}


def _dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _resolve_status(node: ast.AST) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return int(node.value)
    if isinstance(node, ast.Attribute):
        # `status.HTTP_404_NOT_FOUND` — the attribute's own name is how `fastapi.status` keys them.
        return _STATUS_NAMES.get(node.attr)
    return None


def _code_from_dict(node: ast.Dict, const_strings: dict[str, str] | None = None) -> str | None:
    for key, value in zip(node.keys, node.values, strict=False):
        if key is not None and _const_str(key) == "code":
            found = _const_str(value)
            if found is not None:
                return found
            #: `{"code": INSUFFICIENT_ROLE}` — the value is a Name bound to a module-level string constant
            #: rather than a literal, and the three 403 builders in `core.security` are all this shape.
            if const_strings and isinstance(value, ast.Name):
                return const_strings.get(value.id)
    return None


class _Census(ast.NodeVisitor):
    """Collects (file:line, code, status) for every statically resolvable refusal raise."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.tree = ast.parse(path.read_text(encoding="utf-8"))
        self.const_dicts: dict[str, ast.Dict] = {}
        #: The sibling of a const dict is a const *string* — `INSUFFICIENT_ROLE: Final = "insufficient_role"`
        #: in `core.security`, which three 403 builders carry into `{"code": INSUFFICIENT_ROLE}`. A visitor
        #: that only resolves `ast.Constant` reads those three dicts as code-less and counts them as debt
        #: the file does not have.
        self.const_strings: dict[str, str] = {}
        for node in self.tree.body:
            #: `NOT_FOUND = {...}` and `NOT_FOUND: Final = {...}` are the same constant wearing different
            #: clothes; a visitor that only reads plain assignments silently misses the annotated half,
            #: which is what every `detail=NOT_FOUND` site in `boards`/`tactics`/`video`/`world` uses.
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.const_dicts[target.id] = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Dict) and isinstance(node.target, ast.Name):
                self.const_dicts[node.target.id] = node.value
            elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.const_strings[target.id] = node.value.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) and isinstance(node.target, ast.Name):
                self.const_strings[node.target.id] = node.value.value
        self.sites: list[tuple[str, int, str, int]] = []
        self.table_driven = 0
        self.unresolved = 0

    def _record(self, call: ast.Call, lineno: int) -> None:
        name = call.func.id if isinstance(call.func, ast.Name) else _dotted(call.func)
        if not name.endswith("HTTPException"):
            return
        raise_status: int | None = None
        for arg in call.args:
            resolved = _resolve_status(arg)
            if resolved is not None:
                raise_status = resolved
                break
        for keyword in call.keywords:
            if keyword.arg == "status_code" and raise_status is None:
                raise_status = _resolve_status(keyword.value)
        code: str | None = None
        detail: ast.AST | None = None
        for keyword in call.keywords:
            if keyword.arg == "detail":
                detail = keyword.value
        if detail is None:
            for arg in call.args[1 if raise_status is not None else 0 :]:
                if isinstance(arg, ast.Dict) or isinstance(arg, ast.Name):
                    detail = arg
                    break
        if isinstance(detail, ast.Dict):
            code = _code_from_dict(detail, self.const_strings)
        elif isinstance(detail, ast.Name):
            const = self.const_dicts.get(detail.id)
            if const is not None:
                code = _code_from_dict(const, self.const_strings)
        if raise_status is None:
            # The status comes from an expression — if it is a table lookup, that is the table driving.
            self.table_driven += 1
            return
        if code is None:
            self.unresolved += 1
            return
        self.sites.append((str(self.path.name), lineno, code, raise_status))

    def visit_Raise(self, node: ast.Raise) -> None:
        if isinstance(node.exc, ast.Call):
            self._record(node.exc, node.lineno)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        if isinstance(node.value, ast.Call):
            self._record(node.value, node.lineno)
        self.generic_visit(node)


def _tree_sites() -> tuple[list[tuple[str, int, str, int]], int, int]:
    sites: list[tuple[str, int, str, int]] = []
    table_driven = 0
    unresolved = 0
    for path in sorted(APP_ROOT.rglob("*.py")):
        census = _Census(path)
        census.visit(census.tree)
        sites.extend(census.sites)
        table_driven += census.table_driven
        unresolved += census.unresolved
    return sites, table_driven, unresolved


def test_every_code_the_tree_raises_is_registered_with_that_status() -> None:
    sites, _table_driven, _unresolved = _tree_sites()
    offenders = [f"{file}:{line} raises {code!r} with {raise_status} but the table says {ANSWERS.get(code)!r}" for file, line, code, raise_status in sites if ANSWERS.get(code) != raise_status]
    assert not offenders, "the tree and the ledger disagree (fix the raise or register the code): " + " | ".join(offenders)


def test_no_raise_site_is_unreadable() -> None:
    """Every raise the tree answers with is either a resolved code+status pair or drives its status from the table.

    The ten sites that lingered in the unresolved bucket (agent_memory x2, agents x2, jobs x5,
    model_router x1) all answered with a bare string or an f-string detail — no code at all — which is
    the shape that let them dodge the first census: a census of *codes* sees nothing at a door that
    prints none. Each now carries §51's coded dict, and the model_router door reads its 403 from
    `answers.ANSWERS` instead of spelling it. Zero is the floor because the next landing's debt will
    be one of these shapes, and this is the case that will name its file:line.
    """

    _sites, _table_driven, unresolved = _tree_sites()
    assert unresolved == 0, f"{unresolved} raise sites answer without a code the census can read"


def test_no_router_keeps_a_local_status_routing_set() -> None:
    """§51's one table, enforced against the way this debt came back.

    `/scout` and `/transfers` did not answer from `ANSWERS` — they each kept a module-level set of the
    codes that deserved 404 (`NOT_FOUND_CODES`, `POOL_NOT_FOUND_CODES`) and spelled the other statuses
    beside the raise. The scan before this landing measured that pattern as *drift already*: the two
    copies named different memberships, so `no_such_listing` answered 404 at `/transfers` and 409 at
    `/scout` for the same word. Registering the codes turns both raises into one lookup, which leaves
    nothing for such a set to be right about — so a router that declares one again is this debt being
    re-spent, and the census refuses the file rather than waiting for the next divergence.
    """

    offenders: list[str] = []
    for path in sorted((APP_ROOT / "api").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
                value = node.value
            if not isinstance(value, ast.Set | ast.SetComp | ast.Dict):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id.endswith("_CODES"):
                    offenders.append(f"{path.name}:{node.lineno} declares {target.id} — status routing belongs to answers.ANSWERS")
    assert not offenders, "a router kept its own status-routing set: " + " | ".join(offenders)


def test_the_census_actually_saw_the_tree() -> None:
    """A scanner that parses nothing would find no disagreement; these floors make that red."""
    sites, table_driven, unresolved = _tree_sites()
    assert len(sites) >= 95, f"only {len(sites)} resolvable raise sites — the walk stopped early"
    assert len(ANSWERS) >= 228, f"the answer table shrank to {len(ANSWERS)} rows"
    # The refusal-class builders (`_ANSWERS.get(error.code, …)`) and the `to_dict()` shapes resolve to
    # neither bucket's assertion above, so each bucket is counted here: a sudden collapse to zero means
    # the extraction changed shape, not that the debt was paid. The scouting and market landing moved
    # twelve raises from the unresolved bucket into this one by asking the table for the status.
    assert table_driven >= 15, f"the table-driven pattern vanished: {table_driven} builders"
    assert unresolved == 0
    assert table_driven + unresolved + len(sites) >= 110


def test_the_table_is_assembled_from_tiers_without_collisions() -> None:
    """`assemble()` raises on a code two tiers claim with different answers; the import above proves it ran."""
    assert ANSWERS["insufficient_role"] == 403
    assert ANSWERS["not_found"] == 404
    assert ANSWERS["unauthenticated"] == 401
    assert ANSWERS["too_large"] == 413
    assert ANSWERS["rate_limited"] == 429
    assert ANSWERS["private_media_not_erased"] == 503


def test_a_registered_refusal_reaches_a_client_as_the_table_publishes() -> None:
    """One door end-to-end: an unauthenticated caller earns the 401 row the census read from the tree."""
    client = TestClient(app)
    response = client.get("/api/v1/community/posts")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthenticated"
