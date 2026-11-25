"""One-off: correct the archived-final count across all six catalogues.

The manual and the dossier teaching key quote the number of committed `*-final.md` chapters.
Re-run with the current pair of numerals whenever the shelf grows; Arabic uses Arabic-Indic
digits. The last bake moved 270 -> 152 -> 156 -> 157 as verified finals landed.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MSG = ROOT / "apps" / "web" / "messages"

for path in sorted(MSG.glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for ns, key in (("manual", "tour22d"), ("worldDossier", "teachOne")):
        value = data.get(ns, {}).get(key)
        if not isinstance(value, str):
            continue
        new = value.replace("158", "157").replace("\u0661\u0665\u0668", "\u0661\u0665\u0667")
        if new != value:
            data[ns][key] = new
            changed += 1
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(path.name, "updated", changed, "key(s)")
