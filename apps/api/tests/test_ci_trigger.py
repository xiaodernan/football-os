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
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

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


def _pushed_branch() -> str:
    """The branch a push in this run would carry, or the branch a pull request here targets."""
    event = os.environ.get("GITHUB_EVENT_NAME")
    if event and event.startswith("pull_request"):
        base = os.environ.get("GITHUB_BASE_REF")
        assert base, "a pull_request event reached this suite without GITHUB_BASE_REF, so no push branch can be asked"
        return base
    if event and event.startswith("push"):
        ref = os.environ.get("GITHUB_REF_NAME")
        assert ref, "a push event reached this suite without GITHUB_REF_NAME, so no push branch can be asked"
        return ref
    result = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, f"cannot read the checked-out branch: {result.stderr}"
    branch = result.stdout.strip()
    assert branch and branch != "HEAD", (
        f"this checkout is on no branch ({branch!r}), so the workflow's push trigger cannot be asked of it"
    )
    return branch


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
    prefix = [str(entry) for entry in path_entries]
    prefix.append(str(Path(sys.executable).parent))
    environment["PATH"] = os.pathsep.join(prefix + [environment.get("PATH", "")])
    return environment


def test_every_workflow_that_runs_on_push_covers_the_branch_the_run_is_about() -> None:
    branch = _pushed_branch()
    workflows = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    assert workflows, f"{WORKFLOWS} holds no workflow file, so this gate would pass over nothing"
    for path in workflows:
        if "push" not in _triggers(path):
            continue
        patterns = _push_patterns(path)
        assert _covers(patterns, branch), (
            f"{path.name} runs on push to {patterns!r}, but this run is about {branch!r}: no push would ever "
            f"reach it, so every job in it is unexecuted automation"
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
