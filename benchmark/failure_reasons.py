"""Group failed validation records by cause (missing module, test failures, patch apply, ...)."""
import collections
import json
import re
import sys
from pathlib import Path

repos = set(sys.argv[1:])
c, ex = collections.Counter(), {}
for line in (Path(__file__).resolve().parent / "validation.jsonl").read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    if r["valid"] or (repos and r["repo"] not in repos):
        continue
    if r["empty"]["resolved"]:
        k = "empty patch already passes"
    else:
        g = r.get("gold1", {})
        t, e = g.get("tail", "") or "", str(g.get("error") or "")
        m = re.search(r"No module named '([^']+)'", t) or re.search(r"cannot import name '([^']+)'", t)
        if m:
            k = "import: " + m.group(0)
        elif "apply" in e.lower():
            k = "patch apply"
        elif re.search(r"\d+ failed", t):
            k = "test failures"
        elif re.search(r"\d+ errors?", t):
            k = "collection/setup errors"
        elif g.get("exit") in (124, 137) or "timed out" in (t + e).lower():
            k = "timeout"
        else:
            k = "other: " + (e or t[-100:]).replace("\n", " ")[:100]
    c[(r["repo"].split("/")[1], k)] += 1
    ex.setdefault((r["repo"].split("/")[1], k), r["instance_id"] + (" post" if r["post_cutoff"] else " pre"))
for (repo, k), v in sorted(c.items(), key=lambda x: (x[0][0], -x[1])):
    print(f"{repo:12s} {v:3d}  {k}   e.g. {ex[(repo, k)]}")
