"""What gate v2's hard rejections rested on (11/7). Per rejected attempt: G3 split into syntax errors (introduced by the
patch, since the file parsed at baseline) and import failures (not compared with baseline); G4 'fails_with_patch' split
by how the agent's reproduction failed: AssertionError (the asserted behaviour is still wrong), another exception
(possibly the script or the environment), or a signal/timeout. CPU only."""
import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
import collections
import json
import re

EXP = _os.path.join(_ROOT, "results")
EXC = re.compile(r"^(?:[\w.]+\.)?(\w+(?:Error|Exception|Exit))\b", re.M)


def g4_kind(detail):
    m = re.search(r"exit (-?\d+)", detail)
    code = int(m.group(1)) if m else None
    if code is not None and (code < 0 or code in (124, 137)) or "timed out" in detail:
        return "signal or timeout"
    exc = EXC.findall(detail)
    if not exc:
        return "behaviour check (scripted check failed, no traceback)"
    return "behaviour check (AssertionError)" if exc[-1] == "AssertionError" else "other exception: " + exc[-1]


for run in ("gate2", "gate2_r2"):
    ev = [json.loads(l) for l in open(f"{EXP}/31b_{run}/offline_events.jsonl")]
    hard = [e for e in ev if e["event"] == "gate" and e["hard"]]
    c = collections.Counter()
    tasks = collections.defaultdict(set)
    for e in hard:
        for h in e["hard"]:
            d = e["report"][h]["detail"]
            if h == "G3_compiles":
                k = "G3 syntax error" if "SyntaxError" in d else "G3 import failure (no baseline comparison)"
            elif h == "G4_repro_flips":
                k = "G4 " + g4_kind(d)
            else:
                k = h
            c[k] += 1
            tasks[k].add(e["task"])
    print(f"== {run}: {len(hard)} rejected attempts on {len({e['task'] for e in hard})} tasks")
    for k, v in sorted(c.items()):
        print(f"  {k:55s} attempts {v:2d}  tasks {len(tasks[k]):2d}  {sorted(tasks[k])[:6]}")

tot = collections.Counter()
for run in ("gate2", "gate2_r2"):
    for e in (json.loads(l) for l in open(f"{EXP}/31b_{run}/offline_events.jsonl")):
        if e["event"] == "gate" and "G4_repro_flips" in e["hard"]:
            k = g4_kind(e["report"]["G4_repro_flips"]["detail"])
            tot["behaviour check" if k.startswith("behaviour") else "other exception" if k.startswith("other") else k] += 1
print("G4 hard rejections over both runs:", dict(tot), "total", sum(tot.values()))
