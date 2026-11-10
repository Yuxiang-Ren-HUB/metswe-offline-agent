"""Remove validation records of a repository whose gold patch failed, so they get re-verified."""
import json
import sys
from pathlib import Path

repo = sys.argv[1]
path = Path(__file__).resolve().parent / "validation.jsonl"
keep, dropped = [], 0
for line in path.read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    if r["repo"] == repo and not r["valid"] and not r["empty"]["resolved"]:
        dropped += 1
        continue
    keep.append(line)
path.write_text("\n".join(keep) + "\n", encoding="utf-8")
print(f"dropped {dropped} failed records of {repo}")
