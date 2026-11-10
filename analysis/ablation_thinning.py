"""Exploratory, not in the frozen plan (added after the ablation results): is a condition better than dropping base's patches at
random down to the same number of submissions? Excess = resolved - submissions x base precision (two base runs pooled), per run.
Paired bootstrap over tasks, keeping every run of a task together. Also the per-run outcome table for the figure. CPU only."""
import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
import json
import random
from pathlib import Path

EXP = _os.path.join(_ROOT, "results")
OUT = Path(_os.path.join(_ROOT, "figures", "fig_ablation_data.json"))
L = lambda c: {(r := json.loads(l))["id"]: r for l in open(f"{EXP}/31b_{c}/results.jsonl")}
R = {c: L(c) for c in ("base", "base_r2", "gate2", "gate2_r2", "gateprompt", "gate2sh")}
dev = set(L("gate"))
ALL = sorted(R["base"])
HELD = [i for i in ALL if i not in dev]
BASE = ("base", "base_r2")
sub = lambda r: bool(r.get("patch"))
res = lambda r: bool(r["resolved"])
S = lambda cs, f, ids: sum(f(R[c][i]) for c in cs for i in ids)


def excess(cs, ids):
    p = S(BASE, res, ids) / S(BASE, sub, ids)
    return (S(cs, res, ids) - S(cs, sub, ids) * p) / len(cs)


def report(lab, cs, ids):
    random.seed(0)
    v = sorted(excess(cs, [random.choice(ids) for _ in ids]) for _ in range(10000))
    k = S(cs, sub, ids) / len(cs); r = S(cs, res, ids) / len(cs); p = S(BASE, res, ids) / S(BASE, sub, ids)
    print(f"  {lab:22s} per run: submitted {k:5.1f} resolved {r:5.1f} | random thinning expects {k*p:5.1f} | excess {excess(cs, ids):+5.1f} "
          f"(95% {v[250]:+.1f} to {v[9749]:+.1f}) | submitted per resolved {k/r:.1f}")


for name, ids in (("all 100 tasks", ALL), ("held-out 53 tasks", HELD)):
    print(name, f"(base precision pooled {S(BASE, res, ids)}/{S(BASE, sub, ids)})")
    report("gate v2 (two runs)", ("gate2", "gate2_r2"), ids)
    report("gate v2 run 1", ("gate2",), ids)
    report("gate v2 run 2", ("gate2_r2",), ids)
    report("A gateprompt", ("gateprompt",), ids)
    report("B gate2sh", ("gate2sh",), ids)

rows = [["Base, run 1", "base"], ["Base, run 2", "base_r2"], ["Prompt only (A)", "gateprompt"], ["Gate v2, run 1", "gate2"],
        ["Gate v2, run 2", "gate2_r2"], ["Gate v2 + shell fix (B)", "gate2sh"]]
data = [{"label": a, "resolved": S((c,), res, ALL), "failing": S((c,), lambda r: sub(r) and not res(r), ALL),
         "none": S((c,), lambda r: not sub(r), ALL)} for a, c in rows]
OUT.write_text(json.dumps(data, indent=1), newline="\n")
print(data)

total = 0
for p in sorted(Path(EXP).glob("31b_*/results.jsonl")):
    h = sum(json.loads(l)["sec"] for l in open(p)) / 3600; total += h; print(f"  {p.parent.name}: {h:.1f} h")
print(f"agent-run hours on kept results: {total:.0f}")
