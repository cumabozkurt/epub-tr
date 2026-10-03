"""Build side-by-side comparisons from --dump JSONL files: python scripts/compare.py uid1 uid2 ..."""
import glob, json, os, sys

uids = sys.argv[1:]
runs = {}
for f in sorted(glob.glob("out/logs/*.jsonl")):
    name = os.path.basename(f)[:-6]
    runs[name] = {json.loads(l)["uid"]: json.loads(l) for l in open(f, encoding="utf-8")}
for uid in uids:
    src = next((r[uid]["source"] for r in runs.values() if uid in r), None)
    print(f"#### Segment {uid}\n\n**Original (EN):** {src}\n")
    for name, r in runs.items():
        t = r.get(uid, {}).get("translation")
        if t:
            print(f"- **{name}**: {t}")
    print()
