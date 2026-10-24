"""The disaster-recovery pair must be unable to lie about what it did.

`scripts/backup_db.sh` and `scripts/restore_db.sh` are the two files this repository promises an operator in an
incident, and nothing in the repository invoked either one: the 2026-10-11 drill in
docs/M12_PRODUCTION_HARDENING_VERIFICATION.md ran `pg_dump` and `pg_restore` *inside the container*, and the absent
sibling of that drill let four defects sit in the scripts the drill was supposed to be exercising. Each defect is a
sentence the script could print without the world agreeing:

  * ``incremental`` printed "Checking WAL archive status", ran ``pg_waldump ... || true`` on a host with no such
    binary, and exited 0 — measured against the old file: exit 0, zero artifacts, zero ``pg_dump`` calls. A
    scheduler reading that exit code would have reported a month of missing WAL archives as green.
  * the restore's ``if [[ $? -eq 0 ]]`` was dead code under ``set -euo pipefail``: the ``pg_restore`` above it had
    already aborted the script, so the only branch describing a half-restored database could never run.
  * the final ``alembic upgrade head`` ran from the repository root, which has no ``alembic.ini``, so the migration
    replay the script announced in its own log failed before it reached a server.
  * the target defaulted to ``football_os_restore`` and the next line was ``DROP DATABASE IF EXISTS`` with no
    policy in between, while ``scripts/qa_db.py`` — the file that has always owned the scratch-name rule — sits two
    directories away. The default also connected to port 5432; this project's container publishes 54321.

So the population here is not only the two scripts. The coordinates come from `infra/docker-compose.yml` through
`scripts/dr_lib.sh`, the name decision comes from `scripts/qa_db.py`, and both are asked for their own values
rather than re-typed into this file. Every leg runs the shipped script (or the shipped shell function) with stub
`psql`/`pg_dump`/`pg_restore`/`python` binaries placed ahead of the real ones on `PATH`, so a change to a
decision — not only to a string — moves a verdict. No leg reaches a database server: the one stubbed call that
would have done so (`qa_db.py --name`) is recorded and short-circuited, which is also what makes the restore's
failure path reachable without a live tier.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "apps" / "api"
SCRIPTS = ROOT / "scripts"
COMPOSE = ROOT / "infra" / "docker-compose.yml"
BACKUP = "scripts/backup_db.sh"
RESTORE = "scripts/restore_db.sh"
DR_LIB = "scripts/dr_lib.sh"
QA_DB = SCRIPTS / "qa_db.py"
DR_SCRIPTS = (BACKUP, RESTORE)

#: What the stub `psql` answers for `pg_stat_archiver` when a leg means "archiving is armed and has produced
#: something": segment|timestamp|failed-count, in the `-F"|"` order the script reads.
ARCHIVER_ARMED = "0000000100000000003A66|2026-10-20 01:02:03+00|0"

#: The table count the stub `psql` answers for the restore script's closing measurement. One constant, because the
#: assertion below reads the same figure the stub prints rather than a second copy of it.
STUB_TABLE_COUNT = "42"

STUBS = {
    "psql": """#!/usr/bin/env bash
record() { [ -n "${STUB_ARGV-}" ] && printf '%s\\n' "$*" >>"$STUB_ARGV"; }
sql="${@: -1}"
case "$sql" in
  *"SHOW archive_mode"*) printf '%s\\n' "${STUB_ARCHIVE_MODE-off}" ;;
  *"pg_stat_archiver"*) printf '%s\\n' "${STUB_ARCHIVER-0000000100000000003A66|2026-10-20 01:02:03+00|0}" ;;
  *"pg_last_xact_replay_timestamp"*) printf '%s\\n' "${STUB_LAG-12}" ;;
  *pg_tables*) printf '%s\\n' "${STUB_TABLES-}" ;;
  *) printf '\\n' ;;
esac
exit "${STUB_PSQL_RC-0}"
""",
    "pg_isready": """#!/usr/bin/env bash
