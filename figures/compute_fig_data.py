"""Cache the numbers behind the paper figures (run in WSL with /opt/g4env/bin/python)."""
import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
import json
from pathlib import Path
EXP = _os.path.join(_ROOT, "results")
OUT = Path(__file__).resolve().parent / "fig_data.json"
L = lambda c: {(r := json.loads(l))["id"]: r for l in open(f"{EXP}/31b_{c}/results.jsonl")}
R = {c: L(c) for c in ["base", "kp", "gate2", "gate", "kp_gate"]}
meta = {json.loads(l)["instance_id"]: json.loads(l) for l in open(_os.path.join(_ROOT, "benchmark", "tasks_exp100.jsonl"))}
ALL = sorted(R["base"]); DEV = sorted(R["gate"]); HELD = sorted(set(ALL) - set(DEV))
def stats(c, ids):
    n = len(ids); s = sum(bool(R[c][i].get("patch")) for i in ids); r = sum(R[c][i]["resolved"] for i in ids)
    return {"n": n, "submitted": s, "resolved": r, "wrong": s - r, "none": n - s}
data = {"sets": {}, "repos": {}}
for lab, ids, cs in (("all", ALL, ["base", "kp", "gate2"]), ("dev", DEV, ["base", "kp", "gate", "kp_gate", "gate2"]), ("held", HELD, ["base", "kp", "gate2"])):
    data["sets"][lab] = {c: stats(c, ids) for c in cs}
for i in ALL:
    rp = meta[i]["repo"].split("/")[1]
    d = data["repos"].setdefault(rp, {"n": 0, "base": 0, "kp": 0, "gate2": 0})
    d["n"] += 1
    for c in ("base", "kp", "gate2"):
        d[c] += R[c][i]["resolved"]
OUT.write_text(json.dumps(data, indent=1))
print(json.dumps(data["sets"], indent=0)[:800])
