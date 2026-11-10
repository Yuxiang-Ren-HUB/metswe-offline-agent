"""Exploratory, beyond the frozen plan: why tasks end with no patch; server 500s (model emitted a malformed tool call) per condition."""
import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
import json, re, collections
from pathlib import Path
E = Path(_os.path.join(_ROOT, "results"))
dev = {json.loads(l)["id"] for l in open(E / "31b_gate/results.jsonl")}
pat = re.compile(r"InternalServerError|status code: 500|Internal Server Error|\b500\b.*(error|Error)")
print("condition: no-patch reasons | tasks with server-500 log lines, total lines, max in one task")
for c in ("base", "base_r2", "gate2", "gate2_r2", "gateprompt", "gate2sh"):
    R = [json.loads(l) for l in open(E / f"31b_{c}/results.jsonl")]
    why = collections.Counter()
    for r in R:
        if r.get("patch"): continue
        e = r.get("error") or ""
        why["timeout" if "session timeout" in e else "call-limit" if "tool call budget" in e else "no-submit" if "without calling" in e else (e[:20] or "gate/empty")] += 1
    cnt = {}
    for p in (E / f"31b_{c}/harness/logs").glob("*.log"):
        n = sum(1 for l in p.read_text(errors="ignore").splitlines() if pat.search(l))
        if n: cnt[p.stem] = n
    print(f"{c:11s}", dict(why), "|", len(cnt), sum(cnt.values()), max(cnt.values(), default=0))