record() { [ -n "${STUB_ARGV-}" ] && printf '%s\\n' "$*" >>"$STUB_ARGV"; }
record "pg_isready $*"
exit "${STUB_READY_RC-0}"
""",
    "pg_dump": """#!/usr/bin/env bash
record() { [ -n "${STUB_ARGV-}" ] && printf '%s\\n' "$*" >>"$STUB_ARGV"; }
record "pg_dump $*"
for a in "$@"; do
  case "$a" in
    --file=*) printf 'FAKE DUMP\\n' >"${a#--file=}" ;;
  esac
done
exit "${STUB_DUMP_RC-0}"
""",
    "pg_restore": """#!/usr/bin/env bash
record() { [ -n "${STUB_ARGV-}" ] && printf '%s\\n' "$*" >>"$STUB_ARGV"; }
record "pg_restore $*"
for a in "$@"; do
  if [ "$a" = "--list" ]; then
    printf '; fake catalog\\n'
    exit "${STUB_LIST_RC-0}"
  fi
done
exit "${STUB_RESTORE_RC-0}"
""",
    # The restore script asks `python` for three things. The scratch-name decision is delegated to the real
    # interpreter, because that decision is the defect under test; the create and the migrate are recorded and
    # short-circuited, because no leg below may reach a server.
    "python": """#!/usr/bin/env bash
record() { [ -n "${STUB_ARGV-}" ] && printf '%s\\n' "$*" >>"$STUB_ARGV"; }
record "python $* cwd=$(pwd)"
for a in "$@"; do
  case "$a" in
    --assert-scratch) exec "$STUB_REAL_PYTHON" "$@" ;;
    --name) exit "${STUB_QADB_RC-0}" ;;
  esac
done
exit "${STUB_PY_RC-0}"
""",
    # The off-host hop. `aws s3 cp <src> s3://<bucket>/<name> --storage-class STANDARD_IA` is the one line that
    # decides whether a backup ever leaves the host, and it was inspection-verified only until this gate ran it.
    # The stub copies the source into a local "bucket" directory (the name after the s3:// prefix) so the leg can
    # prove the artifact actually landed off-host without a real S3 credential in the tree.
    "aws": """#!/usr/bin/env bash
record() { [ -n "${STUB_ARGV-}" ] && printf '%s\\n' "$*" >>"$STUB_ARGV"; }
record "aws $*"
src=""; dst=""; prev=""
for a in "$@"; do
  [ "$prev" = "cp" ] && src="$a"
  case "$a" in
    s3://*) dst="$a" ;;
  esac
  prev="$a"
done
if [ -n "$dst" ] && [ -n "${STUB_S3_DIR-}" ]; then
  name="${dst##*/}"
  cat "$src" > "${STUB_S3_DIR}/$name"
fi
exit "${STUB_AWS_RC-0}"
""",
}


def _bash() -> str:
    """The shell that runs the legs, named rather than guessed.

    A bare `bash` on this host can be a WSL relay that dies on a Windows path, so the Git-bash binary is tried
    before `PATH`; on the Linux CI runner `PATH` answers first. The choice is printed by the pre-flight case below,
    so a leg that fails for want of a shell says that instead of looking like a script defect.
    """
    for candidate in (
        os.environ.get("DR_BASH", ""),
        "C:/Program Files/Git/usr/bin/bash.exe",
        shutil.which("bash") or "",
        "/bin/bash",
    ):
        if candidate and Path(candidate).exists():
            return candidate
    raise AssertionError("no bash shell found: DR_BASH, the Git-bash path, `bash` on PATH, and /bin/bash all missed")


def _compose_lines(pattern: str) -> list[str]:
    return [line for line in COMPOSE.read_text(encoding="utf-8").splitlines() if re.search(pattern, line)]


def _compose_env(key: str) -> str:
    """`POSTGRES_DB` / `POSTGRES_USER` as the container defines them, read the same way the scripts read them."""
    lines = _compose_lines(rf"{key}: *[A-Za-z0-9_]+")
    assert len(lines) == 1, f"{COMPOSE} carries {len(lines)} {key} assignment(s); the DR pair derives from exactly one"
    return re.search(rf"{key}: *([A-Za-z0-9_]+)", lines[0]).group(1)  # type: ignore[union-attr]


def _derived_port() -> str:
    """The host side of the container's PostgreSQL mapping, read from the compose file that ships it."""
    lines = _compose_lines(r"\d+:5432\b")
    assert len(lines) == 1, (
        f"{COMPOSE} carries {len(lines)} line(s) mapping container port 5432; the DR pair derives its default from "
        "exactly one, so this gate has no single port to hold the scripts to"
    )
    match = re.search(r"(\d+):5432\b", lines[0])
    assert match is not None, f"{lines[0]!r} matched the mapping pattern but yielded no host port"
    return match.group(1)


