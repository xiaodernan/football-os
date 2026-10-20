#!/usr/bin/env bash
# The project's one lint target, written down once. `scripts/check.sh` and `.github/workflows/ci.yml` both call
# this file, so the local gate and CI cannot disagree about which files are linted. That disagreement is what
# PLAN.md's Item 0 exists to end: three targets were in use at once and only one was enforced, so a green local
# run was not evidence that the commit was green. Neither caller may name a target of its own any more.
#
# Two measurements decide the shape of this file:
#
#   * ruff runs with `apps/api` as its project root, because that is what makes `app.*` first-party. Run from the
#     repository root with `--config apps/api/pyproject.toml`, the same config sorts `from app.core.config import
#     settings` into the third-party block and reports 71 import-ordering errors in files the old target called
#     clean. Those reds are artifacts of the invocation, not of the code, and a gate that produces them gets
#     ignored within a week.
#   * Everything outside `apps/api` is derived from `git ls-files` on every run. A hand-typed list is how four
#     committed files in `scripts/` stayed invisible to a command whose own comment claimed it walked the whole
#     project; a derived list means a newly committed `.py` cannot arrive out of target, and a narrowed one is
#     visible in the count this script prints.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API="$ROOT/apps/api"

# Tracked means committed-or-staged: a file a person has added is in the target before it is in `main`.
mapfile -d '' -t tracked < <(git -C "$ROOT" ls-files -z -- '*.py')
outside=()
for f in "${tracked[@]}"; do
  [[ $f == apps/api/* ]] || outside+=("$f")
done

declare -A seen=()
dirs=()
for f in "${outside[@]}"; do
  d="${f%/*}"
  if [[ -n "${seen[$d]+x}" ]]; then
    continue
  fi
  seen[$d]=1
  dirs+=("$d")
done

# The population is printed, never just counted: "0 committed files outside apps/api" has to read as a narrowing
# of the target, not as a pass. This repo has committed Python; if the walk returns an empty tracked set,
# something is broken about the invocation (no git, wrong repo, a pathspec typo) and the run must say so.
(( ${#tracked[@]} > 0 )) || { echo "REFUSED: git ls-files returned no committed .py at $ROOT"; exit 2; }
echo "lint target: apps/api (whole tree) plus ${#outside[@]} committed .py outside it, in ${#dirs[@]} derived dir(s): $(IFS=,; echo "${dirs[*]:-none}")"
if ((${#outside[@]} > 0)); then
  printf '  %s\n' "${outside[@]}"
fi

targets=("$API")
for d in "${dirs[@]}"; do
  targets+=("$ROOT/$d")
done

(cd "$API" && python -m ruff check "${targets[@]}")
