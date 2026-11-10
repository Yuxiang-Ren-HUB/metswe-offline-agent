"""Check MetSWE tasks with the official grader: the empty patch must fail and the gold patch must pass (WSL, /opt/g4env).

  python verify_demo.py --ids pyart__1894,pyart__1895 --out /tmp/metswe_demo.jsonl

Needs the repository's image (met-sandbox-<repo>:warm, see env/) and the task snapshots, which `validate_tasks.py
snapshot --ids ...` creates from GitHub. Unlike validate_tasks.py it reads the final task list, never touches the
validation records and writes only to --out. Each task runs the empty patch once and the gold patch once, air-gapped.
"""
import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from adk_submission import ModelRegistry
from swegemma.config import EvalConfig
from swegemma.harness.verification import verify_task
from swegemma.models.task import Task
from swegemma.sandbox.docker import ContainerConfig, ContainerManager

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--ids", required=True, help="comma-separated instance ids from tasks_final.jsonl")
ap.add_argument("--out", required=True)
ap.add_argument("--snapshots", default=os.environ.get("METSWE_SNAPSHOTS", "/opt/offline/snapshots"))
ap.add_argument("--wheels", default=os.environ.get("METSWE_EMPTY_WHEELS", "/opt/offline/empty_wheels"),
                help="an empty directory: keeps the competition's own wheels out of these images")
a = ap.parse_args()
out = Path(a.out)
assert not out.exists(), f"{out} exists"
Path(a.wheels).mkdir(parents=True, exist_ok=True)
tasks = {(t := json.loads(l))["instance_id"]: t for l in (HERE / "tasks_final.jsonl").read_text(encoding="utf-8").splitlines()}
ids = a.ids.split(",")
missing = [i for i in ids if i not in tasks]
assert not missing, f"not in MetSWE: {missing}"


async def main():
    ok = 0
    for i in ids:
        t = tasks[i]
        image = f"met-sandbox-{t['repo'].split('/')[1].lower()}:warm"
        task = Task(instance_id=i, repo=t["repo"], base_commit=t["base_commit"], problem_statement=t["problem_statement"],
                    patch=t["patch"], test_patch=t["test_patch"], created_at=t["created_at"])
        config = EvalConfig(tasks_path=HERE / "tasks_final.jsonl", snapshots_dir=Path(a.snapshots),
                            results_dir=Path("/tmp/metswe_verify"), submission_dir=Path("/tmp/metswe_none"),
                            models=ModelRegistry(), image=image, wheels_dir=Path(a.wheels))
        docker = ContainerManager(ContainerConfig(image=image, network_mode="none"))
        rec = {"instance_id": i, "image": image}
        for label, patch in (("empty", ""), ("gold", t["patch"])):
            t0 = time.time()
            r = await verify_task(docker, config, task, Path(a.snapshots) / f"{i}.tgz", agent_patch=patch)
            rec[label] = {"resolved": bool(r.resolved), "exit": r.test_exit_code, "sec": round(time.time() - t0)}
        rec["valid"] = not rec["empty"]["resolved"] and rec["gold"]["resolved"]
        ok += rec["valid"]
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"{i}: empty patch resolved={rec['empty']['resolved']} ({rec['empty']['sec']} s), "
              f"gold patch resolved={rec['gold']['resolved']} ({rec['gold']['sec']} s) -> {'OK' if rec['valid'] else 'FAILED'}",
              flush=True)
    print(f"{ok} / {len(ids)} tasks behave as validated")


os.environ.setdefault("KAGGLE_SANDBOX_DIR", "/mnt/f/kaggle/gemma_agent/data/sandbox")
asyncio.run(main())
