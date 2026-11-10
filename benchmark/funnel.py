"""Benchmark funnel for the paper (11/7): candidates -> linked issues -> executed -> valid -> valid on the final images,
with the reason each executed candidate was dropped. Reads summary.json, linked_prs.json, validation_rounds.jsonl
(the last record of every executed candidate before the final re-check) and validation.jsonl (the final re-check)."""
import collections
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
rounds = [json.loads(l) for l in (HERE / "validation_rounds.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
final = {(r := json.loads(l))["instance_id"]: r for l in (HERE / "validation.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
assert len({r["instance_id"] for r in rounds}) == len(rounds), "one record per executed candidate"


def reason(r):
    if r["empty"]["resolved"]:
        return "empty patch already passes"
    g = r.get("gold1", {}) or {}
    t, e = g.get("tail", "") or "", str(g.get("error") or "")
    if "apply" in e.lower():
        return "test or gold patch does not apply"
    if re.search(r"No module named|cannot import name", t):
        return "missing dependency in the offline image"
    if g.get("exit") in (124, 137) or "timed out" in (t + e).lower():
        return "timeout"
    if g.get("resolved") and not (r.get("gold2") or {}).get("resolved"):
        return "gold passes once, fails on repeat (flaky)"
    if re.search(r"\d+ failed", t):
        return "gold patch fails its own tests offline"
    if re.search(r"\d+ errors?", t):
        return "test collection or setup errors"
    return "other"


print(f"executed candidates: {len(rounds)}; valid in validation rounds: {sum(r['valid'] for r in rounds)}")
c = collections.Counter(reason(r) for r in rounds if not r["valid"])
for k, v in c.most_common():
    print(f"  dropped: {k:45s} {v}")
fv = [i for i, r in final.items() if r["valid"]]
print(f"re-verified on final images: {len(final)}; still valid: {len(fv)}")
for i, r in final.items():
    if not r["valid"]:
        print(f"  dropped at final re-check: {i} ({reason(r)})")
print("by repository (executed / valid final):")
ex = collections.Counter(r["repo"].split("/")[1] for r in rounds)
ok = collections.Counter(r["repo"].split("/")[1] for i, r in final.items() if r["valid"])
for k in ex:
    print(f"  {k:12s} {ex[k]:4d} {ok.get(k, 0):4d}")
summ = json.loads((HERE / "summary.json").read_text(encoding="utf-8"))
print("candidates (test+src, <=3 source files):", sum(v.get("test+src_le3src", 0) for v in summ.values()))
