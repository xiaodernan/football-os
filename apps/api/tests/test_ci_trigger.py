"""The CI workflow names a branch that does not exist, so every gate it carries has never run.

`.github/workflows/ci.yml` was written at c9e48cb with `on.push.branches: [main]`. This repository has one
branch, `master` (`origin/HEAD -> origin/master`), and GitHub has recorded **zero** runs of the workflow:
`gh api repos/…/actions/runs --jq .total_count` answers `0`. So the shared lint target, `mypy`, the SQLite and
PostgreSQL suites, the RAG gates and the twelve web gates in that file were documents, not gates — a green tree
was never read by any of them. The same window is the one in which the lint target went red at HEAD (`B007` in
`tests/test_locale_claims.py`, introduced by 525fe4d): nothing was watching it.

This gate asks the workflow's own trigger of the branch the run is actually about — `GITHUB_REF_NAME` on a push
event, `GITHUB_BASE_REF` on a pull request, `git rev-parse --abbrev-ref HEAD` locally — so it refuses a trigger
that names a branch no push carries. It also runs `scripts/lint.sh`, the same file CI and `scripts/check.sh`
call, so a lint red fails `pytest` on the machine that wrote it rather than on a workflow run that never happens;
and it stubs the script's `python` to record the arguments ruff is handed, so the population the target
*announces* and the population it *checks* are the same set, derived here from `git ls-files`.

**The local read is a fallback, not an assertion.** It used to refuse the literal `HEAD` that
`rev-parse --abbrev-ref HEAD` answers on a detached checkout, which reddened this case on every `git worktree`
plane a landing of this project is graded on: at `21bbf86` the whole API suite answered 1 failed / 2148 passed /
4 skipped and the one failure was here (`.scratch/item40-suite.log`). That suite had only reached rc=0 earlier
because the command carried `GITHUB_EVENT_NAME=push GITHUB_REF_NAME=master` — a verdict recorded without naming
the prefix is evidence about the invocation, not about the commit. So the branch now comes from the event when
there is one, from the checkout when it is on a branch, and otherwise from `git for-each-ref --contains HEAD`: the
commit's own history, which is what a push would carry. When no branch carries it the case skips, naming the refs
it did find, and both sides of that resolver are asserted on a throwaway repository — a skip that cannot fail is a
gate that cannot work.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.test_dr_scripts import _bash

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github" / "workflows"
CI = WORKFLOWS / "ci.yml"
LINT = ROOT / "scripts" / "lint.sh"
API = ROOT / "apps" / "api"

#: The step name CI gives its one lint invocation. The step must run the shared target from the repository
#: root: the job's own working directory is `apps/api`, where `scripts/lint.sh` does not exist.
LINT_STEP = "Lint"
SHARED_TARGET = "bash scripts/lint.sh"

#: A `python` that records its argv and succeeds, so the script's own invocation can be read without running
#: ruff. It is placed ahead of the interpreter on `PATH` for one child process only.
PYTHON_STUB = """#!/usr/bin/env bash
printf '%s\\n' "$*" >>"${STUB_ARGV:?}"
exit 0
"""


def _loaded(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path} is not a YAML mapping: {loaded!r}"
    return loaded


def _triggers(path: Path) -> dict[str, Any]:
    """The workflow's `on:` mapping.

    YAML 1.1 reads a bare `on` key as the boolean `True`, so the key is looked up under both spellings rather
    than assuming the parser agrees with GitHub's reader about a word this file cannot avoid using.
    """
    loaded = _loaded(path)
    trigger = loaded.get("on", loaded.get(True))
    if trigger is None:
        return {}
    if isinstance(trigger, str):
        return {trigger: None}
    if isinstance(trigger, list):
        return {str(name): None for name in trigger}
    assert isinstance(trigger, dict), f"{path}'s `on:` is not a mapping: {trigger!r}"
    return trigger


def _push_patterns(path: Path) -> list[str] | None:
    """The branch patterns a `push` triggers this workflow on: `None` means every branch, `[]` means none."""
    triggers = _triggers(path)
    if "push" not in triggers:
        return []
    config = triggers["push"]
    if not isinstance(config, dict) or "branches" not in config:
        return None
    branches = config["branches"]
    if isinstance(branches, str):
        return [branches]
    assert isinstance(branches, list), f"{path}'s push.branches is not a list: {branches!r}"
    return [str(branch) for branch in branches]


def _covers(patterns: list[str] | None, branch: str) -> bool:
    return patterns is None or any(fnmatch.fnmatchcase(branch, pattern) for pattern in patterns)


def _git_text(root: Path, *args: str) -> str:
    """One read-only `git` call against a repository, with its stdout as text."""
    done = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert done.returncode == 0, f"`git {' '.join(args)}` failed in {root}: {done.stderr.strip()[:200]}"
    return done.stdout


def _git_lines(root: Path, *args: str) -> list[str]:
    return [line.strip() for line in _git_text(root, *args).splitlines() if line.strip()]


@contextmanager
def _without_github_env():
    """Suspend the runner's `GITHUB_*` plumbing for the graded calls.

    The fallback under test answers from the *local checkout* when no push event names a branch; in CI a
    `push` event is exactly what names one (`GITHUB_REF_NAME=master`), and leaving it in place grades the
    runner's environment instead of the throwaway repository — the honest form of the gate is one that
    measures the fallback wherever the suite runs.
    """
    saved = {key: value for key, value in os.environ.items() if key.startswith("GITHUB_")}
    for key in saved:
        del os.environ[key]
    try:
        yield
    finally:
        os.environ.update(saved)


def _branches_carrying_head(root: Path) -> list[str]:
    """Every local branch whose history contains the checked-out commit."""
    return _git_lines(root, "for-each-ref", "--contains", "HEAD", "--format=%(refname:short)", "refs/heads/")


def _published_branch(root: Path) -> str:
    """The branch this project's work is pushed to, or `""` when the checkout cannot say.

    `origin/HEAD` is the remote's own statement of its default branch, and it is the fact the defect this gate was
    written for was found by reading (`origin/HEAD -> origin/master`, while the workflow triggered on `main`). A
    checkout with no remote — a `git archive` plane, a fresh single-branch clone — answers from the branches it
    holds: `master`, then `main`, then the one branch when there is exactly one.
    """
    symbolic = subprocess.run(
        ["git", "-C", str(root), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    name = symbolic.stdout.strip()
    if symbolic.returncode == 0 and name:
        return name.removeprefix("origin/")
    branches = _git_lines(root, "for-each-ref", "--format=%(refname:short)", "refs/heads/")
    for candidate in ("master", "main"):
        if candidate in branches:
            return candidate
    return branches[0] if len(branches) == 1 else ""


def _pushed_branches(root: Path) -> list[str]:
    """The branch or branches a push of this run's work could carry — empty when none can be named.

    The local fallback is what makes this gate usable on the planes landings are graded on. Every landing of this
    project runs its suite on a detached `git worktree`, where `rev-parse --abbrev-ref HEAD` answers the literal
    `HEAD`; asserting on that reddens the instrument instead of the tree, and the suite only goes green on such a
    plane when the command is handed a `GITHUB_REF_NAME` the machine does not have — which turns a recorded
    verdict into evidence about the invocation rather than the commit. So the fallback asks git which branch
    *carries* the commit, and a run that has no answer says so as a skip that names the refs it did find.
    """
    event = os.environ.get("GITHUB_EVENT_NAME")
    if event and event.startswith("pull_request"):
        base = os.environ.get("GITHUB_BASE_REF")
        assert base, "a pull_request event reached this suite without GITHUB_BASE_REF, so no push branch can be asked"
        return [base]
    if event and event.startswith("push"):
        ref = os.environ.get("GITHUB_REF_NAME")
        assert ref, "a push event reached this suite without GITHUB_REF_NAME, so no push branch can be asked"
        return [ref]
    checked_out = _git_text(root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if checked_out and checked_out != "HEAD":
        return [checked_out]
    published = _published_branch(root)
    return [published] if published and published in _branches_carrying_head(root) else []


def _tracked_outside_api() -> list[str]:
    """Every tracked `.py` outside `apps/api`, from the same `git ls-files` the target reads."""
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--", "*.py"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8", "replace")
    return sorted(name for name in tracked.split("\0") if name and not name.startswith("apps/api/"))


def _native(path: str) -> str:
    """One spelling for a directory, whichever shell wrote it.

    The target runs under bash, which writes the repository root as `/d/足球项目` here and as `/home/runner/…`
    in CI. A native path is used as-is; a Windows drive written the way bash writes it — `/d/…` — is translated
    before `Path` would read it as `D:\\d\\…`.
    """
    if os.name == "nt":
        match = re.fullmatch(r"/([A-Za-z])/(.*)", path)
        if match:
            path = f"{match.group(1).upper()}:/{match.group(2)}"
    return os.path.normcase(str(Path(path).resolve()))


def _lint_environment(path_entries: list[Path]) -> dict[str, str]:
    environment = dict(os.environ)
    inherited = environment.get("PATH", "")
    prefix = [str(entry) for entry in path_entries]
    prefix.append(str(Path(sys.executable).parent))
    target = prefix
    # The target's first command is `dirname`, and on Windows the utilities beside the Git-bash binary are not
    # on the inherited PATH (`Git/cmd` holds `git`, `Git/usr/bin` holds `dirname`). Without them the script dies
    # at line 20 with `dirname: command not found`, and the stub's own `#!/usr/bin/env bash` interpreter would
    # resolve to this host's WSL relay instead of Git-bash — so when the shell's directory is NOT already on the
    # inherited PATH it goes ahead of it, right behind the interpreter. On Linux the inherited PATH already
    # answers both (`/bin`, `/usr/bin`), so nothing is added and the toolchain python wins.
    shell_dir = str(Path(_bash()).parent)
    parts = [part for part in inherited.split(os.pathsep) if part]

    def norm(value: str) -> str:
        return os.path.normcase(os.path.normpath(value))

    already = any(norm(part) == norm(shell_dir) for part in parts)
    if not already:
        target.append(shell_dir)
    target.append(inherited)
    environment["PATH"] = os.pathsep.join(part for part in target if part)
    return environment


def test_every_workflow_that_runs_on_push_covers_the_branch_the_run_is_about() -> None:
    branches = _pushed_branches(ROOT)
    workflows = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    assert workflows, f"{WORKFLOWS} holds no workflow file, so this gate would pass over nothing"
    if not branches:
        pytest.skip(
            f"this checkout is detached at a commit that the branch this project pushes "
            f"({_published_branch(ROOT)!r}) does not carry — `git for-each-ref --contains HEAD` answers "
            f"{_branches_carrying_head(ROOT)!r} — so no push event would ever name a branch for this run. "
            "The skip is loud in the tally; the alternative was to redden every plane a landing is graded on."
        )
    for branch in branches:
        for path in workflows:
            if "push" not in _triggers(path):
                continue
            patterns = _push_patterns(path)
            assert _covers(patterns, branch), (
                f"{path.name} runs on push to {patterns!r}, but this run is about {branch!r}: no push would ever "
                f"reach it, so every job in it is unexecuted automation"
            )


def test_the_branch_fallback_answers_on_a_detached_checkout_and_names_why_when_it_cannot() -> None:
    """The fallback is graded on a repository this run builds, not on the one it happens to be standing in.

    A `pytest.skip` is one character of a tally line away from a silent gate, so the two sides of the resolver are
    asserted here over a throwaway repository: a detached checkout at a commit the published branch carries answers
    that branch — the shape every landing plane is — and a detached checkout at a commit only a side branch carries
    answers nothing, which is what makes the skip above a statement about the commit rather than about git.
    """
    with _without_github_env(), tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        # The probe's repository must not inherit this host's signing or hook path: a global `commit.gpgsign`
        # or a `core.hooksPath` that needs a service would fail a commit with nothing to do with what is graded.
        isolate = ["-c", "commit.gpgsign=false", "-c", f"core.hooksPath={repo / 'no-hooks'}"]
        _git_text(repo, "init", "--quiet", "-b", "master")
        _git_text(repo, "config", "user.name", "fallback probe")
        _git_text(repo, "config", "user.email", "fallback@example.invalid")
        (repo / "f").write_text("one\n", encoding="utf-8")
        _git_text(repo, "add", "f")
        _git_text(repo, *isolate, "commit", "--quiet", "-m", "one")
        assert _pushed_branches(repo) == ["master"], "a checkout on a branch must answer that branch"
        _git_text(repo, "checkout", "--quiet", "--detach")
        assert _pushed_branches(repo) == ["master"], (
            "a detached checkout at a commit master carries must answer master: this is the shape of every "
            "landing plane, and an empty answer here is the gate going silent"
        )
        _git_text(repo, "checkout", "--quiet", "-b", "side")
        (repo / "g").write_text("two\n", encoding="utf-8")
        _git_text(repo, "add", "g")
        _git_text(repo, *isolate, "commit", "--quiet", "-m", "two")
        assert _branches_carrying_head(repo) == ["side"], _branches_carrying_head(repo)
        assert _pushed_branches(repo) == ["side"], (
            "a checkout that is on `side` answers `side`, detached history or not: the checked-out branch is "
            "the run's own answer and the fallback never overrules it"
        )
        _git_text(repo, "checkout", "--quiet", "--detach")
        assert _pushed_branches(repo) == [], (
            "detached at a commit the published branch does not carry has no push branch, and answering one "
            "would grade a workflow trigger against a branch that would never carry this work"
        )


def test_the_ci_workflow_still_runs_on_pull_requests() -> None:
    triggers = _triggers(CI)
    assert "pull_request" in triggers, (
        f"{CI.name} answers {sorted(triggers)!r}: a pull request would not run the project's gates"
    )


def test_the_ci_lint_step_runs_the_one_shared_target_from_the_repository_root() -> None:
    jobs = _loaded(CI).get("jobs")
    assert isinstance(jobs, dict), f"{CI.name} declares no jobs"
    steps = [step for job in jobs.values() for step in (job or {}).get("steps") or []]
    lint = [step for step in steps if step.get("name") == LINT_STEP]
    assert len(lint) == 1, f"{CI.name} names {len(lint)} steps {LINT_STEP!r}; the project has one lint target"
    step = lint[0]
    assert step.get("run", "").strip() == SHARED_TARGET, (
        f"{CI.name}'s {LINT_STEP} step runs {step.get('run')!r}, not the shared target {SHARED_TARGET!r}"
    )
    assert step.get("working-directory") == "${{ github.workspace }}", (
        f"{CI.name}'s {LINT_STEP} step runs in {step.get('working-directory')!r}, where {SHARED_TARGET} does not exist"
    )


def test_ci_names_no_second_lint_target() -> None:
    jobs = _loaded(CI).get("jobs")
    assert isinstance(jobs, dict), f"{CI.name} declares no jobs"
    for job_name, job in jobs.items():
        for step in (job or {}).get("steps") or []:
            run = step.get("run") or ""
            assert "ruff check" not in run, (
                f"{CI.name}'s {job_name!r} job runs {run!r}: a second lint target is how the local gate and CI "
                f"drifted apart before, and only the shared one is exercised here"
            )


def test_the_matcher_can_refuse_a_branch() -> None:
    assert not _covers(["main"], "master"), "the matcher called `main` a cover for `master`"
    assert _covers(["master"], "master")
    assert _covers(["mas*"], "master")
    assert _covers(None, "anything"), "a trigger without `branches` runs on every branch"
    assert not _covers([], "master"), "a workflow without a push trigger runs on no push"


def test_the_shared_lint_target_is_green_on_the_population_it_derives() -> None:
    outside = _tracked_outside_api()
    result = subprocess.run(
        [_bash(), str(LINT)],
        cwd=ROOT,
        env=_lint_environment([]),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    assert result.returncode == 0, (
        f"the shared lint target exited {result.returncode} on this tree, so a push would be red: {result.stdout!r} {result.stderr!r}"
    )
    lines = result.stdout.splitlines()
    assert lines, "the shared lint target printed nothing"
    assert lines[0].startswith("lint target: apps/api (whole tree)"), (
        f"the shared lint target printed {lines[0]!r} instead of naming the whole of apps/api"
    )
    printed = sorted(line.strip() for line in lines[1:] if line.startswith("  "))
    assert printed == outside, (
        "the shared lint target printed a population that is not every tracked .py outside apps/api: "
        f"missing {sorted(set(outside) - set(printed))!r}, extra {sorted(set(printed) - set(outside))!r}"
    )


def test_the_shared_lint_target_hands_ruff_exactly_the_population_it_announces(
    tmp_path: Path,
) -> None:
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    stub = stub_dir / "python"
    stub.write_text(PYTHON_STUB, encoding="utf-8", newline="\n")
    stub.chmod(0o755)
    record = tmp_path / "argv.txt"

    environment = _lint_environment([stub_dir])
    environment["STUB_ARGV"] = str(record)
    result = subprocess.run(
        [_bash(), str(LINT)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    assert result.returncode == 0, (
        f"the shared lint target exited {result.returncode} under a stub: {result.stderr!r}"
    )
    assert record.exists(), "the shared lint target never invoked python, so it cannot have linted anything"
    argv = record.read_text(encoding="utf-8").split()
    assert argv[:3] == ["-m", "ruff", "check"], f"the shared target invoked python with {argv[:3]!r}, not ruff check"
    targets = {_native(target) for target in argv[3:]}
    expected = {_native(str(API))} | {_native(str(ROOT / str(Path(name).parent))) for name in _tracked_outside_api()}
    assert targets == expected, (
        "the shared lint target handed ruff a different population than `git ls-files` derives: "
        f"missing {sorted(expected - targets)!r}, extra {sorted(targets - expected)!r}"
    )
