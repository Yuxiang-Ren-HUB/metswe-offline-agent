"""Replicate run (run3.sh: base_r2, gate2_r2) against run 1, for the offline paper (11/7). CPU only.

Prints every number the paper uses about the second run and writes the cache behind Figure 2 (fig2_data.json).
"""
import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
import collections
import json
import random
from math import comb
from pathlib import Path

EXP = _os.path.join(_ROOT, "results")
FIG2 = Path(_os.path.join(_ROOT, "figures", "fig2_data.json"))
L = lambda c: {(r := json.loads(l))["id"]: r for l in open(f"{EXP}/31b_{c}/results.jsonl")}
R = {c: L(c) for c in ["base", "kp", "gate2", "gate", "base_r2", "gate2_r2"]}
ALL = sorted(R["base"]); DEV = sorted(R["gate"]); HELD = sorted(set(ALL) - set(DEV))
assert all(sorted(R[c]) == ALL for c in ["kp", "gate2", "base_r2", "gate2_r2"])
RUNS = {"base": ("base", "base_r2"), "gate2": ("gate2", "gate2_r2")}


def signp(w, l):
    n = w + l; k = min(w, l)
    return min(1, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1


sub = lambda r: bool(r.get("patch"))
res = lambda r: bool(r["resolved"])
wrong = lambda r: sub(r) and not res(r)


def end(r):
    e = str(r.get("error") or "")
    if "InternalServerError" in e or "APIConnection" in e:
        return "server error"
    if "tool call budget" in e:
        return "call limit"
    if "timeout" in e:
        return "time limit"
    return "other" if e else "finished"


print("== per run, MetSWE-100")
for c in ["base", "base_r2", "kp", "gate2", "gate2_r2"]:
    v = R[c]; s = sum(sub(v[i]) for i in ALL); r = sum(res(v[i]) for i in ALL)
    ends = collections.Counter(end(v[i]) for i in ALL)
    t = sum(v[i].get("sec") or 0 for i in ALL) / len(ALL)
    print(f"  {c:9s} resolved {r:2d} submitted {s:2d} wrong {s-r:2d} none {100-s:2d} precision {r/s:.2f} "
          f"time/task {t:.0f}s ends {dict(ends)}")

print("\n== base vs gate v2, paired, per round and pooled")
for lab, ids in (("ALL", ALL), ("HELD", HELD)):
    for k in (0, 1):
        b, g = R[RUNS["base"][k]], R[RUNS["gate2"][k]]
        ww = sum(wrong(b[i]) and not wrong(g[i]) for i in ids), sum(wrong(g[i]) and not wrong(b[i]) for i in ids)
        rr = sum(res(b[i]) and not res(g[i]) for i in ids), sum(res(g[i]) and not res(b[i]) for i in ids)
        wb, wg = sum(wrong(b[i]) for i in ids), sum(wrong(g[i]) for i in ids)
        xb, xg = sum(res(b[i]) for i in ids), sum(res(g[i]) for i in ids)
        print(f"  {lab} round {k+1}: wrong {wb}->{wg} discordant {ww[0]}:{ww[1]} p={signp(*ww):.4f} | "
              f"resolved {xb} vs {xg} discordant base-only {rr[0]} gate-only {rr[1]} p={signp(*rr):.2f}")
    # pooled: per task, count over the two runs
    cnt = lambda f, c, i: f(R[RUNS[c][0]][i]) + f(R[RUNS[c][1]][i])
    for name, f in (("wrong", wrong), ("resolved", res)):
        tb = sum(cnt(f, "base", i) for i in ids); tg = sum(cnt(f, "gate2", i) for i in ids)
        hi = sum(cnt(f, "base", i) > cnt(f, "gate2", i) for i in ids); lo = sum(cnt(f, "base", i) < cnt(f, "gate2", i) for i in ids)
        print(f"  {lab} pooled {name}: base {tb} gate {tg}; tasks base>gate {hi}, gate>base {lo}, p={signp(hi, lo):.5f}")
    sb = sum(cnt(sub, "base", i) for i in ids); sg = sum(cnt(sub, "gate2", i) for i in ids)
    rb = sum(cnt(res, "base", i) for i in ids); rg = sum(cnt(res, "gate2", i) for i in ids)
    print(f"  {lab} pooled precision: base {rb}/{sb}={rb/sb:.2f} gate {rg}/{sg}={rg/sg:.2f}")

# paired bootstrap over tasks, both runs pooled
random.seed(0); B = 10000; dw, dr, dp = [], [], []
for _ in range(B):
    s = [random.choice(ALL) for _ in ALL]
    agg = {c: [sum(f(R[r][i]) for r in RUNS[c] for i in s) for f in (sub, res)] for c in RUNS}
    (sb, rb), (sg, rg) = agg["base"], agg["gate2"]
    dw.append((sg - rg) - (sb - rb)); dr.append(rg - rb); dp.append(rg / sg - rb / sb)
q = lambda a: (sorted(a)[int(.025 * B)], sorted(a)[int(.975 * B)])
print("  pooled paired bootstrap 95%% CI (two runs summed): wrong %d..%d | resolved %d..%d | precision %.3f..%.3f"
      % (*q(dw), *q(dr), *q(dp)))

print("\n== run-to-run agreement: same condition twice vs different conditions in one round")
for c, (r1, r2) in RUNS.items():
    a, b = R[r1], R[r2]
    both = sum(res(a[i]) and res(b[i]) for i in ALL); o1 = sum(res(a[i]) and not res(b[i]) for i in ALL)
    o2 = sum(res(b[i]) and not res(a[i]) for i in ALL)
    wd = sum(wrong(a[i]) != wrong(b[i]) for i in ALL)
    print(f"  {c}: resolved both {both}, run1 only {o1}, run2 only {o2}, ever {both+o1+o2}; "
          f"resolved-discordant {o1+o2}; wrong-discordant {wd}")
for k in (0, 1):
    a, b = R[RUNS["base"][k]], R[RUNS["gate2"][k]]
    print(f"  base vs gate2 round {k+1}: resolved-discordant {sum(res(a[i]) != res(b[i]) for i in ALL)}; "
          f"wrong-discordant {sum(wrong(a[i]) != wrong(b[i]) for i in ALL)}")
a, b = R["base"], R["kp"]
print(f"  base vs kp round 1: resolved-discordant {sum(res(a[i]) != res(b[i]) for i in ALL)}")
five = ["base", "base_r2", "kp", "gate2", "gate2_r2"]
print("  resolved by any of the five 100-task runs:", sum(any(res(R[c][i]) for c in five) for i in ALL),
      "| by all five:", sum(all(res(R[c][i]) for c in five) for i in ALL))
hist = collections.Counter(sum(res(R[c][i]) for c in five) for i in ALL)
print("  tasks by number of the five runs that resolve them:", dict(sorted(hist.items())))

print("\n== cost of the gate: call limit, submit attempts, losses")
for c in ["base", "base_r2", "gate2", "gate2_r2"]:
    v = R[c]; cap = [i for i in ALL if end(v[i]) == "call limit"]
    print(f"  {c:9s} hits call limit on {len(cap)} tasks; mean tool calls {sum(v[i]['tool_calls'] or 0 for i in ALL)/100:.1f}")
for k in (0, 1):
    g, b = R[RUNS["gate2"][k]], R[RUNS["base"][k]]
    ev = [json.loads(l) for l in open(f"{EXP}/31b_{RUNS['gate2'][k]}/offline_events.jsonl")]
    abst = {e["task"]: e["reason"] for e in ev if e["event"] == "abstain"}
    att = collections.Counter(e["task"] for e in ev if e["event"] == "gate" and e["path"] == "submit")
    rej = collections.Counter(e["task"] for e in ev if e["event"] == "gate" and e["path"] == "submit" and e["hard"])
    cap = [i for i in ALL if end(g[i]) == "call limit"]
    print(f"  round {k+1}: gate submit calls {sum(att.values())} on {len(att)} tasks, {sum(rej.values())} rejected; "
          f"call-limit tasks {len(cap)}: base resolved {sum(res(b[i]) for i in cap)} of them, "
          f"gate outcome {dict(collections.Counter('resolved' if res(g[i]) else 'wrong' if sub(g[i]) else ('abstained' if i in abst else 'no patch') for i in cap))}")
    lost = [i for i in ALL if res(b[i]) and not res(g[i])]
    why = collections.Counter()
    for i in lost:
        if sub(g[i]):
            why["submitted a wrong patch"] += 1
        elif i in abst:
            why["gate rejected the edit (" + end(g[i]) + ")"] += 1
        else:
            why["no edit, " + end(g[i])] += 1
    print(f"    base resolved, gate v2 did not: {len(lost)} -> {dict(why)}")
    held_abst = [i for i in HELD if i in abst]
    print(f"    held-out abstentions {len(held_abst)}, of which base resolved {sum(res(b[i]) for i in held_abst)}")

print("\n== by repository, resolved (base r1/r2, gate2 r1/r2)")
meta = {json.loads(l)["instance_id"]: json.loads(l) for l in open(_os.path.join(_ROOT, "benchmark", "tasks_exp100.jsonl"))}
rp = collections.defaultdict(list)
for i in ALL:
    rp[meta[i]["repo"].split("/")[1]].append(i)
for name, ids in sorted(rp.items(), key=lambda x: -len(x[1])):
    print(f"  {name:12s} n={len(ids):2d} " + " ".join(f"{c}={sum(res(R[c][i]) for i in ids)}" for c in ["base", "base_r2", "gate2", "gate2_r2"]))
for lab, ids in (("pre", [i for i in ALL if meta[i]["created_at"] < "2025-02"]), ("post", [i for i in ALL if meta[i]["created_at"] >= "2025-02"])):
    print(f"  {lab:4s} n={len(ids):2d} " + " ".join(f"{c}={sum(res(R[c][i]) for i in ids)}" for c in ["base", "base_r2"]))

# Figure 2 cache: per condition, tasks by (outcome run 1, outcome run 2)
oc = lambda r: "resolved" if res(r) else "wrong" if sub(r) else "none"
fig2 = {}
for c, (r1, r2) in RUNS.items():
    fig2[c] = {f"{x}|{y}": sum(oc(R[r1][i]) == x and oc(R[r2][i]) == y for i in ALL)
               for x in ("resolved", "wrong", "none") for y in ("resolved", "wrong", "none")}
    fig2[c]["runs"] = [{o: sum(oc(R[r][i]) == o for i in ALL) for o in ("resolved", "wrong", "none")} for r in (r1, r2)]
FIG2.write_text(json.dumps(fig2, indent=1))
print("\nfig2 cache:", json.dumps(fig2))
