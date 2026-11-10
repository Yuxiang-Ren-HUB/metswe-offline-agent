"""Exploratory domain-specific vs generic comparison (11/7), with the five borderline labels counted three ways:
as domain-specific, excluded, or generic. Also within Satpy, the only repository with many tasks of both kinds.
Labels: mining/task_types_reviewed.jsonl (LLM-assigned, LLM-reviewed). Two runs of base and gate v2 pooled. CPU only."""
import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
import json
from math import comb

T = {(t := json.loads(l))["instance_id"]: t for l in open(_os.path.join(_ROOT, "benchmark", "task_types_reviewed.jsonl"), encoding="utf-8")}
EXP = _os.path.join(_ROOT, "results")
L = lambda c: {(r := json.loads(l))["id"]: r for l in open(f"{EXP}/31b_{c}/results.jsonl")}
R = {c: L(c) for c in ("base", "base_r2", "gate2", "gate2_r2")}
B, G = ("base", "base_r2"), ("gate2", "gate2_r2")
sub = lambda r: bool(r.get("patch")); res = lambda r: bool(r["resolved"]); fail = lambda r: sub(r) and not res(r)
cnt = lambda f, rs, i: sum(f(R[r][i]) for r in rs)


def signp(w, l):
    n = w + l; k = min(w, l)
    return min(1, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1


def row(lab, ids):
    n = 2 * len(ids)
    fb = sum(cnt(fail, B, i) for i in ids); fg = sum(cnt(fail, G, i) for i in ids)
    hi = sum(cnt(fail, B, i) > cnt(fail, G, i) for i in ids); lo = sum(cnt(fail, B, i) < cnt(fail, G, i) for i in ids)
    rb = sum(cnt(res, B, i) for i in ids)
    print(f"  {lab:28s} n={len(ids):3d}: failing-patch rate {100*fb/n:5.1f}% -> {100*fg/n:5.1f}% (tasks {hi}:{lo}, p={signp(hi, lo):.4f}); "
          f"base resolved {rb}/{n} = {100*rb/n:.0f}%")


border = {i for i in T if T[i]["borderline"]}
dom = {i for i in T if T[i]["domain_specific"]}
for name, d, g in (("borderline as domain", dom, set(T) - dom),
                   ("borderline excluded", dom - border, set(T) - dom),
                   ("borderline as generic", dom - border, (set(T) - dom) | border)):
    print(name)
    row("domain-specific", sorted(d)); row("generic", sorted(g))
print("within Satpy only (borderline as domain)")
sat = {i for i in T if T[i]["repo"] == "pytroll/satpy"}
row("Satpy domain-specific", sorted(sat & dom)); row("Satpy generic", sorted(sat - dom))
print("non-Satpy, non-xarray (six smaller libraries)")
small = {i for i in T if T[i]["repo"] not in ("pytroll/satpy", "pydata/xarray")}
row("small libs domain-specific", sorted(small & dom)); row("small libs generic", sorted(small - dom))
row("xarray (all generic)", sorted(i for i in T if T[i]["repo"] == "pydata/xarray"))
