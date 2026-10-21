#!/usr/bin/env python
"""A first-party security probe against a running API, with a JSON report.

This is not an external penetration test, and the report it writes says so. It is the
project's own battery over the claims M12 makes — that a private door refuses a caller
with no credential, that one account cannot read another's rows, that a cached answer is
never served to a different caller, that the limiter refuses, that a refusal is one shape
and leaks nothing, that the headers and CORS policy are the ones configured — run against
a live server rather than asserted from a test client.

The private-door population is not a list in this file: it is read from the committed
contract (`docs/api/openapi.json`), the same artifact the web client and the currency
gates read. A door that lands in the contract without a credential check appears here on
the next run, which is the point of deriving it.

Usage:
    python scripts/security_probe.py --base http://127.0.0.1:8751 \\
        --report .scratch/security-probe.json

The server must run with `ENV` other than `test` (the limiter and the response cache are
disabled there) and its `CORS_ORIGINS` must contain `--allow-origin`, which defaults to the
project's own web origin (`apps/api/.env` publishes the 3210 pair).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "api" / "openapi.json"
PARAM = re.compile(r"\{([^}]+)\}")

#: Floors for the contract census. They exist so an empty or half-read contract cannot
#: pass as a clean probe; they are set well under the counts at HEAD (212 secured
#: operations, 52 public, 91 private GET paths) and are printed with the run.
MIN_SECURED = 200
MIN_PUBLIC = 40
MIN_PRIVATE_GET = 85

PASSWORD = "probe-password-123"
LEAK_MARKERS = ("Traceback", "sqlalchemy", "SELECT ", "INSERT INTO", "C:\\", "/app/", "site-packages")


@dataclass
class Check:
    ident: str
    section: str
    claim: str
    ok: bool
    evidence: dict[str, Any] = field(default_factory=dict)
    note: str = ""


@dataclass
class Account:
    client: httpx.Client
    email: str
    token: str
    user: dict[str, Any]
    set_cookies: list[str]


class Probe:
    def __init__(self, base: str, allow_origin: str) -> None:
        self.base = base.rstrip("/")
        self.allow_origin = allow_origin
        self.checks: list[Check] = []
        self.started = datetime.now(UTC)
        self.contract_sha = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.anon = httpx.Client(base_url=self.base, timeout=20.0, follow_redirects=False)
        self.server_errors: list[dict[str, Any]] = []

    # -- contract ---------------------------------------------------------------------

    def private_operations(self) -> list[tuple[str, str, dict[str, Any]]]:
        out = []
        for path, ops in self.contract["paths"].items():
            for method, op in ops.items():
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue
                if op.get("security"):
                    out.append((method.upper(), path, op))
        return sorted(out, key=lambda row: (row[1], row[0]))

    def public_operations(self) -> list[tuple[str, str, dict[str, Any]]]:
        out = []
        for path, ops in self.contract["paths"].items():
            for method, op in ops.items():
                if method in ("get", "post", "put", "patch", "delete") and not op.get("security"):
                    out.append((method.upper(), path, op))
        return out

    @staticmethod
    def concrete_path(path: str, op: dict[str, Any]) -> str:
        declared = {p["name"]: p for p in op.get("parameters", []) if p.get("in") == "path"}

        def substitute(match: re.Match[str]) -> str:
            name = match.group(1)
            schema = declared.get(name, {}).get("schema", {})
            kind = schema.get("type")
            if kind in ("integer", "number"):
                return "1"
            if kind == "boolean":
                return "true"
            if schema.get("format") == "uuid":
                return "00000000-0000-0000-0000-000000000000"
            return "probe"

        return PARAM.sub(substitute, path)

    def remember_status(self, response: httpx.Response) -> None:
        if response.status_code >= 500:
            self.server_errors.append(
                {"method": response.request.method, "url": str(response.request.url), "status": response.status_code}
            )

    def call(self, client: httpx.Client, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = client.request(method, path, **kwargs)
        self.remember_status(response)
        return response

    # -- sections ---------------------------------------------------------------------

    def contract_census(self) -> None:
        private = self.private_operations()
        public = self.public_operations()
        private_gets = [row for row in private if row[0] == "GET"]
        ok = len(private) >= MIN_SECURED and len(public) >= MIN_PUBLIC and len(private_gets) >= MIN_PRIVATE_GET
        self.checks.append(
            Check(
                "C0",
                "contract",
                "the private-door population is read from the committed contract and is not empty",
                ok,
                {
                    "sha256": self.contract_sha,
                    "secured_operations": len(private),
                    "public_operations": len(public),
                    "private_get_paths": len(private_gets),
                    "floors": [MIN_SECURED, MIN_PUBLIC, MIN_PRIVATE_GET],
                },
            )
        )

    def unauthenticated_doors(self) -> None:
        rows = []
        for method, path, op in self.private_operations():
            concrete = self.concrete_path(path, op)
            body = {} if method in ("POST", "PUT", "PATCH") else None
            try:
                response = self.call(self.anon, method, concrete, json=body)
            except httpx.HTTPError as exc:
                rows.append({"method": method, "path": path, "status": None, "error": type(exc).__name__})
                continue
            rows.append({"method": method, "path": path, "status": response.status_code})

        statuses: dict[str, int] = {}
        for row in rows:
            statuses[str(row["status"])] = statuses.get(str(row["status"]), 0) + 1
        bad = [row for row in rows if row["status"] != 401]
        self.checks.append(
            Check(
                "S1",
                "authentication",
                "every secured operation refuses a caller with no credential, and asks for one",
                not bad,
                {"knocked": len(rows), "statuses": statuses, "deviations": bad[:20]},
            )
        )

    def tampered_token(self, account: Account) -> None:
        raw = account.token
        tampered = raw[:-4] + ("aaaa" if not raw.endswith("aaaa") else "bbbb")
        response = self.call(self.anon, "GET", "/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered}"})
        body = response.text
        self.checks.append(
            Check(
                "S2",
                "authentication",
                "a token whose signature no longer verifies is refused",
                response.status_code == 401 and not any(marker in body for marker in LEAK_MARKERS),
                {"status": response.status_code, "body_keys": sorted(self.body_keys(response))},
            )
        )

    def accounts(self) -> tuple[Account, Account]:
        def register(label: str) -> Account:
            client = httpx.Client(base_url=self.base, timeout=20.0, follow_redirects=False)
            email = f"probe-{label}-{uuid.uuid4().hex[:12]}@example.test"
            response = self.call(
                client,
                "POST",
                "/api/v1/auth/register",
                json={
                    "email": email,
                    "password": PASSWORD,
                    "display_name": f"Probe {label.upper()}",
                    "role": "player",
                    "accepts_data_policy": True,
                },
            )
            if response.status_code != 201:
                raise SystemExit(f"register {label} answered {response.status_code}: {response.text[:300]}")
            token = response.json()["access_token"]
            who = self.call(client, "GET", "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            return Account(client, email, token, who.json(), response.headers.get_list("set-cookie"))

        return register("a"), register("b")

    def call_as(self, account: Account, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {account.token}"
        return self.call(account.client, method, path, headers=headers, **kwargs)

    def board_payload(self, account: Account, marker: str) -> dict[str, Any]:
        """A board write whose eleven positions come from the server's own authored catalogue."""
        listing = self.call_as(account, "GET", "/api/v1/tactics").json()
        slug = listing["items"][0]["slug"]
        detail = self.call_as(account, "GET", f"/api/v1/tactics/{slug}").json()
        return {
            "name": f"Probe board {marker[:8]}",
            "origin_system": slug,
            "phase_in": detail["phase_in"],
            "phase_out": detail["phase_out"],
        }

    def ownership(self, a: Account, b: Account) -> None:
        marker = uuid.uuid4().hex
        created = self.call_as(a, "POST", "/api/v1/boards", json=self.board_payload(a, marker))
        board = created.json() if created.status_code == 201 else {}
        ident = board.get("id") or board.get("slug") or ""

        read = self.call_as(b, "GET", f"/api/v1/boards/{ident}")
        patch = self.call_as(b, "PATCH", f"/api/v1/boards/{ident}", json={"note": "probe"})
        listing = self.call_as(b, "GET", f"/api/v1/boards?probe={marker}")
        own = self.call_as(a, "GET", f"/api/v1/boards/{ident}")
        listing_a = self.call_as(a, "GET", f"/api/v1/boards?probe={marker}")

        board_leaked = bool(board.get("id")) and (
            board["id"] in listing.text or (board.get("slug") and board["slug"] in listing.text)
        )
        me_a = self.call_as(a, "GET", "/api/v1/auth/me").json()
        me_b = self.call_as(b, "GET", "/api/v1/auth/me").json()
        ok = (
            created.status_code == 201
            and ident != ""
            and own.status_code == 200
            and board.get("id") in listing_a.text
            and read.status_code == 404
            and patch.status_code == 404
            and not board_leaked
            and me_a.get("email") == a.email
            and me_b.get("email") == b.email
            and me_a.get("id") != me_b.get("id")
        )
        self.checks.append(
            Check(
                "S3",
                "ownership",
                "one account's row is absent to another, in both the direct read and the listing",
                ok,
                {
                    "created": created.status_code,
                    "created_error": created.text[:200] if created.status_code != 201 else "",
                    "owner_read": own.status_code,
                    "stranger_read": read.status_code,
                    "stranger_patch": patch.status_code,
                    "stranger_listing_status": listing.status_code,
                    "stranger_listing_contains_owner_row": board_leaked,
                    "me_is_caller_scoped": me_a.get("id") != me_b.get("id") and me_a.get("email") == a.email,
                },
            )
        )

    def cache_isolation(self, a: Account, b: Account) -> None:
        marker = uuid.uuid4().hex
        created = self.call_as(a, "POST", "/api/v1/boards", json=self.board_payload(a, marker))
        board_id = created.json().get("id", "") if created.status_code == 201 else ""
        query = f"/api/v1/boards?probe={marker}"

        # The owner warms the key first, so the stranger's read below is a read of a
        # warm path — the condition under which a key that names no caller hands over
        # someone else's row.
        a_first = self.call_as(a, "GET", query)
        b_first = self.call_as(b, "GET", query)
        a_second = self.call_as(a, "GET", query)
        b_second = self.call_as(b, "GET", query)

        # A public path at a query the cache has never seen: MISS then HIT.
        public_query = f"/healthz?probe={marker}"
        public_first = self.anon.get(self.base + public_query)
        public_second = self.anon.get(self.base + public_query)
        ids = [public_first.headers.get("x-request-id"), public_second.headers.get("x-request-id")]
        hit = public_second.headers.get("x-cache") == "HIT"
        same_body = public_first.text == public_second.text
        fresh_id = bool(ids[0]) and bool(ids[1]) and ids[0] != ids[1]

        leak = b_first.text + b_second.text
        b_got_a_row = bool(board_id) and board_id in leak
        a_owns_row = bool(board_id) and board_id in a_first.text and board_id in a_second.text
        ok = (
            created.status_code == 201
            and a_owns_row
            and b_first.status_code == 200
            and b_second.status_code == 200
            and hit
            and same_body
            and fresh_id
            and not b_got_a_row
        )
        self.checks.append(
            Check(
                "S4",
                "cache",
                "a public answer is served from cache under its own request id, and a cached private answer never crosses callers",
                ok,
                {
                    "a_first": [a_first.status_code, a_first.headers.get("x-cache")],
                    "b_first": [b_first.status_code, b_first.headers.get("x-cache")],
                    "a_second": [a_second.status_code, a_second.headers.get("x-cache")],
                    "b_second": [b_second.status_code, b_second.headers.get("x-cache")],
                    "owner_row_present_for_owner": a_owns_row,
                    "stranger_received_owner_row": b_got_a_row,
                    "public_hit": hit,
                    "public_bodies_identical": same_body,
                    "public_request_ids_differ": fresh_id,
                },
            )
        )

    def rate_limit(self, a: Account) -> None:
        codes = []
        first_429 = None
        for index in range(1, 13):
            response = a.client.post(
                "/api/v1/auth/login",
                json={"email": a.email, "password": PASSWORD},
            )
            self.remember_status(response)
            codes.append(response.status_code)
            if response.status_code == 429 and first_429 is None:
                first_429 = index
                retry_after = response.headers.get("retry-after", "")
                body = response.json().get("detail", {})
                self.checks.append(
                    Check(
                        "S5",
                        "rate limit",
                        "a login burst is refused with a coded 429 that says when to retry",
                        first_429 is not None
                        and first_429 > 1
                        and body.get("code") == "rate_limited"
                        and retry_after.isdigit()
                        and int(retry_after) > 0,
                        {
                            "burst_statuses": codes,
                            "first_429_at_burst_request": first_429,
                            "retry_after": retry_after,
                            "code": body.get("code"),
                            "note": "the burst follows one unauthenticated census knock on this path, so the "
                            "published 10/300s refuses the 11th hit in the window",
                        },
                    )
                )
        if first_429 is None:
            self.checks.append(
                Check(
                    "S5",
                    "rate limit",
                    "a login burst is refused with a coded 429 that says when to retry",
                    False,
                    {"burst_statuses": codes, "first_429_at_burst_request": None},
                )
            )

    def error_shapes(self, a: Account) -> None:
        malformed = self.anon.post(
            "/api/v1/auth/login", content=b"{", headers={"Content-Type": "application/json"}
        )
        self.remember_status(malformed)
        unknown = self.anon.get("/api/v1/probe-does-not-exist")
        self.remember_status(unknown)
        wrong_method = self.anon.request("DELETE", "/api/v1/healthz")
        self.remember_status(wrong_method)
        short_name = self.call_as(a, "POST", "/api/v1/boards", json={"name": "x"})
        bodies = {
            "malformed_json": malformed.text,
            "unknown_path": unknown.text,
            "wrong_method": wrong_method.text,
            "validation": short_name.text,
        }
        marker_hits = {name: [m for m in LEAK_MARKERS if m in body] for name, body in bodies.items()}
        malformed_detail = malformed.json().get("detail", {})
        rejected = malformed_detail.get("details") if isinstance(malformed_detail, dict) else None
        rejected_keys = sorted({key for row in rejected or [] for key in row}) if isinstance(rejected, list) else []
        validation_detail = short_name.json().get("detail", {})
        validation_rows = validation_detail.get("details") if isinstance(validation_detail, dict) else None

        unknown_detail = unknown.json().get("detail") if unknown.headers.get("content-type", "").startswith("application/json") else None
        unknown_shape = "object" if isinstance(unknown_detail, dict) else ("string" if isinstance(unknown_detail, str) else "other")
        ok = (
            malformed.status_code == 422
            and isinstance(malformed_detail, dict)
            and malformed_detail.get("code") == "validation_error"
            and "input" not in rejected_keys
            and "ctx" not in rejected_keys
            and short_name.status_code == 422
            and isinstance(validation_rows, list)
            and validation_rows
            and all("loc" in row and "type" in row for row in validation_rows)
            and not any(marker_hits.values())
        )
        self.checks.append(
            Check(
                "S6",
                "error shape",
                "refusals are one coded shape, name the field and rule, echo no submitted value and leak no internals",
                ok,
                {
                    "malformed_json": [malformed.status_code, malformed_detail.get("code") if isinstance(malformed_detail, dict) else None],
                    "rejected_keys": rejected_keys,
                    "validation": [short_name.status_code, len(validation_rows or [])],
                    "unknown_path": [unknown.status_code, unknown_shape],
                    "wrong_method": [wrong_method.status_code],
                    "leak_markers": marker_hits,
                },
                note="an unknown path is Starlette's own 404, not a door: its shape is recorded, not required",
            )
        )

    def headers(self) -> None:
        first = self.anon.get(self.base + f"/healthz?headers={uuid.uuid4().hex}")
        second = self.anon.get(self.base + f"/healthz?headers={uuid.uuid4().hex}")
        unauth = self.anon.get("/api/v1/auth/me")
        ids = [first.headers.get("x-request-id"), second.headers.get("x-request-id")]
        durations = [first.headers.get("x-request-duration-ms", ""), unauth.headers.get("x-request-duration-ms", "")]
        ok = (
            first.headers.get("x-content-type-options") == "nosniff"
            and unauth.headers.get("x-content-type-options") == "nosniff"
            and first.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
            and bool(ids[0])
            and bool(ids[1])
            and ids[0] != ids[1]
            and all(d.isdigit() for d in durations)
        )
        self.checks.append(
            Check(
                "S7",
                "headers",
                "every answer carries the security headers and its own request identity, including a refusal",
                ok,
                {
                    "nosniff_200": first.headers.get("x-content-type-options"),
                    "nosniff_401": unauth.headers.get("x-content-type-options"),
                    "referrer_policy": first.headers.get("referrer-policy"),
                    "request_ids_differ": ids[0] != ids[1],
                    "durations": durations,
                },
            )
        )

    def cors(self) -> None:
        evil = "https://evil.example"
        allowed = self.anon.get(self.base + f"/healthz?cors={uuid.uuid4().hex}", headers={"Origin": self.allow_origin})
        rogue = self.anon.get(self.base + f"/healthz?cors={uuid.uuid4().hex}", headers={"Origin": evil})
        preflight = self.anon.request(
            "OPTIONS",
            "/api/v1/boards",
            headers={
                "Origin": self.allow_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        rogue_preflight = self.anon.request(
            "OPTIONS",
            "/api/v1/boards",
            headers={
                "Origin": evil,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        ok = (
            allowed.headers.get("access-control-allow-origin") == self.allow_origin
            and allowed.headers.get("access-control-allow-credentials") == "true"
            and rogue.headers.get("access-control-allow-origin") is None
            and rogue_preflight.headers.get("access-control-allow-origin") is None
        )
        self.checks.append(
            Check(
                "S8",
                "cors",
                "only a configured origin is echoed, with credentials, and a rogue origin is never answered",
                ok,
                {
                    "allowed": [allowed.status_code, allowed.headers.get("access-control-allow-origin")],
                    "rogue": [rogue.status_code, rogue.headers.get("access-control-allow-origin")],
                    "preflight": [preflight.status_code, preflight.headers.get("access-control-allow-origin")],
                    "rogue_preflight": [rogue_preflight.status_code, rogue_preflight.headers.get("access-control-allow-origin")],
                    "allow_credentials": allowed.headers.get("access-control-allow-credentials"),
                },
            )
        )

    def cookies(self, a: Account) -> None:
        set_cookies = a.set_cookies
        refresh = [c for c in set_cookies if c.startswith("fo_refresh=")]
        cookie = refresh[0].lower() if refresh else ""
        ok = (
            bool(cookie)
            and "httponly" in cookie
            and "samesite=strict" in cookie
            and "path=/api/v1/auth" in cookie
        )
        self.checks.append(
            Check(
                "S9",
                "cookies",
                "the refresh cookie is httpOnly, SameSite=strict and scoped to the auth path",
                ok,
                {
                    "source": "the registration response",
                    "refresh_cookie_present": bool(cookie),
                    "httponly": "httponly" in cookie,
                    "samesite_strict": "samesite=strict" in cookie,
                    "path": "path=/api/v1/auth" in cookie,
                    "secure": "secure" in cookie,
                    "secure_note": "absent because this server runs with ENV=development; is_production gates it",
                },
            )
        )

    @staticmethod
    def body_keys(response: httpx.Response) -> set[str]:
        try:
            payload = response.json()
        except ValueError:
            return set()
        detail = payload.get("detail") if isinstance(payload, dict) else None
        return set(detail) if isinstance(detail, dict) else set(payload) if isinstance(payload, dict) else set()

    # -- runner -----------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        health = None
        for _ in range(60):
            try:
                health = self.anon.get("/healthz")
                if health.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        if health is None or health.status_code != 200:
            raise SystemExit(f"the server at {self.base} did not answer /healthz within 60s")

        self.contract_census()
        self.unauthenticated_doors()
        a, b = self.accounts()
        self.tampered_token(a)
        self.ownership(a, b)
        self.cache_isolation(a, b)
        self.rate_limit(a)
        self.error_shapes(a)
        self.headers()
        self.cors()
        self.cookies(a)

        finished = datetime.now(UTC)
        failed = [check for check in self.checks if not check.ok]
        return {
            "kind": "first-party security probe, not an external penetration test",
            "base": self.base,
            "started_at": self.started.isoformat(),
            "finished_at": finished.isoformat(),
            "duration_seconds": round((finished - self.started).total_seconds(), 2),
            "contract": {"path": "docs/api/openapi.json", "sha256": self.contract_sha},
            "checks": [check.__dict__ for check in self.checks],
            "passed": len(self.checks) - len(failed),
            "failed": len(failed),
            "server_errors": self.server_errors,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--base", default="http://127.0.0.1:8751", help="the API under probe")
    parser.add_argument("--report", default=".scratch/security-probe.json", help="where the JSON report lands")
    parser.add_argument(
        "--allow-origin",
        default="http://localhost:3210",
        help="an origin the server's CORS_ORIGINS contains; the probe uses it and a rogue one",
    )
    args = parser.parse_args()

    probe = Probe(args.base, args.allow_origin)
    report = probe.run()

    target = Path(args.report)
    if not target.is_absolute():
        target = ROOT / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for check in report["checks"]:
        mark = "PASS" if check["ok"] else "FAIL"
        print(f"{mark} {check['ident']} {check['section']}: {check['claim']}")
        if not check["ok"]:
            print(f"     evidence: {json.dumps(check['evidence'], sort_keys=True)}")
    print(
        f"\n{report['passed']} passed, {report['failed']} failed, "
        f"{len(report['server_errors'])} server error(s); report at {target}"
    )
    if report["server_errors"]:
        print(f"server errors: {json.dumps(report['server_errors'][:5])}")
    return 0 if report["failed"] == 0 and not report["server_errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