def _stub_dir(tmp_path: Path) -> Path:
    stubs = tmp_path / "stubs"
    stubs.mkdir(parents=True, exist_ok=True)
    for name, body in STUBS.items():
        path = stubs / name
        path.write_text(body, encoding="utf-8", newline="\n")
        os.chmod(path, 0o755)
    return stubs


def _tool_dirs(bash: str) -> str:
    """The directory holding `dirname`, `grep`, `awk`, `mktemp` for the shell that will run the leg.

    On the Linux runner the ambient `PATH` already carries `/usr/bin`. On this host the child inherits a
    Windows-style `PATH` that does not carry Git's `usr/bin`, and the scripts' own `dirname` call failed with
    "command not found" — a statement about the harness, not about the script under test. The directory is
    added only when it is really there and really holds the tools, so a Linux run is left exactly as it was.
    """
    parent = Path(bash).parent
    if not (parent / "dirname.exe").exists() and not (parent / "dirname").exists():
        return ""
    return str(parent)


def _run(tmp_path: Path, argv: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run one shipped script — or one shipped shell function — with the stubs in front and no ambient PG* leaking.

    `PATH` is prepended, never replaced: the scripts under test shell out to `date`, `find`, `mktemp` and `awk`, and
    a scrubbed `PATH` would make them fail for a reason that has nothing to do with what is being measured.
    """
    bash = _bash()
    child = dict(os.environ)
    child["PATH"] = os.pathsep.join(part for part in (str(_stub_dir(tmp_path)), _tool_dirs(bash), child["PATH"]) if part)
    child["STUB_REAL_PYTHON"] = sys.executable
    child["STUB_ARGV"] = str(tmp_path / "argv.txt")
    child["STUB_TABLES"] = STUB_TABLE_COUNT
    for name in ("PGHOST", "PGPORT", "PGUSER", "PGDATABASE", "BACKUP_DIR", "REPLICA_HOST", "BACKUP_S3_BUCKET"):
        child.pop(name, None)
    # The scripts default their artifacts to /var/backups, a production path this host does not let a test write.
    # Redirecting it here keeps a permission error from masquerading as a verdict; a case that cares about the
    # directory passes its own.
    backups = tmp_path / "backups"
    backups.mkdir(exist_ok=True)
    child["BACKUP_DIR"] = str(backups).replace("\\", "/")
    child.update(env or {})
    return subprocess.run(
        [bash, *argv],
        cwd=str(ROOT),
        env=child,
        capture_output=True,
        text=True,
        encoding="utf-8",
        # bash localises its own diagnostics in the host's encoding; a replacement character in a `mkdir:` line
        # must not kill the reader thread and turn an asserted `stderr` into None.
        errors="replace",
        timeout=180,
    )


def _code_lines(relative: str) -> list[str]:
    """The script's own lines, comments stripped.

    Every script here explains the 5432-vs-54321 history in prose, so a scan that read comments would forbid the
    very sentence that documents the defect. Only executable lines are charged.
    """
    lines: list[str] = []
    for raw in (ROOT / relative).read_text(encoding="utf-8").splitlines():
        if raw.lstrip().startswith("#"):
            continue
        lines.append(re.sub(r"(?<!\\)#.*$", "", raw))
    return lines


def _argv(tmp_path: Path) -> list[str]:
    log = tmp_path / "argv.txt"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def _load_qa_db():
    spec = importlib.util.spec_from_file_location("qa_db_under_test", QA_DB)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def shell() -> str:
    bash = _bash()
    probe = subprocess.run([bash, "-c", "printf ok"], capture_output=True, text=True, encoding="utf-8")
    assert probe.returncode == 0 and probe.stdout == "ok", f"the leg shell {bash!r} cannot run a printf: {probe.stderr!r}"
    return bash


def test_the_leg_shell_is_named_and_works(shell: str) -> None:
    assert shell, "a leg that cannot name its shell would blame the scripts for the harness"


def test_the_derivation_reads_the_compose_the_project_ships(tmp_path: Path, shell: str) -> None:
    port = _derived_port()
    result = _run(tmp_path, ["-c", f'source "{DR_LIB}"; dr_published_pg_port'])
    assert result.returncode == 0, f"dr_published_pg_port refused to read {COMPOSE}: {result.stderr!r}"
    assert result.stdout.strip() == port, (
        f"the shipped derivation answered {result.stdout.strip()!r} while {COMPOSE} says {port!r}; the scripts and "
        "this gate would then disagree about which server to talk to without either noticing"
    )
    assert port != "5432", (
        f"{COMPOSE} maps host port {port} to the container's PostgreSQL. The DR pair's default used to be 5432; if "
        "this project ever publishes 5432 the pin above still holds and this sentence needs re-reading, not removal"
    )


def test_dr_lib_refuses_a_compose_it_cannot_pick_from(tmp_path: Path, shell: str) -> None:
    """Zero or two candidate mappings stop the scripts; they do not fall back to a remembered number."""
    for label, body, expected in (
        ("two-mapping", 'db:\n  ports:\n    - "54321:5432"\n    - "54322:5432"\n', "2"),
        ("no-mapping", "db:\n  image: pgvector/pgvector:pg16\n", "0"),
    ):
        compose = tmp_path / f"{label}.yml"
        compose.write_text(body, encoding="utf-8", newline="\n")
        result = _run(
            tmp_path,
            ["-c", f'source "{DR_LIB}"; dr_published_pg_port'],
            env={"DR_COMPOSE_FILE": str(compose).replace("\\", "/")},
        )
        assert result.returncode == 2, (
            f"a compose with no single PostgreSQL mapping has to stop the scripts; against {label} it exited "
            f"{result.returncode} with stdout {result.stdout!r}"
        )
        assert f"carries {expected} PostgreSQL host-port mapping line(s)" in result.stderr, (
            f"the {label} refusal did not state the count it read: {result.stderr!r}"
        )


def test_no_dr_script_types_the_server_coordinates(shell: str) -> None:
    """Neither DR script may carry its own PG* default again, and both must ask `dr_lib` for the four values.

    Charged on code lines only: `infra/docker-compose.yml` is the carrier of these numbers, and a second copy in a
    shell script is what pointed the pair at port 5432 while the container published 54321.
    """
    offenders: list[str] = []
    for relative in DR_SCRIPTS:
        code = "\n".join(_code_lines(relative))
        for name in ("PGHOST", "PGPORT", "PGUSER", "PGDATABASE"):
            if re.search(rf'^\s*{name}=', code, re.M):
                offenders.append(f"{relative} assigns {name} itself")
        for literal in ("5432", "football_os", "football"):
            if re.search(rf'\-\-{literal}\b', code) or re.search(rf':-{literal}[}}"]', code):
                offenders.append(f"{relative} hard-codes {literal!r}")
        if 'source "$ROOT/scripts/dr_lib.sh"' not in code:
            offenders.append(f"{relative} does not source scripts/dr_lib.sh")
        if "dr_pg_defaults" not in code:
            offenders.append(f"{relative} never calls dr_pg_defaults, so it runs with whatever the ambient shell says")
    assert not offenders, f"the DR pair stopped reading its coordinates from the compose file: {offenders}"


def test_the_port_the_scripts_use_reaches_pg_dump(tmp_path: Path, shell: str) -> None:
    """The derived default is not decoration: it arrives on the command line of the shipped backup call."""
    backups = tmp_path / "backups"
    backups.mkdir()
    result = _run(tmp_path, [BACKUP, "full"], env={"BACKUP_DIR": str(backups).replace("\\", "/")})
    assert result.returncode == 0, f"`backup_db.sh full` failed against the stubs: {result.stdout!r} {result.stderr!r}"
    dumps = [line for line in _argv(tmp_path) if line.startswith("pg_dump ")]
    assert len(dumps) == 1, f"the full leg expected exactly one pg_dump call, read {dumps!r}"
    port = _derived_port()
    assert f"--port={port}" in dumps[0], f"pg_dump ran without the compose-derived port in its argv: {dumps[0]!r}"
    database = _compose_env("POSTGRES_DB")
    assert f"--dbname={database}" in dumps[0], (
        f"pg_dump's database did not carry compose's POSTGRES_DB ({database!r}): {dumps[0]!r}"
    )
    assert f"--username={_compose_env('POSTGRES_USER')}" in dumps[0], (
        f"pg_dump's user did not carry compose's POSTGRES_USER: {dumps[0]!r}"
    )
    dumps_dir = list(backups.glob("football_os_*.dump"))
    assert len(dumps_dir) == 1, f"a full backup that reports success must leave exactly one artifact, saw {dumps_dir}"
    assert "Cleanup: removed 0 backup(s) older than 7 days" in result.stdout, (
        f"the cleanup line must report the count it read from the same listing it deleted: {result.stdout!r}"
    )


def test_the_scratch_policy_refuses_the_databases_an_operator_must_not_overwrite(tmp_path: Path) -> None:
    """`qa_db.py`'s own rule, read through the shipped CLI once and through the shipped function for the table.

    The names are the ones this repository has actually used or actually runs: `football_os` is the live database,
    `football_os_restore` was the restore script's own default, and `postgres` is the maintenance database the pair
    connects through.
    """
    module = _load_qa_db()
    for name in ("football_os", "football_os_restore", "football_os_restore_drill", "postgres"):
        assert module.scratch_refusal(name) is not None, f"{name!r} was accepted as a scratch name"
    for name in ("football_os_scratch_restore", "football_os_qa", f"football_os_scratch_dr_leg_{os.getpid()}"):
        assert module.scratch_refusal(name) is None, f"{name!r} was refused although it says throwaway: {module.scratch_refusal(name)}"

    refused = subprocess.run(
        [sys.executable, str(QA_DB), "--assert-scratch", "football_os"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    assert refused.returncode == 1, f"the shipped policy CLI accepted the live database name: {refused.stdout!r}"
    assert "REFUSED" in refused.stderr and "football_os" in refused.stderr, (
        f"the refusal did not name the database it refused: {refused.stderr!r}"
    )


def test_restore_default_target_passes_the_policy_it_calls(shell: str) -> None:
    """The default the restore script hands to the policy is read from the script's own bytes, not typed here."""
    matches = re.findall(r'TARGET_DB="\$\{2:-([a-z0-9_]+)\}"', (ROOT / RESTORE).read_text(encoding="utf-8"))
    assert len(matches) == 1, f"expected one TARGET_DB default in {RESTORE}, read {matches!r}"
    default = matches[0]
    result = subprocess.run(
        [sys.executable, str(QA_DB), "--assert-scratch", default],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    assert result.returncode == 0, (
        f"{RESTORE} defaults to {default!r}, which its own policy call refuses: {result.stderr!r} — an operator "
        "running the documented command would be stopped at step one"
    )


def test_restore_refuses_a_live_database_before_it_touches_anything(tmp_path: Path, shell: str) -> None:
    dump = tmp_path / "incident.dump"
    dump.write_text("FAKE DUMP\n", encoding="utf-8", newline="\n")
    result = _run(tmp_path, [RESTORE, str(dump).replace("\\", "/"), "football_os"])
    assert result.returncode != 0, "restore_db.sh restored into the name the scratch policy refuses"
    assert "does not start with qa/walk/scratch" in (result.stderr or "") + (result.stdout or ""), (
        f"the refusal did not quote the policy it applied: {result.stdout!r} {result.stderr!r}"
    )
    assert "Restore completed" not in result.stdout, f"a refused restore still announced success: {result.stdout!r}"
    assert not [line for line in _argv(tmp_path) if line.startswith("pg_restore ")], (
        "the name decision arrived after pg_restore had already run — everything past it is work on the live database"
    )


def test_an_incremental_backup_without_an_archive_refuses(tmp_path: Path, shell: str) -> None:
    backups = tmp_path / "backups"
    backups.mkdir()
    result = _run(tmp_path, [BACKUP, "incremental"], env={"BACKUP_DIR": str(backups).replace("\\", "/")})
    assert result.returncode == 2, (
        f"archive_mode=off must stop the incremental leg; it exited {result.returncode} with {result.stdout!r} — "
        "the defect this case exists for was exit 0 with no artifact at all"
    )
    assert "REFUSED" in result.stdout and "archive_mode" in result.stdout, (
        f"the refusal did not name the setting it asked about: {result.stdout!r}"
    )
    assert "Backup completed successfully" not in result.stdout, f"a refused backup said it completed: {result.stdout!r}"
    assert list(backups.iterdir()) == [], f"`incremental` produced artifacts it did not mention: {list(backups.iterdir())}"


def test_an_incremental_backup_reports_the_archive_it_measured(tmp_path: Path, shell: str) -> None:
    backups = tmp_path / "backups"
    backups.mkdir()
    result = _run(
        tmp_path,
        [BACKUP, "incremental"],
        env={"BACKUP_DIR": str(backups).replace("\\", "/"), "STUB_ARCHIVE_MODE": "on", "STUB_ARCHIVER": ARCHIVER_ARMED},
    )
    assert result.returncode == 0, f"an armed archive must pass the check: {result.stdout!r} {result.stderr!r}"
    assert "Last archived WAL: 0000000100000000003A66 at 2026-10-20 01:02:03+00" in result.stdout, (
        f"the pass did not report the segment it read: {result.stdout!r}"
    )
    empty = _run(
        tmp_path,
        [BACKUP, "incremental"],
        env={"BACKUP_DIR": str(backups).replace("\\", "/"), "STUB_ARCHIVE_MODE": "on", "STUB_ARCHIVER": "-|-|0"},
    )
    assert empty.returncode == 2, (
        f"archive_mode=on with nothing ever archived is the silent month this case exists for; it exited "
        f"{empty.returncode} with {empty.stdout!r}"
    )


def test_replica_lag_that_cannot_be_read_is_a_refusal(tmp_path: Path, shell: str) -> None:
    """An unread lag is not a green check, and a lag over the ceiling is not a warning line in a successful run."""
    armed = {"STUB_ARCHIVE_MODE": "on", "REPLICA_HOST": "replica.example"}
    unread = _run(tmp_path, [BACKUP, "incremental"], env=dict(armed, STUB_LAG=""))
    assert unread.returncode == 2, f"a replica that answers nothing must fail the check: {unread.stdout!r}"
    assert "did not answer the replay-lag query" in unread.stdout, f"the refusal misdescribed what it saw: {unread.stdout!r}"
    over = _run(tmp_path, [BACKUP, "incremental"], env=dict(armed, STUB_LAG="900"))
    assert over.returncode == 2, f"900s of lag against a 300s ceiling exited {over.returncode}: {over.stdout!r}"
    assert "Backup completed successfully" not in over.stdout, f"an over-ceiling lag still completed: {over.stdout!r}"
    under = _run(tmp_path, [BACKUP, "incremental"], env=dict(armed, STUB_LAG="12"))
    assert under.returncode == 0, f"12s against a 300s ceiling must pass: {under.stdout!r}"
    tight = _run(tmp_path, [BACKUP, "incremental"], env=dict(armed, STUB_LAG="12", REPLICA_LAG_CEILING_SECONDS="10"))
    assert tight.returncode == 2, (
        f"a 10s ceiling with 12s of lag exited {tight.returncode}; the ceiling is only a ceiling if the leg reads it: "
        f"{tight.stdout!r}"
    )


def test_a_failed_restore_cannot_report_success(tmp_path: Path, shell: str) -> None:
    """The dead branch, made alive: `pg_restore` failing stops the script before its own success line.

    A `$?` test cannot run under `set -euo pipefail` — the failing command aborts the script first, which is why the
    old "ERROR: Restore failed" line was unreachable and why this leg reads the captured status instead.
    """
    for relative in DR_SCRIPTS:
        # `rc=$?` is the fix, so the ban is on a *conditional* reading `$?` — the branch that cannot run under
        # `set -e` because the failing command has already aborted the script.
        offenders = [line for line in _code_lines(relative) if re.search(r"\b(?:if|elif|while)\b.*\$\?", line)]
        assert not offenders, (
            f"{relative} branches on $? again ({offenders!r}); under `set -e` that branch never runs"
        )
        assert "set -euo pipefail" in (ROOT / relative).read_text(encoding="utf-8"), (
            f"{relative} lost `set -euo pipefail`, the reason the old failure branch was unreachable"
        )

    dump = tmp_path / "incident.dump"
    dump.write_text("FAKE DUMP\n", encoding="utf-8", newline="\n")
    target = f"football_os_scratch_dr_leg_{os.getpid()}"
    failed = _run(tmp_path, [RESTORE, str(dump).replace("\\", "/"), target], env={"STUB_RESTORE_RC": "1"})
    assert failed.returncode != 0, f"a failing pg_restore exited the script 0: {failed.stdout!r}"
    assert "pg_restore exited 1" in failed.stdout, f"the failure line did not carry the status it captured: {failed.stdout!r}"
    assert "Restore completed" not in failed.stdout, f"a partial copy was announced as a restore: {failed.stdout!r}"
    assert not [line for line in _argv(tmp_path) if "alembic" in line], (
        "the migration replay ran against a database the restore had not finished writing"
    )


def test_the_migration_replay_runs_from_where_alembic_ini_is(tmp_path: Path, shell: str) -> None:
    """`alembic.ini` is at `apps/api/`, the repository root has none, and the leg is measured at the cwd it ran in.

    The old line ran `python -m alembic upgrade head` from the root and failed with "No config file 'alembic.ini'
    found" — the announcement in the log, the replay never done.
    """
    assert (API / "alembic.ini").exists(), f"{API} is where the migration environment lives; this gate's basis moved"
    assert not (ROOT / "alembic.ini").exists(), (
        "the repository root gained an alembic.ini, so the restore script's cwd choice needs re-reading rather than "
        "this case weakening"
    )

    dump = tmp_path / "incident.dump"
    dump.write_text("FAKE DUMP\n", encoding="utf-8", newline="\n")
    target = f"football_os_scratch_dr_leg_{os.getpid()}"
    ok = _run(tmp_path, [RESTORE, str(dump).replace("\\", "/"), target])
    assert ok.returncode == 0, f"the all-pass leg failed: {ok.stdout!r} {ok.stderr!r}"
    migrations = [line for line in _argv(tmp_path) if " -m alembic " in line]
    assert len(migrations) == 1, f"expected one alembic call from the restore script, read {migrations!r}"
    tail = Path(migrations[0].split("cwd=")[1].replace("\\", "/")).parts[-2:]
    assert tail == ("apps", "api"), (
        f"alembic ran from ...{migrations[0].split('cwd=')[1]!r}; the replay only finds its config one way, and the "
        f"root is where {ROOT / 'alembic.ini'} does not exist"
    )
    assert "holds 42 public table(s)" in ok.stdout, (
        f"the closing line must report the count it read from the restored database: {ok.stdout!r}"
    )
    unread = _run(tmp_path, [RESTORE, str(dump).replace("\\", "/"), target], env={"STUB_TABLES": ""})
    assert unread.returncode != 0, f"a restore whose table count could not be read still exited 0: {unread.stdout!r}"
    assert "Restore completed" not in unread.stdout, f"an unread count was printed as 0 tables: {unread.stdout!r}"


def test_backup_db_still_names_what_it_cannot_do(shell: str) -> None:
    """The refusal text is the operator's only documentation mid-incident, so it stays attached to the branch."""
    code = "\n".join(_code_lines(BACKUP))
    for sentence in ("REFUSED", "archive_mode", "backup_db.sh full"):
        assert sentence in code, f"the incremental refusal no longer says {sentence!r}, which is the way out it offers"


def test_the_off_host_upload_fires_when_a_bucket_is_named(tmp_path: Path, shell: str) -> None:
    """The one line that decides whether a backup leaves the host must actually run, with the named bucket and the
    storage class, and the artifact must land off-host. Until this gate it was inspection-verified only.

    No leg reaches a database server: the `pg_dump` stub writes the dump, and the `aws` stub copies it into a local
    "bucket" directory, so the off-host hop is exercised without a real S3 credential in the tree.
    """
    backups = tmp_path / "backups"
    backups.mkdir()
    bucket = tmp_path / "s3-bucket"
    bucket.mkdir()
    result = _run(
        tmp_path,
        [BACKUP, "full"],
        env={
            "BACKUP_DIR": str(backups).replace("\\", "/"),
            "BACKUP_S3_BUCKET": "test-bucket",
            "STUB_S3_DIR": str(bucket).replace("\\", "/"),
        },
    )
    assert result.returncode == 0, (
        f"`backup_db.sh full` with a bucket failed: {result.stdout!r} {result.stderr!r}"
    )
    uploads = [line for line in _argv(tmp_path) if line.startswith("aws ")]
    assert len(uploads) == 1, f"the off-host leg expected exactly one aws call, read {uploads!r}"
    assert "s3 cp" in uploads[0] and "s3://test-bucket/" in uploads[0], (
        f"the upload did not target the named bucket: {uploads[0]!r}"
    )
    assert "--storage-class STANDARD_IA" in uploads[0], (
        f"the upload omitted the storage class the script promises: {uploads[0]!r}"
    )
    landed = list(bucket.glob("football_os_*.dump"))
    assert len(landed) == 1, f"the off-host upload must land the artifact in the bucket; saw {landed!r}"


def test_no_off_host_upload_without_a_bucket(tmp_path: Path, shell: str) -> None:
    """An unset `BACKUP_S3_BUCKET` means the off-host hop never runs — the default is a local-only dump."""
    backups = tmp_path / "backups"
    backups.mkdir()
    result = _run(tmp_path, [BACKUP, "full"], env={"BACKUP_DIR": str(backups).replace("\\", "/")})
    assert result.returncode == 0, (
        f"`backup_db.sh full` without a bucket failed: {result.stdout!r} {result.stderr!r}"
    )
    uploads = [line for line in _argv(tmp_path) if line.startswith("aws ")]
    assert not uploads, f"no S3_BUCKET must mean no upload call; saw {uploads!r}"
    assert "Uploading to s3://" not in result.stdout, (
        f"the log claimed an upload with no bucket: {result.stdout!r}"
    )
