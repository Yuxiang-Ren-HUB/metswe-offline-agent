import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
import json
EXP = _os.path.join(_ROOT, "results")
L = lambda c: {(r := json.loads(l))["id"]: r for l in open(f"{EXP}/31b_{c}/results.jsonl")}
b, g = L("base"), L("gate2")
bud = [i for i, r in g.items() if "tool call budget" in (r.get("error") or "")]
print("gate2 budget tasks", len(bud), "base resolved among them:", [i for i in bud if b[i]["resolved"]], "base no patch:", sum(not b[i].get("patch") for i in bud))
print("lost:", [(i, (g[i].get("error") or "")[:30], len(g[i].get("patch") or "")) for i in g if b[i]["resolved"] and not g[i]["resolved"]])
T = [json.loads(l) for l in open(_os.path.join(_ROOT, "benchmark", "tasks_exp100.jsonl"))]
rebench = {1908, 1928, 1943, 1956, 1977, 2006, 2007, 2066, 2073, 2239, 2270, 2271, 2272, 2398, 2412, 2422, 2653, 2674, 2691, 2808, 2852, 2999, 3024, 3056, 3103, 3188, 3242, 3307, 3323, 3324, 3347, 3437, 985, 1934, 2629, 2728}
mp = [(t["instance_id"], t["created_at"][:10]) for t in T if t["repo"] == "Unidata/MetPy"]
print("metpy tasks", mp)
print("metpy issue/PR numbers in rebench:", [i for i, _ in mp if int(i.split("__")[1]) in rebench])
