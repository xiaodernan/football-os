"""Regenerate docs/api/openapi.json from the tree it is committed into, and print the route table.

    python scripts/export_openapi.py [--out PATH]

The spec is built in-process from `app.main.app.openapi()`, so the artifact can only ever describe the code sitting
next to this file. An earlier version fetched `{base}/api/v1/openapi.json` over HTTP from a *running* service
(default `http://127.0.0.1:8731`), which made the committed contract a property of whichever process happened to hold
that port: a default run against a foreign, older build wrote 86 paths over a 126-path file. Port 8731 is a shared
port on this machine, so that hazard is not historical.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
OUT = ROOT / "docs" / "api" / "openapi.json"


def spec_from_tree() -> dict:
    """`app.main.app.openapi()`, with the loaded `app` package proven to be this repository's."""
    sys.path.insert(0, str(API))
    import app.main as api_main

    loaded = Path(api_main.__file__).resolve()
    if not loaded.is_relative_to(API.resolve()):
        raise SystemExit(f"REFUSE: `app.main` resolved to {loaded}, outside {API} — an installed copy elsewhere "
                         "would answer for this tree")
    return api_main.app.openapi()


def render(spec: dict) -> str:
    return json.dumps(spec, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT, help="where to write; defaults to the committed contract")
    args = parser.parse_args()

    spec = spec_from_tree()
    target = args.out.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    # LF explicitly, on every platform: this artifact is committed as LF and the currency gate compares its bytes,
    # so a host that translates newlines on write must not be able to make a correct contract look wrong.
    target.write_text(render(spec), encoding="utf-8", newline="\n")

    methods = sum(len(ops) for ops in spec["paths"].values() for ops in [list(ops) if isinstance(ops, dict) else []])
    schemas = len(spec.get("components", {}).get("schemas", {}))
    print(f"wrote {target} — {len(spec['paths'])} paths, {methods} operations, schemas={schemas}")
    for path in sorted(spec["paths"]):
        verbs = ",".join(sorted(v.upper() for v in spec["paths"][path]))
        print(f"  {verbs:22s} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
