"""Ablations A (gateprompt: gate v2's prompt, gate off) and B (gate2sh: gate v2, reproduction written via the shell),
against base and gate v2 (two runs each). Written 11/7 before any ablation result was inspected; see
paper/ablation_analysis_plan.md. Works on partial results (only tasks present in every run are compared). CPU only."""
import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
import json
import os
import random
import statistics
import sys
from math import comb
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from call_budget import calls, kind  # noqa: E402  (prints its own table on import)

EXP = _os.path.join(_ROOT, "results")
L = lambda c: {(r := json.loads(l))["id"]: r for l in open(f"{EXP}/31b_{c}/results.jsonl")}
RUNS = ["base", "base_r2", "gate2", "gate2_r2", "gateprompt", "gate2sh"]
# ABLATION_DRYRUN=1 substitutes existing runs for the ablations, to test this script without reading their results
DRY = {"gateprompt": "base_r2", "gate2sh": "gate2_r2"} if os.environ.get("ABLATION_DRYRUN") == "1" else {}
R = {c: L(DRY.get(c, c)) for c in RUNS}
ALL = sorted(set.intersection(*(set(R[c]) for c in RUNS)))
DEV = set(L("gate"))
HELD = [i for i in ALL if i not in DEV]
print(f"\n== tasks present in all runs: {len(ALL)} (held-out {len(HELD)})")

sub = lambda r: bool(r.get("patch"))
res = lambda r: bool(r["resolved"])
fail = lambda r: sub(r) and not res(r)
cap = lambda r: "tool call budget" in str(r.get("error") or "")


def signp(w, l):
    n = w + l; k = min(w, l)
    return min(1, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1


print("\n== per run")
for c in RUNS:
    v = R[c]; n = len(ALL)
    s = sum(sub(v[i]) for i in ALL); r = sum(res(v[i]) for i in ALL)
    print(f"  {c:10s} resolved {r:3d} failing {s-r:3d} none {n-s:3d} coverage {s/n:.2f} precision {r/max(s,1):.2f} "
          f"time {statistics.mean(v[i]['sec'] for i in ALL):.0f}s call-limit {sum(cap(v[i]) for i in ALL)} | "
          f"held-out resolved {sum(res(v[i]) for i in HELD)} failing {sum(fail(v[i]) for i in HELD)}")

def boot(a, b, n=10000):
    """Paired bootstrap over tasks of (a minus b) in failing patches and resolutions; 95% percentile interval."""
    rng = random.Random(0)
    df, dr = [], []
    for _ in range(n):
        s = [rng.choice(ALL) for _ in ALL]
        df.append(sum(fail(R[a][i]) - fail(R[b][i]) for i in s))
        dr.append(sum(res(R[a][i]) - res(R[b][i]) for i in s))
    q = lambda v: (sorted(v)[int(.025 * n)], sorted(v)[int(.975 * n)])
    return (*q(df), *q(dr))


print("\n== paired (sign tests and paired bootstrap over tasks)")
for a, refs in (("gateprompt", ["base", "base_r2", "gate2", "gate2_r2"]), ("gate2sh", ["gate2", "gate2_r2"])):
    for b in refs:
        fw = sum(fail(R[b][i]) and not fail(R[a][i]) for i in ALL), sum(fail(R[a][i]) and not fail(R[b][i]) for i in ALL)
        rw = sum(res(R[a][i]) and not res(R[b][i]) for i in ALL), sum(res(R[b][i]) and not res(R[a][i]) for i in ALL)
        ci = boot(a, b)
        print(f"  {a} vs {b:9s}: failing only-{b} {fw[0]} / only-{a} {fw[1]} (p={signp(*fw):.4f}) | "
              f"resolved only-{a} {rw[0]} / only-{b} {rw[1]} (p={signp(*rw):.3f}) | "
              f"95% CI {a} minus {b}: failing {ci[0]}..{ci[1]}, resolved {ci[2]}..{ci[3]}")

print("\n== mechanism (traces and gate events)")
for c in RUNS:
    per = {}
    for i in ALL:
        f = Path(f"{EXP}/31b_{DRY.get(c, c)}/harness/traces/trace_{i}.json")
        if f.exists():
            per[i] = [kind(*x) for x in calls(f)]
    n = len(per)
    first = [v.index("source_edit") + 1 for v in per.values() if "source_edit" in v]
    wrote = sum(("repro" in v or "repro_refused" in v) for v in per.values())
    line = (f"  {c:10s} traces {n}: repro calls/task {sum(v.count('repro') for v in per.values())/n:.2f}, "
            f"refused writes/task {sum(v.count('repro_refused') for v in per.values())/n:.2f}, "
            f"tasks touching repro.py {wrote}, first source edit (median) {statistics.median(first):.0f}")
    ev_path = Path(f"{EXP}/31b_{DRY.get(c, c)}/offline_events.jsonl")
    if ev_path.exists():
        ev = [json.loads(l) for l in open(ev_path)]
        ev = [e for e in ev if e.get("task") in set(ALL)]
        line += (f" | gate rejections {sum(1 for e in ev if e['event'] == 'gate' and e['path'] == 'submit' and e['hard'])}, "
                 f"abstentions {len({e['task'] for e in ev if e['event'] == 'abstain'})}")
    print(line)
