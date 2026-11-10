"""Final consistency pass: re-verify every currently valid task against the final images.

Images changed between validation rounds (packages added, pytest<8 for MetPy, pandas<3 for xarray), so
records from earlier rounds may not hold for the final environment. This moves validation.jsonl aside,
keeps the earlier records for reference, and re-verifies the union of valid tasks from scratch.
Run inside WSL with /opt/g4env/bin/python.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
cur = HERE / "validation.jsonl"
prev = HERE / "validation_rounds.jsonl"

records = {}
for line in cur.read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    records[r["instance_id"]] = r
valid = sorted(i for i, r in records.items() if r["valid"])
print(f"{len(valid)} valid tasks to re-verify", flush=True)

shutil.copy(cur, prev)  # keep every earlier round for the record
cur.write_text("", encoding="utf-8")
subprocess.run([sys.executable, str(HERE / "validate_tasks.py"), "verify", "--ids", ",".join(valid),
                "--concurrency", sys.argv[1] if len(sys.argv) > 1 else "4"], check=True)
