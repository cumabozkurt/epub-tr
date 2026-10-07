"""Build side-by-side comparisons from --dump JSONL files: python scripts/compare.py uid1 uid2 ..."""
import glob
import json
import os
import sys

uids = sys.argv[1:]
runs = {}
for f in sorted(glob.glob("out/logs/*.jsonl")):
    name = os.path.basename(f)[:-6]
    with open(f, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh]
    runs[name] = {r["uid"]: r for r in rows}
for uid in uids:
    src = next((r[uid]["source"] for r in runs.values() if uid in r), None)
    print(f"#### Segment {uid}\n\n**Original (EN):** {src}\n")
    for name, r in runs.items():
        t = r.get(uid, {}).get("translation")
        if t:
            print(f"- **{name}**: {t}")
    print()
