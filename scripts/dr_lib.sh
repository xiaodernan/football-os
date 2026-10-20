#!/usr/bin/env bash
# The server the disaster-recovery pair connects to, read from the file that decides it: `infra/docker-compose.yml`.
#
# Both DR scripts used to type their own defaults, and the typed copies disagreed with the container. The port was
# the load-bearing one: the pair defaulted to 5432 while this project's Postgres publishes 54321 (README.md's port
# row, and the compose mapping this file reads). An operator following the documented drill on a machine with no
# PG* environment exported would therefore have run `pg_dump` against a server nothing in this repository starts,
# and `check_pg`'s "Cannot connect to PostgreSQL at localhost:5432" would have been a true sentence about the wrong
# port — the container was healthy the whole time. A default is a copy, so `POSTGRES_USER` and `POSTGRES_DB` moved
# here too; today they happen to say `football` and `football_os`, which is why the change is invisible until the
# compose file is edited.
#
# Deriving beats guessing: when the file carries zero or two matching lines, this refuses with the count it read
# rather than falling back to a number. A silent fallback is how a guard becomes decoration.
#
# `DR_COMPOSE_FILE` points the read somewhere else. It exists so the gate can hand this file a compose with two
# mappings and watch it refuse; an operator with a second stack is the other reason.
#
# No `set -e` here on purpose: this file is sourced, and a library that changes its caller's error mode is how a
# caller stops failing where it means to.
DR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DR_COMPOSE_FILE="${DR_COMPOSE_FILE:-$DR_ROOT/infra/docker-compose.yml}"

# Print the single value compose carries for an `-oE` pattern. $1 pattern, $2 what the line is called,
# $3 an `sed -E` expression that lifts the value out of the match. Returns 2 with the count it saw when the
# file does not carry exactly one such line.
dr_one_compose_value() {
  local pattern="$1" label="$2" stripper="$3"
  local matches count
  if [[ ! -f "$DR_COMPOSE_FILE" ]]; then
    printf 'REFUSED: %s is not readable, so the %s cannot be derived\n' "$DR_COMPOSE_FILE" "$label" >&2
    return 2
  fi
  matches="$(grep -oE "$pattern" "$DR_COMPOSE_FILE" 2>/dev/null || true)"
  count="$(printf '%s' "$matches" | grep -c . || true)"
  if ((count != 1)); then
    printf 'REFUSED: %s carries %s %s line(s); this script needs exactly one, so it will not pick\n' \
      "$DR_COMPOSE_FILE" "$count" "$label" >&2
    return 2
  fi
  printf '%s\n' "$matches" | sed -E "$stripper"
}

# The host side of the mapping that publishes the container's PostgreSQL. The container side is matched, not
# assumed: a stack that moves the internal port stops here rather than restoring into an unrelated listener.
dr_published_pg_port() { dr_one_compose_value '[0-9]+:5432\b' 'PostgreSQL host-port mapping' 's/:.*//'; }

dr_compose_env() { dr_one_compose_value "$1: *[A-Za-z0-9_]+" "$1 assignment" 's/^[A-Z_]+: *//'; }

# Fill PGHOST/PGPORT/PGDATABASE/PGUSER from compose, leaving anything the operator exported alone. An exported
# PGPORT is a deliberate override; the typed 5432 was the accident, so the override still wins.
dr_pg_defaults() {
  local port database user
  port="$(dr_published_pg_port)" || return 2
  database="$(dr_compose_env POSTGRES_DB)" || return 2
  user="$(dr_compose_env POSTGRES_USER)" || return 2
  export PGHOST="${PGHOST:-localhost}"
  export PGPORT="${PGPORT:-$port}"
  export PGDATABASE="${PGDATABASE:-$database}"
  export PGUSER="${PGUSER:-$user}"
}
