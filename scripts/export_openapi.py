"""Regenerate docs/api/openapi.json from the running API and print the route table.

    python -m uvicorn app.main:app --port 8731   # then, from apps/api:
    python ../../scripts/export_openapi.py [--base http://127.0.0.1:8731]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "api" / "openapi.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8731")
    args = parser.parse_args()

    with urllib.request.urlopen(f"{args.base}/api/v1/openapi.json", timeout=30) as response:
        spec = json.loads(response.read().decode("utf-8"))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    methods = sum(len(ops) for ops in spec["paths"].values() for ops in [list(ops) if isinstance(ops, dict) else []])
    print(f"wrote {OUT.relative_to(ROOT)} — {len(spec['paths'])} paths, {methods} operations, schemas={len(spec.get('components', {}).get('schemas', {}))}")
    for path in sorted(spec["paths"]):
        verbs = ",".join(sorted(v.upper() for v in spec["paths"][path]))
        print(f"  {verbs:22s} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
