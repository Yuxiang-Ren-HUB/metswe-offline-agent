"""Where gate v2's tool calls go (11/7): reproduction-script work, the /tmp write_file refusals, submit attempts and
calls before the first source edit, per run, from the harness traces. CPU only."""
import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
import ast
import json
import statistics
from pathlib import Path

EXP = Path(_os.path.join(_ROOT, "results"))
TEST = ("test", "conftest")


def calls(trace):
    out = []
    for s in json.load(open(trace))["steps"]:
        tc = s.get("tool_calls")
        if not tc:
            continue
        tc = ast.literal_eval(tc) if isinstance(tc, str) else tc
        obs = str(s.get("observation") or "")
        for c in tc:
            out.append((c["function_name"], c.get("arguments") or {}, obs))
    return out


def kind(fn, args, obs):
    blob = json.dumps(args)
    if fn == "submit_patch":
        return "submit"
    if "repro.py" in blob:
        return "repro_refused" if fn == "write_file" and "escapes workspace root" in obs else "repro"
    if fn in ("edit_file", "write_file"):
        p = str(args.get("path") or args.get("file_path") or "")
        return "test_edit" if any(t in p for t in TEST) else "source_edit"
    return "other"


def results(run):
    return {(r := json.loads(l))["id"]: r for l in open(EXP / f"31b_{run}" / "results.jsonl")}


for run in ("base", "base_r2", "gate2", "gate2_r2"):
    R = results(run)
    per = {}
    for tid in R:
        f = EXP / f"31b_{run}" / "harness" / "traces" / f"trace_{tid}.json"
        if f.exists():
            per[tid] = [kind(*c) for c in calls(f)]
    n = len(per)
    tot = lambda k: sum(v.count(k) for v in per.values())
    first = [v.index("source_edit") + 1 for v in per.values() if "source_edit" in v]
    no_edit = sum("source_edit" not in v for v in per.values())
    cap = [t for t in per if "tool call budget" in str(R[t].get("error") or "")]
    capmean = lambda k: sum(per[t].count(k) for t in cap) / max(len(cap), 1)
    print(f"{run:9s} traces {n}: calls/task {sum(map(len, per.values()))/n:.1f} | repro {tot('repro')/n:.1f} "
          f"(+refused write {tot('repro_refused')/n:.2f}) | submit {tot('submit')/n:.2f} | "
          f"first source edit at call {statistics.median(first):.0f} (median) | no source edit {no_edit}")
    if cap:
        print(f"          call-limit tasks {len(cap)}: repro {capmean('repro'):.1f}, refused {capmean('repro_refused'):.2f}, "
              f"submit {capmean('submit'):.1f}, source edits {capmean('source_edit'):.1f}, "
              f"no source edit {sum('source_edit' not in per[t] for t in cap)}")
