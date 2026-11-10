import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
import json, os, collections
from math import comb
EXP = _os.path.join(_ROOT, "results")
meta = {json.loads(l)["instance_id"]: json.loads(l) for l in open(_os.path.join(_ROOT, "benchmark", "tasks_exp100.jsonl"))}
R = {c: {(r := json.loads(l))["id"]: r for l in open(f"{EXP}/31b_{c}/results.jsonl")} for c in ["base", "kp", "gate2", "gate", "kp_gate"]}
def signp(w, l):
    n = w + l; k = min(w, l)
    return min(1, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1
def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n)) / d; h = z * ((p*(1-p)/n + z*z/(4*n*n)) ** .5) / d
    return c - h, c + h
def row(c, ids):
    v = R[c]; res = sum(v[i]["resolved"] for i in ids); sub = sum(bool(v[i]["patch"]) for i in ids)
    lo, hi = wilson(res, len(ids))
    return res, sub, sub - res, f"{c:8s} n={len(ids):3d} resolved={res:2d} [{lo:.2f},{hi:.2f}] submitted={sub:2d} wrong={sub-res:2d} precision={res/max(sub,1):.2f} coverage={sub/len(ids):.2f}"
ALL = sorted(meta); DEV = sorted(R["gate"]); HELD = sorted(set(ALL) - set(DEV))
for lab, ids, conds in (("ALL 100", ALL, ["base", "kp", "gate2"]), ("DEV 47", DEV, ["base", "kp", "gate", "kp_gate", "gate2"]), ("HELD 53", HELD, ["base", "kp", "gate2"])):
    print(f"\n== {lab}")
    for c in conds: print("  " + row(c, ids)[3])
    for c in conds[1:]:
        g = sum(R[c][i]["resolved"] and not R["base"][i]["resolved"] for i in ids); l = sum(R["base"][i]["resolved"] and not R[c][i]["resolved"] for i in ids)
        wb = sum(bool(R["base"][i]["patch"]) and not R["base"][i]["resolved"] for i in ids); wc = sum(bool(R[c][i]["patch"]) and not R[c][i]["resolved"] for i in ids)
        print(f"    {c} vs base: +{g} -{l} (sign p={signp(g,l):.2f}); wrong {wb}->{wc}")
# wrong patch reduction significance (paired: base wrong & c not wrong vs reverse)
for c in ["kp", "gate2"]:
    a = sum(bool(R["base"][i]["patch"]) and not R["base"][i]["resolved"] and not (bool(R[c][i]["patch"]) and not R[c][i]["resolved"]) for i in ALL)
    b = sum(not (bool(R["base"][i]["patch"]) and not R["base"][i]["resolved"]) and bool(R[c][i]["patch"]) and not R[c][i]["resolved"] for i in ALL)
    print(f"wrong-patch discordant {c}: base-only-wrong {a}, {c}-only-wrong {b}, sign p={signp(a,b):.4f}")
# by repo
print("\nby repo (resolved base/kp/gate2):")
rp = collections.defaultdict(list)
for i in ALL: rp[meta[i]["repo"].split("/")[1]].append(i)
for k, ids in sorted(rp.items(), key=lambda x: -len(x[1])):
    print(f"  {k:12s} n={len(ids):2d} " + " ".join(f"{c}={sum(R[c][i]['resolved'] for i in ids)}" for c in ["base", "kp", "gate2"]))
print("\npre/post 2025-02 (resolved):")
for lab, ids in (("pre", [i for i in ALL if meta[i]["created_at"] < "2025-02"]), ("post", [i for i in ALL if meta[i]["created_at"] >= "2025-02"])):
    print(f"  {lab:4s} n={len(ids):2d} " + " ".join(f"{c}={sum(R[c][i]['resolved'] for i in ids)}" for c in ["base", "kp", "gate2"]))
# union / oracle
u = sum(any(R[c][i]["resolved"] for c in ["base", "kp", "gate2"]) for i in ALL)
print("\nresolved by any of base/kp/gate2:", u)
# kp usage
for c in ["kp", "kp_gate"]:
    es = [json.loads(l) for l in open(f"{EXP}/31b_{c}/offline_events.jsonl")]
    q = [e for e in es if e["event"] == "kp_query"]
    t = {e["task"] for e in q}
    ids = ALL if c == "kp" else DEV
    print(f"{c}: kp queries {len(q)} in {len(t)}/{len(ids)} tasks; resolved with kp use {sum(R[c][i]['resolved'] for i in t if i in R[c])}/{len(t)}, without {sum(R[c][i]['resolved'] for i in ids if i not in t)}/{len(ids)-len(t)}")
# time & energy
pw = []
for l in open(f"{EXP}/gpu_power.csv"):
    try: pw.append(float(l.split(",")[1].strip().split()[0]))
    except Exception: pass
mp = sum(pw) / len(pw)
print(f"\nmean GPU power over run {mp:.0f} W ({len(pw)} samples, {len(pw)*30/3600:.1f} h)")
for c in ["base", "kp", "gate2"]:
    s = [R[c][i]["sec"] for i in ALL]; tot = sum(s); res = sum(R[c][i]["resolved"] for i in ALL)
    print(f"  {c:6s} mean {tot/len(s):.0f} s/task, total {tot/3600:.1f} h, ~{mp*tot/3.6e6:.2f} kWh, ~{mp*tot/3.6e6/max(res,1)*1000:.0f} Wh per resolved; median {sorted(s)[len(s)//2]:.0f}")
# outcome taxonomy
print("\noutcomes:")
for c in ["base", "kp", "gate2"]:
    print(f"  {c:6s}", dict(collections.Counter(("resolved" if R[c][i]["resolved"] else ("wrong patch" if R[c][i]["patch"] else "no patch")) + " | " + (R[c][i]["error"] or "")[:28] for i in ALL)))
