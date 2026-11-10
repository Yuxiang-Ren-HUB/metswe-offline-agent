import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
import json, collections
EXP = _os.path.join(_ROOT, "results")
R = {(r := json.loads(l))["id"]: r for l in open(f"{EXP}/31b_gate2/results.jsonl")}
B = {(r := json.loads(l))["id"]: r for l in open(f"{EXP}/31b_base/results.jsonl")}
ev = collections.defaultdict(list)
for l in open(f"{EXP}/31b_gate2/offline_events.jsonl"):
    e = json.loads(l); ev[e["task"]].append(e)
grp = collections.defaultdict(lambda: [0, 0])
for i, r in R.items():
    if not r.get("patch"): continue
    gates = [e for e in ev[i] if e["event"] == "gate"]
    if not gates: k = "no gate run"
    else:
        rep = gates[-1]["report"]
        if "crash" in rep: k = "checker crash"
        elif rep.get("all_pass"): k = "all five pass"
        else:
            g4 = rep.get("G4_repro_flips", {}); g5 = rep.get("G5_no_regression", {})
            k = f"warn: G4={g4.get('kind')} G5={'ok' if g5.get('pass', True) else 'fail'}"
        k += " /" + str(gates[-1].get("path"))
    grp[k][0] += 1; grp[k][1] += r["resolved"]
for k, (n, s) in sorted(grp.items(), key=lambda x: -x[1][0]):
    print(f"{n:3d} accepted, {s:2d} resolved ({s/n:.0%})  {k}")
# base precision for reference; and G4 ok overall
g4ok = [i for i, r in R.items() if r.get("patch") and any(e["event"] == "gate" and e["report"].get("G4_repro_flips", {}).get("kind") == "ok" for e in ev[i][-1:])]
print("last gate G4 ok:", len(g4ok), "resolved", sum(R[i]["resolved"] for i in g4ok))
