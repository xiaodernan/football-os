"""One-off: correct the stale final count (270 -> 152) across all six catalogues.

The manual and the dossier teaching key both quoted 270 real finals; the shelf now holds
152 committed `*-final.md` chapters. The number is part of the honesty contract, so every
locale must agree. Arabic numerals use Arabic-Indic digits.
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
        new = value.replace("270", "152").replace("\u0662\u0667\u0660", "\u0661\u0665\u0662")
        if new != value:
            data[ns][key] = new
            changed += 1
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(path.name, "updated", changed, "key(s)")
