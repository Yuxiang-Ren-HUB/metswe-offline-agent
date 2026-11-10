"""CPU-only supplementary analyses for the offline paper (11/5)."""
import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
import json, os, re, random, sys, collections
sys.path.insert(0, _os.path.join(_ROOT, "agent", "skills", "presubmit-check", "scripts"))
import presubmit_check as pc
EXP = _os.path.join(_ROOT, "results")
L = lambda c: {(r := json.loads(l))["id"]: r for l in open(f"{EXP}/31b_{c}/results.jsonl")}
R = {c: L(c) for c in ["base", "kp", "gate2", "gate", "kp_gate"]}
ALL = sorted(R["base"]); DEV = sorted(R["gate"])
sub = lambda r: bool(r.get("patch"))

print("== (a) random abstention at gate2's coverage, and paired bootstrap")
b, g = R["base"], R["gate2"]
nb = sum(sub(b[i]) for i in ALL); rb = sum(b[i]["resolved"] for i in ALL)
ng = sum(sub(g[i]) for i in ALL); rg = sum(g[i]["resolved"] for i in ALL)
print(f"base keeps {nb} patches ({rb} right). Random abstention down to {ng}: expected right {rb*ng/nb:.1f}, wrong {ng-rb*ng/nb:.1f}, precision {rb/nb:.2f}")
print(f"gate2: {ng} patches, {rg} right, {ng-rg} wrong, precision {rg/ng:.2f}")
# probability that random abstention from base's 84 keeps >= rg right among ng: impossible beyond rb; report hypergeometric for keeping all 19 with 63
random.seed(0); B = 10000; dp = []; dw = []; dr = []
for _ in range(B):
    s = [random.choice(ALL) for _ in ALL]
    sb = sum(sub(b[i]) for i in s); sg = sum(sub(g[i]) for i in s)
    xb = sum(b[i]["resolved"] for i in s); xg = sum(g[i]["resolved"] for i in s)
    dp.append(xg / max(sg, 1) - xb / max(sb, 1)); dw.append((sg - xg) - (sb - xb)); dr.append(xg - xb)
q = lambda a: (sorted(a)[int(.025 * B)], sorted(a)[int(.975 * B)])
print("bootstrap 95%% CI: precision diff %.3f..%.3f | wrong-patch diff %d..%d | resolved diff %d..%d" % (*q(dp), *q(dw), *q(dr)))

print("\n== coverage / precision per condition")
for lab, ids, cs in (("ALL", ALL, ["base", "kp", "gate2"]), ("DEV", DEV, ["base", "kp", "gate", "kp_gate", "gate2"])):
    for c in cs:
        n = sum(sub(R[c][i]) for i in ids); r = sum(R[c][i]["resolved"] for i in ids)
        print(f"  {lab} {c:8s} coverage {n/len(ids):.2f} precision {r/max(n,1):.2f} resolved {r}")

print("\n== (b) post-hoc static filter on base's final patches (G1 + G2 from the patch alone)")
def files(p): return sorted(set(re.findall(r"^diff --git a/(\S+) b/", p, re.M)))
for c in ["base", "kp"]:
    cnt = collections.Counter()
    for i in ALL:
        r = R[c][i]
        if not sub(r): continue
        fs = files(r["patch"])
        ok1, _ = pc.gate_files(fs); ok2, _ = pc.gate_tests(fs)
        src = [f for f in fs if not pc.is_protected(f) and not pc.JUNK.search(f) and not pc.is_scratch(f)]
        kind = "fine" if ok1 and ok2 else ("no source change" if not src else "junk/test files beside source")
        cnt[(kind, r["resolved"])] += 1
    print(" ", c, dict(cnt))

print("\n== (c) API-misuse errors seen in tool outputs (base vs kp)")
PAT = {
    "AttributeError: no attribute": re.compile(r"AttributeError: [^\n]*has no attribute"),
    "TypeError: unexpected kwarg": re.compile(r"TypeError: [^\n]*unexpected keyword argument"),
    "TypeError: missing/too many args": re.compile(r"TypeError: [^\n]*(missing \d+ required|takes \d+ positional|positional argument)"),
    "ImportError: cannot import name": re.compile(r"ImportError: cannot import name"),
    "ModuleNotFoundError": re.compile(r"ModuleNotFoundError: No module named"),
}
def outputs(t):
    for s in t["steps"]:
        obs = s.get("observation")
        if obs: yield json.dumps(obs)
for c in ["base", "kp", "gate2"]:
    per = collections.Counter(); tasks_any = 0; res_any = 0; n = 0
    for i in ALL:
        p = f"{EXP}/31b_{c}/harness/traces/trace_{i}.json"
        if not os.path.exists(p): continue
        n += 1
        text = "\n".join(outputs(json.load(open(p)))).replace("\n", "\n")
        hit = {k for k, rx in PAT.items() if rx.search(text)}
        per.update(hit)
        if hit:
            tasks_any += 1; res_any += R[c][i]["resolved"]
    print(f"  {c:6s} traces {n}: tasks with >=1 API-type error {tasks_any} (resolved {res_any}); by type {dict(per)}")
